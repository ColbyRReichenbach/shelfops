import base64
from datetime import datetime, timedelta, timezone

from jose import jwt

from core import config as config_module
from core import security as security_module


def _b64url_uint(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _build_rsa_fixture():
    from cryptography.hazmat.primitives.asymmetric import rsa

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_numbers = private_key.public_key().public_numbers()
    kid = "test-kid"
    jwk = {
        "kty": "RSA",
        "kid": kid,
        "use": "sig",
        "alg": "RS256",
        "n": _b64url_uint(public_numbers.n),
        "e": _b64url_uint(public_numbers.e),
    }
    return private_key, jwk, kid


def _reset_settings_cache():
    config_module.get_settings.cache_clear()


def test_decode_access_token_auth0_rs256(monkeypatch):
    private_key, jwk, kid = _build_rsa_fixture()
    issuer = "https://example-tenant.us.auth0.com"
    audience = "https://api.shelfops.com"
    token = jwt.encode(
        {
            "sub": "auth0|abc123",
            "customer_id": "00000000-0000-0000-0000-000000000001",
            "aud": audience,
            "iss": issuer,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        private_key,
        algorithm="RS256",
        headers={"kid": kid},
    )

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("AUTH0_DOMAIN", "example-tenant.us.auth0.com")
    monkeypatch.setenv("AUTH0_AUDIENCE", audience)
    monkeypatch.setenv("JWT_SECRET", "unit-test-nondefault-secret")
    monkeypatch.setenv("ENCRYPTION_KEY", "unit-test-nondefault-encryption-key")
    monkeypatch.setenv("DEBUG", "false")
    _reset_settings_cache()
    monkeypatch.setattr(security_module, "_get_jwks", lambda resolved_issuer: {"keys": [jwk]})

    payload = security_module.decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "auth0|abc123"
    assert payload["customer_id"] == "00000000-0000-0000-0000-000000000001"


def test_decode_access_token_auth0_invalid_audience(monkeypatch):
    private_key, jwk, kid = _build_rsa_fixture()
    token = jwt.encode(
        {
            "sub": "auth0|abc123",
            "aud": "https://wrong-audience.example.com",
            "iss": "https://example-tenant.us.auth0.com",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        private_key,
        algorithm="RS256",
        headers={"kid": kid},
    )

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("AUTH0_DOMAIN", "example-tenant.us.auth0.com")
    monkeypatch.setenv("AUTH0_AUDIENCE", "https://api.shelfops.com")
    monkeypatch.setenv("JWT_SECRET", "unit-test-nondefault-secret")
    monkeypatch.setenv("ENCRYPTION_KEY", "unit-test-nondefault-encryption-key")
    monkeypatch.setenv("DEBUG", "false")
    _reset_settings_cache()
    monkeypatch.setattr(security_module, "_get_jwks", lambda resolved_issuer: {"keys": [jwk]})

    assert security_module.decode_access_token(token) is None


def test_decode_access_token_rejects_expired_local_token(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("AUTH0_DOMAIN", "")
    monkeypatch.setenv("AUTH0_AUDIENCE", "")
    monkeypatch.setenv("JWT_SECRET", "unit-test-local-secret")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("ENCRYPTION_KEY", "unit-test-nondefault-encryption-key")
    monkeypatch.setenv("DEBUG", "false")
    _reset_settings_cache()

    expired_token = jwt.encode(
        {
            "sub": "local|expired",
            "customer_id": "00000000-0000-0000-0000-000000000001",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        },
        "unit-test-local-secret",
        algorithm="HS256",
    )

    assert security_module.decode_access_token(expired_token) is None
