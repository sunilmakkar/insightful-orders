"""
Health check blueprint for Insightful-Orders.

Responsibilities:
    - Provide a lightweight endpoint for container/platform probes.
    - Should not require authentication.
    - Returns HTTP 200 OK with {"status": "ok"} if the app is running.
"""

from flask_smorest import Blueprint


# ----------------------------------------------------------------------
# Blueprint Setup
# ----------------------------------------------------------------------
health_bp = Blueprint("health", __name__, url_prefix="/healthz", description="Health check endpoint for uptime probes.")

@health_bp.route("", methods=["GET"])
@health_bp.response(200)
def health_check():
    """
    Return simple JSON for liveness/readiness probes.

    Example:
        {"status": "ok"}
    """
    return {"status": "ok"}