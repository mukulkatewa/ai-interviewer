"""Postgres access: one asyncpg pool per process (projectprep.md, D15).

asyncpg exchanges jsonb columns as JSON *strings*, which suits us: we write
`model.model_dump_json()` and read with `Model.model_validate_json()`, letting
Pydantic's fast parser do the work in both directions.
"""

from typing import Annotated

import asyncpg
from fastapi import Depends
from starlette.requests import HTTPConnection


async def create_pool(dsn: str, max_size: int) -> asyncpg.Pool:
    return await asyncpg.create_pool(
        dsn,
        min_size=1,
        max_size=max_size,
        # A stuck query fails fast instead of holding one of our few connections.
        command_timeout=10,
    )


def get_pool(conn: HTTPConnection) -> asyncpg.Pool:
    # Created once in the app lifespan (app/main.py). HTTPConnection, not
    # Request, so WebSocket routes can depend on it too.
    return conn.app.state.pool


Db = Annotated[asyncpg.Pool, Depends(get_pool)]
