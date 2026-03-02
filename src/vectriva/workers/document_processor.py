"""Document processing worker for ingestion pipeline."""

import uuid
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader, UnstructuredExcelLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..models.database import Document, DocumentChunk, TenantConfig
from ..services.llm_factory import get_tenant_embeddings

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    length_function=len,
)


async def process_document(db: AsyncSession, document_id: str) -> None:
    """Process a document and generate embeddings."""
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()

    if not document:
        raise ValueError(f"Document {document_id} not found")

    config_result = await db.execute(
        select(TenantConfig).where(TenantConfig.tenant_id == document.tenant_id)
    )
    tenant_config = config_result.scalar_one_or_none()

    embeddings = get_tenant_embeddings(tenant_config)

    document.status = "processing"
    await db.flush()

    try:
        file_path = Path(document.file_path)
        file_ext = file_path.suffix.lower()

        chunks_to_create: list[dict[str, Any]] = []

        if file_ext == ".pdf":
            chunks_to_create = await _process_pdf(file_path, document, embeddings)
        elif file_ext in [".xlsx", ".xls"]:
            chunks_to_create = await _process_excel(file_path, document, embeddings)
        elif file_ext in [".png", ".jpg", ".jpeg"]:
            chunks_to_create = await _process_image(file_path, document, embeddings)
        else:
            raise ValueError(f"Unsupported file type: {file_ext}")

        from ..services.vector_search import serialize_embedding

        for chunk_data in chunks_to_create:
            embedding_bytes = serialize_embedding(chunk_data["embedding"])
            chunk = DocumentChunk(
                id=str(uuid.uuid4()),
                document_id=document.id,
                tenant_id=document.tenant_id,
                content=chunk_data["content"],
                chunk_type=chunk_data["type"],
                embedding=embedding_bytes,
                embedding_dimension=len(chunk_data["embedding"]),
                chunk_metadata=chunk_data.get("metadata", {}),
            )
            db.add(chunk)

        document.status = "indexed"
        document.chunk_count = len(chunks_to_create)
        await db.commit()

    except Exception as e:
        document.status = "failed"
        document.error_message = str(e)
        await db.commit()
        raise


async def _process_pdf(file_path: Path, document: Document, embeddings: Any) -> list[dict]:
    """Process PDF document."""
    loader = PyPDFLoader(str(file_path))
    pages = loader.load()

    all_text = "\n\n".join([page.page_content for page in pages])
    chunks = text_splitter.split_text(all_text)

    results = []
    for chunk_text in chunks:
        embedding = await embeddings.aembed_query(chunk_text)
        results.append(
            {
                "content": chunk_text,
                "type": "text",
                "embedding": embedding,
                "metadata": {"source": "pdf"},
            }
        )

    return results


async def _process_excel(file_path: Path, document: Document, embeddings: Any) -> list[dict]:
    """Process Excel document."""
    loader = UnstructuredExcelLoader(str(file_path), mode="elements")
    elements = loader.load()

    results = []
    for element in elements:
        if element.metadata.get("category") == "Table":
            chunk_type = "table"
        else:
            chunk_type = "text"

        embedding = await embeddings.aembed_query(element.page_content)
        results.append(
            {
                "content": element.page_content,
                "type": chunk_type,
                "embedding": embedding,
                "metadata": element.metadata,
            }
        )

    return results


async def _process_image(file_path: Path, document: Document, embeddings: Any) -> list[dict]:
    """Process image document."""
    img = Image.open(file_path)

    caption = f"Image: {document.name}"

    embedding = await embeddings.aembed_query(caption)

    return [
        {
            "content": caption,
            "type": "image_caption",
            "embedding": embedding,
            "metadata": {
                "width": img.width,
                "height": img.height,
                "format": img.format,
            },
        }
    ]
