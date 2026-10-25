"""Shared interface for internship listing sources."""

from __future__ import annotations

from typing import Any, Protocol


class InternshipSource(Protocol):
    """An adapter that returns normalized internship listing dictionaries."""

    def fetch_listings(self) -> list[dict[str, Any]]:
        """Load listing records from the source."""
