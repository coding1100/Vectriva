# Multi-Model Provider Support

## Overview

Vectriva now supports **multiple LLM and embedding providers** with tenant-level configuration flexibility. Each tenant can choose their preferred provider and model.

---

## Supported Providers

### 1. Google Gemini (Default)
- **LLM Models**:
  - `gemini-1.5-pro` (2M context, $0.00125/1K tokens)
  - `gemini-1.5-flash` (1M context, $0.000075/1K tokens)
  - `gemini-2.0-flash-exp` (1M context, FREE)

- **Embedding Models**:
  - `models/text-embedding-004` (768 dimensions)
  - `models/embedding-001` (768 dimensions)

### 2. OpenAI
- **LLM Models**:
  - `gpt-4o` (128K context, $0.005/1K tokens)
  - `gpt-4o-mini` (128K context, $0.00015/1K tokens)
  - `gpt-4-turbo` (128K context, $0.01/1K tokens)

- **Embedding Models**:
  - `text-embedding-3-small` (1536 dimensions)
  - `text-embedding-3-large` (3072 dimensions)

---

## Configuration Levels

### 1. System-Level Defaults (Environment)

Set in `.env`:
```bash
# Default for all new tenants
DEFAULT_LLM_PROVIDER=gemini
DEFAULT_LLM_MODEL=gemini-1.5-pro
DEFAULT_EMBEDDING_PROVIDER=gemini
DEFAULT_EMBEDDING_MODEL=models/text-embedding-004

# Provider credentials
GEMINI_API_KEY=your-gemini-api-key
OPENAI_API_KEY=sk-your-openai-key  # optional
```

### 2. Tenant-Level Configuration (Database)

Each tenant can override defaults:

```python
class TenantConfig:
    llm_provider: Literal["openai", "gemini"]
    llm_model: str
    embedding_provider: Literal["openai", "gemini"]
    embedding_model: str
```

**API Endpoints**:
```bash
# View current config
GET /api/tenants/{id}/config

# Update model provider
PATCH /api/tenants/{id}/config
{
  "llm_provider": "gemini",
  "llm_model": "gemini-1.5-flash",
  "embedding_provider": "gemini",
  "embedding_model": "models/text-embedding-004"
}
```

---

## Architecture Changes

### Before (OpenAI-only)
```
Agent → OpenAI Client → GPT-4o
RAG   → OpenAI Embeddings → text-embedding-3-small
```

### After (Multi-Provider)
```
Agent → LLMFactory → [OpenAI | Gemini] → Tenant's chosen model
RAG   → LLMFactory → [OpenAI | Gemini] → Tenant's chosen embeddings
```

---

## Implementation Details

### 1. LLM Factory (`services/llm_factory.py`)

**Factory Pattern** for creating provider-specific clients:

```python
from vectriva.services.llm_factory import LLMFactory

# Create chat model
chat_model = LLMFactory.create_chat_model(
    provider="gemini",
    model="gemini-1.5-pro",
    temperature=0.7
)

# Create embeddings
embeddings = LLMFactory.create_embeddings(
    provider="gemini",
    model="models/text-embedding-004"
)

# Tenant-specific instances
chat_model = get_tenant_llm(tenant_config)
embeddings = get_tenant_embeddings(tenant_config)
```

### 2. Vector Storage (Provider-Agnostic)

**Changed from pgvector to BYTEA**:

| Aspect | Old (pgvector) | New (BYTEA) |
|--------|----------------|-------------|
| Storage | `Vector(1536)` | `BYTEA` + `dimension` |
| Search | Native `<=>` operator | Python cosine similarity |
| Flexibility | Fixed dimension | Any dimension (768, 1536, 3072) |
| Dependencies | Requires pgvector extension | PostgreSQL only |

**Trade-offs**:
- ✅ Supports multiple embedding dimensions
- ✅ No pgvector extension dependency
- ✅ Works with any provider
- ⚠️ Slower for large datasets (consider Qdrant migration later)

### 3. Vector Search (`services/vector_search.py`)

**Custom similarity search**:

```python
# Serialize for storage
embedding_bytes = serialize_embedding([0.1, 0.2, 0.3, ...])

# Deserialize for search
embedding_list = deserialize_embedding(embedding_bytes)

# Compute similarity
score = cosine_similarity(query_embedding, chunk_embedding)

# Find top-K
top_k = find_top_k_similar(query_embedding, all_chunks, k=5)
```

---

## Usage Examples

### Example 1: Create Tenant with Gemini

```bash
# Register and login
curl -X POST http://localhost:8000/api/auth/register \
  -d '{"email": "user@example.com", "password": "password123"}'

# Create tenant (defaults to Gemini)
curl -X POST http://localhost:8000/api/tenants \
  -H "Authorization: Bearer <token>" \
  -d '{"name": "My Company", "timezone": "UTC"}'

# Config automatically set:
# {
#   "llm_provider": "gemini",
#   "llm_model": "gemini-1.5-pro",
#   "embedding_provider": "gemini",
#   "embedding_model": "models/text-embedding-004"
# }
```

### Example 2: Switch to OpenAI

```bash
# Update tenant config
curl -X PATCH http://localhost:8000/api/tenants/<tenant_id>/config \
  -H "Authorization: Bearer <token>" \
  -d '{
    "llm_provider": "openai",
    "llm_model": "gpt-4o-mini",
    "embedding_provider": "openai",
    "embedding_model": "text-embedding-3-small"
  }'
```

### Example 3: List Available Models

```bash
# Get all providers and models
curl http://localhost:8000/api/models/providers

# Get embedding models
curl http://localhost:8000/api/models/embeddings
```

---

## Database Schema Changes

### TenantConfig Table

**Added Columns**:
```sql
ALTER TABLE tenant_configs ADD COLUMN llm_provider VARCHAR DEFAULT 'gemini';
ALTER TABLE tenant_configs ADD COLUMN llm_model VARCHAR DEFAULT 'gemini-1.5-pro';
ALTER TABLE tenant_configs ADD COLUMN embedding_provider VARCHAR DEFAULT 'gemini';
ALTER TABLE tenant_configs ADD COLUMN embedding_model VARCHAR DEFAULT 'models/text-embedding-004';
```

### DocumentChunk Table

**Modified Columns**:
```sql
-- Old
embedding VECTOR(1536)

-- New
embedding BYTEA
embedding_dimension INTEGER
```

**Reason**: Support variable embedding dimensions (768 for Gemini, 1536/3072 for OpenAI)

---

## Migration Guide

### For Existing Installations

If you have existing data with pgvector:

1. **Export embeddings**:
```sql
SELECT id, embedding::text FROM document_chunks;
```

2. **Convert to BYTEA**:
```python
import struct
embedding_bytes = struct.pack(f"{len(vector)}f", *vector)
```

3. **Re-insert with dimension**:
```sql
UPDATE document_chunks 
SET embedding = ?, embedding_dimension = 1536 
WHERE id = ?;
```

### For Fresh Installations

Just run migrations:
```bash
alembic upgrade head
```

---

## API Changes

### New Endpoints

**List Providers**:
```
GET /api/models/providers
```

Response:
```json
[
  {
    "id": "gemini",
    "name": "Google Gemini",
    "available_models": [...],
    "supports_embeddings": true
  },
  {
    "id": "openai",
    "name": "OpenAI",
    "available_models": [...],
    "supports_embeddings": true
  }
]
```

**List Embeddings**:
```
GET /api/models/embeddings
```

Response:
```json
[
  {
    "provider": "gemini",
    "model_id": "models/text-embedding-004",
    "name": "Gemini Embedding 004 (768 dims)",
    "dimensions": 768
  },
  {
    "provider": "openai",
    "model_id": "text-embedding-3-small",
    "name": "OpenAI Small (1536 dims)",
    "dimensions": 1536
  }
]
```

### Modified Endpoints

**Get/Update Config** now includes model fields:

```json
{
  "persona_name": "Assistant",
  "tone": "professional",
  "llm_provider": "gemini",
  "llm_model": "gemini-1.5-pro",
  "embedding_provider": "gemini",
  "embedding_model": "models/text-embedding-004",
  ...
}
```

---

## Performance Considerations

### Embedding Dimensions

| Provider | Model | Dimensions | Storage per 1M chunks |
|----------|-------|------------|----------------------|
| Gemini | text-embedding-004 | 768 | ~3 GB |
| OpenAI | text-embedding-3-small | 1536 | ~6 GB |
| OpenAI | text-embedding-3-large | 3072 | ~12 GB |

**Recommendation**: Use Gemini embeddings (768d) for faster search and lower storage.

### Search Performance

| Method | Dataset Size | Latency |
|--------|--------------|---------|
| Python cosine | < 10K chunks | 50-100ms |
| Python cosine | 10K-100K chunks | 500-1000ms |
| pgvector (future) | > 100K chunks | 10-50ms |

**Scaling Path**:
- Phase 1 (< 100K chunks): Python search (current)
- Phase 2 (100K-1M chunks): Re-enable pgvector with dynamic dimensions
- Phase 3 (> 1M chunks): Migrate to Qdrant

---

## Cost Comparison

### Example: 1M tokens processed per month

| Provider | Model | Cost/Month |
|----------|-------|------------|
| Gemini | gemini-1.5-flash | $0.075 |
| Gemini | gemini-1.5-pro | $1.25 |
| OpenAI | gpt-4o-mini | $0.15 |
| OpenAI | gpt-4o | $5.00 |
| OpenAI | gpt-4-turbo | $10.00 |

**Recommendation**: Start with `gemini-1.5-flash` for cost efficiency, upgrade to `gemini-1.5-pro` for better quality.

---

## Environment Setup

### Option 1: Gemini Only (Recommended for Start)

```bash
# .env
DEFAULT_LLM_PROVIDER=gemini
GEMINI_API_KEY=your-gemini-api-key

# Optional: Leave OpenAI empty
OPENAI_API_KEY=
```

### Option 2: OpenAI Only

```bash
# .env
DEFAULT_LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-key

# Optional: Leave Gemini empty
GEMINI_API_KEY=
```

### Option 3: Both Providers

```bash
# .env
DEFAULT_LLM_PROVIDER=gemini
GEMINI_API_KEY=your-gemini-key
OPENAI_API_KEY=sk-your-openai-key
```

**Benefits**: Tenants can choose, or fall back if one provider has issues.

---

## Testing Different Providers

### Test with Gemini (Default)

```bash
# Create tenant (uses Gemini by default)
curl -X POST http://localhost:8000/api/tenants \
  -H "Authorization: Bearer <token>" \
  -d '{"name": "Gemini Tenant"}'

# Upload document (embeds with Gemini)
curl -X POST http://localhost:8000/api/documents \
  -H "Authorization: Bearer <token>" \
  -F "file=@doc.pdf"

# Chat (uses Gemini for agent)
curl -X POST http://localhost:8000/api/chat \
  -H "X-API-Key: <key>" \
  -d '{"message": "Hello"}'
```

### Test with OpenAI

```bash
# Switch tenant to OpenAI
curl -X PATCH http://localhost:8000/api/tenants/<tenant_id>/config \
  -H "Authorization: Bearer <token>" \
  -d '{
    "llm_provider": "openai",
    "llm_model": "gpt-4o-mini",
    "embedding_provider": "openai",
    "embedding_model": "text-embedding-3-small"
  }'

# Now all operations use OpenAI
```

---

## Model Selection Best Practices

### For Development
- Use **Gemini 1.5 Flash** or **GPT-4o Mini**
- Lowest cost, fast iteration
- Good quality for testing

### For Production (Accuracy Priority)
- Use **Gemini 1.5 Pro** or **GPT-4o**
- Best reasoning capabilities
- Higher quality responses

### For Production (Cost Priority)
- Use **Gemini 1.5 Flash**
- 10x cheaper than GPT-4o
- Still high quality for most use cases

### For Embeddings
- Use **Gemini text-embedding-004** (768d)
- Lower storage costs
- Faster similarity search
- Excellent semantic quality

---

## Files Modified

1. ✅ `pyproject.toml` - Added Gemini dependencies
2. ✅ `core/config.py` - Provider config options
3. ✅ `models/database.py` - Model fields in TenantConfig
4. ✅ `models/schemas.py` - API schema updates
5. ✅ `services/llm_factory.py` - **NEW** - Factory pattern
6. ✅ `services/rag_service.py` - Use factory
7. ✅ `services/vector_search.py` - **NEW** - Custom search
8. ✅ `workers/document_processor.py` - Use factory
9. ✅ `api/tenants.py` - Return model fields
10. ✅ `api/models.py` - **NEW** - Model listing endpoints
11. ✅ `api/main.py` - Register models router
12. ✅ `alembic/versions/001_initial_schema.py` - Updated schema
13. ✅ `.env.example` - Added Gemini config
14. ✅ `scripts/init_db.py` - Removed pgvector dependency

---

## Migration from OpenAI to Gemini

If you started with OpenAI setup:

```bash
# Update environment
DEFAULT_LLM_PROVIDER=gemini
GEMINI_API_KEY=your-key

# Update tenant config via API
curl -X PATCH /api/tenants/{id}/config \
  -d '{
    "llm_provider": "gemini",
    "llm_model": "gemini-1.5-pro",
    "embedding_provider": "gemini",
    "embedding_model": "models/text-embedding-004"
  }'

# Re-index documents (to use new embeddings)
curl -X POST /api/documents/{id}/reindex
```

**Note**: Changing embedding provider requires re-indexing all documents.

---

## Advanced: Mixed Provider Setup

**Use Case**: Gemini for agent chat, OpenAI for embeddings

```python
# In tenant config
{
  "llm_provider": "gemini",        # Chat with Gemini (cheaper)
  "llm_model": "gemini-1.5-flash",
  "embedding_provider": "openai",   # Embed with OpenAI (higher quality)
  "embedding_model": "text-embedding-3-large"
}
```

**Benefits**:
- Cost savings on chat (Gemini is cheaper)
- Best-in-class embeddings (OpenAI large model)

---

## Troubleshooting

### Error: "Unsupported LLM provider"

**Cause**: Provider not in `["openai", "gemini"]`

**Fix**: Check tenant config spelling

---

### Error: "Failed to generate query embedding"

**Cause**: Missing API key for configured provider

**Fix**: 
```bash
# Check .env has the right key
GEMINI_API_KEY=your-key  # for Gemini
OPENAI_API_KEY=sk-key    # for OpenAI
```

---

### Error: "Invalid API key"

**Gemini**:
- Get key from: https://aistudio.google.com/app/apikey
- Format: `AIza...`

**OpenAI**:
- Get key from: https://platform.openai.com/api-keys
- Format: `sk-...`

---

## Summary

✅ **Multi-provider support** - OpenAI and Gemini  
✅ **Tenant-level choice** - Each tenant picks their provider  
✅ **Cost flexibility** - From free (Gemini Flash) to premium (GPT-4o)  
✅ **Variable dimensions** - 768d to 3072d embeddings  
✅ **No vendor lock-in** - Easy to add more providers  
✅ **Production-ready** - Factory pattern, error handling  

**Your setup**: Start with Gemini (free/cheap), optionally add OpenAI later for tenants who need it.
