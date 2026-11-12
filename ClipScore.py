#!/usr/bin/env python3
import argparse
import glob
import os
import pathlib
import sys
import pandas as pd
from PIL import Image
import torch
from transformers import CLIPProcessor, CLIPModel

def find_image_path(base_img_dir: str, category: str, image_id) -> str | None:
    category = str(category)
    image_id = str(image_id)
    pattern = os.path.join(base_img_dir, category, f"{image_id}.*")
    matches = glob.glob(pattern)
    if not matches:
        return None
    return matches[0]

def main():
    parser = argparse.ArgumentParser(
        description="Calculate CLIPScore text-to-image alignment for generated captions."
    )
    parser.add_argument(
        "--excel",
        required=True,
        help="Path to the Excel file with columns: category, image_id, caption_ai",
    )
    parser.add_argument(
        "--img-dir",
        default="img",
        help="Base directory containing image subfolders (default: img/).",
    )
    parser.add_argument(
        "--output",
        help="Path for the output Excel file. If omitted, overrides the input file.",
    )
    args = parser.parse_args()

    excel_path = args.excel
    img_dir = args.img_dir
    output_path = args.output if args.output else excel_path

    print(f"Loading Excel file: {excel_path}")
    df = pd.read_excel(excel_path)

    if "caption_ai" not in df.columns:
        print("Error: Excel file must contain a 'caption_ai' column.", file=sys.stderr)
        sys.exit(1)

    df["CLIPScore"] = 0.0

    print("Loading CLIP Model and Processor (openai/clip-vit-base-patch16)...")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = CLIPModel.from_pretrained("openai/clip-vit-base-patch16").to(device)
    processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch16")

    processed_count = 0
    scores_accumulated = []

    print("Processing images row by row...")
    for idx, row in df.iterrows():
        cand_caption = str(row.get("caption_ai", "")).strip()
        category = row.get("category", "")
        image_id = row.get("image_id", "")

        if pd.isna(category) or pd.isna(image_id) or not cand_caption or cand_caption.lower() == "nan":
            continue

        image_path = find_image_path(img_dir, category, image_id)
        if not image_path:
            continue

        try:
            # Load and process image & text
            image = Image.open(image_path).convert("RGB")
            inputs = processor(text=[cand_caption], images=image, return_tensors="pt", padding=True).to(device)
            
            with torch.no_grad():
                outputs = model(**inputs)
                
            # Extract logit scale and calculate alignment score
            # CLIPScore standard scales logit similarity by 2.5 to map values ~ 0-100
            logits_per_image = outputs.logits_per_image
            clip_score_val = round(logits_per_image.item(), 2)
            
            df.at[idx, "CLIPScore"] = clip_score_val
            scores_accumulated.append(clip_score_val)
            processed_count += 1
            
        except Exception as e:
            print(f"[Row {idx}] Error evaluating image {image_id}: {e}", file=sys.stderr)
            df.at[idx, "CLIPScore"] = 0.0

    print(f"Writing updated metrics to: {output_path}")
    df.to_excel(output_path, index=False)

    if scores_accumulated:
        avg_clip = sum(scores_accumulated) / len(scores_accumulated)
        print("\n=== Evaluation Results ===")
        print(f"Total Images Evaluated: {processed_count}")
        print(f"Average CLIP Score: {avg_clip:.2f}")
        print("==========================")
    else:
        print("No rows were successfully evaluated.")

if __name__ == "__main__":
    main()