"""State definitions for LangGraph agent."""

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel

from .context import AgentContext, TimeSlot


class IntentClassificationResult(BaseModel):
    """Result of intent classification."""

    intent: Literal[
        "informational",
        "comparison",
        "buying_intent",
        "booking_intent",
        "escalation_request",
        "unclear",
    ]
    confidence: float
    reasoning: str


class BookingAction(BaseModel):
    """Result of booking router."""

    action: Literal["new_booking", "reschedule", "cancel"]
    event_id: str | None = None


class DateTimeExtraction(BaseModel):
    """Extracted date/time from user message."""

    preferred_date: date
    preferred_time_range: tuple[int, int] | None = None
    is_flexible: bool = True
    raw_text: str


class ProductComparison(BaseModel):
    """Structured product comparison."""

    products: list[str]
    comparison_attributes: list[str]
    table: dict[str, dict[str, Any]]


class ProductRecommendation(BaseModel):
    """Product recommendation result."""

    product_name: str
    reasoning: str
    confidence: float
    relevant_chunks: list[str]


class StateInput(BaseModel):
    """Common input to all states."""

    context: AgentContext
    user_message: str
    additional_data: dict[str, Any] = {}


class StateOutput(BaseModel):
    """Common output from all states."""

    next_state: str
    context_updates: dict[str, Any]
    response_data: dict[str, Any] = {}
    tool_results: dict[str, Any] = {}


async def intent_classification_state(input_data: StateInput) -> StateOutput:
    """
    Classify user intent using LLM with structured output.

    Transitions:
    - informational -> KnowledgeRetrieval
    - comparison -> ProductComparison
    - buying_intent -> RecommendationEngine
    - booking_intent -> BookingRouter
    - escalation_request -> HumanEscalation
    - unclear -> Clarification
    """
    raise NotImplementedError("LLM integration required")


async def knowledge_retrieval_state(input_data: StateInput) -> StateOutput:
    """
    Execute RAG query against tenant documents.

    Transitions: Always -> ResponseGeneration
    """
    raise NotImplementedError("RAG service integration required")


async def product_comparison_state(input_data: StateInput) -> StateOutput:
    """
    Retrieve and structure product comparison.

    Transitions: Always -> ResponseGeneration
    """
    raise NotImplementedError("RAG + LLM integration required")


async def recommendation_engine_state(input_data: StateInput) -> StateOutput:
    """
    Generate product recommendations based on user requirements.

    Transitions: Always -> ResponseGeneration
    """
    raise NotImplementedError("RAG + LLM integration required")


async def booking_router_state(input_data: StateInput) -> StateOutput:
    """
    Determine booking sub-intent.

    Transitions:
    - new_booking -> BookingExtractDateTime
    - reschedule -> RescheduleFlow
    - cancel -> CancelFlow
    """
    raise NotImplementedError("LLM integration required")


async def booking_extract_datetime_state(input_data: StateInput) -> StateOutput:
    """
    Extract date/time preferences from user message.

    Transitions: Always -> BookingCheckAvailability
    """
    raise NotImplementedError("LLM integration required")


async def booking_check_availability_state(input_data: StateInput) -> StateOutput:
    """
    Query Google Calendar for available slots.

    Transitions:
    - slots_found (len > 0) -> BookingOfferSlots
    - no_slots -> BookingNoSlots
    """
    raise NotImplementedError("Calendar service integration required")


async def booking_offer_slots_state(input_data: StateInput) -> StateOutput:
    """
    Format and present available slots to user.

    Transitions: Wait for user selection (next turn)
    """
    raise NotImplementedError("Formatting logic required")


async def booking_confirm_slot_state(input_data: StateInput) -> StateOutput:
    """
    Confirm user's slot selection.

    Transitions: Always -> BookingCreateEvent
    """
    raise NotImplementedError("LLM integration required")


async def booking_create_event_state(input_data: StateInput) -> StateOutput:
    """
    Create calendar event with Google Meet link.

    Transitions: Always -> BookingSuccess
    """
    raise NotImplementedError("Calendar service integration required")


async def booking_success_state(input_data: StateInput) -> StateOutput:
    """
    Confirm booking success.

    Transitions: Always -> ResponseGeneration
    """
    raise NotImplementedError("Formatting logic required")


async def booking_no_slots_state(input_data: StateInput) -> StateOutput:
    """
    Handle no available slots scenario.

    Transitions: Always -> ResponseGeneration
    """
    raise NotImplementedError("Formatting logic required")


async def reschedule_flow_state(input_data: StateInput) -> StateOutput:
    """
    Handle rescheduling flow.

    Transitions: -> BookingCheckAvailability
    """
    raise NotImplementedError("Logic required")


async def cancel_flow_state(input_data: StateInput) -> StateOutput:
    """
    Handle cancellation flow.

    Transitions: -> BookingCancelEvent
    """
    raise NotImplementedError("Logic required")


async def booking_cancel_event_state(input_data: StateInput) -> StateOutput:
    """
    Cancel calendar event.

    Transitions: Always -> BookingSuccess
    """
    raise NotImplementedError("Calendar service integration required")


async def human_escalation_state(input_data: StateInput) -> StateOutput:
    """
    Flag conversation for human review and restrict capabilities.

    Transitions: Always -> EscalatedMode
    """
    raise NotImplementedError("Escalation service integration required")


async def escalated_mode_state(input_data: StateInput) -> StateOutput:
    """
    Continue conversation with restricted capabilities.

    Transitions: Only -> KnowledgeRetrieval
    """
    raise NotImplementedError("Logic required")


async def clarification_state(input_data: StateInput) -> StateOutput:
    """
    Ask clarifying questions.

    Transitions: Wait for user response -> IntentClassification
    """
    raise NotImplementedError("LLM integration required")


async def response_generation_state(input_data: StateInput) -> StateOutput:
    """
    Generate final response to user.

    Transitions: End turn
    """
    raise NotImplementedError("LLM integration required")
