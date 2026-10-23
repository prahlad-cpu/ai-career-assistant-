"""Phase 1 smoke tests for the app, authentication, and profile."""

from app.extensions import db
from app.models import User


def register(client, name="Sam Student", email="sam@example.com", password="strong-password"):
    return client.post(
        "/register",
        data={
            "name": name,
            "email": email,
            "password": password,
            "confirm_password": password,
        },
        follow_redirects=True,
    )


def test_healthz_returns_ok(client):
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json == {"status": "ok"}


def test_landing_page_links_to_registration_and_login(client):
    response = client.get("/")

    assert response.status_code == 200
    assert b"AI Career Assistant" in response.data
    assert b"/register" in response.data
    assert b"/login" in response.data


def test_dashboard_requires_authentication(client):
    response = client.get("/dashboard")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_registration_creates_hashed_account_and_dashboard(client, app):
    response = register(client, email="  SAM@example.com ")

    assert response.status_code == 200
    assert b"Welcome to your dashboard" in response.data
    with app.app_context():
        account = db.session.scalar(db.select(User).where(User.email == "sam@example.com"))
        assert account is not None
        assert account.password_hash != "strong-password"
        assert account.check_password("strong-password")


def test_registration_rejects_duplicate_email(client):
    register(client)
    client.post("/logout")

    response = register(client, name="Another Student")

    assert response.status_code == 200
    assert b"already exists" in response.data


def test_login_rejects_wrong_password_and_accepts_correct_password(client):
    register(client)
    client.post("/logout")

    denied = client.post(
        "/login",
        data={"email": "sam@example.com", "password": "incorrect-password"},
    )
    assert denied.status_code == 200
    assert b"not recognized" in denied.data

    accepted = client.post(
        "/login",
        data={"email": "sam@example.com", "password": "strong-password"},
        follow_redirects=True,
    )
    assert accepted.status_code == 200
    assert b"Welcome to your dashboard" in accepted.data


def test_profile_updates_student_preferences(client):
    register(client)

    response = client.post(
        "/profile",
        data={
            "name": "Sam Student",
            "college": "Example Institute",
            "degree": "B.Tech",
            "branch": "Computer Science",
            "graduation_year": "2027",
            "preferred_locations": "Bengaluru, Remote",
            "preferred_domains": "Web Development, Data Science",
            "internship_type": "remote",
            "minimum_stipend": "10000",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"profile has been updated" in response.data
    with client.application.app_context():
        account = db.session.scalar(db.select(User).where(User.email == "sam@example.com"))
        assert account.preferred_locations == ["Bengaluru", "Remote"]
        assert account.preferred_domains == ["Web Development", "Data Science"]
        assert account.graduation_year == 2027
        assert account.minimum_stipend == 10000


def test_logout_ends_authenticated_session(client):
    register(client)

    response = client.post("/logout", follow_redirects=True)

    assert response.status_code == 200
    assert b"You have been signed out" in response.data
    assert client.get("/dashboard").status_code == 302
