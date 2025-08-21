"""
Covers dump-only defaults in schemas.
"""

from app.schemas import UserSchema

def test_user_schema_includes_debug_marker():
    dumped = UserSchema().dump({"id": 1, "email": "x@y.com"})
    assert "debug_marker" in dumped