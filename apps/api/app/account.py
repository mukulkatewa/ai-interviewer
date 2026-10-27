"""The user's own account data (projectprep.md 5.13, section 8)."""

from fastapi import APIRouter, Response

from app.auth import AuthUser
from app.db import Db

router = APIRouter(prefix="/me", tags=["account"])


@router.delete("/data", status_code=204)
async def delete_my_data(user: AuthUser, db: Db) -> Response:
    """Delete everything this user created. The Supabase login itself stays (section 8).

    Deleting resumes and job descriptions cascades through the composite FKs to
    analyses -> interviews -> turns and evaluations, so two deletes cover all of it.
    """
    async with db.acquire() as conn, conn.transaction():
        # Jobs have no user_id (D31); drop this user's pending work too.
        await conn.execute(
            "delete from jobs where payload->>'user_id' = $1 and status in ('queued', 'running')", str(user.id)
        )
        await conn.execute("delete from resumes where user_id = $1", user.id)
        await conn.execute("delete from job_descriptions where user_id = $1", user.id)
    return Response(status_code=204)
