"""Internship recommendation pages."""

from __future__ import annotations

import math
from typing import Any

from flask import Blueprint, abort, flash, render_template, request
from flask_login import current_user, login_required
from sqlalchemy import select

from app.extensions import db
from app.models import Internship, Resume
from app.services.skill_gap import analyze_skill_gap, extract_job_skill_requirements
from app.services.matching_engine import (
    Recommendation,
    score_recommendations,
    tfidf_baseline_scores,
)

internships_bp = Blueprint("internships", __name__)
PAGE_SIZE = 12
SORT_OPTIONS = {"score", "stipend", "newest", "title"}
MAX_JOB_DESCRIPTION_LENGTH = 12_000


@internships_bp.get("/recommendations")
@login_required
def recommendations():
    """Show ranked internship matches for the active resume."""
    resume = db.session.scalar(
        select(Resume).where(
            Resume.user_id == current_user.id,
            Resume.is_active.is_(True),
        )
    )
    listings = db.session.scalars(
        select(Internship).order_by(Internship.posted_date.desc(), Internship.title.asc())
    ).all()
    recommendations: list[Recommendation] = []
    scoring = request.args.get("scoring", "hybrid").casefold()
    if scoring not in {"hybrid", "tfidf"}:
        scoring = "hybrid"
    if resume and listings:
        if scoring == "hybrid":
            recommendations = score_recommendations(resume, current_user, listings)
        else:
            baseline_scores = tfidf_baseline_scores(resume, listings)
            recommendations = [
                Recommendation(
                    internship=listing,
                    score=baseline_scores[listing.id],
                    semantic_similarity=0.0,
                    skill_overlap=0.0,
                    education_experience_fit=0.0,
                    preference_fit=0.0,
                    matched_skills=[],
                    missing_required_skills=[],
                    matched_preferred_skills=[],
                    reason="Keyword-only TF-IDF cosine baseline score.",
                )
                for listing in listings
            ]

    domains = sorted({listing.domain for listing in listings})
    modes = sorted({listing.mode for listing in listings})
    filters: dict[str, Any] = {
        "domain": request.args.get("domain", "").strip(),
        "location": request.args.get("location", "").strip(),
        "mode": request.args.get("mode", "").strip().casefold(),
        "min_stipend": _integer_arg("min_stipend", default=0, minimum=0),
        "min_score": _float_arg("min_score", default=0, minimum=0, maximum=100),
        "q": request.args.get("q", "").strip()[:100],
        "sort": request.args.get("sort", "score").casefold(),
    }
    if filters["mode"] not in modes:
        filters["mode"] = ""
    if filters["domain"] not in domains:
        filters["domain"] = ""
    if filters["sort"] not in SORT_OPTIONS:
        filters["sort"] = "score"

    filtered = [match for match in recommendations if _matches_filters(match, filters)]
    _sort_matches(filtered, filters["sort"])
    page = _integer_arg("page", default=1, minimum=1)
    total = len(filtered)
    page_count = max(1, math.ceil(total / PAGE_SIZE))
    page = min(page, page_count)
    page_matches = filtered[(page - 1) * PAGE_SIZE : page * PAGE_SIZE]
    return render_template(
        "internships/recommendations.html",
        matches=page_matches,
        domains=domains,
        modes=modes,
        filters=filters,
        page=page,
        page_count=page_count,
        total=total,
        has_resume=resume is not None,
        has_listings=bool(listings),
        scoring=scoring,
    )


@internships_bp.get("/skill-gap/<string:internship_id>")
@login_required
def skill_gap(internship_id: str):
    """Show a role-specific skill gap for the signed-in user's active resume."""
    internship = db.session.get(Internship, internship_id)
    if internship is None:
        abort(404)
    resume = db.session.scalar(
        select(Resume).where(
            Resume.user_id == current_user.id,
            Resume.is_active.is_(True),
        )
    )
    report = (
        analyze_skill_gap(
            resume.profile_json or {},
            internship.required_skills or [],
            internship.preferred_skills or [],
        )
        if resume
        else None
    )
    return render_template(
        "internships/skill_gap.html",
        report=report,
        has_resume=resume is not None,
        title=internship.title,
        description=internship.description,
        is_pasted=False,
    )


@internships_bp.route("/skill-gap/paste", methods=["GET", "POST"])
@login_required
def pasted_skill_gap():
    """Analyze skills from a pasted job description without storing its text."""
    title = ""
    description = ""
    report = None
    resume = db.session.scalar(
        select(Resume).where(
            Resume.user_id == current_user.id,
            Resume.is_active.is_(True),
        )
    )
    if request.method == "POST":
        title = request.form.get("title", "").strip()[:120]
        description = request.form.get("description", "").strip()
        if not description:
            flash("Paste a job description to analyze its skill requirements.", "error")
        elif len(description) > MAX_JOB_DESCRIPTION_LENGTH:
            flash(
                f"Job description must be {MAX_JOB_DESCRIPTION_LENGTH:,} characters or fewer.",
                "error",
            )
            description = description[:MAX_JOB_DESCRIPTION_LENGTH]
        else:
            if resume is None:
                flash("Upload and activate a resume to compare your skills.", "error")
            else:
                required, preferred = extract_job_skill_requirements(description)
                report = analyze_skill_gap(
                    resume.profile_json or {},
                    required,
                    preferred,
                )
                if not report.has_job_skills:
                    flash(
                        "No skills from the current taxonomy were detected. Try a description with named tools or technologies.",
                        "info",
                    )
    return render_template(
        "internships/skill_gap.html",
        report=report,
        has_resume=resume is not None,
        title=title or "Pasted job description",
        description=description,
        is_pasted=True,
    )


def _integer_arg(name: str, *, default: int, minimum: int) -> int:
    try:
        value = int(request.args.get(name, default))
    except (TypeError, ValueError):
        return default
    return max(minimum, value)


def _float_arg(name: str, *, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(request.args.get(name, default))
    except (TypeError, ValueError):
        return default
    if not math.isfinite(value):
        return default
    return min(maximum, max(minimum, value))


def _matches_filters(match: Recommendation, filters: dict[str, Any]) -> bool:
    listing = match.internship
    if filters["domain"] and listing.domain != filters["domain"]:
        return False
    if filters["location"] and filters["location"].casefold() not in listing.location.casefold():
        return False
    if filters["mode"] and listing.mode != filters["mode"]:
        return False
    if listing.stipend < filters["min_stipend"] or match.score < filters["min_score"]:
        return False
    query = filters["q"].casefold()
    if query:
        searchable = " ".join(
            [
                listing.title,
                listing.company,
                listing.location,
                listing.domain,
                listing.description,
                *listing.required_skills,
                *listing.preferred_skills,
            ]
        ).casefold()
        if query not in searchable:
            return False
    return True


def _sort_matches(matches: list[Recommendation], sort_by: str) -> None:
    if sort_by == "stipend":
        matches.sort(key=lambda match: (match.internship.stipend, match.score), reverse=True)
    elif sort_by == "newest":
        matches.sort(
            key=lambda match: (
                match.internship.posted_date,
                match.score,
            ),
            reverse=True,
        )
    elif sort_by == "title":
        matches.sort(key=lambda match: match.internship.title.casefold())
    else:
        matches.sort(key=lambda match: (match.score, match.internship.posted_date), reverse=True)
