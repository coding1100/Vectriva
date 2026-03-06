"""Google Calendar integration API endpoints."""

import secrets
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.database import get_db
from ..models.database import Integration, Tenant
from ..models.schemas import (
    GoogleAuthURLResponse,
    GoogleCalendarInfo,
    GoogleCalendarsResponse,
    GoogleCallbackRequest,
    IntegrationStatusResponse,
    SetCalendarRequest,
)
from ..services.encryption_service import encrypt_token
from .middleware import get_current_tenant

router = APIRouter(prefix="/tenants/{tenant_id}/integrations", tags=["integrations"])
callback_router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("/google/auth-url", response_model=GoogleAuthURLResponse)
async def get_google_auth_url(
    tenant: Tenant = Depends(get_current_tenant), db: AsyncSession = Depends(get_db)
) -> GoogleAuthURLResponse:
    """Get Google OAuth authorization URL."""
    state_token = secrets.token_urlsafe(32)

    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [settings.google_redirect_uri],
            }
        },
        scopes=settings.google_oauth_scopes,
        redirect_uri=settings.google_redirect_uri,
    )

    auth_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        state=f"{tenant.id}:{state_token}",
    )

    return GoogleAuthURLResponse(auth_url=auth_url, state_token=state_token)


@callback_router.post("/google/callback")
async def google_callback(
    request: GoogleCallbackRequest, db: AsyncSession = Depends(get_db)
) -> dict[str, str]:
    """Handle Google OAuth callback."""
    try:
        tenant_id, state_token = request.state.split(":")
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid state")

    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [settings.google_redirect_uri],
            }
        },
        scopes=settings.google_oauth_scopes,
        redirect_uri=settings.google_redirect_uri,
    )

    flow.fetch_token(code=request.code)
    creds = flow.credentials

    result = await db.execute(
        select(Integration).where(
            Integration.tenant_id == tenant_id, Integration.provider == "google_calendar"
        )
    )
    integration = result.scalar_one_or_none()

    encrypted_access = encrypt_token(creds.token, tenant_id)
    encrypted_refresh = encrypt_token(creds.refresh_token, tenant_id) if creds.refresh_token else None

    if integration:
        integration.encrypted_access_token = encrypted_access
        integration.encrypted_refresh_token = encrypted_refresh
        integration.expires_at = creds.expiry
    else:
        integration = Integration(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            provider="google_calendar",
            encrypted_access_token=encrypted_access,
            encrypted_refresh_token=encrypted_refresh,
            expires_at=creds.expiry,
        )
        db.add(integration)

    await db.commit()

    return {"status": "success", "tenant_id": tenant_id}


@router.get("/google/calendars", response_model=GoogleCalendarsResponse)
async def list_google_calendars(
    tenant: Tenant = Depends(get_current_tenant), db: AsyncSession = Depends(get_db)
) -> GoogleCalendarsResponse:
    """List available Google Calendars."""
    from ..services.calendar_service import get_calendar_credentials

    creds = await get_calendar_credentials(db, tenant.id)
    service = build("calendar", "v3", credentials=creds)

    calendars = []
    try:
        # Get the standard list of calendars
        calendar_list = service.calendarList().list().execute()
        for cal in calendar_list.get("items", []):
            calendars.append(
                GoogleCalendarInfo(
                    id=cal["id"],
                    summary=cal.get("summary", "Unnamed Calendar"),
                    primary=cal.get("primary", False),
                )
            )
            
        # If the list is empty (common for service accounts), try to get primary directly
        if not calendars:
            try:
                primary = service.calendars().get(calendarId="primary").execute()
                calendars.append(
                    GoogleCalendarInfo(
                        id=primary["id"],
                        summary=primary.get("summary", "Service Account Primary"),
                        primary=True,
                    )
                )
            except Exception:
                pass
                
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch calendars: {e}",
        )

    return GoogleCalendarsResponse(calendars=calendars)


@router.put("/google/calendar")
async def set_booking_calendar(
    request: SetCalendarRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Set the calendar to use for bookings."""
    result = await db.execute(
        select(Integration).where(
            Integration.tenant_id == tenant.id, Integration.provider == "google_calendar"
        )
    )
    integration = result.scalar_one_or_none()

    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Google Calendar not connected"
        )

    integration.calendar_id = request.calendar_id
    await db.commit()

    return {"status": "success", "calendar_id": request.calendar_id}


@router.get("/google/status", response_model=IntegrationStatusResponse)
async def get_google_integration_status(
    tenant: Tenant = Depends(get_current_tenant), db: AsyncSession = Depends(get_db)
) -> IntegrationStatusResponse:
    """Get Google Calendar integration status."""
    from ..services.calendar_service import _get_service_account_credentials
    
    result = await db.execute(
        select(Integration).where(
            Integration.tenant_id == tenant.id, Integration.provider == "google_calendar"
        )
    )
    integration = result.scalar_one_or_none()

    # Check if we have service account credentials
    sa_creds = _get_service_account_credentials()

    if not integration and not sa_creds:
        return IntegrationStatusResponse(connected=False, calendar_id=None, calendar_name=None)

    # If we have either integration OR sa_creds, we are "connected"
    calendar_name = None
    calendar_id = integration.calendar_id if integration else None
    
    if sa_creds and not calendar_id:
        # Default to the service account primary if nothing explicitly set yet
        calendar_id = "primary"
        
    return IntegrationStatusResponse(
        connected=True,
        calendar_id=calendar_id,
        calendar_name=calendar_name,
    )

@router.put("/google/calendar")
async def set_booking_calendar(
    request: SetCalendarRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Set the calendar to use for bookings."""
    import uuid
    from ..services.calendar_service import _get_service_account_credentials
    
    result = await db.execute(
        select(Integration).where(
            Integration.tenant_id == tenant.id, Integration.provider == "google_calendar"
        )
    )
    integration = result.scalar_one_or_none()

    if not integration:
        # If no integration exists, but we have SA creds, create the integration record to store the calendar_id
        sa_creds = _get_service_account_credentials()
        if not sa_creds:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Google Calendar not connected"
            )
            
        integration = Integration(
            id=str(uuid.uuid4()),
            tenant_id=tenant.id,
            provider="google_calendar",
            calendar_id=request.calendar_id,
            encrypted_access_token="service_account",
        )
        db.add(integration)
    else:
        integration.calendar_id = request.calendar_id
        
    await db.commit()

    return {"status": "success", "calendar_id": request.calendar_id}


@router.delete("/google", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_google_calendar(
    tenant: Tenant = Depends(get_current_tenant), db: AsyncSession = Depends(get_db)
) -> None:
    """Disconnect Google Calendar integration."""
    result = await db.execute(
        select(Integration).where(
            Integration.tenant_id == tenant.id, Integration.provider == "google_calendar"
        )
    )
    integration = result.scalar_one_or_none()

    if integration:
        await db.delete(integration)
        await db.commit()
