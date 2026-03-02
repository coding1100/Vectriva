"""Authentication and tenant isolation middleware."""

from datetime import datetime
from typing import Any

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..core.errors import AuthenticationError, UnauthorizedError
from ..models.database import APIKey, Tenant, TenantUser, User
from ..services.auth_service import decode_token


async def get_current_user(
    authorization: str = Header(...), db: AsyncSession = Depends(get_db)
) -> User:
    """Get current authenticated user from JWT."""
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid auth scheme")

        payload = decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

        result = await db.execute(select(User).where(User.id == user_id, User.is_active == True))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

        return user
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


async def get_current_tenant(
    tenant_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> Tenant:
    """Get tenant and verify user has access."""
    result = await db.execute(
        select(TenantUser).where(
            TenantUser.tenant_id == tenant_id, TenantUser.user_id == user.id
        )
    )
    tenant_user = result.scalar_one_or_none()
    if not tenant_user:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    tenant_result = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id, Tenant.is_active == True)
    )
    tenant = tenant_result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    return tenant


async def verify_api_key(
    x_api_key: str = Header(...), db: AsyncSession = Depends(get_db)
) -> tuple[Tenant, APIKey]:
    """Verify API key and return tenant."""
    import hashlib

    key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()

    result = await db.execute(select(APIKey).where(APIKey.key_hash == key_hash, APIKey.is_active == True))
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    api_key.last_used_at = datetime.utcnow()

    tenant_result = await db.execute(
        select(Tenant).where(Tenant.id == api_key.tenant_id, Tenant.is_active == True)
    )
    tenant = tenant_result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    return tenant, api_key
