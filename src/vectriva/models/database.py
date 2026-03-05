"""SQLAlchemy database models."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import BYTEA
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for all database models."""

    pass


class User(Base):
    """User account."""

    __tablename__ = "users"

    id = Column(String, primary_key=True)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    tenant_users = relationship("TenantUser", back_populates="user")


class Tenant(Base):
    """Tenant organization."""

    __tablename__ = "tenants"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    timezone = Column(String, default="UTC", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    tenant_users = relationship("TenantUser", back_populates="tenant")
    documents = relationship("Document", back_populates="tenant")
    conversations = relationship("Conversation", back_populates="tenant")
    config = relationship("TenantConfig", back_populates="tenant", uselist=False)
    api_keys = relationship("APIKey", back_populates="tenant")
    integrations = relationship("Integration", back_populates="tenant")


class TenantUser(Base):
    """Many-to-many relationship between tenants and users."""

    __tablename__ = "tenant_users"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    role = Column(Enum("owner", "admin", "member", name="tenant_role"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    tenant = relationship("Tenant", back_populates="tenant_users")
    user = relationship("User", back_populates="tenant_users")

    __table_args__ = (UniqueConstraint("tenant_id", "user_id"),)


class TenantConfig(Base):
    """Tenant-specific configuration."""

    __tablename__ = "tenant_configs"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), unique=True, nullable=False)

    # Agent Persona
    persona_name = Column(String, default="Assistant", nullable=False)
    tone = Column(Enum("professional", "friendly", "casual", name="tone_type"), default="professional")
    custom_instructions = Column(Text, default="")

    # Model Configuration
    llm_provider = Column(Enum("openai", "gemini", name="llm_provider"), default="gemini")
    llm_model = Column(String, default="gemini-2.0-flash")
    embedding_provider = Column(Enum("openai", "gemini", name="embedding_provider"), default="gemini")
    embedding_model = Column(String, default="models/gemini-embedding-001")

    # Business Hours (stored as JSON)
    business_hours = Column(JSON, default=list)

    # Escalation Rules
    auto_escalate_on_failure_count = Column(Integer, default=3)
    auto_escalate_on_negative_sentiment = Column(Boolean, default=True)
    escalation_email = Column(String, nullable=True)

    # Widget Appearance
    primary_color = Column(String, default="#0066CC")
    widget_position = Column(Enum("bottom-right", "bottom-left", name="widget_position"), default="bottom-right")
    welcome_message = Column(String, default="Hi! How can I help you today?")

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    tenant = relationship("Tenant", back_populates="config")


class Document(Base):
    """Uploaded document."""

    __tablename__ = "documents"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_type = Column(String, nullable=False)
    status = Column(
        Enum("queued", "processing", "indexed", "failed", name="document_status"),
        default="queued",
        nullable=False,
    )
    chunk_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    tenant = relationship("Tenant", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document")


class DocumentChunk(Base):
    """Document chunk with embedding."""

    __tablename__ = "document_chunks"

    id = Column(String, primary_key=True)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False, index=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    chunk_type = Column(
        Enum("text", "table", "image_caption", name="chunk_type"), nullable=False
    )
    embedding = Column(BYTEA, nullable=False)
    embedding_dimension = Column(Integer, nullable=False)
    chunk_metadata = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    document = relationship("Document", back_populates="chunks")

    __table_args__ = (Index("idx_chunks_tenant_id", "tenant_id"),)


class Conversation(Base):
    """Customer conversation."""

    __tablename__ = "conversations"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    customer_id = Column(String, nullable=True)
    customer_email = Column(String, nullable=True)
    is_escalated = Column(Boolean, default=False)
    escalation_reason = Column(String, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at = Column(DateTime, nullable=True)

    tenant = relationship("Tenant", back_populates="conversations")
    messages = relationship("ConversationMessage", back_populates="conversation")
    tool_calls = relationship("ToolCallLog", back_populates="conversation")
    retrievals = relationship("RetrievalLog", back_populates="conversation")
    escalations = relationship("Escalation", back_populates="conversation")


class ConversationMessage(Base):
    """Individual message in conversation."""

    __tablename__ = "conversation_messages"

    id = Column(String, primary_key=True)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False, index=True)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    message_metadata = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    conversation = relationship("Conversation", back_populates="messages")


class ToolCallLog(Base):
    """Log of agent tool invocations."""

    __tablename__ = "tool_call_logs"

    id = Column(String, primary_key=True)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False, index=True)
    tool_name = Column(String, nullable=False)
    inputs = Column(JSON, nullable=False)
    outputs = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    conversation = relationship("Conversation", back_populates="tool_calls")


class RetrievalLog(Base):
    """Log of RAG retrievals."""

    __tablename__ = "retrieval_logs"

    id = Column(String, primary_key=True)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False, index=True)
    query = Column(Text, nullable=False)
    query_embedding_id = Column(String, nullable=False)
    chunk_ids = Column(JSON, nullable=False)
    similarity_scores = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    conversation = relationship("Conversation", back_populates="retrievals")


class Escalation(Base):
    """Human escalation record."""

    __tablename__ = "escalations"

    id = Column(String, primary_key=True)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False, index=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    reason = Column(String, nullable=False)
    context_summary = Column(Text, nullable=False)
    notification_sent = Column(Boolean, default=False)
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    conversation = relationship("Conversation", back_populates="escalations")


class APIKey(Base):
    """Tenant API key."""

    __tablename__ = "api_keys"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    key_hash = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_used_at = Column(DateTime, nullable=True)

    tenant = relationship("Tenant", back_populates="api_keys")


class Integration(Base):
    """External service integration (Google Calendar, etc.)."""

    __tablename__ = "integrations"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    provider = Column(String, nullable=False)
    encrypted_access_token = Column(Text, nullable=False)
    encrypted_refresh_token = Column(Text, nullable=True)
    calendar_id = Column(String, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    tenant = relationship("Tenant", back_populates="integrations")

    __table_args__ = (UniqueConstraint("tenant_id", "provider"),)


class CalendarEvent(Base):
    """Calendar event created by agent."""

    __tablename__ = "calendar_events"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False)
    google_event_id = Column(String, nullable=False)
    customer_email = Column(String, nullable=False)
    customer_name = Column(String, nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    meet_link = Column(String, nullable=True)
    status = Column(
        Enum("scheduled", "rescheduled", "cancelled", name="event_status"),
        default="scheduled",
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
