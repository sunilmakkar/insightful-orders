"""
Factory Boy fixtures for Insightful-Orders unit tests.

Responsibilities:
    - Provide SQLAlchemy-backed factories for User, Merchant, Customer, and Order.
    - Commit persistence so created objects are immediately usable in tests.
"""

import factory
from faker import Faker
from passlib.hash import bcrypt
from app.extensions import db
from app.models import User, Merchant, Customer, Order

fake = Faker()

# ----------------------------------------------------------------------
# Base Factory (SQLAlchemy)
# ----------------------------------------------------------------------
class BaseFactory(factory.alchemy.SQLAlchemyModelFactory):
    """Base Factory: integrates Factory Boy with the app's SQLAlchemy session."""
    class Meta:
        abstract = True
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "commit"


# -----------------------------------------------------------------------
# Merchant Factory
# -----------------------------------------------------------------------
class MerchantFactory(BaseFactory):
    """Create fake Merchant objects for tests."""
    class Meta:
        model = Merchant

    name = factory.LazyAttribute(lambda _: fake.company())


# -----------------------------------------------------------------------
# User Factory
# -----------------------------------------------------------------------
class UserFactory(BaseFactory):
    """Create fake User objects for tests."""
    class Meta:
        model = User

    email = factory.LazyAttribute(lambda _: fake.email())
    password_hash = factory.LazyFunction(lambda: bcrypt.hash("test1234"))  # Known test password
    role = "admin"
    merchant = factory.SubFactory(MerchantFactory)


# -----------------------------------------------------------------------
# Customer Factory
# -----------------------------------------------------------------------
class CustomerFactory(BaseFactory):
    """Create fake Customer objects for tests."""
    class Meta:
        model = Customer

    # FIXED: allow merchant_id override
    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        merchant_id = kwargs.pop("merchant_id", None)
        if merchant_id:
            merchant = db.session.get(Merchant, merchant_id)
            kwargs["merchant"] = merchant
        return super()._create(model_class, *args, **kwargs)

    merchant = factory.SubFactory(MerchantFactory)
    email = factory.LazyAttribute(lambda _: fake.email())
    first_name = factory.LazyAttribute(lambda _: fake.first_name())
    last_name = factory.LazyAttribute(lambda _: fake.last_name())
    external_id = factory.LazyAttribute(lambda _: fake.uuid4())


# -----------------------------------------------------------------------
# Order Factory
# -----------------------------------------------------------------------
class OrderFactory(BaseFactory):
    """Create fake Order objects for tests."""
    class Meta:
        model = Order

    # FIXED: allow merchant_id override
    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        merchant_id = kwargs.pop("merchant_id", None)
        if merchant_id:
            merchant = db.session.get(Merchant, merchant_id)
            kwargs["merchant"] = merchant
        return super()._create(model_class, *args, **kwargs)

    merchant = factory.SubFactory(MerchantFactory)
    customer = factory.SubFactory(CustomerFactory, merchant=factory.SelfAttribute("..merchant"))
    
    external_id = factory.LazyAttribute(lambda _: fake.uuid4())
    status = factory.Iterator(["created", "paid", "shipped", "delivered", "cancelled"])
    currency = "BRL"
    total_amount = factory.LazyFunction(lambda: fake.pydecimal(left_digits=3, right_digits=2, positive=True))
    created_at = factory.LazyAttribute(lambda _: fake.date_time_this_year())
