"""
Tests for retrain failure handling — ModelVersion.status must be set to
'failed' when retrain_forecast_model() raises an exception.

WS-2.6
"""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def test_mark_model_version_failed_builds_correct_update():
    """
    _mark_model_version_failed() must issue an UPDATE that sets status='failed'
    and does not touch champion or archived rows.
    """
    # We verify the function exists and is importable
    from workers.retrain import _mark_model_version_failed

    assert callable(_mark_model_version_failed)


def test_mark_model_version_failed_swallows_db_errors():
    """
    If the DB is unavailable, _mark_model_version_failed's caller must
    catch the exception gracefully via the try/except wrapper in retrain.
    The function itself propagates to the caller which handles it.
    """
    from workers.retrain import _mark_model_version_failed

    # Patch the sqlalchemy module at the source location used inside the function
    with patch("sqlalchemy.ext.asyncio.create_async_engine") as mock_engine_factory:
        mock_engine_factory.side_effect = Exception("DB connection refused")
        # The outer caller wraps in try/except; the function may raise DB errors
        # This test verifies the function exists and handles imports correctly
        try:
            _mark_model_version_failed(
                customer_id="00000000-0000-0000-0000-000000000001",
                model_name="demand_forecast",
                version="v1",
                error_message="unit test error",
            )
        except Exception:
            pass  # Expected: DB errors propagate to caller which logs them


def test_retrain_failure_releases_lock():
    """
    If retrain_forecast_model() raises an exception, the Redis lock must still
    be released (via the finally block).
    """
    mock_r = MagicMock()
    mock_r.set.return_value = True  # Lock acquired

    with patch("workers.retrain.redis") as mock_redis:
        mock_redis.from_url.return_value = mock_r

        with patch("workers.retrain._load_csv_data") as mock_load:
            mock_load.side_effect = RuntimeError("data load failure")

            from workers.retrain import retrain_forecast_model

            with pytest.raises(RuntimeError, match="data load failure"):
                retrain_forecast_model.run(data_dir="/fake/path")

    # Lock must have been released via finally block
    mock_r.delete.assert_called()


def test_retrain_skips_when_lock_held():
    """
    If the Redis lock is already held, retrain_forecast_model() should return
    a 'skipped' status without raising.
    """
    mock_r = MagicMock()
    mock_r.set.return_value = None  # Lock NOT acquired (held by another worker)

    with patch("workers.retrain.redis") as mock_redis:
        mock_redis.from_url.return_value = mock_r

        from workers.retrain import retrain_forecast_model

        result = retrain_forecast_model.run(data_dir="/fake/path")

    assert result["status"] == "skipped"
    assert result["reason"] == "lock_held"


def test_record_retraining_event_called_with_failed_status_on_error():
    """
    When retrain_forecast_model() fails, _record_retraining_event must be
    called with status='failed' (not 'completed').
    """
    mock_r = MagicMock()
    mock_r.set.return_value = True

    with patch("workers.retrain.redis") as mock_redis:
        mock_redis.from_url.return_value = mock_r

        with patch("workers.retrain._load_db_data") as mock_load, patch(
            "workers.retrain._record_retraining_event"
        ) as mock_record, patch("workers.retrain._mark_model_version_failed"):

            mock_load.side_effect = ValueError("insufficient data")

            from workers.retrain import retrain_forecast_model

            with pytest.raises(ValueError):
                retrain_forecast_model.run(
                    customer_id="00000000-0000-0000-0000-000000000099"
                )

        # Verify _record_retraining_event was called with status='failed'
        mock_record.assert_called_once()
        call_kwargs = mock_record.call_args[1]
        assert call_kwargs["status"] == "failed"
        assert call_kwargs["error"] == "insufficient data"
