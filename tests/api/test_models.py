import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_list_model_providers(client: AsyncClient):
    """Test getting the list of model providers."""
    response = await client.get("/api/models/providers")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    # Check if openai and gemini are in the providers
    provider_ids = [p["id"] for p in data]
    assert "openai" in provider_ids
    assert "gemini" in provider_ids

@pytest.mark.asyncio
async def test_list_embedding_models(client: AsyncClient):
    """Test getting the list of embedding models."""
    response = await client.get("/api/models/embeddings")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    # Check if openai and gemini embedding models exist
    providers = [m["provider"] for m in data]
    assert "openai" in providers
    assert "gemini" in providers
