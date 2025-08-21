"""
Authentication blueprint for Insightful-Orders.

Responsibilities:
    - User registration and merchant bootstrap.
    - Email/password login issuing access/refresh JWTs.
    - Refresh flow to mint new access tokens.
    - Return current user details based on JWT identity.

Routes:
    POST   /auth/register    Register a new user (and merchant).
    POST   /auth/login       Authenticate and return access/refresh tokens.
    POST   /auth/refresh     Exchange refresh token for a new access token.
    GET    /auth/me          Return the current authenticated user's details.

Security:
    - JWT enforced per-route via decorators.
    - Identity stored in JWT is str(User.id); convert back to int when reading.
"""

from flask.views import MethodView
from flask_smorest import Blueprint, abort
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    jwt_required,
    get_jwt_identity
)
from app.extensions import db
from app.models import User, Merchant
from app.schemas import UserSchema, AuthSchema

# ----------------------------------------------------------------------
# Blueprint Setup
# ----------------------------------------------------------------------
auth_bp = Blueprint("auth", __name__, url_prefix="/auth", description="Auth endpoints")


# ----------------------------------------------------------------------
# Extra response schemas (NEW) so docs show returns
# ----------------------------------------------------------------------
from marshmallow import Schema, fields

class MessageSchema(Schema):
    message = fields.Str(required=True, metadata={"example": "User registered successfully"})

class TokenPairSchema(Schema):
    access_token = fields.Str(required=True, metadata={"example": "eyJhbGciOiJI..."})
    refresh_token = fields.Str(required=True, metadata={"example": "eyJhbGciOiJI..."})

class AccessTokenSchema(Schema): 
    access_token = fields.Str(required=True, metadata={"example": "eyJhbGciOiJI..."})


# ----------------------------------------------------------------------
# Register
# ----------------------------------------------------------------------
@auth_bp.route("/register")
class RegisterUser(MethodView):
    """Register a new user and their merchant.

    Request body (validated by UserSchema):
      - email (str, required)
      - password (str, required)
      - role (str, optional; defaults to "admin")
      - merchant_name (str, optional; defaults to "Default Store")
    """

    @auth_bp.arguments(UserSchema)
    @auth_bp.response(201, MessageSchema)   
    def post(self, user_data):
        """Create user + merchant, hash password, and persist.

        Returns:
            tuple[dict, int]: Success message and HTTP 201.

        Raises:
            409: If a user with the same email already exists.
        """
        # Enforce unique email at the application layer (DB unique constraint should also exist)
        if User.query.filter_by(email=user_data["email"]).first():
            abort(409, message="User already exists")

        # Create a merchant for the user on first registration
        merchant = Merchant(name=user_data.get("merchant_name", "Default Store"))
        user = User(
            email=user_data["email"],
            role=user_data.get("role", "admin"),
            merchant=merchant
        )
        # Store password securely (never store plaintext)
        user.set_password(user_data["password"])

        db.session.add(merchant)
        db.session.add(user)
        db.session.commit()

        return {"message": "User registered successfully"}, 201


# ----------------------------------------------------------------------
# Login
# ----------------------------------------------------------------------
@auth_bp.route("/login")
class LoginUser(MethodView):
    """Authenticate a user by email/password and issue JWTs."""

    @auth_bp.arguments(AuthSchema)
    @auth_bp.response(200, TokenPairSchema)
    def post(self, credentials):
        """Validate credentials and return access/refresh tokens.

        Returns:
            dict: { "access_token": str, "refresh_token": str }

        Raises:
            401: If email or password is invalid.
        """
        user = User.query.filter_by(email=credentials["email"]).first()
        if not user or not user.check_password(credentials["password"]):
            # Uniform error to avoid user enumeration
            abort(401, message="Invalid credentials")

        # Store identity as string for consistency when decoding later
        access_token = create_access_token(
            identity=str(user.id),
            additional_claims={"merchant_id": user.merchant_id}
        )
        refresh_token = create_refresh_token(
            identity=str(user.id),
            additional_claims={"merchant_id": user.merchant_id}
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token
        }


# ----------------------------------------------------------------------
# Refresh
# ----------------------------------------------------------------------
@auth_bp.route("/refresh")
class RefreshToken(MethodView):
    """Exchange a valid refresh token for a new access token."""

    @jwt_required(refresh=True)
    @auth_bp.response(200, AccessTokenSchema)
    def post(self):
        """Return a new short-lived access token.

        Security:
            Requires a refresh token (not an access token).
        """
        current_user = int(get_jwt_identity())
        user = db.session.get(User, current_user)
        if not user:
            abort(404, message="User not found")

        new_access_token = create_access_token(
            identity=str(user.id),
            additional_claims={"merchant_id": user.merchant_id}
        )
        
        return {"access_token": new_access_token}


# ----------------------------------------------------------------------
# Me
# ----------------------------------------------------------------------
@auth_bp.route("/me")
class MeEndpoint(MethodView):
    """Return details for the currently authenticated user."""

    @jwt_required()
    @auth_bp.response(200, UserSchema)
    def get(self):
        """Fetch the user record for the JWT identity.

        Returns:
            dict: Result of `User.to_dict()`.

        Raises:
            404: If the user no longer exists (e.g., deleted after token issuance).
        """
        # Identity was stored as str(user.id) on login; convert back to int for lookups
        user_id = int(get_jwt_identity())
        user = db.session.get(User, user_id)
        if not user:
            abort(404, message="User not found")
        return user
