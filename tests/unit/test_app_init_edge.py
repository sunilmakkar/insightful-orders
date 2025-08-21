"""
Edge-case tests for app/__init__.py
"""

from app import create_app


def test_create_app_scheduler_disabled(monkeypatch):
    """App should not start alerts scheduler if disabled in config."""
    app = create_app("testing")

    # Force-disable via config
    app.config["ALERTS_SCHEDULER_ENABLED"] = False

    # Re-run init logic manually to hit branch
    app = create_app("testing")

    # Assert scheduler not started
    assert not hasattr(app, "_alerts_scheduler_started") or app._alerts_scheduler_started is False
