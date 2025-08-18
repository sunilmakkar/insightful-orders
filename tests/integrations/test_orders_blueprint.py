"""
Integration tests for /orders endpoints.

Covers:
    - Pagination behavior on list.
    - Bulk create with customer upsert-by-email.
    - Cross-merchant access denial (403/404).
"""

from tests.factories import CustomerFactory, OrderFactory, MerchantFactory, UserFactory


# ----------------------------------------------------------------------
# test_list_pagination
# ----------------------------------------------------------------------
def test_list_pagination(client, auth_headers, db_session):
    """Seed 45 orders and ensure page=2&page_size=20 returns 20 items and total count=45."""
    merchant_id = auth_headers["merchant_id"]

    # Use one merchant, same as JWT
    for _ in range(45):
        cust = CustomerFactory(merchant_id=merchant_id)
        OrderFactory(merchant_id=merchant_id, customer=cust)
    db_session.commit()

    resp = client.get("/orders?page=2&page_size=20", headers=auth_headers)
    assert resp.status_code == 200

    data = resp.get_json()
    assert data["page"] == 2
    assert data["page_size"] == 20
    assert data["count"] == 45
    assert len(data["items"]) == 20


# ----------------------------------------------------------------------
# test_bulk_create_and_forbidden_cross_merchant
# ----------------------------------------------------------------------
def test_bulk_create_and_forbidden_cross_merchant(client, app, auth_headers, db_session):
    """Bulk-create orders under merchant A, then ensure merchant B cannot access them."""
    merchant_id = auth_headers["merchant_id"]

    # Explicit other customer (different merchant via SubFactory)
    other_customer = CustomerFactory()  
    db_session.commit()

    payload = {
        "orders": [
            {
                "customer": {"email": "new@demo.com", "first_name": "New", "last_name": "Cust"},
                "total_amount": "120.50",
                "status": "paid",
            },
            {
                "customer": {"email": other_customer.email},
                "total_amount": "10.00",
            },
        ]
    }

    # Bulk create under merchant A
    resp = client.post("/orders", json=payload, headers=auth_headers)
    assert resp.status_code == 201
    data = resp.get_json()["created"]
    oid = data[0]["id"]

    # Merchant B tries to fetch order → denied
    with app.app_context():
        m2 = MerchantFactory()
        u2 = UserFactory(merchant=m2, email="intruder+test@example.com")
        db_session.add_all([m2, u2])
        db_session.commit()

        from flask_jwt_extended import create_access_token
        wrong_token = create_access_token(
            identity=str(u2.id),
            additional_claims={"merchant_id": m2.id},
        )
        wrong_headers = {"Authorization": f"Bearer {wrong_token}"}

    r2 = client.get(f"/orders/{oid}", headers=wrong_headers)
    assert r2.status_code in (403, 404)

