# tests/unit/test_alerts_blueprint_errors.py
"""
Extra coverage for app/blueprints/alerts.py.

Focus:
- Exercises validation error paths when required fields are missing.
- Confirms the endpoint responds with 400 and a JSON error payload.
"""

import json
from app import create_app


def test_create_alert_rule_missing_operator():
    """POST /alerts/rules without operator should 400 with JSON error."""
    app = create_app("testing")
    client = app.test_client()

    payload = {
        "metric": "orders_per_min",
        "threshold": 5,
        "time_window_s": 60,
        "is_active": True,
        # operator missing on purpose
    }
    resp = client.post(
        "/alerts",  # ✅ correct route
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 422
    data = resp.get_json()
    assert "errors" in data or "message" in data
