"""
Extra coverage for app/schemas.py.

Focus:
- Cover dump_only + default fields in UserSchema.
- Ensure AlertRuleSchema can dump core fields without error.
- Ensure OrderSchema's pre_dump hook works when given an object
  with a created_at datetime attribute.
"""

import datetime
from types import SimpleNamespace
from app import schemas


def test_user_schema_includes_debug_marker():
    """Dumping a UserSchema should include the debug_marker default."""
    user = {"id": 1, "email": "test@example.com"}
    result = schemas.UserSchema().dump(user)
    assert result.get("debug_marker") == "UserSchema_in_use"


def test_alert_rule_schema_dump_only():
    """AlertRuleSchema should dump without needing a session for load."""
    payload = {
        "id": 123,
        "metric": "orders_per_min",
        "operator": ">=",
        "threshold": 10.5,
        "time_window_s": 300,
        "is_active": True,
        "merchant_id": 1,
    }
    schema = schemas.AlertRuleSchema()
    dumped = schema.dump(payload)
    assert dumped["metric"] == "orders_per_min"
    assert dumped["merchant_id"] == 1


def test_order_schema_dump_with_object():
    """OrderSchema should dump cleanly when given an object with created_at."""
    order_obj = SimpleNamespace(
        id=42,
        merchant_id=1,
        created_at=datetime.datetime.utcnow(),
    )
    dumped = schemas.OrderSchema().dump(order_obj)
    assert dumped["id"] == 42
    assert dumped["merchant_id"] == 1
    assert "created_at" in dumped
