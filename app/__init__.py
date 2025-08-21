"""
Application factory and wiring for Insightful-Orders.

Responsibilities:
    - Load configuration via app.config.from_object(get_config(config_name)).
    - Initialize extensions: SQLAlchemy (db), Flask-Migrate (migrate), Marshmallow (ma),
      JWT (jwt), Redis client (redis_client), and API docs (flask-smorest 'api').
    - Register blueprints: auth, orders, metrics, alerts, and bind WebSocket routes.
    - Optionally register CLI commands if present (non-fatal if missing).
    - Start a background APScheduler job to evaluate alert rules at intervals
      (enabled by default; disabled for tests).

Environment / Config flags:
    - ALERTS_SCHEDULER_ENABLED (bool, default: True): toggles the alerts scheduler.
    - TESTING (bool, default: False): when True, prevents the scheduler from starting.

Usage:
    app = create_app("development")
"""

from flask import Flask
from app.config import get_config
from app.extensions import db, ma, jwt, redis_client, api, migrate
from apscheduler.schedulers.background import BackgroundScheduler
from app.services.alerts import evaluate_rules 
from datetime import datetime
import atexit


def create_app(config_name: str = "development"):
    """
    Application factory for Insightful-Orders.

    - Initializes all Flask extensions (db, migrate, ma, jwt, api, redis).
    - Registers blueprints (auth, orders, metrics, alerts).
    - Starts the alerts evaluator scheduler (non-testing envs).
    """
    # Create Flask app instance
    app = Flask(__name__)

    # Load configuration settings (based on config_name)
    app.config.from_object(get_config(config_name))

    # ------------------------------------------------------------------
    # Initialize Extensions
    # ------------------------------------------------------------------
    db.init_app(app)                # SQLAlchemy ORM

    # ✅ Auto-create tables if using SQLite (for local/dev/demo only)
    if app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite"):
        with app.app_context():
            db.create_all()

            
    migrate.init_app(app, db)       # Flask-Migrate for Alembic migrations
    ma.init_app(app)                # Marshmallow for serialization/validation
    jwt.init_app(app)               # JWT authentication
    redis_client.init_app(app)      # Redis client connection
    api.init_app(app)               # API documentation (flask-smorest)

    # ------------------------------------------------------------------
    # Register Blueprints
    # ------------------------------------------------------------------
    from app.blueprints.auth import auth_bp
    from app.blueprints.orders import orders_bp
    from app.blueprints.metrics import metrics_bp
    from app.blueprints.alerts import alerts_bp, sock
    from app.blueprints.health import health_bp

    api.register_blueprint(auth_bp)      # Auth endpoints (/auth)
    api.register_blueprint(orders_bp)    # Orders endpoints (/orders)
    api.register_blueprint(metrics_bp)   # Metrics endpoints (/metrics)
    api.register_blueprint(alerts_bp)    # Alerts endpoints (/alerts)
    api.register_blueprint(health_bp)    # Health endpoint (/healthz) 
    sock.init_app(app)                   # bind WebSocket routes to this app

    # ------------------------------------------------------------------
    # Otional CLI Registration (non-fatal if missing)
    # ------------------------------------------------------------------
    try:
        from .cli import register_cli  # type: ignore
        register_cli(app)
    except Exception:
        pass

    # -----------------------------------------------
    # Start Alerts Scheduler
    # -----------------------------------------------
    if app.config.get("ALERTS_SCHEDULER_ENABLED", True) and not app.config.get("TESTING", False):
        if not getattr(app, "_alerts_scheduler_started", False):
            scheduler = BackgroundScheduler(daemon=True)

            def _run_evaluator():
                with app.app_context():
                    res = evaluate_rules()
                    print(f"[alerts] evaluate_rules -> {res}", flush=True)

            scheduler.add_job(
                _run_evaluator,
                "interval",
                seconds=15,
                id="alerts_evaluator",
                replace_existing=True,
                next_run_time=datetime.utcnow(),  # first run immediately
            )
            scheduler.start()
            print("[alerts] scheduler.start()", flush=True)

            # Keep a handle and mark as started to avoid dupes
            app.extensions["alerts_scheduler"] = scheduler
            app._alerts_scheduler_started = True  # type: ignore[attr-defined]

            # Graceful stop on process exit
            atexit.register(lambda: scheduler.shutdown(wait=False))

    return app