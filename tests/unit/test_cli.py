"""
Unit tests for CLI commands (manage.py / flask CLI).

Covers:
    - seed-demo: populates demo merchant, user, customers, and orders.
"""

import pytest
from click.testing import CliRunner
from app.models import Merchant, User


# ----------------------------------------------------------------------
# Test: seed-demo command
# ----------------------------------------------------------------------
def test_seed_demo_creates_demo_data(app):
    """Running `flask seed-demo` should create demo merchant and user."""
    runner = CliRunner()

    with app.app_context():
        result = runner.invoke(app.cli, ["seed-demo"])

        # Assert CLI printed confirmation
        assert "Seeded DemoStore" in result.output

        merchant = Merchant.query.filter_by(name="DemoStore").first()
        user = User.query.filter_by(email="admin@demo.local").first()

        assert merchant is not None
        assert user is not None
        assert user.merchant_id == merchant.id
