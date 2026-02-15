import pytest

from core import config as config_module


def _reset_settings_cache():
    config_module.get_settings.cache_clear()


def test_non_local_debug_mode_is_blocked(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("JWT_SECRET", "real-secret")
    monkeypatch.setenv("ENCRYPTION_KEY", "real-encryption-key")
    _reset_settings_cache()

    with pytest.raises(ValueError, match="debug=true"):
        config_module.get_settings()


def test_non_local_default_secrets_are_blocked(monkeypatch):
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("JWT_SECRET", config_module.DEFAULT_JWT_SECRET)
    monkeypatch.setenv("ENCRYPTION_KEY", "real-encryption-key")
    _reset_settings_cache()

    with pytest.raises(ValueError, match="default JWT secret"):
        config_module.get_settings()


def test_local_allows_dev_defaults(monkeypatch):
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("JWT_SECRET", config_module.DEFAULT_JWT_SECRET)
    monkeypatch.setenv("ENCRYPTION_KEY", config_module.DEFAULT_ENCRYPTION_KEY)
    _reset_settings_cache()

    settings = config_module.get_settings()
    assert settings.app_env == "local"
