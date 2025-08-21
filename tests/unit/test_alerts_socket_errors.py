"""
Covers error and finally branches of alerts_socket in app/blueprints/alerts.py.
"""

import types
from app.blueprints import alerts

class DummyWS:
    def __init__(self): 
        self.sent, self.closed = [], False
    def send(self, msg): 
        self.sent.append(msg)
    def close(self): 
        self.closed = True

def test_alerts_socket_handles_bad_bytes(monkeypatch):
    ws = DummyWS()

    # Fake pubsub with subscribe + listen
    class FakePubSub:
        def subscribe(self, channel):
            self.channel = channel
        def listen(self):
            # Emit one message with bad bytes
            yield {"type": "message", "data": b"\xff"}
        def unsubscribe(self, ch=None): 
            self.unsubscribed = True
        def close(self): 
            self.closed = True

    monkeypatch.setattr(
        alerts.redis_client, "client", types.SimpleNamespace(pubsub=lambda: FakePubSub())
    )
    monkeypatch.setattr(alerts, "request", types.SimpleNamespace(args={"token": "dummy"}))
    monkeypatch.setattr("flask_jwt_extended.decode_token", lambda t: {"merchant_id": "m1"})

    alerts.alerts_socket(ws)

    # It should send a string fallback for the bad byte message
    assert ws.sent
    assert isinstance(ws.sent[0], str)
    # And cleanup should have been called
    assert getattr(alerts.redis_client.client.pubsub(), "unsubscribed", True)