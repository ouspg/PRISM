"""Tests for ITS estimation."""

import datetime

import numpy as np
import pandas as pd
import pytest

from prism_analyze.analysis.its import run_its, _build_design_matrix
from prism_analyze.config import AnalysisConfig


class TestDesignMatrix:
    def test_shape(self):
        dates = pd.date_range("2020-01-01", periods=24, freq="MS")
        series = pd.Series(np.ones(24), index=dates)
        X = _build_design_matrix(series, datetime.date(2021, 1, 1))

        assert X.shape == (24, 4)
        assert list(X.columns) == ["const", "time", "level_change", "slope_change"]

    def test_pre_post_split(self):
        dates = pd.date_range("2020-01-01", periods=24, freq="MS")
        series = pd.Series(np.ones(24), index=dates)
        X = _build_design_matrix(series, datetime.date(2021, 1, 1))

        # First 12 months should have level_change=0
        assert X["level_change"].iloc[:12].sum() == 0
        # Last 12 months should have level_change=1
        assert X["level_change"].iloc[12:].sum() == 12

    def test_slope_change_zero_pre(self):
        dates = pd.date_range("2020-01-01", periods=24, freq="MS")
        series = pd.Series(np.ones(24), index=dates)
        X = _build_design_matrix(series, datetime.date(2021, 1, 1))

        assert X["slope_change"].iloc[:12].sum() == 0
        assert X["slope_change"].iloc[12] == 0  # starts at 0 at intervention
        assert X["slope_change"].iloc[13] == 1


class TestRunITS:
    def test_detects_level_shift(self, series_with_break):
        config = AnalysisConfig()
        result = run_its(
            series=series_with_break,
            inflection_id="test-break",
            inflection_date=datetime.date(2022, 1, 1),
            config=config,
            hac_maxlags=2,
        )

        # Known level shift of +20 should be detected
        assert result.level_change > 10  # allow for noise
        assert result.level_change_pvalue < 0.05
        assert result.inflection_id == "test-break"

    def test_no_effect_on_stationary(self, stationary_series):
        config = AnalysisConfig()
        result = run_its(
            series=stationary_series,
            inflection_id="no-effect",
            inflection_date=datetime.date(2022, 7, 1),
            config=config,
            hac_maxlags=2,
        )

        # Should not find significant effects in white noise
        assert result.level_change_pvalue > 0.01 or abs(result.level_change) < 5

    def test_counterfactual_shape(self, series_with_break):
        config = AnalysisConfig()
        result = run_its(
            series=series_with_break,
            inflection_id="test",
            inflection_date=datetime.date(2022, 1, 1),
            config=config,
            hac_maxlags=2,
        )

        assert len(result.counterfactual) == len(series_with_break)
        assert result.counterfactual.index.equals(series_with_break.index)

    def test_r_squared_reasonable(self, series_with_break):
        config = AnalysisConfig()
        result = run_its(
            series=series_with_break,
            inflection_id="test",
            inflection_date=datetime.date(2022, 1, 1),
            config=config,
            hac_maxlags=2,
        )

        assert 0 <= result.r_squared <= 1
        assert result.r_squared > 0.5  # should explain most variance
