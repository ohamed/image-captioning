#!/usr/bin/env python3
import argparse
import pathlib
import sys
import pandas as pd
from bert_score import score

def main():
    parser = argparse.ArgumentParser(
        description="Calculate BERTScore semantic similarity for generated captions."
    )
    parser.add_argument(
        "--excel",
        required=True,
        help="Path to the Excel file containing 'caption' and 'caption_ai' columns.",
    )
    parser.add_argument(
        "--output",
        help="Path for the output Excel file. If omitted, overrides the input file.",
    )
    args = parser.parse_args()

    excel_path = args.excel
    output_path = args.output if args.output else excel_path

    print(f"Loading Excel file: {excel_path}")
    df = pd.read_excel(excel_path)

    # Validate required columns exist
    if "caption" not in df.columns or "caption_ai" not in df.columns:
        print("Error: Excel file must contain both 'caption' and 'caption_ai' columns.", file=sys.stderr)
        sys.exit(1)

    # Initialize or clean column
    df["BERTScore"] = 0.0

    valid_indices = []
    references = []
    candidates = []

    # Collect valid pairs for batch processing (much faster than row-by-row)
    for idx, row in df.iterrows():
        ref = str(row.get("caption", "")).strip()
        cand = str(row.get("caption_ai", "")).strip()

        if ref and cand and ref.lower() != "nan" and cand.lower() != "nan":
            valid_indices.append(idx)
            references.append(ref)
            candidates.append(cand)

    if not candidates:
        print("No valid caption pairs found to evaluate.")
        sys.exit(0)

    print(f"Calculating BERTScore for {len(candidates)} rows... (Downloads RoBERTa-common on first run)")
    
    # lang="en" automatically sets the recommended roberta-common model
    P, R, F1 = score(candidates, references, lang="en", verbose=False)

    # Map scores back to the dataframe scaled to 0-100
    for i, idx in enumerate(valid_indices):
        f1_score = round(F1[i].item() * 100.0, 2)
        df.at[idx, "BERTScore"] = f1_score

    print(f"Writing updated metrics to: {output_path}")
    df.to_excel(output_path, index=False)

    # Calculate and output summary corpus metric
    avg_score = df.loc[valid_indices, "BERTScore"].mean()
    print("\n=== Evaluation Results ===")
    print(f"Total Rows Evaluated: {len(valid_indices)}")
    print(f"Average BERTScore: {avg_score:.2f}")
    print("==========================")

if __name__ == "__main__":
    main()