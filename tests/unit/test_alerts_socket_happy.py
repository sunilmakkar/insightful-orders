"""
Extra coverage for alerts_socket in alerts.py.

Focus:
1. test_alerts_socket_happy_path
   - Mocks request.args with a valid token and patches decode_token → merchant_id.
   - Provides a DummyPubSub that yields one message.
   - Asserts that the WebSocket receives the forwarded JSON message.
"""
# tests/unit/test_alerts_socket_happy.py

import app.blueprints.alerts as alerts


def test_alerts_socket_happy_path(monkeypatch):
    """WebSocket should forward messages from Redis pubsub to client."""

    # Fake request.args with a token
    monkeypatch.setattr(alerts, "request", type("R", (), {"args": {"token": "fake"}})())

    # Patch decode_token → return merchant_id
    monkeypatch.setattr(
        "flask_jwt_extended.decode_token",
        lambda token: {"merchant_id": "m1"},
    )

    # Dummy WS
    class DummyWS:
        def __init__(self):
            self.sent = []
            self.closed = False
        def send(self, msg): self.sent.append(msg)
        def close(self): self.closed = True

    # Dummy PubSub that yields one message then stops
    class DummyPubSub:
        def __init__(self):
            self.subscribed = False
        def subscribe(self, channel): self.subscribed = True
        def listen(self):
            yield {"type": "message", "data": b'{"hello":"world"}'}
            return
        def unsubscribe(self, channel): pass
        def close(self): pass

    # Dummy Redis
    class DummyRedisClient:
        def __init__(self): self.client = self
        def pubsub(self): return DummyPubSub()

    monkeypatch.setattr(alerts, "redis_client", DummyRedisClient())

    ws = DummyWS()
    alerts.alerts_socket(ws)

    # ✅ ws got the forwarded message
    assert ws.sent
    assert '{"hello":"world"}' in ws.sent[0]
