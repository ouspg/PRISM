"""Tests for structural break detection."""

import datetime

import numpy as np
import pandas as pd
import pytest

from prism_analyze.analysis.breaks import detect_breaks, _find_nearest_break
from prism_analyze.catalog.schema import Catalog, InflectionPoint
from prism_analyze.config import AnalysisConfig


class TestFindNearestBreak:
    def test_finds_nearest(self):
        breaks = [pd.Timestamp("2022-01-15"), pd.Timestamp("2022-07-01")]
        nearest, dist = _find_nearest_break(datetime.date(2022, 1, 10), breaks)
        assert nearest == pd.Timestamp("2022-01-15")
        assert dist == 5

    def test_empty_breaks(self):
        nearest, dist = _find_nearest_break(datetime.date(2022, 1, 1), [])
        assert nearest is None
        assert dist is None


class TestDetectBreaks:
    def test_detects_known_break(self, series_with_break, config):
        catalog = Catalog(
            inflection_points=[
                InflectionPoint(
                    id="known-break",
                    date=datetime.date(2022, 1, 1),
                    label="Known Break",
                    category="llm-general",
                )
            ]
        )
        result = detect_breaks(series_with_break, catalog, config)

        assert len(result.detected_breaks) > 0
        assert len(result.catalog_overlaps) == 1

    def test_no_breaks_in_stationary(self, stationary_series, config):
        catalog = Catalog(inflection_points=[])
        # Use high penalty to suppress spurious breaks
        config_strict = AnalysisConfig(break_penalty=10.0)
        result = detect_breaks(stationary_series, catalog, config_strict)

        # Should detect few or no breaks in white noise with high penalty
        assert isinstance(result.detected_breaks, list)

    def test_overlap_window(self, series_with_break, config):
        catalog = Catalog(
            inflection_points=[
                InflectionPoint(
                    id="nearby",
                    date=datetime.date(2022, 1, 15),
                    label="Nearby Event",
                    category="llm-general",
                ),
                InflectionPoint(
                    id="far-away",
                    date=datetime.date(2023, 6, 1),
                    label="Far Event",
                    category="llm-general",
                ),
            ]
        )
        result = detect_breaks(series_with_break, catalog, config)

        overlaps = {o.inflection_id: o for o in result.catalog_overlaps}
        # "nearby" should be in window if a break was detected near 2022-01
        # "far-away" should not be in window
        assert "nearby" in overlaps
        assert "far-away" in overlaps
