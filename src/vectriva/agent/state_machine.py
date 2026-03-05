"""LangGraph state machine implementation."""

import json
import logging
from typing import Annotated, Any

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from .context import AgentContext
from ..agent.tools import RetrieveProductDataInput
from ..core.config import settings
from ..core.errors import NoDocumentsIndexedError
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
    # Booking Nodes (Stubs — require Google Calendar integration)
    # ========================================================================

    async def _booking_router(self, state: GraphState) -> dict[str, Any]:
        """Route to appropriate booking sub-flow."""
        return {
            "messages": [{"role": "assistant", "content": "I'd love to help you with booking! However, the appointment scheduling feature is not yet configured for this account. Please contact the business directly to schedule an appointment."}],
            "booking_action": "new_booking",
        }

    async def _booking_extract_datetime(self, state: GraphState) -> dict[str, Any]:
        return {"messages": [{"role": "assistant", "content": "Booking is not yet available."}]}

    async def _booking_check_availability(self, state: GraphState) -> dict[str, Any]:
        return {"available_slots": []}

    async def _booking_offer_slots(self, state: GraphState) -> dict[str, Any]:
        return {}

    async def _booking_confirm_slot(self, state: GraphState) -> dict[str, Any]:
        return {}

    async def _booking_create_event(self, state: GraphState) -> dict[str, Any]:
        return {}

    async def _booking_success(self, state: GraphState) -> dict[str, Any]:
        return {}

    async def _booking_no_slots(self, state: GraphState) -> dict[str, Any]:
        return {
            "messages": [{"role": "assistant", "content": "I wasn't able to find any available slots. Please try a different date or contact the business directly."}],
        }

    async def _reschedule_flow(self, state: GraphState) -> dict[str, Any]:
        return {"messages": [{"role": "assistant", "content": "Rescheduling is not yet available. Please contact the business directly."}]}

    async def _cancel_flow(self, state: GraphState) -> dict[str, Any]:
        return {"messages": [{"role": "assistant", "content": "Cancellation is not yet available. Please contact the business directly."}]}

    async def _booking_cancel_event(self, state: GraphState) -> dict[str, Any]:
        return {}

    # ========================================================================
    # Invoke
    # ========================================================================

    async def invoke(self, initial_state: GraphState) -> GraphState:
        """Execute the agent workflow."""
        result = await self.compiled_graph.ainvoke(initial_state)
        return result
