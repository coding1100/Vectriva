# Vectriva Architecture

## Project Structure

```
Vectriva/
├── src/vectriva/
│   ├── agent/                   # LangGraph Agent Core
│   │   ├── __init__.py
│   │   ├── context.py           # AgentContext dataclass
│   │   ├── state_machine.py     # LangGraph state graph
│   │   ├── states.py            # Individual state implementations
│   │   └── tools.py             # Tool schemas (Pydantic)
│   │
│   ├── api/                     # FastAPI Endpoints
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app
│   │   ├── auth.py              # Auth endpoints (register/login)
│   │   ├── tenants.py           # Tenant & config management
│   │   ├── documents.py         # Document upload/management
│   │   ├── integrations.py      # Google Calendar OAuth
│   │   ├── conversations.py     # Observability endpoints
│   │   ├── chat.py              # Chat endpoint (agent invocation)
│   │   └── middleware.py        # Auth & tenant isolation
│   │
│   ├── core/                    # Core Utilities
│   │   ├── __init__.py
│   │   ├── config.py            # Settings (Pydantic)
│   │   ├── database.py          # SQLAlchemy async session
│   │   ├── redis.py             # Redis client
│   │   ├── errors.py            # Custom exceptions
│   │   └── retry.py             # Retry logic & policies
│   │
│   ├── models/                  # Data Models
│   │   ├── __init__.py
│   │   ├── database.py          # SQLAlchemy ORM models
│   │   └── schemas.py           # Pydantic API schemas
│   │
│   ├── services/                # Business Logic Layer
│   │   ├── __init__.py
│   │   ├── auth_service.py      # JWT & password hashing
│   │   ├── calendar_service.py  # Google Calendar API
│   │   ├── rag_service.py       # Vector retrieval
│   │   ├── escalation_service.py
│   │   └── encryption_service.py # Token encryption (Fernet)
│   │
│   └── workers/                 # Background Workers
│       ├── __init__.py
│       └── document_processor.py # Document ingestion pipeline
│
├── alembic/                     # Database Migrations
│   ├── env.py
│   ├── versions/
│   │   └── 001_initial_schema.py
│   └── script.py.mako
│
├── tests/                       # Test Suite
│   ├── __init__.py
│   └── conftest.py
│
├── scripts/
│   └── init_db.py               # Database initialization
│
├── docker-compose.yml           # Local dev environment
├── Dockerfile                   # Production container
├── alembic.ini                  # Alembic config
├── pyproject.toml               # Dependencies (uv)
├── .env.example                 # Environment template
├── main.py                      # Run script
└── README.md
```

## Key Components

### 1. Agent State Machine (`agent/state_machine.py`)

Deterministic LangGraph workflow with 18 states:

- **IntentClassification**: Route to appropriate flow
- **KnowledgeRetrieval**: RAG query execution
- **ProductComparison**: Multi-product structured comparison
- **RecommendationEngine**: Product matching logic
- **BookingRouter**: Determine booking action (new/reschedule/cancel)
- **BookingExtractDateTime**: Parse date/time from user input
- **BookingCheckAvailability**: Query Google Calendar
- **BookingOfferSlots**: Present available times
- **BookingConfirmSlot**: Confirm selection
- **BookingCreateEvent**: Create event with Meet link
- **HumanEscalation**: Flag for human review
- **EscalatedMode**: Restricted capabilities mode

### 2. Tool Schemas (`agent/tools.py`)

Six tools exposed to the agent:

1. `check_availability` - Query calendar for free slots
2. `create_event` - Book appointment with Meet link
3. `reschedule_event` - Modify existing booking
4. `cancel_event` - Cancel appointment
5. `retrieve_product_data` - RAG retrieval
6. `escalate_to_human` - Human handoff

Each tool has:
- Pydantic input/output schemas
- Validation rules
- Typed error responses

### 3. Database Models (`models/database.py`)

13 tables with full multi-tenant isolation:

- `users` - User accounts
- `tenants` - Tenant organizations
- `tenant_users` - Many-to-many with roles
- `tenant_configs` - Per-tenant settings
- `documents` - Uploaded files
- `document_chunks` - Embedded chunks (with pgvector)
- `conversations` - Chat sessions
- `conversation_messages` - Individual messages
- `tool_call_logs` - Agent tool invocations
- `retrieval_logs` - RAG queries
- `escalations` - Human escalation records
- `api_keys` - Tenant API keys
- `integrations` - OAuth tokens (encrypted)
- `calendar_events` - Booked appointments

### 4. API Endpoints

#### Auth (`api/auth.py`)
- `POST /api/auth/register` - Create account
- `POST /api/auth/login` - Get JWT tokens
- `POST /api/auth/refresh` - Refresh access token

#### Tenants (`api/tenants.py`)
- `POST /api/tenants` - Create tenant
- `GET /api/tenants/{id}/config` - Get config
- `PATCH /api/tenants/{id}/config` - Update config
- `POST /api/tenants/{id}/api-keys` - Generate API key
- `GET /api/tenants/{id}/api-keys` - List keys
- `DELETE /api/tenants/{id}/api-keys/{key_id}` - Revoke key

#### Documents (`api/documents.py`)
- `POST /api/documents` - Upload document
- `GET /api/documents` - List documents
- `GET /api/documents/{id}` - Get document details
- `GET /api/documents/{id}/chunks` - View chunks
- `DELETE /api/documents/{id}` - Delete document

#### Integrations (`api/integrations.py`)
- `GET /api/integrations/google/auth-url` - Start OAuth
- `POST /api/integrations/google/callback` - OAuth callback
- `GET /api/integrations/google/calendars` - List calendars
- `PUT /api/integrations/google/calendar` - Set booking calendar
- `GET /api/integrations/google/status` - Check connection
- `DELETE /api/integrations/google` - Disconnect

#### Conversations (`api/conversations.py`)
- `GET /api/conversations` - List conversations (paginated)
- `GET /api/conversations/{id}` - Get conversation details
- `GET /api/conversations/{id}/tool-calls` - Tool execution logs
- `GET /api/conversations/{id}/retrievals` - RAG retrieval logs

#### Chat (`api/chat.py`)
- `POST /api/chat` - Send message to agent (uses API key auth)

### 5. Services Layer

- `auth_service.py` - JWT creation/validation, password hashing
- `calendar_service.py` - Google Calendar API wrapper
- `rag_service.py` - Vector search & retrieval
- `escalation_service.py` - Escalation workflow
- `encryption_service.py` - Fernet encryption for OAuth tokens

### 6. Error Handling (`core/retry.py`)

Retry policies per error type:

| Error | Retryable | Max Retries | Backoff |
|-------|-----------|-------------|---------|
| `CalendarAPIError` | Yes | 3 | Exponential (1s, 2s, 4s) |
| `EmbeddingServiceError` | Yes | 2 | Linear (1s, 2s) |
| `SlotNoLongerAvailable` | No | - | Re-fetch |
| `EventNotFound` | No | - | Inform user |

Auto-escalation triggers:
- 3+ consecutive errors
- Confidence < 0.4
- Explicit user request

### 7. Document Processing Pipeline (`workers/document_processor.py`)

Async processing flow:

1. Upload → Store raw file
2. Queue → Celery task
3. Process → Extract content based on type:
   - PDF: Text extraction + chunking
   - Excel: Table detection + summaries
   - Images: Caption generation (placeholder)
4. Embed → Generate embeddings per chunk
5. Index → Store in pgvector with tenant_id

## Data Flow

### Chat Request Flow

```
Client (with API key)
  ↓
POST /api/chat
  ↓
verify_api_key (middleware) → Tenant + APIKey
  ↓
Load/Create AgentContext from Redis
  ↓
Invoke LangGraph state machine
  ↓
Execute states (LLM calls, tool calls, transitions)
  ↓
Generate response
  ↓
Store context to Redis
  ↓
Log messages/tools to PostgreSQL
  ↓
Return response to client
```

### Document Ingestion Flow

```
Client uploads PDF
  ↓
POST /api/documents/upload
  ↓
Store file in storage/
  ↓
Create Document record (status=queued)
  ↓
Enqueue Celery job
  ↓
Worker picks up job
  ↓
Extract text/tables/images
  ↓
Chunk content
  ↓
Generate embeddings (OpenAI)
  ↓
Store chunks with vectors in PostgreSQL
  ↓
Update Document (status=indexed)
```

### Google Calendar Booking Flow

```
Agent detects booking intent
  ↓
Extract date/time preferences (LLM structured output)
  ↓
Call check_availability tool
  ↓
calendar_service.check_availability()
  ↓
Fetch encrypted tokens from DB
  ↓
Decrypt using tenant-specific key
  ↓
Query Google Calendar API
  ↓
Find free slots (avoid busy times)
  ↓
Present slots to user
  ↓
User selects slot
  ↓
Call create_event tool
  ↓
calendar_service.create_event()
  ↓
Create event with conferenceData (Meet link)
  ↓
Store event in calendar_events table
  ↓
Return confirmation with Meet link
```

## Security

### Multi-Tenant Isolation

Every query includes `tenant_id` filter:

```python
# Good
select(Document).where(Document.tenant_id == tenant_id)

# Bad (cross-tenant leak risk)
select(Document).where(Document.id == document_id)
```

Middleware enforces tenant access:
- JWT-based admin auth: `get_current_tenant()`
- API key-based widget auth: `verify_api_key()`

### OAuth Token Security

Google OAuth tokens encrypted at rest:

1. Derive tenant-specific key from master key
2. Encrypt tokens using Fernet
3. Store encrypted blobs in `integrations` table
4. Decrypt on-demand for API calls

### Password Security

- Bcrypt hashing with salt
- Min 8 characters
- No plaintext storage

## Deployment

### Local Development

```bash
# Start dependencies
docker-compose up -d

# Create .env from template
cp .env.example .env

# Install dependencies
uv venv
source .venv/bin/activate
uv pip install -e .

# Initialize database
python scripts/init_db.py
alembic upgrade head

# Run server
python main.py
```

### Production

```bash
# Build image
docker build -t vectriva:latest .

# Run with environment variables
docker run -e DATABASE_URL=... -e OPENAI_API_KEY=... -p 8000:8000 vectriva:latest
```

## Next Steps

1. Implement LLM integration in state functions
2. Add Celery worker for document processing
3. Implement sentiment analysis for escalation
4. Add rate limiting middleware
5. Build Next.js admin dashboard
6. Create embeddable chat widget
7. Add comprehensive tests
8. Set up CI/CD pipeline
