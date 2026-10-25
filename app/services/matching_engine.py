"""Explainable hybrid internship recommendation and score caching."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from flask import current_app, has_app_context

from app.extensions import db
from app.models import Internship, MatchScore, Resume, User
from app.services.embedding_service import (
    EmbeddingService,
    cosine_similarity_matrix,
    get_embedding_service,
    mean_embedding,
)

WEIGHTS_PATH = Path(__file__).resolve().parents[2] / "config" / "matching.yaml"
TOKEN_PATTERN = re.compile(r"[a-z0-9+#.]+", re.IGNORECASE)


@dataclass(frozen=True)
class Recommendation:
    """One scored internship with transparent evidence and sub-scores."""

    internship: Internship
    score: float
    semantic_similarity: float
    skill_overlap: float
    education_experience_fit: float
    preference_fit: float
    matched_skills: list[str]
    missing_required_skills: list[str]
    matched_preferred_skills: list[str]
    reason: str

    def as_breakdown(self) -> dict[str, Any]:
        """Return the serializable score explanation used by the match cache."""
        return {
            "score": self.score,
            "semantic_similarity": self.semantic_similarity,
            "skill_overlap": self.skill_overlap,
            "education_experience_fit": self.education_experience_fit,
            "preference_fit": self.preference_fit,
            "matched_skills": self.matched_skills,
            "missing_required_skills": self.missing_required_skills,
            "matched_preferred_skills": self.matched_preferred_skills,
            "reason": self.reason,
        }


def load_weights(path: Path = WEIGHTS_PATH) -> dict[str, float]:
    """Load and validate configured hybrid scoring weights."""
    weights: dict[str, float] = {}
    in_weights = False
    with path.open(encoding="utf-8") as config_file:
        for line in config_file:
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            if not line.startswith((" ", "\t")):
                in_weights = line.strip() == "weights:"
                continue
            if in_weights:
                key, separator, value = line.strip().partition(":")
                if not separator:
                    raise ValueError("Matching weights config contains an invalid entry.")
                try:
                    weights[key.strip()] = float(value.strip())
                except ValueError as error:
                    raise ValueError(f"Matching weight {key.strip()!r} must be numeric.") from error
    expected = {
        "semantic_similarity",
        "skill_overlap",
        "education_experience_fit",
        "preference_fit",
    }
    if set(weights) != expected or not np.isclose(sum(weights.values()), 1.0):
        raise ValueError("Matching weights must define all four components and sum to 1.0.")
    if any(not isinstance(weight, (float, int)) or weight < 0 for weight in weights.values()):
        raise ValueError("Matching weights must be non-negative numbers.")
    return {name: float(weight) for name, weight in weights.items()}


def profile_chunks(profile: dict[str, Any], parsed_text: str | None = None) -> list[str]:
    """Build separate skills, project, and experience text chunks for embedding."""
    chunks: list[str] = []
    skills = [
        skill
        for category_skills in profile.get("skills", {}).values()
        for skill in category_skills
    ]
    if skills:
        chunks.append("Skills: " + ", ".join(sorted(set(skills), key=str.casefold)))
    projects = _string_entries(profile.get("projects"))
    if projects:
        chunks.extend(f"Project: {entry}" for entry in projects)
    experience = _string_entries(profile.get("experience"))
    if experience:
        chunks.extend(f"Experience: {entry}" for entry in experience)
    summary = profile.get("summary")
    if isinstance(summary, str) and summary.strip():
        chunks.append(f"Summary: {summary.strip()}")
    if not chunks:
        education = _string_entries(profile.get("education"))
        chunks.extend(f"Education: {entry}" for entry in education)
    if not chunks and parsed_text:
        chunks.extend(
            part.strip()
            for part in parsed_text.splitlines()
            if len(part.strip()) >= 12
        )
    return chunks or ["Student seeking an internship opportunity."]


def internship_text(internship: Internship) -> str:
    """Build a focused semantic representation of an internship listing."""
    return " ".join(
        [
            internship.title,
            internship.domain,
            internship.description,
            "Required skills: " + ", ".join(internship.required_skills),
            "Preferred skills: " + ", ".join(internship.preferred_skills),
        ]
    )


def score_recommendations(
    resume: Resume,
    user: User,
    internships: list[Internship],
    *,
    embedding_service: EmbeddingService | None = None,
    weights: dict[str, float] | None = None,
) -> list[Recommendation]:
    """Calculate and persist cached hybrid recommendations for a resume."""
    if not internships:
        return []
    if embedding_service is None:
        if has_app_context():
            embedding_service = get_embedding_service(
                model_name=current_app.config["EMBEDDING_MODEL"],
                cache_dir=current_app.config["EMBEDDING_CACHE_DIR"],
            )
        else:
            embedding_service = get_embedding_service()
    weights = weights or load_weights()
    profile = resume.profile_json or {}
    resume_hash = content_fingerprint(
        {"profile": profile, "parsed_text": resume.parsed_text or ""}
    )
    query_vector = mean_embedding(embedding_service.embed_texts(profile_chunks(profile, resume.parsed_text)))

    backend = embedding_service.backend_name
    needs_embeddings = [
        internship
        for internship in internships
        if not internship.embedding
        or internship.embedding_backend != backend
        or len(internship.embedding) != len(query_vector)
        or internship.embedding_fingerprint != content_fingerprint(internship_text(internship))
    ]
    if needs_embeddings:
        vectors = embedding_service.embed_texts(
            [internship_text(internship) for internship in needs_embeddings]
        )
        backend = embedding_service.backend_name
        for internship, vector in zip(needs_embeddings, vectors):
            internship.embedding = vector
            internship.embedding_backend = backend
            internship.embedding_fingerprint = content_fingerprint(internship_text(internship))
        db.session.flush()
    internship_hashes = {
        internship.id: content_fingerprint(
            {
                "title": internship.title,
                "company": internship.company,
                "location": internship.location,
                "mode": internship.mode,
                "stipend": internship.stipend,
                "min_education": internship.min_education,
                "domain": internship.domain,
                "description": internship.description,
                "required_skills": internship.required_skills,
                "preferred_skills": internship.preferred_skills,
                "embedding_backend": internship.embedding_backend,
                "embedding_fingerprint": internship.embedding_fingerprint,
            }
        )
        for internship in internships
    }

    cached_scores = {
        score.internship_id: score
        for score in db.session.query(MatchScore)
        .filter(MatchScore.resume_id == resume.id)
        .all()
    }
    uncached = []
    for internship in internships:
        score = cached_scores.get(internship.id)
        internship_hash = internship_hashes[internship.id]
        if (
            score is None
            or score.resume_fingerprint != resume_hash
            or score.internship_fingerprint != internship_hash
        ):
            uncached.append(internship)

    all_similarities = cosine_similarity_matrix(
        [query_vector], [internship.embedding or [] for internship in internships]
    )[0]
    semantic_scores = {
        internship.id: float(score)
        for internship, score in zip(
            internships, _calibrate_semantic_scores(all_similarities)
        )
    }
    if uncached:
        for internship in uncached:
            recommendation = _score_one(
                resume,
                user,
                internship,
                semantic_scores[internship.id],
                weights,
            )
            cache = cached_scores.get(internship.id)
            if cache is None:
                cache = MatchScore(
                    resume_id=resume.id,
                    internship_id=internship.id,
                    resume_fingerprint=resume_hash,
                    internship_fingerprint=internship_hashes[internship.id],
                    final_score=recommendation.score,
                    breakdown=recommendation.as_breakdown(),
                )
                db.session.add(cache)
            else:
                cache.resume_fingerprint = resume_hash
                cache.internship_fingerprint = internship_hashes[internship.id]
                cache.final_score = recommendation.score
                cache.breakdown = recommendation.as_breakdown()
        db.session.commit()

    recommendations: list[Recommendation] = []
    for internship in internships:
        cached = cached_scores.get(internship.id)
        if cached is None:
            cached = db.session.query(MatchScore).filter_by(
                resume_id=resume.id, internship_id=internship.id
            ).one()
        values = cached.breakdown
        recommendations.append(
            Recommendation(
                internship=internship,
                score=float(cached.final_score),
                semantic_similarity=values["semantic_similarity"],
                skill_overlap=values["skill_overlap"],
                education_experience_fit=values["education_experience_fit"],
                preference_fit=values["preference_fit"],
                matched_skills=values["matched_skills"],
                missing_required_skills=values["missing_required_skills"],
                matched_preferred_skills=values["matched_preferred_skills"],
                reason=values["reason"],
            )
        )
    return recommendations


def tfidf_baseline_scores(
    resume: Resume, internships: list[Internship]
) -> dict[str, float]:
    """Return TF-IDF cosine scores for the optional keyword-only baseline."""
    profile = resume.profile_json or {}
    resume_text = " ".join(
        [
            resume.parsed_text or "",
            *(
                skill
                for values in profile.get("skills", {}).values()
                for skill in values
            ),
        ]
    )
    documents = [
        " ".join(
            [
                internship.title,
                internship.description,
                *internship.required_skills,
                *internship.preferred_skills,
            ]
        )
        for internship in internships
    ]
    tokenized = [TOKEN_PATTERN.findall(text.casefold()) for text in [resume_text, *documents]]
    document_frequency = Counter(
        token for tokens in tokenized for token in set(tokens)
    )
    document_count = len(tokenized)

    def vectorize(tokens: list[str]) -> dict[str, float]:
        counts = Counter(tokens)
        weighted = {
            token: (1 + math.log(count))
            * (math.log((document_count + 1) / (document_frequency[token] + 1)) + 1)
            for token, count in counts.items()
        }
        norm = math.sqrt(sum(value * value for value in weighted.values()))
        return {token: value / norm for token, value in weighted.items()} if norm else {}

    resume_vector = vectorize(tokenized[0])
    result: dict[str, float] = {}
    for internship, tokens in zip(internships, tokenized[1:]):
        job_vector = vectorize(tokens)
        similarity = sum(
            value * job_vector.get(token, 0.0) for token, value in resume_vector.items()
        )
        result[internship.id] = round(float(similarity * 100), 2)
    return result


def _score_one(
    resume: Resume,
    user: User,
    internship: Internship,
    semantic_score: float,
    weights: dict[str, float],
) -> Recommendation:
    profile = resume.profile_json or {}
    student_skills = {
        skill.casefold()
        for category_skills in profile.get("skills", {}).values()
        for skill in category_skills
    }
    required = list(internship.required_skills or [])
    preferred = list(internship.preferred_skills or [])
    matched_required = [skill for skill in required if skill.casefold() in student_skills]
    matched_preferred = [skill for skill in preferred if skill.casefold() in student_skills]
    missing_required = [skill for skill in required if skill.casefold() not in student_skills]
    total_weight = 2 * len(required) + len(preferred)
    skill_score = (
        100.0 * (2 * len(matched_required) + len(matched_preferred)) / total_weight
        if total_weight
        else 0.0
    )
    education_fit = _education_experience_fit(profile, internship.min_education)
    preference_fit = _preference_fit(user, internship)
    parts = {
        "semantic_similarity": semantic_score,
        "skill_overlap": skill_score,
        "education_experience_fit": education_fit,
        "preference_fit": preference_fit,
    }
    final_score = sum(weights[key] * value for key, value in parts.items())
    required_text = (
        f"{len(matched_required)}/{len(required)} required skills"
        if required
        else f"{len(matched_preferred)} preferred skills"
    )
    project_entries = _string_entries(profile.get("projects"))
    domain_hint = "projects and experience"
    if project_entries and internship.domain:
        domain_hint = f"your projects align with {internship.domain}"
    strength = "Strong match" if final_score >= 70 else "Potential match" if final_score >= 45 else "Skill-building opportunity"
    reason = f"{strength}: {required_text}; {domain_hint}."
    return Recommendation(
        internship=internship,
        score=round(float(np.clip(final_score, 0, 100)), 1),
        semantic_similarity=round(float(semantic_score), 1),
        skill_overlap=round(float(skill_score), 1),
        education_experience_fit=round(float(education_fit), 1),
        preference_fit=round(float(preference_fit), 1),
        matched_skills=matched_required,
        missing_required_skills=missing_required,
        matched_preferred_skills=matched_preferred,
        reason=reason,
    )


def _calibrate_semantic_scores(similarities: np.ndarray) -> np.ndarray:
    """Spread corpus cosine similarities robustly over a 0–100 scale."""
    low, high = np.percentile(similarities, [5, 95])
    if high - low < 0.05:
        return np.clip((similarities + 1.0) * 50.0, 0.0, 100.0)
    return np.clip((similarities - low) / (high - low) * 100.0, 0.0, 100.0)


def _education_experience_fit(profile: dict[str, Any], minimum_education: str) -> float:
    entries = _string_entries(profile.get("education"))
    education = " ".join(entries).casefold()
    required = minimum_education.casefold()
    if not entries or "bachelor" in required or "undergraduate" in required:
        education_score = 75.0 if entries else 55.0
    elif "master" in required and any(token in education for token in ("master", "phd", "doctor")):
        education_score = 100.0
    else:
        education_score = 80.0
    has_experience = bool(
        _string_entries(profile.get("experience")) or _string_entries(profile.get("projects"))
    )
    return 0.7 * education_score + (30.0 if has_experience else 0.0)


def _preference_fit(user: User, internship: Internship) -> float:
    dimensions: list[float] = []
    locations = [value.casefold() for value in (user.preferred_locations or [])]
    if locations:
        job_location = internship.location.casefold()
        dimensions.append(
            100.0 if any(value == job_location or value in job_location for value in locations) else 0.0
        )
    if user.internship_type:
        dimensions.append(100.0 if user.internship_type.casefold() == internship.mode.casefold() else 0.0)
    if user.minimum_stipend is not None:
        dimensions.append(
            100.0 if internship.stipend >= user.minimum_stipend else
            50.0 * internship.stipend / max(user.minimum_stipend, 1)
        )
    domains = [value.casefold() for value in (user.preferred_domains or [])]
    if domains:
        normalized_domain = internship.domain.casefold()
        dimensions.append(
            100.0 if any(value in normalized_domain or normalized_domain in value for value in domains) else 0.0
        )
    return float(np.mean(dimensions)) if dimensions else 70.0


def _string_entries(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [entry.strip() for entry in value if isinstance(entry, str) and entry.strip()]


def content_fingerprint(value: Any) -> str:
    """Return a stable hash for cache and embedding invalidation."""
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
