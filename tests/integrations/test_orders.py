"""
Integration tests for /orders endpoints.

Endpoints:
    - GET    /orders
    - POST   /orders        (bulk create)
    - GET    /orders/<id>

Covers:
    - Pagination behavior on list.
    - Bulk create with customer upsert-by-email.
    - Cross-merchant access denial (403 or 404).

Notes:
    - Uses Factory Boy to seed merchants/users/customers/orders.
    - JWTs include the expected merchant_id claim.
"""

import pytest
from flask_jwt_extended import create_access_token
from app.models import Merchant

from tests.factories import (
    MerchantFactory,
    UserFactory,
    CustomerFactory,
    OrderFactory,
)


# ----------------------------------------------------------------------
# Helpers / Fixtures
# ----------------------------------------------------------------------
@pytest.fixture
def auth_client(app):
    """Create a merchant + user, mint a JWT, and return a test client with token."""
    with app.app_context():
        m = MerchantFactory()
        u = UserFactory(merchant=m)
        token = create_access_token(identity=str(u.id),
                                     additional_claims={"merchant_id": m.id})
        client = app.test_client()
        return client, token, m


def auth_headers(token: str) -> dict:
    """Attach Authorization header to requests."""
    return {"Authorization": f"Bearer {token}"}


def test_list_pagination(auth_client):
    """Seed 45 orders and ensure page=2&page_size=20 returns 20 items and total count=45."""
    client, token, merchant = auth_client

    # Seed orders for the same merchant
    for _ in range(45):
        OrderFactory(merchant=merchant, customer=CustomerFactory(merchant=merchant))

    resp = client.get("/orders?page=2&page_size=20", headers=auth_headers(token))
    assert resp.status_code == 200

    data = resp.get_json()
    assert data["page"] == 2
    assert data["page_size"] == 20
    assert data["count"] == 45
    assert len(data["items"]) == 20


# ----------------------------------------------------------------------
# POST /orders — Bulk Create + Cross-Merchant Denial
# ----------------------------------------------------------------------
def test_bulk_create_and_forbidden_cross_merchant(app, auth_client):
    """
    Bulk-create 2 orders under merchant A, then attempt to read one with a token
    from merchant B → expect 403/404. Also confirms customer upsert is per-merchant.
    """
    client, token, merchant = auth_client

    # Customer belonging to a different merchant (to test the upsert-by-email per-merchant boundary)
    other_customer = CustomerFactory()  # different merchant via its SubFactory

    payload = {
        "orders": [
            {
                "customer": {"email": "new@demo.com", "first_name": "New", "last_name": "Cust"},
                "total_amount": "120.50",
                "status": "paid",
            },
            {
                # This email belongs to other_customer in another merchant,
                # but our endpoint upserts per (merchant, email), so it's valid here.
                "customer": {"email": other_customer.email},
                "total_amount": "10.00",
            },
        ]
    }

    # Bulk create under merchant A
    resp = client.post("/orders", json=payload, headers=auth_headers(token))
    assert resp.status_code == 201
    data = resp.get_json()["created"]
    assert len(data) == 2
    oid = data[0]["id"]

    # Build a token for merchant B and confirm access is denied
    wrong_client = app.test_client()
    with app.app_context():
        m2 = MerchantFactory()
        u2 = UserFactory(merchant=m2, email="intruder@x.com")
        wrong_token = create_access_token(identity=str(u2.id)
                                          , additional_claims={"merchant_id": m2.id})

    r2 = wrong_client.get(f"/orders/{oid}", headers=auth_headers(wrong_token))
    assert r2.status_code in (403, 404)  # 404 if you purposely hide resource existence
