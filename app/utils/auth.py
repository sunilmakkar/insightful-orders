"""
Authentication utilities for Insightful-Orders.

Responsibilities:
    - Extract merchant context from JWTs.
    - Enforce that requests include a valid token before accessing resources.

Currently includes:
    - get_jwt_merchant_id(): Ensures JWT is present/valid and returns merchant_id claim.
"""


from flask_jwt_extended import verify_jwt_in_request, get_jwt


def get_jwt_merchant_id() -> int:
    """
    Extract `merchant_id` from the current JWT claims.
    Ensures the token is present and valid before returning.

    Returns:
        int: merchant_id from token claims.

    Raises:
        RuntimeError: If token is missing or merchant_id not in claims.
    """
    verify_jwt_in_request()
    claims = get_jwt()
    merchant_id = claims.get("merchant_id")
    if merchant_id is None:
        raise RuntimeError("JWT does not include merchant_id")
    return merchant_id