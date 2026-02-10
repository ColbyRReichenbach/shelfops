"""
Celery Application Configuration
"""

from celery import Celery
from celery.schedules import crontab
from core.config import get_settings

settings = get_settings()

# Dev tenant ID — matches seed_test_data.py and api/deps.py DEV_CUSTOMER_ID
DEV_CUSTOMER_ID = "00000000-0000-0000-0000-000000000001"

celery_app = Celery(
    "shelfops",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "workers.sync.*": {"queue": "sync"},
        "workers.retrain.*": {"queue": "ml"},
    },
    # ── Celery Beat Schedule ─────────────────────────────────────────
    # These run automatically when `celery -A workers.celery_app beat` is started.
    # Customer IDs are placeholder — in production, a task would iterate over
    # all active customers that have connected integrations.
    beat_schedule={
        "sync-square-inventory-15m": {
            "task": "workers.sync.sync_square_inventory",
            "schedule": crontab(minute="*/15"),
            "kwargs": {"customer_id": DEV_CUSTOMER_ID},
            "options": {"queue": "sync"},
        },
        "sync-square-transactions-30m": {
            "task": "workers.sync.sync_square_transactions",
            "schedule": crontab(minute="*/30"),
            "kwargs": {"customer_id": DEV_CUSTOMER_ID},
            "options": {"queue": "sync"},
        },
        "retrain-forecast-weekly": {
            "task": "workers.retrain.retrain_forecast_model",
            "schedule": crontab(hour=2, minute=0, day_of_week="sunday"),
            "kwargs": {"promote": True},
            "options": {"queue": "ml"},
        },
        "alert-check-hourly": {
            "task": "workers.sync.run_alert_check",
            "schedule": crontab(minute=0),
            "kwargs": {"customer_id": DEV_CUSTOMER_ID},
            "options": {"queue": "sync"},
        },
    },
)

# Auto-discover tasks
celery_app.autodiscover_tasks(["workers"])
