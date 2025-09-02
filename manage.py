"""Flask CLI entrypoint.

Allows running Flask commands (migrations, shell, etc.) via `python manage.py`
without setting FLASK_APP manually.

Also includes custom CLI commands, such as:
    - seed-demo: Populate the database with a demo merchant, user, customers, and orders.

Usage examples:
    python manage.py run         # Start the app
    python manage.py shell       # Open an interactive shell with app context
    python manage.py db upgrade  # Run Alembic migrations
    flask seed-demo              # Seed demo data into the database
"""

import os
import click
from faker import Faker
from flask.cli import FlaskGroup, with_appcontext

from app import create_app
from app.extensions import db
from app.models import Merchant, User, Customer, Order
from app.extensions import db, migrate
from dotenv import load_dotenv


# ----------------------------------------------------------------------
# App Bootstrap: Load environment and initialize Flask factory
# ----------------------------------------------------------------------
# Try .env.prod first, use .env as fallback
if os.path.exists(".env.prod"):
    load_dotenv(".env.prod")
elif os.path.exists(".env"):
    load_dotenv(".env")

# Determine config from environment, defaulting to development.
config_name = os.getenv("CONFIG", "development")

# Create the Flask app using the application factory.
app = create_app(config_name)

# Flask CLI group allows invoking commands with app context automatically.
cli = FlaskGroup(app)

# Faker instance for generating dummy names, emails, and dates.
fake = Faker()


# ----------------------------------------------------------------------
# CLI Command: reset-demo
# ----------------------------------------------------------------------
@click.command("reset-demo")
@with_appcontext
def reset_demo():
    """
    Wipe all demo data: merchants, users, customers, orders.
    Use this before reseeding to avoid duplicates.
    """
    Order.query.delete()
    Customer.query.delete()
    User.query.delete()
    Merchant.query.delete()
    db.session.commit()
    click.echo("All demo data removed.")


# ----------------------------------------------------------------------
# CLI Command: seed-demo
# ----------------------------------------------------------------------
@click.command("seed-demo")
@with_appcontext
def seed_demo():
    """
    Populate the database with a demo merchant, two users,
    80 customers, and 300 orders.

    - Creates merchant "DemoStore" if it doesn't exist.
    - Creates admin user admin@example.com with password 'demo1234'.
    - Creates integration test user itest@example.com with password 'test1234'.
    - Creates 80 unique customers.
    - Creates 300 orders randomly assigned to these customers.
    """

    # ------------------------------------------------------------------
    # Create merchant if not exists
    # ------------------------------------------------------------------
    merchant = Merchant.query.filter_by(name="DemoStore").first()
    if not merchant:
        merchant = Merchant(name="DemoStore")
        db.session.add(merchant)
        db.session.flush()  # get merchant.id

    # ------------------------------------------------------------------
    # Create admin user if not exists
    # ------------------------------------------------------------------
    admin = User.query.filter_by(email="admin@example.com").first()
    if not admin:
        admin = User(
            merchant_id=merchant.id,
            email="admin@example.com",
            role="admin",
        )
        admin.set_password("demo1234")  # 🔑 locked for unit tests
        db.session.add(admin)
    admin.merchant_id = merchant.id
    admin.set_password("demo1234")

    # ------------------------------------------------------------------
    # Create integration test user if not exists
    # ------------------------------------------------------------------
    click.echo("DEBUG: about to create or update itest@example.com")
    itest = User.query.filter_by(email="itest@example.com").first()
    if not itest:
        itest = User(
            merchant_id=merchant.id,
            email="itest@example.com",
            role="admin",
        )
        db.session.add(itest)
    itest.merchant_id = merchant.id
    itest.set_password("test1234")
    click.echo(f"DEBUG: itest object in session = {itest}")

    # ------------------------------------------------------------------
    # Commit admin + itest
    # ------------------------------------------------------------------
    click.echo("DEBUG: committing admin + itest users...")
    try:
        db.session.commit()
        click.echo("DEBUG: commit succeeded")
    except Exception as e:
        click.echo(f"DEBUG: commit failed with error: {e}")
        db.session.rollback()


    # ------------------------------------------------------------------
    # Debug: check what’s actually in DB immediately
    # ------------------------------------------------------------------
    users = User.query.all()
    click.echo(f"DEBUG: Users in DB after commit: {[u.email for u in users]}")


    # ------------------------------------------------------------------
    # CLEAR old customers + orders before reseeding
    # This avoids IntegrityError from duplicate emails (CHANGED SECTION)
    # ------------------------------------------------------------------
    click.echo("DEBUG: wiping old customers and orders...")
    Order.query.delete()
    Customer.query.delete()
    db.session.commit()

    # ------------------------------------------------------------------
    # Create customers (80 unique)
    # ------------------------------------------------------------------
    customers = []
    for _ in range(80):
        c = Customer(
            merchant_id=merchant.id,
            email=fake.unique.email(),
            first_name=fake.first_name(),
            last_name=fake.last_name(),
        )
        db.session.add(c)
        customers.append(c)

    db.session.flush()  # get IDs for customers

    # ------------------------------------------------------------------
    # Create orders (300 total, random customers/status)
    # ------------------------------------------------------------------
    orders = []
    for _ in range(300):
        c = fake.random_element(elements=customers)
        o = Order(
            merchant_id=merchant.id,
            customer_id=c.id,
            total_amount=fake.pydecimal(left_digits=3, right_digits=2, positive=True),
            status=fake.random_element(
                elements=["created", "paid", "shipped", "delivered", "cancelled"]
            ),
            currency="BRL",
            created_at=fake.date_time_between(start_date="-6M", end_date="now"),
        )
        db.session.add(o)
        orders.append(o)

    # Commit all changes in one transaction
    db.session.commit()

# Register commands on the FlaskGroup
cli.add_command(reset_demo)
cli.add_command(seed_demo)

if __name__ == "__main__":
    cli()
