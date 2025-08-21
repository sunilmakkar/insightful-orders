"""
Covers the scheduler startup branch in app/__init__.py.
"""

from app import create_app

def test_scheduler_starts(monkeypatch):
    app = create_app("development")
    # Scheduler should register unless explicitly disabled
    assert "alerts_scheduler" in app.extensions
    assert getattr(app, "_alerts_scheduler_started", False)