"""Custom CLI commands for the Flask application.

These commands are registered with the Flask app via the `register_cli` function
and can be executed inside the container using `flask <command>`.

Example:
    docker compose exec api flask seed-demo
"""


import click
from faker import Faker
from flask.cli import with_appcontext

from .extensions import db
from .models import Merchant, User, Customer, Order

# Faker instance for generating realistic random data
fake = Faker()


@click.command("seed-demo")
@with_appcontext
def seed_demo():
    """
    Populate the database with a demo merchant, one admin user,
    80 customers, and 300 orders.

    This command is idempotent — it will not duplicate the demo merchant or user
    if they already exist.
    """
    # ------------------------------------------------------------------
    # Create demo merchant if it doesn't already exist
    # ------------------------------------------------------------------
    merchant = Merchant.query.filter_by(name="DemoStore").first()
    if not merchant:
        merchant = Merchant(name="DemoStore")
        db.session.add(merchant)
        db.session.flush()  # flush to get merchant.id without committing

    # ------------------------------------------------------------------
    # Create admin user for the demo merchant
    # ------------------------------------------------------------------
    user = User.query.filter_by(email="admin@demo.local").first()
    if not user:
        user = User(
            merchant_id=merchant.id,
            email="admin@demo.local",
            role="admin",
        )
        user.set_password("demo1234")  # hash password
        db.session.add(user)

    # ------------------------------------------------------------------
    # Create demo customers
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

    # Flush so customers have IDs before creating orders
    db.session.flush()

    # ------------------------------------------------------------------
    # Create demo orders
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

    # Commit all records in one transaction
    db.session.commit()

    click.echo(f"Seeded DemoStore: customers={len(customers)} orders={len(orders)}")


def register_cli(app):
    """
    Register all custom CLI commands with the Flask app.

    Args:
        app (Flask): The Flask application instance.
    """
    app.cli.add_command(seed_demo)
