"""
Alert evaluation and publishing logic for Insightful-Orders.

Responsibilities:
    - Define and evaluate alert rules for merchants based on order metrics.
    - Publish alert events to Redis channels for consumption via WebSockets.
    - Provide helper functions used by the scheduler and alert blueprint.

Workflow:
    1. Scheduler triggers evaluate_rules() every interval (e.g., 15s).
    2. Rules are evaluated against recent order data (e.g., orders per min, AOV).
    3. Matching rules are published to Redis channels using merchant-specific keys.
"""

from app.extensions import db, redis_client
from app.models import AlertRule
from app.utils.helpers import alerts_channel_for_merchant
from datetime import datetime
import json


def evaluate_alerts_for_metric(merchant_id: int, metric: str, value: float) -> None:
    """
    Check all active alert rules for a merchant & metric against a given value.
    If triggered, publish alert to merhchant's WebSocket channel via Redis.

    Args:
        merchant_id: Merchant to check alerts for.
        metric: Metric name (e.g., 'aov', 'orders_count').
        value: Current metric value to compare
    
    Returns:
        None.
    """
    # Fetch all active alert rules for this metric
    rules = (
        db.session.query(AlertRule)
        .filter_by(merchant_id=merchant_id, metric=metric, is_active=True)
        .all()
    )

    for rule in rules:
        if _is_rule_triggered(rule, value):
            _publish_alert(rule, value)

def _is_rule_triggered(rule: AlertRule, value: float) -> bool:
    """
    Check if a given value violates this alert rule's threshold condition.
    """
    if rule.operator == ">":
        return value > rule.threshold
    elif rule.operator == "<":
        return value < rule.threshold
    elif rule.operator == ">=":
        return value >= rule.threshold
    elif rule.operator == "<=":
        return value <= rule.threshold
    elif rule.operator == "==":
        return value == rule.threshold
    elif rule.operator == "!=":
        return value != rule.threshold
    return False

def _publish_alert(rule: AlertRule, value: float) -> None:
     """
    Publish an alert event to the Redis channel for the merchant.

    Args:
        merchant_id (int): Merchant ID associated with the alert.
        rule (AlertRule): The rule that triggered.
        value (float): The computed metric value that triggered the alert.
    """
     payload = {
        "rule_id": int(rule.id),
        "merchant_id": int(rule.merchant_id),
        "metric": str(rule.metric),
        "operator": str(rule.operator),
        "threshold": float(rule.threshold),
        "value": float(value),
        "time_window_s": int(rule.time_window_s),
        "triggered_at": datetime.utcnow().isoformat(),
        "message": f"{rule.metric} {rule.operator} {rule.threshold} over last {rule.time_window_s}s (value={value:.3f})",
    }

     redis_client.client.publish(
        alerts_channel_for_merchant(rule.merchant_id),
        json.dumps(payload)
    )


# These imports are safe to keep near the bottom to avoid cycles.
from datetime import timedelta
from sqlalchemy import func
from app.models import Order

def _now_utc_s():
    """UTC now truncated to seconds (stable timestamps)."""
    return datetime.utcnow().replace(microsecond=0)

def _window_bounds_s(window_s: int):
    """Return (start, end) UTC datetimes for a trailing window in seconds."""
    end = _now_utc_s()
    start = end - timedelta(seconds=int(window_s))
    return start, end

def _compute_orders_per_min(session, merchant_id: int, window_s: int) -> float:
    """Count orders in window / minutes (supports sub-minute windows)."""
    start, end = _window_bounds_s(window_s)
    count = (
        session.query(func.count(Order.id))
        .filter(
            Order.merchant_id == merchant_id,
            Order.created_at >= start,
            Order.created_at <= end,
        )
        .scalar()
    ) or 0
    minutes = max(window_s / 60.0, 1e-9)  # avoid divide-by-zero
    return float(count) / minutes

def _compute_aov_window(session, merchant_id: int, window_s: int) -> float:
    """Average order value within the trailing window (0.0 if none)."""
    start, end = _window_bounds_s(window_s)
    avg_val = (
        session.query(func.avg(Order.total_amount))
        .filter(
            Order.merchant_id == merchant_id,
            Order.created_at >= start,
            Order.created_at <= end,
        )
        .scalar()
    )
    return float(avg_val) if avg_val is not None else 0.0

# Map rule.metric -> function
_METRIC_FUNCS = {
    "orders_per_min": _compute_orders_per_min,
    "aov_window": _compute_aov_window,
}

def evaluate_rules() -> dict:
    """
    Batch evaluator run by the scheduler:
      - Loads all active AlertRule rows
      - Groups by (merchant_id, metric, time_window_s)
      - Computes each metric once
      - Compares against thresholds and publishes alerts when matched

    Returns:
        {"evaluated": <int>, "matched": <int>}
    """
    session = db.session
    rules = (
        session.query(AlertRule)
        .filter(AlertRule.is_active.is_(True))
        .order_by(AlertRule.merchant_id.asc())
        .all()
    )

    evaluated = matched = 0
    # Cache computed metric values so we don’t repeat the same query
    cache = {}  # key: (merchant_id, metric, window_s) -> float

    for r in rules:
        key = (int(r.merchant_id), str(r.metric), int(r.time_window_s))
        if key not in cache:
            fn = _METRIC_FUNCS.get(r.metric)
            # Unknown metric names simply get skipped
            cache[key] = fn(session, r.merchant_id, r.time_window_s) if fn else None

        value = cache[key]
        evaluated += 1

        if value is None:
            # No calculator for this metric; skip quietly
            continue

        # Reuse your existing trigger + publish path
        if _is_rule_triggered(r, float(value)):
            _publish_alert(r, float(value))
            matched += 1

    return {"evaluated": evaluated, "matched": matched}
