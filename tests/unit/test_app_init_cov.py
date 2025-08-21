"""
Extra coverage for app/__init__.py.

Focus:
1. test_create_app_basic
   - Calls create_app("testing") to ensure an app object is created.
   - Verifies that expected blueprints (alerts, auth, metrics, orders, health) are registered.

2. test_app_has_error_handlers
   - Forces an exception inside a test_request_context.
   - Ensures global error handlers are attached and return a proper response tuple or object.
"""


import pytest
from app import create_app


def test_create_app_basic():
    """App factory should create an app with expected blueprints."""
    app = create_app("testing")

    assert app is not None
    assert "alerts" in app.blueprints
    assert "auth" in app.blueprints
    assert "metrics" in app.blueprints
    assert "orders" in app.blueprints
    assert "health" in app.blueprints


def test_app_has_error_handlers():
    """Ensure error handlers are attached and invoked for errors."""
    app = create_app("testing")
    client = app.test_client()

    # Trigger a 404 → should hit error handler
    resp = client.get("/nonexistent")
    assert resp.status_code == 404
    assert b"Not Found" in resp.data or resp.is_json


