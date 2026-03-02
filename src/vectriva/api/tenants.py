"""Tenant management API endpoints."""

import hashlib
import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..models.database import APIKey, Tenant, TenantConfig, TenantUser, User
from ..models.schemas import (
    APIKeyResponse,
    APIKeyUsageResponse,
    CreateAPIKeyRequest,
    CreateTenantRequest,
    TenantConfigResponse,
    TenantResponse,
    UpdateTenantConfigRequest,
)
from ..api.middleware import get_current_tenant, get_current_user

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    request: CreateTenantRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TenantResponse:
    """Create a new tenant."""
    tenant_id = str(uuid.uuid4())
    tenant = Tenant(
        id=tenant_id,
        name=request.name,
        timezone=request.timezone,
    )
    db.add(tenant)

    tenant_user = TenantUser(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        user_id=user.id,
        role="owner",
    )
    db.add(tenant_user)

    config = TenantConfig(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
    )
    db.add(config)

    await db.commit()

    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        timezone=tenant.timezone,
        is_active=tenant.is_active,
        created_at=tenant.created_at,
    )


@router.get("/{tenant_id}/config", response_model=TenantConfigResponse)
async def get_tenant_config(
    tenant: Tenant = Depends(get_current_tenant), db: AsyncSession = Depends(get_db)
) -> TenantConfigResponse:
    """Get tenant configuration."""
    result = await db.execute(select(TenantConfig).where(TenantConfig.tenant_id == tenant.id))
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Config not found")

    return TenantConfigResponse(
        persona_name=config.persona_name,
        tone=config.tone,
        custom_instructions=config.custom_instructions,
        timezone=tenant.timezone,
        business_hours=config.business_hours,
        auto_escalate_on_failure_count=config.auto_escalate_on_failure_count,
        auto_escalate_on_negative_sentiment=config.auto_escalate_on_negative_sentiment,
        escalation_email=config.escalation_email,
        primary_color=config.primary_color,
        widget_position=config.widget_position,
        welcome_message=config.welcome_message,
    )


@router.patch("/{tenant_id}/config", response_model=TenantConfigResponse)
async def update_tenant_config(
    request: UpdateTenantConfigRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> TenantConfigResponse:
    """Update tenant configuration."""
    result = await db.execute(select(TenantConfig).where(TenantConfig.tenant_id == tenant.id))
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Config not found")

    for field, value in request.model_dump(exclude_unset=True).items():
        setattr(config, field, value)

    await db.commit()

    return TenantConfigResponse(
        persona_name=config.persona_name,
        tone=config.tone,
        custom_instructions=config.custom_instructions,
        timezone=tenant.timezone,
        business_hours=config.business_hours,
        auto_escalate_on_failure_count=config.auto_escalate_on_failure_count,
        auto_escalate_on_negative_sentiment=config.auto_escalate_on_negative_sentiment,
        escalation_email=config.escalation_email,
        primary_color=config.primary_color,
        widget_position=config.widget_position,
        welcome_message=config.welcome_message,
    )


@router.post("/{tenant_id}/api-keys", response_model=APIKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    request: CreateAPIKeyRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> APIKeyResponse:
    """Generate a new API key."""
    key = f"vect_live_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(key.encode()).hexdigest()

    api_key = APIKey(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        key_hash=key_hash,
        name=request.name,
    )
    db.add(api_key)
    await db.commit()

    return APIKeyResponse(
        id=api_key.id,
        name=api_key.name,
        key=key,
        key_preview=key[-4:],
        is_active=api_key.is_active,
        created_at=api_key.created_at,
        last_used_at=api_key.last_used_at,
    )


@router.get("/{tenant_id}/api-keys", response_model=list[APIKeyResponse])
async def list_api_keys(
    tenant: Tenant = Depends(get_current_tenant), db: AsyncSession = Depends(get_db)
) -> list[APIKeyResponse]:
    """List all API keys for tenant."""
    result = await db.execute(select(APIKey).where(APIKey.tenant_id == tenant.id))
    keys = result.scalars().all()

    return [
        APIKeyResponse(
            id=key.id,
            name=key.name,
            key_preview="****" + key.key_hash[-4:],
            is_active=key.is_active,
            created_at=key.created_at,
            last_used_at=key.last_used_at,
        )
        for key in keys
    ]


@router.delete("/{tenant_id}/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: str,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Revoke an API key."""
    result = await db.execute(
        select(APIKey).where(APIKey.id == key_id, APIKey.tenant_id == tenant.id)
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

    api_key.is_active = False
    await db.commit()
