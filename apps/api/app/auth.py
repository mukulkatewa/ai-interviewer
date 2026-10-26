"""Who is calling? Verify the Supabase login token locally (projectprep.md, D16)."""

from functools import lru_cache
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.config import get_settings

# Pinned, never read from the token: trusting the token's own "alg" header is
# how algorithm-confusion attacks (e.g. "alg": "none") get in.
ALGORITHMS = ["ES256"]
AUDIENCE = "authenticated"

# auto_error=False so a missing header gives our 401 (with WWW-Authenticate),
# not FastAPI's default 403.
_bearer = HTTPBearer(auto_error=False)


class CurrentUser(BaseModel):
    id: UUID
    email: str | None = None


@lru_cache
def get_jwks_client() -> jwt.PyJWKClient:
    # Downloads the public keys on first use and caches them. An unknown key id
    # (Supabase rotated keys) triggers one refetch, so rotation needs no restart.
    return jwt.PyJWKClient(get_settings().jwks_url, cache_keys=True)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(401, detail, headers={"WWW-Authenticate": "Bearer"})


def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    jwks: Annotated[jwt.PyJWKClient, Depends(get_jwks_client)],
) -> CurrentUser:
    # A plain `def` on purpose: FastAPI runs it in a worker thread, so the rare
    # blocking JWKS fetch never stalls the event loop. Verification itself is ~0.1 ms.
    if creds is None:
        raise _unauthorized("Not logged in")
    try:
        key = jwks.get_signing_key_from_jwt(creds.credentials)
        claims = jwt.decode(
            creds.credentials,
            key.key,
            algorithms=ALGORITHMS,
            audience=AUDIENCE,
            issuer=get_settings().jwt_issuer,
            options={"require": ["exp", "sub", "aud", "iss"]},
        )
    except jwt.PyJWKClientConnectionError as e:
        # Our problem (can't reach Supabase), not the caller's: don't say "bad token".
        raise HTTPException(503, "Auth temporarily unavailable") from e
    except jwt.PyJWTError as e:
        raise _unauthorized("Invalid or expired token") from e

    return CurrentUser(id=claims["sub"], email=claims.get("email"))


AuthUser = Annotated[CurrentUser, Depends(get_current_user)]
