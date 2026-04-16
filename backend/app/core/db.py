from collections.abc import AsyncIterator

import asyncpg

from app.core.config import get_settings
from app.core.errors import AppError

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    settings = get_settings()
    if settings.database_url is None:
        raise AppError("DATABASE_URL is not configured.", details={"setting": "DATABASE_URL"})
    if _pool is None:
        try:
            _pool = await asyncpg.create_pool(
                dsn=settings.database_url,
                min_size=1,
                max_size=10,
            )
        except (asyncpg.PostgresError, OSError, ValueError) as exc:
            raise AppError(
                (
                    "Could not connect to Postgres. "
                    "Check DATABASE_URL and prefer the Supabase session pooler "
                    "connection string for IPv4-only environments."
                ),
                details={"setting": "DATABASE_URL"},
            ) from exc
    return _pool


async def get_connection() -> AsyncIterator[asyncpg.Connection]:
    pool = await get_pool()
    async with pool.acquire() as connection:
        yield connection
