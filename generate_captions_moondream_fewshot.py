#!/usr/bin/env python3
import argparse
import glob
import os
import pathlib
import subprocess
import sys

import pandas as pd
import json
import re

# GLOBAL CONFIGURATION (Keeps function structures identical to base file)
BASE_PROMPT = (
    "You are a technical documentation expert. Describe what is visible in this image using concise, "
    "lowercase, noun-focused language. Identify objects, materials, components, actions, and spatial arrangements. "
    "Examples of the exact required style:"
    "- A stainless steel disc with a finished surface and 8 threaded holes"
    "- A motor unit is mounted on a test bench, with electrical connections and diagnostic equipment attached."
    "- technician wearing safety glasses operating milling machine while measuring workpiece with digital caliper"
    "Now describe this image in the same objective, noun-heavy technical style: "
)

def clean_caption(text: str) -> str:
    if not isinstance(text, str):
        return ""

    original = text.strip()
    if not original:
        return ""

    t = original.lower().strip()

    if t.startswith("idsignature"):
        return "Metal label plate"

    t = re.sub(r"\burns?\b", "containers", t)

    if re.match(r"containers are used to hold chemicals( and other materials)?\.?$", t):
        return "Chemical containers in a lab"
    if re.match(r"containers are used to hold liquids\.?$", t):
        return "Containers for liquids in a lab"

    t = re.sub(r"are used to hold.*", "", t).strip()
    t = re.sub(r"are used to.*", "", t).strip()

    words = t.split()

    while words and words[-1] in {"and", "a", "an", "the", "with", "that", "this", "these"}:
        words.pop()

    if len(words) < 3:
        return "Containers and equipment in a lab"

    cleaned_words = []
    for w in words:
        if not cleaned_words or cleaned_words[-1] != w:
            cleaned_words.append(w)

    t = " ".join(cleaned_words)
    t = t[0].upper() + t[1:]
    t = t.rstrip(".")

    return t


def find_image_path(base_img_dir: str, category: str, image_id) -> str | None:
    category = str(category)
    image_id = str(image_id)

    pattern = os.path.join(base_img_dir, category, f"{image_id}.*")
    matches = glob.glob(pattern)

    if not matches:
        return None

    return matches[0]


def normalize_for_ollama(image_path: str) -> str:
    p = image_path.replace("\\", "/")
    if not p.startswith("./") and not p.startswith("/"):
        p = "./" + p.lstrip("./")
    return p


# SIGNATURE UNCHANGED from base file
def generate_caption_with_moondream(image_path: str,
                                    model: str = "moondream:1.8b") -> str | None:
    """
    Call `ollama run moondream:1.8b` on an image and return the caption text.
    """
    image_token = normalize_for_ollama(image_path)
    # Uses the global prompt variable
    full_prompt = f"{BASE_PROMPT} {image_token}"

    cmd = ["ollama", "run", model, full_prompt]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
        )
    except FileNotFoundError:
        print("Error: `ollama` command not found.", file=sys.stderr)
        return None
    except subprocess.CalledProcessError as e:
        print(f"Error while calling Ollama for image {image_path}:\n{e.stderr}", file=sys.stderr)
        return None

    output = result.stdout.strip()
    if not output:
        return None

    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines:
        return None

    caption = lines[-1]

    # Clean prompt artifacts if echoed
    caption = caption.replace("Caption:", "").replace("caption:", "").strip()
    if caption.startswith("Example"):
        caption = caption.split(":", 1)[-1].strip()

    words = caption.split()
    if len(words) > 20:
        caption = " ".join(words[:20])

    return caption


def main():
    parser = argparse.ArgumentParser(
        description="Fill the caption_ai column using Moondream (Ollama)."
    )
    parser.add_argument("--excel", required=True, help="Path to the input Excel file.")
    parser.add_argument("--output", help="Path for the output Excel file.")
    parser.add_argument("--img-dir", default="img", help="Base directory containing image subfolders.")
    parser.add_argument("--model", default="moondream:1.8b", help="Ollama model name to use.")

    args = parser.parse_args()

    excel_path = args.excel
    img_dir = args.img_dir
    model_name = args.model

    print(f"Loading Excel file: {excel_path}")
    df = pd.read_excel(excel_path)

    if "caption_ai" not in df.columns:
        print("caption_ai column not found; creating it.")
        df["caption_ai"] = ""
    else:
        df["caption_ai"] = df["caption_ai"].astype("string")

    processed = 0
    
    # Storage list for JSON logs
    prompt_logs = []

    # LOOP STRUCTURE UNCHANGED from base file
    for idx, row in df.iterrows():
        value = row.get("caption_ai", None)
        if pd.notna(value) and str(value).strip():
            continue

        category = row.get("category", "")
        image_id = row.get("image_id", "")

        if pd.isna(category) or pd.isna(image_id):
            print(f"[Row {idx}] Missing category or image_id, skipping.", file=sys.stderr)
            continue

        image_path = find_image_path(img_dir, category, image_id)
        if not image_path:
            print(f"[Row {idx}] No image found, skipping.", file=sys.stderr)
            continue

        print(f"[Row {idx}] Generating caption for image: {image_path}")
        
        # CALL UNCHANGED from base file
        caption = generate_caption_with_moondream(image_path, model=model_name)
        
        if caption is None:
            print(f"[Row {idx}] Failed to generate caption.", file=sys.stderr)
            continue

        cleaned_caption = clean_caption(caption)
        
        if cleaned_caption == "":
            cleaned_caption = caption.strip().capitalize()

        df.at[idx, "caption_ai"] = cleaned_caption
        processed += 1
        print(f"[Row {idx}] cleaned = '{cleaned_caption}'")

        # Log appends cleanly at the end of the loop
        prompt_logs.append({
            "row_index": idx,
            "image_id": image_id,
            "category": category,
            "prompt_used": BASE_PROMPT,
            "raw_model_output": caption,
            "final_cleaned_caption": cleaned_caption
        })

    # Determine output path
    if args.output:
        output_path = args.output
    else:
        p = pathlib.Path(excel_path)
        output_path = str(p.with_name(p.stem + "_fewshot" + p.suffix))

    json_output_path = str(pathlib.Path(output_path).with_suffix(".json"))

    print(f"Processed rows with new captions: {processed}")
    print(f"Writing updated Excel file to: {output_path}")
    df.to_excel(output_path, index=False)
    
    print(f"Writing Prompt Logs to JSON: {json_output_path}")
    with open(json_output_path, "w", encoding="utf-8") as f:
        json.dump(prompt_logs, f, indent=4)
        
    print("Done.")


if __name__ == "__main__":
    main()