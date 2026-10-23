"""Registration, login, logout, and student profile routes."""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import select

from app.extensions import db
from app.forms import LoginForm, ProfileForm, RegistrationForm
from app.models import User

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """Create an account and sign the new user in."""
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    form = RegistrationForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        existing_user = db.session.scalar(select(User).where(User.email == email))
        if existing_user:
            form.email.errors.append("An account with this email already exists.")
        else:
            user = User(name=form.name.data.strip(), email=email)
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash("Your account is ready.", "success")
            return redirect(url_for("main.dashboard"))
    return render_template("auth/register.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Authenticate an existing user."""
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = db.session.scalar(select(User).where(User.email == email))
        if user is None or not user.check_password(form.password.data):
            flash("Email or password was not recognized.", "error")
        else:
            login_user(user, remember=form.remember_me.data)
            flash("Welcome back.", "success")
            return redirect(url_for("main.dashboard"))
    return render_template("auth/login.html", form=form)


@auth_bp.post("/logout")
@login_required
def logout():
    """End the current authenticated session."""
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("main.index"))


@auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    """View and update student profile and internship preferences."""
    form = ProfileForm(obj=current_user)
    if form.validate_on_submit():
        current_user.name = form.name.data.strip()
        current_user.college = form.college.data.strip() or None
        current_user.degree = form.degree.data.strip() or None
        current_user.branch = form.branch.data.strip() or None
        current_user.graduation_year = form.graduation_year.data
        current_user.preferred_locations = _split_preferences(form.preferred_locations.data)
        current_user.preferred_domains = _split_preferences(form.preferred_domains.data)
        current_user.internship_type = form.internship_type.data or None
        current_user.minimum_stipend = form.minimum_stipend.data
        db.session.commit()
        flash("Your profile has been updated.", "success")
        return redirect(url_for("auth.profile"))
    if not form.is_submitted():
        form.preferred_locations.data = ", ".join(current_user.preferred_locations or [])
        form.preferred_domains.data = ", ".join(current_user.preferred_domains or [])
    return render_template("auth/profile.html", form=form)


def _split_preferences(value: str | None) -> list[str]:
    """Convert a comma-separated profile field into normalized values."""
    return [item.strip() for item in (value or "").split(",") if item.strip()]
