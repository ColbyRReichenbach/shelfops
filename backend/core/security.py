"""
ShelfOps Security Utilities

Encryption for OAuth tokens, JWT handling, password hashing.
"""

import base64
import hashlib
import time
from datetime import datetime, timedelta

import httpx
from cryptography.fernet import Fernet
from jose import JWTError, jwt
from passlib.context import CryptContext

from core.config import get_settings

settings = get_settings()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Fernet encryption for OAuth tokens
# IMPORTANT: Dev key must be deterministic so all processes share the same key.
# A random key per import would break cross-process decryption and survive restarts.
if settings.encryption_key == "dev-encryption-key-change-in-production":
    _dev_key = base64.urlsafe_b64encode(hashlib.sha256(b"shelfops-dev-key-not-for-production").digest())
    _fernet = Fernet(_dev_key)
else:
    _fernet = Fernet(settings.encryption_key.encode())


def encrypt(plaintext: str) -> str:
    """Encrypt sensitive data (OAuth tokens, etc)."""
    return _fernet.encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """Decrypt sensitive data."""
    return _fernet.decrypt(ciphertext.encode()).decode()


def hash_password(password: str) -> str:
    """Hash a password for storage."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a JWT access token."""
    runtime_settings = get_settings()
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(hours=24))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, runtime_settings.jwt_secret, algorithm=runtime_settings.jwt_algorithm)


_JWKS_CACHE: dict[str, tuple[float, dict]] = {}


def _is_local_env() -> bool:
    env = get_settings().app_env.strip().lower()
    return env in {"", "local", "dev", "development", "test"}


def _resolve_auth0_issuer() -> str:
    runtime_settings = get_settings()
    if runtime_settings.auth0_issuer:
        return runtime_settings.auth0_issuer.rstrip("/")
    if not runtime_settings.auth0_domain:
        return ""
    domain = runtime_settings.auth0_domain.strip()
    if domain.startswith("http://") or domain.startswith("https://"):
        return domain.rstrip("/")
    return f"https://{domain}".rstrip("/")


def _get_jwks(issuer: str) -> dict | None:
    runtime_settings = get_settings()
    cache_ttl = max(60, int(runtime_settings.auth0_jwks_cache_ttl_seconds))
    now = time.time()
    cached = _JWKS_CACHE.get(issuer)
    if cached and cached[0] > now:
        return cached[1]

    url = f"{issuer}/.well-known/jwks.json"
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(url)
            resp.raise_for_status()
        payload = resp.json()
        if isinstance(payload, dict) and isinstance(payload.get("keys"), list):
            _JWKS_CACHE[issuer] = (now + cache_ttl, payload)
            return payload
    except Exception:
        return None
    return None


def _decode_auth0_access_token(token: str) -> dict | None:
    runtime_settings = get_settings()
    issuer = _resolve_auth0_issuer()
    audience = runtime_settings.auth0_audience
    if not issuer or not audience:
        return None

    try:
        header = jwt.get_unverified_header(token)
    except JWTError:
        return None
    kid = header.get("kid")
    if not kid:
        return None

    jwks = _get_jwks(issuer)
    if not jwks:
        return None
    key = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
    if key is None:
        return None

    try:
        return jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=audience,
            issuer=issuer,
        )
    except JWTError:
        return None


def decode_access_token(token: str) -> dict | None:
    """Decode and validate an access token from Auth0 (preferred) or local JWT."""
    runtime_settings = get_settings()

    # Production path: Auth0/JWKS-backed validation.
    auth0_payload = _decode_auth0_access_token(token)
    if auth0_payload is not None:
        return auth0_payload

    # Local fallback keeps existing dev/test ergonomics and backward-compat fixtures.
    if runtime_settings.auth0_domain and runtime_settings.auth0_audience and not _is_local_env():
        return None

    try:
        return jwt.decode(
            token,
            runtime_settings.jwt_secret,
            algorithms=[runtime_settings.jwt_algorithm],
        )
    except JWTError:
        return None
