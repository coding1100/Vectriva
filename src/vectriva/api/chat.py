"""Chat API endpoint."""

import json
import logging
import uuid
from datetime import datetime
from typing import Any, AsyncGenerator

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..agent.context import AgentContext, Message
from ..agent.state_machine import GraphState, VectrivaAgent
from ..agent.tools import RetrieveProductDataInput
from ..core.database import get_db
from ..core.errors import NoDocumentsIndexedError
from ..core.redis import get_context, store_context
from ..models.database import Conversation, ConversationMessage, Tenant, TenantConfig
from ..models.schemas import ChatRequest, ChatResponse
from ..api.middleware import verify_api_key
from ..services.llm_factory import get_tenant_llm
from ..services.rag_service import retrieve_product_data

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


async def _fallback_rag_response(
    db: AsyncSession, tenant_id: str, user_message: str, tenant_config: TenantConfig | None
) -> str:
    """Direct RAG + LLM fallback when the agent graph fails."""
    from langchain_core.messages import HumanMessage, SystemMessage

    try:
        input_data = RetrieveProductDataInput(query=user_message, top_k=5)
        rag_result = await retrieve_product_data(db, tenant_id, input_data)
        chunks_text = "\n\n".join(c.content for c in rag_result.chunks)
    except NoDocumentsIndexedError:
        chunks_text = "(No documents indexed yet.)"
    except Exception:
        chunks_text = "(Retrieval unavailable.)"

    llm = get_tenant_llm(tenant_config)
    persona = getattr(tenant_config, "persona_name", "Assistant")
    tone = getattr(tenant_config, "tone", "professional")

    messages = [
        SystemMessage(content=(
            f"You are {persona}, a {tone} product assistant. "
            f"Answer based on this context:\n\n{chunks_text}\n\n"
            "If you don't have enough information, say so honestly."
        )),
        HumanMessage(content=user_message),
    ]

    response = await llm.ainvoke(messages)
    return response.content


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    auth: tuple[Tenant, Any] = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    """Process chat message through agent."""
    tenant, api_key = auth

    # Load tenant config for LLM/persona settings
    config_result = await db.execute(
        select(TenantConfig).where(TenantConfig.tenant_id == tenant.id)
    )
    tenant_config = config_result.scalar_one_or_none()

    conversation_id = request.conversation_id
    if not conversation_id:
        conversation_id = str(uuid.uuid4())
        conversation = Conversation(
            id=conversation_id,
            tenant_id=tenant.id,
            customer_email=request.customer_email,
            started_at=datetime.utcnow(),
        )
        db.add(conversation)
        await db.flush()

    context_dict = await get_context(conversation_id)
    if context_dict:
        context = AgentContext.from_dict(context_dict)
    else:
        context = AgentContext(
            conversation_id=conversation_id,
            tenant_id=tenant.id,
            customer_timezone=request.customer_timezone,
        )

    user_message = Message(
        role="user", content=request.message, timestamp=datetime.utcnow()
    )
    context.messages.append(user_message)
    context.turn_count += 1

    user_msg_record = ConversationMessage(
        id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        role="user",
        content=request.message,
    )
    db.add(user_msg_record)

    # Create agent with DB session and tenant config
    agent = VectrivaAgent(db=db)
    agent.set_tenant_config(tenant_config)

    initial_state = GraphState(
        context=context,
        messages=[{"role": "user", "content": request.message}],
    )

    try:
        final_state = await agent.invoke(initial_state)

        response_text = None
        for msg in reversed(final_state["messages"]):
            if isinstance(msg, dict):
                if msg.get("role") in ("assistant", "ai"):
                    response_text = msg.get("content")
                    break
            elif hasattr(msg, "content") and hasattr(msg, "type"):
                if msg.type in ("ai", "assistant"):
                    response_text = msg.content
                    break

        if not response_text:
            response_text = "I processed your request but couldn't generate a response. Please try again."

    except Exception as e:
        logger.error("Agent invocation failed, using fallback: %s", e, exc_info=True)
        context.consecutive_errors += 1

        try:
            response_text = await _fallback_rag_response(
                db, tenant.id, request.message, tenant_config
            )
        except Exception as fallback_err:
            logger.error("Fallback also failed: %s", fallback_err)
            response_text = "I'm having trouble right now. Please try again shortly."

    agent_message = Message(
        role="agent", content=response_text, timestamp=datetime.utcnow()
    )
    context.messages.append(agent_message)
    context.updated_at = datetime.utcnow()

    agent_msg_record = ConversationMessage(
        id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        role="agent",
        content=response_text,
    )
    db.add(agent_msg_record)

    await store_context(conversation_id, context.to_dict())
    await db.commit()

    return ChatResponse(
        conversation_id=conversation_id,
        message=response_text,
        is_escalated=context.is_escalated,
    )


async def _prepare_streaming_context(
    request: ChatRequest,
    tenant: Tenant,
    db: AsyncSession,
) -> tuple[str, AgentContext, TenantConfig | None]:
    """Shared setup for both streaming and non-streaming: config, conversation, context."""
    config_result = await db.execute(
        select(TenantConfig).where(TenantConfig.tenant_id == tenant.id)
    )
    tenant_config = config_result.scalar_one_or_none()

    conversation_id = request.conversation_id
    if not conversation_id:
        conversation_id = str(uuid.uuid4())
        conversation = Conversation(
            id=conversation_id,
            tenant_id=tenant.id,
            customer_email=request.customer_email,
            started_at=datetime.utcnow(),
        )
        db.add(conversation)
        await db.flush()

    context_dict = await get_context(conversation_id)
    if context_dict:
        context = AgentContext.from_dict(context_dict)
    else:
        context = AgentContext(
            conversation_id=conversation_id,
            tenant_id=tenant.id,
            customer_timezone=request.customer_timezone,
        )

    user_message = Message(
        role="user", content=request.message, timestamp=datetime.utcnow()
    )
    context.messages.append(user_message)
    context.turn_count += 1

    user_msg_record = ConversationMessage(
        id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        role="user",
        content=request.message,
    )
    db.add(user_msg_record)

    return conversation_id, context, tenant_config


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    auth: tuple[Tenant, Any] = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Stream chat response via Server-Sent Events."""
    tenant, api_key = auth

    conversation_id, context, tenant_config = await _prepare_streaming_context(
        request, tenant, db
    )

    agent = VectrivaAgent(db=db)
    agent.set_tenant_config(tenant_config)

    initial_state = GraphState(
        context=context,
        messages=[{"role": "user", "content": request.message}],
    )

    async def event_stream() -> AsyncGenerator[str, None]:
        full_response = ""
        is_escalated = context.is_escalated

        try:
            yield _sse_event({"type": "start", "conversation_id": conversation_id})

            pre_state = await agent.run_pre_generation(initial_state)
            detected_intent = pre_state.get("intent", "")

            if detected_intent in ("booking_intent", "escalation_request"):
                final_state = await agent.invoke(initial_state)
                full_response = _extract_assistant_message(final_state) or ""
                if full_response:
                    yield _sse_event({"type": "token", "content": full_response})
            else:
                escalation_msgs = _get_escalation_or_clarification(pre_state)
                if escalation_msgs:
                    full_response = escalation_msgs
                    yield _sse_event({"type": "token", "content": full_response})
                else:
                    llm_messages = agent.build_response_messages(
                        GraphState(**pre_state)
                    )
                    llm = agent._get_llm()

                    async for chunk in llm.astream(llm_messages):
                        token = chunk.content if hasattr(chunk, "content") else str(chunk)
                        if token:
                            full_response += token
                            yield _sse_event({"type": "token", "content": token})

            if not full_response:
                full_response = "I couldn't generate a response. Please try again."
                yield _sse_event({"type": "token", "content": full_response})

        except Exception as e:
            logger.error("Streaming failed, using fallback: %s", e, exc_info=True)
            try:
                full_response = await _fallback_rag_response(
                    db, tenant.id, request.message, tenant_config
                )
                yield _sse_event({"type": "token", "content": full_response})
            except Exception:
                full_response = "I'm having trouble right now. Please try again shortly."
                yield _sse_event({"type": "token", "content": full_response})

        agent_message = Message(
            role="agent", content=full_response, timestamp=datetime.utcnow()
        )
        context.messages.append(agent_message)
        context.updated_at = datetime.utcnow()

        agent_msg_record = ConversationMessage(
            id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            role="agent",
            content=full_response,
        )
        db.add(agent_msg_record)

        await store_context(conversation_id, context.to_dict())
        await db.commit()

        yield _sse_event({
            "type": "done",
            "conversation_id": conversation_id,
            "is_escalated": is_escalated,
        })

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _sse_event(data: dict[str, Any]) -> str:
    """Format a dict as an SSE event line."""
    return f"data: {json.dumps(data)}\n\n"


def _extract_assistant_message(state: dict[str, Any]) -> str | None:
    """Extract the last assistant message from a completed graph state."""
    messages = state.get("messages", [])
    for msg in reversed(messages):
        if isinstance(msg, dict) and msg.get("role") in ("assistant", "ai"):
            return msg.get("content")
        if hasattr(msg, "content") and hasattr(msg, "type") and msg.type in ("ai", "assistant"):
            return msg.content
    return None


def _get_escalation_or_clarification(state: dict[str, Any]) -> str | None:
    """Check if the pre-generation graph produced a terminal response (escalation/clarification)."""
    messages = state.get("messages", [])
    for msg in reversed(messages):
        if isinstance(msg, dict) and msg.get("role") in ("assistant", "ai"):
            return msg.get("content")
        if hasattr(msg, "content") and hasattr(msg, "type") and msg.type in ("ai", "assistant"):
            return msg.content
    return None
