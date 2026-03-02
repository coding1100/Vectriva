"""Initialize database: create vectriva DB if missing, then verify connection."""

import asyncio
import re

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from vectriva.core.config import settings


def _get_psycopg2_url(db_name: str = "postgres") -> str:
    """Convert asyncpg URL to psycopg2 URL, optionally with different database."""
    url = settings.database_url
    url = re.sub(r"postgresql\+asyncpg://", "postgresql://", url)
    url = re.sub(r"/[^/]+$", f"/{db_name}", url)
    return url


def ensure_database_exists() -> None:
    """Create vectriva database if it does not exist."""
    conn = psycopg2.connect(_get_psycopg2_url("postgres"))
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = 'vectriva'")
    if not cur.fetchone():
        cur.execute("CREATE DATABASE vectriva")
        print("Created database 'vectriva'")
    cur.close()
    conn.close()


async def verify_connection() -> None:
    """Verify connection to vectriva database."""
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        result = await conn.execute(text("SELECT version()"))
        version = result.scalar()
        print(f"Database connection successful: {version}")
    await engine.dispose()


async def init_db() -> None:
    """Initialize database."""
    ensure_database_exists()
    await verify_connection()


if __name__ == "__main__":
    asyncio.run(init_db())
