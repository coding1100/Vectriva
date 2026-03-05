"""Chat API endpoint."""

import logging
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends
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
