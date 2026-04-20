from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_tenant_db
from data_sources.csv_onboarding import get_customer_readiness, ingest_csv_batch, validate_csv_batch

router = APIRouter(prefix="/api/v1/data", tags=["data"])


class CsvOnboardingRequest(BaseModel):
    stores_csv: str | None = None
    products_csv: str | None = None
    transactions_csv: str | None = None
    inventory_csv: str | None = None


@router.post("/csv/validate")
async def validate_csv_onboarding(
    body: CsvOnboardingRequest,
    db: AsyncSession = Depends(get_tenant_db),
    user: dict = Depends(get_current_user),
):
    payloads = {
        "stores": body.stores_csv,
        "products": body.products_csv,
        "transactions": body.transactions_csv,
        "inventory": body.inventory_csv,
    }
    return await validate_csv_batch(db, customer_id=UUID(str(user["customer_id"])), payloads=payloads)


@router.post("/csv/ingest")
async def ingest_csv_onboarding(
    body: CsvOnboardingRequest,
    db: AsyncSession = Depends(get_tenant_db),
    user: dict = Depends(get_current_user),
):
    payloads = {
        "stores": body.stores_csv,
        "products": body.products_csv,
        "transactions": body.transactions_csv,
        "inventory": body.inventory_csv,
    }
    try:
        return await ingest_csv_batch(db, customer_id=UUID(str(user["customer_id"])), payloads=payloads)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/readiness")
async def get_data_readiness(
    db: AsyncSession = Depends(get_tenant_db),
    user: dict = Depends(get_current_user),
):
    return await get_customer_readiness(db, customer_id=UUID(str(user["customer_id"])))
