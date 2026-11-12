import pandas as pd
import argparse
import sys
import os
import glob
import torch

from PIL import Image
from transformers import CLIPProcessor, CLIPModel
from bert_score import BERTScorer
from sacrebleu import sentence_bleu, corpus_bleu
from rouge_score import rouge_scorer

#EXCEL_PATH = "data/image_metadata_with_ai.xlsx"   # change if needed

CATEGORIES = ["Reflector", "RU", "RU-Montage", "Visits"]

# Find Image path for CLIPScore
def find_image_path(base_img_dir: str, category: str, image_id) -> str | None:
    category = str(category)
    image_id = str(image_id)
    pattern = os.path.join(base_img_dir, category, f"{image_id}.*")
    matches = glob.glob(pattern)
    return matches[0] if matches else None


def compute_bleu_rouge(references, hypotheses):
    """
    references: list of reference strings (human captions)
    hypotheses: list of hypothesis strings (AI captions)
    returns: dict with BLEU, ROUGE-1, ROUGE-L (F1)
    """
    # ---- BLEU (SacreBLEU) ----
    bleu = corpus_bleu(hypotheses, [references])
    bleu_score = bleu.score  # corpus BLEU

    # ---- ROUGE (rouge-score) ----
    scorer = rouge_scorer.RougeScorer(['rouge1', 'rougeL'], use_stemmer=True)

    rouge1_f = 0.0
    rougeL_f = 0.0
    n = len(hypotheses)

    for ref, hyp in zip(references, hypotheses):
        scores = scorer.score(ref, hyp)
        rouge1_f += scores['rouge1'].fmeasure
        rougeL_f += scores['rougeL'].fmeasure

    rouge1_f = (rouge1_f/max(n, 1)) * 100.0  # convert to percentage
    rougeL_f = (rougeL_f/max(n, 1)) * 100.0

    return {
        "BLEU": bleu_score,
        "ROUGE-1_F": rouge1_f,
        "ROUGE-L_F": rougeL_f,
    }


def main(EXCEL_PATH, IMG_DIR):
    # ---- Load Excel ----
    df = pd.read_excel(EXCEL_PATH)

    for col in ["BLEU", "ROUGE-1_F", "ROUGE-L_F", "BERTScore", "CLIPScore"]:
        if col not in df.columns:
            df[col] = 0.0

    scorer = rouge_scorer.RougeScorer(['rouge1', 'rougeL'], use_stemmer=True)

    print("Loading BERTScore model.....")
    bert_scorer = BERTScorer(lang="en", rescale_with_baseline=True)

    print("Loading CLIPScore model.....")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch16")
    clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch16").to(device)

    print("Calculating row-by-row sentence metrics...")

    for idx, row in df.iterrows():
        ref = row.get("caption", None)
        hyp = row.get("caption_ai", None)
        
        cat = row.get("category", None)
        img_id = row.get("image_id", None)

        ref = str(ref).strip() if pd.notna(ref) else ""
        hyp = str(hyp).strip() if pd.notna(hyp) else ""

        if ref and hyp:
            bleu_score = sentence_bleu(hyp.lower(), [ref.lower()]).score
            rouge_scores = scorer.score(ref, hyp)
            
            df.at[idx, "BLEU"] = round(bleu_score,2)
            df.at[idx, "ROUGE-1_F"] = round(rouge_scores['rouge1'].fmeasure * 100.0, 4)
            df.at[idx, "ROUGE-L_F"] = round(rouge_scores['rougeL'].fmeasure * 100.0, 4)
            
            # BERTScore
            _, _, bert_f1 = bert_scorer.score([hyp], [ref])
            df.at[idx, "BERTScore"] = round(bert_f1.item() * 100.0, 2)

            # CLIPScore
            img_path = find_image_path(IMG_DIR, cat, img_id)
            if img_path and os.path.exists(img_path):
                try:
                    image = Image.open(img_path).convert("RGB")
                    inputs = clip_processor(text=[hyp], images=image, return_tensors="pt", padding=True).to(device)
                    with torch.no_grad():
                        outputs = clip_model(**inputs)
                    clip_score_val = outputs.logits_per_image.item()
                    df.at[idx, "CLIPScore"] = round(clip_score_val, 2)

                except Exception as e:
                    print(f"[Row {idx}] CLIP Error on image {img_id}: {e}", file=sys.stderr)
                    df.at[idx, "CLIPScore"] = 0.0
        else:
            df.at[idx, "BLEU"] = 0.0
            df.at[idx, "ROUGE-1_F"] = 0.0
            df.at[idx, "ROUGE-L_F"] = 0.0
            df.at[idx, "BERTScore"] = 0.0
            df.at[idx, "CLIPScore"] = 0.0

    print(f"Saving updated metrics back to: {EXCEL_PATH}")
    df.to_excel(EXCEL_PATH, index=False)
    print("Save complete.\n")

    # Keep only rows where both captions are non-empty
    def non_empty(x):
        return isinstance(x, str) and x.strip() != ""

    df_eval = df[df["caption"].apply(non_empty) & df["caption_ai"].apply(non_empty)]

    if df_eval.empty:
        print("No rows with both human and AI captions available for evaluation.")
        return

    # ---- Overall metrics ----
    refs_all = df_eval["caption"].tolist()
    hyps_all = df_eval["caption_ai"].tolist()

    overall_scores = compute_bleu_rouge(refs_all, hyps_all)

    #BERTScore and CLIPScore Average
    bert_avg = df_eval["BERTScore"].mean()
    clip_avg = df_eval["CLIPScore"].mean()

    print("=== Overall scores ===")
    print(f"BLEU:       {overall_scores['BLEU']:.4f}")
    print(f"ROUGE-1 F1: {overall_scores['ROUGE-1_F']:.4f}")
    print(f"ROUGE-L F1: {overall_scores['ROUGE-L_F']:.4f}")
    print(f"BERTScore:  {bert_avg:.4f}")
    print(f"CLIPScore:  {clip_avg:.4f}")
    print()

    # ---- Category-level metrics ----
    print("=== Category-level scores ===")

    for cat in CATEGORIES:
        df_cat = df_eval[df_eval["category"] == cat]
        if df_cat.empty:
            print(f"[{cat}] -> no annotated examples, skipping.")
            continue

        refs = df_cat["caption"].tolist()
        hyps = df_cat["caption_ai"].tolist()

        scores = compute_bleu_rouge(refs, hyps)

        cat_bert = df_cat["BERTScore"].mean()
        cat_clip = df_cat["CLIPScore"].mean()

        print(f"\nCategory: {cat}")
        print(f"  #examples: {len(df_cat)}")
        print(f"  BLEU:       {scores['BLEU']:.4f}")
        print(f"  ROUGE-1 F1: {scores['ROUGE-1_F']:.4f}")
        print(f"  ROUGE-L F1: {scores['ROUGE-L_F']:.4f}")
        print(f"  BERTScore:  {cat_bert:.4f}")
        print(f"  CLIPScore:  {cat_clip:.4f}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate image captions")
    parser.add_argument(
        "--excel",
        type=str,
        required=True,
        help="Path to Excel file containing captions"
    )

    parser.add_argument(
        "--img-dir",
        type=str,
        default="img",
        help="Base directory containing image subfolders"
    )

    args = parser.parse_args()
    EXCEL_PATH = args.excel
    IMG_DIR = args.img_dir

    main(args.excel, args.img_dir)
