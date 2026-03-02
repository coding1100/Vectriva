"""Pydantic schemas for API requests/responses."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field, HttpUrl


# ============================================================================
# Auth Schemas
# ============================================================================


class RegisterRequest(BaseModel):
    """User registration request."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=100)


class LoginRequest(BaseModel):
    """User login request."""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """JWT token response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: str


class RefreshTokenRequest(BaseModel):
    """Refresh token request."""

    refresh_token: str


# ============================================================================
# Tenant Schemas
# ============================================================================


class CreateTenantRequest(BaseModel):
    """Create tenant request."""

    name: str = Field(min_length=1, max_length=100)
    timezone: str = "UTC"


class TenantResponse(BaseModel):
    """Tenant response."""

    id: str
    name: str
    timezone: str
    is_active: bool
    created_at: datetime


class BusinessHourBlock(BaseModel):
    """Business hours for a day of week."""

    day_of_week: int = Field(ge=0, le=6)  # 0=Monday, 6=Sunday
    start_hour: int = Field(ge=0, le=23)
    start_minute: int = Field(ge=0, le=59)
    end_hour: int = Field(ge=0, le=23)
    end_minute: int = Field(ge=0, le=59)


class TenantConfigResponse(BaseModel):
    """Tenant configuration response."""

    persona_name: str
    tone: Literal["professional", "friendly", "casual"]
    custom_instructions: str
    timezone: str
    business_hours: list[BusinessHourBlock]
    auto_escalate_on_failure_count: int
    auto_escalate_on_negative_sentiment: bool
    escalation_email: EmailStr | None
    primary_color: str
    widget_position: Literal["bottom-right", "bottom-left"]
    welcome_message: str


class UpdateTenantConfigRequest(BaseModel):
    """Update tenant configuration."""

    persona_name: str | None = None
    tone: Literal["professional", "friendly", "casual"] | None = None
    custom_instructions: str | None = None
    business_hours: list[BusinessHourBlock] | None = None
    auto_escalate_on_failure_count: int | None = None
    auto_escalate_on_negative_sentiment: bool | None = None
    escalation_email: EmailStr | None = None
    primary_color: str | None = None
    widget_position: Literal["bottom-right", "bottom-left"] | None = None
    welcome_message: str | None = None


# ============================================================================
# Document Schemas
# ============================================================================


class DocumentUploadResponse(BaseModel):
    """Document upload response."""

    document_id: str
    status: Literal["queued", "processing", "indexed", "failed"]
    name: str


class DocumentResponse(BaseModel):
    """Document details response."""

    id: str
    name: str
    file_type: str
    status: Literal["queued", "processing", "indexed", "failed"]
    chunk_count: int
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class DocumentChunkResponse(BaseModel):
    """Document chunk response."""

    id: str
    content: str
    chunk_type: Literal["text", "table", "image_caption"]
    metadata: dict[str, Any]


# ============================================================================
# Integration Schemas
# ============================================================================


class GoogleAuthURLResponse(BaseModel):
    """Google OAuth URL response."""

    auth_url: HttpUrl
    state_token: str


class GoogleCallbackRequest(BaseModel):
    """Google OAuth callback request."""

    code: str
    state: str


class GoogleCalendarInfo(BaseModel):
    """Google Calendar info."""

    id: str
    summary: str
    primary: bool


class GoogleCalendarsResponse(BaseModel):
    """List of available calendars."""

    calendars: list[GoogleCalendarInfo]


class SetCalendarRequest(BaseModel):
    """Set booking calendar request."""

    calendar_id: str


class IntegrationStatusResponse(BaseModel):
    """Integration status."""

    connected: bool
    calendar_id: str | None
    calendar_name: str | None


# ============================================================================
# API Key Schemas
# ============================================================================


class CreateAPIKeyRequest(BaseModel):
    """Create API key request."""

    name: str | None = None


class APIKeyResponse(BaseModel):
    """API key response."""

    id: str
    name: str | None
    key: str | None = None  # Only returned on creation
    key_preview: str  # Last 4 chars
    is_active: bool
    created_at: datetime
    last_used_at: datetime | None


class APIKeyUsageResponse(BaseModel):
    """API key usage stats."""

    key_id: str
    total_requests: int
    requests_last_24h: int
    last_used_at: datetime | None


# ============================================================================
# Conversation Schemas
# ============================================================================


class ConversationListResponse(BaseModel):
    """List of conversations."""

    conversations: list["ConversationSummary"]
    total: int
    page: int
    page_size: int


class ConversationSummary(BaseModel):
    """Conversation summary."""

    id: str
    customer_email: str | None
    message_count: int
    is_escalated: bool
    started_at: datetime
    ended_at: datetime | None


class ConversationDetailResponse(BaseModel):
    """Full conversation details."""

    id: str
    tenant_id: str
    customer_id: str | None
    customer_email: str | None
    is_escalated: bool
    escalation_reason: str | None
    messages: list["MessageResponse"]
    started_at: datetime
    ended_at: datetime | None


class MessageResponse(BaseModel):
    """Message in conversation."""

    id: str
    role: str
    content: str
    created_at: datetime
    metadata: dict[str, Any]


class ToolCallLogResponse(BaseModel):
    """Tool call log."""

    id: str
    tool_name: str
    inputs: dict[str, Any]
    outputs: dict[str, Any] | None
    error: str | None
    latency_ms: int | None
    created_at: datetime


class RetrievalLogResponse(BaseModel):
    """RAG retrieval log."""

    id: str
    query: str
    chunk_ids: list[str]
    similarity_scores: list[float]
    created_at: datetime


# ============================================================================
# Chat Schemas
# ============================================================================


class ChatRequest(BaseModel):
    """Chat message request."""

    message: str
    conversation_id: str | None = None
    customer_email: EmailStr | None = None
    customer_timezone: str = "UTC"


class ChatResponse(BaseModel):
    """Chat message response."""

    conversation_id: str
    message: str
    is_escalated: bool
    metadata: dict[str, Any] = {}


# ============================================================================
# Analytics Schemas
# ============================================================================


class AnalyticsSummaryResponse(BaseModel):
    """Analytics summary."""

    total_conversations: int
    conversations_last_24h: int
    total_bookings: int
    bookings_last_24h: int
    average_messages_per_conversation: float
    escalation_rate: float
    top_intents: dict[str, int]
