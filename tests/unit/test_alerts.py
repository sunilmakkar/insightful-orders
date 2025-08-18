"""
Unit tests for the alerts service (app.services.alerts).

Covers:
    - Core predicate for rule triggering across operators.
    - Publishing behavior for a single metric evaluation.
    - Batch evaluation via the scheduler with result caching.
    - Skipping of unknown/unsupported metrics.

Notes:
    - Uses monkeypatch to isolate db.session and Redis publish.
    - Channel helper is overridden to a stable test format.
"""

import json
from decimal import Decimal

import pytest

# Module under test
import app.services.alerts as alerts_mod
from app.models import AlertRule


# ----------------------------------------------------------------------
# Test Doubles / Helpers
# ----------------------------------------------------------------------
class _PublishSpy:
    """Spy for redis_client.client.publish(channel, payload)."""
    def __init__(self):
        self.calls = []

    def __call__(self, channel, payload):
        self.calls.append((channel, payload))
        # return number of subscribers (not used)
        return 1


class _QueryStub:
    """
    Minimal stub to satisfy:
        db.session.query(Model)...
        .filter_by(...).all()
        .filter(...).scalar()
        .order_by(...).all()
    Instantiate with canned responses keyed by Model class.
    """
    def __init__(self, model_to_rows=None, scalar_value=None):
        self.model_to_rows = model_to_rows or {}
        self._scalar_value = scalar_value

    # SQLAlchemy calls session.query(Model) and returns a Query-ish object.
    def __call__(self, model):
        self._current_model = model
        return self

    def filter_by(self, **kwargs):
        # ignore filters here; unit tests supply exact rows they want
        return self

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return list(self.model_to_rows.get(self._current_model, []))

    def scalar(self):
        return self._scalar_value


class _SessionStub:
    """Holds the .query callable required by the code under test."""
    def __init__(self, query_callable):
        self.query = query_callable


@pytest.fixture(autouse=True)
def _isolation(monkeypatch):
    """
    Provide an isolated db.session and Redis publish for each test.
    Restores originals automatically via monkeypatch.
    """
    # Stub db.session
    query = _QueryStub()
    session = _SessionStub(query_callable=query)
    monkeypatch.setattr(alerts_mod.db, "session", session, raising=True)

    # Spy on Redis publish
    spy = _PublishSpy()
    # make sure redis_client.client exists even if not init'd
    class _RedisClientInner:
        publish = staticmethod(spy)
    class _RedisClientWrapper:
        client = _RedisClientInner()
    monkeypatch.setattr(alerts_mod.redis_client, "client", _RedisClientInner(), raising=True)

    # Default channel helper -> standardized format used in your app
    monkeypatch.setattr(
        alerts_mod, "alerts_channel_for_merchant",
        lambda mid: f"alerts:merchant:{int(mid)}",
        raising=True
    )

    yield
    # (monkeypatch auto-restores)


# ----------------------------------------------------------------------
# Core Predicate: _is_rule_triggered
# ----------------------------------------------------------------------
@pytest.mark.parametrize(
    "operator,threshold,value,expect",
    [
        (">",  10, 11, True),
        (">",  10,  9, False),
        (">=", 10, 10, True),
        ("<",  10,  9, True),
        ("<",  10, 11, False),
        ("<=", 10, 10, True),
        ("==", 10, 10, True),
        ("!=", 10,  9, True),
        ("!=", 10, 10, False),
    ]
)
def test__is_rule_triggered(operator, threshold, value, expect):
    """Evaluate the rule-trigger predicate across operators and values."""
    r = AlertRule(
        merchant_id=2,
        metric="orders_per_min",
        operator=operator,
        threshold=Decimal(str(threshold)),
        time_window_s=60,
        is_active=True,
    )
    assert alerts_mod._is_rule_triggered(r, float(value)) is expect


# ----------------------------------------------------------------------
# evaluate_alerts_for_metric — Publish Behavior
# ----------------------------------------------------------------------
def test_evaluate_alerts_for_metric_publishes_when_triggered(monkeypatch):
    """Publishes to Redis when the metric value satisfies the rule."""
    # Arrange: one active rule: value (6) > threshold (5) -> should publish
    rule = AlertRule(
        merchant_id=2,
        metric="orders_per_min",
        operator=">",
        threshold=Decimal("5"),
        time_window_s=60,
        is_active=True,
    )
    rule.id = 123    # make id stable for assertions

    # Configure the db.session stub to return our single rule for AlertRule
    alerts_mod.db.session.query.model_to_rows = {AlertRule: [rule]}

    # Spy on publish (installed by fixture)
    pubspy = _PublishSpy()
    class _RC: publish = staticmethod(pubspy)

    monkeypatch.setattr(alerts_mod.redis_client, "client", _RC(), raising=True)

    # Act
    alerts_mod.evaluate_alerts_for_metric(merchant_id=2, metric="orders_per_min", value=6.0)

    # Assert
    assert len(pubspy.calls) == 1
    channel, payload = pubspy.calls[0]
    assert channel == "alerts:merchant:2"
    data = json.loads(payload)
    assert data["rule_id"] == int(rule.id)  # id might be None for transient object -> int(None) raises
    assert data["merchant_id"] == 2
    assert data["metric"] == "orders_per_min"
    assert data["operator"] == ">"
    assert data["threshold"] == 5.0
    assert data["value"] == 6.0
    assert "triggered_at" in data
    assert "message" in data


# ----------------------------------------------------------------------
# evaluate_alerts_for_metric — Not Publish Behavior
# ----------------------------------------------------------------------
def test_evaluate_alerts_for_metric_no_publish_when_not_triggered(monkeypatch):
    """Does not publish when the metric value does not satisfy the rule."""
    # Arrange: threshold 10, value 7 -> should NOT publish
    rule = AlertRule(
        merchant_id=2,
        metric="orders_per_min",
        operator=">",
        threshold=Decimal("10"),
        time_window_s=60,
        is_active=True,
    )
    alerts_mod.db.session.query.model_to_rows = {AlertRule: [rule]}

    pubspy = _PublishSpy()

    class _RC: publish = staticmethod(pubspy)

    monkeypatch.setattr(alerts_mod.redis_client, "client", _RC(), raising=True)

    # Act
    alerts_mod.evaluate_alerts_for_metric(merchant_id=2, metric="orders_per_min", value=7.0)

    # Assert
    assert pubspy.calls == []


# ----------------------------------------------------------------------
# evaluate_rules — Scheduler Batch Behavior
# ----------------------------------------------------------------------
def test_evaluate_rules_uses_cache_and_counts_matches(monkeypatch):
    """
    Two rules share the same (merchant, metric, window); the metric function
    should be invoked only once. Expect 1 match (6>4) and 1 non-match (6>10).
    """
    r1 = AlertRule(
        merchant_id=2, metric="orders_per_min",
        operator=">", threshold=Decimal("4"),
        time_window_s=60, is_active=True,
    )
    r2 = AlertRule(
        merchant_id=2, metric="orders_per_min",
        operator=">", threshold=Decimal("10"),
        time_window_s=60, is_active=True,
    )
    alerts_mod.db.session.query.model_to_rows = {AlertRule: [r1, r2]}

    # Count how many times the metric fn is called
    calls = {"orders_per_min": 0}

    def fake_metric_fn(session, merchant_id, window_s):
        calls["orders_per_min"] += 1
        return 6.0  # value to compare against thresholds

    # Swap in a controlled metric function map
    monkeypatch.setattr(alerts_mod, "_METRIC_FUNCS", {"orders_per_min": fake_metric_fn}, raising=True)

    # Spy on publish to count matches (expect 1 match: 6>4 yes, 6>10 no)
    published = {"count": 0}
    def fake_publish(rule, value):
        published["count"] += 1
    monkeypatch.setattr(alerts_mod, "_publish_alert", fake_publish, raising=True)

    # Act
    result = alerts_mod.evaluate_rules()

    # Assert
    assert result == {"evaluated": 2, "matched": 1}
    assert calls["orders_per_min"] == 1  # cached result reused


# ----------------------------------------------------------------------
# evaluate_alerts_for_metric — Empty Metric
# ----------------------------------------------------------------------
def test_evaluate_rules_skips_unknown_metric(monkeypatch):
    """Skips rules whose metric is not present in _METRIC_FUNCS."""
    # Rule with metric not present in _METRIC_FUNCS -> should be skipped
    r = AlertRule(
        merchant_id=2, metric="unknown_metric",
        operator=">", threshold=Decimal("1"),
        time_window_s=60, is_active=True,
    )
    alerts_mod.db.session.query.model_to_rows = {AlertRule: [r]}

    # Ensure no publish occurs
    monkeypatch.setattr(alerts_mod, "_publish_alert", lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not publish")), raising=True)

    # Act
    result = alerts_mod.evaluate_rules()

    # Assert
    assert result == {"evaluated": 1, "matched": 0}
