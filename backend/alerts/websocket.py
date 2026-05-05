"""WebSocket endpoint for real-time alert delivery."""

import asyncio
from typing import cast

import redis.asyncio as aioredis
import structlog
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt
from redis.exceptions import RedisError

from core.config import get_settings

settings = get_settings()
router = APIRouter()
logger = structlog.get_logger()


async def authenticate_ws(token: str) -> dict | None:
    """Validate JWT token from WebSocket query param."""
    if settings.debug:
        return {
            "sub": "dev-user",
            "customer_id": "00000000-0000-0000-0000-000000000001",
        }
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except JWTError:
        return None


def _extract_subprotocol_token(websocket: WebSocket) -> tuple[str | None, str | None]:
    raw_header = websocket.headers.get("sec-websocket-protocol")
    if not raw_header:
        return None, None

    for candidate in (value.strip() for value in raw_header.split(",")):
        if candidate.startswith("bearer."):
            return candidate.removeprefix("bearer."), candidate
    return None, None


@router.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket, token: str | None = Query(None)):
    """
    WebSocket endpoint that streams alerts via Redis pub/sub.

    Connect: ws://host/ws/alerts using Sec-WebSocket-Protocol: bearer.<jwt>

    Messages sent to client:
        {"type": "alert", "payload": {...}}
        {"type": "inventory_update", "payload": {...}}
    """
    header_token, negotiated_protocol = _extract_subprotocol_token(websocket)
    auth_token = header_token or token

    # Authenticate
    if settings.debug and auth_token is None:
        user = {
            "sub": "dev-user",
            "customer_id": "00000000-0000-0000-0000-000000000001",
        }
    elif auth_token is None:
        user = None
    else:
        user = await authenticate_ws(auth_token)
    if user is None:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await websocket.accept(subprotocol=cast(str | None, negotiated_protocol))

    customer_id = user.get("customer_id", "")
    channel = f"alerts:{customer_id}"

    redis = None
    pubsub = None
    subscribed = False
    try:
        # Subscribe to Redis channel
        redis = aioredis.from_url(settings.redis_url)
        pubsub = redis.pubsub()
        try:
            await pubsub.subscribe(channel)
        except RedisError as exc:
            logger.warning("websocket.redis_unavailable", error=str(exc))
            await websocket.send_json(
                {
                    "type": "connection_status",
                    "payload": {
                        "status": "degraded",
                        "reason": "alert_stream_unavailable",
                    },
                }
            )
            await websocket.close(code=1013, reason="Alert stream unavailable")
            return
        subscribed = True

        # Send heartbeat + listen for Redis messages
        async def listen_redis():
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        await websocket.send_text(message["data"].decode())
                    except Exception:
                        break

        async def send_heartbeat():
            while True:
                await asyncio.sleep(30)
                try:
                    await websocket.send_json({"type": "heartbeat", "payload": {}})
                except Exception:
                    break

        # Run both concurrently
        await asyncio.gather(listen_redis(), send_heartbeat())

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.error("websocket.error", error=str(exc))
    finally:
        if pubsub:
            try:
                if subscribed:
                    await pubsub.unsubscribe(channel)
                await pubsub.aclose()
            except RedisError as exc:
                logger.warning("websocket.redis_cleanup_failed", error=str(exc))
        if redis:
            try:
                await redis.aclose()
            except RedisError as exc:
                logger.warning("websocket.redis_close_failed", error=str(exc))
