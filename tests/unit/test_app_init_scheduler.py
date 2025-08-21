"""
Covers the scheduler startup branch in app/__init__.py.
"""

from app import create_app

def test_scheduler_skipped_in_testing():
    app = create_app("testing")
    # Scheduler should NOT register in testing config
    assert "alerts_scheduler" not in app.extensions
    assert not getattr(app, "_alerts_scheduler_started", False)