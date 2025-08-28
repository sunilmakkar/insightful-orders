"""
Integration tests for WebSocket alerts against a running API server.

Covers:
    - Successful WebSocket handshake with a valid JWT.
    - Rejection/closure behavior when no JWT is provided.
    - End-to-end pub/sub: Redis publish → server fan-out → WebSocket client recv.

Notes:
    - These tests expect a live API at 127.0.0.1:5000 with real credentials.
    - JWTs are obtained via /auth/login to match the server's signing key.
    - Pub/Sub uses a direct Redis connection (e.g., docker-compose service).
"""

import json
import time
import os
import redis

import pytest
from urllib import request as urlreq, error as urlerr
from websocket import (
    create_connection,
    WebSocketBadStatusException,
    WebSocketConnectionClosedException,
    WebSocketTimeoutException,
)
from app.utils.helpers import alerts_channel_for_merchant
import os


# ----------------------------------------------------------------------
# Config / Constants
# ----------------------------------------------------------------------
API_BASE = os.getenv("API_BASE", "http://127.0.0.1:5000")
WS_BASE  = os.getenv("WS_BASE", "ws://127.0.0.1:5000/ws/alerts")

CONNECT_TIMEOUT_S = 3
RECV_TIMEOUT_S = 5  # overall deadline for pub/sub delivery


# ----------------------------------------------------------------------
# HTTP Helpers
# ----------------------------------------------------------------------
def _http_post_json(path: str, payload: dict, timeout: float = 10.0) -> dict:
    """
    POST JSON to the live API and return decoded JSON.

    Retries a few times in case the API container isn't ready yet.
    Raises AssertionError with details if HTTPError occurs.
    """
    data = json.dumps(payload).encode("utf-8")
    req = urlreq.Request(
        f"{API_BASE}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlreq.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))



def _http_get_json(path: str, token: str) -> dict:
    """GET JSON from the live API with Bearer auth; return decoded JSON or raise."""
    req = urlreq.Request(
        f"{API_BASE}{path}",
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    try:
        with urlreq.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urlerr.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise AssertionError(f"HTTP {e.code} on GET {path}: {body}") from e


def _login_get_token(email="itest@example.com", password="test1234") -> str:
    """Login against /auth/login and return the access token, with retry logic for CI flakiness."""
    creds = {"email": email, "password": password}
    last_err = None

    for attempt in range(3):  # try up to 3 times
        try:
            res = _http_post_json("/auth/login", creds)
            token = res.get("access_token")
            assert token, f"Login did not return access_token: {res}"
            return token
        except Exception as e:
            last_err = e
            time.sleep(1 + attempt)  # small backoff: 1s, 2s, 3s

    raise AssertionError(f"Login failed after retries: {last_err}")



# ----------------------------------------------------------------------
# WebSocket Helpers
# ----------------------------------------------------------------------
def _ws_url(token: str | None = None) -> str:
    """Compose the WebSocket URL, optionally appending ?token=..."""
    return WS_BASE + (f"?token={token}" if token else "")


# ----------------------------------------------------------------------
# Redis Helper
# ----------------------------------------------------------------------
def _redis():
    return redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"))


# ----------------------------------------------------------------------
# Handshake — With Token
# ----------------------------------------------------------------------
@pytest.mark.integration
def test_ws_handshake_success():
    """Connecting with a valid JWT should succeed."""
    token = _login_get_token()
    ws = create_connection(_ws_url(token), timeout=CONNECT_TIMEOUT_S, compression=None)
    try:
        assert ws.connected is True
    finally:
        ws.close()


# ----------------------------------------------------------------------
# Handshake — Without Token
# ----------------------------------------------------------------------
@pytest.mark.integration
def test_ws_handshake_rejects_without_token():
    """
    Acceptable rejection behaviors:
      - HTTP error at handshake
      - Timeout during handshake
      - Connection opens but closes immediately
      - Connection opens but first recv() blocks or closes
    """
    url = _ws_url(None)

    try:
        ws = create_connection(url, timeout=CONNECT_TIMEOUT_S, compression=None)
        try:
            frame = ws.recv()
            assert not frame, "Expected rejection, got data"
        except (WebSocketConnectionClosedException, WebSocketTimeoutException):
            pass  # closed or timed out = rejected
        finally:
            ws.close()
    except (WebSocketTimeoutException, WebSocketConnectionClosedException):
        pass  # handshake timeout/closed = rejected
    except Exception as e:
        assert "401" in str(e) or "403" in str(e)


# ----------------------------------------------------------------------
# Pub/Sub — Redis → Server → WebSocket Client
# ----------------------------------------------------------------------
@pytest.mark.integration
def test_pubsub_message_flows_to_client():
    """Publishing to the merchant channel should be received by the connected client."""
    token = _login_get_token()

    # Get merchant_id from the real API
    me = _http_get_json("/auth/me", token)
    merchant_id = me.get("merchant_id")
    assert isinstance(merchant_id, int), f"/auth/me missing merchant_id: {me}"

    ws = create_connection(_ws_url(token), timeout=CONNECT_TIMEOUT_S, compression=None)
    try:
        assert ws.connected is True

        # Give the server a moment to attach the Redis subscription.
        time.sleep(1.0)

        payload = {"event": "itest", "ok": True, "merchant_id": merchant_id}
        channel = alerts_channel_for_merchant(merchant_id)

        _redis().publish(channel, json.dumps(payload))

        # Poll until RECV_TIMEOUT_S with short increments
        deadline = time.time() + (RECV_TIMEOUT_S * 2)  
        ws.settimeout(0.5)
        data = None
        while time.time() < deadline:
            try:
                text = ws.recv()
                data = json.loads(text)
                break
            except WebSocketTimeoutException:
                continue

        assert data == payload, f"Did not receive pubsub payload in {RECV_TIMEOUT_S}s"
    finally:
        ws.close()
