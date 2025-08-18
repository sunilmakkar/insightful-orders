"""Database models for merchants, users, customers, and orders.

Defines ORM mappings for core authentication entities (Merchant, User)
and Phase 3 order domain entities (Customer, Order).
Passwords are hashed using Passlib's bcrypt implementation.
"""

from datetime import datetime
from passlib.hash import bcrypt
from .extensions import db


# ----------------------------------------------------------------------
# Merchant model
# ----------------------------------------------------------------------
class Merchant(db.Model):
    """Represents a merchant (store/organization) in the system.

    Attributes:
        id (int): Primary key.
        name (str): Merchant name (required).
        users (list[User]): Relationship to associated users.
        customers (list[Customer]): Relationship to associated customers.
        orders (list[Order]): Relationship to associated orders.
    """
    __tablename__ = "merchants"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)

    # Relationships
    users = db.relationship("User", backref="merchant", lazy=True)
    customers = db.relationship("Customer", backref="merchant", lazy="selectin")
    orders = db.relationship("Order", backref="merchant", lazy="selectin")


# ----------------------------------------------------------------------
# User model
# ----------------------------------------------------------------------
class User(db.Model):
    """Represents a system user belonging to a merchant.

    Attributes:
        id (int): Primary key.
        email (str): Unique email address for login.
        password_hash (str): Hashed password (bcrypt).
        role (str): User's role (default: "staff").
        merchant_id (int): Foreign key to Merchant.
    """
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="staff")
    merchant_id = db.Column(db.Integer, db.ForeignKey("merchants.id"), nullable=False)

    # ------------------------------------------------------------------
    # Auth helpers
    # ------------------------------------------------------------------
    def set_password(self, password: str) -> None:
        """Hash and store the given plaintext password."""
        self.password_hash = bcrypt.hash(password)

    def check_password(self, password: str) -> bool:
        """Verify the given plaintext password against the stored hash."""
        return bcrypt.verify(password, self.password_hash)

    def to_dict(self) -> dict:
        """Serialize user fields into a dictionary (excluding password hash)."""
        return {
            "id": self.id,
            "email": self.email,
            "role": self.role,
            "merchant_id": self.merchant_id,
        }


# ----------------------------------------------------------------------
# Customer model
# ----------------------------------------------------------------------
class Customer(db.Model):
    """Represents a customer of a merchant.

    Attributes:
        id (int): Primary key.
        merchant_id (int): Foreign key to Merchant.
        external_id (str): External customer ID (e.g., Olist customer_unique_id).
        first_name (str): Customer's first name.
        last_name (str): Customer's last name.
        email (str): Customer's email address.
        created_at (datetime): Timestamp when the customer record was created.
    """
    __tablename__ = "customers"

    id = db.Column(db.Integer, primary_key=True)
    merchant_id = db.Column(db.Integer, db.ForeignKey("merchants.id"), nullable=False, index=True)

    external_id = db.Column(db.String(64), index=True)
    first_name = db.Column(db.String(80))
    last_name = db.Column(db.String(80))
    email = db.Column(db.String(255), index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationship: one customer → many orders
    orders = db.relationship("Order", back_populates="customer", lazy="selectin")

    __table_args__ = (
        db.UniqueConstraint("merchant_id", "email", name="uq_customer_per_merchant"),
    )


# ----------------------------------------------------------------------
# Order model
# ----------------------------------------------------------------------
class Order(db.Model):
    """Represents an order placed by a customer for a merchant.

    Attributes:
        id (int): Primary key.
        merchant_id (int): Foreign key to Merchant.
        customer_id (int): Foreign key to Customer.
        external_id (str): External order ID (e.g., Olist order_id).
        status (str): Order status (default: "created").
        currency (str): ISO 4217 currency code (default: "BRL").
        total_amount (Decimal): Total amount for the order.
        created_at (datetime): Timestamp when the order was created.
    """
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    merchant_id = db.Column(db.Integer, db.ForeignKey("merchants.id"), nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False, index=True)

    external_id = db.Column(db.String(64), index=True)
    status = db.Column(db.String(32), default="created", nullable=False, index=True)
    currency = db.Column(db.String(3), default="BRL", nullable=False)
    total_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationship: one order → one customer
    customer = db.relationship("Customer", back_populates="orders", lazy="joined")

    __table_args__ = (
        db.Index("ix_orders_merchant_created_at", "merchant_id", "created_at"),
    )

# ----------------------------------------------------------------------
# AlertRule model
# ----------------------------------------------------------------------
class AlertRule(db.Model):
    """
    Merchant-scoped alert rule evaluated periodically.

    Example: metric='orders_per_min', operator='>', threshold=5, time_window_s=60
    """
    __tablename__ = "alert_rules"

    id = db.Column(db.Integer, primary_key=True)
    merchant_id = db.Column(db.Integer, db.ForeignKey("merchants.id"), nullable=False)

    metric = db.Column(db.String(64), nullable=False)           # e.g., 'orders_per_min', 'aov_window'
    operator = db.Column(db.String(2), nullable=False)          # one of: >, >=, <, <=
    threshold = db.Column(db.Numeric(12, 2), nullable=False)    # numeric threshold
    time_window_s = db.Column(db.Integer, nullable=False, default=60)

    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    merchant = db.relationship("Merchant", backref=db.backref("alert_rules", lazy="selectin"))

    __table_args__ = (
        db.Index("ix_alert_rules_active", "merchant_id", "is_active"),
        db.Index("ix_alert_rules_metric", "merchant_id", "metric"),
    )



