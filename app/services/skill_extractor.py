"""Curated taxonomy loader and deterministic resume skill extraction."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import TypedDict


class Taxonomy(TypedDict):
    """Canonical skill names, categories, aliases, and match patterns."""

    categories: dict[str, list[str]]
    aliases: dict[str, str]
    patterns: list[tuple[re.Pattern[str], str, str]]


TAXONOMY_PATH = Path(__file__).resolve().parents[2] / "data" / "skills_taxonomy.json"


@lru_cache(maxsize=1)
def load_taxonomy() -> Taxonomy:
    """Load the version-controlled skill taxonomy and compile its match rules."""
    with TAXONOMY_PATH.open(encoding="utf-8") as taxonomy_file:
        raw = json.load(taxonomy_file)
    categories: dict[str, list[str]] = raw["categories"]
    canonical_categories = {
        skill.casefold(): category
        for category, skills in categories.items()
        for skill in skills
    }
    aliases: dict[str, str] = {
        alias.casefold(): canonical
        for alias, canonical in raw.get("aliases", {}).items()
    }
    invalid_aliases = [
        alias for alias, canonical in aliases.items() if canonical.casefold() not in canonical_categories
    ]
    if invalid_aliases:
        raise ValueError(f"Skill taxonomy aliases reference unknown skills: {invalid_aliases}")

    terms: dict[str, str] = {
        skill: skill for skills in categories.values() for skill in skills
    }
    terms.update({alias: canonical for alias, canonical in aliases.items()})
    patterns = [
        (
            re.compile(rf"(?<!\w){re.escape(term)}(?!\w)", re.IGNORECASE),
            canonical,
            canonical_categories[canonical.casefold()],
        )
        for term, canonical in sorted(terms.items(), key=lambda item: len(item[0]), reverse=True)
    ]
    return {"categories": categories, "aliases": aliases, "patterns": patterns}


def extract_skills(text: str) -> dict[str, list[str]]:
    """Extract canonical skills from resume text, grouped by taxonomy category."""
    taxonomy = load_taxonomy()
    found: dict[str, set[str]] = {}
    for pattern, canonical, category in taxonomy["patterns"]:
        if pattern.search(text):
            found.setdefault(category, set()).add(canonical)
    return {
        category: sorted(skills, key=str.casefold)
        for category, skills in sorted(found.items())
    }


def canonicalize_skill(skill: str) -> str | None:
    """Resolve a skill name or configured alias to its canonical name."""
    taxonomy = load_taxonomy()
    normalized = skill.strip().casefold()
    for skills in taxonomy["categories"].values():
        for canonical in skills:
            if canonical.casefold() == normalized:
                return canonical
    canonical = taxonomy["aliases"].get(normalized)
    return canonical
