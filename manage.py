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

# Determine config from environment, defaulting to development.
config_name = os.getenv("CONFIG", "development")

# Create the Flask app using the application factory.
app = create_app(config_name)

# Flask CLI group allows invoking commands with app context automatically.
cli = FlaskGroup(app)

# Faker instance for generating dummy names, emails, and dates.
fake = Faker()


# ----------------------------------------------------------------------
# CLI Command: seed-demo
# ----------------------------------------------------------------------
@click.command("seed-demo")
@with_appcontext
def seed_demo():
    """
    Populate the database with a demo merchant, one admin user,
    80 customers, and 300 orders.

    - Creates merchant "DemoStore" if it doesn't exist.
    - Creates admin user admin@demo.local with password 'demo1234'.
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
    user = User.query.filter_by(email="admin@demo.local").first()
    if not user:
        user = User(
            merchant_id=merchant.id,
            email="admin@demo.local",
            role="admin",
        )
        user.set_password("demo1234")  # hashed in model
        db.session.add(user)

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

    click.echo(f"Seeded DemoStore: customers={len(customers)} orders={len(orders)}")


# ----------------------------------------------------------------------
# Register custom CLI commands with the app
# ----------------------------------------------------------------------
def register_cli(app):
    """Attach all custom CLI commands to the Flask app."""
    app.cli.add_command(seed_demo)


# Register commands immediately so they work with manage.py
if app:
    register_cli(app)
else:
    import sys
    print("❌ ERROR: create_app() returned None. Check app/__init__.py and config.", file=sys.stderr)


if __name__ == "__main__":
    cli()
