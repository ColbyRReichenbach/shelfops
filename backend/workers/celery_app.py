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
        "workers.inventory_optimizer.*": {"queue": "ml"},
        "workers.monitoring.*": {"queue": "sync"},
        "workers.vendor_metrics.*": {"queue": "sync"},
        "workers.promo_tracking.*": {"queue": "sync"},
    },
    # ── Celery Beat Schedule ─────────────────────────────────────────
    # These run automatically when `celery -A workers.celery_app beat` is started.
    # Customer IDs are placeholder — in production, a task would iterate over
    # all active customers that have connected integrations.
    beat_schedule={
        # ── Data Sync ───────────────────────────────────────────────
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
        # ── ML Pipeline ────────────────────────────────────────────
        "retrain-forecast-weekly": {
            "task": "workers.retrain.retrain_forecast_model",
            "schedule": crontab(hour=2, minute=0, day_of_week="sunday"),
            "kwargs": {"promote": True},
            "options": {"queue": "ml"},
        },
        # ── Decision Engine ────────────────────────────────────────
        "optimize-reorder-points-nightly": {
            "task": "workers.inventory_optimizer.optimize_reorder_points",
            "schedule": crontab(hour=2, minute=30),  # After forecast generation
            "kwargs": {"customer_id": DEV_CUSTOMER_ID},
            "options": {"queue": "ml"},
        },
        # ── Alert & Monitoring ─────────────────────────────────────
        "alert-check-hourly": {
            "task": "workers.sync.run_alert_check",
            "schedule": crontab(minute=0),
            "kwargs": {"customer_id": DEV_CUSTOMER_ID},
            "options": {"queue": "sync"},
        },
        "drift-detection-daily": {
            "task": "workers.monitoring.detect_model_drift",
            "schedule": crontab(hour=3, minute=0),
            "kwargs": {"customer_id": DEV_CUSTOMER_ID},
            "options": {"queue": "sync"},
        },
        "data-freshness-hourly": {
            "task": "workers.monitoring.check_data_freshness",
            "schedule": crontab(minute=30),  # Offset from alert check
            "kwargs": {"customer_id": DEV_CUSTOMER_ID},
            "options": {"queue": "sync"},
        },
        "opportunity-cost-daily": {
            "task": "workers.monitoring.calculate_opportunity_cost",
            "schedule": crontab(hour=4, minute=0),
            "kwargs": {"customer_id": DEV_CUSTOMER_ID},
            "options": {"queue": "sync"},
        },
        # ── MLOps - Backtesting ────────────────────────────────────
        "backtest-daily": {
            "task": "workers.monitoring.run_daily_backtest",
            "schedule": crontab(hour=6, minute=0),  # After opportunity cost
            "kwargs": {"customer_id": DEV_CUSTOMER_ID},
            "options": {"queue": "sync"},
        },
        "backtest-weekly": {
            "task": "workers.monitoring.run_weekly_backtest",
            "schedule": crontab(hour=4, minute=0, day_of_week="sunday"),  # After retrain
            "kwargs": {"customer_id": DEV_CUSTOMER_ID, "lookback_days": 90},
            "options": {"queue": "sync"},
        },
        # ── Vendor & Promotions ────────────────────────────────────
        "update-vendor-scorecards-daily": {
            "task": "workers.vendor_metrics.update_vendor_scorecards",
            "schedule": crontab(hour=1, minute=0),
            "kwargs": {"customer_id": DEV_CUSTOMER_ID},
            "options": {"queue": "sync"},
        },
        "promo-effectiveness-weekly": {
            "task": "workers.promo_tracking.measure_completed_promotions",
            "schedule": crontab(hour=5, minute=0, day_of_week="monday"),
            "kwargs": {"customer_id": DEV_CUSTOMER_ID},
            "options": {"queue": "sync"},
        },
        # ── Phase 1 - Quick Wins (Anomaly Detection) ──────────────────
        "detect-anomalies-ml-6h": {
            "task": "workers.monitoring.detect_anomalies_ml",
            "schedule": crontab(minute=0, hour="*/6"),  # Every 6 hours
            "kwargs": {"customer_id": DEV_CUSTOMER_ID},
            "options": {"queue": "sync"},
        },
        "detect-ghost-stock-daily": {
            "task": "workers.monitoring.detect_ghost_stock",
            "schedule": crontab(hour=4, minute=30),  # After opportunity cost
            "kwargs": {"customer_id": DEV_CUSTOMER_ID},
            "options": {"queue": "sync"},
        },
        # ── Category Model Retraining ────────────────────────────────
        "retrain-category-models-weekly": {
            "task": "workers.retrain.retrain_forecast_model",
            "schedule": crontab(hour=3, minute=0, day_of_week="sunday"),  # After global retrain
            "kwargs": {
                "promote": True,
                "model_name": "demand_forecast_fresh",
                "category_tier": "fresh",
                "trigger": "scheduled",
            },
            "options": {"queue": "ml"},
        },
        "retrain-gm-models-weekly": {
            "task": "workers.retrain.retrain_forecast_model",
            "schedule": crontab(hour=3, minute=30, day_of_week="sunday"),
            "kwargs": {
                "promote": True,
                "model_name": "demand_forecast_gm",
                "category_tier": "general_merchandise",
                "trigger": "scheduled",
            },
            "options": {"queue": "ml"},
        },
        "retrain-hardware-models-weekly": {
            "task": "workers.retrain.retrain_forecast_model",
            "schedule": crontab(hour=4, minute=0, day_of_week="sunday"),
            "kwargs": {
                "promote": True,
                "model_name": "demand_forecast_hardware",
                "category_tier": "hardware",
                "trigger": "scheduled",
            },
            "options": {"queue": "ml"},
        },
    },
)

# Auto-discover tasks
celery_app.autodiscover_tasks(["workers"])
