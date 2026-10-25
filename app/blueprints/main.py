"""Landing page and dashboard routes."""

from flask import Blueprint, redirect, render_template, url_for
from flask_login import current_user, login_required
from sqlalchemy import select

from app.extensions import db
from app.models import Resume
from app.services.ats_scorer import score_resume

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
    active_resume = db.session.scalar(
        select(Resume).where(
            Resume.user_id == current_user.id,
            Resume.is_active.is_(True),
        )
    )
    ats_report = score_resume(active_resume) if active_resume else None
    return render_template(
        "main/dashboard.html",
        active_resume=active_resume,
        ats_report=ats_report,
    )
