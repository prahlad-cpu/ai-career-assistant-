"""Taxonomy-driven skill gap classification and learning-plan suggestions."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from urllib.parse import quote_plus

from app.services.skill_extractor import canonicalize_skill, load_taxonomy

PREFERRED_CONTEXT = (
    "preferred", "nice to have", "nice-to-have", "bonus", "optional", "ideally", "desired"
)


@dataclass(frozen=True)
class SkillAssessment:
    """A job skill's status, priority, and learning resources."""

    name: str
    requirement: str
    status: str
    related_skill: str | None
    priority: str
    why_it_matters: str
    estimated_time: str
    resources: list[tuple[str, str]]


@dataclass(frozen=True)
class SkillGapReport:
    """Matched/partial/missing skill counts and a prioritized plan."""

    assessments: list[SkillAssessment]
    learning_plan: list[SkillAssessment]
    readiness: int
    matched_count: int
    partial_count: int
    missing_count: int
    has_job_skills: bool


def analyze_skill_gap(
    profile: dict[str, object],
    required_skills: list[str],
    preferred_skills: list[str] | None = None,
) -> SkillGapReport:
    """Compare parsed resume skills to a role and calculate readiness."""
    student_skills: dict[str, str] = {}
    raw_skills = profile.get("skills")
    if isinstance(raw_skills, dict):
        for values in raw_skills.values():
            if isinstance(values, list):
                for value in values:
                    if isinstance(value, str) and value.strip():
                        canonical = canonicalize_skill(value) or value.strip()
                        student_skills.setdefault(canonical.casefold(), canonical)

    role_skills: list[tuple[str, str]] = []
    seen: set[str] = set()
    for requirement, skills in (
        ("required", required_skills),
        ("preferred", preferred_skills or []),
    ):
        for value in skills:
            canonical = canonicalize_skill(value) or value.strip()
            key = canonical.casefold()
            if canonical and key not in seen:
                seen.add(key)
                role_skills.append((canonical, requirement))

    assessments: list[SkillAssessment] = []
    for name, requirement in role_skills:
        exact = student_skills.get(name.casefold())
        related = None if exact else _closest_related_skill(name, list(student_skills.values()))
        status = "matched" if exact else "partial" if related else "missing"
        priority = _priority(requirement, status)
        assessments.append(
            SkillAssessment(
                name=name,
                requirement=requirement,
                status=status,
                related_skill=related,
                priority=priority,
                why_it_matters=(
                    f"{name} is listed as a {requirement} role skill and is relevant to the day-to-day work."
                ),
                estimated_time=_learning_estimate(name),
                resources=_learning_resources(name),
            )
        )
    learning_plan = sorted(
        (item for item in assessments if item.status != "matched"),
        key=lambda item: (
            {"High": 0, "Medium": 1, "Low": 2}[item.priority],
            item.name.casefold(),
        ),
    )
    weight_total = sum(2 if item.requirement == "required" else 1 for item in assessments)
    readiness_points = sum(
        (2 if item.requirement == "required" else 1)
        * (1 if item.status == "matched" else 0.5 if item.status == "partial" else 0)
        for item in assessments
    )
    readiness = round(100 * readiness_points / weight_total) if weight_total else 0
    return SkillGapReport(
        assessments=assessments,
        learning_plan=learning_plan,
        readiness=readiness,
        matched_count=sum(item.status == "matched" for item in assessments),
        partial_count=sum(item.status == "partial" for item in assessments),
        missing_count=sum(item.status == "missing" for item in assessments),
        has_job_skills=bool(assessments),
    )


def extract_job_skill_requirements(description: str) -> tuple[list[str], list[str]]:
    """Extract taxonomy skills from a pasted JD and infer preferred wording."""
    taxonomy = load_taxonomy()
    preferred: set[str] = set()
    required: set[str] = set()
    lines = description.splitlines()
    for line_index, line in enumerate(lines):
        context = " ".join(lines[max(0, line_index - 1):line_index + 1]).casefold()
        is_preferred = any(marker in context for marker in PREFERRED_CONTEXT)
        for pattern, canonical, _ in taxonomy["patterns"]:
            if pattern.search(line):
                (preferred if is_preferred else required).add(canonical)
    preferred -= required
    sort_skills = lambda values: sorted(values, key=str.casefold)
    return sort_skills(required), sort_skills(preferred)


def _closest_related_skill(target: str, candidates: list[str]) -> str | None:
    taxonomy = load_taxonomy()
    skill_categories = {
        skill.casefold(): category
        for category, skills in taxonomy["categories"].items()
        for skill in skills
    }
    target_category = skill_categories.get(target.casefold())
    target_tokens = _tokens(target)
    best: tuple[float, str] | None = None
    for candidate in candidates:
        candidate_category = skill_categories.get(candidate.casefold())
        candidate_tokens = _tokens(candidate)
        shared = target_tokens & candidate_tokens
        token_score = len(shared) / len(target_tokens | candidate_tokens) if shared else 0.0
        name_score = SequenceMatcher(None, target.casefold(), candidate.casefold()).ratio()
        category_bonus = 0.1 if target_category and target_category == candidate_category else 0.0
        similarity = max(token_score, name_score) + category_bonus
        if shared and any(len(token) >= 3 for token in shared):
            similarity = max(similarity, 0.55 + category_bonus)
        if similarity >= 0.58 and (best is None or similarity > best[0]):
            best = (similarity, candidate)
    return best[1] if best else None


def _tokens(value: str) -> set[str]:
    return {token.casefold() for token in value.replace("-", " ").replace("/", " ").split()}


def _priority(requirement: str, status: str) -> str:
    if requirement == "required":
        return "High" if status == "missing" else "Medium"
    return "Low"


def _learning_estimate(skill: str) -> str:
    category = next(
        (
            category
            for category, skills in load_taxonomy()["categories"].items()
            if skill.casefold() in {item.casefold() for item in skills}
        ),
        "",
    ).casefold()
    if any(term in category for term in ("programming", "data science", "machine learning")):
        return "2–4 weeks of focused practice"
    if any(term in category for term in ("framework", "cloud", "database")):
        return "1–3 weeks of guided practice"
    return "3–10 days for a working introduction"


def _learning_resources(skill: str) -> list[tuple[str, str]]:
    query = quote_plus(skill)
    return [
        ("Official documentation search", f"https://www.google.com/search?q={query}+official+documentation"),
        ("Video lessons search", f"https://www.youtube.com/results?search_query={query}+tutorial"),
        ("Free courses search", f"https://www.google.com/search?q={query}+free+course"),
    ]
