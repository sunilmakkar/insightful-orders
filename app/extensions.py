"""Flask extension instances and initialization helpers.

Centralizes creation of extension objects (db, ma, jwt, etc.) so they can
be imported anywhere without causing circular imports. Each extension is
initialized with `init_app(app)` in the application factory.
"""

from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from flask_smorest import Api
from redis import Redis


# ----------------------------------------------------------------------
# Core Flask extensions
# ----------------------------------------------------------------------
# SQLAlchemy ORM instance; handles DB connections and model definitions.
db = SQLAlchemy()

# Marshmallow instance; used for schema serialization/deserialization/validation.
ma = Marshmallow()

# JWT manager; configures token creation/validation hooks for authentication.
jwt = JWTManager()

# API manager from flask-smorest; registers blueprints and handles OpenAPI docs.
api = Api()

# Alembic migration handler; integrates with Flask CLI for schema migrations.
migrate = Migrate()

# ----------------------------------------------------------------------
# Redis Client Wrapper
# ----------------------------------------------------------------------
class RedisClient:
    """Simple Redis client wrapper to integrate with Flask config.

    Attributes:
        client (Redis): Active Redis connection.
    """
    def __init__(self):
        self.client = None

    def init_app(self, app):
        """Initialize Redis connection from Flask app config.

        Args:
            app (Flask): The Flask app instance.

        Notes:
            - Expects `REDIS_URL` in app.config.
            - Uses redis-py `from_url()` for easy connection string parsing.
        """
        self.client = Redis.from_url(app.config.get("REDIS_URL"))


# Singleton Redis client for use throughout the app.
redis_client = RedisClient()
