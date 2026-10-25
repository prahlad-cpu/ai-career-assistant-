"""Transparent rule-based ATS compatibility scoring for parsed resumes."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.models import Resume

ACTION_VERBS = re.compile(
    r"^(?:built|created|developed|designed|implemented|improved|led|launched|"
    r"managed|optimized|organized|reduced|increased|analyzed|automated|"
    r"delivered|deployed|tested|wrote|configured|collaborated|conducted)\b",
    re.IGNORECASE,
)
QUANTIFIED_IMPACT = re.compile(
    r"\b\d+(?:[,.]\d+)?\s*(?:%|percent|users?|customers?|projects?|"
    r"hours?|days?|weeks?|months?|years?|records?|requests?|x\b)",
    re.IGNORECASE,
)
PIPE_FORMATTING = re.compile(r"\s\|\s")


@dataclass(frozen=True)
class ATSCheck:
    """One weighted ATS checklist item and its improvement guidance."""

    label: str
    score: int
    weight: int
    detail: str
    fix: str


@dataclass(frozen=True)
class ATSReport:
    """A complete, explainable ATS score and prioritized fixes."""

    score: int
    checks: list[ATSCheck]
    top_fixes: list[str]
    target_title: str | None


def score_resume(
    resume: Resume,
    target_skills: list[str] | None = None,
    target_title: str | None = None,
) -> ATSReport:
    """Score ATS-relevant resume evidence from the stored, parsed profile."""
    profile = resume.profile_json or {}
    sections = {item.casefold() for item in _strings(profile.get("sections"))}
    skills_by_category = profile.get("skills")
    if not isinstance(skills_by_category, dict):
        skills_by_category = {}
    resume_skills = {
        skill.casefold()
        for values in skills_by_category.values()
        if isinstance(values, list)
        for skill in values
        if isinstance(skill, str)
    }
    email = isinstance(profile.get("email"), str) and bool(profile["email"].strip())
    phone = isinstance(profile.get("phone"), str) and bool(profile["phone"].strip())
    links = profile.get("links")
    links = links if isinstance(links, dict) else {}
    has_professional_link = bool(_strings(links.get("linkedin")) or _strings(links.get("github")))
    contact_score = sum((5 if email else 0, 5 if phone else 0, 5 if has_professional_link else 0))

    structured_sections = {
        section
        for section, key in (
            ("education", "education"),
            ("skills", "skills"),
            ("projects", "projects"),
            ("experience", "experience"),
            ("certifications", "certifications"),
            ("summary", "summary"),
        )
        if _strings(profile.get(key)) or (key == "skills" and resume_skills)
    }
    detected_sections = sections | structured_sections
    standard_sections = detected_sections & {
        "education",
        "skills",
        "projects",
        "experience",
        "certifications",
        "summary",
    }
    section_score = min(100, round(len(standard_sections) / 4 * 100))

    skill_count_score = min(100, round(len(resume_skills) / 8 * 100))
    skill_section_score = 100 if "skills" in detected_sections else 0
    target_set = {
        skill.strip().casefold()
        for skill in target_skills or []
        if isinstance(skill, str) and skill.strip()
    }
    if target_set:
        target_coverage = round(100 * len(resume_skills & target_set) / len(target_set))
        skills_score = round(0.4 * skill_section_score + 0.25 * skill_count_score + 0.35 * target_coverage)
        skills_detail = (
            f"{len(resume_skills)} detected skills; {len(resume_skills & target_set)} of "
            f"{len(target_set)} target skills found."
        )
        skills_fix = "Add relevant target skills only where your experience supports them, and keep a clearly labeled skills section."
    else:
        skills_score = round(0.45 * skill_section_score + 0.55 * skill_count_score)
        skills_detail = f"{len(resume_skills)} taxonomy skills detected; a dedicated skills section improves parsing."
        skills_fix = "Add a dedicated skills section with the tools and technologies you can demonstrate."

    impact_lines = _strings(profile.get("projects")) + _strings(profile.get("experience"))
    action_count = sum(bool(ACTION_VERBS.search(line.lstrip("-•* ").strip())) for line in impact_lines)
    metric_count = sum(bool(QUANTIFIED_IMPACT.search(line)) for line in impact_lines)
    action_score = min(100, round(action_count / max(1, min(4, len(impact_lines))) * 100))
    metric_score = min(100, round(metric_count / max(1, min(2, len(impact_lines))) * 100))
    impact_score = round((action_score + metric_score) / 2)

    parsed_text = resume.parsed_text or ""
    word_count = len(parsed_text.split())
    if word_count == 0:
        length_score = 0
    elif 250 <= word_count <= 900:
        length_score = 100
    elif 150 <= word_count <= 1100:
        length_score = 70
    else:
        length_score = 35
    bullet_count = len(impact_lines)
    density_score = min(100, round(bullet_count / 4 * 100)) if bullet_count else 0
    length_density_score = round(0.65 * length_score + 0.35 * density_score)

    lines = parsed_text.splitlines()
    long_lines = sum(len(line) > 160 for line in lines)
    table_like_lines = sum(bool(PIPE_FORMATTING.search(line)) for line in lines)
    formatting_score = (
        0
        if not parsed_text.strip()
        else 100
        if not long_lines and not table_like_lines
        else max(0, 100 - 25 * long_lines - 20 * table_like_lines)
    )

    checks = [
        ATSCheck(
            "Contact information", contact_score * 100 // 15, 15,
            "Email, phone, and at least one LinkedIn or GitHub link are checked.",
            "Add a professional email, phone number, and LinkedIn or GitHub link near the top.",
        ),
        ATSCheck(
            "Standard sections", section_score, 20,
            f"{len(standard_sections)} standard sections detected.",
            "Use clear headings such as Education, Skills, Projects, and Experience.",
        ),
        ATSCheck(
            "Skills and target keywords", skills_score, 20, skills_detail,
            skills_fix,
        ),
        ATSCheck(
            "Action verbs and quantified impact", impact_score, 20,
            f"{action_count} project/experience entries start with an action verb; "
            f"{metric_count} include a measurable result.",
            "Start project and experience bullets with action verbs and add real, verifiable results where available.",
        ),
        ATSCheck(
            "Length and bullet density", length_density_score, 15,
            f"{word_count} words and {bullet_count} project/experience entries detected.",
            "Keep a student resume concise (roughly one page) and use readable, focused bullets.",
        ),
        ATSCheck(
            "Text-based formatting checks", formatting_score, 10,
            "Text checks found no obvious long lines or table separators. Layout, columns, and images cannot be verified from extracted text.",
            "Prefer a single-column layout with standard headings; visual layout is not retained in the parsed resume.",
        ),
    ]
    score = round(sum(check.score * check.weight for check in checks) / sum(
        check.weight for check in checks
    ))
    fix_checks = [check for check in checks if check.score < 100]
    fix_checks.sort(key=lambda check: (check.score, -check.weight))
    top_fixes = [check.fix for check in fix_checks[:5]]
    return ATSReport(
        score=score,
        checks=checks,
        top_fixes=top_fixes,
        target_title=target_title if target_set else None,
    )


def _strings(value: Any) -> list[str]:
    if isinstance(value, list):
        return [item.strip() for item in value if isinstance(item, str) and item.strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []
