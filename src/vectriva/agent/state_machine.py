"""LangGraph state machine implementation."""

from typing import Annotated, Any, Literal

from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel

from .context import AgentContext


class GraphState(BaseModel):
    """The state that flows through the graph."""

    context: AgentContext
    messages: Annotated[list[dict[str, Any]], add_messages]
    next_action: str | None = None
    intent: str | None = None
    booking_action: str | None = None
    available_slots: list[dict[str, Any]] = []
    retrieved_chunks: list[dict[str, Any]] = []
    error: str | None = None


class VectrivaAgent:
    """The LangGraph-based agent orchestrator."""

    def __init__(self) -> None:
        """Initialize the agent with state graph."""
        self.graph = self._build_graph()
        self.compiled_graph = self.graph.compile()

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph state machine."""
        graph = StateGraph(GraphState)

        # Add all state nodes
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

        # Set entry point
        graph.set_entry_point("IntentClassification")

        # Add conditional edges from IntentClassification
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

        # Add edges for knowledge paths
        graph.add_edge("KnowledgeRetrieval", "ResponseGeneration")
        graph.add_edge("ProductComparison", "ResponseGeneration")
        graph.add_edge("RecommendationEngine", "ResponseGeneration")

        # Clarification loops back
        graph.add_edge("Clarification", "IntentClassification")

        # Booking Router conditional edges
        graph.add_conditional_edges(
            "BookingRouter",
            self._route_booking,
            {
                "new_booking": "BookingExtractDateTime",
                "reschedule": "RescheduleFlow",
                "cancel": "CancelFlow",
            },
        )

        # Booking flow edges
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

        # Reschedule/Cancel flows
        graph.add_edge("RescheduleFlow", "BookingCheckAvailability")
        graph.add_edge("CancelFlow", "BookingCancelEvent")
        graph.add_edge("BookingCancelEvent", "BookingSuccess")

        # Escalation flow
        graph.add_edge("HumanEscalation", "EscalatedMode")
        graph.add_edge("EscalatedMode", "KnowledgeRetrieval")

        # End point
        graph.add_edge("ResponseGeneration", END)

        return graph

    # ========================================================================
    # Routing Functions
    # ========================================================================

    def _route_intent(self, state: GraphState) -> str:
        """Route based on classified intent."""
        return state.intent or "unclear"

    def _route_booking(self, state: GraphState) -> str:
        """Route based on booking action."""
        return state.booking_action or "new_booking"

    def _route_availability(self, state: GraphState) -> str:
        """Route based on slot availability."""
        return "slots_found" if len(state.available_slots) > 0 else "no_slots"

    # ========================================================================
    # State Implementation Functions
    # ========================================================================

    async def _intent_classification(self, state: GraphState) -> GraphState:
        """Classify user intent."""
        raise NotImplementedError("LLM integration required")

    async def _knowledge_retrieval(self, state: GraphState) -> GraphState:
        """Execute RAG query."""
        raise NotImplementedError("RAG service integration required")

    async def _product_comparison(self, state: GraphState) -> GraphState:
        """Structure product comparison."""
        raise NotImplementedError("RAG + LLM integration required")

    async def _recommendation_engine(self, state: GraphState) -> GraphState:
        """Generate product recommendations."""
        raise NotImplementedError("RAG + LLM integration required")

    async def _booking_router(self, state: GraphState) -> GraphState:
        """Determine booking sub-intent."""
        raise NotImplementedError("LLM integration required")

    async def _booking_extract_datetime(self, state: GraphState) -> GraphState:
        """Extract date/time preferences."""
        raise NotImplementedError("LLM integration required")

    async def _booking_check_availability(self, state: GraphState) -> GraphState:
        """Check calendar availability."""
        raise NotImplementedError("Calendar service integration required")

    async def _booking_offer_slots(self, state: GraphState) -> GraphState:
        """Format and present slots."""
        raise NotImplementedError("Formatting logic required")

    async def _booking_confirm_slot(self, state: GraphState) -> GraphState:
        """Confirm slot selection."""
        raise NotImplementedError("LLM integration required")

    async def _booking_create_event(self, state: GraphState) -> GraphState:
        """Create calendar event."""
        raise NotImplementedError("Calendar service integration required")

    async def _booking_success(self, state: GraphState) -> GraphState:
        """Confirm booking success."""
        raise NotImplementedError("Formatting logic required")

    async def _booking_no_slots(self, state: GraphState) -> GraphState:
        """Handle no slots scenario."""
        raise NotImplementedError("Formatting logic required")

    async def _reschedule_flow(self, state: GraphState) -> GraphState:
        """Handle rescheduling."""
        raise NotImplementedError("Logic required")

    async def _cancel_flow(self, state: GraphState) -> GraphState:
        """Handle cancellation."""
        raise NotImplementedError("Logic required")

    async def _booking_cancel_event(self, state: GraphState) -> GraphState:
        """Cancel calendar event."""
        raise NotImplementedError("Calendar service integration required")

    async def _human_escalation(self, state: GraphState) -> GraphState:
        """Escalate to human."""
        raise NotImplementedError("Escalation service integration required")

    async def _escalated_mode(self, state: GraphState) -> GraphState:
        """Continue with restricted capabilities."""
        raise NotImplementedError("Logic required")

    async def _clarification(self, state: GraphState) -> GraphState:
        """Ask clarifying questions."""
        raise NotImplementedError("LLM integration required")

    async def _response_generation(self, state: GraphState) -> GraphState:
        """Generate final response."""
        raise NotImplementedError("LLM integration required")

    async def invoke(self, initial_state: GraphState) -> GraphState:
        """Execute the agent workflow."""
        return await self.compiled_graph.ainvoke(initial_state)
