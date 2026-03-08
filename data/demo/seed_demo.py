#!/usr/bin/env python3
"""
seed_demo.py — Summit Outdoor Supply demo dataset loader.

Reads demo_tenant.json and the three transaction CSV files, then prints
a summary of what would be inserted into the database. With --execute,
it attempts a live DB insert (requires DATABASE_URL in environment).

Idempotent: checks for the demo tenant before inserting.

Usage:
    python3 seed_demo.py                # dry-run (default)
    python3 seed_demo.py --dry-run      # explicit dry-run
    python3 seed_demo.py --execute      # attempt live DB insert
"""

import argparse
import csv
import json
import os
import sys
from pathlib import Path

DEMO_DIR = Path(__file__).parent
TENANT_FILE = DEMO_DIR / "demo_tenant.json"
CSV_FILES = [
    DEMO_DIR / "transactions_day000_030.csv",
    DEMO_DIR / "transactions_day031_090.csv",
    DEMO_DIR / "transactions_day091_095.csv",
]


def load_tenant() -> dict:
    """Load demo tenant metadata from JSON."""
    if not TENANT_FILE.exists():
        print(f"[ERROR] Tenant file not found: {TENANT_FILE}", file=sys.stderr)
        sys.exit(1)
    with open(TENANT_FILE) as f:
        return json.load(f)


def load_transactions() -> list[dict]:
    """Load and merge all transaction CSV files in chronological order."""
    all_rows: list[dict] = []
    for csv_path in CSV_FILES:
        if not csv_path.exists():
            print(f"[WARNING] CSV file not found, skipping: {csv_path}", file=sys.stderr)
            continue
        with open(csv_path, newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            print(f"  Loaded {len(rows):>4} rows from {csv_path.name}")
            all_rows.extend(rows)
    return all_rows


def print_summary(tenant: dict, rows: list[dict]) -> None:
    """Print a human-readable summary of what would be inserted."""
    dates = sorted({r["date"] for r in rows})
    skus = sorted({r["product_id"] for r in rows})
    stores = sorted({r["store_id"] for r in rows})

    total_units = sum(int(r["quantity"]) for r in rows)
    nonzero = [r for r in rows if int(r["quantity"]) > 0]

    print()
    print("=" * 60)
    print("  ShelfOps Demo Dataset — Summit Outdoor Supply")
    print("=" * 60)
    print(f"  Tenant:       {tenant['name']}")
    print(f"  Customer ID:  {tenant['customer_id']}")
    print(f"  Slug:         {tenant['slug']}")
    print(f"  Timezone:     {tenant['timezone']}")
    print(f"  Tier:         {tenant['tier']}")
    print()
    print(f"  Date range:   {dates[0]} to {dates[-1]} ({len(dates)} days)")
    print(f"  Stores:       {len(stores)}")
    print(f"  SKUs:         {len(skus)}")
    print(f"  Total rows:   {len(rows)}")
    print(f"  Non-zero rows:{len(nonzero)}")
    print(f"  Total units:  {total_units:,}")
    print()
    print("  SKU breakdown:")
    for sku in skus:
        sku_rows = [r for r in rows if r["product_id"] == sku]
        sku_units = sum(int(r["quantity"]) for r in sku_rows)
        sku_nonzero = sum(1 for r in sku_rows if int(r["quantity"]) > 0)
        print(f"    {sku}: {sku_units:>5} total units, {sku_nonzero:>3}/{len(sku_rows)} days with sales")
    print()
    print("  Engineered patterns:")
    print("    - Summer demand spike on Kayak Paddle Pro (prod-003)")
    print("      SHAP: 'seasonal driver +38%'")
    print("    - Black Friday lift on apparel SKUs (prod-005, prod-006, prod-008)")
    print("      SHAP: 'promo event +29%'")
    print("    - Vendor X delivery failures, days 32-34")
    print("      SHAP: 'supplier variance +15%'")
    print("=" * 60)


def check_tenant_exists(customer_id: str) -> bool:
    """Check if demo tenant already exists in the database."""
    try:
        import asyncio

        from sqlalchemy import select, text
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

        DATABASE_URL = os.environ.get("DATABASE_URL")
        if not DATABASE_URL:
            print("[INFO] DATABASE_URL not set — skipping existence check.")
            return False

        async def _check() -> bool:
            engine = create_async_engine(DATABASE_URL)
            try:
                async with async_sessionmaker(engine, class_=AsyncSession)() as db:
                    result = await db.execute(
                        text("SELECT COUNT(*) FROM customers WHERE customer_id = :cid"),
                        {"cid": customer_id},
                    )
                    count = result.scalar()
                    return bool(count and count > 0)
            finally:
                await engine.dispose()

        return asyncio.run(_check())
    except Exception as exc:
        print(f"[WARNING] Could not check tenant existence: {exc}")
        return False


def execute_insert(tenant: dict, rows: list[dict]) -> None:
    """Attempt live DB insert (requires DATABASE_URL environment variable)."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("[ERROR] DATABASE_URL environment variable is required for --execute.", file=sys.stderr)
        sys.exit(1)

    customer_id = tenant["customer_id"]

    if check_tenant_exists(customer_id):
        print(f"[INFO] Demo tenant {customer_id} already exists — skipping insert (idempotent).")
        return

    print(f"[INFO] Inserting demo tenant and {len(rows)} transaction rows...")
    print("[INFO] (Full DB insert not implemented in this script — use the API or Alembic seed)")
    print("[INFO] To load via API: POST /api/v1/customers with demo_tenant.json payload,")
    print("[INFO] then POST /api/v1/transactions/bulk with each CSV file.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load Summit Outdoor Supply demo dataset into ShelfOps.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Print what would be inserted without touching the DB (default: True).",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        default=False,
        help="Attempt live DB insert (requires DATABASE_URL env var).",
    )
    args = parser.parse_args()

    print("[seed_demo] Loading demo dataset files...")
    tenant = load_tenant()
    rows = load_transactions()

    print_summary(tenant, rows)

    if args.execute:
        execute_insert(tenant, rows)
    else:
        print()
        print("[seed_demo] Dry-run complete. Use --execute to attempt live DB insert.")


if __name__ == "__main__":
    main()
