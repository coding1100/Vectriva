"""Seed initial user, tenant, and API key for development."""

import asyncio
import hashlib
import secrets
import sys
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vectriva.core.database import AsyncSessionLocal
from vectriva.models.database import APIKey, Tenant, TenantConfig, TenantUser, User
from vectriva.services.auth_service import hash_password


async def seed(email: str = "admin@example.com", password: str = "Admin123!") -> None:
    """Create user, tenant, and API key."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == email))
        existing = result.scalar_one_or_none()
        if existing:
            print(f"User {email} already exists. Fetching tenant and creating API key...")
            user = existing
            result = await db.execute(
                select(Tenant)
                .join(TenantUser, TenantUser.tenant_id == Tenant.id)
                .where(TenantUser.user_id == user.id)
            )
            tenant = result.scalars().unique().first()
            if not tenant:
                tenant = await _create_tenant(db, user)
        else:
            user = User(
                id=str(uuid.uuid4()),
                email=email,
                hashed_password=hash_password(password),
            )
            db.add(user)
            await db.flush()
            tenant = await _create_tenant(db, user)
            print(f"Created user: {email}")

        api_key = await _ensure_api_key(db, tenant)
        await db.commit()

        print("\n" + "=" * 60)
        print("SEED COMPLETE")
        print("=" * 60)
        print(f"Email:     {email}")
        print(f"Password:  {password}")
        print(f"Tenant ID: {tenant.id}")
        print(f"API Key:   {api_key}")
        print("=" * 60)
        print("\nExample requests:")
        print(f'  Login:    curl -X POST http://localhost:8000/api/auth/login -H "Content-Type: application/json" -d \'{{"email":"{email}","password":"{password}"}}\'')
        print(f'  Chat:     curl -X POST http://localhost:8000/api/chat -H "X-API-Key: {api_key}" -H "Content-Type: application/json" -d \'{{"message":"Hello","customer_email":"test@example.com"}}\'')
        print("=" * 60)


async def _create_tenant(db: AsyncSession, user: User) -> Tenant:
    """Create tenant and config."""
    tenant_id = str(uuid.uuid4())
    tenant = Tenant(id=tenant_id, name="Default Tenant", timezone="UTC")
    db.add(tenant)

    tenant_user = TenantUser(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        user_id=user.id,
        role="owner",
    )
    db.add(tenant_user)

    config = TenantConfig(id=str(uuid.uuid4()), tenant_id=tenant_id)
    db.add(config)
    await db.flush()
    return tenant


async def _ensure_api_key(db: AsyncSession, tenant: Tenant) -> str:
    """Create a new API key and return it."""
    key = f"vect_live_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(key.encode()).hexdigest()
    api_key = APIKey(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        key_hash=key_hash,
        name="Seed Key",
    )
    db.add(api_key)
    await db.flush()
    return key


if __name__ == "__main__":
    email = sys.argv[1] if len(sys.argv) > 1 else "admin@example.com"
    password = sys.argv[2] if len(sys.argv) > 2 else "Admin123!"
    asyncio.run(seed(email, password))
