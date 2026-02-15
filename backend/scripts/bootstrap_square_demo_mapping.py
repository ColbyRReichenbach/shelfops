#!/usr/bin/env python3
"""Bootstrap per-customer Square demo mapping config.

Usage:
  python backend/scripts/bootstrap_square_demo_mapping.py --customer-id <uuid>
  python backend/scripts/bootstrap_square_demo_mapping.py --customer-id <uuid> --seed-demo-mappings
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Add backend/ to import path when run as a script.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import get_settings
from db.models import Customer, Integration, Product, Store

DEFAULT_CUSTOMER_ID = "00000000-0000-0000-0000-000000000001"


def _as_config_map(raw: Any) -> dict[str, Any]:
    return dict(raw) if isinstance(raw, dict) else {}


def _build_demo_map(prefix: str, internal_ids: list[str]) -> dict[str, str]:
    ordered = sorted({str(v) for v in internal_ids if v})
    return {f"{prefix}_{idx:03d}": internal_id for idx, internal_id in enumerate(ordered, start=1)}


async def _bootstrap(args: argparse.Namespace) -> dict[str, Any]:
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    customer_uuid = uuid.UUID(args.customer_id)

    try:
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as db:
            customer = await db.get(Customer, customer_uuid)
            if customer is None:
                raise ValueError(f"Customer not found: {customer_uuid}")

            integration: Integration | None
            created = False

            if args.integration_id:
                integration_uuid = uuid.UUID(args.integration_id)
                integration = await db.get(Integration, integration_uuid)
                if integration is None:
                    raise ValueError(f"Integration not found: {integration_uuid}")
                if str(integration.customer_id) != str(customer_uuid):
                    raise ValueError(
                        f"Integration {integration_uuid} belongs to customer {integration.customer_id}, "
                        f"not {customer_uuid}"
                    )
                if integration.provider != "square":
                    raise ValueError(f"Integration provider must be 'square', got '{integration.provider}'")
            else:
                result = await db.execute(
                    select(Integration).where(
                        Integration.customer_id == customer_uuid,
                        Integration.provider == "square",
                    )
                )
                integration = result.scalar_one_or_none()

            if integration is None:
                if not args.create_if_missing:
                    raise ValueError("No square integration found and --no-create-if-missing was set")
                integration = Integration(
                    customer_id=customer_uuid,
                    provider="square",
                    integration_type="rest_api",
                    status=args.status,
                    config={},
                )
                db.add(integration)
                await db.flush()
                created = True

            before = _as_config_map(integration.config)
            after = dict(before)
            after["square_synthesize_demo_mappings"] = not args.disable_synthesis

            store_seeded = 0
            product_seeded = 0
            if args.seed_demo_mappings:
                store_rows = await db.execute(select(Store.store_id).where(Store.customer_id == customer_uuid))
                product_rows = await db.execute(select(Product.product_id).where(Product.customer_id == customer_uuid))

                demo_store_map = _build_demo_map("demo_loc", [str(row.store_id) for row in store_rows.all()])
                demo_product_map = _build_demo_map("demo_catalog", [str(row.product_id) for row in product_rows.all()])

                existing_store_map = _as_config_map(after.get("square_location_to_store"))
                existing_product_map = _as_config_map(after.get("square_catalog_to_product"))

                if args.overwrite_existing_mappings or not existing_store_map:
                    after["square_location_to_store"] = demo_store_map
                    store_seeded = len(demo_store_map)
                if args.overwrite_existing_mappings or not existing_product_map:
                    after["square_catalog_to_product"] = demo_product_map
                    product_seeded = len(demo_product_map)

            changed_keys = sorted(k for k in after if before.get(k) != after.get(k))
            if changed_keys:
                integration.config = after

            if args.dry_run:
                await db.rollback()
            else:
                await db.commit()

            return {
                "status": "success",
                "customer_id": str(customer_uuid),
                "integration_id": str(integration.integration_id),
                "created_integration": created,
                "dry_run": args.dry_run,
                "synthesis_enabled": bool(after.get("square_synthesize_demo_mappings")),
                "seed_demo_mappings": bool(args.seed_demo_mappings),
                "seeded_store_mappings": store_seeded,
                "seeded_product_mappings": product_seeded,
                "store_mapping_count": len(_as_config_map(after.get("square_location_to_store"))),
                "product_mapping_count": len(_as_config_map(after.get("square_catalog_to_product"))),
                "changed_keys": changed_keys,
            }
    finally:
        await engine.dispose()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Enable Square demo mapping synthesis for a customer integration")
    parser.add_argument("--customer-id", default=DEFAULT_CUSTOMER_ID, help="Target customer UUID")
    parser.add_argument("--integration-id", default=None, help="Optional specific integration UUID")
    parser.add_argument(
        "--status",
        default="pending",
        choices=["connected", "disconnected", "error", "pending"],
        help="Status used only when creating a new integration",
    )
    parser.add_argument(
        "--create-if-missing",
        action="store_true",
        default=True,
        help="Create a square integration when one does not exist (default: true)",
    )
    parser.add_argument(
        "--no-create-if-missing",
        dest="create_if_missing",
        action="store_false",
        help="Fail instead of creating a square integration when missing",
    )
    parser.add_argument(
        "--disable-synthesis",
        action="store_true",
        help="Disable synthesis instead of enabling it",
    )
    parser.add_argument(
        "--seed-demo-mappings",
        action="store_true",
        help="Seed deterministic demo location/catalog maps from existing stores/products",
    )
    parser.add_argument(
        "--overwrite-existing-mappings",
        action="store_true",
        help="Replace existing square_location_to_store and square_catalog_to_product",
    )
    parser.add_argument("--dry-run", action="store_true", help="Compute changes and print result without committing")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    result = asyncio.run(_bootstrap(args))
    if args.pretty:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
