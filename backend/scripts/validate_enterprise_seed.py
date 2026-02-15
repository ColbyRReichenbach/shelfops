#!/usr/bin/env python3
"""
Validate synthetic enterprise seed outputs for integration readiness.

This script checks generated files and performs adapter-level parsing checks for:
  - EDI 846 documents
  - SFTP-style transaction/inventory CSVs
  - Kafka-style JSONL transaction events

Usage:
  python backend/scripts/validate_enterprise_seed.py --input data/seed_smoke
  python backend/scripts/validate_enterprise_seed.py --input data/seed --strict
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from integrations.base import SyncStatus
from integrations.edi_adapter import EDIX12Parser
from integrations.event_adapter import normalize_transaction_event, validate_event
from integrations.sftp_adapter import SFTPAdapter


@dataclass
class ValidationSummary:
    checks_run: int = 0
    checks_passed: int = 0
    checks_failed: int = 0

    def pass_check(self) -> None:
        self.checks_run += 1
        self.checks_passed += 1

    def fail_check(self) -> None:
        self.checks_run += 1
        self.checks_failed += 1


def expect(condition: bool, message: str, summary: ValidationSummary) -> None:
    if condition:
        print(f"  ✅ {message}")
        summary.pass_check()
    else:
        print(f"  ❌ {message}")
        summary.fail_check()


def _first_line(path: Path) -> str:
    with path.open(encoding="utf-8") as f:
        return f.readline().strip()


def validate_structure(seed_dir: Path, strict: bool, summary: ValidationSummary) -> None:
    print("\n[1/5] Validating seed directory structure...")
    required_dirs = ["transactions", "inventory", "edi", "events"]
    for name in required_dirs:
        expect((seed_dir / name).exists(), f"Directory exists: {seed_dir / name}", summary)

    expect((seed_dir / "products.csv").exists(), "File exists: products.csv", summary)
    expect((seed_dir / "stores.csv").exists(), "File exists: stores.csv", summary)

    tx_count = len(list((seed_dir / "transactions").glob("*.csv")))
    inv_count = len(list((seed_dir / "inventory").glob("*.csv")))
    edi_count = len(list((seed_dir / "edi").glob("*.edi")))
    events_count = len(list((seed_dir / "events").glob("*.jsonl")))

    min_tx = 3 if strict else 1
    min_inv = 3 if strict else 1
    min_edi = 5 if strict else 1
    min_events = 1

    expect(tx_count >= min_tx, f"Transactions files >= {min_tx} (found {tx_count})", summary)
    expect(inv_count >= min_inv, f"Inventory files >= {min_inv} (found {inv_count})", summary)
    expect(edi_count >= min_edi, f"EDI files >= {min_edi} (found {edi_count})", summary)
    expect(events_count >= min_events, f"Event files >= {min_events} (found {events_count})", summary)


def validate_csv_headers(seed_dir: Path, summary: ValidationSummary) -> None:
    print("\n[2/5] Validating CSV headers...")
    tx_files = sorted((seed_dir / "transactions").glob("*.csv"))
    inv_files = sorted((seed_dir / "inventory").glob("*.csv"))

    if tx_files:
        tx_header = _first_line(tx_files[0])
        expect(
            "TRANS_ID" in tx_header and "QTY_SOLD" in tx_header and "TRANS_DATE" in tx_header,
            f"Transactions header shape valid ({tx_files[0].name})",
            summary,
        )
    else:
        expect(False, "At least one transactions CSV exists", summary)

    if inv_files:
        inv_header = _first_line(inv_files[0])
        expect(
            "STORE_NBR" in inv_header and "ON_HAND_QTY" in inv_header and "SNAPSHOT_DATE" in inv_header,
            f"Inventory header shape valid ({inv_files[0].name})",
            summary,
        )
    else:
        expect(False, "At least one inventory CSV exists", summary)

    products_header = _first_line(seed_dir / "products.csv")
    expect(
        "sku" in products_header and "gtin" in products_header and "unit_price" in products_header,
        "Products header includes key columns",
        summary,
    )

    stores_header = _first_line(seed_dir / "stores.csv")
    expect(
        "external_code" in stores_header and "name" in stores_header and "state" in stores_header,
        "Stores header includes key columns",
        summary,
    )


def validate_edi(seed_dir: Path, summary: ValidationSummary) -> None:
    print("\n[3/5] Validating EDI files...")
    parser = EDIX12Parser()
    edi_files = sorted((seed_dir / "edi").glob("*.edi"))
    if not edi_files:
        expect(False, "At least one EDI file exists", summary)
        return

    seen_types: set[str] = set()
    type_success = {"846": 0, "856": 0, "810": 0, "850": 0}
    for path in edi_files:
        raw = path.read_text(encoding="utf-8")
        txn_type = parser.detect_transaction_type(raw)
        if not txn_type:
            continue
        seen_types.add(txn_type)

        if txn_type == "846":
            if parser.parse_846(raw):
                type_success["846"] += 1
        elif txn_type == "856":
            if parser.parse_856(raw).items:
                type_success["856"] += 1
        elif txn_type == "810":
            if parser.parse_810(raw).line_items:
                type_success["810"] += 1
        elif txn_type == "850":
            if "ST*850" in raw:
                type_success["850"] += 1

    for edi_type in ("846", "850", "856", "810"):
        expect(edi_type in seen_types, f"EDI type present: {edi_type}", summary)
        expect(type_success[edi_type] > 0, f"EDI type parsed with records: {edi_type}", summary)


def validate_events(seed_dir: Path, summary: ValidationSummary) -> None:
    print("\n[4/5] Validating event JSONL + normalization...")
    event_files = sorted((seed_dir / "events").glob("*.jsonl"))
    if not event_files:
        expect(False, "At least one event JSONL file exists", summary)
        return

    event_file = event_files[0]
    required_fields = ["event_id", "store_id", "timestamp", "items"]
    samples = 0
    normalized_rows = 0

    with event_file.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            event = json.loads(line)
            schema_errors = validate_event(event, {"required_fields": required_fields})
            if schema_errors:
                continue
            rows = normalize_transaction_event(event)
            samples += 1
            normalized_rows += len(rows)
            if samples >= 20:
                break

    expect(samples > 0, f"Validated at least one event sample from {event_file.name}", summary)
    expect(normalized_rows > 0, "Normalized event samples produced transaction rows", summary)


async def validate_sftp_local(seed_dir: Path, summary: ValidationSummary) -> None:
    print("\n[5/5] Validating SFTP adapter local parsing path...")
    tx_files = sorted((seed_dir / "transactions").glob("*.csv"))
    inv_files = sorted((seed_dir / "inventory").glob("*.csv"))
    if not tx_files or not inv_files:
        expect(False, "Transactions and inventory files available for SFTP adapter check", summary)
        return

    with tempfile.TemporaryDirectory(prefix="shelfops_sftp_validate_") as tmp:
        staging = Path(tmp) / "staging"
        archive = Path(tmp) / "archive"
        (staging / "transactions").mkdir(parents=True, exist_ok=True)
        (staging / "inventory").mkdir(parents=True, exist_ok=True)
        archive.mkdir(parents=True, exist_ok=True)

        shutil.copy2(tx_files[0], staging / "transactions" / tx_files[0].name)
        shutil.copy2(inv_files[0], staging / "inventory" / inv_files[0].name)

        adapter = SFTPAdapter(
            customer_id="00000000-0000-0000-0000-000000000001",
            config={
                "local_staging_dir": str(staging),
                "archive_dir": str(archive),
                "delimiter": ",",
            },
        )

        tx_result = await adapter.sync_transactions()
        inv_result = await adapter.sync_inventory()

        expect(
            tx_result.status in {SyncStatus.SUCCESS, SyncStatus.PARTIAL},
            f"SFTP transactions sync status valid ({tx_result.status.value})",
            summary,
        )
        expect(tx_result.records_processed > 0, "SFTP transactions produced records", summary)
        expect(
            inv_result.status in {SyncStatus.SUCCESS, SyncStatus.PARTIAL},
            f"SFTP inventory sync status valid ({inv_result.status.value})",
            summary,
        )
        expect(inv_result.records_processed > 0, "SFTP inventory produced records", summary)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate enterprise synthetic seed outputs")
    parser.add_argument("--input", type=str, default="data/seed_smoke", help="Seed directory to validate")
    parser.add_argument("--strict", action="store_true", help="Use stricter minimum file-count thresholds")
    args = parser.parse_args()

    seed_dir = Path(args.input)
    summary = ValidationSummary()

    print("=" * 68)
    print("  ShelfOps Enterprise Seed Validator")
    print("=" * 68)
    print(f"  Input:  {seed_dir}")
    print(f"  Strict: {'yes' if args.strict else 'no'}")

    if not seed_dir.exists():
        print(f"\n❌ Seed directory does not exist: {seed_dir}")
        return 2

    validate_structure(seed_dir, args.strict, summary)
    validate_csv_headers(seed_dir, summary)
    validate_edi(seed_dir, summary)
    validate_events(seed_dir, summary)
    asyncio.run(validate_sftp_local(seed_dir, summary))

    print("\n" + "=" * 68)
    print("  Validation Summary")
    print("=" * 68)
    print(f"  Checks run:    {summary.checks_run}")
    print(f"  Checks passed: {summary.checks_passed}")
    print(f"  Checks failed: {summary.checks_failed}")

    if summary.checks_failed > 0:
        print("\n❌ Validation failed. Resolve issues before claiming integration readiness.")
        return 1

    print("\n✅ Validation passed. Seed artifacts are ready for integration test workflows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
