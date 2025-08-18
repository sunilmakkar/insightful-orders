"""
Unit tests for analytics: monthly cohorts.

Function under test:
    - app.services.analytics.monthly_cohorts

Covers:
    - Cohort assignment based on first-order month.
    - Distinct-customer retention counts across m0..mN.
    - Zero-filling for missing month offsets.
    - Optional start/end window filtering.

Notes:
    - Uses the `app` fixture for application context and DB session.
"""

from datetime import datetime

from app.services.analytics import monthly_cohorts
from tests.factories import MerchantFactory, CustomerFactory, OrderFactory
from app.extensions import db


# ----------------------------------------------------------------------
# Helper
# ----------------------------------------------------------------------
def _dt(y, m, d=1, hh=12, mm=0, ss=0):
    """Convenience helper to construct datetimes for fixtures."""
    return datetime(y, m, d, hh, mm, ss)


# ----------------------------------------------------------------------
# monthly_cohorts — Basic Matrix
# ----------------------------------------------------------------------
def test_monthly_cohorts_basic_matrix(app):
    """
    Scenario:
        - 3 customers; cohorts Jan/Feb/Mar 2024
        - Repeat orders to create offsets m0..m2
    Expect:
        - Correct distinct-customer counts per offset
        - Dense columns m0..m2 present for all cohorts (zero-filled if missing)
    """
    with app.app_context():
        m = MerchantFactory()

        # Cohort A: first order Jan 2024; repeats in Feb and Mar
        c1 = CustomerFactory(merchant=m)
        OrderFactory(merchant=m, customer=c1, created_at=_dt(2024, 1, 5))
        OrderFactory(merchant=m, customer=c1, created_at=_dt(2024, 2, 10))
        OrderFactory(merchant=m, customer=c1, created_at=_dt(2024, 3, 15))

        # Cohort B: first order Feb 2024; repeat in Mar
        c2 = CustomerFactory(merchant=m)
        OrderFactory(merchant=m, customer=c2, created_at=_dt(2024, 2, 3))
        OrderFactory(merchant=m, customer=c2, created_at=_dt(2024, 3, 7))

        # Cohort C: first order Mar 2024; single order
        c3 = CustomerFactory(merchant=m)
        OrderFactory(merchant=m, customer=c3, created_at=_dt(2024, 3, 20))

        db.session.commit()

        # Call service with explicit window (covers window filtering path)
        res = monthly_cohorts(
            session=db.session,
            merchant_id=m.id,
            start=_dt(2024, 1, 1),
            end=_dt(2024, 3, 31),
        )

        # Top-level keys
        assert res["start"] == "2024-01"
        assert res["end"] == "2024-03"
        assert isinstance(res["cohorts"], list)

        # Convert list → dict by cohort for easy assertions
        rows = {r["cohort"]: r for r in res["cohorts"]}

        # Expect cohorts present
        assert "2024-01" in rows
        assert "2024-02" in rows
        assert "2024-03" in rows

        # Offsets should be dense up to m2 (since there is activity in Mar from Jan cohort)
        for cohort in ("2024-01", "2024-02", "2024-03"):
            assert "m0" in rows[cohort]
            assert "m1" in rows[cohort]
            assert "m2" in rows[cohort]

        # Distinct-customer counts by our setup:
        # - Jan cohort (c1): m0=1 (Jan), m1=1 (Feb), m2=1 (Mar)
        assert rows["2024-01"]["m0"] == 1
        assert rows["2024-01"]["m1"] == 1
        assert rows["2024-01"]["m2"] == 1

        # - Feb cohort (c2): m0=1 (Feb), m1=1 (Mar), m2=0
        assert rows["2024-02"]["m0"] == 1
        assert rows["2024-02"]["m1"] == 1
        assert rows["2024-02"]["m2"] == 0

        # - Mar cohort (c3): m0=1 (Mar), m1=0, m2=0
        assert rows["2024-03"]["m0"] == 1
        assert rows["2024-03"]["m1"] == 0
        assert rows["2024-03"]["m2"] == 0


# ----------------------------------------------------------------------
# monthly_cohorts — Empty Result
# ----------------------------------------------------------------------
def test_monthly_cohorts_empty_when_no_orders(app):
    """No orders → cohorts is empty; start/end are None without an explicit window."""
    with app.app_context():
        m = MerchantFactory()
        db.session.commit()

        res = monthly_cohorts(session=db.session, merchant_id=m.id)
        assert res["cohorts"] == []
        # start/end are None because no data and no explicit window
        assert res["start"] is None
        assert res["end"] is None
