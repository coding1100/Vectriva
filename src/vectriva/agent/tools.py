"""Agent tool schemas and definitions."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, HttpUrl


# ============================================================================
# check_availability Tool
# ============================================================================


class CheckAvailabilityInput(BaseModel):
    """Input schema for checking calendar availability."""

    date: date
    duration_minutes: int = Field(default=30, ge=15, le=120)
    timezone: str = Field(description="IANA timezone, e.g. America/New_York")


class TimeSlot(BaseModel):
    """A time slot with start and end times in UTC."""

    start: datetime
    end: datetime


class CheckAvailabilityOutput(BaseModel):
    """Output schema for availability check."""

    available_slots: list[TimeSlot]
    calendar_id: str
    checked_date: date


# ============================================================================
# create_event Tool
# ============================================================================


class CreateEventInput(BaseModel):
    """Input schema for creating a calendar event."""

    start_time: datetime
    end_time: datetime
    customer_email: EmailStr
    customer_name: str = Field(min_length=1, max_length=100)
    summary: str = Field(default="Consultation Booking")
    description: str = Field(default="")


class CreateEventOutput(BaseModel):
    """Output schema for event creation."""

    event_id: str
    meet_link: str = ""
    calendar_link: str = ""
    start_time: datetime
    end_time: datetime


# ============================================================================
# reschedule_event Tool
# ============================================================================


class RescheduleEventInput(BaseModel):
    """Input schema for rescheduling an event."""

    event_id: str
    new_start_time: datetime
    new_end_time: datetime


class RescheduleEventOutput(BaseModel):
    """Output schema for event rescheduling."""

    event_id: str
    old_time: TimeSlot
    new_time: TimeSlot
    meet_link: str = ""


# ============================================================================
# cancel_event Tool
# ============================================================================


class CancelEventInput(BaseModel):
    """Input schema for canceling an event."""

    event_id: str
    cancellation_reason: str = Field(default="Cancelled by customer")


class CancelEventOutput(BaseModel):
    """Output schema for event cancellation."""

    event_id: str
    cancelled_at: datetime
    was_notified: bool


# ============================================================================
# retrieve_product_data Tool
# ============================================================================


class RetrieveProductDataInput(BaseModel):
    """Input schema for RAG retrieval."""

    query: str = Field(min_length=1, max_length=500)
    top_k: int = Field(default=5, ge=1, le=20)
    filter_document_types: list[str] | None = None


class Chunk(BaseModel):
    """A retrieved document chunk."""

    content: str
    document_id: str
    document_name: str
    chunk_type: Literal["text", "table", "image_caption"]
    similarity_score: float
    metadata: dict[str, str | int | float | bool]


class RetrieveProductDataOutput(BaseModel):
    """Output schema for RAG retrieval."""

    chunks: list[Chunk]
    query_embedding_id: str


# ============================================================================
# escalate_to_human Tool
# ============================================================================


class EscalateToHumanInput(BaseModel):
    """Input schema for human escalation."""

    reason: Literal[
        "customer_request",
        "repeated_failures",
        "low_confidence",
        "sensitive_topic",
        "negative_sentiment",
    ]
    context_summary: str = Field(max_length=500)


class EscalateToHumanOutput(BaseModel):
    """Output schema for human escalation."""

    escalation_id: str
    escalated_at: datetime
    notification_sent: bool
