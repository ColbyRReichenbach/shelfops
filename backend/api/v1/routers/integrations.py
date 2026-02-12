"""
Integrations Router — POS integration management + Square OAuth.
"""

import hashlib
import hmac
import json
from datetime import datetime
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db, get_tenant_db
from core.config import get_settings
from core.security import encrypt
from db.models import Integration

router = APIRouter(prefix="/api/v1/integrations", tags=["integrations"])
settings = get_settings()


# ─── Schemas ────────────────────────────────────────────────────────────────


class IntegrationResponse(BaseModel):
    integration_id: UUID
    customer_id: UUID
    provider: str
    merchant_id: str | None
    status: str
    last_sync_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ─── Square OAuth ───────────────────────────────────────────────────────────


@router.get("/square/connect")
async def square_connect(
    user: dict = Depends(get_current_user),
):
    """Redirect to Square OAuth authorization page."""
    base_url = (
        "https://connect.squareupsandbox.com"
        if settings.square_environment == "sandbox"
        else "https://connect.squareup.com"
    )
    auth_url = (
        f"{base_url}/oauth2/authorize"
        f"?client_id={settings.square_client_id}"
        f"&scope=ITEMS_READ+INVENTORY_READ+ORDERS_READ+MERCHANT_PROFILE_READ"
        f"&state={user['customer_id']}"
    )
    return RedirectResponse(url=auth_url)


@router.get("/square/callback")
async def square_callback(
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
):
    """Handle Square OAuth callback — exchange code for tokens."""
    base_url = (
        "https://connect.squareupsandbox.com"
        if settings.square_environment == "sandbox"
        else "https://connect.squareup.com"
    )

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{base_url}/oauth2/token",
            json={
                "client_id": settings.square_client_id,
                "client_secret": settings.square_client_secret,
                "code": code,
                "grant_type": "authorization_code",
            },
        )

    if response.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to exchange OAuth code")

    token_data = response.json()

    integration = Integration(
        customer_id=state,
        provider="square",
        access_token_encrypted=encrypt(token_data["access_token"]),
        refresh_token_encrypted=encrypt(token_data.get("refresh_token", "")),
        merchant_id=token_data.get("merchant_id"),
        status="connected",
    )
    db.add(integration)
    await db.commit()

    return {"status": "connected", "provider": "square"}


# ─── Square Webhook ─────────────────────────────────────────────────────────


@router.post("/square/webhook")
async def square_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Handle inbound Square webhooks with signature verification."""
    body = await request.body()
    signature = request.headers.get("x-square-hmacsha256-signature", "")

    # Verify signature
    if settings.square_webhook_secret:
        expected = hmac.new(
            settings.square_webhook_secret.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

    payload = json.loads(body)
    event_type = payload.get("type", "")
    _merchant_id = payload.get("merchant_id", "")  # noqa: F841 — used in future event routing

    # Route events to processors
    # TODO: Implement event processors for inventory changes, orders, etc.

    return {"status": "received", "event_type": event_type}


# ─── CRUD ───────────────────────────────────────────────────────────────────


@router.get("/", response_model=list[IntegrationResponse])
async def list_integrations(
    db: AsyncSession = Depends(get_tenant_db),
):
    """List all integrations for the current customer."""
    result = await db.execute(select(Integration))
    return result.scalars().all()


@router.delete("/{integration_id}", status_code=204)
async def disconnect_integration(
    integration_id: UUID,
    db: AsyncSession = Depends(get_tenant_db),
):
    """Disconnect a POS integration."""
    result = await db.execute(select(Integration).where(Integration.integration_id == integration_id))
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    integration.status = "disconnected"
    await db.commit()
