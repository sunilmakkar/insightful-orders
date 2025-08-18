"""
Unit tests for alert service logic.

Covers:
    - _compute_orders_per_min
    - _compute_aov_window
"""

import pytest
from datetime import datetime, timedelta
from app.services import alerts
from app.models import Order


# ----------------------------------------------------------------------
# Helper: Insert orders into db_session
# ----------------------------------------------------------------------
def _insert_orders(db_session, merchant_id, orders):
    """Helper to bulk insert test orders."""
    for o in orders:
        db_session.add(
            Order(
                merchant_id=merchant_id,
                # CHANGED: use an explicit customer_id that exists in fixtures
                customer_id=o.get("customer_id", 1),
                total_amount=o["total_amount"],
                created_at=o["created_at"],
            )
        )
    db_session.commit()


# ----------------------------------------------------------------------
# Test: _compute_orders_per_min
# ----------------------------------------------------------------------
def test_compute_orders_per_min(db_session, app):
    """_compute_orders_per_min should count orders in the window."""
    now = datetime.utcnow()
    merchant_id = 1

    _insert_orders(
        db_session,
        merchant_id,
        [
            {"total_amount": 100, "created_at": now - timedelta(seconds=30)},
            {"total_amount": 200, "created_at": now - timedelta(seconds=90)},
        ],
    )

    count = alerts._compute_orders_per_min(db_session, merchant_id, window_s=60)
    assert count == 1


# ----------------------------------------------------------------------
# Test: _compute_aov_window
# ----------------------------------------------------------------------
def test_compute_aov_window(db_session, app):
    """_compute_aov_window should return average order value in window."""
    now = datetime.utcnow()
    merchant_id = 1

    _insert_orders(
        db_session,
        merchant_id,
        [
            {"total_amount": 100, "created_at": now - timedelta(seconds=30)},
            {"total_amount": 200, "created_at": now - timedelta(seconds=30)},
        ],
    )

    aov = alerts._compute_aov_window(db_session, merchant_id, window_s=60)
    assert aov == 150
