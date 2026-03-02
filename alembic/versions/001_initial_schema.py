"""Initial schema

Revision ID: 001
Revises: 
Create Date: 2026-03-02

"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    
    op.create_table(
        'users',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )
    op.create_index('ix_users_email', 'users', ['email'])
    
    op.create_table(
        'tenants',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('timezone', sa.String(), nullable=False, server_default='UTC'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table(
        'tenant_users',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('role', sa.Enum('owner', 'admin', 'member', name='tenant_role'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'user_id')
    )
    
    op.create_table(
        'tenant_configs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('persona_name', sa.String(), nullable=False, server_default='Assistant'),
        sa.Column('tone', sa.Enum('professional', 'friendly', 'casual', name='tone_type'), server_default='professional'),
        sa.Column('custom_instructions', sa.Text(), server_default=''),
        sa.Column('business_hours', sa.JSON(), server_default='[]'),
        sa.Column('auto_escalate_on_failure_count', sa.Integer(), server_default='3'),
        sa.Column('auto_escalate_on_negative_sentiment', sa.Boolean(), server_default='true'),
        sa.Column('escalation_email', sa.String(), nullable=True),
        sa.Column('primary_color', sa.String(), server_default='#0066CC'),
        sa.Column('widget_position', sa.Enum('bottom-right', 'bottom-left', name='widget_position'), server_default='bottom-right'),
        sa.Column('welcome_message', sa.String(), server_default='Hi! How can I help you today?'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id')
    )
    
    op.create_table(
        'documents',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('file_path', sa.String(), nullable=False),
        sa.Column('file_type', sa.String(), nullable=False),
        sa.Column('status', sa.Enum('queued', 'processing', 'indexed', 'failed', name='document_status'), server_default='queued'),
        sa.Column('chunk_count', sa.Integer(), server_default='0'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_documents_tenant_id', 'documents', ['tenant_id'])
    
    op.create_table(
        'document_chunks',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('document_id', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('chunk_type', sa.Enum('text', 'table', 'image_caption', name='chunk_type'), nullable=False),
        sa.Column('embedding', Vector(1536), nullable=False),
        sa.Column('metadata', sa.JSON(), server_default='{}'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id']),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_document_chunks_document_id', 'document_chunks', ['document_id'])
    op.create_index('ix_document_chunks_tenant_id', 'document_chunks', ['tenant_id'])
    op.execute('CREATE INDEX idx_chunks_tenant_embedding ON document_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)')
    
    op.create_table(
        'conversations',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('customer_id', sa.String(), nullable=True),
        sa.Column('customer_email', sa.String(), nullable=True),
        sa.Column('is_escalated', sa.Boolean(), server_default='false'),
        sa.Column('escalation_reason', sa.String(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('ended_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_conversations_tenant_id', 'conversations', ['tenant_id'])
    
    op.create_table(
        'conversation_messages',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('conversation_id', sa.String(), nullable=False),
        sa.Column('role', sa.String(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('metadata', sa.JSON(), server_default='{}'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_conversation_messages_conversation_id', 'conversation_messages', ['conversation_id'])
    
    op.create_table(
        'tool_call_logs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('conversation_id', sa.String(), nullable=False),
        sa.Column('tool_name', sa.String(), nullable=False),
        sa.Column('inputs', sa.JSON(), nullable=False),
        sa.Column('outputs', sa.JSON(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_tool_call_logs_conversation_id', 'tool_call_logs', ['conversation_id'])
    
    op.create_table(
        'retrieval_logs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('conversation_id', sa.String(), nullable=False),
        sa.Column('query', sa.Text(), nullable=False),
        sa.Column('query_embedding_id', sa.String(), nullable=False),
        sa.Column('chunk_ids', sa.JSON(), nullable=False),
        sa.Column('similarity_scores', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_retrieval_logs_conversation_id', 'retrieval_logs', ['conversation_id'])
    
    op.create_table(
        'escalations',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('conversation_id', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('reason', sa.String(), nullable=False),
        sa.Column('context_summary', sa.Text(), nullable=False),
        sa.Column('notification_sent', sa.Boolean(), server_default='false'),
        sa.Column('resolved', sa.Boolean(), server_default='false'),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id']),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_escalations_conversation_id', 'escalations', ['conversation_id'])
    op.create_index('ix_escalations_tenant_id', 'escalations', ['tenant_id'])
    
    op.create_table(
        'api_keys',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('key_hash', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key_hash')
    )
    op.create_index('ix_api_keys_tenant_id', 'api_keys', ['tenant_id'])
    
    op.create_table(
        'integrations',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('provider', sa.String(), nullable=False),
        sa.Column('encrypted_access_token', sa.Text(), nullable=False),
        sa.Column('encrypted_refresh_token', sa.Text(), nullable=True),
        sa.Column('calendar_id', sa.String(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'provider')
    )
    op.create_index('ix_integrations_tenant_id', 'integrations', ['tenant_id'])
    
    op.create_table(
        'calendar_events',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('conversation_id', sa.String(), nullable=False),
        sa.Column('google_event_id', sa.String(), nullable=False),
        sa.Column('customer_email', sa.String(), nullable=False),
        sa.Column('customer_name', sa.String(), nullable=False),
        sa.Column('start_time', sa.DateTime(), nullable=False),
        sa.Column('end_time', sa.DateTime(), nullable=False),
        sa.Column('meet_link', sa.String(), nullable=True),
        sa.Column('status', sa.Enum('scheduled', 'rescheduled', 'cancelled', name='event_status'), server_default='scheduled'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_calendar_events_tenant_id', 'calendar_events', ['tenant_id'])


def downgrade() -> None:
    op.drop_index('ix_calendar_events_tenant_id', table_name='calendar_events')
    op.drop_table('calendar_events')
    
    op.drop_index('ix_integrations_tenant_id', table_name='integrations')
    op.drop_table('integrations')
    
    op.drop_index('ix_api_keys_tenant_id', table_name='api_keys')
    op.drop_table('api_keys')
    
    op.drop_index('ix_escalations_tenant_id', table_name='escalations')
    op.drop_index('ix_escalations_conversation_id', table_name='escalations')
    op.drop_table('escalations')
    
    op.drop_index('ix_retrieval_logs_conversation_id', table_name='retrieval_logs')
    op.drop_table('retrieval_logs')
    
    op.drop_index('ix_tool_call_logs_conversation_id', table_name='tool_call_logs')
    op.drop_table('tool_call_logs')
    
    op.drop_index('ix_conversation_messages_conversation_id', table_name='conversation_messages')
    op.drop_table('conversation_messages')
    
    op.drop_index('ix_conversations_tenant_id', table_name='conversations')
    op.drop_table('conversations')
    
    op.execute('DROP INDEX IF EXISTS idx_chunks_tenant_embedding')
    op.drop_index('ix_document_chunks_tenant_id', table_name='document_chunks')
    op.drop_index('ix_document_chunks_document_id', table_name='document_chunks')
    op.drop_table('document_chunks')
    
    op.drop_index('ix_documents_tenant_id', table_name='documents')
    op.drop_table('documents')
    
    op.drop_table('tenant_configs')
    op.drop_table('tenant_users')
    op.drop_table('tenants')
    
    op.drop_index('ix_users_email', table_name='users')
    op.drop_table('users')
    
    op.execute('DROP EXTENSION IF EXISTS vector')
