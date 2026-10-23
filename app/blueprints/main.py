"""Landing page and dashboard routes."""

from flask import Blueprint, redirect, render_template, url_for
from flask_login import current_user, login_required

main_bp = Blueprint("main", __name__)


@main_bp.get("/")
def index():
    """Show the landing page or redirect signed-in users to the dashboard."""
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return render_template("main/index.html")


@main_bp.get("/dashboard")
@login_required
def dashboard():
    """Show the signed-in user's career assistant dashboard."""
    return render_template("main/dashboard.html")
