"""Model provider management endpoints."""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/models", tags=["models"])


class ModelProvider(BaseModel):
    """Model provider information."""

    id: str
    name: str
    description: str
    available_models: list["ModelInfo"]
    supports_embeddings: bool


class ModelInfo(BaseModel):
    """Model information."""

    id: str
    name: str
    context_window: int
    cost_per_1k_tokens: float


@router.get("/providers", response_model=list[ModelProvider])
async def list_model_providers() -> list[ModelProvider]:
    """List available model providers and their models."""
    return [
        ModelProvider(
            id="openai",
            name="OpenAI",
            description="GPT-4 and GPT-4o models from OpenAI",
            available_models=[
                ModelInfo(
                    id="gpt-4o",
                    name="GPT-4o",
                    context_window=128000,
                    cost_per_1k_tokens=0.005,
                ),
                ModelInfo(
                    id="gpt-4o-mini",
                    name="GPT-4o Mini",
                    context_window=128000,
                    cost_per_1k_tokens=0.00015,
                ),
                ModelInfo(
                    id="gpt-4-turbo",
                    name="GPT-4 Turbo",
                    context_window=128000,
                    cost_per_1k_tokens=0.01,
                ),
            ],
            supports_embeddings=True,
        ),
        ModelProvider(
            id="gemini",
            name="Google Gemini",
            description="Gemini 1.5 Pro and Flash models from Google",
            available_models=[
                ModelInfo(
                    id="gemini-1.5-pro",
                    name="Gemini 1.5 Pro",
                    context_window=2000000,
                    cost_per_1k_tokens=0.00125,
                ),
                ModelInfo(
                    id="gemini-1.5-flash",
                    name="Gemini 1.5 Flash",
                    context_window=1000000,
                    cost_per_1k_tokens=0.000075,
                ),
                ModelInfo(
                    id="gemini-2.0-flash-exp",
                    name="Gemini 2.0 Flash (Experimental)",
                    context_window=1000000,
                    cost_per_1k_tokens=0.0,
                ),
            ],
            supports_embeddings=True,
        ),
    ]


@router.get("/embeddings", response_model=list[dict[str, str | int]])
async def list_embedding_models() -> list[dict[str, str | int]]:
    """List available embedding models."""
    return [
        {
            "provider": "openai",
            "model_id": "text-embedding-3-small",
            "name": "OpenAI Small (1536 dims)",
            "dimensions": 1536,
        },
        {
            "provider": "openai",
            "model_id": "text-embedding-3-large",
            "name": "OpenAI Large (3072 dims)",
            "dimensions": 3072,
        },
        {
            "provider": "gemini",
            "model_id": "models/text-embedding-004",
            "name": "Gemini Embedding 004 (768 dims)",
            "dimensions": 768,
        },
    ]
