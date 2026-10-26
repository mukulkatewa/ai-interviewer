def preflight(client, origin: str):
    return client.options(
        "/resumes",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization",
        },
    )


def test_allowed_origin_passes_preflight(client):
    resp = preflight(client, "http://localhost:3000")
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_unknown_origin_is_refused(client):
    resp = preflight(client, "https://evil.example")
    assert "access-control-allow-origin" not in resp.headers
