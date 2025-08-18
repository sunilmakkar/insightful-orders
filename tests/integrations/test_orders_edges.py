"""
Integration edge cases for Orders API.

Focus:
    - Access control between merchants (403/404).
    - Proper scoping of customers by merchant.
"""

import pytest
from flask_jwt_extended import create_access_token

from app import db
from tests.factories import MerchantFactory, UserFactory, CustomerFactory, OrderFactory


# ----------------------------------------------------------------------
# Helper: auth headers
# ----------------------------------------------------------------------
def auth_headers_for(token: str) -> dict:
    """Return Authorization headers for a given token."""
    return {"Authorization": f"Bearer {token}"}


# ----------------------------------------------------------------------
# Retrieve Order Wrong Merchant
# ----------------------------------------------------------------------
def test_retrieve_order_wrong_merchant(app):
    """
    GIVEN an order belonging to merchant A
    WHEN a client with merchant B’s token tries to retrieve it
    THEN the API should return 403/404 (forbidden or hidden)
    """
    client = app.test_client()
    with app.app_context():
        # Merchant A with user + order
        merchant_a = MerchantFactory()
        user_a = UserFactory(merchant=merchant_a)
        customer_a = CustomerFactory(merchant=merchant_a)
        order_a = OrderFactory(customer=customer_a, merchant=merchant_a)
        order_id = order_a.id  # ✅ capture ID while still attached

        # Merchant B with user + token
        merchant_b = MerchantFactory()
        user_b = UserFactory(merchant=merchant_b)
        token_b = create_access_token(
            identity=str(user_b.id),
            additional_claims={"merchant_id": merchant_b.id},
        )

    # Try to retrieve merchant A’s order with merchant B’s token
    resp = client.get(f"/orders/{order_id}", headers=auth_headers_for(token_b))
    assert resp.status_code in (403, 404)


# ----------------------------------------------------------------------
# Delete Order Wrong Merchant
# ----------------------------------------------------------------------
def test_delete_order_wrong_merchant(app):
    """
    GIVEN an order belonging to merchant A
    WHEN a client with merchant B’s token tries to delete it
    THEN the API should return 403/404
    """
    client = app.test_client()
    with app.app_context():
        # Merchant A with user + order
        merchant_a = MerchantFactory()
        user_a = UserFactory(merchant=merchant_a)
        customer_a = CustomerFactory(merchant=merchant_a)
        order_a = OrderFactory(customer=customer_a, merchant=merchant_a)
        order_id = order_a.id  # ✅ capture ID while still attached

        # Merchant B with user + token
        merchant_b = MerchantFactory()
        user_b = UserFactory(merchant=merchant_b)
        token_b = create_access_token(
            identity=str(user_b.id),
            additional_claims={"merchant_id": merchant_b.id},
        )

    # Try to delete merchant A’s order with merchant B’s token
    resp = client.delete(f"/orders/{order_id}", headers=auth_headers_for(token_b))
    assert resp.status_code in (403, 404)
