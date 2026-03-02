"""RAG service for document retrieval."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..agent.tools import Chunk, RetrieveProductDataInput, RetrieveProductDataOutput
from ..core.config import settings
from ..core.errors import EmbeddingServiceError, NoDocumentsIndexedError
from ..models.database import DocumentChunk, TenantConfig
from .llm_factory import get_tenant_embeddings


async def retrieve_product_data(
    db: AsyncSession, tenant_id: str, input_data: RetrieveProductDataInput
) -> RetrieveProductDataOutput:
    """Retrieve relevant document chunks using vector similarity."""
    config_result = await db.execute(
        select(TenantConfig).where(TenantConfig.tenant_id == tenant_id)
    )
    tenant_config = config_result.scalar_one_or_none()

    embeddings = get_tenant_embeddings(tenant_config)

    try:
        query_embedding = await embeddings.aembed_query(input_data.query)
    except Exception as e:
        raise EmbeddingServiceError(f"Failed to generate query embedding: {e}") from e

    query = select(DocumentChunk).where(DocumentChunk.tenant_id == tenant_id)

    if input_data.filter_document_types:
        query = query.where(DocumentChunk.chunk_type.in_(input_data.filter_document_types))

    result = await db.execute(query)
    chunks_db = result.scalars().all()

    if not chunks_db:
        raise NoDocumentsIndexedError("No documents available for retrieval")

    from .vector_search import deserialize_embedding, find_top_k_similar

    chunk_embeddings = [(chunk.id, chunk.embedding) for chunk in chunks_db]
    top_k_results = find_top_k_similar(query_embedding, chunk_embeddings, input_data.top_k)

    chunks_map = {chunk.id: chunk for chunk in chunks_db}
    chunks = []

    for chunk_id, similarity in top_k_results:
        chunk = chunks_map[chunk_id]
        chunks.append(
            Chunk(
                content=chunk.content,
                document_id=chunk.document_id,
                document_name="",
                chunk_type=chunk.chunk_type,
                similarity_score=similarity,
                metadata=chunk.chunk_metadata,
            )
        )

    query_embedding_id = str(uuid.uuid4())

    return RetrieveProductDataOutput(chunks=chunks, query_embedding_id=query_embedding_id)
