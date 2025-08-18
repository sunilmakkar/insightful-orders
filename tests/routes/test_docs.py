"""
Route smoke tests for API documentation.

Covers:
    - Swagger UI at /api/docs
    - Redoc UI at /api/redoc
    - OpenAPI spec JSON at /api/openapi.json

Notes:
    - No auth required for these routes.
    - Verifies basic availability and key fields in the spec.
"""

# ----------------------------------------------------------------------
# /api/openapi.json — JSON spec
# ----------------------------------------------------------------------
def test_openapi_json_ok(client):
    """OpenAPI JSON is served and includes bearerAuth security scheme."""
    with client as c:
        resp = c.get("/api/openapi.json")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, dict)

        # Top-level security requires bearerAuth
        assert "security" in data
        assert {"bearerAuth": []} in data["security"]

        # Security scheme is present and correctly defined
        comps = data.get("components", {})
        schemes = comps.get("securitySchemes", {})
        bearer = schemes.get("bearerAuth", {})
        assert bearer.get("type") == "http"
        assert bearer.get("scheme") == "bearer"
        # Optional: confirm your title/version if you like
        assert data.get("info", {}).get("title", "").lower().startswith("insightful")


# ----------------------------------------------------------------------
# /api/docs — Swagger UI
# ----------------------------------------------------------------------
def test_swagger_ui_ok(client):
    """Swagger UI HTML is served at /api/docs."""
    with client as c:
        resp = c.get("/api/docs")
        assert resp.status_code == 200
        # HTML content-type and non-empty body
        assert "text/html" in resp.content_type
        assert resp.data and len(resp.data) > 100


# ----------------------------------------------------------------------
# /api/redoc — Redoc UI
# ----------------------------------------------------------------------
def test_redoc_ok(client):
    """Redoc HTML is served at /api/redoc."""
    with client as c:
        resp = c.get("/api/redoc")
        assert resp.status_code == 200
        assert "text/html" in resp.content_type
        assert resp.data and len(resp.data) > 100
