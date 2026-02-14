"""
ShelfOps API — FastAPI Application Entry Point
"""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import get_settings

settings = get_settings()
logger = structlog.get_logger()


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
app.include_router(ws_router)


@app.get("/health")
async def health_check():
    """Health check endpoint for Cloud Run / load balancers."""
    return {"status": "healthy", "version": settings.app_version}
