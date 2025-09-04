"""
downsample_olist.py — Script to create a smaller Olist dataset for local testing.

Purpose:
- Reads the full Kaggle Olist CSVs from the `data/` directory.
- Randomly samples ~2,000 rows from each dataset (or fewer if file has <2,000 rows).
- Saves the smaller versions into `data/sample/`.

Why:
- The full Olist dataset is ~100k rows, too large for quick seeding and demo purposes.
- A ~2k row subset is lightweight, faster to seed, and still realistic for a portfolio project.

Usage:
    python scripts/downsample_olist.py
"""

import os
import pandas as pd

# Input folder with full Kaggle Olist datasets
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

# Output folder for smaller sample datasets
SAMPLE_DIR = os.path.join(DATA_DIR, "sample")

# How many rows in the downsampled datasets
SAMPLE_SIZE = 2000

# Files we care about (from Olist Kaggle)
FILES = [
    "olist_orders_dataset.csv",
    "olist_order_items_dataset.csv",
    "olist_customers_dataset.csv",
    "olist_products_dataset.csv",
    "olist_sellers_dataset.csv",
    "olist_order_payments_dataset.csv",
    "olist_order_reviews_dataset.csv",
    "product_category_name_translation.csv",
]

def ensure_sample_dir():
    """Create output dir if not exists."""
    os.makedirs(SAMPLE_DIR, exist_ok=True)

def downsample_file(filename, sample_size=SAMPLE_SIZE):
    """Downsample a single CSV file and save to sample folder."""
    input_path = os.path.join(DATA_DIR, filename)
    output_path = os.path.join(SAMPLE_DIR, filename)

    if not os.path.exists(input_path):
        print(f"⚠️ Skipping {filename}, not found in data/")
        return
    
    print(f"📂 Reading {filename}...")
    df = pd.read_csv(input_path)

    if len(df) > sample_size:
        df_sample = df.sample(n=sample_size, random_state=42)
    else:
        df_sample = df  # keep full dataset if already smaller
    
    df_sample.to_csv(output_path, index=False)
    print(f"✅ Saved {len(df_sample)} rows to {output_path}")

def main():
    ensure_sample_dir()
    for file in FILES:
        downsample_file(file)

if __name__ == "__main__":
    main()


