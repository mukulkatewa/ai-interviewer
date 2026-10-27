"""Per-user daily limits (projectprep.md 5.13, D12, D32).

Counted from the user's own rows in the last 24 hours, using the existing
(user_id, created_at) indexes. Checked before any LLM spend. Two simultaneous
requests can both pass the check and exceed the limit by one; at these
limits that's harmless, and it saves a lock per request.
"""

import math
from typing import Literal
from uuid import UUID

import asyncpg
from fastapi import HTTPException

Resource = Literal["resumes", "analyses", "interviews"]

# Table names come from this fixed mapping, never from request input.
_LABELS: dict[Resource, str] = {
    "resumes": "resume uploads",
    "analyses": "job match reports",
    "interviews": "mock interviews",
}


async def enforce(db: asyncpg.Pool, user_id: UUID, resource: Resource, limit: int) -> None:
    """Raise 429 with Retry-After if the user already did `limit` of these in 24 h."""
    row = await db.fetchrow(
        f"""
        select count(*) as used,
               extract(epoch from min(created_at) + interval '24 hours' - now()) as wait_s
        from {resource}
        where user_id = $1 and created_at > now() - interval '24 hours'
        """,
        user_id,
    )
    if row["used"] < limit:
        return
    # A slot frees up when the oldest action in the window turns 24 hours old.
    wait_s = max(1, math.ceil(row["wait_s"]))
    hours = math.ceil(wait_s / 3600)
    raise HTTPException(
        429,
        f"You've reached today's limit of {limit} {_LABELS[resource]}. "
        f"Try again in about {hours} hour{'s' if hours > 1 else ''}.",
        headers={"Retry-After": str(wait_s)},
    )
