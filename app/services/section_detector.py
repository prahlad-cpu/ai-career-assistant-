"""Rule-based resume section detection."""

from __future__ import annotations

import re

SECTION_HEADINGS: dict[str, set[str]] = {
    "summary": {"summary", "profile", "professional summary", "career objective", "objective"},
    "education": {"education", "academic background", "academic qualifications"},
    "skills": {"skills", "technical skills", "core skills", "key skills", "technologies"},
    "projects": {"projects", "personal projects", "academic projects", "selected projects"},
    "experience": {
        "experience",
        "work experience",
        "professional experience",
        "internship experience",
        "employment history",
    },
    "certifications": {"certifications", "certificates", "licenses and certifications"},
    "achievements": {"achievements", "awards", "honors", "accomplishments"},
}
_HEADING_PREFIX = re.compile(r"^\s*(?:\d+(?:\.\d+)*[.)]?\s+|[•*-]\s*)")


def detect_sections(text: str) -> dict[str, str]:
    """Return the non-empty text grouped under recognized resume headings."""
    collected: dict[str, list[str]] = {}
    current_section: str | None = None

    for line in text.splitlines():
        heading = _HEADING_PREFIX.sub("", line).strip().rstrip(":").strip()
        normalized_heading = re.sub(r"\s+", " ", heading).casefold()
        section = next(
            (
                name
                for name, headings in SECTION_HEADINGS.items()
                if normalized_heading in headings
            ),
            None,
        )
        if section is not None:
            current_section = section
            collected.setdefault(section, [])
        elif current_section is not None:
            collected[current_section].append(line)

    return {
        name: "\n".join(lines).strip()
        for name, lines in collected.items()
        if "\n".join(lines).strip()
    }
