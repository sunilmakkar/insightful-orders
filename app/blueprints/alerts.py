"""
Alerts blueprint for Insightful-Orders.

Responsibilities:
    - Provide REST endpoints for managing alert rules (CRUD-lite).
    - Support pagination for listing alert rules.
    - Handle WebSocket connections for real-time alert delivery.
    - Bridge between Flask-JWT auth (merchant_id from JWT) and Redis pub/sub
      channels for live push.

Routes:
    POST   /alerts         Create a new alert rule.
    GET    /alerts         List existing alert rules (paginated).
    WS     /alerts/ws      Subscribe to real-time alerts via WebSocket.
"""

from flask import request
from flask_jwt_extended import jwt_required
from flask_sock import Sock
from flask_smorest import Blueprint  # <-- use smorest so REST endpoints appear in OpenAPI
from marshmallow import Schema, fields, validate

from app.extensions import db, redis_client
from app.models import AlertRule
from app.schemas import AlertRuleSchema
from app.utils.auth import get_jwt_merchant_id
from app.utils.helpers import paginate, alerts_channel_for_merchant

# ----------------------------------------------------------------------
# Blueprint Setup
# ----------------------------------------------------------------------
alerts_bp = Blueprint(
    "alerts",
    __name__,
    url_prefix="/alerts",
    description="Create and list merchant-scoped alert rules.",
)
sock = Sock()

# ----------------------------------------------------------------------
# Request & Response Schemas
# ----------------------------------------------------------------------
class AlertRuleCreateSchema(Schema): 
    """Schema for creating a new alert rule (merchant_id injected from JWT)."""
    metric = fields.Str(required=True, metadata={"example": "orders_per_min"})
    operator = fields.Str(
        required=True,
        validate=validate.OneOf([">", ">=", "<", "<=", "==", "!="]),
        metadata={"example": ">="},
    )
    threshold = fields.Float(required=True, metadata={"example": 100.0})
    time_window_s = fields.Int(required=True, metadata={"example": 300})
    is_active = fields.Bool(load_default=True, metadata={"example": True})

class AlertRuleListSchema(Schema):
    """Paginated list wrapper for alert rules."""
    page = fields.Int(required=True, metadata={"example": 1})
    page_size = fields.Int(required=True, metadata={"example": 20})
    count = fields.Int(required=True, metadata={"example": 42})
    items = fields.List(fields.Nested(AlertRuleSchema), required=True)


# ----------------------------------------------------------------------
# Create Alert Rule
# ----------------------------------------------------------------------
@alerts_bp.route("", methods=["POST"])
@alerts_bp.arguments(AlertRuleCreateSchema)  
@alerts_bp.response(201, AlertRuleSchema)
@jwt_required()
def create_alert_rule(data):
    """
    Create a new alert rule for the authenticated merchant.

    Request body:
        AlertRuleSchema fields (except merchant_id, which is injected from JWT):
        - metric (str): e.g., "orders_per_min", "aov_window"
        - operator (str): one of [">", ">=", "<", "<=", "==", "!="]
        - threshold (number)
        - time_window_s (int): evaluation window in seconds
        - is_active (bool)
    """
    merchant_id = get_jwt_merchant_id()
    data = (request.get_json() or {}).copy()
    data["merchant_id"] = merchant_id

    schema = AlertRuleSchema()
    rule = schema.load(data, session=db.session)

    db.session.add(rule)
    db.session.commit()

    return rule


# ----------------------------------------------------------------------
# List Alert Rules (Paginated)
# ----------------------------------------------------------------------
@alerts_bp.route("", methods=["GET"])
@alerts_bp.response(200, AlertRuleListSchema)
@jwt_required()
def list_alert_rules():
    """
    List the authenticated merchant’s alert rules (paginated).

    Query params:
      - page (int, default=1)
      - page_size (int, default=20; capped in paginate())
    """
    merchant_id = get_jwt_merchant_id()
    query = AlertRule.query.filter_by(merchant_id=merchant_id)
    return paginate(query, AlertRuleSchema())


# ----------------------------------------------------------------------
# WebSocket: Live Alerts
# ----------------------------------------------------------------------
def alerts_socket(ws):
    """
    Subscribe the client to real-time alerts for its merchant.

    Handshake:
      - Client passes JWT as a `token` query param (e.g., ?token=eyJ...).

    Behavior:
      - Decodes token → merchant_id
      - Subscribes to Redis pub/sub channel for that merchant
      - Forwards each message to the WebSocket client as-is (JSON string)
    """
    # Extract merchant_id from token in query params
    token = request.args.get("token")
    if not token:
        ws.close()
        return

    from flask_jwt_extended import decode_token
    try:
        merchant_id = decode_token(token)["merchant_id"]
    except Exception:
        ws.close()
        return

    channel = alerts_channel_for_merchant(merchant_id)
    pubsub = redis_client.client.pubsub()
    pubsub.subscribe(channel)

    try:
        for message in pubsub.listen():
            if message["type"] == "message":
                data = message["data"]
                if isinstance(data, (bytes, bytearray)):
                    try:
                        data = data.decode("utf-8")
                    except Exception:
                        # fallback: safe JSON string
                        import json
                        data = json.dumps({"raw": list(message["data"])})
                elif not isinstance(data, str):
                    import json
                    data = json.dumps(data)

                # ✅ Always send a TEXT frame (str)
                ws.send(str(data))
    except Exception:
        pass
    finally:
        try:
            pubsub.unsubscribe(channel)
            pubsub.close()
        except Exception:
            pass


# Register the same function with Flask-Sock
sock.route("/ws/alerts")(alerts_socket)