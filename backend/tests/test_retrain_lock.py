"""
Tests for the Redis retrain lock in workers/retrain.py.
"""

from unittest.mock import MagicMock, patch

from workers.retrain import _acquire_retrain_lock, _release_retrain_lock


def test_acquire_lock_returns_true_when_redis_unavailable():
    """Fail open: if Redis is down, don't block retraining."""
    with patch("workers.retrain.redis") as mock_redis:
        mock_redis.from_url.side_effect = Exception("Connection refused")
        result = _acquire_retrain_lock("test-customer-id")
    assert result is True


def test_acquire_and_release():
    """Lock acquired, then released."""
    mock_r = MagicMock()
    mock_r.set.return_value = True
    with patch("workers.retrain.redis") as mock_redis:
        mock_redis.from_url.return_value = mock_r
        acquired = _acquire_retrain_lock("cust-1")
        _release_retrain_lock("cust-1")
    assert acquired is True
    mock_r.delete.assert_called_once_with("retrain_lock:cust-1")


def test_acquire_lock_returns_false_when_lock_held():
    """Returns False when Redis SET NX returns falsy (lock already held)."""
    mock_r = MagicMock()
    mock_r.set.return_value = None  # Redis returns None when NX key already exists
    with patch("workers.retrain.redis") as mock_redis:
        mock_redis.from_url.return_value = mock_r
        result = _acquire_retrain_lock("cust-2")
    assert result is False


def test_lock_key_includes_customer_id():
    """The Redis key must include the customer_id for per-tenant isolation."""
    mock_r = MagicMock()
    mock_r.set.return_value = True
    with patch("workers.retrain.redis") as mock_redis:
        mock_redis.from_url.return_value = mock_r
        _acquire_retrain_lock("my-tenant-abc")
    call_args = mock_r.set.call_args
    lock_key = call_args[0][0]
    assert "my-tenant-abc" in lock_key
    assert lock_key.startswith("retrain_lock:")


def test_lock_has_timeout():
    """The lock must be set with a TTL (ex parameter) to prevent deadlocks."""
    mock_r = MagicMock()
    mock_r.set.return_value = True
    with patch("workers.retrain.redis") as mock_redis:
        mock_redis.from_url.return_value = mock_r
        _acquire_retrain_lock("cust-3", timeout=1800)
    call_kwargs = mock_r.set.call_args[1]
    assert "ex" in call_kwargs
    assert call_kwargs["ex"] == 1800


def test_release_swallows_redis_exception():
    """Release must not raise even if Redis is unavailable."""
    with patch("workers.retrain.redis") as mock_redis:
        mock_redis.from_url.side_effect = Exception("Connection refused")
        # Should not raise
        _release_retrain_lock("cust-4")


def test_acquire_uses_nx_flag():
    """Lock acquisition must use NX=True for atomic set-if-not-exists."""
    mock_r = MagicMock()
    mock_r.set.return_value = True
    with patch("workers.retrain.redis") as mock_redis:
        mock_redis.from_url.return_value = mock_r
        _acquire_retrain_lock("cust-5")
    call_kwargs = mock_r.set.call_args[1]
    assert call_kwargs.get("nx") is True
