import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_cors_allows_local_dev_origins(client: AsyncClient):
    response = await client.options(
        "/api/v1/data/readiness",
        headers={
            "Origin": "http://127.0.0.1:4174",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:4174"


@pytest.mark.asyncio
async def test_cors_rejects_non_local_origin(client: AsyncClient):
    response = await client.options(
        "/api/v1/data/readiness",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 400
