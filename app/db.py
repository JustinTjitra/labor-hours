"""asyncpg connection pool + thin query helpers, shared by the API and workers."""
from __future__ import annotations

import asyncpg

from .config import settings

_pool: asyncpg.Pool | None = None


def _dsn() -> str:
    # Some hosts (Render, Heroku) hand out postgres://; asyncpg wants postgresql://.
    return settings.database_url.replace("postgres://", "postgresql://", 1)


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(dsn=_dsn(), min_size=1, max_size=10)
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def fetch(query: str, *args) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *args)
        return [dict(r) for r in rows]


async def fetchrow(query: str, *args) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, *args)
        return dict(row) if row else None


async def execute(query: str, *args) -> str:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.execute(query, *args)
