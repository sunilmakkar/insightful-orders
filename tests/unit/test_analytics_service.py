"""
Unit test for analytics service (rfm_scores).

Covers:
    - Merchant with no orders should return an empty list.
"""

from app.services.analytics import rfm_scores


def test_rfm_scores_returns_empty_for_no_orders(db_session):
    """rfm_scores should return [] if a merchant has no orders."""
    results = rfm_scores(db_session, merchant_id=999, now=None)
    assert isinstance(results, list)
    assert results == []
