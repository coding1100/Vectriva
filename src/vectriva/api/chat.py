"""Chat API endpoint."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..agent.context import AgentContext, Message
from ..agent.state_machine import GraphState, VectrivaAgent
from ..core.database import get_db
from ..core.redis import get_context, store_context
from ..models.database import Conversation, ConversationMessage, Tenant
from ..models.schemas import ChatRequest, ChatResponse
from ..api.middleware import verify_api_key

router = APIRouter(prefix="/chat", tags=["chat"])

agent = VectrivaAgent()


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest, auth: tuple[Tenant, Any] = Depends(verify_api_key), db: AsyncSession = Depends(get_db)
) -> ChatResponse:
    """Process chat message through agent."""
    tenant, api_key = auth

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

    initial_state = GraphState(
        context=context,
        messages=[{"role": "user", "content": request.message}],
    )

    try:
        final_state = await agent.invoke(initial_state)
        response_text = final_state.messages[-1].get("content", "I encountered an error.")
    except Exception as e:
        response_text = "I'm having trouble right now. Please try again."
        context.consecutive_errors += 1

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
