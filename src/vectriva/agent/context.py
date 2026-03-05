"""Agent conversation context model."""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel


class Message(BaseModel):
    """A single message in the conversation."""

    role: str  # "user" | "agent"
    content: str
    timestamp: datetime
    metadata: dict[str, Any] = {}


class TimeRange(BaseModel):
    """A time range preference."""

    start_hour: int  # 0-23
    end_hour: int  # 0-23


class TimeSlot(BaseModel):
    """A specific time slot."""

    start: datetime  # UTC
    end: datetime  # UTC


@dataclass
class AgentContext:
    """Context that persists across conversation turns."""

    # Identity
    conversation_id: str
    tenant_id: str
    customer_id: str | None = None

    # Conversation State
    current_state: str = "IntentClassification"
    turn_count: int = 0
    messages: list[Message] = field(default_factory=list)

    # Intent Tracking
    last_intent: str | None = None
    intent_history: list[str] = field(default_factory=list)

    # Booking Context (persists across turns)
    booking_flow_active: bool = False
    preferred_date: date | None = None
    preferred_time_range: TimeRange | None = None
    selected_slot: TimeSlot | None = None
    pending_event_id: str | None = None

    # Escalation State
    is_escalated: bool = False
    escalation_reason: str | None = None

    # Error Tracking
    consecutive_errors: int = 0
    tool_call_count: int = 0

    # Metadata
    customer_timezone: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for Redis storage."""
        return {
            "conversation_id": self.conversation_id,
            "tenant_id": self.tenant_id,
            "customer_id": self.customer_id,
            "current_state": self.current_state,
            "turn_count": self.turn_count,
            "messages": [msg.model_dump(mode="json") for msg in self.messages],
            "last_intent": self.last_intent,
            "intent_history": self.intent_history,
            "booking_flow_active": self.booking_flow_active,
            "preferred_date": self.preferred_date.isoformat() if self.preferred_date else None,
            "preferred_time_range": (
                self.preferred_time_range.model_dump() if self.preferred_time_range else None
            ),
            "selected_slot": self.selected_slot.model_dump(mode="json") if self.selected_slot else None,
            "pending_event_id": self.pending_event_id,
            "is_escalated": self.is_escalated,
            "escalation_reason": self.escalation_reason,
            "consecutive_errors": self.consecutive_errors,
            "tool_call_count": self.tool_call_count,
            "customer_timezone": self.customer_timezone,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentContext":
        """Deserialize from dict."""
        messages = [Message(**msg) for msg in data.get("messages", [])]
        preferred_date_str = data.get("preferred_date")
        preferred_time_range_dict = data.get("preferred_time_range")
        selected_slot_dict = data.get("selected_slot")

        return cls(
            conversation_id=data["conversation_id"],
            tenant_id=data["tenant_id"],
            customer_id=data.get("customer_id"),
            current_state=data.get("current_state", "IntentClassification"),
            turn_count=data.get("turn_count", 0),
            messages=messages,
            last_intent=data.get("last_intent"),
            intent_history=data.get("intent_history", []),
            booking_flow_active=data.get("booking_flow_active", False),
            preferred_date=date.fromisoformat(preferred_date_str) if preferred_date_str else None,
            preferred_time_range=(
                TimeRange(**preferred_time_range_dict) if preferred_time_range_dict else None
            ),
            selected_slot=TimeSlot(**selected_slot_dict) if selected_slot_dict else None,
            pending_event_id=data.get("pending_event_id"),
            is_escalated=data.get("is_escalated", False),
            escalation_reason=data.get("escalation_reason"),
            consecutive_errors=data.get("consecutive_errors", 0),
            tool_call_count=data.get("tool_call_count", 0),
            customer_timezone=data.get("customer_timezone"),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )
