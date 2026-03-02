"""Initialize database with pgvector extension."""

import asyncio

from sqlalchemy.ext.asyncio import create_async_engine

from src.vectriva.core.config import settings


async def init_db() -> None:
    """Initialize database and create pgvector extension."""
    engine = create_async_engine(settings.database_url)

    async with engine.begin() as conn:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        print("pgvector extension created successfully")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(init_db())
