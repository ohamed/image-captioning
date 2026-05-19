#!/usr/bin/env python3
"""
Generate image captions using Qwen2.5-VL via Ollama and write them to an Excel file.
Designed for Windows with proper path handling and robust error management.
"""

import argparse
import base64
import json
import sys
import time
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

# Constants
OLLAMA_API_URL = "http://localhost:11434/api/generate"
OLLAMA_TIMEOUT = 120  # seconds
OLLAMA_RETRIES = 2
OLLAMA_RETRY_DELAYS = [1.0, 2.0]  # seconds between retries

# Common image extensions to try
IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif", ".webp"]

"""
CAPTION_PROMPT = (
    "You are describing technical photos for an engineering lab notebook. "
    "Describe exactly what is visible, using neutral, technical language. "
    "Use one or two sentences (15–35 words total). "
    "Avoid speculation; do not guess what is not clearly visible. "
    "Do not use the words 'urn', 'ids', 'idsignature', or 'ers'."
)
"""

"""
CAPTION_PROMPT = (
    "You are describing technical photos for an engineering lab notebook. "
    "Write exactly ONE sentence (12–18 words maximum). "
    "Use neutral, technical language. "
    "Describe only what is directly visible; do not speculate. "
    "Do not use the words 'urn', 'ids', 'idsignature', or 'ers'."
)

### Mid-size Prompt
CAPTION_PROMPT = (
    "You are describing technical photos for an engineering lab notebook. "
    "Example output: 'A reflective surface with mounting hardware visible.' (11 words)\n"
    "Write exactly ONE sentence (12–18 words maximum). "
    "Use neutral, technical language only. "
    "Describe only what is directly visible; never speculate or infer. "
    "Do not use the words 'urn', 'ids', 'idsignature', or 'ers'."
)
"""

CAPTION_PROMPT = (
    "You are an expert technical documenter describing photographs for an engineering laboratory notebook. "
    "Your task is to produce a precise, objective image caption based strictly on what is visually observable. "
    "Describe visible objects, materials, components, surfaces, fasteners, tools, labels, and spatial arrangements "
    "using neutral, technical language suitable for formal engineering documentation. "
    "Do not speculate, infer purpose, or assume functionality beyond what is clearly visible in the image. "
    "Write exactly ONE complete sentence containing between 12 and 18 words. "
    "Avoid adjectives that imply interpretation, condition, or intent unless directly visible. "
    "Do not include explanations, opinions, or contextual background. "
    "Example output: 'A reflective surface with mounting hardware visible.' (11 words). "
    "Do not use the words 'urn', 'ids', 'idsignature', or 'ers'."
)

def encode_image_to_base64(image_path: Path) -> str:
    """Read image file and encode to base64 string."""
    with open(image_path, "rb") as f:
        image_data = f.read()
    return base64.b64encode(image_data).decode("utf-8")


def find_image_file(base_path: Path) -> Optional[Path]:
    """
    Try to find the actual image file by checking common extensions.
    base_path: Path without extension (e.g., img/Reflector/20180105_101214)
    Returns the full Path if found, None otherwise.
    """
    # If the path already exists as-is, return it
    if base_path.exists():
        return base_path

    # Try common image extensions
    for ext in IMAGE_EXTENSIONS:
        candidate = Path(str(base_path) + ext)
        if candidate.exists():
            return candidate

    # Not found
    return None


#88
def call_ollama_api(
    model: str, prompt: str, image_base64: str, retry_count: int = 0
) -> Optional[str]:
    """
    Call Ollama API with image and prompt.
    Returns the caption text or None on error.
    Implements retry logic for transient failures.
    """
    
    """
    payload = {
        "model": model,
        "prompt": prompt,
        "images": [image_base64],
        "stream": False,
    }
    
    """
    payload = {
        "model": model,
        "prompt": prompt,
        "images": [image_base64],
        "stream": False,
        "options": {
            "temperature": 0.75,  # Lower = more deterministic, less verbose
            "top_p": 0.85,        # Reduce sampling diversity
            "top_k": 35,         # Limit token candidates
        }
    }


    try:
        response = requests.post(
            OLLAMA_API_URL, json=payload, timeout=OLLAMA_TIMEOUT
        )

        # Check for HTTP errors
        if response.status_code != 200:
            print(
                f"      [ERROR] Ollama returned status {response.status_code}: {response.text[:100]}"
            )
            return None

        # Parse JSON response
        try:
            response_json = response.json()
        except json.JSONDecodeError as e:
            print(f"      [ERROR] Failed to parse Ollama response JSON: {e}")
            return None

        # Extract caption from response, with fallback logic
        caption = response_json.get("response")
        if caption:
            return caption.strip()

        # Fallback to other plausible fields if "response" is missing
        for fallback_field in ["text", "output", "result"]:
            if fallback_field in response_json:
                caption = response_json[fallback_field]
                if isinstance(caption, str):
                    return caption.strip()

        print(f"      [ERROR] No caption text found in Ollama response")
        return None

    except requests.exceptions.ConnectionError:
        # Ollama not reachable
        return None
    except requests.exceptions.Timeout:
        # Timeout occurred
        if retry_count < OLLAMA_RETRIES:
            print(
                f"      [TIMEOUT] Retrying (attempt {retry_count + 1}/{OLLAMA_RETRIES})..."
            )
            time.sleep(OLLAMA_RETRY_DELAYS[retry_count])
            return call_ollama_api(model, prompt, image_base64, retry_count + 1)
        print(f"      [ERROR] Ollama request timed out after {OLLAMA_RETRIES} retries")
        return None
    except requests.exceptions.RequestException as e:
        # Other request errors
        if retry_count < OLLAMA_RETRIES:
            print(f"      [RETRY] Request error: {e}")
            time.sleep(OLLAMA_RETRY_DELAYS[retry_count])
            return call_ollama_api(model, prompt, image_base64, retry_count + 1)
        print(f"      [ERROR] Ollama request failed: {e}")
        return None


def check_ollama_available() -> bool:
    """Check if Ollama is reachable at the API endpoint."""
    try:
        response = requests.get(
            "http://localhost:11434/api/tags", timeout=5
        )
        return response.status_code == 200
    except Exception:
        return False


def resolve_image_path(img_root: Path, category: str, image_id: str) -> Path:
    """
    Resolve the full image path given root, category, and image_id.
    Windows-safe using pathlib.Path.
    """
    return img_root / category / image_id


def process_images(
    input_file: Path,
    output_file: Path,
    img_root: Path,
    model: str,
    overwrite: bool,
    limit: Optional[int],
) -> None:
    """
    Main processing loop:
    1. Read Excel file
    2. For each row, skip if caption_ai exists (unless --overwrite)
    3. Resolve image path (with extension search)
    4. Call Ollama API
    5. Write result to caption_ai column
    6. Save output Excel file
    """
    # Read input Excel
    print(f"Reading input Excel: {input_file}")
    df = pd.read_excel(input_file, engine="openpyxl")

    # Ensure caption_ai column exists and is of object dtype (to avoid dtype warnings)
    if "caption_ai" not in df.columns:
        print("Creating new 'caption_ai' column")
        df["caption_ai"] = ""
    
    # Ensure caption_ai is object dtype to avoid FutureWarning
    df["caption_ai"] = df["caption_ai"].astype(object)

    # Apply limit if specified
    rows_to_process = df.shape[0]
    if limit is not None:
        rows_to_process = min(limit, rows_to_process)
        print(f"Limiting to first {limit} rows")

    processed_count = 0
    skipped_count = 0
    error_count = 0

    for idx in range(rows_to_process):
        row = df.iloc[idx]

        # Skip if caption_ai already exists and --overwrite not set
        if not overwrite and pd.notna(row.get("caption_ai")) and row["caption_ai"] != "":
            print(f"Row {idx}: Skipping (caption_ai already exists)")
            skipped_count += 1
            continue

        # Extract required fields
        try:
            category = row["category"]
            image_id = row["image_id"]
        except KeyError as e:
            print(f"Row {idx}: [ERROR] Missing required column: {e}")
            df.at[idx, "caption_ai"] = "[ERROR]"
            error_count += 1
            continue

        # Resolve image path (without extension initially)
        base_image_path = resolve_image_path(img_root, category, image_id)

        print(f"Row {idx}: Searching for image: {base_image_path}")

        # Find actual image file (with extension)
        image_path = find_image_file(base_image_path)

        # Check if image exists
        if image_path is None:
            print(f"      [MISSING IMAGE] File not found (tried extensions: {', '.join(IMAGE_EXTENSIONS)})")
            df.at[idx, "caption_ai"] = "[MISSING IMAGE]"
            error_count += 1
            continue

        print(f"      Found: {image_path}")

        # Encode image
        try:
            image_base64 = encode_image_to_base64(image_path)
        except Exception as e:
            print(f"      [ERROR] Failed to read image: {e}")
            df.at[idx, "caption_ai"] = "[ERROR]"
            error_count += 1
            continue

        # Call Ollama API
        caption = call_ollama_api(model, CAPTION_PROMPT, image_base64)

        if caption is None:
            # Error already logged in call_ollama_api
            df.at[idx, "caption_ai"] = "[ERROR]"
            error_count += 1
            continue

        # Success
        print(f"      [OK] Caption generated ({len(caption)} chars)")
        df.at[idx, "caption_ai"] = caption
        processed_count += 1

    # Save output Excel
    print(f"\nSaving output Excel: {output_file}")
    df.to_excel(output_file, index=False, engine="openpyxl")

    # Print summary
    print(f"\n=== Processing Summary ===")
    print(f"Processed:  {processed_count}")
    print(f"Skipped:    {skipped_count}")
    print(f"Errors:     {error_count}")
    print(f"Total:      {rows_to_process}")


def main():
    """Parse arguments and run the caption generation pipeline."""
    parser = argparse.ArgumentParser(
        description="Generate image captions using Qwen2.5-VL via Ollama"
    )
    parser.add_argument("--input", required=True, help="Input Excel file")
    parser.add_argument("--output", required=True, help="Output Excel file")
    parser.add_argument(
        "--img_root",
        default="img",
        help="Root directory for images (default: img)",
    )
    parser.add_argument(
        "--model",
        default="qwen2.5vl:3b",
        help="Ollama model name (default: qwen2.5vl:3b)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Regenerate captions even if caption_ai is non-empty",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only the first N rows",
    )

    args = parser.parse_args()

    # Convert to Path objects
    input_path = Path(args.input)
    output_path = Path(args.output)
    img_root_path = Path(args.img_root)

    # Validate input file exists
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}")
        sys.exit(1)

    # Validate image root exists
    if not img_root_path.exists():
        print(f"Error: Image root directory not found: {img_root_path}")
        sys.exit(1)

    # Check if Ollama is running
    print("Checking Ollama connection...")
    if not check_ollama_available():
        print(
            "Ollama is not running at http://localhost:11434. Start Ollama and try again."
        )
        sys.exit(1)

    print("Ollama is reachable ✓\n")

    # Run processing
    try:
        process_images(
            input_path,
            output_path,
            img_root_path,
            args.model,
            args.overwrite,
            args.limit,
        )
        print("\n✓ Done!")
    except Exception as e:
        print(f"\nFatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
