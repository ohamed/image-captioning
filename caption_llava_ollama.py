#!/usr/bin/env python3
"""
LLaVA Caption Generator via Ollama (Windows-optimized)
Generates image captions for engineering lab photos using local LLaVA model.

Usage:
    python caption_llava_ollama.py --input image_metadata.xlsx --output image_metadata_with_ai.xlsx

Requirements:
    - Python 3.10+
    - pandas, openpyxl, requests
    - Ollama running locally (http://localhost:11434)
    - LLaVA model pulled: ollama pull llava:latest
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


# ============================================================================
# CONFIGURATION
# ============================================================================

OLLAMA_API_URL = "http://localhost:11434/api/generate"
OLLAMA_TIMEOUT = 120  # seconds
#DEFAULT_MODEL = "llava:latest"
DEFAULT_MODEL = "llava:7b"
MAX_RETRIES = 2
RETRY_DELAY_BASE = 1.0  # seconds

#Use one or two sentences (15–35 words total).


PROMPT_TEXT = (
"You are describing technical photos for an engineering lab notebook."
"Describe exactly what is visible, using neutral, technical language."
"Use one or two sentences (12–18 words total)."
"Avoid speculation; do not guess what is not clearly visible."
"Do not use the words 'urn', 'ids', 'idsignature', or 'ers'."
)
"""

#CAPTION_PROMPT_STRICT_LLAVA
PROMPT_TEXT = (
    "SYSTEM: You are a technical captioning engine for engineering lab notebook photos. "
    "Follow the formatting rules exactly.\n"
    "USER: Describe the image using neutral, technical language suitable for engineering documentation. "
    "Describe only what is directly visible (objects, materials, labels, fasteners, tools, and spatial relationships). "
    "Do NOT speculate, infer purpose, or add context not visible in the image. "
    "Write exactly ONE sentence with 12–18 words total. "
    "Failure to follow the sentence count or word limit is an error. "
    "Do not use the words 'urn', 'ids', 'idsignature', or 'ers'.\n"
    "ASSISTANT: "
)
"""

ERROR_MISSING = "[MISSING IMAGE]"
ERROR_FAILED = "[ERROR]"


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def find_image_file(img_root: Path, category: str, image_id: str) -> Optional[Path]:
    """
    Find image file in category directory.
    Handles cases where image_id may or may not include file extension.
    
    Args:
        img_root: Root image directory
        category: Category subdirectory (e.g., 'Reflector')
        image_id: Image filename or partial name
        
    Returns:
        Full Path to image file if found, None otherwise
    """
    category_path = img_root / category
    
    if not category_path.exists():
        return None
    
    # If image_id already has an extension, try exact match first
    if image_id.endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp')):
        full_path = category_path / image_id
        if full_path.exists():
            return full_path
    else:
        # Try common image extensions
        for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp']:
            full_path = category_path / (image_id + ext)
            if full_path.exists():
                return full_path
    
    return None


def image_to_base64(image_path: Path) -> Optional[str]:
    """
    Read image file and encode as base64.
    Returns None if file doesn't exist or can't be read.
    """
    try:
        if not image_path.exists():
            return None
        with open(image_path, "rb") as f:
            image_bytes = f.read()
        return base64.b64encode(image_bytes).decode("utf-8")
    except Exception as e:
        print(f"    ERROR reading image: {e}")
        return None


def test_ollama_connection() -> bool:
    """
    Test if Ollama is running and reachable.
    Returns True if connection successful, False otherwise.
    """
    try:
        response = requests.get(f"{OLLAMA_API_URL.rsplit('/', 1)[0]}/tags", timeout=5)
        return response.status_code == 200
    except requests.exceptions.ConnectionError:
        return False
    except Exception:
        return False


def generate_caption(
    image_base64: str,
    model_name: str = DEFAULT_MODEL,
    max_retries: int = MAX_RETRIES,
) -> Optional[str]:
    """
    Call Ollama API to generate caption for image.
    Includes retry logic for transient failures.

    Args:
        image_base64: Base64-encoded image bytes
        model_name: Ollama model name (e.g., 'llava:latest')
        max_retries: Number of retry attempts

    Returns:
        Caption text on success, None on failure
    """
    payload = {
        "model": model_name,
        "prompt": PROMPT_TEXT,
        "images": [image_base64],
        "stream": False,
    }

    for attempt in range(max_retries + 1):
        try:
            response = requests.post(
                OLLAMA_API_URL,
                json=payload,
                timeout=OLLAMA_TIMEOUT,
            )

            if response.status_code != 200:
                error_text = response.text[:200] if response.text else "No response"
                print(f"    Attempt {attempt + 1}: HTTP {response.status_code} - {error_text}")
                if attempt < max_retries:
                    sleep_time = RETRY_DELAY_BASE * (attempt + 1)
                    time.sleep(sleep_time)
                continue

            data = response.json()
            caption = data.get("response", "").strip()

            if caption:
                return caption

            print(f"    Attempt {attempt + 1}: Empty response from model")
            if attempt < max_retries:
                sleep_time = RETRY_DELAY_BASE * (attempt + 1)
                time.sleep(sleep_time)

        except requests.exceptions.Timeout:
            print(f"    Attempt {attempt + 1}: Request timeout ({OLLAMA_TIMEOUT}s)")
            if attempt < max_retries:
                sleep_time = RETRY_DELAY_BASE * (attempt + 1)
                time.sleep(sleep_time)
        except requests.exceptions.ConnectionError as e:
            print(f"    Attempt {attempt + 1}: Connection error - {e}")
            if attempt < max_retries:
                sleep_time = RETRY_DELAY_BASE * (attempt + 1)
                time.sleep(sleep_time)
        except json.JSONDecodeError as e:
            print(f"    Attempt {attempt + 1}: JSON decode error - {e}")
            if attempt < max_retries:
                sleep_time = RETRY_DELAY_BASE * (attempt + 1)
                time.sleep(sleep_time)
        except Exception as e:
            print(f"    Attempt {attempt + 1}: Unexpected error - {e}")
            if attempt < max_retries:
                sleep_time = RETRY_DELAY_BASE * (attempt + 1)
                time.sleep(sleep_time)

    return None


def process_excel(
    input_file: Path,
    output_file: Path,
    img_root: Path,
    model_name: str = DEFAULT_MODEL,
    overwrite: bool = False,
    limit: Optional[int] = None,
) -> None:
    """
    Main processing function: read Excel, generate captions, write output.

    Args:
        input_file: Path to input Excel file
        output_file: Path to output Excel file
        img_root: Root directory for images
        model_name: Ollama model to use
        overwrite: If True, regenerate even if caption_ai exists
        limit: If set, process only first N rows
    """
    # Load input Excel
    print(f"Loading Excel file: {input_file}")
    try:
        df = pd.read_excel(input_file, engine="openpyxl")
    except Exception as e:
        print(f"ERROR: Failed to read Excel file: {e}")
        sys.exit(1)

    print(f"Loaded {len(df)} rows")

    # Validate required columns
    required_cols = ["project_id", "category", "image_id", "caption"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"ERROR: Missing required columns: {missing_cols}")
        sys.exit(1)

    # Create caption_ai column if it doesn't exist, or convert to string dtype
    if "caption_ai" not in df.columns:
        df["caption_ai"] = ""
    else:
        # Convert to string type to avoid dtype warnings
        df["caption_ai"] = df["caption_ai"].fillna("").astype(str)

    # Apply row limit if specified
    if limit:
        df = df.iloc[:limit].copy()
        print(f"Processing first {limit} rows")
    else:
        df = df.copy()

    print(f"\nStarting caption generation...")
    print(f"  Model: {model_name}")
    print(f"  Overwrite existing: {overwrite}")
    print(f"  Total rows: {len(df)}\n")

    processed = 0
    skipped = 0
    success = 0
    error = 0

    for idx, row in df.iterrows():
        processed += 1
        category = row["category"]
        image_id = row["image_id"]

        # Check if caption_ai already exists (skip if not overwriting)
        existing = row.get("caption_ai", "")
        if existing and str(existing).strip() and not overwrite:
            print(f"[{idx + 1:3d}] SKIP (exists): {image_id}")
            skipped += 1
            continue

        # Find image file (handles missing extension)
        image_path = find_image_file(img_root, category, str(image_id))

        # Check if image exists
        if image_path is None:
            print(f"[{idx + 1:3d}] MISSING: {img_root / category / image_id}")
            df.at[idx, "caption_ai"] = ERROR_MISSING
            error += 1
            continue

        print(f"[{idx + 1:3d}] Processing: {image_path}")

        # Encode image to base64
        image_base64 = image_to_base64(image_path)
        if not image_base64:
            print(f"    -> Failed to encode image")
            df.at[idx, "caption_ai"] = ERROR_FAILED
            error += 1
            continue

        # Generate caption via Ollama
        caption = generate_caption(image_base64, model_name)

        if caption:
            print(f"    ✓ {caption[:70]}...")
            df.at[idx, "caption_ai"] = caption
            success += 1
        else:
            print(f"    ✗ Failed to generate caption")
            df.at[idx, "caption_ai"] = ERROR_FAILED
            error += 1

    # Print summary
    print(f"\n{'=' * 70}")
    print(f"SUMMARY")
    print(f"{'=' * 70}")
    print(f"Processed:  {processed}")
    print(f"Skipped:    {skipped}")
    print(f"Success:    {success}")
    print(f"Errors:     {error}")

    # Save output
    print(f"\nSaving to: {output_file}")
    try:
        df.to_excel(output_file, index=False, engine="openpyxl")
        print(f"✓ Complete!")
    except Exception as e:
        print(f"ERROR: Failed to write output file: {e}")
        sys.exit(1)


# ============================================================================
# CLI & MAIN
# ============================================================================

def main():
    """Parse CLI arguments and run processing pipeline."""
    parser = argparse.ArgumentParser(
        description="Generate image captions using LLaVA via local Ollama",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python caption_llava_ollama.py --input image_metadata.xlsx --output output.xlsx
  python caption_llava_ollama.py --input image_metadata.xlsx --output output.xlsx --limit 5
  python caption_llava_ollama.py --input image_metadata.xlsx --output output.xlsx --overwrite
        """,
    )

    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Input Excel file (XLSX) with image metadata",
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Output Excel file (XLSX) with AI-generated captions",
    )
    parser.add_argument(
        "--img_root",
        type=str,
        default="img",
        help="Root directory containing image subdirectories (default: img)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_MODEL,
        help=f"Ollama model name (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Regenerate captions even if caption_ai is not empty",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only first N rows (useful for testing)",
    )

    args = parser.parse_args()

    # Convert to Path objects
    input_file = Path(args.input)
    output_file = Path(args.output)
    img_root = Path(args.img_root)

    # Validate input file exists
    if not input_file.exists():
        print(f"ERROR: Input file not found: {input_file}")
        sys.exit(1)

    # Validate img_root exists
    if not img_root.exists():
        print(f"ERROR: Image root directory not found: {img_root}")
        sys.exit(1)

    # Test Ollama connection
    print("Checking Ollama connection at http://localhost:11434...")
    if not test_ollama_connection():
        print(
            "ERROR: Ollama is not running at http://localhost:11434\n"
            "Please start Ollama and try again.\n"
            "  - Windows/Mac: Open the Ollama desktop application\n"
            "  - Linux: Run 'ollama serve' in a terminal\n"
        )
        sys.exit(1)
    print("✓ Ollama is running\n")

    # Measure total processing time
    start_time = time.perf_counter()
    
    # Run processing pipeline
    process_excel(
        input_file=input_file,
        output_file=output_file,
        img_root=img_root,
        model_name=args.model,
        overwrite=args.overwrite,
        limit=args.limit,
    )
    
    end_time = time.perf_counter()
    elapsed_sec = end_time - start_time
    print(f"\nTotal processing time: {elapsed_sec:.2f} seconds")


if __name__ == "__main__":
    main()
