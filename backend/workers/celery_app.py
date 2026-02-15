"""
Celery Application Configuration
"""

from celery import Celery
from celery.schedules import crontab

from core.config import get_settings

settings = get_settings()

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
        "workers.forecast.*": {"queue": "ml"},
        "workers.inventory_optimizer.*": {"queue": "ml"},
        "workers.monitoring.*": {"queue": "sync"},
        "workers.vendor_metrics.*": {"queue": "sync"},
        "workers.promo_tracking.*": {"queue": "sync"},
        "workers.scheduler.*": {"queue": "sync"},
    },
    # ── Celery Beat Schedule ─────────────────────────────────────────
    # These jobs fan out across active tenants via workers.scheduler.dispatch_active_tenants.
    beat_schedule={
        # ── Data Sync ───────────────────────────────────────────────
        "sync-square-inventory-15m": {
            "task": "workers.scheduler.dispatch_active_tenants",
            "schedule": crontab(minute="*/15"),
            "kwargs": {"task_name": "workers.sync.sync_square_inventory"},
            "options": {"queue": "sync"},
        },
        "sync-square-transactions-30m": {
            "task": "workers.scheduler.dispatch_active_tenants",
            "schedule": crontab(minute="*/30"),
            "kwargs": {"task_name": "workers.sync.sync_square_transactions"},
            "options": {"queue": "sync"},
        },
        # ── ML Pipeline ────────────────────────────────────────────
        "retrain-forecast-weekly": {
            "task": "workers.scheduler.dispatch_active_tenants",
            "schedule": crontab(hour=2, minute=0, day_of_week="sunday"),
            "kwargs": {
                "task_name": "workers.retrain.retrain_forecast_model",
                "task_kwargs": {"promote": True},
            },
            "options": {"queue": "sync"},
        },
        "generate-forecasts-daily": {
            "task": "workers.scheduler.dispatch_active_tenants",
            "schedule": crontab(hour=3, minute=0),
            "kwargs": {"task_name": "workers.forecast.generate_forecasts"},
            "options": {"queue": "sync"},
        },
        "compute-forecast-accuracy-daily": {
            "task": "workers.scheduler.dispatch_active_tenants",
            "schedule": crontab(hour=5, minute=0),
            "kwargs": {"task_name": "workers.monitoring.compute_forecast_accuracy"},
            "options": {"queue": "ml"},
        },
        # ── Decision Engine ────────────────────────────────────────
        "optimize-reorder-points-nightly": {
            "task": "workers.scheduler.dispatch_active_tenants",
            "schedule": crontab(hour=2, minute=30),  # After forecast generation
            "kwargs": {"task_name": "workers.inventory_optimizer.optimize_reorder_points"},
            "options": {"queue": "sync"},
        },
        # ── Alert & Monitoring ─────────────────────────────────────
        "alert-check-hourly": {
            "task": "workers.scheduler.dispatch_active_tenants",
            "schedule": crontab(minute=0),
            "kwargs": {"task_name": "workers.sync.run_alert_check"},
            "options": {"queue": "sync"},
        },
        "drift-detection-daily": {
            "task": "workers.scheduler.dispatch_active_tenants",
            "schedule": crontab(hour=3, minute=0),
            "kwargs": {"task_name": "workers.monitoring.detect_model_drift"},
            "options": {"queue": "sync"},
        },
        "data-freshness-hourly": {
            "task": "workers.scheduler.dispatch_active_tenants",
            "schedule": crontab(minute=30),  # Offset from alert check
            "kwargs": {"task_name": "workers.monitoring.check_data_freshness"},
            "options": {"queue": "sync"},
        },
        "opportunity-cost-daily": {
            "task": "workers.scheduler.dispatch_active_tenants",
            "schedule": crontab(hour=4, minute=0),
            "kwargs": {"task_name": "workers.monitoring.calculate_opportunity_cost"},
            "options": {"queue": "sync"},
        },
        # ── MLOps - Backtesting ────────────────────────────────────
        "backtest-daily": {
            "task": "workers.scheduler.dispatch_active_tenants",
            "schedule": crontab(hour=6, minute=0),  # After opportunity cost
            "kwargs": {"task_name": "workers.monitoring.run_daily_backtest"},
            "options": {"queue": "sync"},
        },
        "backtest-weekly": {
            "task": "workers.scheduler.dispatch_active_tenants",
            "schedule": crontab(hour=4, minute=0, day_of_week="sunday"),  # After retrain
            "kwargs": {
                "task_name": "workers.monitoring.run_weekly_backtest",
                "task_kwargs": {"lookback_days": 90},
            },
            "options": {"queue": "sync"},
        },
        # ── Vendor & Promotions ────────────────────────────────────
        "update-vendor-scorecards-daily": {
            "task": "workers.scheduler.dispatch_active_tenants",
            "schedule": crontab(hour=1, minute=0),
            "kwargs": {"task_name": "workers.vendor_metrics.update_vendor_scorecards"},
            "options": {"queue": "sync"},
        },
        "promo-effectiveness-weekly": {
            "task": "workers.scheduler.dispatch_active_tenants",
            "schedule": crontab(hour=5, minute=0, day_of_week="monday"),
            "kwargs": {"task_name": "workers.promo_tracking.measure_completed_promotions"},
            "options": {"queue": "sync"},
        },
        # ── Phase 1 - Quick Wins (Anomaly Detection) ──────────────────
        "detect-anomalies-ml-6h": {
            "task": "workers.scheduler.dispatch_active_tenants",
            "schedule": crontab(minute=0, hour="*/6"),  # Every 6 hours
            "kwargs": {"task_name": "workers.monitoring.detect_anomalies_ml"},
            "options": {"queue": "sync"},
        },
        "detect-ghost-stock-daily": {
            "task": "workers.scheduler.dispatch_active_tenants",
            "schedule": crontab(hour=4, minute=30),  # After opportunity cost
            "kwargs": {"task_name": "workers.monitoring.detect_ghost_stock"},
            "options": {"queue": "sync"},
        },
        # ── Category Model Retraining ────────────────────────────────
        "retrain-category-models-weekly": {
            "task": "workers.scheduler.dispatch_active_tenants",
            "schedule": crontab(hour=3, minute=0, day_of_week="sunday"),  # After global retrain
            "kwargs": {
                "task_name": "workers.retrain.retrain_forecast_model",
                "task_kwargs": {
                    "promote": True,
                    "model_name": "demand_forecast_fresh",
                    "category_tier": "fresh",
                    "trigger": "scheduled",
                },
            },
            "options": {"queue": "sync"},
        },
        "retrain-gm-models-weekly": {
            "task": "workers.scheduler.dispatch_active_tenants",
            "schedule": crontab(hour=3, minute=30, day_of_week="sunday"),
            "kwargs": {
                "task_name": "workers.retrain.retrain_forecast_model",
                "task_kwargs": {
                    "promote": True,
                    "model_name": "demand_forecast_gm",
                    "category_tier": "general_merchandise",
                    "trigger": "scheduled",
                },
            },
            "options": {"queue": "sync"},
        },
        "retrain-hardware-models-weekly": {
            "task": "workers.scheduler.dispatch_active_tenants",
            "schedule": crontab(hour=4, minute=0, day_of_week="sunday"),
            "kwargs": {
                "task_name": "workers.retrain.retrain_forecast_model",
                "task_kwargs": {
                    "promote": True,
                    "model_name": "demand_forecast_hardware",
                    "category_tier": "hardware",
                    "trigger": "scheduled",
                },
            },
            "options": {"queue": "sync"},
        },
    },
)

# Auto-discover tasks
celery_app.autodiscover_tasks(["workers"])
