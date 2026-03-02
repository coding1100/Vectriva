"""Escalation service for human handoff."""

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from ..agent.tools import EscalateToHumanInput, EscalateToHumanOutput
from ..core.errors import AlreadyEscalatedError
from ..models.database import Conversation, Escalation


async def escalate_conversation(
    db: AsyncSession, conversation_id: str, tenant_id: str, input_data: EscalateToHumanInput
) -> EscalateToHumanOutput:
    """Escalate conversation to human."""
    existing = await db.execute(
        Escalation.__table__.select().where(Escalation.conversation_id == conversation_id)
    )
    if existing.scalar_one_or_none():
        raise AlreadyEscalatedError("Conversation already escalated")

    escalation = Escalation(
        id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        tenant_id=tenant_id,
        reason=input_data.reason,
        context_summary=input_data.context_summary,
        notification_sent=False,
    )
    db.add(escalation)

    conv_result = await db.execute(
        Conversation.__table__.select().where(Conversation.id == conversation_id)
    )
    conversation = conv_result.scalar_one_or_none()
    if conversation:
        await db.execute(
            Conversation.__table__.update()
            .where(Conversation.id == conversation_id)
            .values(is_escalated=True, escalation_reason=input_data.reason)
        )

    await db.flush()

    return EscalateToHumanOutput(
        escalation_id=escalation.id,
        escalated_at=datetime.utcnow(),
        notification_sent=False,
    )
