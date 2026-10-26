"""Token verification with a locally generated ES256 key pair (no network)."""

import time
import uuid
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import AuthUser, get_jwks_client
from app.config import get_settings

PRIVATE_KEY = ec.generate_private_key(ec.SECP256R1())
OTHER_KEY = ec.generate_private_key(ec.SECP256R1())
USER_ID = uuid.uuid4()

app = FastAPI()


@app.get("/me")
def me(user: AuthUser):
    return user


class FakeJWKS:
    """Always hands back our test public key, like a JWKS with one key."""

    def get_signing_key_from_jwt(self, token):
        jwt.get_unverified_header(token)  # malformed tokens fail here, like the real client
        return SimpleNamespace(key=PRIVATE_KEY.public_key())


@pytest.fixture
def client():
    app.dependency_overrides[get_jwks_client] = FakeJWKS
    yield TestClient(app)
    app.dependency_overrides.clear()


def token(key=PRIVATE_KEY, alg="ES256", **overrides) -> str:
    claims = {
        "sub": str(USER_ID),
        "email": "asha@example.com",
        "aud": "authenticated",
        "iss": get_settings().jwt_issuer,
        "exp": int(time.time()) + 3600,
        **overrides,
    }
    return jwt.encode(claims, key, algorithm=alg)


def get_me(client, tok: str | None):
    headers = {"Authorization": f"Bearer {tok}"} if tok else {}
    return client.get("/me", headers=headers)


def test_valid_token_returns_user(client):
    resp = get_me(client, token())
    assert resp.status_code == 200
    assert resp.json() == {"id": str(USER_ID), "email": "asha@example.com"}


@pytest.mark.parametrize(
    "bad_token",
    [
        pytest.param(token(exp=int(time.time()) - 10), id="expired"),
        pytest.param(token(aud="anon"), id="wrong-audience"),
        pytest.param(token(iss="https://evil.example/auth/v1"), id="wrong-issuer"),
        pytest.param(token(key=OTHER_KEY), id="signed-by-other-key"),
        pytest.param(token(key="x" * 32, alg="HS256"), id="algorithm-swap"),
        pytest.param("not.a.jwt", id="garbage"),
    ],
)
def test_invalid_tokens_are_401(client, bad_token):
    resp = get_me(client, bad_token)
    assert resp.status_code == 401
    assert resp.headers["WWW-Authenticate"] == "Bearer"


def test_missing_header_is_401(client):
    assert get_me(client, None).status_code == 401
