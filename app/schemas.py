"""Marshmallow schemas for request validation and serialization.

These schemas define the structure and validation rules for incoming
and outgoing JSON payloads in authentication, customer, and order endpoints.
"""

from marshmallow import Schema, fields, validate, pre_dump
from datetime import datetime
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema, auto_field
from app.models import AlertRule


# ----------------------------------------------------------------------
# User Schema
# ----------------------------------------------------------------------
class UserSchema(Schema):
    """Schema for user registration requests.

    Fields:
        email (str): Valid email address (required).
        password (str): Plaintext password (required, load_only so it’s never serialized back).
        role (str): Optional role for the new user (default handled in model).
        merchant_name (str): Optional merchant name (default handled in endpoint).
    """
    email = fields.Email(required=True)
    password = fields.String(required=True, load_only=True)
    role = fields.String(required=False)
    merchant_name = fields.String(required=False)
    merchant_id = fields.Int(dump_only=True)

    debug_marker = fields.String(dump_only=True, dump_default="UserSchema_in_use")


# ----------------------------------------------------------------------
# Auth Schema
# ----------------------------------------------------------------------
class AuthSchema(Schema):
    """Schema for user login requests.

    Fields:
        email (str): Valid email address (required).
        password (str): Plaintext password (required).
    """
    email = fields.Email(required=True)
    password = fields.String(required=True)


# ----------------------------------------------------------------------
# Customer Schema
# ----------------------------------------------------------------------
class CustomerSchema(Schema):
    """Schema for serializing/deserializing Customer objects.

    Fields:
        id (int): Customer ID (read-only).
        merchant_id (int): Associated merchant ID (read-only).
        external_id (str): Optional external customer identifier.
        first_name (str): Customer's first name.
        last_name (str): Customer's last name.
        email (str): Customer's email address.
        created_at (datetime): Timestamp of record creation (read-only).
    """
    id = fields.Int(dump_only=True)
    merchant_id = fields.Int(dump_only=True)
    external_id = fields.Str(load_default=None)
    first_name = fields.Str(load_default=None)
    last_name = fields.Str(load_default=None)
    email = fields.Email(load_default=None)
    created_at = fields.DateTime(dump_only=True)

    @pre_dump
    def ensure_datetime(self, obj, **kwargs):
        """Ensure created_at is always a datetime before serialization."""
        if isinstance(obj.created_at, str):
            try:
                obj.created_at = datetime.fromisoformat(obj.created_at)
            except ValueError:
                obj.created_at = datetime.utcnow()
        return obj


# ----------------------------------------------------------------------
# Order Schema
# ----------------------------------------------------------------------
class OrderSchema(Schema):
    """Schema for serializing/deserializing Order objects.

    Fields:
        id (int): Order ID (read-only).
        merchant_id (int): Associated merchant ID (read-only).
        customer_id (int): ID of the customer placing the order (required).
        external_id (str): Optional external order identifier.
        status (str): Order status (validated against allowed list).
        currency (str): Currency code (ISO 4217, 3 characters).
        total_amount (Decimal): Total amount for the order.
        created_at (datetime): Timestamp of order creation (read-only).
    """
    id = fields.Int(dump_only=True)
    merchant_id = fields.Int(dump_only=True)
    customer_id = fields.Int(required=True)
    external_id = fields.Str(load_default=None)
    status = fields.Str(
        validate=validate.OneOf(["created", "paid", "shipped", "delivered", "cancelled"]),
        load_default="created"
    )
    currency = fields.Str(validate=validate.Length(equal=3), load_default="BRL")
    total_amount = fields.Decimal(as_string=True, load_default="0.00")
    created_at = fields.DateTime(dump_only=True, format="iso")

    @pre_dump
    def ensure_datetime(self, obj, **kwargs):
        """Ensure created_at is always a datetime before serialization."""
        if isinstance(obj.created_at, str):
            try:
                obj.created_at = datetime.fromisoformat(obj.created_at)
            except ValueError:
                # Fallback: ignore or handle badly formatted strings
                obj.created_at = datetime.utcnow()
        return obj


# ----------------------------------------------------------------------
# Order Create Schema
# ----------------------------------------------------------------------
class OrderCreateSchema(Schema):
    """Schema for creating a single order.

    Fields:
        customer (dict): Customer details (supports upsert-by-email).
        external_id (str): Optional external order identifier.
        status (str): Order status (default "created").
        currency (str): Currency code (default "BRL").
        total_amount (Decimal): Total order amount (required).
    """
    customer = fields.Dict(required=True)  # supports upsert-by-email
    external_id = fields.Str(load_default=None)
    status = fields.Str(load_default="created")
    currency = fields.Str(load_default="BRL")
    total_amount = fields.Decimal(as_string=True, required=True)


# ----------------------------------------------------------------------
# Order Bulk Schema
# ----------------------------------------------------------------------
class OrderBulkSchema(Schema):
    """Schema for bulk creating orders.

    Fields:
        orders (list[OrderCreateSchema]): List of orders to create.
                                          Limited to 500 orders per request.
    """
    orders = fields.List(
        fields.Nested(OrderCreateSchema),
        required=True,
        validate=validate.Length(max=500)
    )


# ----------------------------------------------------------------------
# Alert Rule Schema
# ----------------------------------------------------------------------
class AlertRuleSchema(SQLAlchemyAutoSchema):
    """Schema for serializing/deserializing alert rule configurations.

    Fields:
        id (int): Alert rule ID (read-only).
        merchant_id (int): Associated merchant ID (foreign key).
        metric (str): Metric being monitored. Allowed values: 
                      "orders_per_min", "aov_window".
        operator (str): Comparison operator for threshold evaluation.
                        Allowed values: ">", ">=", "<", "<=", "==", "!=".
        threshold (float/int): Threshold value for the alert condition.
        time_window_s (int): Evaluation window in seconds. Must be between 
                             10 seconds and 86,400 seconds (1 day).
        created_at (datetime): Timestamp when rule was created (read-only).
        updated_at (datetime): Timestamp when rule was last updated (read-only).
    """
    class Meta:
        model = AlertRule
        load_instance = True       # load() returns an AlertRule instance
        include_fk = True          # include merchant_id FK
        # (We pass sqla_session at .load(..., session=db.session) in the view)

    threshold = fields.Float(required=True)

    # Field-level validation
    metric = auto_field(validate=validate.OneOf(["orders_per_min", "aov_window"]))         
    operator = auto_field(validate=validate.OneOf([">", ">=", "<", "<=", "==", "!="]))
    time_window_s = auto_field(validate=validate.Range(min=10, max=86400))

    # Read-only fields
    id = auto_field(dump_only=True)
    created_at = auto_field(dump_only=True)
    updated_at = auto_field(dump_only=True)

    @pre_dump
    def ensure_datetimes(self, obj, **kwargs):
        """Convert str timestamps back to datetime objects before dump."""
        from datetime import datetime

        if isinstance(obj, dict):
            for key in ("created_at", "updated_at"):
                if isinstance(obj.get(key), str):
                    try:
                        obj[key] = datetime.fromisoformat(obj[key])
                    except ValueError:
                        obj[key] = datetime.utcnow()
            return obj

        if isinstance(obj.created_at, str):
            obj.created_at = datetime.fromisoformat(obj.created_at)
        if isinstance(getattr(obj, "updated_at", None), str):
            obj.updated_at = datetime.fromisoformat(obj.updated_at)
        return obj