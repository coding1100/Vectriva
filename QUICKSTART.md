# Vectriva Quick Start Guide

## Prerequisites

- Python 3.12+
- Docker & Docker Compose
- uv package manager
- OpenAI API key
- Google Cloud Console project (for Calendar API)

## Step 1: Environment Setup

### Clone and Navigate
```bash
cd Vectriva
```

### Start Infrastructure
```bash
docker-compose up -d
```

This starts:
- PostgreSQL 16 with pgvector on port 5432
- Redis 7 on port 6379

### Create Environment File
```bash
cp .env.example .env
```

Edit `.env` and set:
```bash
# Required - Choose at least one provider
GEMINI_API_KEY=your-gemini-api-key  # Get from https://aistudio.google.com/app/apikey
# OR
OPENAI_API_KEY=sk-your-openai-key   # Get from https://platform.openai.com/api-keys

# Model defaults (Gemini recommended)
DEFAULT_LLM_PROVIDER=gemini
DEFAULT_LLM_MODEL=gemini-1.5-pro
DEFAULT_EMBEDDING_PROVIDER=gemini
DEFAULT_EMBEDDING_MODEL=models/text-embedding-004

# Google Calendar (required for booking)
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# Security (CHANGE THESE!)
JWT_SECRET_KEY=your-random-secret-key-32-chars-minimum
ENCRYPTION_MASTER_KEY=your-32-byte-encryption-key-change-this!

# Database (default for docker-compose)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/vectriva
REDIS_URL=redis://localhost:6379/0
```

## Step 2: Install Dependencies

### Create Virtual Environment
```bash
uv venv
```

### Activate Environment
**Windows**:
```bash
.venv\Scripts\activate
```

**Linux/Mac**:
```bash
source .venv/bin/activate
```

### Install Packages
```bash
uv pip install -e .
```

## Step 3: Initialize Database

### Enable pgvector Extension
```bash
python scripts/init_db.py
```

### Run Migrations
```bash
alembic upgrade head
```

This creates all 13 tables with proper indexes and constraints.

### Verify Database Integration
```bash
python scripts/verify_db.py
```

Expected output: list of tables (users, tenants, tenant_configs, documents, etc.)

**pgAdmin**: Connect to your PostgreSQL (port 5432 for local, 5433 if using Docker). Navigate: **Databases → vectriva → Schemas → public → Tables**. Right-click Tables → Refresh if empty.

### Seed Initial Data (Quick Setup)
```bash
python scripts/seed.py
```
Creates user (admin@example.com / Admin123!), tenant, and API key. Prints credentials and example curl commands.

**Manual flow** (if not using seed):
1. Register: `POST /api/auth/register`
2. Create tenant: `POST /api/tenants` with `Authorization: Bearer <token>`
3. Create API key: `POST /api/tenants/{tenant_id}/api-keys`
4. List your tenants: `GET /api/tenants` with `Authorization: Bearer <token>`

## Step 4: Start the Server

```bash
python main.py
```

Server starts at: http://localhost:8000

API Documentation: http://localhost:8000/docs

## Step 5: Test the API

### Register a User
```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "password123"}'
```

Response:
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "user_id": "uuid"
}
```

### Create a Tenant
```bash
curl -X POST http://localhost:8000/api/tenants \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  -d '{"name": "My Company", "timezone": "America/New_York"}'
```

### Generate API Key
```bash
curl -X POST http://localhost:8000/api/tenants/<tenant_id>/api-keys \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "Production Key"}'
```

Response includes full key (shown once):
```json
{
  "id": "uuid",
  "name": "Production Key",
  "key": "vect_live_xxxxxxxxxxxxx",
  "is_active": true
}
```

### Upload a Document
```bash
curl -X POST "http://localhost:8000/api/tenants/{tenant_id}/documents" \
  -H "Authorization: Bearer <access_token>" \
  -F "file=@product_manual.pdf"
```
Documents are processed asynchronously by Celery. Start worker: `celery -A vectriva.workers.celery_app worker -l info`

### Connect Google Calendar

1. Get OAuth URL:
```bash
curl "http://localhost:8000/api/tenants/{tenant_id}/integrations/google/auth-url" \
  -H "Authorization: Bearer <access_token>"
```

2. Visit the `auth_url` in browser
3. Grant consent
4. You'll be redirected back with a code (handle callback in your app)

### Chat with Agent
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "X-API-Key: vect_live_xxxxxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What products do you have?",
    "customer_email": "customer@example.com",
    "customer_timezone": "America/Los_Angeles"
  }'
```

## Architecture Overview

### Agent Flow
```
User Message → Intent Classification → [Route] → Response Generation
```

Routing options:
- Informational → RAG Retrieval
- Comparison → Product Comparison
- Buying Intent → Recommendations
- Booking Intent → Booking Flow (8 sub-states)
- Escalation → Human Escalation

### Booking Flow
```
Extract DateTime → Check Availability → Offer Slots → Confirm → Create Event → Success
```

### Security Model
- **Admin Auth**: JWT tokens (30min access, 7-day refresh)
- **Widget Auth**: API keys (tenant-specific)
- **Multi-Tenant Isolation**: All queries filtered by `tenant_id`
- **OAuth Tokens**: Encrypted at rest with tenant-specific keys

## Next Steps

1. **Implement LLM Calls**: State functions have signatures but need OpenAI integration
2. **Add Celery**: Background document processing
3. **Build Frontend**: Next.js admin dashboard
4. **Create Widget**: Embeddable chat script
5. **Add Tests**: pytest suite for all endpoints
6. **Setup CI/CD**: GitHub Actions pipeline

## Troubleshooting

### Database Connection Fails
```bash
# Check if PostgreSQL is running
docker-compose ps

# Check logs
docker-compose logs postgres
```

### Redis Connection Fails
```bash
# Check if Redis is running
docker-compose ps

# Test connection
redis-cli ping
```

### Import Errors
```bash
# Ensure virtual environment is activated
which python  # Should show .venv/bin/python

# Reinstall in editable mode
uv pip install -e .
```

### Migration Errors
```bash
# Check current migration status
alembic current

# Reset database (WARNING: destroys data)
alembic downgrade base
alembic upgrade head
```

## Development Commands

### Code Quality
```bash
# Format code
ruff format .

# Lint
ruff check .

# Type check
mypy src
```

### Testing
```bash
# Install dev dependencies
uv pip install -e ".[dev]"

# Run tests
pytest

# With coverage
pytest --cov=src/vectriva
```

### Database Management
```bash
# Create new migration
alembic revision -m "description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1
```

## Production Deployment

See `ARCHITECTURE.md` for detailed deployment strategy.

Quick production checklist:
- [ ] Change all secrets in `.env`
- [ ] Use managed PostgreSQL
- [ ] Use managed Redis
- [ ] Set `DEBUG=false`
- [ ] Enable HTTPS
- [ ] Configure CORS properly
- [ ] Set up monitoring (Sentry, DataDog)
- [ ] Configure backup strategy
- [ ] Set up CI/CD pipeline
- [ ] Load test before launch
