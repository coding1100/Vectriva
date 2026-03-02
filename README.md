# Vectriva

Production-Grade Agentic Multimodal RAG SaaS Platform

## Overview

Vectriva enables businesses to deploy intelligent, product-trained AI agents capable of:

- Understanding product documentation (PDFs, Excel, images)
- Multimodal RAG retrieval (text, tables, images)
- Conversational product guidance and recommendations
- Booking appointments via Google Calendar with Meet links
- Operating in a secure multi-tenant SaaS environment

## Technology Stack

- **Backend**: Python 3.12+, FastAPI
- **Agent**: LangGraph, LangChain, OpenAI
- **Database**: PostgreSQL + pgvector
- **Cache**: Redis
- **Task Queue**: Celery
- **Auth**: Custom JWT + OAuth2

## Getting Started

### Prerequisites

- Python 3.12+
- PostgreSQL 16+ with pgvector extension
- Redis
- uv package manager

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd Vectriva
```

2. Create virtual environment and install dependencies:
```bash
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your credentials
```

4. Initialize database:
```bash
alembic upgrade head
```

5. Run the server:
```bash
uvicorn src.vectriva.api.main:app --reload
```

## Architecture

### Agent Workflow

The agent uses a deterministic LangGraph state machine with the following states:

- Intent Classification
- Knowledge Retrieval
- Product Comparison
- Recommendation Engine
- Booking Flow (with sub-states)
- Human Escalation

### Multi-Tenant Isolation

Every database operation is filtered by `tenant_id` with row-level security. Each tenant has:

- Isolated document library
- Separate embedding namespace
- Individual OAuth tokens
- API keys for external access

## API Documentation

Once running, visit:

- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

## Development

### Project Structure

```
src/vectriva/
├── agent/           # LangGraph state machine
├── api/             # FastAPI endpoints
├── core/            # Config, database, errors
├── models/          # SQLAlchemy & Pydantic models
├── services/        # Business logic
└── workers/         # Background tasks
```

### Testing

```bash
uv pip install -e ".[dev]"
pytest
```

### Code Quality

```bash
ruff check .
ruff format .
mypy src
```

## License

Proprietary
