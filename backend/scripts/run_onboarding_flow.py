#!/usr/bin/env python3
"""SMB onboarding flow: map -> validate -> canonicalize -> retrain candidate."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Add backend to path when executed as a script.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ml.features import create_features
from ml.train import save_models, train_ensemble
from workers.retrain import _load_profiled_data, _next_version


def main() -> int:
    parser = argparse.ArgumentParser(description="Run SMB onboarding flow with contract-driven canonicalization")
    parser.add_argument("--contract", required=True, help="Path to contract YAML")
    parser.add_argument("--sample-path", required=True, help="Path to raw source sample CSV/JSONL or directory")
    parser.add_argument(
        "--canonical-output-dir",
        default="data/canonical/onboarding",
        help="Directory where canonical_transactions.csv will be written",
    )
    parser.add_argument("--version", default=None, help="Model version (default: auto increment)")
    parser.add_argument("--dataset", default="smb_onboarding", help="Dataset label for tracking")
    parser.add_argument("--promote", action="store_true", help="Promote to champion after training")
    args = parser.parse_args()

    contract_path = Path(args.contract)
    sample_path = Path(args.sample_path)
    output_dir = Path(args.canonical_output_dir)

    version = args.version or _next_version()

    transactions_df = _load_profiled_data(str(contract_path), str(sample_path), str(output_dir))
    features_df = create_features(transactions_df=transactions_df, force_tier="cold_start")
    ensemble_result = train_ensemble(
        features_df=features_df,
        dataset_name=args.dataset,
        version=version,
    )
    save_models(
        ensemble_result=ensemble_result,
        version=version,
        dataset_name=args.dataset,
        promote=args.promote,
    )

    print("Onboarding flow complete")
    print(f"  contract: {contract_path}")
    print(f"  sample_path: {sample_path}")
    print(f"  canonical_output: {output_dir / 'canonical_transactions.csv'}")
    print(f"  model_version: {version}")
    print(f"  promoted: {args.promote}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
