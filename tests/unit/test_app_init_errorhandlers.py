"""
Extra coverage for app/__init__.py error handlers.

Focus:
- Ensures the 404 handler returns JSON with the expected structure.
- Ensures the 500 handler returns JSON when an unhandled exception occurs.
"""

from app import create_app


def test_404_error_handler_returns_json():
    """Requesting a nonexistent route should trigger our 404 JSON error handler."""
    app = create_app("testing")
    client = app.test_client()

    resp = client.get("/this-route-does-not-exist")
    assert resp.status_code == 404
    data = resp.get_json()
    assert data is not None
    # match your app’s actual schema
    assert "code" in data and data["code"] == 404
    assert "status" in data and "Not Found" in data["status"]


def test_500_error_handler_returns_json():
    """Forcing a 500 should trigger our 500 JSON error handler."""
    app = create_app("testing")
    app.config["TESTING"] = True
    app.config["PROPAGATE_EXCEPTIONS"] = False  # let Flask invoke the error handler

    @app.route("/boom")
    def boom():
        raise RuntimeError("forced crash")

    client = app.test_client()
    resp = client.get("/boom")
    assert resp.status_code == 500
    data = resp.get_json()
    assert data is not None
    assert "code" in data and data["code"] == 500
    assert "status" in data and "Internal Server Error" in data["status"]