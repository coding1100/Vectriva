"""Redis client for caching and context storage."""

import json
from typing import Any

import redis.asyncio as redis

from .config import settings

redis_client = redis.from_url(settings.redis_url, decode_responses=True)


async def store_context(conversation_id: str, context_dict: dict[str, Any]) -> None:
    """Store agent context in Redis with TTL."""
    key = f"context:{conversation_id}"
    await redis_client.setex(
        key,
        settings.redis_context_ttl_seconds,
        json.dumps(context_dict),
    )


async def get_context(conversation_id: str) -> dict[str, Any] | None:
    """Retrieve agent context from Redis."""
    key = f"context:{conversation_id}"
    data = await redis_client.get(key)
    if data:
        return json.loads(data)
    return None


async def delete_context(conversation_id: str) -> None:
    """Delete agent context from Redis."""
    key = f"context:{conversation_id}"
    await redis_client.delete(key)
