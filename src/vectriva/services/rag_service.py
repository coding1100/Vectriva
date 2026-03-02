"""RAG service for document retrieval."""

import uuid
from typing import Any

from langchain_openai import OpenAIEmbeddings
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..agent.tools import Chunk, RetrieveProductDataInput, RetrieveProductDataOutput
from ..core.config import settings
from ..core.errors import EmbeddingServiceError, NoDocumentsIndexedError
from ..models.database import DocumentChunk

embeddings = OpenAIEmbeddings(
    model=settings.openai_embedding_model,
    openai_api_key=settings.openai_api_key,
)


async def retrieve_product_data(
    db: AsyncSession, tenant_id: str, input_data: RetrieveProductDataInput
) -> RetrieveProductDataOutput:
    """Retrieve relevant document chunks using vector similarity."""
    try:
        query_embedding = await embeddings.aembed_query(input_data.query)
    except Exception as e:
        raise EmbeddingServiceError(f"Failed to generate query embedding: {e}") from e

    query = (
        select(DocumentChunk)
        .where(DocumentChunk.tenant_id == tenant_id)
        .order_by(DocumentChunk.embedding.cosine_distance(query_embedding))
        .limit(input_data.top_k)
    )

    if input_data.filter_document_types:
        query = query.where(DocumentChunk.chunk_type.in_(input_data.filter_document_types))

    result = await db.execute(query)
    chunks_db = result.scalars().all()

    if not chunks_db:
        raise NoDocumentsIndexedError("No documents available for retrieval")

    chunks = [
        Chunk(
            content=chunk.content,
            document_id=chunk.document_id,
            document_name="",  # TODO: Join with document table
            chunk_type=chunk.chunk_type,
            similarity_score=0.0,  # TODO: Calculate from distance
            metadata=chunk.metadata,
        )
        for chunk in chunks_db
    ]

    query_embedding_id = str(uuid.uuid4())

    return RetrieveProductDataOutput(chunks=chunks, query_embedding_id=query_embedding_id)
