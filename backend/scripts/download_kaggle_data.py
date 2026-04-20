"""
Legacy Kaggle Dataset Downloader for ShelfOps ML Training

Downloads and preprocesses public retail datasets from Kaggle for
training the demand forecasting models.

Available datasets:
  1. Favorita Grocery Sales (legacy reference)
  2. Walmart Sales Forecasting (legacy weekly reference, not M5)
  3. Rossmann Store Sales (legacy reference)

Note:
  The active ShelfOps roadmap now targets M5/Walmart and FreshRetailNet for
  benchmark evidence. This helper remains only for older Kaggle dataset flows
  already present in the repo.

Prerequisites:
  pip install kaggle
  export KAGGLE_USERNAME=your_username
  export KAGGLE_KEY=your_api_key

Run:
  python scripts/download_kaggle_data.py --dataset favorita
  python scripts/download_kaggle_data.py --dataset all
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

DATASETS = {
    "favorita": {
        "kaggle_id": "c/store-sales-time-series-forecasting",
        "description": "Corporación Favorita Grocery Sales (Ecuador, 3.5M+ rows)",
        "files": [
            "train.csv",  # 3.5M rows of daily store-product sales
            "stores.csv",  # 54 stores with city, state, type, cluster
            "oil.csv",  # Oil prices (macroeconomic feature)
            "transactions.csv",  # Daily transaction counts per store
            "holidays_events.csv",  # Holidays and events
        ],
        "columns_map": {
            "store_nbr": "store_code",
            "family": "category",
            "sales": "quantity_sold",
            "date": "transaction_date",
            "onpromotion": "is_promotional",
        },
    },
    "walmart": {
        "kaggle_id": "c/walmart-recruiting-store-sales-forecasting",
        "description": "Walmart Store Sales (45 stores, weekly department sales)",
        "files": [
            "train.csv",
            "stores.csv",
            "features.csv",  # Temperature, fuel price, CPI, unemployment
        ],
        "columns_map": {
            "Store": "store_code",
            "Dept": "category",
            "Weekly_Sales": "quantity_sold",
            "Date": "transaction_date",
            "IsHoliday": "is_holiday",
        },
    },
    "rossmann": {
        "kaggle_id": "c/rossmann-store-sales",
        "description": "Rossmann Store Sales (1,115 stores, daily sales)",
        "files": [
            "train.csv",
            "store.csv",
        ],
        "columns_map": {
            "Store": "store_code",
            "Sales": "quantity_sold",
            "Date": "transaction_date",
            "Promo": "is_promotional",
            "StateHoliday": "is_holiday",
        },
    },
}


def check_kaggle_credentials() -> bool:
    """Verify Kaggle API credentials are configured."""
    kaggle_json = Path.home() / ".kaggle" / "kaggle.json"
    env_user = os.environ.get("KAGGLE_USERNAME")
    env_key = os.environ.get("KAGGLE_KEY")

    if kaggle_json.exists():
        return True
    if env_user and env_key:
        return True

    print("❌ Kaggle credentials not found!")
    print()
    print("  Option 1: Set environment variables")
    print("    export KAGGLE_USERNAME=your_username")
    print("    export KAGGLE_KEY=your_api_key")
    print()
    print("  Option 2: Create ~/.kaggle/kaggle.json")
    print('    {"username": "your_username", "key": "your_api_key"}')
    print()
    print("  Get your API key at: https://www.kaggle.com/settings")
    return False


def download_dataset(dataset_key: str, output_dir: Path) -> bool:
    """Download a Kaggle dataset."""
    if dataset_key not in DATASETS:
        print(f"❌ Unknown dataset: {dataset_key}")
        print(f"   Available: {', '.join(DATASETS.keys())}")
        return False

    info = DATASETS[dataset_key]
    target_dir = output_dir / dataset_key

    print(f"📥 Downloading: {info['description']}")
    print(f"   Target: {target_dir}")

    try:
        import kaggle

        kaggle.api.authenticate()

        target_dir.mkdir(parents=True, exist_ok=True)
        kaggle.api.competition_download_files(
            info["kaggle_id"].replace("c/", ""),
            path=str(target_dir),
        )

        # Unzip if needed
        for zip_file in target_dir.glob("*.zip"):
            shutil.unpack_archive(str(zip_file), str(target_dir))
            zip_file.unlink()

        print(f"   ✅ Downloaded to {target_dir}")

        # List files
        for f in sorted(target_dir.glob("*.csv")):
            size_mb = f.stat().st_size / (1024 * 1024)
            print(f"      📄 {f.name} ({size_mb:.1f} MB)")

        return True

    except ImportError:
        print("   ❌ 'kaggle' package not installed. Run: pip install kaggle")
        return False
    except Exception as e:
        print(f"   ❌ Download failed: {e}")
        return False


def preprocess_dataset(dataset_key: str, data_dir: Path) -> None:
    """
    Preprocess downloaded data into ShelfOps-compatible format.

    Renames columns to match ShelfOps field names and exports
    to a standardized CSV that the seed_enterprise_data.py
    script or the SFTP adapter can ingest directly.
    """
    import pandas as pd

    info = DATASETS[dataset_key]
    source_dir = data_dir / dataset_key
    output_file = data_dir / f"{dataset_key}_preprocessed.csv"

    if not source_dir.exists():
        print(f"   ⚠️ Dataset not found at {source_dir}, skipping preprocessing")
        return

    print(f"   🔧 Preprocessing {dataset_key}...")

    train_file = source_dir / "train.csv"
    if not train_file.exists():
        print(f"   ⚠️ train.csv not found in {source_dir}")
        return

    df = pd.read_csv(train_file, low_memory=False)
    original_rows = len(df)

    # Rename columns
    df = df.rename(columns=info["columns_map"])

    # Add missing columns with defaults
    if "store_code" not in df.columns:
        df["store_code"] = "STORE_001"
    if "category" not in df.columns:
        df["category"] = "General"

    df.to_csv(output_file, index=False)
    print(f"   ✅ Preprocessed: {original_rows:,} rows → {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Download Kaggle retail datasets for ShelfOps")
    parser.add_argument(
        "--dataset",
        choices=list(DATASETS.keys()) + ["all"],
        required=True,
        help="Legacy Kaggle dataset to download",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/kaggle",
        help="Output directory (default: data/kaggle)",
    )
    parser.add_argument(
        "--preprocess",
        action="store_true",
        help="Preprocess after downloading",
    )
    args = parser.parse_args()

    output_dir = Path(args.output)

    print("=" * 60)
    print("📊 ShelfOps — Legacy Kaggle Dataset Downloader")
    print("=" * 60)

    if not check_kaggle_credentials():
        sys.exit(1)

    datasets_to_download = list(DATASETS.keys()) if args.dataset == "all" else [args.dataset]

    for key in datasets_to_download:
        print()
        success = download_dataset(key, output_dir)
        if success and args.preprocess:
            preprocess_dataset(key, output_dir)

    print()
    print("=" * 60)
    print("✅ Done! Next steps:")
    print("  1. If you are working on legacy/reference data, run the downstream seed or contract flow you need.")
    print(
        "  2. For the active roadmap, use DATA_SOURCES.md and the .codex tasks instead of relying on these Kaggle defaults."
    )
    print("=" * 60)


if __name__ == "__main__":
    main()
