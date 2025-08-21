"""
Global test fixtures (unit + integration).

Responsibilities:
    - Provide a base Flask app in testing mode.
    - Initialize and clean up the database between test sessions.
    - Provide common fixtures (e.g., test client, database session).
    - Shared across both unit and integration test suites.

Notes:
    - Uses the 'testing' config via create_app("testing").
    - Database tables are created/dropped once per test session.
"""


import pytest
from app import create_app, db
from flask_jwt_extended import create_access_token
from app.models import User, Merchant


# ----------------------------------------------------------------------
# App (function-scoped)
# ----------------------------------------------------------------------
@pytest.fixture(scope="session")
def app():
    """Create a Flask app instance configured for testing.

    - Uses the 'testing' config from config.py.
    - Initializes an in-memory SQLite database.
    - Seeds a default merchant and admin user.
    - Tears down all tables after tests.
    """
    app = create_app("testing")

    # Explicit test configs for Redis & JWT
    app.config["REDIS_URL"] = "redis://localhost:6379/0"
    app.config["JWT_SECRET_KEY"] = "super-secret-test-key"
    app.config["SECRET_KEY"] = "super-secret-test-key"
    with app.app_context():
        db.create_all()

        # Create merchant and flush so we get the ID immediately
        merchant = Merchant(name="Test Store")
        db.session.add(merchant)
        db.session.flush()

        # Create and persist test user
        user = User(
            email="admin@example.com",   # ✅ unified email (fix)
            merchant_id=merchant.id,
            role="admin",
        )
        user.set_password("yourpassword")
        db.session.add(user)
        db.session.commit()

        yield app

        db.session.remove()
        db.drop_all()


# ----------------------------------------------------------------------
# Client
# ----------------------------------------------------------------------
@pytest.fixture
def client(app):
    """Return a Flask test client bound to the test app."""
    return app.test_client()


# ----------------------------------------------------------------------
# Access Token
# ----------------------------------------------------------------------
@pytest.fixture
def access_token(app):
    """Return a valid JWT access token for the seeded test user."""
    with app.app_context():
        user = User.query.filter_by(email="admin@example.com").first()  # ✅ match
        token = create_access_token(
            identity=str(user.id),
            additional_claims={"merchant_id": user.merchant_id},
        )
        return token


# ----------------------------------------------------------------------
# DB Session
# ----------------------------------------------------------------------
@pytest.fixture
def db_session(app):
    """Return the SQLAlchemy session for the test app."""
    with app.app_context():
        yield db.session


# ----------------------------------------------------------------------
# Auth Headers
# ----------------------------------------------------------------------
@pytest.fixture
def auth_headers(app, access_token):
    """Return headers with JWT and merchant_id for authenticated requests."""
    with app.app_context():
        user = User.query.filter_by(email="admin@example.com").first()  # ✅ match
        return {
            "Authorization": f"Bearer {access_token}",
            "merchant_id": user.merchant_id,
        }
