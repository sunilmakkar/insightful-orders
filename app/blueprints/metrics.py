"""
Metrics blueprint for Insightful-Orders.

Responsibilities:
    - Expose merchant analytics computed by the services layer.
    - Validate and document responses via Marshmallow schemas.
    - Read merchant context from JWT claims.

Routes:
    GET  /metrics/aov       Rolling Average Order Value (windowed).
    GET  /metrics/rfm       Per-customer RFM scores.
    GET  /metrics/cohorts   Monthly cohort retention matrix.
"""

from flask import request
from flask.views import MethodView
from flask_jwt_extended import jwt_required, get_jwt
from flask_smorest import Blueprint
from sqlalchemy.orm import Session
from marshmallow import Schema, fields

from app.extensions import db
from app.services.analytics import rolling_aov, rfm_scores, monthly_cohorts
from app.utils.helpers import parse_monthish


# ----------------------------------------------------------------------
# Blueprint Setup
# ----------------------------------------------------------------------
metrics_bp = Blueprint("metrics", __name__, url_prefix="/metrics", description="Analytics endpoints for customer insights (AOV, RFM, Cohorts).")


# ----------------------------------------------------------------------
# Query Param Schemas
# ----------------------------------------------------------------------
class AOVQuerySchema(Schema):
    window = fields.Str(
        required=False,
        load_default="30d",
        metadata={"description": "Rolling window (30d, 12w, 6m, 1y)", "example": "30d"}
    )

class CohortsQuerySchema(Schema):
    from_ = fields.Str(
        data_key="from",
        required=False,
        metadata={"description": "Start month YYYY-MM or YYYY-MM-DD"}
    )
    to = fields.Str(
        required=False,
        metadata={"description": "End month YYYY-MM or YYYY-MM-DD"}
    )


# ----------------------------------------------------------------------
# Response Schema: /aov
# ----------------------------------------------------------------------
class RollingAOVSchema(Schema):
    """Response schema for rolling Average Order Value results."""
    window = fields.Str(required=True, metadata={"example": "30d"})
    from_ = fields.Str(attribute="from", data_key="from", required=True)
    to = fields.Str(required=True)
    orders = fields.Int(required=True, metadata={"example": 123})
    aov = fields.Float(required=True, metadata={"example": 142.37})


# ----------------------------------------------------------------------
# GET /metrics/aov
# ----------------------------------------------------------------------
@metrics_bp.route("/aov")
class RollingAOVResource(MethodView):
    @metrics_bp.arguments(AOVQuerySchema, location="query") 
    @metrics_bp.response(200, RollingAOVSchema)
    @jwt_required()
    def get(self, args):   # <-- FIXED: only one get() method
        """
        Return the Average Order Value over a rolling time window.
        """
        window = args.get("window", "30d")   # <-- use parsed args, not request.args
        claims = get_jwt()
        merchant_id = claims.get("merchant_id")
        if not merchant_id:
            return {"message": "Missing merchant_id in token"}, 400

        session: Session = db.session
        result = rolling_aov(session, merchant_id, window)
        return result


# ----------------------------------------------------------------------
# Response Schema: /rfm
# ----------------------------------------------------------------------
class RFMSchema(Schema):
    """Response schema for RFM scores."""
    customer_id = fields.Int(required=True, metadata={"example": 101})
    recency_days = fields.Int(required=True, metadata={"example": 12})
    frequency = fields.Int(required=True, metadata={"example": 8})
    monetary = fields.Float(required=True, metadata={"example": 456.78})
    r = fields.Int(required=True, metadata={"example": 5})
    f = fields.Int(required=True, metadata={"example": 4})
    m = fields.Int(required=True, metadata={"example": 5})
    rfm = fields.Str(required=True, metadata={"example": "545"})


# ----------------------------------------------------------------------
# GET /metrics/rfm
# ----------------------------------------------------------------------
@metrics_bp.route("/rfm")
class RFMResource(MethodView):
    @metrics_bp.response(200, RFMSchema(many=True))
    @jwt_required()
    def get(self):   # <-- no args schema, so just self
        """
        Return Recency-Frequency-Monetary scores for all customers of this merchant.
        """
        claims = get_jwt()
        merchant_id = claims.get("merchant_id")
        if not merchant_id:
            return {"message": "Missing merchant_id in token"}, 400
        
        session: Session = db.session
        results = rfm_scores(session, merchant_id)
        return results


# ----------------------------------------------------------------------
# Response Schema: /cohorts
# ----------------------------------------------------------------------
class CohortMatrixSchema(Schema):
    start = fields.Str(required=True, metadata={"example": "2024-01"})
    end = fields.Str(required=True, metadata={"example": "2024-06"})
    cohorts = fields.List(
        fields.Dict(keys=fields.Str(), values=fields.Raw()),
        required=True
    )


# ----------------------------------------------------------------------
# GET /metrics/cohorts
# ----------------------------------------------------------------------
@metrics_bp.route("/cohorts")
class CohortsResource(MethodView):
    @metrics_bp.arguments(CohortsQuerySchema, location="query")    
    @metrics_bp.response(200, CohortMatrixSchema)
    @jwt_required()
    def get(self, args):
        """
        Return monthly cohort retention matrix.
        """
        claims = get_jwt()
        merchant_id = claims.get("merchant_id")
        if not merchant_id:
            return {"message": "Missing merchant_id in token"}, 400

        start_q = parse_monthish(args.get("from"))
        end_q = parse_monthish(args.get("to"))

        session: Session = db.session
        result = monthly_cohorts(session, merchant_id, start=start_q, end=end_q)
        return result
