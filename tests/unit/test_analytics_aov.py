"""
Unit tests for analytics: rolling AOV.

Function under test:
    - app.services.analytics.rolling_aov

Notes:
    - Uses the `app` fixture for an application context and DB session.
    - Fixes `now` to a deterministic timestamp for stable assertions.
"""

from datetime import datetime, timedelta
from decimal import Decimal

from app.extensions import db

from app.services.analytics import rolling_aov
from tests.factories import (
    MerchantFactory,
    CustomerFactory,
    OrderFactory
)


# ----------------------------------------------------------------------
# Rolling AOV — Basic Window Math
# ----------------------------------------------------------------------
def test_rolling_aov_basic(app):
    """
    Creates orders inside and outside a 30d window and verifies:
    - only in-window orders are counted
    - AOV math is correct
    - from/to/window fields are returned 
    """
    fixed_now = datetime(2025, 8, 10, 12, 0, 0) # deterministic "now"
    with app.app_context():
        # Merhcant under test
        m = MerchantFactory()
        c = CustomerFactory(merchant=m)

        # In-window orders: total = 150 over 2 orders => 75.0
        OrderFactory(
            merchant=m,
            customer=c,
            created_at=fixed_now - timedelta(days=1),
            total_amount=Decimal("100.00"),
            status="paid",
        )

        OrderFactory(  # <— second in-window order
            merchant=m,
            customer=c,
            created_at=fixed_now - timedelta(days=10),
            total_amount=Decimal("50.00"),
            status="paid",
        )

        # Outside-window order (should be ignored)
        OrderFactory(
            merchant=m,
            customer=c,
            created_at=fixed_now - timedelta(days=45),
            total_amount=Decimal("999.00"),
            status="paid",
        )

        # Noise from another merchant (should be ignored)
        m2 = MerchantFactory()
        c2 = CustomerFactory(merchant=m2)
        OrderFactory(
            merchant=m2,
            customer=c2,
            created_at=fixed_now - timedelta(days=2),
            total_amount=Decimal("777.00"),
            status="paid",
        )

        db.session.flush()

        result = rolling_aov(db.session, m.id, "30d", now=fixed_now)

        assert result["window"] == "30d"
        assert result["orders"] == 2
        assert result["aov"] == 75.0

        # Sanity on date bounds
        assert result["to"].startswith("2025-08-10T12:00:00")
        assert result["from"].startswith("2025-07-11") # 30 days before fixed_now


# ----------------------------------------------------------------------
# Rolling AOV — No Orders
# ----------------------------------------------------------------------
def test_rolling_aov_no_orders(app):
    """
    With no orders in the window, the function should return zeros.
    """
    fixed_now = datetime(2025, 8, 10, 12, 0, 0)
    with app.app_context():
        m = MerchantFactory()

        result = rolling_aov(db.session, m.id, "30d", now=fixed_now)
        assert result["window"] == "30d"
        assert result["orders"] == 0
        assert result["aov"] == 0.0

