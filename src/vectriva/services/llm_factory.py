"""LLM provider factory for multi-model support."""

from typing import Any, Literal

from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from ..core.config import settings


class LLMFactory:
    """Factory for creating LLM and embedding clients based on provider."""

    @staticmethod
    def create_chat_model(
        provider: Literal["openai", "gemini"] | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> BaseChatModel:
        """
        Create a chat model instance.

        Args:
            provider: "openai" or "gemini". Defaults to settings.default_llm_provider
            model: Model name. Defaults to provider's default model
            temperature: Sampling temperature
            **kwargs: Additional provider-specific parameters
        """
        provider = provider or settings.default_llm_provider

        if provider == "openai":
            return ChatOpenAI(
                api_key=settings.openai_api_key,
                model=model or settings.openai_model,
                temperature=temperature,
                **kwargs,
            )
        elif provider == "gemini":
            return ChatGoogleGenerativeAI(
                google_api_key=settings.gemini_api_key,
                model=model or settings.gemini_model,
                temperature=temperature,
                **kwargs,
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")

    @staticmethod
    def create_embeddings(
        provider: Literal["openai", "gemini"] | None = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> Embeddings:
        """
        Create an embeddings instance.

        Args:
            provider: "openai" or "gemini". Defaults to settings.default_embedding_provider
            model: Model name. Defaults to provider's default model
            **kwargs: Additional provider-specific parameters
        """
        provider = provider or settings.default_embedding_provider

        if provider == "openai":
            return OpenAIEmbeddings(
                api_key=settings.openai_api_key,
                model=model or settings.openai_embedding_model,
                **kwargs,
            )
        elif provider == "gemini":
            return GoogleGenerativeAIEmbeddings(
                google_api_key=settings.gemini_api_key,
                model=model or settings.gemini_embedding_model,
                **kwargs,
            )
        else:
            raise ValueError(f"Unsupported embedding provider: {provider}")

    @staticmethod
    def get_embedding_dimension(provider: Literal["openai", "gemini"], model: str) -> int:
        """Get embedding dimension for a specific model."""
        dimensions = {
            # OpenAI
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536,
            # Gemini
            "text-embedding-004": 768,
            "models/text-embedding-004": 768,
            "embedding-001": 768,
            "models/gemini-embedding-001": 768,
        }
        return dimensions.get(model, 768)


def get_tenant_llm(tenant_config: Any) -> BaseChatModel:
    """Get LLM instance for specific tenant based on their config."""
    provider = getattr(tenant_config, "llm_provider", settings.default_llm_provider)
    model = getattr(tenant_config, "llm_model", None)

    return LLMFactory.create_chat_model(provider=provider, model=model)


def get_tenant_embeddings(tenant_config: Any) -> Embeddings:
    """Get embeddings instance for specific tenant based on their config."""
    provider = getattr(tenant_config, "embedding_provider", settings.default_embedding_provider)
    model = getattr(tenant_config, "embedding_model", None)

    return LLMFactory.create_embeddings(provider=provider, model=model)
