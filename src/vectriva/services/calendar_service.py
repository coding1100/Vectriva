"""Google Calendar integration service."""

import logging
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from googleapiclient.discovery import build
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..agent.tools import (
    CancelEventInput,
    CancelEventOutput,
    CheckAvailabilityInput,
    CheckAvailabilityOutput,
    CreateEventInput,
    CreateEventOutput,
    RescheduleEventInput,
    RescheduleEventOutput,
    TimeSlot,
)
from ..core.config import settings
from ..core.errors import (
    CalendarAPIError,
    CalendarNotConnectedError,
    DateOutOfRangeError,
    EventInPastError,
    EventNotFoundError,
    InvalidTimezoneError,
    SlotNoLongerAvailableError,
)
from ..models.database import CalendarEvent, Integration
from .encryption_service import decrypt_token, encrypt_token

logger = logging.getLogger(__name__)

CALENDAR_SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
]


def _get_service_account_credentials() -> service_account.Credentials | None:
    """Load service account credentials from the configured JSON file."""
    sa_path = settings.google_service_account_path
    if not sa_path:
        # Fallback to hardcoded root path if settings wasn't reloaded
        sa_path = "creds.json"

    path = Path(sa_path)
    if not path.is_absolute():
        path = Path.cwd() / path

    print(f"Checking for service account at: {path}")
    if not path.exists():
        print(f"Service account file NOT FOUND: {path}")
        logger.warning("Service account file not found: %s", path)
        return None

    print(f"Service account file FOUND: {path}")
    return service_account.Credentials.from_service_account_file(
        str(path), scopes=CALENDAR_SCOPES
    )


async def get_calendar_credentials(db: AsyncSession, tenant_id: str) -> Credentials | service_account.Credentials:
    """Get Google Calendar credentials for tenant.

    Tries per-tenant OAuth first, falls back to service account.
    """
    result = await db.execute(
        select(Integration).where(
            Integration.tenant_id == tenant_id, Integration.provider == "google_calendar"
        )
    )
    integration = result.scalar_one_or_none()

    if integration and integration.encrypted_access_token:
        access_token = decrypt_token(integration.encrypted_access_token, tenant_id)
        refresh_token = (
            decrypt_token(integration.encrypted_refresh_token, tenant_id)
            if integration.encrypted_refresh_token
            else None
        )

        creds = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
        )

        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            integration.encrypted_access_token = encrypt_token(creds.token, tenant_id)
            integration.expires_at = creds.expiry
            await db.flush()

        return creds

    sa_creds = _get_service_account_credentials()
    if sa_creds:
        return sa_creds

    raise CalendarNotConnectedError("Google Calendar not connected and no service account configured")


async def _get_calendar_id(db: AsyncSession, tenant_id: str) -> str:
    """Resolve target calendar ID for tenant."""
    result = await db.execute(
        select(Integration).where(
            Integration.tenant_id == tenant_id, Integration.provider == "google_calendar"
        )
    )
    integration = result.scalar_one_or_none()
    if integration and integration.calendar_id:
        return integration.calendar_id
    return "primary"


async def _get_tenant_timezone(db: AsyncSession, tenant_id: str) -> ZoneInfo:
    """Get tenant business timezone, defaulting to UTC."""
    from ..models.database import Tenant

    result = await db.execute(select(Tenant.timezone).where(Tenant.id == tenant_id))
    timezone_str = result.scalar_one_or_none() or "UTC"
    try:
        return ZoneInfo(timezone_str)
    except Exception as e:
        raise InvalidTimezoneError(f"Invalid tenant timezone: {timezone_str}") from e


def _parse_timezone(timezone_str: str) -> ZoneInfo:
    """Parse an IANA timezone string into ZoneInfo."""
    try:
        return ZoneInfo(timezone_str)
    except Exception as e:
        raise InvalidTimezoneError(f"Invalid timezone: {timezone_str}") from e


def _to_utc_aware(dt: datetime) -> datetime:
    """Normalize datetime to timezone-aware UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(ZoneInfo("UTC"))


def _parse_google_event_time(raw: dict[str, str]) -> tuple[datetime, datetime]:
    """Parse Google Calendar event start/end into UTC-aware datetimes."""
    start_raw = raw.get("start", {}).get("dateTime")
    end_raw = raw.get("end", {}).get("dateTime")
    if not start_raw or not end_raw:
        # Skip all-day events for slot-level scheduling.
        raise ValueError("All-day event without dateTime")
    start = datetime.fromisoformat(start_raw).astimezone(ZoneInfo("UTC"))
    end = datetime.fromisoformat(end_raw).astimezone(ZoneInfo("UTC"))
    return start, end


async def check_availability(
    db: AsyncSession, tenant_id: str, input_data: CheckAvailabilityInput
) -> CheckAvailabilityOutput:
    """Check availability for a user's local date against tenant business hours.

    Returns slots in UTC for deterministic booking creation.
    """
    user_tz = _parse_timezone(input_data.timezone)
    tenant_tz = await _get_tenant_timezone(db, tenant_id)

    today_in_user_tz = datetime.now(user_tz).date()
    if input_data.date < today_in_user_tz:
        raise DateOutOfRangeError("Cannot book in the past")

    if input_data.date > today_in_user_tz + timedelta(days=settings.max_booking_days_ahead):
        raise DateOutOfRangeError(f"Cannot book more than {settings.max_booking_days_ahead} days ahead")

    creds = await get_calendar_credentials(db, tenant_id)
    service = build("calendar", "v3", credentials=creds)
    calendar_id = await _get_calendar_id(db, tenant_id)

    user_day_start = datetime.combine(input_data.date, datetime.min.time(), tzinfo=user_tz)
    user_day_end = user_day_start + timedelta(days=1)
    user_day_start_utc = user_day_start.astimezone(ZoneInfo("UTC"))
    user_day_end_utc = user_day_end.astimezone(ZoneInfo("UTC"))

    first_business_date = user_day_start_utc.astimezone(tenant_tz).date() - timedelta(days=1)
    last_business_date = user_day_end_utc.astimezone(tenant_tz).date() + timedelta(days=1)

    try:
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=user_day_start_utc.isoformat().replace("+00:00", "Z"),
            timeMax=user_day_end_utc.isoformat().replace("+00:00", "Z"),
            singleEvents=True,
            orderBy="startTime",
        ).execute()
    except Exception as e:
        raise CalendarAPIError(f"Failed to fetch calendar events: {e}") from e

    busy_slots: list[tuple[datetime, datetime]] = []
    for event in events_result.get("items", []):
        try:
            busy_slots.append(_parse_google_event_time(event))
        except ValueError:
            continue

    available_slots = _find_available_slots(
        first_business_date=first_business_date,
        last_business_date=last_business_date,
        duration_minutes=input_data.duration_minutes,
        busy_slots=busy_slots,
        tenant_tz=tenant_tz,
        user_day_start_utc=user_day_start_utc,
        user_day_end_utc=user_day_end_utc,
    )

    return CheckAvailabilityOutput(
        available_slots=available_slots, calendar_id=calendar_id, checked_date=input_data.date
    )


def _find_available_slots(
    first_business_date: date,
    last_business_date: date,
    duration_minutes: int,
    busy_slots: list[tuple[datetime, datetime]],
    tenant_tz: ZoneInfo,
    user_day_start_utc: datetime,
    user_day_end_utc: datetime,
) -> list[TimeSlot]:
    """Find available slots across tenant business hours, clipped to user day."""
    slots: list[TimeSlot] = []
    duration = timedelta(minutes=duration_minutes)
    business_date = first_business_date

    while business_date <= last_business_date:
        business_start_local = datetime.combine(
            business_date, datetime.min.time(), tzinfo=tenant_tz
        ).replace(hour=9, minute=0, second=0, microsecond=0)
        business_end_local = datetime.combine(
            business_date, datetime.min.time(), tzinfo=tenant_tz
        ).replace(hour=17, minute=0, second=0, microsecond=0)

        current_time = max(
            business_start_local.astimezone(ZoneInfo("UTC")), user_day_start_utc
        )
        window_end = min(
            business_end_local.astimezone(ZoneInfo("UTC")), user_day_end_utc
        )

        while current_time + duration <= window_end:
            slot_end = current_time + duration
            is_available = not any(
                (current_time < busy_end and slot_end > busy_start)
                for busy_start, busy_end in busy_slots
            )
            if is_available:
                slots.append(TimeSlot(start=current_time, end=slot_end))
            current_time += timedelta(minutes=30)

        business_date += timedelta(days=1)

    return slots


async def create_event(
    db: AsyncSession, tenant_id: str, input_data: CreateEventInput
) -> CreateEventOutput:
    """Create calendar event with Google Meet link."""
    start_utc = _to_utc_aware(input_data.start_time)
    end_utc = _to_utc_aware(input_data.end_time)

    if start_utc < datetime.now(ZoneInfo("UTC")):
        raise EventInPastError("Cannot create event in the past")

    if end_utc <= start_utc:
        raise ValueError("End time must be after start time")

    creds = await get_calendar_credentials(db, tenant_id)
    service = build("calendar", "v3", credentials=creds)
    calendar_id = await _get_calendar_id(db, tenant_id)

    event_body = {
        "summary": input_data.summary,
        "description": input_data.description,
        "start": {"dateTime": start_utc.isoformat(), "timeZone": "UTC"},
        "end": {"dateTime": end_utc.isoformat(), "timeZone": "UTC"},
        "attendees": [{"email": input_data.customer_email, "displayName": input_data.customer_name}],
        "conferenceData": {
            "createRequest": {
                "requestId": str(uuid.uuid4()),
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        },
    }

    try:
        created_event = service.events().insert(
            calendarId=calendar_id,
            body=event_body,
            conferenceDataVersion=1,
        ).execute()
    except Exception as e:
        raise CalendarAPIError(f"Failed to create event: {e}") from e

    meet_link = created_event.get("conferenceData", {}).get("entryPoints", [{}])[0].get("uri", "")
    calendar_link = created_event.get("htmlLink", "")

    event_record = CalendarEvent(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        conversation_id=input_data.description if input_data.description.startswith("conv:") else None,
        google_event_id=created_event["id"],
        customer_email=input_data.customer_email,
        customer_name=input_data.customer_name,
        start_time=start_utc.replace(tzinfo=None),
        end_time=end_utc.replace(tzinfo=None),
        meet_link=meet_link or None,
        status="scheduled",
    )
    db.add(event_record)
    await db.flush()

    return CreateEventOutput(
        event_id=event_record.id,
        meet_link=meet_link,
        calendar_link=calendar_link,
        start_time=start_utc,
        end_time=end_utc,
    )


async def reschedule_event(
    db: AsyncSession, tenant_id: str, input_data: RescheduleEventInput
) -> RescheduleEventOutput:
    """Reschedule an existing event."""
    if input_data.new_start_time < datetime.utcnow():
        raise EventInPastError("Cannot reschedule to the past")

    result = await db.execute(
        select(CalendarEvent).where(
            CalendarEvent.id == input_data.event_id,
            CalendarEvent.tenant_id == tenant_id,
        )
    )
    event_record = result.scalar_one_or_none()
    if not event_record:
        raise EventNotFoundError(f"Event {input_data.event_id} not found")

    creds = await get_calendar_credentials(db, tenant_id)
    service = build("calendar", "v3", credentials=creds)
    calendar_id = await _get_calendar_id(db, tenant_id)

    try:
        google_event = service.events().get(
            calendarId=calendar_id, eventId=event_record.google_event_id
        ).execute()

        google_event["start"] = {"dateTime": input_data.new_start_time.isoformat(), "timeZone": "UTC"}
        google_event["end"] = {"dateTime": input_data.new_end_time.isoformat(), "timeZone": "UTC"}

        updated_event = service.events().update(
            calendarId=calendar_id,
            eventId=event_record.google_event_id,
            body=google_event,
        ).execute()
    except Exception as e:
        raise CalendarAPIError(f"Failed to reschedule event: {e}") from e

    old_time = TimeSlot(start=event_record.start_time, end=event_record.end_time)
    new_time = TimeSlot(start=input_data.new_start_time, end=input_data.new_end_time)

    event_record.start_time = input_data.new_start_time
    event_record.end_time = input_data.new_end_time
    event_record.status = "rescheduled"
    await db.flush()

    meet_link = updated_event.get("conferenceData", {}).get("entryPoints", [{}])[0].get("uri", "")

    return RescheduleEventOutput(
        event_id=input_data.event_id,
        old_time=old_time,
        new_time=new_time,
        meet_link=meet_link,
    )


async def cancel_event(
    db: AsyncSession, tenant_id: str, input_data: CancelEventInput
) -> CancelEventOutput:
    """Cancel a calendar event."""
    result = await db.execute(
        select(CalendarEvent).where(
            CalendarEvent.id == input_data.event_id,
            CalendarEvent.tenant_id == tenant_id,
        )
    )
    event_record = result.scalar_one_or_none()
    if not event_record:
        raise EventNotFoundError(f"Event {input_data.event_id} not found")

    if event_record.start_time < datetime.utcnow():
        raise EventInPastError("Cannot cancel past event")

    creds = await get_calendar_credentials(db, tenant_id)
    service = build("calendar", "v3", credentials=creds)
    calendar_id = await _get_calendar_id(db, tenant_id)

    try:
        service.events().delete(
            calendarId=calendar_id, eventId=event_record.google_event_id
        ).execute()
    except Exception as e:
        raise CalendarAPIError(f"Failed to cancel event: {e}") from e

    event_record.status = "cancelled"
    await db.flush()

    return CancelEventOutput(
        event_id=input_data.event_id,
        cancelled_at=datetime.utcnow(),
        was_notified=True,
    )
