"""Verify database connection and list tables."""

import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from vectriva.core.config import settings


async def verify() -> None:
    """Check connection and list tables."""
    engine = create_async_engine(settings.database_url)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text("""
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                    ORDER BY table_name
                """)
            )
            tables = [row[0] for row in result]
            if tables:
                print("Tables in vectriva database:")
                for t in tables:
                    print(f"  - {t}")
            else:
                print("No tables found. Run: alembic upgrade head")
    except Exception as e:
        print(f"Error: {e}")
        print("Ensure: 1) Docker is running  2) docker-compose up -d")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(verify())
