import pandas as pd
import argparse

from sacrebleu import corpus_bleu
from rouge_score import rouge_scorer

#EXCEL_PATH = "data/image_metadata_with_ai.xlsx"   # change if needed

CATEGORIES = ["Reflector", "RU", "RU-Montage", "Visits"]


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

    rouge1_f /= max(n, 1)
    rougeL_f /= max(n, 1)

    return {
        "BLEU": bleu_score,
        "ROUGE-1_F": rouge1_f,
        "ROUGE-L_F": rougeL_f,
    }


def main(EXCEL_PATH):
    # ---- Load Excel ----
    df = pd.read_excel(EXCEL_PATH)

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

    print("=== Overall corpus-level scores ===")
    print(f"BLEU:       {overall_scores['BLEU']:.2f}")
    print(f"ROUGE-1 F1: {overall_scores['ROUGE-1_F']:.4f}")
    print(f"ROUGE-L F1: {overall_scores['ROUGE-L_F']:.4f}")
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

        print(f"\nCategory: {cat}")
        print(f"  #examples: {len(df_cat)}")
        print(f"  BLEU:       {scores['BLEU']:.2f}")
        print(f"  ROUGE-1 F1: {scores['ROUGE-1_F']:.4f}")
        print(f"  ROUGE-L F1: {scores['ROUGE-L_F']:.4f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate image captions")
    parser.add_argument(
        "--excel",
        type=str,
        required=True,
        help="Path to Excel file containing captions"
    )

    args = parser.parse_args()
    EXCEL_PATH = args.excel

    main(EXCEL_PATH)

