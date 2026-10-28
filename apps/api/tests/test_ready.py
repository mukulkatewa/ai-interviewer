"""/health is liveness, /ready is "can we serve users" (database required, TTS reported only)."""

from app.main import app


class StubTTS:
    def __init__(self, up: bool):
        self.up = up

    async def healthy(self) -> bool:
        return self.up


def test_health_never_touches_the_database(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_ready_when_everything_is_up(client, monkeypatch):
    monkeypatch.setattr(app.state, "tts", StubTTS(True))
    assert client.get("/ready").json() == {"status": "ok", "database": "up", "tts": "up"}


def test_ready_stays_200_when_only_tts_is_down(client, monkeypatch):
    """Interviews fall back to browser voice (D26), so TTS being down must not take the site out of rotation."""
    monkeypatch.setattr(app.state, "tts", StubTTS(False))
    resp = client.get("/ready")
    assert resp.status_code == 200 and resp.json()["tts"] == "down"


def test_ready_is_503_when_the_database_is_unreachable(client, monkeypatch):
    class DeadPool:
        async def fetchval(self, *_):
            raise ConnectionError("db down")

        async def close(self):  # the app's shutdown closes whatever pool it holds
            pass

    monkeypatch.setattr(app.state, "pool", DeadPool())
    resp = client.get("/ready")
    assert resp.status_code == 503 and resp.json()["database"] == "down"
