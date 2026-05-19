#!/usr/bin/env python3
import argparse
import glob
import os
import pathlib
import subprocess
import sys

import pandas as pd


def find_image_path(base_img_dir: str, category: str, image_id) -> str | None:
    """
    Find the image file for a given category and image_id under:
        base_img_dir/<category>/<image_id>.*
    Returns the first match or None if not found.
    """
    # Ensure everything is a string
    category = str(category)
    image_id = str(image_id)

    pattern = os.path.join(base_img_dir, category, f"{image_id}.*")
    matches = glob.glob(pattern)

    if not matches:
        return None
    # If there are multiple, just take the first one
    return matches[0]


def generate_caption_with_moondream(image_path: str,
                                    model: str = "moondream:1.8b") -> str | None:
    """
    Call `ollama run moondream:1.8b` on an image and return the caption text.
    Uses a soft constraint in the prompt for one short sentence, max ~12 words.
    """
    prompt = (
        "Describe this image in one short sentence (maximum 12 words). "
        "Use simple language."
    )

    # Command: ollama run moondream:1.8b "prompt text" -i /path/to/image
    cmd = ["ollama", "run", model, prompt, "-i", image_path]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
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
            f"Error while calling Ollama for image {image_path}:\n{e.stderr}",
            file=sys.stderr,
        )
        return None

    # Ollama prints the generated text to stdout. We take the last non-empty line.
    output = result.stdout.strip()
    if not output:
        return None

    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines:
        return None

    caption = lines[-1]

    # Optional: enforce a hard limit of ~12 words if you want to be strict
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

    # Load Excel
    print(f"Loading Excel file: {excel_path}")
    df = pd.read_excel(excel_path)

    # Ensure caption_ai column exists
    if "caption_ai" not in df.columns:
        print("caption_ai column not found; creating it.")
        df["caption_ai"] = ""

    # Iterate over rows
    for idx, row in df.iterrows():
        existing_caption = str(row.get("caption_ai", "") or "").strip()
        if existing_caption:
            # Skip rows where caption_ai is already non-empty
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
            print(
                f"[Row {idx}] Failed to generate caption for image '{image_id}'.",
                file=sys.stderr,
            )
            continue

        df.at[idx, "caption_ai"] = caption
        print(f"[Row {idx}] caption_ai = {caption}")

    # Determine output path
    if args.output:
        output_path = args.output
    else:
        p = pathlib.Path(excel_path)
        output_path = str(p.with_name(p.stem + "_with_ai" + p.suffix))

    # Save updated Excel
    print(f"Writing updated Excel file to: {output_path}")
    df.to_excel(output_path, index=False)
    print("Done.")


if __name__ == "__main__":
    main()
