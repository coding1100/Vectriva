"""Conversation observability API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..models.database import (
    Conversation,
    ConversationMessage,
    RetrievalLog,
    Tenant,
    ToolCallLog,
)
from ..models.schemas import (
    AnalyticsSummaryResponse,
    ConversationDetailResponse,
    ConversationListResponse,
    ConversationSummary,
    MessageResponse,
    RetrievalLogResponse,
    ToolCallLogResponse,
)
from .middleware import get_current_tenant

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=ConversationListResponse)
async def list_conversations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> ConversationListResponse:
    """List conversations for tenant."""
    total_result = await db.execute(
        select(func.count()).select_from(Conversation).where(Conversation.tenant_id == tenant.id)
    )
    total = total_result.scalar()

    offset = (page - 1) * page_size
    result = await db.execute(
        select(Conversation)
        .where(Conversation.tenant_id == tenant.id)
        .order_by(Conversation.started_at.desc())
        .limit(page_size)
        .offset(offset)
    )
    conversations = result.scalars().all()

    summaries = []
    for conv in conversations:
        msg_count_result = await db.execute(
            select(func.count())
            .select_from(ConversationMessage)
            .where(ConversationMessage.conversation_id == conv.id)
        )
        msg_count = msg_count_result.scalar()

        summaries.append(
            ConversationSummary(
                id=conv.id,
                customer_email=conv.customer_email,
                message_count=msg_count,
                is_escalated=conv.is_escalated,
                started_at=conv.started_at,
                ended_at=conv.ended_at,
            )
        )

    return ConversationListResponse(
        conversations=summaries, total=total, page=page, page_size=page_size
    )


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: str,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> ConversationDetailResponse:
    """Get full conversation details."""
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id, Conversation.tenant_id == tenant.id
        )
    )
    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages_result = await db.execute(
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == conversation_id)
        .order_by(ConversationMessage.created_at)
    )
    messages = messages_result.scalars().all()

    return ConversationDetailResponse(
        id=conversation.id,
        tenant_id=conversation.tenant_id,
        customer_id=conversation.customer_id,
        customer_email=conversation.customer_email,
        is_escalated=conversation.is_escalated,
        escalation_reason=conversation.escalation_reason,
        messages=[
            MessageResponse(
                id=msg.id,
                role=msg.role,
                content=msg.content,
                created_at=msg.created_at,
                metadata=msg.message_metadata,
            )
            for msg in messages
        ],
        started_at=conversation.started_at,
        ended_at=conversation.ended_at,
    )


@router.get("/{conversation_id}/tool-calls", response_model=list[ToolCallLogResponse])
async def get_tool_calls(
    conversation_id: str,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> list[ToolCallLogResponse]:
    """Get tool execution logs for conversation."""
    result = await db.execute(
        select(ToolCallLog)
        .where(ToolCallLog.conversation_id == conversation_id)
        .order_by(ToolCallLog.created_at)
    )
    logs = result.scalars().all()

    return [
        ToolCallLogResponse(
            id=log.id,
            tool_name=log.tool_name,
            inputs=log.inputs,
            outputs=log.outputs,
            error=log.error,
            latency_ms=log.latency_ms,
            created_at=log.created_at,
        )
        for log in logs
    ]


@router.get("/{conversation_id}/retrievals", response_model=list[RetrievalLogResponse])
async def get_retrievals(
    conversation_id: str,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> list[RetrievalLogResponse]:
    """Get RAG retrieval logs for conversation."""
    result = await db.execute(
        select(RetrievalLog)
        .where(RetrievalLog.conversation_id == conversation_id)
        .order_by(RetrievalLog.created_at)
    )
    logs = result.scalars().all()

    return [
        RetrievalLogResponse(
            id=log.id,
            query=log.query,
            chunk_ids=log.chunk_ids,
            similarity_scores=log.similarity_scores,
            created_at=log.created_at,
        )
        for log in logs
    ]


@router.get("/analytics/summary", response_model=AnalyticsSummaryResponse)
async def get_analytics_summary(
    tenant: Tenant = Depends(get_current_tenant), db: AsyncSession = Depends(get_db)
) -> AnalyticsSummaryResponse:
    """Get analytics summary for tenant."""
    raise NotImplementedError("Analytics aggregation required")
