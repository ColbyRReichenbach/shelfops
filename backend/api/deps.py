"""
ShelfOps API Dependencies

Dependency injection for DB sessions, auth, and tenant context.
"""

from collections.abc import AsyncGenerator
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from db.session import AsyncSessionLocal

settings = get_settings()
security = HTTPBearer(auto_error=not settings.debug)

# Dev customer_id must match seed_test_data.py
DEV_CUSTOMER_ID = "00000000-0000-0000-0000-000000000001"


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict:
    """Decode JWT and return user payload. Bypassed in debug mode."""
    if settings.debug:
        return {
            "sub": "dev-user",
            "email": "dev@shelfops.com",
            "customer_id": DEV_CUSTOMER_ID,
        }

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    from core.security import decode_access_token

    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    return payload


async def get_tenant_db(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> AsyncSession:
    """
    Get a DB session with tenant context set.
    Sets PostgreSQL RLS variable for row-level security.
    """
    customer_id = user.get("customer_id")
    if not customer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No customer context",
        )
    await db.execute(
        text("SELECT set_config('app.current_customer_id', :cid, true)"),
        {"cid": str(customer_id)},
    )
    return db
