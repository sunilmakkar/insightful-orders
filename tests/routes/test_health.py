"""
Unit tests for the health check blueprint.

Covers:
    - The `/healthz` endpoint is publicly accessible.
    - Returns HTTP 200 OK.
    - Returns the expected JSON payload {"status": "ok"}.
"""

def test_health_check(client):
    """GET /healthz should return 200 and JSON {"status": "ok"}"""
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}