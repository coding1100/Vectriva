"""Celery tasks."""

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from vectriva.core.database import AsyncSessionLocal
from vectriva.workers.celery_app import app
from vectriva.workers.document_processor import process_document


@app.task(bind=True, max_retries=3)
def process_document_task(self, document_id: str) -> None:
    """Process a document asynchronously (chunk, embed, index)."""
    async def _run() -> None:
        async with AsyncSessionLocal() as db:
            await process_document(db, document_id)

    try:
        asyncio.run(_run())
    except Exception as exc:
        raise self.retry(exc=exc)
