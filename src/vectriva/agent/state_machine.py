"""LangGraph state machine implementation."""

import json
import logging
import re
from datetime import date, datetime, timedelta
from typing import Annotated, Any
from zoneinfo import ZoneInfo

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from .context import AgentContext
from ..agent.tools import (
    CheckAvailabilityInput,
    CreateEventInput,
    CancelEventInput,
    RetrieveProductDataInput,
)
from ..core.config import settings
from ..core.errors import (
    CalendarNotConnectedError,
    NoDocumentsIndexedError,
)
from ..models.database import TenantConfig
from ..services.llm_factory import get_tenant_llm
from ..services.rag_service import retrieve_product_data

logger = logging.getLogger(__name__)

INTENT_CLASSIFICATION_PROMPT = """\
You are an intent classifier for a product-trained AI assistant.

Given the user's message and conversation history, classify the intent into exactly one of:
- "informational": The user is asking a factual question about products, features, or services.
- "comparison": The user wants to compare two or more products or options.
- "buying_intent": The user shows interest in purchasing or wants recommendations.
- "booking_intent": The user wants to book, schedule, reschedule, or cancel an appointment.
- "escalation_request": The user explicitly asks to speak with a human or is frustrated.
- "unclear": The message is too vague to classify.

Respond with ONLY a JSON object:
{"intent": "<one of the above>", "confidence": <0.0-1.0>, "reasoning": "<brief reason>"}
"""

RESPONSE_GENERATION_PROMPT = """\
You are a helpful, knowledgeable product assistant for a business.
Your persona name is: {persona_name}
Your tone should be: {tone}
{custom_instructions}

Use the following retrieved context to answer the user's question accurately.
If the context doesn't contain enough information, say so honestly — do not hallucinate.
Always be helpful and guide the user toward a solution.

--- RETRIEVED CONTEXT ---
{context}
--- END CONTEXT ---
"""

COMPARISON_PROMPT = """\
You are a product comparison specialist.
Your persona name is: {persona_name}
Your tone should be: {tone}

Compare the relevant products based on the retrieved context below.
Structure your response clearly with key differences, pros/cons, and a recommendation if appropriate.

--- RETRIEVED CONTEXT ---
{context}
--- END CONTEXT ---
"""

RECOMMENDATION_PROMPT = """\
You are a product recommendation specialist.
Your persona name is: {persona_name}
Your tone should be: {tone}

Based on the user's needs and the retrieved product information below,
provide a tailored recommendation. Explain why you recommend it and mention alternatives.

--- RETRIEVED CONTEXT ---
{context}
--- END CONTEXT ---
"""

CLARIFICATION_PROMPT = """\
You are a helpful assistant. The user's message was unclear.
Ask a brief, friendly clarifying question to understand what they need.
Keep it to 1-2 sentences.
"""

BOOKING_ROUTER_PROMPT = """\
You are a booking action classifier. Given the user's message about scheduling,
classify the action into exactly one of:
- "new_booking": The user wants to book/schedule a new appointment.
- "reschedule": The user wants to change an existing appointment.
- "cancel": The user wants to cancel an existing appointment.

Respond with ONLY a JSON object:
{{"action": "<one of the above>", "reasoning": "<brief reason>"}}
"""

BOOKING_EXTRACT_PROMPT = """\
You are a date/time extraction assistant. Today's date is {today}.

From the user's message, extract their preferred date and time for an appointment.
If they mention a relative date (like "tomorrow", "next Monday"), convert it to an absolute date.
If they mention a specific time, include it. If not, set preferred_time to null.

Respond with ONLY a JSON object:
{{"preferred_date": "<YYYY-MM-DD or null>", "preferred_time": "<HH:MM or null>", "duration_minutes": <int or 30>}}

User's message: {user_message}
"""


class GraphState(BaseModel):
    """The state that flows through the graph."""

    model_config = {"arbitrary_types_allowed": True}

    context: AgentContext
    messages: Annotated[list[Any], add_messages]
    next_action: str | None = None
    intent: str | None = None
    booking_action: str | None = None
    available_slots: list[dict[str, Any]] = []
    retrieved_chunks: list[dict[str, Any]] = []
    error: str | None = None


class VectrivaAgent:
    """The LangGraph-based agent orchestrator."""

    def __init__(self, db: AsyncSession | None = None) -> None:
        self._db: AsyncSession | None = db
        self._tenant_config: TenantConfig | None = None
        self.graph = self._build_graph()
        self.compiled_graph = self.graph.compile()

    def set_session(self, db: AsyncSession) -> None:
        self._db = db

    def set_tenant_config(self, config: TenantConfig | None) -> None:
        self._tenant_config = config

    def _get_llm(self) -> Any:
        return get_tenant_llm(self._tenant_config)

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph state machine."""
        graph = StateGraph(GraphState)

        graph.add_node("IntentClassification", self._intent_classification)
        graph.add_node("KnowledgeRetrieval", self._knowledge_retrieval)
        graph.add_node("ProductComparison", self._product_comparison)
        graph.add_node("RecommendationEngine", self._recommendation_engine)
        graph.add_node("BookingRouter", self._booking_router)
        graph.add_node("BookingExtractDateTime", self._booking_extract_datetime)
        graph.add_node("BookingCheckAvailability", self._booking_check_availability)
        graph.add_node("BookingOfferSlots", self._booking_offer_slots)
        graph.add_node("BookingConfirmSlot", self._booking_confirm_slot)
        graph.add_node("BookingCreateEvent", self._booking_create_event)
        graph.add_node("BookingSuccess", self._booking_success)
        graph.add_node("BookingNoSlots", self._booking_no_slots)
        graph.add_node("RescheduleFlow", self._reschedule_flow)
        graph.add_node("CancelFlow", self._cancel_flow)
        graph.add_node("BookingCancelEvent", self._booking_cancel_event)
        graph.add_node("HumanEscalation", self._human_escalation)
        graph.add_node("EscalatedMode", self._escalated_mode)
        graph.add_node("Clarification", self._clarification)
        graph.add_node("ResponseGeneration", self._response_generation)

        graph.set_entry_point("IntentClassification")

        graph.add_conditional_edges(
            "IntentClassification",
            self._route_intent,
            {
                "informational": "KnowledgeRetrieval",
                "comparison": "ProductComparison",
                "buying_intent": "RecommendationEngine",
                "booking_intent": "BookingRouter",
                "escalation_request": "HumanEscalation",
                "unclear": "Clarification",
            },
        )

        graph.add_edge("KnowledgeRetrieval", "ResponseGeneration")
        graph.add_edge("ProductComparison", "ResponseGeneration")
        graph.add_edge("RecommendationEngine", "ResponseGeneration")
        graph.add_edge("Clarification", END)

        graph.add_conditional_edges(
            "BookingRouter",
            self._route_booking,
            {
                "new_booking": "BookingExtractDateTime",
                "reschedule": "RescheduleFlow",
                "cancel": "CancelFlow",
                "not_configured": END,
            },
        )

        graph.add_edge("BookingExtractDateTime", "BookingCheckAvailability")
        graph.add_conditional_edges(
            "BookingCheckAvailability",
            self._route_availability,
            {
                "slots_found": "BookingOfferSlots",
                "no_slots": "BookingNoSlots",
            },
        )
        graph.add_edge("BookingOfferSlots", "BookingConfirmSlot")
        graph.add_edge("BookingConfirmSlot", "BookingCreateEvent")
        graph.add_edge("BookingCreateEvent", "BookingSuccess")
        graph.add_edge("BookingNoSlots", "ResponseGeneration")
        graph.add_edge("BookingSuccess", "ResponseGeneration")

        graph.add_edge("RescheduleFlow", "BookingCheckAvailability")
        graph.add_edge("CancelFlow", "BookingCancelEvent")
        graph.add_edge("BookingCancelEvent", "BookingSuccess")

        graph.add_edge("HumanEscalation", "EscalatedMode")
        graph.add_edge("EscalatedMode", "KnowledgeRetrieval")

        graph.add_edge("ResponseGeneration", END)

        return graph

    # ========================================================================
    # Routing Functions
    # ========================================================================

    def _route_intent(self, state: GraphState) -> str:
        return state.intent or "unclear"

    def _route_booking(self, state: GraphState) -> str:
        return state.booking_action or "new_booking"

    def _route_availability(self, state: GraphState) -> str:
        return "slots_found" if len(state.available_slots) > 0 else "no_slots"

    # ========================================================================
    # Helper: get user message from state
    # ========================================================================

    def _get_last_user_message(self, state: GraphState) -> str:
        for msg in reversed(state.messages):
            if isinstance(msg, dict) and msg.get("role") == "user":
                return msg.get("content", "")
            if hasattr(msg, "content") and hasattr(msg, "type") and msg.type == "human":
                return msg.content
        return ""

    def _build_conversation_history(self, state: GraphState) -> str:
        lines = []
        for msg in state.context.messages[-6:]:
            lines.append(f"{msg.role}: {msg.content}")
        return "\n".join(lines)

    def _extract_customer_details(self, state: GraphState) -> tuple[str | None, str | None]:
        """Extract customer name and email from conversation messages."""
        customer_email: str | None = None
        customer_name: str | None = None
        email_pattern = r"[\w.+-]+@[\w-]+\.[\w.]+"
        name_pattern = r"(?:my name is|i am|this is)\s+([A-Za-z][A-Za-z' -]{1,80})"

        for msg in state.context.messages:
            text = msg.content.strip()
            if not customer_email:
                email_match = re.search(email_pattern, text, flags=re.IGNORECASE)
                if email_match:
                    customer_email = email_match.group(0)
            if not customer_name:
                name_match = re.search(name_pattern, text, flags=re.IGNORECASE)
                if name_match:
                    customer_name = name_match.group(1).strip().title()

        return customer_name, customer_email

    def _has_booking_confirmation(self, user_message: str) -> bool:
        """Check if user confirmed they want to proceed with booking."""
        text = user_message.lower()
        explicit_confirm = ("confirm" in text) or ("yes" in text) or ("go ahead" in text)
        intent_confirm = ("book" in text) or ("schedule" in text) or ("appointment" in text)
        return explicit_confirm or intent_confirm

    # ========================================================================
    # Core Nodes
    # ========================================================================

    async def _intent_classification(self, state: GraphState) -> dict[str, Any]:
        """Classify user intent using LLM structured output."""
        llm = self._get_llm()
        user_msg = self._get_last_user_message(state)
        history = self._build_conversation_history(state)

        messages = [
            SystemMessage(content=INTENT_CLASSIFICATION_PROMPT),
            HumanMessage(content=f"Conversation history:\n{history}\n\nUser message: {user_msg}"),
        ]

        try:
            response = await llm.ainvoke(messages)
            content = response.content.strip()
            # Strip markdown fences if present
            if content.startswith("```"):
                content = content.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

            result = json.loads(content)
            intent = result.get("intent", "unclear")
            confidence = result.get("confidence", 0.5)

            valid_intents = {
                "informational", "comparison", "buying_intent",
                "booking_intent", "escalation_request", "unclear",
            }
            if intent not in valid_intents:
                intent = "informational"

            if confidence < settings.sentiment_threshold:
                intent = "unclear"

            logger.info("Intent classified: %s (confidence: %.2f)", intent, confidence)

            state.context.last_intent = intent
            state.context.intent_history.append(intent)

            return {"intent": intent}

        except (json.JSONDecodeError, Exception) as e:
            logger.warning("Intent classification failed, defaulting to informational: %s", e)
            return {"intent": "informational"}

    async def _knowledge_retrieval(self, state: GraphState) -> dict[str, Any]:
        """Execute RAG query against tenant documents."""
        if not self._db:
            return {"retrieved_chunks": [], "error": "No database session"}

        user_msg = self._get_last_user_message(state)
        tenant_id = state.context.tenant_id

        try:
            input_data = RetrieveProductDataInput(query=user_msg, top_k=5)
            result = await retrieve_product_data(self._db, tenant_id, input_data)

            chunks = [
                {
                    "content": c.content,
                    "document_id": c.document_id,
                    "chunk_type": c.chunk_type,
                    "similarity_score": c.similarity_score,
                }
                for c in result.chunks
            ]
            logger.info("Retrieved %d chunks for query", len(chunks))
            return {"retrieved_chunks": chunks}

        except NoDocumentsIndexedError:
            logger.info("No documents indexed for tenant %s", tenant_id)
            return {"retrieved_chunks": []}
        except Exception as e:
            logger.error("RAG retrieval failed: %s", e)
            return {"retrieved_chunks": [], "error": str(e)}

    async def _response_generation(self, state: GraphState) -> dict[str, Any]:
        """Generate final response using LLM + retrieved context."""
        booking_error_msg = None
        booking_result = None
        for chunk in state.retrieved_chunks:
            chunk_type = chunk.get("chunk_type")
            if chunk_type == "booking_error":
                try:
                    payload = json.loads(chunk.get("content", "{}"))
                    booking_error_msg = payload.get("message")
                except (json.JSONDecodeError, TypeError):
                    booking_error_msg = chunk.get("content")
            if chunk_type == "booking_result":
                try:
                    booking_result = json.loads(chunk.get("content", "{}"))
                except (json.JSONDecodeError, TypeError):
                    booking_result = None

        if booking_error_msg:
            return {"messages": [{"role": "assistant", "content": booking_error_msg}]}

        if booking_result:
            start_raw = booking_result.get("start_time")
            meet_link = booking_result.get("meet_link", "")
            calendar_link = booking_result.get("calendar_link", "")
            user_timezone = state.context.customer_timezone or "UTC"
            try:
                start_utc = datetime.fromisoformat(start_raw)
                if start_utc.tzinfo is None:
                    start_utc = start_utc.replace(tzinfo=ZoneInfo("UTC"))
                user_tz = ZoneInfo(user_timezone)
                start_local = start_utc.astimezone(user_tz)
                date_text = start_local.strftime("%A, %B %d, %Y")
                time_text = f"{start_local.strftime('%I:%M %p')} {user_timezone} ({start_utc.strftime('%I:%M %p')} UTC)"
            except Exception:
                date_text = "Scheduled date"
                time_text = "Scheduled time"

            msg = (
                "Your appointment has been booked!\n\n"
                f"**Date:** {date_text}\n"
                f"**Time:** {time_text}\n"
            )
            if meet_link:
                msg += f"**Google Meet:** {meet_link}\n"
            if calendar_link:
                msg += f"**Calendar Event:** {calendar_link}\n"
            msg += "\nYou'll receive a calendar invitation shortly."
            return {"messages": [{"role": "assistant", "content": msg}]}

        llm = self._get_llm()
        user_msg = self._get_last_user_message(state)

        persona_name = getattr(self._tenant_config, "persona_name", "Assistant")
        tone = getattr(self._tenant_config, "tone", "professional")
        custom_instructions = getattr(self._tenant_config, "custom_instructions", "")

        chunks_text = ""
        if state.retrieved_chunks:
            chunks_text = "\n\n".join(
                f"[{c.get('chunk_type', 'text')}] {c.get('content', '')}"
                for c in state.retrieved_chunks
            )
        else:
            chunks_text = "(No documents found. Answer based on general knowledge and indicate that no specific product documentation was found.)"

        system_prompt = RESPONSE_GENERATION_PROMPT.format(
            persona_name=persona_name,
            tone=tone,
            custom_instructions=f"\nAdditional instructions: {custom_instructions}" if custom_instructions else "",
            context=chunks_text,
        )

        history = self._build_conversation_history(state)

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Conversation:\n{history}\n\nUser: {user_msg}"),
        ]

        try:
            response = await llm.ainvoke(messages)
            return {"messages": [{"role": "assistant", "content": response.content}]}
        except Exception as e:
            logger.error("Response generation failed: %s", e)
            return {"messages": [{"role": "assistant", "content": "I'm sorry, I encountered an issue generating a response. Please try again."}]}

    async def _product_comparison(self, state: GraphState) -> dict[str, Any]:
        """Retrieve chunks and structure a product comparison."""
        if not self._db:
            return {"retrieved_chunks": []}

        user_msg = self._get_last_user_message(state)
        tenant_id = state.context.tenant_id

        try:
            input_data = RetrieveProductDataInput(query=user_msg, top_k=10)
            result = await retrieve_product_data(self._db, tenant_id, input_data)
            chunks = [
                {"content": c.content, "document_id": c.document_id,
                 "chunk_type": c.chunk_type, "similarity_score": c.similarity_score}
                for c in result.chunks
            ]
            return {"retrieved_chunks": chunks}
        except NoDocumentsIndexedError:
            return {"retrieved_chunks": []}
        except Exception as e:
            logger.error("Comparison retrieval failed: %s", e)
            return {"retrieved_chunks": []}

    async def _recommendation_engine(self, state: GraphState) -> dict[str, Any]:
        """Retrieve relevant products and prepare for recommendation."""
        if not self._db:
            return {"retrieved_chunks": []}

        user_msg = self._get_last_user_message(state)
        tenant_id = state.context.tenant_id

        try:
            input_data = RetrieveProductDataInput(query=user_msg, top_k=10)
            result = await retrieve_product_data(self._db, tenant_id, input_data)
            chunks = [
                {"content": c.content, "document_id": c.document_id,
                 "chunk_type": c.chunk_type, "similarity_score": c.similarity_score}
                for c in result.chunks
            ]
            return {"retrieved_chunks": chunks}
        except NoDocumentsIndexedError:
            return {"retrieved_chunks": []}
        except Exception as e:
            logger.error("Recommendation retrieval failed: %s", e)
            return {"retrieved_chunks": []}

    async def _clarification(self, state: GraphState) -> dict[str, Any]:
        """Ask the user to clarify their request."""
        llm = self._get_llm()
        user_msg = self._get_last_user_message(state)

        messages = [
            SystemMessage(content=CLARIFICATION_PROMPT),
            HumanMessage(content=f"User said: {user_msg}"),
        ]

        try:
            response = await llm.ainvoke(messages)
            return {"messages": [{"role": "assistant", "content": response.content}]}
        except Exception as e:
            logger.error("Clarification failed: %s", e)
            return {"messages": [{"role": "assistant", "content": "Could you please clarify what you're looking for? I want to make sure I help you correctly."}]}

    async def _human_escalation(self, state: GraphState) -> dict[str, Any]:
        """Flag conversation for human review."""
        state.context.is_escalated = True
        state.context.escalation_reason = "customer_request"
        logger.info("Conversation %s escalated", state.context.conversation_id)
        return {
            "messages": [{"role": "assistant", "content": "I've flagged this conversation for our team. A human representative will review it shortly. In the meantime, I'll do my best to help with any product questions."}],
        }

    async def _escalated_mode(self, state: GraphState) -> dict[str, Any]:
        """Continue in escalated mode — still answer knowledge questions."""
        return {}

    # ========================================================================
    # Booking Nodes
    # ========================================================================

    async def _check_calendar_connected(self) -> bool:
        """Check if Google Calendar is available (per-tenant OAuth or service account)."""
        if not self._db or not self._tenant_config:
            return False

        if settings.google_service_account_path:
            from pathlib import Path
            sa_path = Path(settings.google_service_account_path)
            if not sa_path.is_absolute():
                sa_path = Path.cwd() / sa_path
            if sa_path.exists():
                return True

        from ..models.database import Integration
        from sqlalchemy import select
        result = await self._db.execute(
            select(Integration).where(
                Integration.tenant_id == self._tenant_config.tenant_id,
                Integration.provider == "google_calendar",
            )
        )
        return result.scalar_one_or_none() is not None

    async def _booking_router(self, state: GraphState) -> dict[str, Any]:
        """Classify booking action: new, reschedule, or cancel."""
        if not await self._check_calendar_connected():
            return {
                "messages": [{"role": "assistant", "content": "I'd love to help you with booking, but appointment scheduling hasn't been set up for this account yet. Please contact the business directly."}],
                "booking_action": "not_configured",
            }

        user_msg = self._get_last_user_message(state)
        llm = self._get_llm()

        try:
            response = await llm.ainvoke([
                SystemMessage(content=BOOKING_ROUTER_PROMPT),
                HumanMessage(content=user_msg),
            ])
            parsed = json.loads(response.content.strip().strip("```json").strip("```"))
            action = parsed.get("action", "new_booking")
            if action not in ("new_booking", "reschedule", "cancel"):
                action = "new_booking"
            return {"booking_action": action}
        except Exception as e:
            logger.warning("Booking router LLM failed, defaulting to new_booking: %s", e)
            return {"booking_action": "new_booking"}

    async def _booking_extract_datetime(self, state: GraphState) -> dict[str, Any]:
        """Extract preferred date/time from user message using LLM."""
        user_msg = self._get_last_user_message(state)
        llm = self._get_llm()
        today = date.today().isoformat()

        try:
            response = await llm.ainvoke([
                SystemMessage(content=BOOKING_EXTRACT_PROMPT.format(
                    today=today, user_message=user_msg
                )),
                HumanMessage(content=user_msg),
            ])
            parsed = json.loads(response.content.strip().strip("```json").strip("```"))

            preferred_date_str = parsed.get("preferred_date")
            if preferred_date_str:
                preferred_date = date.fromisoformat(preferred_date_str)
            else:
                preferred_date = date.today() + timedelta(days=1)

            state.context.preferred_date = preferred_date
            return {"context": state.context}
        except Exception as e:
            logger.warning("Date extraction failed, using tomorrow: %s", e)
            state.context.preferred_date = date.today() + timedelta(days=1)
            return {"context": state.context}

    async def _booking_check_availability(self, state: GraphState) -> dict[str, Any]:
        """Check actual Google Calendar availability."""
        from ..services.calendar_service import check_availability

        target_date = state.context.preferred_date or (date.today() + timedelta(days=1))
        timezone = state.context.customer_timezone or "UTC"

        try:
            input_data = CheckAvailabilityInput(
                date=target_date,
                duration_minutes=settings.slot_duration_minutes,
                timezone=timezone,
            )
            result = await check_availability(
                self._db, state.context.tenant_id, input_data
            )
            slots = [
                {"start": s.start.isoformat(), "end": s.end.isoformat()}
                for s in result.available_slots
            ]
            return {"available_slots": slots}
        except CalendarNotConnectedError:
            return {
                "available_slots": [],
                "messages": [{"role": "assistant", "content": "Calendar is not connected. Please ask the business to set up their calendar integration."}],
            }
        except Exception as e:
            logger.error("Availability check failed: %s", e)
            return {
                "available_slots": [],
                "error": str(e),
            }

    async def _booking_offer_slots(self, state: GraphState) -> dict[str, Any]:
        """Present available slots to the user."""
        slots = state.available_slots
        if not slots:
            return {"messages": [{"role": "assistant", "content": "No available time slots were found."}]}

        slot_lines = []
        user_tz_name = state.context.customer_timezone or "UTC"
        try:
            user_tz = ZoneInfo(user_tz_name)
        except Exception:
            user_tz_name = "UTC"
            user_tz = ZoneInfo("UTC")

        for i, slot in enumerate(slots[:8], 1):
            start = slot.get("start", "")
            try:
                dt = datetime.fromisoformat(start)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=ZoneInfo("UTC"))
                local_dt = dt.astimezone(user_tz)
                slot_lines.append(f"{i}. {local_dt.strftime('%I:%M %p')} ({user_tz_name})")
            except (ValueError, TypeError):
                slot_lines.append(f"{i}. {start}")

        target_date = state.context.preferred_date or date.today()
        msg = (
            f"Here are the available time slots for {target_date.strftime('%A, %B %d')}:\n\n"
            + "\n".join(slot_lines)
            + f"\n\n(All times shown in your timezone: {user_tz_name})\n\n"
            + "\n\nPlease reply with:\n"
            + "1) selected slot number,\n"
            + "2) your full name,\n"
            + "3) your email,\n"
            + "4) confirmation (e.g. 'Confirm booking')."
        )

        state.context.booking_flow_active = True
        return {
            "messages": [{"role": "assistant", "content": msg}],
            "context": state.context,
        }

    async def _booking_confirm_slot(self, state: GraphState) -> dict[str, Any]:
        """Auto-confirm the first available slot for now.

        In a multi-turn flow the user would pick a slot. For the initial
        implementation we select the first slot and proceed.
        """
        slots = state.available_slots
        if slots:
            first = slots[0]
            from .context import TimeSlot as CtxTimeSlot
            state.context.selected_slot = CtxTimeSlot(
                start=datetime.fromisoformat(first["start"]),
                end=datetime.fromisoformat(first["end"]),
            )
        return {"context": state.context}

    async def _booking_create_event(self, state: GraphState) -> dict[str, Any]:
        """Create the Google Calendar event."""
        from ..services.calendar_service import create_event

        slot = state.context.selected_slot
        if not slot:
            return {"messages": [{"role": "assistant", "content": "No slot was selected. Please try again."}]}

        user_msg = self._get_last_user_message(state)
        customer_name, customer_email = self._extract_customer_details(state)
        missing_fields: list[str] = []
        if not customer_name:
            missing_fields.append("full name")
        if not customer_email:
            missing_fields.append("email")
        if not state.context.customer_timezone:
            missing_fields.append("timezone")
        if not self._has_booking_confirmation(user_msg):
            missing_fields.append("booking confirmation")

        if missing_fields:
            missing = ", ".join(missing_fields)
            msg = (
                "I can book this appointment, but I still need: "
                f"{missing}. Please provide them in one message."
            )
            return {
                "retrieved_chunks": [
                    {
                        "content": json.dumps(
                            {"message": msg, "missing_fields": missing_fields}
                        ),
                        "chunk_type": "booking_error",
                    }
                ]
            }

        try:
            input_data = CreateEventInput(
                start_time=slot.start,
                end_time=slot.end,
                customer_email=customer_email,
                customer_name=customer_name,
                summary="Appointment Booking",
                description=f"conv:{state.context.conversation_id}",
            )
            result = await create_event(
                self._db, state.context.tenant_id, input_data
            )
            state.context.pending_event_id = result.event_id
            return {
                "context": state.context,
                "retrieved_chunks": [
                    {
                        "content": json.dumps({
                            "event_id": result.event_id,
                            "meet_link": result.meet_link,
                            "calendar_link": result.calendar_link,
                            "start_time": result.start_time.isoformat(),
                            "end_time": result.end_time.isoformat(),
                        }),
                        "chunk_type": "booking_result",
                    }
                ],
            }
        except Exception as e:
            logger.error("Failed to create calendar event: %s", e)
            return {
                "messages": [{"role": "assistant", "content": f"I couldn't create the appointment: {e}. Please try again or contact the business directly."}],
            }

    async def _booking_success(self, state: GraphState) -> dict[str, Any]:
        """Generate a confirmation message for the booking."""
        booking_info = None
        for chunk in state.retrieved_chunks:
            if chunk.get("chunk_type") == "booking_result":
                try:
                    booking_info = json.loads(chunk["content"])
                except (json.JSONDecodeError, KeyError):
                    pass

        if booking_info:
            start = datetime.fromisoformat(booking_info["start_time"])
            meet_link = booking_info.get("meet_link", "")
            msg = (
                f"Your appointment has been booked!\n\n"
                f"**Date:** {start.strftime('%A, %B %d, %Y')}\n"
                f"**Time:** {start.strftime('%I:%M %p')} UTC\n"
            )
            if meet_link:
                msg += f"**Google Meet:** {meet_link}\n"
            msg += "\nYou'll receive a calendar invitation shortly. Is there anything else I can help with?"
        else:
            msg = "Your appointment has been booked! You'll receive a calendar invitation shortly."

        state.context.booking_flow_active = False
        return {
            "messages": [{"role": "assistant", "content": msg}],
            "context": state.context,
        }

    async def _booking_no_slots(self, state: GraphState) -> dict[str, Any]:
        """Handle case when no slots are available."""
        target_date = state.context.preferred_date or date.today()
        return {
            "messages": [{"role": "assistant", "content": (
                f"Unfortunately, there are no available time slots on {target_date.strftime('%A, %B %d')}. "
                "Would you like to try a different date?"
            )}],
        }

    async def _reschedule_flow(self, state: GraphState) -> dict[str, Any]:
        """Handle rescheduling — extract new date and re-check availability."""
        user_msg = self._get_last_user_message(state)
        llm = self._get_llm()
        today = date.today().isoformat()

        try:
            response = await llm.ainvoke([
                SystemMessage(content=BOOKING_EXTRACT_PROMPT.format(
                    today=today, user_message=user_msg
                )),
                HumanMessage(content=user_msg),
            ])
            parsed = json.loads(response.content.strip().strip("```json").strip("```"))
            preferred_date_str = parsed.get("preferred_date")
            if preferred_date_str:
                state.context.preferred_date = date.fromisoformat(preferred_date_str)
            else:
                state.context.preferred_date = date.today() + timedelta(days=1)
        except Exception:
            state.context.preferred_date = date.today() + timedelta(days=1)

        return {"context": state.context}

    async def _cancel_flow(self, state: GraphState) -> dict[str, Any]:
        """Handle appointment cancellation."""
        event_id = state.context.pending_event_id
        if not event_id:
            return {
                "messages": [{"role": "assistant", "content": "I don't have a record of a pending appointment to cancel. Could you provide more details?"}],
            }
        return {}

    async def _booking_cancel_event(self, state: GraphState) -> dict[str, Any]:
        """Execute the cancellation via Google Calendar API."""
        from ..services.calendar_service import cancel_event

        event_id = state.context.pending_event_id
        if not event_id:
            return {
                "messages": [{"role": "assistant", "content": "No appointment found to cancel."}],
            }

        try:
            input_data = CancelEventInput(
                event_id=event_id,
                cancellation_reason="Cancelled by customer via chat",
            )
            await cancel_event(self._db, state.context.tenant_id, input_data)
            state.context.pending_event_id = None
            state.context.booking_flow_active = False
            return {
                "messages": [{"role": "assistant", "content": "Your appointment has been cancelled. Is there anything else I can help with?"}],
                "context": state.context,
            }
        except Exception as e:
            logger.error("Cancel event failed: %s", e)
            return {
                "messages": [{"role": "assistant", "content": f"I couldn't cancel the appointment: {e}. Please contact the business directly."}],
            }

    # ========================================================================
    # Invoke
    # ========================================================================

    async def invoke(self, initial_state: GraphState) -> GraphState:
        """Execute the agent workflow."""
        result = await self.compiled_graph.ainvoke(initial_state)
        return result

    def build_response_messages(
        self, state: GraphState
    ) -> list[SystemMessage | HumanMessage]:
        """Build the LLM message list for response generation from current state.

        Used by the streaming endpoint to call llm.astream() directly.
        """
        user_msg = self._get_last_user_message(state)
        persona_name = getattr(self._tenant_config, "persona_name", "Assistant")
        tone = getattr(self._tenant_config, "tone", "professional")
        custom_instructions = getattr(self._tenant_config, "custom_instructions", "")

        chunks_text = ""
        if state.retrieved_chunks:
            chunks_text = "\n\n".join(
                f"[{c.get('chunk_type', 'text')}] {c.get('content', '')}"
                for c in state.retrieved_chunks
            )
        else:
            chunks_text = "(No documents found. Answer based on general knowledge and indicate that no specific product documentation was found.)"

        system_prompt = RESPONSE_GENERATION_PROMPT.format(
            persona_name=persona_name,
            tone=tone,
            custom_instructions=f"\nAdditional instructions: {custom_instructions}" if custom_instructions else "",
            context=chunks_text,
        )

        history = self._build_conversation_history(state)

        return [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Conversation:\n{history}\n\nUser: {user_msg}"),
        ]

    async def run_pre_generation(self, initial_state: GraphState) -> GraphState:
        """Run the agent up to ResponseGeneration, then stop.

        Returns the state with retrieved_chunks populated, ready for streaming.
        The non-streaming graph runs ResponseGeneration internally, but for
        streaming we skip it and call llm.astream() externally.
        """
        pre_graph = StateGraph(GraphState)

        pre_graph.add_node("IntentClassification", self._intent_classification)
        pre_graph.add_node("KnowledgeRetrieval", self._knowledge_retrieval)
        pre_graph.add_node("ProductComparison", self._product_comparison)
        pre_graph.add_node("RecommendationEngine", self._recommendation_engine)
        pre_graph.add_node("HumanEscalation", self._human_escalation)
        pre_graph.add_node("Clarification", self._clarification)

        pre_graph.set_entry_point("IntentClassification")

        pre_graph.add_conditional_edges(
            "IntentClassification",
            self._route_intent,
            {
                "informational": "KnowledgeRetrieval",
                "comparison": "ProductComparison",
                "buying_intent": "RecommendationEngine",
                "booking_intent": "KnowledgeRetrieval",
                "escalation_request": "HumanEscalation",
                "unclear": "Clarification",
            },
        )

        pre_graph.add_edge("KnowledgeRetrieval", END)
        pre_graph.add_edge("ProductComparison", END)
        pre_graph.add_edge("RecommendationEngine", END)
        pre_graph.add_edge("HumanEscalation", END)
        pre_graph.add_edge("Clarification", END)

        compiled = pre_graph.compile()
        result = await compiled.ainvoke(initial_state)
        return result
