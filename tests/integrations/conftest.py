"""
Integration test fixtures (session-scoped).

Responsibilities:
    - Provide a testing Flask app and database for the entire session.
    - Seed a single merchant + admin user available to all integration tests.
    - Issue a session-scoped JWT access token for authenticated requests.
    - Provide request headers with JWT + merchant_id for authenticated calls.

Notes:
    - Uses the 'testing' config via create_app("testing").
    - Creates/drops all tables once per test session.
"""

import pytest
from app import create_app, db
from app.models import Merchant, User
from flask_jwt_extended import create_access_token


# ----------------------------------------------------------------------
# App (session-scoped)
# ----------------------------------------------------------------------
@pytest.fixture(scope="session")
def app():
    """Session-scoped Flask app with initialized database and seed data."""
    app = create_app("testing")
    with app.app_context():
        db.create_all()

        # Seed one merchant + user for the whole test session
        merchant = Merchant(name="IT Store")
        db.session.add(merchant)
        db.session.flush()  # ensure merchant.id is available

        user = User(email="itest@example.com", merchant_id=merchant.id, role="admin")
        user.set_password("test1234")
        db.session.add(user)
        db.session.commit()

        yield app

        db.session.remove()
        db.drop_all()


# ----------------------------------------------------------------------
# Access Token (session-scoped)
# ----------------------------------------------------------------------
@pytest.fixture(scope="session")
def access_token(app):
    """Session-scoped JWT for the seeded user."""
    with app.app_context():
        user = User.query.filter_by(email="itest@example.com").first()
        return create_access_token(
            identity=str(user.id),
            additional_claims={"merchant_id": user.merchant_id},
        )


# ----------------------------------------------------------------------
# Auth Headers (function-scoped)
# ----------------------------------------------------------------------
@pytest.fixture
def auth_headers(app, access_token):
    """Per-test headers with Authorization + merchant_id."""
    with app.app_context():
        user = User.query.filter_by(email="itest@example.com").first()
        return {
            "Authorization": f"Bearer {access_token}",
            "merchant_id": user.merchant_id,
        }
