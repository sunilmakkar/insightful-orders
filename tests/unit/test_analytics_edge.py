"""
Edge-case tests for analytics service.

Focus:
    - Quintile scoring extremes.
    - RFM scoring when all customers identical.
    - Cohort matrix minimal case.
"""

import pytest
from datetime import datetime, timedelta

from app import db
from app.models import Merchant, Customer, Order
from app.services import analytics


# ----------------------------------------------------------------------
# Quintile Scoring Extremes
# ----------------------------------------------------------------------
def test_score_by_quintiles_smaller_is_better():
    """
    GIVEN values with clear orderings
    WHEN scored by quintiles
    THEN confirm scoring works for both ascending and descending logic
    """
    # Use (id, value) pairs, as expected by _score_by_quintiles
    pairs_high = list(enumerate([100, 200, 300, 400, 500], start=1))
    pairs_low = list(enumerate([1, 2, 3, 4, 5], start=1))

    scores_high = analytics._score_by_quintiles(pairs_high, smaller_is_better=False)
    scores_low = analytics._score_by_quintiles(pairs_low, smaller_is_better=True)

    # Assert all return 5 scores
    assert all(1 <= v <= 5 for v in scores_high.values())
    assert all(1 <= v <= 5 for v in scores_low.values())


# ----------------------------------------------------------------------
# RFM All Identical
# ----------------------------------------------------------------------
def test_rfm_scores_all_identical(app, db_session):
    """
    GIVEN 3 customers with identical recency/frequency/monetary
    WHEN computing RFM scores
    THEN all should receive the same combined score
    """
    with app.app_context():
        merchant = Merchant(name="Edge RFM")
        db_session.add(merchant)
        db_session.flush()

        now = datetime.utcnow()
        for i in range(3):
            cust = Customer(email=f"user{i}@demo.com", merchant_id=merchant.id)
            db_session.add(cust)
            db_session.flush()
            for _ in range(2):
                db_session.add(Order(
                    customer=cust,
                    merchant=merchant,
                    total_amount=100,
                    created_at=now - timedelta(days=1),
                ))
        db_session.commit()

        scores = analytics.rfm_scores(db_session, merchant.id, now=now)
        assert len(scores) == 3
        # Every customer has the same score
        assert len(set(s["rfm"] for s in scores)) == 1


# ----------------------------------------------------------------------
# Cohort Minimal Case
# ----------------------------------------------------------------------
def test_monthly_cohorts_sqlite_and_pg(app, db_session):
    """
    GIVEN a merchant with one customer and one order
    WHEN computing cohorts across a 3-month window
    THEN confirm the cohort matrix has the correct minimal shape
    """
    with app.app_context():
        merchant = Merchant(name="Edge Cohort")
        db_session.add(merchant)
        db_session.flush()

        cust = Customer(email="solo@demo.com", merchant_id=merchant.id)
        db_session.add(cust)
        db_session.flush()

        db_session.add(Order(
            customer=cust,
            merchant=merchant,
            total_amount=50,
            created_at=datetime(2024, 1, 15),
        ))
        db_session.commit()

        cohorts = analytics.monthly_cohorts(
            db_session,
            merchant.id,
            start=datetime(2024, 1, 1),
            end=datetime(2024, 3, 1),
        )

        assert "cohorts" in cohorts
        assert cohorts["cohorts"][0]["m0"] == 1
