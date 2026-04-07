"""Tests for catalog schema, loader, and validation."""

import datetime
import tempfile
from pathlib import Path

import pytest
import yaml

from prism_analyze.catalog.loader import load_catalog
from prism_analyze.catalog.schema import Catalog, InflectionPoint
from prism_analyze.data.schema import CatalogError


class TestInflectionPoint:
    def test_minimal_valid(self):
        p = InflectionPoint(
            id="test-1",
            date=datetime.date(2023, 1, 1),
            label="Test Event",
            category="llm-general",
        )
        assert p.id == "test-1"
        assert p.scope == "global"
        assert p.confidence == "medium"

    def test_date_from_string(self):
        p = InflectionPoint(
            id="test-2",
            date="2023-06-15",
            label="String Date",
            category="llm-general",
        )
        assert p.date == datetime.date(2023, 6, 15)

    def test_all_fields(self):
        p = InflectionPoint(
            id="test-3",
            date=datetime.date(2023, 1, 1),
            label="Full Event",
            category="ai-coding-assistant",
            subcategory="code-completion",
            scope="platform-specific",
            confidence="high",
            evidence_url="https://example.com",
            tags=["tag1", "tag2"],
            notes="Some notes",
        )
        assert p.tags == ["tag1", "tag2"]


class TestCatalog:
    def test_filter_by_date_range(self, sample_catalog):
        filtered = sample_catalog.filter_by_date_range(
            datetime.date(2022, 1, 1), datetime.date(2022, 12, 31)
        )
        assert len(filtered) == 2

    def test_filter_by_category(self, sample_catalog):
        filtered = sample_catalog.filter_by_category("llm-general")
        assert len(filtered) == 2

    def test_get_by_id(self, sample_catalog):
        point = sample_catalog.get_by_id("event-b")
        assert point is not None
        assert point.label == "Event B"

    def test_get_by_id_missing(self, sample_catalog):
        assert sample_catalog.get_by_id("nonexistent") is None

    def test_len(self, sample_catalog):
        assert len(sample_catalog) == 3

    def test_iter(self, sample_catalog):
        ids = [p.id for p in sample_catalog]
        assert ids == ["event-a", "event-b", "event-c"]


class TestLoader:
    def test_load_custom_catalog(self, tmp_path):
        catalog_data = {
            "inflection_points": [
                {
                    "id": "custom-1",
                    "date": "2023-01-01",
                    "label": "Custom Event",
                    "category": "llm-general",
                }
            ]
        }
        path = tmp_path / "catalog.yaml"
        path.write_text(yaml.dump(catalog_data))

        catalog = load_catalog(path=path)
        assert len(catalog) == 1
        assert catalog.inflection_points[0].id == "custom-1"

    def test_load_with_overrides(self, tmp_path):
        base_data = {
            "inflection_points": [
                {
                    "id": "base-1",
                    "date": "2023-01-01",
                    "label": "Base Event",
                    "category": "llm-general",
                }
            ]
        }
        override_data = [
            {
                "id": "base-1",
                "date": "2023-06-01",
                "label": "Overridden Event",
                "category": "llm-general",
            },
            {
                "id": "new-1",
                "date": "2023-07-01",
                "label": "New Event",
                "category": "ai-coding-assistant",
            },
        ]

        base_path = tmp_path / "base.yaml"
        base_path.write_text(yaml.dump(base_data))
        override_path = tmp_path / "overrides.yaml"
        override_path.write_text(yaml.dump(override_data))

        catalog = load_catalog(path=base_path, user_overrides=override_path)
        assert len(catalog) == 2
        assert catalog.get_by_id("base-1").label == "Overridden Event"

    def test_invalid_category_raises(self, tmp_path):
        catalog_data = {
            "inflection_points": [
                {
                    "id": "bad-1",
                    "date": "2023-01-01",
                    "label": "Bad Category",
                    "category": "nonexistent-category",
                }
            ]
        }
        path = tmp_path / "bad.yaml"
        path.write_text(yaml.dump(catalog_data))

        with pytest.raises(CatalogError, match="nonexistent-category"):
            load_catalog(path=path)

    def test_load_bundled_default(self):
        catalog = load_catalog()
        assert len(catalog) > 0
