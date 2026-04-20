"""
Integrations Router — POS integration management + Square OAuth.
"""

import base64
import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime, timedelta
from urllib.parse import quote
from uuid import UUID

import httpx
import redis as redis_lib
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db, get_tenant_db
from core.config import get_settings
from core.security import encrypt
from data_sources.square import build_square_mapping_preview
from db.models import Integration, IntegrationSyncLog, WebhookEventLog
from integrations.sla_policy import resolve_sla_hours
from workers.sync import _build_square_id_map, _square_mapping_confirmed, _update_square_mapping_state

router = APIRouter(prefix="/api/v1/integrations", tags=["integrations"])
settings = get_settings()

# ─── Webhook Debounce ────────────────────────────────────────────────────────

_DEBOUNCE_TTL_SECONDS = 300  # 5-minute window
_WEBHOOK_MAX_ATTEMPTS = 3


def _debounce_and_dispatch(redis_key: str, task_fn, *task_args) -> bool:
    """
    Best-effort Redis debounce guard for Celery task dispatch.

    Sets a key with a 5-minute TTL on first call; skips dispatch if the key
    already exists (task already queued within the window).  A Redis outage
    is caught and logged so it never breaks webhook processing.

    Returns True if the task was dispatched, False if it was debounced.
    """
    try:
        client = redis_lib.from_url(settings.redis_url, socket_connect_timeout=1)
        # NX=True means SET only if the key does NOT exist.
        acquired = client.set(redis_key, "1", ex=_DEBOUNCE_TTL_SECONDS, nx=True)
        if not acquired:
            return False
    except Exception:
        # Redis unavailable — fall through and dispatch anyway so no event is lost.
        pass

    task_fn.delay(*task_args)
    return True


async def _dispatch_square_webhook_event(
    db: AsyncSession,
    *,
    event_log: WebhookEventLog,
    integration: Integration | None,
    event_type: str,
    merchant_id: str,
) -> dict:
    event_log.delivery_attempts = int(event_log.delivery_attempts or 0) + 1
    if integration is None:
        event_log.status = "failed"
        event_log.last_error = "no_matching_square_integration"
    else:
        customer_id = str(integration.customer_id)
        try:
            if event_type in {"inventory.count.updated"}:
                from workers.sync import sync_square_inventory

                _debounce_and_dispatch(
                    f"square_webhook:inventory:{customer_id}",
                    sync_square_inventory,
                    customer_id,
                )
            elif event_type in {"order.created", "order.updated", "order.fulfillment.updated"}:
                from workers.sync import sync_square_transactions

                _debounce_and_dispatch(
                    f"square_webhook:orders:{customer_id}",
                    sync_square_transactions,
                    customer_id,
                )
            event_log.status = "replayed" if event_log.delivery_attempts > 1 else "processed"
            event_log.last_error = None
            event_log.processed_at = datetime.utcnow()
            await db.commit()
            return {"status": event_log.status, "event_type": event_type, "merchant_id": merchant_id}
        except Exception as exc:
            event_log.status = "failed"
            event_log.last_error = str(exc)

    if event_log.delivery_attempts >= _WEBHOOK_MAX_ATTEMPTS:
        event_log.status = "dead_letter"
    await db.commit()
    return {
        "status": event_log.status,
        "event_type": event_type,
        "merchant_id": merchant_id,
        "error": event_log.last_error,
    }


# ─── OAuth State Helpers ─────────────────────────────────────────────────────


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _state_signing_key() -> bytes:
    # Combine secrets to avoid accidental key reuse in other signatures.
    return f"{settings.jwt_secret}:{settings.encryption_key}".encode()


def _sign_square_oauth_state(customer_id: str) -> str:
    payload = {
        "customer_id": customer_id,
        "nonce": uuid.uuid4().hex,
        "exp": int(time.time()) + max(60, int(settings.square_oauth_state_ttl_seconds)),
    }
    payload_token = _b64url_encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = hmac.new(_state_signing_key(), payload_token.encode("utf-8"), hashlib.sha256).digest()
    return f"{payload_token}.{_b64url_encode(signature)}"


def _verify_square_oauth_state(state: str) -> str:
    try:
        payload_token, sig_token = state.split(".", 1)
    except ValueError as exc:
        raise ValueError("invalid_state_format") from exc

    expected_sig = hmac.new(_state_signing_key(), payload_token.encode("utf-8"), hashlib.sha256).digest()
    provided_sig = _b64url_decode(sig_token)
    if not hmac.compare_digest(provided_sig, expected_sig):
        raise ValueError("invalid_state_signature")

    try:
        payload = json.loads(_b64url_decode(payload_token))
    except Exception as exc:
        raise ValueError("invalid_state_payload") from exc

    exp = int(payload.get("exp", 0))
    if exp <= int(time.time()):
        raise ValueError("expired_state")

    customer_id = str(payload.get("customer_id", "")).strip()
    if not customer_id:
        raise ValueError("missing_customer_id")
    return customer_id


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


class SquareMappingPreviewResponse(BaseModel):
    integration_id: UUID
    provider: str
    mapping_confirmed: bool
    mapping_coverage: dict
    unmapped_location_ids: list[str]
    unmapped_catalog_ids: list[str]
    locations: list[dict]
    catalog_items: list[dict]


class SquareMappingConfirmRequest(BaseModel):
    square_location_to_store: dict[str, str] = {}
    square_catalog_to_product: dict[str, str] = {}
    square_mapping_confirmed: bool = True


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
    state = _sign_square_oauth_state(str(user["customer_id"]))
    auth_url = (
        f"{base_url}/oauth2/authorize"
        f"?client_id={settings.square_client_id}"
        f"&scope=ITEMS_READ+INVENTORY_READ+ORDERS_READ+MERCHANT_PROFILE_READ"
        f"&state={quote(state, safe='')}"
    )
    return RedirectResponse(url=auth_url)


@router.get("/square/callback")
async def square_callback(
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
):
    """Handle Square OAuth callback — exchange code for tokens."""
    try:
        customer_id = _verify_square_oauth_state(state)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid OAuth state: {exc}") from exc

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
        customer_id=customer_id,
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
    raw_headers = {key: value for key, value in request.headers.items()}
    signature = request.headers.get("x-square-hmacsha256-signature", "")
    payload = json.loads(body)
    event_type = payload.get("type", "")
    merchant_id = payload.get("merchant_id", "")
    integration: Integration | None = None
    customer_id: UUID | None = None
    if merchant_id:
        integration_result = await db.execute(
            select(Integration).where(
                Integration.merchant_id == merchant_id,
                Integration.provider == "square",
                Integration.status == "connected",
            )
        )
        integration = integration_result.scalar_one_or_none()
        customer_id = integration.customer_id if integration else None

    event_log = WebhookEventLog(
        customer_id=customer_id,
        integration_id=integration.integration_id if integration else None,
        provider="square",
        merchant_id=merchant_id,
        event_type=event_type or "unknown",
        status="received",
        payload=payload,
        headers=raw_headers,
        received_at=datetime.utcnow(),
    )
    db.add(event_log)
    await db.flush()
    await db.commit()

    # Verify signature after payload is durably stored.
    if settings.square_webhook_secret:
        expected = hmac.new(
            settings.square_webhook_secret.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            event_log.status = "invalid_signature"
            event_log.last_error = "invalid_square_signature"
            await db.commit()
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

    result = await _dispatch_square_webhook_event(
        db,
        event_log=event_log,
        integration=integration,
        event_type=event_type,
        merchant_id=merchant_id,
    )
    result["webhook_event_id"] = str(event_log.webhook_event_id)
    return result


@router.get("/square/mapping-preview", response_model=SquareMappingPreviewResponse)
async def get_square_mapping_preview(
    db: AsyncSession = Depends(get_tenant_db),
    user: dict = Depends(get_current_user),
):
    from db.models import Product, Store
    from integrations.square import SquareClient

    customer_id = UUID(str(user["customer_id"]))
    result = await db.execute(
        select(Integration).where(
            Integration.customer_id == customer_id,
            Integration.provider == "square",
            Integration.status == "connected",
        )
    )
    integration = result.scalar_one_or_none()
    if integration is None:
        raise HTTPException(status_code=404, detail="Square integration not found")

    valid_store_ids = {
        str(row.store_id)
        for row in (await db.execute(select(Store.store_id).where(Store.customer_id == customer_id))).all()
    }
    valid_product_ids = {
        str(row.product_id)
        for row in (await db.execute(select(Product.product_id).where(Product.customer_id == customer_id))).all()
    }

    integration_config = integration.config if isinstance(integration.config, dict) else {}
    location_map = {
        key: str(value)
        for key, value in _build_square_id_map(integration_config.get("square_location_to_store")).items()
    }
    catalog_map = {
        key: str(value)
        for key, value in _build_square_id_map(integration_config.get("square_catalog_to_product")).items()
    }

    client = SquareClient(integration.access_token_encrypted)
    locations = await client.get_locations()
    catalog_items = await client.get_catalog()
    preview = build_square_mapping_preview(
        locations=locations,
        catalog_items=catalog_items,
        location_map=location_map,
        catalog_map=catalog_map,
        valid_store_ids=valid_store_ids,
        valid_product_ids=valid_product_ids,
    )

    integration.config = _update_square_mapping_state(
        integration_config,
        mapping_confirmed=_square_mapping_confirmed(integration_config),
        mapping_coverage=preview["mapping_coverage"],
        unmapped_location_ids=preview["unmapped_location_ids"],
        unmapped_catalog_ids=preview["unmapped_catalog_ids"],
    )
    await db.commit()

    return {
        "integration_id": integration.integration_id,
        "provider": "square",
        "mapping_confirmed": _square_mapping_confirmed(integration.config),
        **preview,
    }


@router.post("/square/mapping-confirm", response_model=IntegrationResponse)
async def confirm_square_mapping(
    body: SquareMappingConfirmRequest,
    db: AsyncSession = Depends(get_tenant_db),
    user: dict = Depends(get_current_user),
):
    customer_id = UUID(str(user["customer_id"]))
    result = await db.execute(
        select(Integration).where(
            Integration.customer_id == customer_id,
            Integration.provider == "square",
            Integration.status == "connected",
        )
    )
    integration = result.scalar_one_or_none()
    if integration is None:
        raise HTTPException(status_code=404, detail="Square integration not found")

    integration_config = integration.config if isinstance(integration.config, dict) else {}
    updated = dict(integration_config)
    updated["square_location_to_store"] = body.square_location_to_store
    updated["square_catalog_to_product"] = body.square_catalog_to_product
    updated["square_mapping_confirmed"] = body.square_mapping_confirmed
    integration.config = updated
    await db.commit()
    await db.refresh(integration)
    return integration


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


# ─── Sync Health ────────────────────────────────────────────────────────────


@router.get("/sync-health")
async def get_sync_health(
    db: AsyncSession = Depends(get_tenant_db),
):
    """
    Get data ingestion health across all integration sources.

    Returns last sync status per source, SLA compliance, and recent failures.
    """
    from sqlalchemy import func

    # Get last sync per integration type
    subquery = select(
        IntegrationSyncLog.integration_type,
        IntegrationSyncLog.integration_name,
        func.max(IntegrationSyncLog.started_at).label("last_sync"),
    ).group_by(
        IntegrationSyncLog.integration_type,
        IntegrationSyncLog.integration_name,
    )
    result = await db.execute(subquery)
    latest_syncs = result.all()

    # Get failure count (last 24h)
    cutoff_24h = datetime.utcnow() - timedelta(hours=24)
    fail_result = await db.execute(
        select(
            IntegrationSyncLog.integration_name,
            func.count().label("failure_count"),
        )
        .where(
            IntegrationSyncLog.sync_status.in_(["failed", "partial"]),
            IntegrationSyncLog.started_at >= cutoff_24h,
        )
        .group_by(IntegrationSyncLog.integration_name)
    )
    failures = {row.integration_name: row.failure_count for row in fail_result.all()}

    # Get total sync count (last 24h)
    total_result = await db.execute(
        select(
            IntegrationSyncLog.integration_name,
            func.count().label("total_count"),
            func.sum(IntegrationSyncLog.records_synced).label("total_records"),
        )
        .where(IntegrationSyncLog.started_at >= cutoff_24h)
        .group_by(IntegrationSyncLog.integration_name)
    )
    totals = {
        row.integration_name: {
            "count": row.total_count,
            "records": int(row.total_records or 0),
        }
        for row in total_result.all()
    }

    sources = []
    integration_rows = (await db.execute(select(Integration).where(Integration.status == "connected"))).scalars().all()
    square_configs = {
        f"{row.provider.title()} POS" if row.provider == "square" else row.provider: (
            row.config if isinstance(row.config, dict) else {}
        )
        for row in integration_rows
    }
    for row in latest_syncs:
        name = row.integration_name
        last_sync = row.last_sync
        hours_since = (datetime.utcnow() - last_sync).total_seconds() / 3600 if last_sync else None
        sla_limit = resolve_sla_hours(row.integration_type, name)
        sla_ok = hours_since is not None and hours_since <= sla_limit

        source = {
            "integration_type": row.integration_type,
            "integration_name": name,
            "last_sync": last_sync.isoformat() if last_sync else None,
            "hours_since_sync": round(hours_since, 1) if hours_since else None,
            "sla_hours": sla_limit,
            "sla_status": "ok" if sla_ok else "breach",
            "failures_24h": failures.get(name, 0),
            "syncs_24h": totals.get(name, {}).get("count", 0),
            "records_24h": totals.get(name, {}).get("records", 0),
        }
        config = square_configs.get(name, {})
        if name == "Square POS":
            source["mapping_confirmed"] = _square_mapping_confirmed(config)
            source["mapping_coverage"] = config.get("square_mapping_coverage", {})
            source["unmapped_location_ids"] = config.get("square_unmapped_location_ids", [])
            source["unmapped_catalog_ids"] = config.get("square_unmapped_catalog_ids", [])
        sources.append(source)

    return {
        "sources": sources,
        "overall_health": "healthy" if all(s["sla_status"] == "ok" for s in sources) else "degraded",
        "checked_at": datetime.utcnow().isoformat(),
    }


@router.get("/webhooks/dead-letter")
async def list_dead_letter_webhooks(
    db: AsyncSession = Depends(get_tenant_db),
):
    result = await db.execute(
        select(WebhookEventLog)
        .where(WebhookEventLog.status == "dead_letter")
        .order_by(WebhookEventLog.received_at.desc())
    )
    return [
        {
            "webhook_event_id": str(row.webhook_event_id),
            "provider": row.provider,
            "merchant_id": row.merchant_id,
            "event_type": row.event_type,
            "status": row.status,
            "delivery_attempts": row.delivery_attempts,
            "last_error": row.last_error,
            "received_at": row.received_at.isoformat(),
        }
        for row in result.scalars().all()
    ]


@router.post("/webhooks/{webhook_event_id}/replay")
async def replay_webhook_event(
    webhook_event_id: UUID,
    db: AsyncSession = Depends(get_tenant_db),
):
    event_log = await db.get(WebhookEventLog, webhook_event_id)
    if event_log is None:
        raise HTTPException(status_code=404, detail="Webhook event not found")

    integration = None
    if event_log.integration_id:
        integration = await db.get(Integration, event_log.integration_id)
    result = await _dispatch_square_webhook_event(
        db,
        event_log=event_log,
        integration=integration,
        event_type=event_log.event_type,
        merchant_id=event_log.merchant_id or "",
    )
    result["webhook_event_id"] = str(event_log.webhook_event_id)
    return result
