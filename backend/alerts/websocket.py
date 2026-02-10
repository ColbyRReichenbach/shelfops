"""
WebSocket endpoint for real-time alert delivery.

Agent: full-stack-engineer
Skill: alert-systems (Redis pub/sub pattern)
"""

import asyncio
import json

import redis.asyncio as aioredis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from jose import jwt, JWTError

from core.config import get_settings

settings = get_settings()
router = APIRouter()


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


@router.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket, token: str = Query(...)):
    """
    WebSocket endpoint that streams alerts via Redis pub/sub.

    Connect: ws://host/ws/alerts?token=<jwt>

    Messages sent to client:
        {"type": "alert", "payload": {...}}
        {"type": "inventory_update", "payload": {...}}
    """
    # Authenticate
    user = await authenticate_ws(token)
    if user is None:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await websocket.accept()

    customer_id = user.get("customer_id", "")
    channel = f"alerts:{customer_id}"

    # Subscribe to Redis channel
    redis = aioredis.from_url(settings.redis_url)
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel)

    try:
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
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()
        await redis.aclose()
