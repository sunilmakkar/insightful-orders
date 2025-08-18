"""
Route tests for /metrics/rfm.

Covers:
    - Seeding minimal per-merchant orders.
    - Authenticated GET on /metrics/rfm.
    - Response shape (list of records with customer_id and rfm fields).

Notes:
    - Uses fixtures: client, db_session, auth_headers.
    - auth_headers includes a valid JWT and merchant_id for convenience.
"""

from datetime import datetime, timedelta
from decimal import Decimal

from app.models import Order

def test_metrics_rfm_route(client, db_session, auth_headers):
    """Returns a list of per-customer RFM records for the authenticated merchant."""
    now = datetime.utcnow()
    orders = [
        Order(customer_id=1, merchant_id=auth_headers["merchant_id"], created_at=now - timedelta(days=5), total_amount=Decimal("500")),
        Order(customer_id=2, merchant_id=auth_headers["merchant_id"], created_at=now - timedelta(days=20), total_amount=Decimal("150")),
    ]
    db_session.add_all(orders)
    db_session.commit()

    # Call the endpoint
    resp = client.get("/metrics/rfm", headers=auth_headers)
    assert resp.status_code == 200

    data = resp.get_json()
    assert isinstance(data, list)
    assert all("customer_id" in rec for rec in data)
    assert all("rfm" in rec for rec in data)
