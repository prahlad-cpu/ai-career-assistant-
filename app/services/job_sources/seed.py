"""Version-controlled internship seed data source."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.services.skill_extractor import canonicalize_skill, extract_skills

SEED_DATA_PATH = Path(__file__).resolve().parents[3] / "data" / "internships_seed.json"
VALID_MODES = {"remote", "onsite", "hybrid"}


class SeedInternshipSource:
    """Load and validate the repository's original internship seed listings."""

    def __init__(self, path: Path = SEED_DATA_PATH) -> None:
        self.path = path

    def fetch_listings(self) -> list[dict[str, Any]]:
        """Read, normalize, and validate the seed dataset."""
        with self.path.open(encoding="utf-8") as seed_file:
            listings = json.load(seed_file)
        if not isinstance(listings, list) or not listings:
            raise ValueError("Internship seed data must be a non-empty JSON list.")

        seen_ids: set[str] = set()
        normalized: list[dict[str, Any]] = []
        required_fields = {
            "id",
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
            "posted_date",
            "apply_url",
        }
        for listing in listings:
            if not isinstance(listing, dict) or not required_fields.issubset(listing):
                raise ValueError("An internship seed listing is missing required fields.")
            listing_id = str(listing["id"]).strip()
            if not listing_id or listing_id in seen_ids:
                raise ValueError(f"Internship seed ID is empty or duplicated: {listing_id!r}.")
            seen_ids.add(listing_id)
            if listing["mode"] not in VALID_MODES:
                raise ValueError(f"Invalid work mode for internship {listing_id}.")
            required_skills = _canonical_skills(listing["required_skills"])
            preferred_skills = _canonical_skills(listing["preferred_skills"])
            extracted = {
                skill
                for category_skills in extract_skills(listing["description"]).values()
                for skill in category_skills
            }
            required_skills = sorted(set(required_skills) | extracted, key=str.casefold)
            normalized.append(
                {
                    **listing,
                    "id": listing_id,
                    "stipend": int(listing["stipend"]),
                    "required_skills": required_skills,
                    "preferred_skills": preferred_skills,
                    "apply_url": listing["apply_url"] or "#",
                    "source": "seed",
                }
            )
        return normalized


def _canonical_skills(skills: list[str]) -> list[str]:
    if not isinstance(skills, list):
        raise ValueError("Internship skills must be provided as a list.")
    canonical = [canonicalize_skill(skill) for skill in skills]
    if any(skill is None for skill in canonical):
        unknown = [source for source, target in zip(skills, canonical) if target is None]
        raise ValueError(f"Unknown internship skills in seed data: {unknown}.")
    return sorted(set(skill for skill in canonical if skill is not None), key=str.casefold)
