"""Internship listings and stored recommendation scores."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import (
    Date,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db


class Internship(db.Model):
    """A seed or future adapter-sourced internship listing."""

    __tablename__ = "internships"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    title: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    company: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    location: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    mode: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    stipend: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration: Mapped[str] = mapped_column(String(80), nullable=False)
    domain: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    required_skills: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    preferred_skills: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    min_education: Mapped[str] = mapped_column(String(80), nullable=False)
    posted_date: Mapped[date] = mapped_column(Date, nullable=False)
    apply_url: Mapped[str] = mapped_column(String(500), nullable=False, default="#")
    embedding: Mapped[list[float] | None] = mapped_column(JSON)
    embedding_backend: Mapped[str | None] = mapped_column(String(80))
    embedding_fingerprint: Mapped[str | None] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(40), nullable=False, default="seed")


class MatchScore(db.Model):
    """Cached recommendation scores for one resume and one internship."""

    __tablename__ = "match_scores"
    __table_args__ = (
        UniqueConstraint("resume_id", "internship_id", name="uq_match_resume_internship"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    resume_id: Mapped[int] = mapped_column(
        ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    internship_id: Mapped[str] = mapped_column(
        ForeignKey("internships.id", ondelete="CASCADE"), nullable=False, index=True
    )
    resume_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    internship_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    final_score: Mapped[float] = mapped_column(Float, nullable=False)
    breakdown: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
