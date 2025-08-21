"""
Authentication route tests for Insightful-Orders.

Covers:
    - Registration (happy path)
    - Login (valid/invalid credentials)
    - Protected route access (/auth/me)
    - Token refresh flow

Routes under test:
    POST /auth/register
    POST /auth/login
    GET  /auth/me
    POST /auth/refresh

Notes:
    - Uses pytest fixtures from tests/unit/conftest.py:
      `client` (Flask test client) and `access_token` (JWT).
"""


# ----------------------------------------------------------------------
# Register User
# ----------------------------------------------------------------------
def test_register_user(client):
    """POST /auth/register should create a user and return 201."""
    res = client.post("/auth/register", json={
        "email": "newuser@example.com",
        "password": "newpass",
        "merchant_name": "New Shop",
        "role": "admin"
    })
    assert res.status_code == 201
    assert res.get_json()["message"] == "User registered successfully"

# ----------------------------------------------------------------------
# Login — Valid Credentials
# ----------------------------------------------------------------------
def test_login_user(client):
    """POST /auth/login with valid credentials returns access+refresh tokens."""
    res = client.post("/auth/login", json={
        "email": "admin@example.com",
        "password": "yourpassword"
    })
    assert res.status_code == 200
    # Expect both access and refresh tokens in the payload
    assert "access_token" in res.get_json()
    assert "refresh_token" in res.get_json()

# ----------------------------------------------------------------------
# Login — Invalid Credentials
# ----------------------------------------------------------------------
def test_login_invalid_credentials(client):
    """POST /auth/login with invalid credentials returns 401."""
    res = client.post("/auth/login", json={
        "email": "admin@example.com",
        "password": "wrongpass"
    })
    assert res.status_code == 401

# ----------------------------------------------------------------------
# /auth/me — Requires Token
# ----------------------------------------------------------------------
def test_me_route_requires_token(client):
    """GET /auth/me without a token should return 401."""
    res = client.get("/auth/me")
    assert res.status_code == 401

# ----------------------------------------------------------------------
# /auth/me — With Token
# ----------------------------------------------------------------------
def test_me_route_with_token(client, access_token):
    """GET /auth/me with a valid token returns user details."""
    res = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    data = res.get_json()
    assert res.status_code == 200, res.get_json()
    assert data["email"] == "admin@example.com"
    assert data["role"] == "admin"

# ----------------------------------------------------------------------
# Refresh Token
# ----------------------------------------------------------------------
def test_refresh_token(client):
    """POST /auth/refresh with a refresh token returns a new access token."""
    # First, login to get a refresh token
    login = client.post("/auth/login", json={
        "email": "admin@example.com",
        "password": "yourpassword" 
    })
    refresh_token = login.get_json()["refresh_token"]

    # Call refresh endpoint with the refresh token
    res = client.post(
        "/auth/refresh",
        headers={"Authorization": f"Bearer {refresh_token}"}
    )
    assert res.status_code == 200
    assert "access_token" in res.get_json()
