"""
Tests for alerts_socket WebSocket handler in alerts.py.

Coverage focus:
1. test_alerts_socket_closes_without_token
   - Simulates a WebSocket handshake without providing a JWT token.
   - Expects the socket to close immediately.

2. test_alerts_socket_handles_exception
   - Replaces Redis pubsub with a dummy that raises an exception on listen().
   - Ensures alerts_socket catches the exception and exits gracefully.
"""

import app.blueprints.alerts as alerts


# ----------------------------------------------------------------------
# Actual tests
# ----------------------------------------------------------------------
def test_alerts_socket_closes_without_token(monkeypatch):
    """WebSocket should close if no token is provided."""
    alerts_socket_func = alerts.alerts_socket

    # ✅ Fake request.args so Flask request context isn’t required
    monkeypatch.setattr(alerts, "request", type("R", (), {"args": {}})())

    class DummyWS:
        def __init__(self):
            self.closed = False
        def close(self): self.closed = True
        def send(self, msg): raise AssertionError("send() should not be called")

    ws = DummyWS()
    alerts_socket_func(ws)
    assert ws.closed is True


def test_alerts_socket_handles_exception(monkeypatch):
    """WebSocket should handle exceptions during pubsub listen."""
    alerts_socket_func = alerts.alerts_socket

    # ✅ Fake request.args with a token so decode_token runs
    monkeypatch.setattr(alerts, "request", type("R", (), {"args": {"token": "fake"}})())

    # Patch decode_token → return a dummy merchant_id
    monkeypatch.setattr(
        "flask_jwt_extended.decode_token",
        lambda token: {"merchant_id": "m1"},
    )

    class DummyWS:
        def __init__(self):
            self.sent = []
            self.closed = False
        def send(self, msg): self.sent.append(msg)
        def close(self): self.closed = True

    class DummyPubSub:
        def subscribe(self, channel): pass   # ✅ needed
        def listen(self): raise RuntimeError("boom")
        def unsubscribe(self, channel): pass
        def close(self): pass

    class DummyRedisClient:
        def __init__(self):
            self.client = self   # ✅ mimic real structure
        def pubsub(self): return DummyPubSub()

    monkeypatch.setattr(alerts, "redis_client", DummyRedisClient())

    ws = DummyWS()
    alerts_socket_func(ws)   # should not crash
    assert ws.closed is True or ws.sent == []
