"""
ShelfOps Security Utilities

Encryption for OAuth tokens, JWT handling, password hashing.
"""

from cryptography.fernet import Fernet
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
from core.config import get_settings

settings = get_settings()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Fernet encryption for OAuth tokens
_fernet = Fernet(Fernet.generate_key()) if settings.encryption_key == "dev-encryption-key-change-in-production" else Fernet(settings.encryption_key.encode())


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
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(hours=24))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError:
        return None
