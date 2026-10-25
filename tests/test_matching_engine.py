"""Seed loading, embedding, scoring, caching, and recommendation UI tests."""

from __future__ import annotations

import hashlib
from datetime import date

import numpy as np
import pytest

from app.extensions import db
from app.models import Internship, MatchScore, Resume, User
from app.services.embedding_service import (
    HashEmbeddingService,
    ResilientEmbeddingService,
    cosine_similarity_matrix,
    mean_embedding,
)
from app.services.job_sources.seed import SeedInternshipSource
from app.services.matching_engine import (
    load_weights,
    profile_chunks,
    score_recommendations,
    tfidf_baseline_scores,
)


class StubEmbeddingService:
    """Predictable test embedding backend that works without model downloads."""

    backend_name = "test-vector-4"

    def __init__(self):
        self.calls = 0

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        vectors = []
        for text in texts:
            digest = hashlib.blake2b(text.encode("utf-8"), digest_size=16).digest()
            vector = np.frombuffer(digest, dtype=np.uint32).astype(np.float32) + 1
            vector /= np.linalg.norm(vector)
            vectors.append(vector.tolist())
        return vectors


@pytest.fixture()
def seeded_internships(app):
    """Load internship fixture rows into the isolated test database."""
    with app.app_context():
        source = SeedInternshipSource()
        records = source.fetch_listings()[:3]
        internships = []
        for record in records:
            record["posted_date"] = date.fromisoformat(record["posted_date"])
            record.pop("source")
            internship = Internship(**record)
            db.session.add(internship)
            internships.append(internship)
        db.session.commit()
        yield internships
        db.session.rollback()


def _account_and_resume():
    user = User(
        name="Aarav Mehta",
        email="matching@example.com",
        preferred_locations=["Bengaluru"],
        preferred_domains=["Web Development"],
        internship_type="remote",
        minimum_stipend=10000,
    )
    user.set_password("strong-password")
    resume = Resume(
        user=user,
        original_filename="resume.docx",
        parsed_text="React JavaScript TypeScript HTML CSS Python",
        profile_json={
            "skills": {
                "Frontend Development": ["React", "JavaScript", "TypeScript", "HTML", "CSS"]
            },
            "projects": ["Built a React website with responsive design."],
            "experience": [],
            "education": ["B.Tech Computer Science, 2027"],
        },
        is_active=True,
    )
    db.session.add(user)
    db.session.add(resume)
    db.session.commit()
    return user, resume


def test_seed_dataset_has_more_than_80_complete_original_listings():
    listings = SeedInternshipSource().fetch_listings()

    assert len(listings) >= 80
    assert len({listing["id"] for listing in listings}) == len(listings)
    assert len({listing["domain"] for listing in listings}) >= 13
    assert all(listing["apply_url"] == "#" for listing in listings)
    assert all(listing["required_skills"] for listing in listings)


def test_resume_embedding_uses_separate_skill_project_experience_chunks():
    chunks = profile_chunks(
        {
            "skills": {"Frontend": ["React", "CSS"]},
            "projects": ["Built a portfolio site."],
            "experience": ["Tested a dashboard."],
            "summary": "Student developer.",
        }
    )

    assert chunks == [
        "Skills: CSS, React",
        "Project: Built a portfolio site.",
        "Experience: Tested a dashboard.",
        "Summary: Student developer.",
    ]


def test_embedding_helpers_normalize_vectors_and_compute_cosine_matrix():
    average = mean_embedding([[1, 0], [0, 1]])
    similarities = cosine_similarity_matrix([[1, 0]], [[1, 0], [0, 1]])

    assert np.isclose(np.linalg.norm(average), 1.0)
    assert similarities.tolist() == [[1.0, 0.0]]


def test_embedding_service_falls_back_when_fastembed_is_unavailable():
    class BrokenBackend:
        backend_name = "bge-small"

        def embed_texts(self, texts):
            raise RuntimeError("model cache unavailable")

    service = ResilientEmbeddingService(BrokenBackend(), HashEmbeddingService())
    vectors = service.embed_texts(["Python developer"])

    assert service.backend_name == "feature-hash-384"
    assert len(vectors[0]) == 384


def test_matching_weights_follow_configured_hybrid_formula():
    weights = load_weights()

    assert weights == {
        "semantic_similarity": 0.5,
        "skill_overlap": 0.3,
        "education_experience_fit": 0.1,
        "preference_fit": 0.1,
    }


def test_matching_scores_are_explainable_and_cache_by_resume_listing(app, seeded_internships):
    with app.app_context():
        user, resume = _account_and_resume()
        service = StubEmbeddingService()
        matches = score_recommendations(
            resume, user, seeded_internships, embedding_service=service
        )

        assert len(matches) == len(seeded_internships)
        assert all(0 <= match.score <= 100 for match in matches)
        assert all("required skills" in match.reason for match in matches)
        assert matches[0].matched_skills
        assert all(internship.embedding_fingerprint for internship in seeded_internships)
        assert db.session.query(MatchScore).filter_by(resume_id=resume.id).count() == 3

        scores_before = {match.internship.id: match.score for match in matches}
        cached_matches = score_recommendations(
            resume, user, seeded_internships, embedding_service=service
        )
        assert {match.internship.id: match.score for match in cached_matches} == scores_before
        assert service.calls == 3
        assert db.session.query(MatchScore).filter_by(resume_id=resume.id).count() == 3
        original_fingerprint = (
            db.session.query(MatchScore).filter_by(resume_id=resume.id).first().resume_fingerprint
        )

        resume.profile_json = {
            **resume.profile_json,
            "skills": {"Frontend Development": ["Python"]},
        }
        resume.parsed_text = "Python backend developer"
        db.session.commit()
        refreshed = score_recommendations(
            resume, user, seeded_internships, embedding_service=StubEmbeddingService()
        )
        assert db.session.query(MatchScore).filter_by(resume_id=resume.id).count() == 3
        new_fingerprint = (
            db.session.query(MatchScore).filter_by(resume_id=resume.id).first().resume_fingerprint
        )
        assert new_fingerprint != original_fingerprint
        assert len(refreshed) == len(seeded_internships)


def test_tfidf_baseline_produces_keyword_similarity_scores(app, seeded_internships):
    with app.app_context():
        _user, resume = _account_and_resume()

        scores = tfidf_baseline_scores(resume, seeded_internships)

        assert set(scores) == {internship.id for internship in seeded_internships}
        assert all(0 <= score <= 100 for score in scores.values())
        assert max(scores.values()) > 0


def test_changed_listing_content_refreshes_vector_and_cached_match(app, seeded_internships):
    with app.app_context():
        user, resume = _account_and_resume()
        service = StubEmbeddingService()
        first = score_recommendations(resume, user, seeded_internships[:1], embedding_service=service)
        old_vector = list(seeded_internships[0].embedding)
        old_fingerprint = (
            db.session.query(MatchScore)
            .filter_by(resume_id=resume.id, internship_id=seeded_internships[0].id)
            .one()
            .internship_fingerprint
        )

        seeded_internships[0].description += " The intern will also document new usability tests."
        db.session.commit()
        second = score_recommendations(
            resume, user, seeded_internships[:1], embedding_service=service
        )

        cache = (
            db.session.query(MatchScore)
            .filter_by(resume_id=resume.id, internship_id=seeded_internships[0].id)
            .one()
        )
        assert service.calls == 4
        assert seeded_internships[0].embedding != old_vector
        assert cache.internship_fingerprint != old_fingerprint
        assert len(first) == len(second) == 1


def test_seed_command_is_idempotent_without_embedding_model(app):
    runner = app.test_cli_runner()
    first = runner.invoke(args=["seed-internships", "--without-embeddings"])
    second = runner.invoke(args=["seed-internships", "--without-embeddings"])

    assert first.exit_code == 0, first.output
    assert second.exit_code == 0, second.output
    with app.app_context():
        assert db.session.query(Internship).count() == 91
        assert all(
            not internship.embedding
            for internship in db.session.scalars(db.select(Internship)).all()
        )


def test_seed_command_precomputes_embeddings_with_injected_service(app, monkeypatch):
    import app.commands as commands

    def fake_get_embedding_service(model_name, cache_dir):
        del model_name, cache_dir
        return StubEmbeddingService()

    monkeypatch.setattr(
        commands,
        "get_embedding_service",
        fake_get_embedding_service,
    )
    result = app.test_cli_runner().invoke(args=["seed-internships"])

    assert result.exit_code == 0, result.output
    with app.app_context():
        internships = db.session.scalars(db.select(Internship)).all()
        assert len(internships) == 91
        assert all(len(internship.embedding) == 4 for internship in internships)
        assert all(internship.embedding_backend == "test-vector-4" for internship in internships)
        assert all(internship.embedding_fingerprint for internship in internships)


def test_recommendations_require_active_resume_and_render_seeded_roles(client, app):
    with client.application.app_context():
        runner = client.application.test_cli_runner()
        runner.invoke(args=["seed-internships", "--without-embeddings"])
    response = client.get("/recommendations")
    assert response.status_code == 302

    client.post(
        "/register",
        data={
            "name": "Aarav Mehta",
            "email": "rec@example.com",
            "password": "strong-password",
            "confirm_password": "strong-password",
        },
    )
    with app.app_context():
        user = db.session.scalar(db.select(User).where(User.email == "rec@example.com"))
        resume = Resume(
            user_id=user.id,
            original_filename="resume.docx",
            parsed_text="React JavaScript TypeScript HTML CSS",
            profile_json={
                "skills": {"Frontend Development": ["React", "JavaScript", "TypeScript"]},
                "projects": ["Built a React website."],
                "experience": [],
            },
            is_active=True,
        )
        db.session.add(resume)
        db.session.commit()

    response = client.get("/recommendations?scoring=tfidf&domain=Web+Development&sort=title")

    assert response.status_code == 200
    assert b"Internship recommendations" in response.data
    assert b"TF-IDF cosine" in response.data
    assert b"Web Development" in response.data


def test_hybrid_recommendations_render_scores_and_skills(client, app, monkeypatch):
    import app.services.matching_engine as matching_engine

    def fake_get_embedding_service(**options):
        del options
        return HashEmbeddingService()

    monkeypatch.setattr(
        matching_engine,
        "get_embedding_service",
        fake_get_embedding_service,
    )
    client.post(
        "/register",
        data={
            "name": "Aarav Mehta",
            "email": "hybrid@example.com",
            "password": "strong-password",
            "confirm_password": "strong-password",
        },
    )
    app.test_cli_runner().invoke(args=["seed-internships", "--without-embeddings"])
    with app.app_context():
        user = db.session.scalar(db.select(User).where(User.email == "hybrid@example.com"))
        db.session.add(
            Resume(
                user_id=user.id,
                original_filename="resume.docx",
                parsed_text="React JavaScript CSS",
                profile_json={
                    "skills": {"Frontend Development": ["React", "JavaScript", "CSS"]},
                    "projects": ["Built a React web app with responsive design."],
                    "experience": [],
                },
                is_active=True,
            )
        )
        db.session.commit()

    response = client.get("/recommendations")

    assert response.status_code == 200
    assert b"Semantic" in response.data
    assert b"Skills" in response.data
    assert b"required" in response.data
    assert b"React" in response.data


def test_recommendations_filter_search_sort_and_paginate(client, app):
    client.post(
        "/register",
        data={
            "name": "Aarav Mehta",
            "email": "filter@example.com",
            "password": "strong-password",
            "confirm_password": "strong-password",
        },
    )
    app.test_cli_runner().invoke(args=["seed-internships", "--without-embeddings"])
    with app.app_context():
        user = db.session.scalar(db.select(User).where(User.email == "filter@example.com"))
        db.session.add(
            Resume(
                user_id=user.id,
                original_filename="resume.docx",
                parsed_text="Python React",
                profile_json={"skills": {"Frontend": ["React", "Python"]}, "projects": []},
                is_active=True,
            )
        )
        db.session.commit()

    response = client.get(
        "/recommendations?scoring=tfidf&q=React&mode=remote&min_stipend=0&min_score=0&sort=stipend&page=1"
    )

    assert response.status_code == 200
    assert b"matching listing" in response.data
    assert b"React" in response.data
