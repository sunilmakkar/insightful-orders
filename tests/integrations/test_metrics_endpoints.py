"""
Integration tests for metrics endpoints.

Endpoints:
    - /metrics/aov
    - /metrics/rfm
    - /metrics/cohorts

Covers:
    - 401 responses without JWT.
    - 200 responses with JWT and basic response-shape assertions.
    - Happy-path behavior with seeded data via Factory Boy.

Notes:
    - Uses fixtures: app, client.
    - JWTs are minted inline with the expected merchant_id claim.
"""

from datetime import datetime, timedelta
from flask_jwt_extended import create_access_token

from app.extensions import db
from tests.factories import MerchantFactory, UserFactory, CustomerFactory, OrderFactory


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _dt(y, m, d=1, hh=12, mm=0, ss=0):
    """Construct a datetime for test fixtures."""
    return datetime(y, m, d, hh, mm, ss)


def _auth_headers(app, merchant_id: int, user_id: int = 1):
    """Create a Bearer JWT header carrying the given merchant_id claim."""
    with app.app_context():
        token = create_access_token(
            identity=str(user_id),
            additional_claims={"merchant_id": merchant_id},
        )
    return {"Authorization": f"Bearer {token}"}


# ----------------------------------------------------------------------
# Unauthorized Cases (no JWT)
# ----------------------------------------------------------------------
def test_aov_requires_jwt(client):
    """GET /metrics/aov without a token returns 401."""
    with client as c:
        resp = c.get("/metrics/aov")
        assert resp.status_code == 401


def test_rfm_requires_jwt(client):
    """GET /metrics/rfm without a token returns 401."""
    with client as c:
        resp = c.get("/metrics/rfm")
        assert resp.status_code == 401


def test_cohorts_requires_jwt(client):
    """GET /metrics/cohorts without a token returns 401."""
    with client as c:
        resp = c.get("/metrics/cohorts")
        assert resp.status_code == 401


# ----------------------------------------------------------------------
# /metrics/cohorts — Happy Path
# ----------------------------------------------------------------------
def test_cohorts_happy_path(app, client):
    """
    Seed 3 customers across Jan/Feb/Mar 2024 to exercise m0..m2 offsets.
    Assert response shape and a few key counts.
    """
    with app.app_context():
        m = MerchantFactory()
        # Link a user to the merchant (not strictly needed for token creation here)
        UserFactory(merchant=m)

        # Cohort A (Jan): orders in Jan, Feb, Mar
        c1 = CustomerFactory(merchant=m)
        OrderFactory(merchant=m, customer=c1, created_at=_dt(2024, 1, 5))
        OrderFactory(merchant=m, customer=c1, created_at=_dt(2024, 2, 10))
        OrderFactory(merchant=m, customer=c1, created_at=_dt(2024, 3, 15))

        # Cohort B (Feb): orders in Feb, Mar
        c2 = CustomerFactory(merchant=m)
        OrderFactory(merchant=m, customer=c2, created_at=_dt(2024, 2, 3))
        OrderFactory(merchant=m, customer=c2, created_at=_dt(2024, 3, 7))

        # Cohort C (Mar): order only in Mar
        c3 = CustomerFactory(merchant=m)
        OrderFactory(merchant=m, customer=c3, created_at=_dt(2024, 3, 20))

        db.session.commit()

        headers = _auth_headers(app, merchant_id=m.id)
        resp = client.get("/metrics/cohorts?from=2024-01&to=2024-03", headers=headers)
        assert resp.status_code == 200

        data = resp.get_json()
        assert set(data.keys()) == {"start", "end", "cohorts"}
        assert data["start"] == "2024-01"
        assert data["end"] == "2024-03"
        assert isinstance(data["cohorts"], list) and len(data["cohorts"]) >= 3

        # Convert to dict for assertions
        rows = {row["cohort"]: row for row in data["cohorts"]}

        for cohort in ("2024-01", "2024-02", "2024-03"):
            assert "m0" in rows[cohort]
            assert "m1" in rows[cohort]
            assert "m2" in rows[cohort]

        # Spot-check counts
        assert rows["2024-01"]["m0"] == 1
        assert rows["2024-01"]["m1"] == 1
        assert rows["2024-01"]["m2"] == 1

        assert rows["2024-02"]["m0"] == 1
        assert rows["2024-02"]["m1"] == 1
        assert rows["2024-02"]["m2"] == 0

        assert rows["2024-03"]["m0"] == 1
        assert rows["2024-03"]["m1"] == 0
        assert rows["2024-03"]["m2"] == 0


# ----------------------------------------------------------------------
# /metrics/rfm — Happy Path
# ----------------------------------------------------------------------
def test_rfm_happy_path(app, client):
    """Seed 2 customers then assert the response contains expected keys."""
    with app.app_context():
        m = MerchantFactory()
        UserFactory(merchant=m)

        c1 = CustomerFactory(merchant=m)
        c2 = CustomerFactory(merchant=m)

        # c1: 2 orders
        OrderFactory(merchant=m, customer=c1, total_amount=100, created_at=_dt(2024, 1, 10))
        OrderFactory(merchant=m, customer=c1, total_amount=150, created_at=_dt(2024, 2, 10))

        # c2: 1 order
        OrderFactory(merchant=m, customer=c2, total_amount=50, created_at=_dt(2024, 1, 12))

        db.session.commit()

        headers = _auth_headers(app, merchant_id=m.id)
        resp = client.get("/metrics/rfm", headers=headers)
        assert resp.status_code == 200

        data = resp.get_json()
        assert isinstance(data, list) and len(data) >= 2

        required_keys = {"customer_id", "recency_days", "frequency", "monetary", "r", "f", "m", "rfm"}
        for row in data:
            assert required_keys.issubset(row.keys())


# ----------------------------------------------------------------------
# /metrics/aov — Happy Path
# ----------------------------------------------------------------------
def test_aov_happy_path(app, client):
    """Seed recent orders and request AOV over a 90d window (include all data)."""
    with app.app_context():
        m = MerchantFactory()
        UserFactory(merchant=m)

        # Make now-ish deterministic-ish by using recent dates
        now = datetime.utcnow()
        within_90d = now - timedelta(days=15)

        c = CustomerFactory(merchant=m)
        OrderFactory(merchant=m, customer=c, total_amount=120, created_at=within_90d)
        OrderFactory(merchant=m, customer=c, total_amount=180, created_at=within_90d + timedelta(days=1))

        db.session.commit()

        headers = _auth_headers(app, merchant_id=m.id)
        resp = client.get("/metrics/aov?window=90d", headers=headers)
        assert resp.status_code == 200

        data = resp.get_json()
        assert set(data.keys()) == {"window", "from", "to", "orders", "aov"}
        assert data["window"] == "90d"
        assert data["orders"] >= 2
        assert isinstance(data["aov"], (int, float))
