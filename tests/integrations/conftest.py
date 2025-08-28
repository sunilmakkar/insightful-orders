"""
Integration test fixtures.

Responsibilities:
    - Reuse the global `app` fixture from tests/conftest.py.
    - Seed an extra merchant + user for integration tests.
    - Provide access token + headers for authenticated integration requests.
"""

import pytest
from app import db
from app.models import Merchant, User
from flask_jwt_extended import create_access_token


# ----------------------------------------------------------------------
# Integration User + Merchant
# ----------------------------------------------------------------------
@pytest.fixture(scope="session")
def integration_user(app):
    """Seed a dedicated merchant+user for integration tests, reusing global app."""
    with app.app_context():
        merchant = Merchant(name="Demo Store")
        db.session.add(merchant)
        db.session.flush()

        user = User(email="itest@example.com", merchant_id=merchant.id, role="admin")
        user.set_password("test1234")
        db.session.add(user)
        db.session.commit()

        # return only primitive values to avoid DetachedInstanceError
        return {"id": user.id, "merchant_id": merchant.id, "email": user.email}


# ----------------------------------------------------------------------
# Access Token (session-scoped)
# ----------------------------------------------------------------------
@pytest.fixture(scope="session")
def access_token(app, integration_user):
    """JWT for the integration user."""
    with app.app_context():
        return create_access_token(
            identity=str(integration_user["id"]),
            additional_claims={"merchant_id": integration_user["merchant_id"]},
        )


# ----------------------------------------------------------------------
# Auth Headers (function-scoped)
# ----------------------------------------------------------------------
@pytest.fixture
def auth_headers(integration_user, access_token):
    """Auth headers for integration requests."""
    return {
        "Authorization": f"Bearer {access_token}",
        "merchant_id": integration_user["merchant_id"],
    }
