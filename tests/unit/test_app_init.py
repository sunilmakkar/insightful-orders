"""
App factory tests for Insightful-Orders.

Covers:
    - Successful app initialization with testing config
    - Core extension registration (db, migrate, marshmallow, smorest, sock)
    - Behavior when invalid config key is provided

Functions under test:
    create_app(config_name)

Notes:
    - Focuses on app factory wiring, not routes.
    - Verifies that expected extensions are attached to the Flask app.
"""

from app import create_app


# ----------------------------------------------------------------------
# App Initialization
# ----------------------------------------------------------------------
def test_create_app_initializes():
    """create_app('testing') should return a Flask app with extensions registered."""
    app = create_app("testing")
    assert app is not None

    # Assert core extensions were registered
    assert "sqlalchemy" in app.extensions
    assert "migrate" in app.extensions
    assert "flask-marshmallow" in app.extensions
    assert "flask-smorest" in app.extensions
    assert "flask-jwt-extended" in app.extensions

    # Assert alerts blueprint (with sock routes) was registered
    assert "alerts" in app.blueprints


# ----------------------------------------------------------------------
# Invalid Config
# ----------------------------------------------------------------------
def test_create_app_with_invalid_config_key():
    """
    create_app with a nonexistent config should still return a valid app.
    (Note: get_config currently defaults instead of raising an exception.)
    """
    app = create_app("nonexistent_config")
    assert app is not None
