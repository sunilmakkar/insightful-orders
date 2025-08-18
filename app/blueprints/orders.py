"""
Orders blueprint for Insightful-Orders.

Responsibilities:
    - List orders with pagination.
    - Bulk-create orders with customer upsert-by-email.
    - Retrieve and delete single orders.
    - Scope all operations to the authenticated merchant (merchant_id from JWT).

Routes:
    GET     /orders                 List orders (paginated).
    POST    /orders                 Bulk-create up to 500 orders.
    GET     /orders/<order_id>      Retrieve a single order.
    DELETE  /orders/<order_id>      Delete a single order.

Security:
    - JWT required on all endpoints.
    - Merchant context derived from JWT claims and enforced per request.
"""

from flask import request, jsonify
from flask_smorest import Blueprint, abort
from flask_jwt_extended import jwt_required, get_jwt
from sqlalchemy import select

from app.extensions import db
from app.models import Customer, Order
from app.schemas import CustomerSchema, OrderSchema, OrderBulkSchema
from app.utils.helpers import paginate


# ----------------------------------------------------------------------
# Blueprint Setup & Schemas
# ----------------------------------------------------------------------
orders_bp = Blueprint("orders", __name__, url_prefix="/orders", description="Operations on orders (JWT required)")

order_schema = OrderSchema()
customer_schema = CustomerSchema()
bulk_schema = OrderBulkSchema()


# ----------------------------------------------------------------------
# Helper: Extract merchant_id from JWT claims
# ----------------------------------------------------------------------
def _merchant_id_from_jwt():
    """
    Extract the merchant_id from the JWT's custom claims.

    Returns:
        int or None: merchant_id if present in JWT claims.
    """
    claims = get_jwt()
    return claims.get("merchant_id")


# ----------------------------------------------------------------------
# Helper: Get or create a customer for the given merchant
# ----------------------------------------------------------------------
def _get_or_create_customer(merchant_id, data):
    """
    Retrieve an existing customer for this merchant by email,
    or create a new one if none exists.

    Args:
        merchant_id (int): ID of the merchant creating the order.
        data (dict): Customer data from the request payload.
                     Example:
                         {
                           "email": "cust@example.com",
                           "first_name": "Jane",
                           "last_name": "Doe"
                         }

    Returns:
        Customer: The existing or newly created Customer instance.

    Raises:
        ValueError: If no email is provided in the payload.
    """
    email = (data or {}).get("email")
    if not email:
        raise ValueError("customer.email is required")

    # Try to find an existing customer for this merchant with the same email
    stmt = select(Customer).where(
        Customer.merchant_id == merchant_id,
        Customer.email == email
    )
    customer = db.session.execute(stmt).scalar_one_or_none()

    if customer:
        # Light update: update name/external_id if new values are provided
        for k in ("first_name", "last_name", "external_id"):
            v = (data or {}).get(k)
            if v:
                setattr(customer, k, v)
    else:
        # Create a new customer record
        customer = Customer(
            merchant_id=merchant_id,
            email=email,
            first_name=(data or {}).get("first_name"),
            last_name=(data or {}).get("last_name"),
            external_id=(data or {}).get("external_id"),
        )
        db.session.add(customer)

    return customer


# ----------------------------------------------------------------------
# GET /orders → List Orders (Paginated)
# ----------------------------------------------------------------------
@orders_bp.get("")
@orders_bp.response(200, OrderSchema(many=True))
@jwt_required()
def list_orders():
    """
    List all orders for the authenticated merchant.

    - Requires JWT authentication.
    - Retrieves merchant_id from JWT claims.
    - Orders results by created_at (newest first).
    - Returns paginated JSON using the paginate() helper.
    """
    merchant_id = _merchant_id_from_jwt()
    q = Order.query.filter_by(merchant_id=merchant_id).order_by(Order.created_at.desc())
    return paginate(q, order_schema)


# ----------------------------------------------------------------------
# POST /orders — Bulk Create Orders
# ----------------------------------------------------------------------
@orders_bp.post("")
@orders_bp.arguments(OrderBulkSchema)
@orders_bp.response(201, OrderSchema(many=True))
@jwt_required()
def bulk_create_orders():
    """
    Bulk-create up to 500 orders for the authenticated merchant.

    Request body:
        {
          "orders": [
            {
              "customer": { "email": "...", "first_name": "...", "last_name": "..." },
              "external_id": "...",
              "status": "paid",
              "currency": "BRL",
              "total_amount": "100.00"
            },
            ...
          ]
        }

    - Validates request payload with OrderBulkSchema.
    - For each order in payload:
        * Get or create the associated customer.
        * Create an Order record linked to that customer.
    - Commits all changes in a single transaction.
    - Returns serialized list of created orders.
    """
    merchant_id = _merchant_id_from_jwt()
    payload = bulk_schema.load(request.get_json() or {})
    created = []

    for item in payload["orders"]:
        customer = _get_or_create_customer(merchant_id, item.get("customer"))
        order = Order(
            merchant_id=merchant_id,
            customer=customer,
            external_id=item.get("external_id"),
            status=item.get("status", "created"),
            currency=item.get("currency", "BRL"),
            total_amount=item["total_amount"],
        )
        db.session.add(order)
        created.append(order)

    db.session.commit()
    return jsonify({"created": order_schema.dump(created, many=True)}), 201


# ----------------------------------------------------------------------
# GET /orders/<order_id> → Retrieve Single Order
# ----------------------------------------------------------------------
@orders_bp.get("/<int:order_id>")
@orders_bp.response(200, OrderSchema) 
@jwt_required()
def retrieve_order(order_id):
    """
    Retrieve a single order by its ID.

    - Requires JWT authentication.
    - Returns 403 if the order does not belong to the authenticated merchant.
    """
    merchant_id = _merchant_id_from_jwt()
    order = db.session.get(Order, order_id)  # SQLAlchemy 2.x style to clear pytest warning
    if order is None:
        abort(404)
    if order.merchant_id != merchant_id:
        abort(403, message="Forbidden")            
    return order 


# ----------------------------------------------------------------------
# DELETE /orders/<order_id> → Delete Single Order
# ----------------------------------------------------------------------
@orders_bp.delete("/<int:order_id>")
@orders_bp.response(204)                           
@jwt_required()
def delete_order(order_id):
    """
    Delete an order by its ID.

    - Requires JWT authentication.
    - Returns 403 if the order does not belong to the authenticated merchant.
    - Deletes the order and commits the change.
    - Returns HTTP 204 No Content on success.
    """
    merchant_id = _merchant_id_from_jwt()
    order = db.session.get(Order, order_id)  # SQLAlchemy 2.x style to clear pytest warning
    if order is None:
        abort(404)
    if order.merchant_id != merchant_id:
        abort(403, message="Forbidden")            ### CHANGED: use abort instead of jsonify
    db.session.delete(order)
    db.session.commit()
    return ""  

