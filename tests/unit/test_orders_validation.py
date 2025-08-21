"""
Unit tests for error handling in orders blueprint (delete_order).

Covers:
    - Deleting a non-existent order returns 404.
    - Deleting an order belonging to another merchant returns 403.
"""

import pytest
from app.models import Order


def test_delete_order_not_found(client, auth_headers):
    """Deleting a non-existent order should return 404."""
    resp = client.delete("/orders/9999", headers=auth_headers)
    assert resp.status_code == 404


def test_delete_order_wrong_merchant(client, db_session, auth_headers):
    """Deleting an order belonging to a different merchant should return 403."""
    # Create an order with a different merchant_id (e.g., 999)
    foreign_order = Order(merchant_id=999, customer_id=1, total_amount=100)
    db_session.add(foreign_order)
    db_session.commit()

    resp = client.delete(f"/orders/{foreign_order.id}", headers=auth_headers)
    assert resp.status_code == 403
    assert b"Forbidden" in resp.data
