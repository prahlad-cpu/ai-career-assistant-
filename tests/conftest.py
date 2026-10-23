"""Shared application and database fixtures."""

import pytest

from app import create_app
from app.extensions import db
from app.models import User


@pytest.fixture()
def app():
    """Provide an isolated application with a fresh in-memory database."""
    application = create_app("testing")
    with application.app_context():
        db.drop_all()
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    """Provide the test client's HTTP interface."""
    return app.test_client()


@pytest.fixture()
def user(app):
    """Create a reusable authenticated test account."""
    with app.app_context():
        account = User(name="Sam Student", email="sam@example.com")
        account.set_password("strong-password")
        db.session.add(account)
        db.session.commit()
        return account.id
