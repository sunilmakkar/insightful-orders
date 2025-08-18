"""
Authentication utility tests for Insightful-Orders.

Covers:
    - Extraction of merchant_id from JWT claims via get_jwt_merchant_id
    - Runtime error when merchant_id is missing

Functions under test:
    get_jwt_merchant_id()

Notes:
    - Uses Flask test client + JWT context.
    - Complements integration tests in tests/test_auth.py.
"""

import pytest
from flask_jwt_extended import create_access_token
from app.utils.auth import get_jwt_merchant_id


# ----------------------------------------------------------------------
# Merchant ID Extraction
# ----------------------------------------------------------------------
def test_get_jwt_merchant_id_returns_claims(client):
    """get_jwt_merchant_id should return merchant_id when present in JWT claims."""
    token = create_access_token(identity="1", additional_claims={"merchant_id": 42})

    # Make request with token
    res = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200

    # Call helper inside a request context
    with client.application.test_request_context(headers={"Authorization": f"Bearer {token}"}):
        assert get_jwt_merchant_id() == 42


# ----------------------------------------------------------------------
# Missing Merchant ID
# ----------------------------------------------------------------------
def test_get_jwt_merchant_id_missing_claim_raises(client):
    """get_jwt_merchant_id should raise when merchant_id is not in claims."""
    token = create_access_token(identity="1")  # no merchant_id in claims

    res = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200

    with client.application.test_request_context(headers={"Authorization": f"Bearer {token}"}):
        with pytest.raises(RuntimeError):
            get_jwt_merchant_id()
