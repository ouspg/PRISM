"""Pydantic models for the inflection point catalog."""

from __future__ import annotations

import datetime
from typing import Literal

from pydantic import BaseModel, Field


class InflectionPoint(BaseModel):
    """A single AI inflection point with metadata."""

    id: str
    date: datetime.date
    label: str
    category: str
    subcategory: str | None = None
    scope: Literal["global", "platform-specific", "org-specific"] = "global"
    confidence: Literal["high", "medium", "low"] = "medium"
    tier: Literal[1, 2, 3] | None = Field(
        default=None,
        description=(
            "Regression tier: 1 = primary ITS regressor, "
            "2 = robustness check only, 3 = descriptive context only."
        ),
    )
    era: str | None = Field(
        default=None,
        description="Named research era this event belongs to.",
    )
    evidence_url: str | None = None
    tags: list[str] = Field(default_factory=list)
    notes: str | None = None


class Catalog(BaseModel):
    """Collection of inflection points with filtering helpers."""

    inflection_points: list[InflectionPoint]

    def filter_by_date_range(
        self, start: datetime.date, end: datetime.date
    ) -> Catalog:
        """Return a new Catalog containing only points within [start, end]."""
        filtered = [
            p for p in self.inflection_points if start <= p.date <= end
        ]
        return Catalog(inflection_points=filtered)

    def filter_by_category(self, category: str) -> Catalog:
        """Return a new Catalog containing only points matching *category*."""
        filtered = [
            p for p in self.inflection_points if p.category == category
        ]
        return Catalog(inflection_points=filtered)

    def filter_by_tier(self, tier: int) -> Catalog:
        """Return a new Catalog containing only points at or below *tier*."""
        filtered = [
            p for p in self.inflection_points if p.tier is not None and p.tier <= tier
        ]
        return Catalog(inflection_points=filtered)

    def filter_by_era(self, era: str) -> Catalog:
        """Return a new Catalog containing only points in *era*."""
        filtered = [p for p in self.inflection_points if p.era == era]
        return Catalog(inflection_points=filtered)

    def get_by_id(self, point_id: str) -> InflectionPoint | None:
        """Look up an inflection point by its id."""
        for p in self.inflection_points:
            if p.id == point_id:
                return p
        return None

    def __len__(self) -> int:
        return len(self.inflection_points)

    def __iter__(self):
        return iter(self.inflection_points)
