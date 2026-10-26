"""Who is calling? Verify the Supabase login token locally (projectprep.md, D16).

HTTP routes get the token from the `Authorization` header; the interview
WebSocket gets it in its first message (browsers can't set headers on
WebSockets). Both go through `verify_token`.
"""

from collections.abc import Callable
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


class InvalidToken(Exception):
    """Missing, malformed, expired, or not signed by our Supabase project."""


class AuthUnavailable(Exception):
    """We couldn't fetch the signing keys. Our problem, not the caller's."""


TokenVerifier = Callable[[str], CurrentUser]


@lru_cache
def get_jwks_client() -> jwt.PyJWKClient:
    # Downloads the public keys on first use and caches them. An unknown key id
    # (Supabase rotated keys) triggers one refetch, so rotation needs no restart.
    return jwt.PyJWKClient(get_settings().jwks_url, cache_keys=True)


def verify_token(token: str, jwks: jwt.PyJWKClient) -> CurrentUser:
    """Blocking only on the rare JWKS fetch; call from a thread in async code."""
    try:
        key = jwks.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            key.key,
            algorithms=ALGORITHMS,
            audience=AUDIENCE,
            issuer=get_settings().jwt_issuer,
            options={"require": ["exp", "sub", "aud", "iss"]},
        )
    except jwt.PyJWKClientConnectionError as e:
        raise AuthUnavailable from e
    except jwt.PyJWTError as e:
        raise InvalidToken from e
    return CurrentUser(id=claims["sub"], email=claims.get("email"))


def get_token_verifier(jwks: Annotated[jwt.PyJWKClient, Depends(get_jwks_client)]) -> TokenVerifier:
    """A dependency, so tests can swap verification without minting real tokens."""
    return lambda token: verify_token(token, jwks)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(401, detail, headers={"WWW-Authenticate": "Bearer"})


def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    verify: Annotated[TokenVerifier, Depends(get_token_verifier)],
) -> CurrentUser:
    # A plain `def` on purpose: FastAPI runs it in a worker thread, so the rare
    # blocking JWKS fetch never stalls the event loop. Verification itself is ~0.1 ms.
    if creds is None:
        raise _unauthorized("Not logged in")
    try:
        return verify(creds.credentials)
    except AuthUnavailable as e:
        raise HTTPException(503, "Auth temporarily unavailable") from e
    except InvalidToken as e:
        raise _unauthorized("Invalid or expired token") from e


AuthUser = Annotated[CurrentUser, Depends(get_current_user)]
