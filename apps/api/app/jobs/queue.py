"""A durable job queue on Postgres (projectprep.md 5.12, D31).

Claiming uses SELECT ... FOR UPDATE SKIP LOCKED, so any number of workers can
poll the same table without ever taking the same job twice.
"""

import json
from typing import Any
from uuid import UUID

import asyncpg
from pydantic import BaseModel

MAX_ATTEMPTS = 3
STALE_AFTER_S = 300  # a job "running" this long belonged to a worker that died


class Job(BaseModel):
    id: UUID
    kind: str
    payload: dict[str, Any]
    attempts: int


async def enqueue(conn: asyncpg.Connection | asyncpg.Pool, kind: str, payload: dict[str, Any]) -> None:
    """Pass the caller's transaction connection to enqueue atomically with other writes (outbox)."""
    await conn.execute("insert into jobs (kind, payload) values ($1, $2)", kind, json.dumps(payload))


async def claim(db: asyncpg.Pool) -> Job | None:
    row = await db.fetchrow(
        """
        update jobs set status = 'running', attempts = attempts + 1, updated_at = now()
        where id = (
            select id from jobs
            where status = 'queued' and run_after <= now()
            order by run_after
            for update skip locked
            limit 1
        )
        returning id, kind, payload, attempts
        """
    )
    if row is None:
        return None
    return Job(id=row["id"], kind=row["kind"], payload=json.loads(row["payload"]), attempts=row["attempts"])


async def complete(db: asyncpg.Pool, job_id: UUID) -> None:
    await db.execute("update jobs set status = 'done', updated_at = now() where id = $1", job_id)


async def retry_later(db: asyncpg.Pool, job_id: UUID, delay_s: float, error: str, *, count_attempt: bool = True) -> None:
    """Back to the queue after `delay_s`. A rate limit isn't the job's fault: it doesn't use up an attempt."""
    await db.execute(
        """
        update jobs set status = 'queued', run_after = now() + make_interval(secs => $2),
               last_error = $3, attempts = attempts - $4, updated_at = now()
        where id = $1
        """,
        job_id, delay_s, error[:1000], 0 if count_attempt else 1,
    )  # fmt: skip


async def fail(db: asyncpg.Pool, job_id: UUID, error: str) -> None:
    await db.execute(
        "update jobs set status = 'failed', last_error = $2, updated_at = now() where id = $1", job_id, error[:1000]
    )


async def requeue_stale(db: asyncpg.Pool) -> int:
    """Jobs stuck in 'running' (worker crashed or redeployed mid-job) go back to the queue."""
    status = await db.execute(
        """
        update jobs set status = 'queued', updated_at = now()
        where status = 'running' and updated_at < now() - make_interval(secs => $1)
        """,
        STALE_AFTER_S,
    )
    return int(status.split()[-1])
