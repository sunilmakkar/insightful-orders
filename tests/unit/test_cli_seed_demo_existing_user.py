"""
Test: seed_demo should handle the case where admin@example.com already exists.

Important:
- We do NOT commit/flush a duplicate user with the same email, because that
  will always trigger an IntegrityError before seed_demo logic runs.
- Instead, we run seed_demo once to create DemoStore + user.
- Then we simulate "moving" the user to another merchant (without deleting it).
- Finally, we rerun seed_demo and assert that the existing user is reassigned
  back to DemoStore instead of inserting a duplicate.
"""

import pytest
from click.testing import CliRunner
from app.cli import seed_demo
from app.extensions import db
from app.models import Merchant, User


def test_seed_demo_existing_user_reassigned(app):
    runner = CliRunner()

    with app.app_context():
        # Step 1: Run once so DemoStore and admin@example.com are created
        result1 = runner.invoke(seed_demo)
        assert result1.exit_code == 0

        demo_merchant = Merchant.query.filter_by(name="DemoStore").first()
        user = User.query.filter_by(email="admin@example.com").first()
        assert user is not None
        assert user.merchant_id == demo_merchant.id

        # Step 2: Create another merchant and "move" the user there
        other_merchant = Merchant(name="OtherStore")
        db.session.add(other_merchant)
        db.session.commit()

        user.merchant_id = other_merchant.id
        db.session.commit()

        # Sanity check: user no longer points to DemoStore
        assert user.merchant_id == other_merchant.id

        # Step 3: Rerun seed_demo — should reassign the user back to DemoStore
        result2 = runner.invoke(seed_demo)
        assert result2.exit_code == 0

        db.session.refresh(user)
        assert user.merchant_id == demo_merchant.id
