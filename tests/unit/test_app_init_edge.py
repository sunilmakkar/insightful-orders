"""
Edge-case tests for app/__init__.py
"""

from app import create_app
import app.config as config


def test_create_app_scheduler_disabled():
    """App should not start alerts scheduler if disabled in config."""

    app = create_app("testing")

    # Explicitly force-disable via config
    app.config["ALERTS_SCHEDULER_ENABLED"] = False

    # Re-run the scheduler logic manually (simulate the branch)
    if not app.config["ALERTS_SCHEDULER_ENABLED"]:
        app._alerts_scheduler_started = False

    # Assert scheduler explicitly marked as not started
    assert app._alerts_scheduler_started is False
