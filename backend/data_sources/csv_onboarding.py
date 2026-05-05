from __future__ import annotations

import io
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Integration, IntegrationSyncLog, InventoryLevel, Product, Store, TenantMLReadiness, Transaction
from ml.readiness import ReadinessThresholds, evaluate_and_persist_tenant_readiness

CSV_PROVIDER = "csv"
CSV_INTEGRATION_NAME = "CSV Onboarding"

CSV_REQUIRED_FIELDS = {
    "stores": {"name"},
    "products": {"sku", "name"},
    "transactions": {"date", "store_name", "sku", "quantity"},
    "inventory": {"timestamp", "store_name", "sku", "quantity_on_hand"},
}

CSV_OPTIONAL_FIELDS = {
    "stores": {"address", "city", "state", "zip_code", "lat", "lon", "timezone"},
    "products": {
        "category",
        "subcategory",
        "brand",
        "unit_cost",
        "unit_price",
        "weight",
        "shelf_life_days",
        "is_seasonal",
        "is_perishable",
    },
    "transactions": {"unit_price", "transaction_type", "discount_amount", "external_id"},
    "inventory": {"quantity_on_order", "quantity_reserved", "quantity_available", "source"},
}


@dataclass(frozen=True)
class CsvValidationIssue:
    file_type: str
    severity: str
    message: str
    row_number: int | None = None
    field: str | None = None


def parse_csv_payload(file_type: str, content: str) -> pd.DataFrame:
    try:
        return pd.read_csv(io.StringIO(content.strip()))
    except Exception as exc:
        raise ValueError(f"{file_type}: unable to parse CSV content ({exc})") from exc


async def validate_csv_batch(
    db: AsyncSession,
    *,
    customer_id: uuid.UUID,
    payloads: dict[str, str],
) -> dict[str, Any]:
    parsed: dict[str, pd.DataFrame] = {}
    issues: list[CsvValidationIssue] = []

    existing_store_names = await _existing_store_names(db, customer_id)
    existing_skus = await _existing_product_skus(db, customer_id)

    for file_type, content in payloads.items():
        if not content:
            continue
        if file_type not in CSV_REQUIRED_FIELDS:
            issues.append(CsvValidationIssue(file_type=file_type, severity="error", message="unsupported csv type"))
            continue

        frame = parse_csv_payload(file_type, content)
        parsed[file_type] = frame
        missing = sorted(CSV_REQUIRED_FIELDS[file_type] - set(frame.columns))
        for field in missing:
            issues.append(
                CsvValidationIssue(
                    file_type=file_type,
                    severity="error",
                    message=f"missing required column '{field}'",
                    field=field,
                )
            )

        extra_columns = sorted(set(frame.columns) - (CSV_REQUIRED_FIELDS[file_type] | CSV_OPTIONAL_FIELDS[file_type]))
        for field in extra_columns:
            issues.append(
                CsvValidationIssue(
                    file_type=file_type,
                    severity="warning",
                    message=f"unrecognized column '{field}' will be ignored",
                    field=field,
                )
            )

    if "stores" in parsed and "name" in parsed["stores"].columns:
        existing_store_names |= {str(name).strip() for name in parsed["stores"]["name"].dropna().tolist()}
    if "products" in parsed and "sku" in parsed["products"].columns:
        existing_skus |= {str(sku).strip() for sku in parsed["products"]["sku"].dropna().tolist()}

    if "transactions" in parsed:
        issues.extend(
            _validate_reference_rows(parsed["transactions"], "transactions", existing_store_names, existing_skus)
        )
        issues.extend(_validate_datetime_rows(parsed["transactions"], "date", "transactions"))
        issues.extend(_validate_numeric_rows(parsed["transactions"], "quantity", "transactions"))
    if "inventory" in parsed:
        issues.extend(_validate_reference_rows(parsed["inventory"], "inventory", existing_store_names, existing_skus))
        issues.extend(_validate_datetime_rows(parsed["inventory"], "timestamp", "inventory"))
        issues.extend(_validate_numeric_rows(parsed["inventory"], "quantity_on_hand", "inventory"))

    return {
        "valid": not any(issue.severity == "error" for issue in issues),
        "issues": [issue.__dict__ for issue in issues],
        "summary": {
            file_type: {
                "rows": int(len(frame)),
                "columns": list(frame.columns),
            }
            for file_type, frame in parsed.items()
        },
    }


async def ingest_csv_batch(
    db: AsyncSession,
    *,
    customer_id: uuid.UUID,
    payloads: dict[str, str],
) -> dict[str, Any]:
    validation = await validate_csv_batch(db, customer_id=customer_id, payloads=payloads)
    if not validation["valid"]:
        raise ValueError("csv payload validation failed")

    parsed = {file_type: parse_csv_payload(file_type, content) for file_type, content in payloads.items() if content}
    created_counts = {"stores": 0, "products": 0, "transactions": 0, "inventory": 0}
    ingested_at = datetime.utcnow()

    store_map = await _upsert_stores(db, customer_id, parsed.get("stores"))
    product_map = await _upsert_products(db, customer_id, parsed.get("products"))

    if parsed.get("transactions") is not None:
        created_counts["transactions"] = await _ingest_transactions(
            db,
            customer_id=customer_id,
            frame=parsed["transactions"],
            store_map=store_map,
            product_map=product_map,
        )
    if parsed.get("inventory") is not None:
        created_counts["inventory"] = await _ingest_inventory(
            db,
            customer_id=customer_id,
            frame=parsed["inventory"],
            store_map=store_map,
            product_map=product_map,
        )

    created_counts["stores"] = len(store_map)
    created_counts["products"] = len(product_map)

    await _upsert_csv_integration(
        db,
        customer_id=customer_id,
        ingested_at=ingested_at,
        parsed=parsed,
        created_counts=created_counts,
    )
    _record_csv_sync_logs(
        db,
        customer_id=customer_id,
        ingested_at=ingested_at,
        parsed=parsed,
    )

    transactions_df = await _load_customer_transactions_df(db, customer_id=customer_id)
    readiness = await evaluate_and_persist_tenant_readiness(
        db,
        customer_id=customer_id,
        transactions_df=transactions_df,
        candidate_version=None,
        model_name="demand_forecast",
        thresholds=ReadinessThresholds(
            min_history_days=90,
            min_store_count=1,
            min_product_count=5,
            min_accuracy_samples=10,
            accuracy_window_days=30,
        ),
    )
    await db.commit()
    return {"created": created_counts, "readiness": readiness}


async def get_customer_readiness(db: AsyncSession, *, customer_id: uuid.UUID) -> dict[str, Any]:
    result = await db.execute(select(TenantMLReadiness).where(TenantMLReadiness.customer_id == customer_id))
    row = result.scalar_one_or_none()
    if row is None:
        return {"state": "not_started", "reason_code": "no_csv_or_training_history", "snapshot": {}}
    return {"state": row.state, "reason_code": row.reason_code, "snapshot": row.gate_snapshot or {}}


def _validate_reference_rows(
    frame: pd.DataFrame,
    file_type: str,
    valid_store_names: set[str],
    valid_skus: set[str],
) -> list[CsvValidationIssue]:
    issues: list[CsvValidationIssue] = []
    for idx, row in frame.iterrows():
        store_name = str(row.get("store_name", "")).strip()
        sku = str(row.get("sku", "")).strip()
        if store_name and store_name not in valid_store_names:
            issues.append(
                CsvValidationIssue(
                    file_type=file_type,
                    severity="error",
                    message=f"unknown store_name '{store_name}'",
                    row_number=int(idx) + 2,
                    field="store_name",
                )
            )
        if sku and sku not in valid_skus:
            issues.append(
                CsvValidationIssue(
                    file_type=file_type,
                    severity="error",
                    message=f"unknown sku '{sku}'",
                    row_number=int(idx) + 2,
                    field="sku",
                )
            )
    return issues


def _validate_datetime_rows(frame: pd.DataFrame, field: str, file_type: str) -> list[CsvValidationIssue]:
    issues: list[CsvValidationIssue] = []
    parsed = pd.to_datetime(frame[field], errors="coerce")
    for idx, valid in enumerate(parsed.notna().tolist()):
        if not valid:
            issues.append(
                CsvValidationIssue(
                    file_type=file_type,
                    severity="error",
                    message=f"invalid datetime value for '{field}'",
                    row_number=idx + 2,
                    field=field,
                )
            )
    return issues


def _validate_numeric_rows(frame: pd.DataFrame, field: str, file_type: str) -> list[CsvValidationIssue]:
    issues: list[CsvValidationIssue] = []
    parsed = pd.to_numeric(frame[field], errors="coerce")
    for idx, valid in enumerate(parsed.notna().tolist()):
        if not valid:
            issues.append(
                CsvValidationIssue(
                    file_type=file_type,
                    severity="error",
                    message=f"invalid numeric value for '{field}'",
                    row_number=idx + 2,
                    field=field,
                )
            )
    return issues


async def _existing_store_names(db: AsyncSession, customer_id: uuid.UUID) -> set[str]:
    result = await db.execute(select(Store.name).where(Store.customer_id == customer_id))
    return {str(row[0]).strip() for row in result.all() if row[0]}


async def _existing_product_skus(db: AsyncSession, customer_id: uuid.UUID) -> set[str]:
    result = await db.execute(select(Product.sku).where(Product.customer_id == customer_id))
    return {str(row[0]).strip() for row in result.all() if row[0]}


async def _upsert_csv_integration(
    db: AsyncSession,
    *,
    customer_id: uuid.UUID,
    ingested_at: datetime,
    parsed: dict[str, pd.DataFrame],
    created_counts: dict[str, int],
) -> Integration:
    result = await db.execute(
        select(Integration).where(
            Integration.customer_id == customer_id,
            Integration.provider == CSV_PROVIDER,
        )
    )
    integration = result.scalar_one_or_none()
    batch_summary = {
        "file_rows": {file_type: int(len(frame)) for file_type, frame in parsed.items()},
        "created_counts": created_counts,
        "updated_at": ingested_at.isoformat(),
    }
    if integration is None:
        integration = Integration(
            customer_id=customer_id,
            provider=CSV_PROVIDER,
            integration_type="rest_api",
            status="connected",
            last_sync_at=ingested_at,
            config={
                "source_label": CSV_INTEGRATION_NAME,
                "ingest_mode": "manual_upload",
                "last_batch_summary": batch_summary,
            },
        )
        db.add(integration)
        await db.flush()
        return integration

    current_config = integration.config if isinstance(integration.config, dict) else {}
    integration.integration_type = "rest_api"
    integration.status = "connected"
    integration.last_sync_at = ingested_at
    integration.config = {
        **current_config,
        "source_label": CSV_INTEGRATION_NAME,
        "ingest_mode": "manual_upload",
        "last_batch_summary": batch_summary,
    }
    return integration


def _record_csv_sync_logs(
    db: AsyncSession,
    *,
    customer_id: uuid.UUID,
    ingested_at: datetime,
    parsed: dict[str, pd.DataFrame],
) -> None:
    for file_type, frame in parsed.items():
        if frame.empty:
            continue
        db.add(
            IntegrationSyncLog(
                customer_id=customer_id,
                integration_type="CSV",
                integration_name=CSV_INTEGRATION_NAME,
                sync_type=file_type,
                records_synced=int(len(frame)),
                sync_status="success",
                started_at=ingested_at,
                completed_at=ingested_at,
                sync_metadata={
                    "source": "csv_onboarding",
                    "rows": int(len(frame)),
                    "columns": list(frame.columns),
                },
            )
        )


async def _upsert_stores(db: AsyncSession, customer_id: uuid.UUID, frame: pd.DataFrame | None) -> dict[str, uuid.UUID]:
    result = await db.execute(select(Store).where(Store.customer_id == customer_id))
    existing = {store.name: store for store in result.scalars().all()}
    mapping = {name: store.store_id for name, store in existing.items()}
    if frame is None:
        return mapping

    for row in frame.to_dict(orient="records"):
        name = str(row["name"]).strip()
        if name in existing:
            continue
        store = Store(
            customer_id=customer_id,
            name=name,
            address=_optional_str(row.get("address")),
            city=_optional_str(row.get("city")),
            state=_optional_str(row.get("state")),
            zip_code=_optional_str(row.get("zip_code")),
            lat=_optional_float(row.get("lat")),
            lon=_optional_float(row.get("lon")),
            timezone=_optional_str(row.get("timezone")) or "America/New_York",
        )
        db.add(store)
        await db.flush()
        existing[name] = store
        mapping[name] = store.store_id
    return mapping


async def _upsert_products(
    db: AsyncSession, customer_id: uuid.UUID, frame: pd.DataFrame | None
) -> dict[str, uuid.UUID]:
    result = await db.execute(select(Product).where(Product.customer_id == customer_id))
    existing = {product.sku: product for product in result.scalars().all()}
    mapping = {sku: product.product_id for sku, product in existing.items()}
    if frame is None:
        return mapping

    for row in frame.to_dict(orient="records"):
        sku = str(row["sku"]).strip()
        if sku in existing:
            continue
        product = Product(
            customer_id=customer_id,
            sku=sku,
            name=str(row["name"]).strip(),
            category=_optional_str(row.get("category")),
            subcategory=_optional_str(row.get("subcategory")),
            brand=_optional_str(row.get("brand")),
            unit_cost=_optional_float(row.get("unit_cost")),
            unit_price=_optional_float(row.get("unit_price")),
            weight=_optional_float(row.get("weight")),
            shelf_life_days=_optional_int(row.get("shelf_life_days")),
            is_seasonal=_optional_bool(row.get("is_seasonal")),
            is_perishable=_optional_bool(row.get("is_perishable")),
        )
        db.add(product)
        await db.flush()
        existing[sku] = product
        mapping[sku] = product.product_id
    return mapping


async def _ingest_transactions(
    db: AsyncSession,
    *,
    customer_id: uuid.UUID,
    frame: pd.DataFrame,
    store_map: dict[str, uuid.UUID],
    product_map: dict[str, uuid.UUID],
) -> int:
    inserted = 0
    for row in frame.to_dict(orient="records"):
        quantity = int(float(row["quantity"]))
        unit_price = _optional_float(row.get("unit_price")) or 0.0
        db.add(
            Transaction(
                customer_id=customer_id,
                store_id=store_map[str(row["store_name"]).strip()],
                product_id=product_map[str(row["sku"]).strip()],
                timestamp=pd.to_datetime(row["date"]).to_pydatetime(),
                quantity=quantity,
                unit_price=unit_price,
                total_amount=round(quantity * unit_price, 2),
                discount_amount=_optional_float(row.get("discount_amount")) or 0.0,
                transaction_type=row.get("transaction_type") or "sale",
                external_id=row.get("external_id"),
            )
        )
        inserted += 1
    await db.flush()
    return inserted


async def _ingest_inventory(
    db: AsyncSession,
    *,
    customer_id: uuid.UUID,
    frame: pd.DataFrame,
    store_map: dict[str, uuid.UUID],
    product_map: dict[str, uuid.UUID],
) -> int:
    inserted = 0
    for row in frame.to_dict(orient="records"):
        quantity_on_hand = int(float(row["quantity_on_hand"]))
        quantity_on_order = _optional_int(row.get("quantity_on_order")) or 0
        quantity_reserved = _optional_int(row.get("quantity_reserved")) or 0
        quantity_available = _optional_int(row.get("quantity_available"))
        if quantity_available is None:
            quantity_available = max(0, quantity_on_hand - quantity_reserved)
        db.add(
            InventoryLevel(
                customer_id=customer_id,
                store_id=store_map[str(row["store_name"]).strip()],
                product_id=product_map[str(row["sku"]).strip()],
                timestamp=pd.to_datetime(row["timestamp"]).to_pydatetime(),
                quantity_on_hand=quantity_on_hand,
                quantity_on_order=quantity_on_order,
                quantity_reserved=quantity_reserved,
                quantity_available=quantity_available,
                source=row.get("source") or "csv_onboarding",
            )
        )
        inserted += 1
    await db.flush()
    return inserted


async def _load_customer_transactions_df(db: AsyncSession, *, customer_id: uuid.UUID) -> pd.DataFrame:
    result = await db.execute(
        select(
            func.date(Transaction.timestamp).label("date"),
            Transaction.store_id,
            Transaction.product_id,
            func.sum(Transaction.quantity).label("quantity"),
        )
        .where(Transaction.customer_id == customer_id, Transaction.transaction_type == "sale")
        .group_by(func.date(Transaction.timestamp), Transaction.store_id, Transaction.product_id)
        .order_by(func.date(Transaction.timestamp).asc())
    )
    rows = result.all()
    return pd.DataFrame(
        [
            {
                "date": row.date,
                "store_id": str(row.store_id),
                "product_id": str(row.product_id),
                "quantity": float(row.quantity or 0.0),
            }
            for row in rows
        ]
    )


def _optional_float(value: Any) -> float | None:
    if value is None or value == "" or pd.isna(value):
        return None
    return float(value)


def _optional_int(value: Any) -> int | None:
    if value is None or value == "" or pd.isna(value):
        return None
    return int(float(value))


def _optional_bool(value: Any) -> bool:
    if value is None or value == "" or pd.isna(value):
        return False
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _optional_str(value: Any) -> str | None:
    if value is None or value == "" or pd.isna(value):
        return None
    return str(value).strip()
