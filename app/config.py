"""Application configuration classes and selector.

Defines environment-specific settings for Flask, SQLAlchemy, JWT, Redis,
and OpenAPI/Swagger UI. Values are primarily sourced from environment
variables to keep secrets out of the repo.
"""

import os


# ----------------------------------------------------------------------
# Base Config
# ----------------------------------------------------------------------
class BaseConfig:
    """Base defaults shared by all environments.

    Notes:
        - JWT_SECRET_KEY and REDIS_URL are expected to be provided via env vars.
        - OPENAPI_URL_PREFIX is used by flask-smorest to mount the API spec & UIs.
        - OPENAPI_* configure the interactive Swagger UI and Redoc.
    """
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
    SQLALCHEMY_TRACK_MODIFICATIONS = False  # Disable event system overhead

    # OpenAPI / Swagger / Redoc
    API_TITLE = "Insightful Orders API"
    API_VERSION = "v1"
    OPENAPI_VERSION = "3.0.3"

    # IMPORTANT: this must be OPENAPI_URL_PREFIX
    OPENAPI_URL_PREFIX = "/api"
    OPENAPI_JSON_PATH = "openapi.json"

    # Swagger UI
    OPENAPI_SWAGGER_UI_PATH = "/docs"
    OPENAPI_SWAGGER_UI_URL = "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"

    # Redoc
    OPENAPI_REDOC_PATH = "/redoc"
    OPENAPI_REDOC_URL = "https://cdn.jsdelivr.net/npm/redoc/bundles/redoc.standalone.js"

    # Security: show JWT "Authorize" in the docs
    API_SPEC_OPTIONS = {
        "security": [{"bearerAuth": []}],
        "components": {
            "securitySchemes": {
                "bearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT",
                }
            }
        },
    }

    REDIS_URL = os.getenv("REDIS_URL")
    ALERTS_SCHEDULER_ENABLED = True


# ----------------------------------------------------------------------
# Dev Config
# ----------------------------------------------------------------------
class DevConfig(BaseConfig):
    """Local development config.

    - Reads SQLALCHEMY_DATABASE_URI from env (e.g., Postgres in Docker).
    - DEBUG enables reloader and better tracebacks.
    - __init__ prints selected URIs to help verify docker-compose env.
    """
    SQLALCHEMY_DATABASE_URI = os.getenv("SQLALCHEMY_DATABASE_URI")
    DEBUG = True

    def __init__(self):
        print(f"🧪 DevConfig URI: {self.SQLALCHEMY_DATABASE_URI}")
        print(f"🧪 Redis URL: {self.REDIS_URL}")


# ----------------------------------------------------------------------
# Test Config
# ----------------------------------------------------------------------
class TestConfig(BaseConfig):
    """Testing config.

    - In-memory SQLite keeps tests isolated and fast.
    - TESTING flag can toggle test-only behaviors in Flask extensions.
    """
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    REDIS_URL = "redis://localhost:6379/0" 
    TESTING = True
    ALERTS_SCHEDULER_ENABLED = True

    JWT_SECRET_KEY = "super-secret-test-key"
    SECRET_KEY = "super-secret-test-key"



# ----------------------------------------------------------------------
# Prod Config
# ----------------------------------------------------------------------
class ProdConfig(BaseConfig):
    """Production config.

    - DATABASE_URI (not SQLALCHEMY_DATABASE_URI env name) is used to avoid
      accidental reuse of dev/test variables in production environments.
    - DEBUG is off to prevent leaking stack traces.
    """
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.getenv("SQLALCHEMY_DATABASE_URI")

# ----------------------------------------------------------------------
# Get Config
# ----------------------------------------------------------------------
def get_config(name: str):
    """Return a config class by environment name, or raise if invalid."""
    config_map = {
        "development": DevConfig,
        "testing": TestConfig,
        "production": ProdConfig
    }
    try:
        return config_map[name]()
    except KeyError:
        raise RuntimeError(f"Invalid config name: {name}")