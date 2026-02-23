import argparse
import pandas as pd

def count_words(text):
    if isinstance(text, str):
        return len(text.split())
    return 0

def main(file_path):
    df = pd.read_excel(file_path)

    df["caption_word_count"] = df["caption"].apply(count_words)
    df["caption_ai_word_count"] = df["caption_ai"].apply(count_words)

    print("Average length of 'caption':", df["caption_word_count"].mean())
    print("Average length of 'caption_ai':", df["caption_ai_word_count"].mean())

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("file_path", help="Path to the Excel file")
    args = parser.parse_args()

    main(args.file_path)
