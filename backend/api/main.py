"""
ShelfOps API — FastAPI Application Entry Point
"""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request

from core.config import get_settings

settings = get_settings()
logger = structlog.get_logger()

LEGACY_ROUTE_MAP = {
    "/ml": "/api/v1/ml",
    "/models": "/api/v1/ml/models",
    "/anomalies": "/api/v1/ml/anomalies",
}
DEPRECATION_SUNSET = "Wed, 30 Jun 2026 00:00:00 GMT"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("ShelfOps API starting up", version=settings.app_version)
    yield
    logger.info("ShelfOps API shutting down")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI-powered retail inventory intelligence platform",
    lifespan=lifespan,
)


@app.middleware("http")
async def legacy_route_alias_middleware(request: Request, call_next):
    """
    Temporary compatibility layer:
      - /ml/* -> /api/v1/ml/*
      - /models/* -> /api/v1/ml/models/*
      - /anomalies/* -> /api/v1/ml/anomalies/*
    Adds deprecation headers on legacy route usage.
    """
    original_path = request.scope.get("path", "")
    rewritten_to: str | None = None

    for legacy_prefix, canonical_prefix in LEGACY_ROUTE_MAP.items():
        if original_path == legacy_prefix or original_path.startswith(f"{legacy_prefix}/"):
            suffix = original_path[len(legacy_prefix) :]
            request.scope["path"] = f"{canonical_prefix}{suffix}"
            rewritten_to = request.scope["path"]
            break

    response = await call_next(request)
    if rewritten_to:
        response.headers["Deprecation"] = "true"
        response.headers["Sunset"] = DEPRECATION_SUNSET
        response.headers["X-API-Deprecated"] = "Use /api/v1/ml/* endpoints"
        response.headers["Link"] = f'<{rewritten_to}>; rel="successor-version"'
    return response


# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import and register routers
from alerts.websocket import router as ws_router
from api.v1.routers import (
    alerts,
    anomalies,
    experiments,
    forecasts,
    integrations,
    inventory,
    ml_alerts,
    ml_ops,
    models,
    outcomes,
    products,
    purchase_orders,
    stores,
)

app.include_router(stores.router)
app.include_router(products.router)
app.include_router(forecasts.router)
app.include_router(alerts.router)
app.include_router(integrations.router)
app.include_router(inventory.router)
app.include_router(purchase_orders.router)
app.include_router(models.router)
app.include_router(ml_alerts.router)
app.include_router(experiments.router)
app.include_router(anomalies.router)
app.include_router(outcomes.router)
app.include_router(ml_ops.router)
app.include_router(ws_router)


@app.get("/health")
async def health_check():
    """Health check endpoint for Cloud Run / load balancers."""
    return {"status": "healthy", "version": settings.app_version}
