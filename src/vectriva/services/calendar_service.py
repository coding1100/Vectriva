"""Google Calendar integration service."""

import uuid
from datetime import date, datetime, timedelta
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
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


async def get_calendar_credentials(db: AsyncSession, tenant_id: str) -> Credentials:
    """Get decrypted Google Calendar credentials for tenant."""
    result = await db.execute(
        select(Integration).where(
            Integration.tenant_id == tenant_id, Integration.provider == "google_calendar"
        )
    )
    integration = result.scalar_one_or_none()

    if not integration:
        raise CalendarNotConnectedError("Google Calendar not connected")

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


async def check_availability(
    db: AsyncSession, tenant_id: str, input_data: CheckAvailabilityInput
) -> CheckAvailabilityOutput:
    """Check calendar availability for given date."""
    if input_data.date < date.today():
        raise DateOutOfRangeError("Cannot book in the past")

    if input_data.date > date.today() + timedelta(days=settings.max_booking_days_ahead):
        raise DateOutOfRangeError(f"Cannot book more than {settings.max_booking_days_ahead} days ahead")

    try:
        import pytz
        tz = pytz.timezone(input_data.timezone)
    except Exception as e:
        raise InvalidTimezoneError(f"Invalid timezone: {input_data.timezone}") from e

    creds = await get_calendar_credentials(db, tenant_id)
    service = build("calendar", "v3", credentials=creds)

    result = await db.execute(
        select(Integration).where(
            Integration.tenant_id == tenant_id, Integration.provider == "google_calendar"
        )
    )
    integration = result.scalar_one()
    calendar_id = integration.calendar_id or "primary"

    start_of_day = datetime.combine(input_data.date, datetime.min.time())
    end_of_day = datetime.combine(input_data.date, datetime.max.time())

    try:
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=start_of_day.isoformat() + "Z",
            timeMax=end_of_day.isoformat() + "Z",
            singleEvents=True,
            orderBy="startTime",
        ).execute()
    except Exception as e:
        raise CalendarAPIError(f"Failed to fetch calendar events: {e}") from e

    events = events_result.get("items", [])
    busy_slots = [
        (
            datetime.fromisoformat(event["start"].get("dateTime", event["start"].get("date"))),
            datetime.fromisoformat(event["end"].get("dateTime", event["end"].get("date"))),
        )
        for event in events
    ]

    available_slots = _find_available_slots(
        input_data.date, input_data.duration_minutes, busy_slots
    )

    return CheckAvailabilityOutput(
        available_slots=available_slots, calendar_id=calendar_id, checked_date=input_data.date
    )


def _find_available_slots(
    target_date: date, duration_minutes: int, busy_slots: list[tuple[datetime, datetime]]
) -> list[TimeSlot]:
    """Find available slots for the given date."""
    business_start = datetime.combine(target_date, datetime.min.time()).replace(hour=9)
    business_end = datetime.combine(target_date, datetime.min.time()).replace(hour=17)

    current_time = business_start
    slots: list[TimeSlot] = []
    duration = timedelta(minutes=duration_minutes)

    while current_time + duration <= business_end:
        slot_end = current_time + duration
        is_available = not any(
            (current_time < busy_end and slot_end > busy_start)
            for busy_start, busy_end in busy_slots
        )

        if is_available:
            slots.append(TimeSlot(start=current_time, end=slot_end))

        current_time += timedelta(minutes=30)

    return slots


async def create_event(
    db: AsyncSession, tenant_id: str, input_data: CreateEventInput
) -> CreateEventOutput:
    """Create calendar event with Google Meet link."""
    if input_data.start_time < datetime.utcnow():
        raise EventInPastError("Cannot create event in the past")

    if input_data.end_time <= input_data.start_time:
        raise ValueError("End time must be after start time")

    creds = await get_calendar_credentials(db, tenant_id)
    service = build("calendar", "v3", credentials=creds)

    result = await db.execute(
        select(Integration).where(
            Integration.tenant_id == tenant_id, Integration.provider == "google_calendar"
        )
    )
    integration = result.scalar_one()
    calendar_id = integration.calendar_id or "primary"

    event_body = {
        "summary": input_data.summary,
        "description": input_data.description,
        "start": {"dateTime": input_data.start_time.isoformat(), "timeZone": "UTC"},
        "end": {"dateTime": input_data.end_time.isoformat(), "timeZone": "UTC"},
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

    return CreateEventOutput(
        event_id=created_event["id"],
        meet_link=meet_link,
        calendar_link=calendar_link,
        start_time=input_data.start_time,
        end_time=input_data.end_time,
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

    integration_result = await db.execute(
        select(Integration).where(
            Integration.tenant_id == tenant_id, Integration.provider == "google_calendar"
        )
    )
    integration = integration_result.scalar_one()
    calendar_id = integration.calendar_id or "primary"

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

    integration_result = await db.execute(
        select(Integration).where(
            Integration.tenant_id == tenant_id, Integration.provider == "google_calendar"
        )
    )
    integration = integration_result.scalar_one()
    calendar_id = integration.calendar_id or "primary"

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
