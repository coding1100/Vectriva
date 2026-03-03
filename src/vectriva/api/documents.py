"""Document management API endpoints."""

import logging
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.database import get_db
from ..models.database import Document, DocumentChunk, Tenant
from ..models.schemas import DocumentChunkResponse, DocumentResponse, DocumentUploadResponse
from .middleware import get_current_tenant

router = APIRouter(prefix="/tenants/{tenant_id}/documents", tags=["documents"])


@router.post("", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> DocumentUploadResponse:
    """Upload a document for processing."""
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No filename")

    file_ext = Path(file.filename).suffix.lower()
    allowed_extensions = [".pdf", ".xlsx", ".xls", ".png", ".jpg", ".jpeg"]
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {file_ext}",
        )

    file_size = 0
    content = await file.read()
    file_size = len(content)

    if file_size > settings.max_file_size_mb * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large (max {settings.max_file_size_mb}MB)",
        )

    document_id = str(uuid.uuid4())
    storage_path = Path(settings.file_storage_path) / tenant.id / f"{document_id}{file_ext}"
    storage_path.parent.mkdir(parents=True, exist_ok=True)

    storage_path.write_bytes(content)

    document = Document(
        id=document_id,
        tenant_id=tenant.id,
        name=file.filename,
        file_path=str(storage_path),
        file_type=file_ext,
        status="queued",
    )
    db.add(document)
    await db.commit()

    try:
        from vectriva.workers.tasks import process_document_task
        process_document_task.delay(document_id)
    except Exception as e:
        logging.warning("Celery task enqueue failed (is worker running?): %s", e)

    return DocumentUploadResponse(
        document_id=document.id,
        status=document.status,
        name=document.name,
    )


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    tenant: Tenant = Depends(get_current_tenant), db: AsyncSession = Depends(get_db)
) -> list[DocumentResponse]:
    """List all documents for tenant."""
    result = await db.execute(select(Document).where(Document.tenant_id == tenant.id))
    documents = result.scalars().all()

    return [
        DocumentResponse(
            id=doc.id,
            name=doc.name,
            file_type=doc.file_type,
            status=doc.status,
            chunk_count=doc.chunk_count,
            error_message=doc.error_message,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        )
        for doc in documents
    ]


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """Get document details."""
    result = await db.execute(
        select(Document).where(Document.id == document_id, Document.tenant_id == tenant.id)
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    return DocumentResponse(
        id=document.id,
        name=document.name,
        file_type=document.file_type,
        status=document.status,
        chunk_count=document.chunk_count,
        error_message=document.error_message,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


@router.get("/{document_id}/chunks", response_model=list[DocumentChunkResponse])
async def get_document_chunks(
    document_id: str,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> list[DocumentChunkResponse]:
    """Get chunks for a document."""
    result = await db.execute(
        select(DocumentChunk).where(
            DocumentChunk.document_id == document_id, DocumentChunk.tenant_id == tenant.id
        )
    )
    chunks = result.scalars().all()

    return [
        DocumentChunkResponse(
            id=chunk.id,
            content=chunk.content,
            chunk_type=chunk.chunk_type,
            metadata=chunk.chunk_metadata,
        )
        for chunk in chunks
    ]


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a document and its chunks."""
    result = await db.execute(
        select(Document).where(Document.id == document_id, Document.tenant_id == tenant.id)
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    await db.execute(
        DocumentChunk.__table__.delete().where(DocumentChunk.document_id == document_id)
    )

    await db.delete(document)

    if os.path.exists(document.file_path):
        os.remove(document.file_path)

    await db.commit()
