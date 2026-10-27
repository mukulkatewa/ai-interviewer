"""Runs queued jobs in the background of the API process (D31)."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import asyncpg

from app.jobs import queue
from app.llm import LLMBusyError

logger = logging.getLogger(__name__)

Handler = Callable[[dict[str, Any]], Awaitable[None]]
FailureHandler = Callable[[dict[str, Any], str], Awaitable[None]]

POLL_INTERVAL_S = 2.0
BACKOFF_S = 30.0  # x attempt number: 30 s, 60 s


class PermanentError(Exception):
    """Retrying can't help (e.g. the interview was deleted): fail now."""


class Worker:
    def __init__(self, db: asyncpg.Pool, handlers: dict[str, Handler], on_failed: dict[str, FailureHandler]):
        self.db = db
        self.handlers = handlers
        self.on_failed = on_failed  # called once a job has failed for good

    async def run_once(self) -> bool:
        """Claim and run one job. Returns False if the queue was empty."""
        job = await queue.claim(self.db)
        if job is None:
            return False
        try:
            await self.handlers[job.kind](job.payload)
        except LLMBusyError as e:
            # Free-tier rate limit: wait as long as the provider says; not an attempt (D22).
            await queue.retry_later(self.db, job.id, e.retry_after_s, str(e), count_attempt=False)
        except Exception as e:  # noqa: BLE001 - a job must never take the worker down
            permanent = isinstance(e, PermanentError) or job.attempts >= queue.MAX_ATTEMPTS
            logger.exception("Job %s (%s) failed, attempt %d", job.id, job.kind, job.attempts)
            if permanent:
                await queue.fail(self.db, job.id, repr(e))
                if job.kind in self.on_failed:
                    await self.on_failed[job.kind](job.payload, repr(e))
            else:
                await queue.retry_later(self.db, job.id, BACKOFF_S * job.attempts, repr(e))
        else:
            await queue.complete(self.db, job.id)
        return True

    async def run_forever(self) -> None:
        await queue.requeue_stale(self.db)
        while True:
            try:
                if not await self.run_once():
                    await asyncio.sleep(POLL_INTERVAL_S)
                    await queue.requeue_stale(self.db)
            except asyncio.CancelledError:
                raise  # app shutdown
            except Exception:  # noqa: BLE001 - e.g. the DB was briefly unreachable: keep polling
                logger.exception("Worker loop error")
                await asyncio.sleep(POLL_INTERVAL_S)
