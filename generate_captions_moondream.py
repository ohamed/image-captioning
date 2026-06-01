#!/usr/bin/env python3
import argparse
import glob
import os
import pathlib
import subprocess
import sys
from evaluate_captions import compute_bleu_rouge
import pandas as pd

import json
import re

def clean_caption(text: str) -> str:
    if not isinstance(text, str):
        return ""

    original = text.strip()
    if not original:
        return ""

    t = original.lower().strip()

    # 1) Handle idsignature hallucination early
    if t.startswith("idsignature"):
        return "Metal label plate"

    # 2) Normalize 'urn' -> 'container(s)' (if 'urn' is not meaningful in your domain)
    t = re.sub(r"\burns?\b", "containers", t)

    # 3) Map very generic boilerplate to something short but useful
    if re.match(r"containers are used to hold chemicals( and other materials)?\.?$", t):
        return "Chemical containers in a lab"
    if re.match(r"containers are used to hold liquids\.?$", t):
        return "Containers for liquids in a lab"

    # 4) Remove generic trailing boilerplate fragments if present
    t = re.sub(r"are used to hold.*", "", t).strip()
    t = re.sub(r"are used to.*", "", t).strip()

    # 5) Split into words to handle truncation and very short captions
    words = t.split()

    # Drop incomplete tail words like "and", "a", "an", "the", "with", "that"
    while words and words[-1] in {"and", "a", "an", "the", "with", "that", "this", "these"}:
        words.pop()

    # If we removed everything or it's too short, fall back to a safe generic
    if len(words) < 3:
        return "Containers and equipment in a lab"

    # 6) Deduplicate adjacent words
    cleaned_words = []
    for w in words:
        if not cleaned_words or cleaned_words[-1] != w:
            cleaned_words.append(w)

    t = " ".join(cleaned_words)

    # 7) Capitalize first letter
    t = t[0].upper() + t[1:]

    # 8) Strip trailing period (optional)
    t = t.rstrip(".")

    return t


def find_image_path(base_img_dir: str, category: str, image_id) -> str | None:
    """
    Find the image file for a given category and image_id under:
        base_img_dir/<category>/<image_id>.*
    Returns the first match or None if not found.
    """
    category = str(category)
    image_id = str(image_id)

    pattern = os.path.join(base_img_dir, category, f"{image_id}.*")
    matches = glob.glob(pattern)

    if not matches:
        return None

    # If there are multiple, just take the first one
    return matches[0]


def normalize_for_ollama(image_path: str) -> str:
    """
    Convert a Windows-style path to the Unix-like style that Moondream
    expects in the prompt, e.g.:

        img\\Reflector\\2018... -> ./img/Reflector/2018...

    """
    # Replace backslashes with forward slashes
    p = image_path.replace("\\", "/")

    # Ensure it starts with "./" (like your working example)
    if not p.startswith("./") and not p.startswith("/"):
        p = "./" + p.lstrip("./")

    return p


def generate_caption_with_moondream(image_path: str,
                                    model: str = "moondream:1.8b") -> str | None:
    """
    Call `ollama run moondream:1.8b` on an image and return the caption text.

    We mimic the working manual command:

        ollama run moondream:1.8b "Describe this image ... ./img/Reflector/xxx.jpg"
    """
    
    ### Shor ###
    """
    base_prompt = (
        "Describe this image in one short sentence (maximum 12 words). "
        "Use simple language."
    )
    """
    
    """
    base_prompt = (
        "You are describing technical photos for an engineering lab notebook. "
        "Describe exactly what is visible, using neutral, technical language. "
        "Do not use the words 'urn', 'ids', 'idsignature', or 'ers'. "
        "Use at most 12 words in a single short sentence."
    )

    base_prompt = (
        "You are describing technical photos for an engineering lab notebook. "
        "Describe exactly what is visible, using neutral, technical language. "
        "Do not use the words 'urn', 'ids', 'idsignature', or 'ers'. "
        "Write one clear technical sentence of approximately 12 to 18 words."
    )
    """
    
    base_prompt = (
        "You are an expert technical documenter describing engineering lab images. "
        "Provide an objective, detailed caption of what is visually present. "
        "Identify visible objects, materials, quantities, shapes, labels, and spatial relationships. "
        "Describe tools, components, calibration items, or mechanical parts when clearly visible. "
        "Use precise, neutral technical language and avoid speculation. "
        "Do not use the words 'urn', 'ids', 'idsignature', or 'ers'. "
        "Write one or two sentences with a total length between 15 and 35 words."
    )

    image_token = normalize_for_ollama(image_path)
    full_prompt = f"{base_prompt} {image_token}"

    cmd = ["ollama", "run", model, full_prompt]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",  # or "ignore"
            check=True,
        )
    except FileNotFoundError:
        print(
            "Error: `ollama` command not found. "
            "Make sure Ollama is installed and on your PATH.",
            file=sys.stderr,
        )
        return None
    except subprocess.CalledProcessError as e:
        print(
            f"Error while calling Ollama for image {image_path}:\n"
            f"STDOUT:\n{e.stdout}\n\nSTDERR:\n{e.stderr}",
            file=sys.stderr,
        )
        return None

    output = result.stdout.strip()
    if not output:
        print(f"No output from Ollama for image {image_path}", file=sys.stderr)
        return None

    # Example stdout:
    #   Added image './img/Reflector/20180105_101214.jpg'
    #   urn with a silver lid ...
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines:
        return None

    caption = lines[-1]

    # Enforce a hard 12-word limit
    words = caption.split()
    if len(words) > 12:
        caption = " ".join(words[:12])

    return caption


def main():
    parser = argparse.ArgumentParser(
        description="Fill the caption_ai column using Moondream (Ollama)."
    )
    parser.add_argument(
        "--excel",
        required=True,
        help="Path to the input Excel file (with columns: project_id, category, image_id, caption, caption_ai).",
    )
    parser.add_argument(
        "--output",
        help=(
            "Path for the output Excel file. "
            "If omitted, will save as <input_stem>_with_ai<suffix>."
        ),
    )
    parser.add_argument(
        "--img-dir",
        default="img",
        help="Base directory containing image subfolders (default: img/).",
    )
    parser.add_argument(
        "--model",
        default="moondream:1.8b",
        help="Ollama model name to use (default: moondream:1.8b).",
    )

    args = parser.parse_args()

    excel_path = args.excel
    img_dir = args.img_dir
    model_name = args.model

    print(f"Loading Excel file: {excel_path}")
    df = pd.read_excel(excel_path)

    # Ensure caption_ai column exists
    if "caption_ai" not in df.columns:
        print("caption_ai column not found; creating it.")
        df["caption_ai"] = ""
    else:
        df["caption_ai"] = df["caption_ai"].astype("string")

    for col in ["BLEU", "ROUGE-1_F", "ROUGE-L_F"]:
        if col not in df.columns:
            df[col] = 0.0

    processed = 0

    # Iterate over rows
    for idx, row in df.iterrows():
        value = row.get("caption_ai", None)
        # Treat NaN as empty; only skip if it's non-empty real text
        if pd.notna(value) and str(value).strip():
            continue

        category = row.get("category", "")
        image_id = row.get("image_id", "")

        if pd.isna(category) or pd.isna(image_id):
            print(
                f"[Row {idx}] Missing category or image_id, skipping.",
                file=sys.stderr,
            )
            continue

        image_path = find_image_path(img_dir, category, image_id)
        if not image_path:
            print(
                f"[Row {idx}] No image found for category='{category}', "
                f"image_id='{image_id}', skipping.",
                file=sys.stderr,
            )
            continue

        print(f"[Row {idx}] Generating caption for image: {image_path}")
        
        caption = generate_caption_with_moondream(image_path, model=model_name)
        
        if caption is None:
            print(f"[Row {idx}] Failed to generate caption for image '{image_id}'.", file=sys.stderr)
            continue

        ### 11-12-2025 OH:
        cleaned_caption = clean_caption(caption)
        
        if cleaned_caption == "":
            cleaned_caption = caption.strip().capitalize()

        df.at[idx, "caption_ai"] = cleaned_caption
        
        processed += 1
        #print(f"[Row {idx}] caption_ai = {cleaned_caption}")
        print(f"[Row {idx}] cleaned = '{cleaned_caption}'")

        # Metrics computation
        x_caption = str(row.get("caption", "")).strip()

        if x_caption and cleaned_caption:
            scores = compute_bleu_rouge([x_caption], [cleaned_caption])
            df.at[idx, "BLEU"] = scores["BLEU"]
            df.at[idx, "ROUGE-1_F"] = scores["ROUGE-1_F"]
            df.at[idx, "ROUGE-L_F"] = scores["ROUGE-L_F"]

            print(f"[Row {idx}] BLEU={scores['BLEU']:.2f}, ROUGE-1_F={scores['ROUGE-1_F']:.4f}, ROUGE-L_F={scores['ROUGE-L_F']:.4f}")
        
        
    # Determine output path
    if args.output:
        output_path = args.output
    else:
        p = pathlib.Path(excel_path)
        output_path = str(p.with_name(p.stem + "_with_ai" + p.suffix))

    print(f"Processed rows with new captions: {processed}")
    print(f"Writing updated Excel file to: {output_path}")
    df.to_excel(output_path, index=False)
    print("Done.")

if __name__ == "__main__":
    main()