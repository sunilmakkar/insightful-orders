"""
Unit tests for analytics: RFM scores.

Function under test:
    - app.services.analytics.rfm_scores

Covers:
    - Seeding sample orders across different R/F/M profiles via a fixture.
    - Returning a list of three customer records for the merchant.
    - Presence of all required fields on each record
      (customer_id, recency_days, frequency, monetary, r, f, m, rfm).

Notes:
    - Uses the `db_session` fixture from tests/conftest.py to write/read test rows.
    - Fixes `now` via the fixture return value to keep recency calculations deterministic.
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal

from app.services.analytics import rfm_scores
from app.models import Order

# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------
@pytest.fixture
def sample_orders(db_session):
    """Insert sample orders spanning different recency/frequency/monetary profiles."""
    now = datetime.utcnow()
    orders = [
        # Customer 1: recent, frequent, high spend
        Order(customer_id=1, merchant_id=10, created_at=now - timedelta(days=5), total_amount=Decimal("500")),
        Order(customer_id=1, merchant_id=10, created_at=now - timedelta(days=2), total_amount=Decimal("300")),

        # Customer 2: older, fewer, low spend
        Order(customer_id=2, merchant_id=10, created_at=now - timedelta(days=30), total_amount=Decimal("50")),

        # Customer 3: medium recency, medium spend
        Order(customer_id=3, merchant_id=10, created_at=now - timedelta(days=10), total_amount=Decimal("200")),
    ]
    db_session.add_all(orders)
    db_session.commit()
    return now


# ----------------------------------------------------------------------
# RFM Scores — Shape and Keys
# ----------------------------------------------------------------------
def test_rfm_scores_returns_expected_shape(db_session, sample_orders):
    """Returns a list of records with expected fields for three distinct customers."""
    results = rfm_scores(db_session, merchant_id=10, now=sample_orders)

    assert isinstance(results, list)
    assert len(results) == 3

    for rec in results:
        assert "customer_id" in rec
        assert "recency_days" in rec
        assert "frequency" in rec
        assert "monetary" in rec
        assert "r" in rec
        assert "f" in rec
        assert "m" in rec
        assert "rfm" in rec
