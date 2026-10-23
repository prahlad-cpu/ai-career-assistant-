"""Account and student profile model."""

from __future__ import annotations

from datetime import datetime, timezone

from flask_login import UserMixin
from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db


class User(UserMixin, db.Model):
    """A registered student and their internship preferences."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    college: Mapped[str | None] = mapped_column(String(160))
    degree: Mapped[str | None] = mapped_column(String(120))
    branch: Mapped[str | None] = mapped_column(String(120))
    graduation_year: Mapped[int | None] = mapped_column(Integer)
    preferred_locations: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    preferred_domains: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    internship_type: Mapped[str | None] = mapped_column(String(20))
    minimum_stipend: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    resumes: Mapped[list[Resume]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def set_password(self, password: str) -> None:
        """Store a one-way hash of a password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Check a password against the stored hash."""
        return check_password_hash(self.password_hash, password)
