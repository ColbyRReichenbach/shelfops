import pytest
from redis.exceptions import RedisError

from alerts import websocket as websocket_module


class _FakeWebSocket:
    headers: dict[str, str] = {}

    def __init__(self) -> None:
        self.accepted = False
        self.sent_json: list[dict] = []
        self.closed: tuple[int, str] | None = None

    async def accept(self, subprotocol=None):
        self.accepted = True
        self.subprotocol = subprotocol

    async def send_json(self, payload: dict):
        self.sent_json.append(payload)

    async def close(self, code: int = 1000, reason: str | None = None):
        self.closed = (code, reason or "")


class _UnavailablePubSub:
    async def subscribe(self, channel: str):
        raise RedisError("redis unavailable")

    async def unsubscribe(self, channel: str):
        raise RedisError("redis unavailable")

    async def aclose(self):
        raise RedisError("redis unavailable")


class _UnavailableRedis:
    def pubsub(self):
        return _UnavailablePubSub()

    async def aclose(self):
        raise RedisError("redis unavailable")


@pytest.mark.asyncio
async def test_alert_websocket_degrades_when_redis_unavailable(monkeypatch):
    monkeypatch.setattr(websocket_module.settings, "debug", True)
    monkeypatch.setattr(websocket_module.aioredis, "from_url", lambda url: _UnavailableRedis())

    websocket = _FakeWebSocket()
    await websocket_module.websocket_alerts(websocket, token=None)

    assert websocket.accepted is True
    assert websocket.sent_json == [
        {
            "type": "connection_status",
            "payload": {
                "status": "degraded",
                "reason": "alert_stream_unavailable",
            },
        }
    ]
    assert websocket.closed == (1013, "Alert stream unavailable")
