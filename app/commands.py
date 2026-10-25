"""Flask CLI commands for internship data maintenance."""

from __future__ import annotations

from datetime import date

import click
from flask import Flask, current_app
from flask.cli import with_appcontext
from sqlalchemy import delete, select

from app.extensions import db
from app.models import Internship, MatchScore
from app.services.embedding_service import get_embedding_service
from app.services.job_sources.seed import SeedInternshipSource
from app.services.matching_engine import content_fingerprint, internship_text


def register_commands(app: Flask) -> None:
    """Register data maintenance commands on the Flask app."""

    @app.cli.command("seed-internships")
    @with_appcontext
    @click.option(
        "--without-embeddings",
        is_flag=True,
        help="Load listings only; use this for an offline database bootstrap.",
    )
    def seed_internships(without_embeddings: bool = False) -> None:
        """Load the original internship dataset and precompute embeddings."""
        source = SeedInternshipSource()
        listings = source.fetch_listings()
        ids = {listing["id"] for listing in listings}
        existing_seeded = db.session.scalars(
            select(Internship).where(Internship.source == "seed")
        ).all()
        for stale in existing_seeded:
            if stale.id not in ids:
                db.session.execute(
                    delete(MatchScore).where(MatchScore.internship_id == stale.id)
                )
                db.session.delete(stale)

        by_id = {internship.id: internship for internship in existing_seeded}
        for item in listings:
            internship = by_id.get(item["id"])
            if internship is None:
                internship = Internship(id=item["id"])
                db.session.add(internship)
            for field in (
                "title",
                "company",
                "location",
                "mode",
                "stipend",
                "duration",
                "domain",
                "description",
                "required_skills",
                "preferred_skills",
                "min_education",
                "apply_url",
                "source",
            ):
                setattr(internship, field, item[field])
            internship.posted_date = date.fromisoformat(item["posted_date"])
            if without_embeddings:
                internship.embedding = None
                internship.embedding_backend = None
                internship.embedding_fingerprint = None
        db.session.flush()

        if not without_embeddings:
            service = get_embedding_service(
                model_name=current_app.config["EMBEDDING_MODEL"],
                cache_dir=current_app.config["EMBEDDING_CACHE_DIR"],
            )
            db_internships = [by_id.get(item["id"]) for item in listings]
            db_internships = [
                internship or db.session.get(Internship, item["id"])
                for internship, item in zip(db_internships, listings)
            ]
            vectors = service.embed_texts(
                [internship_text(internship) for internship in db_internships]
            )
            backend = service.backend_name
            for internship, vector in zip(db_internships, vectors):
                internship.embedding = vector
                internship.embedding_backend = backend
                internship.embedding_fingerprint = content_fingerprint(internship_text(internship))

        db.session.commit()
        mode = "loaded without embeddings" if without_embeddings else f"embedded with {backend}"
        click.echo(f"Seeded {len(listings)} internships ({mode}).")
