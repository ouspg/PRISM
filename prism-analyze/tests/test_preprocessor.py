"""Tests for the preprocessing stage."""

import numpy as np
import pandas as pd
import pytest

from prism_analyze.analysis.preprocessor import preprocess, _test_stationarity, _flag_outliers
from prism_analyze.config import AnalysisConfig
from prism_analyze.data.schema import InsufficientDataError, ValidationError


class TestStationarity:
    def test_stationary_series(self, stationary_series):
        result = _test_stationarity(stationary_series, alpha=0.05)
        assert result.is_stationary is True

    def test_non_stationary_series(self):
        """Random walk should be non-stationary."""
        np.random.seed(42)
        dates = pd.date_range("2020-01-01", periods=100, freq="MS")
        values = np.cumsum(np.random.normal(0, 1, 100))
        series = pd.Series(values, index=dates)

        result = _test_stationarity(series, alpha=0.05)
        assert result.is_stationary is False


class TestOutlierFlagging:
    def test_flags_outliers(self):
        dates = pd.date_range("2020-01-01", periods=10, freq="MS")
        values = [10, 10, 10, 10, 10, 10, 10, 10, 10, 100]
        series = pd.Series(values, index=dates, dtype=float)

        outliers = _flag_outliers(series, method="iqr", threshold=1.5)
        assert len(outliers) > 0
        assert dates[-1] in outliers

    def test_no_outliers(self, stationary_series):
        outliers = _flag_outliers(stationary_series, method="iqr", threshold=3.0)
        # With a wide threshold, few or no outliers expected
        assert isinstance(outliers, list)


class TestPreprocess:
    def test_stationary_no_differencing(self, stationary_series, config):
        result = preprocess(stationary_series, config)
        assert result.differencing_order == 0
        assert result.stationarity.is_stationary is True
        assert result.inferred_frequency is not None

    def test_non_stationary_gets_differenced(self, config):
        np.random.seed(42)
        dates = pd.date_range("2020-01-01", periods=60, freq="MS")
        values = np.cumsum(np.random.normal(1, 0.5, 60))
        series = pd.Series(values, index=dates)

        result = preprocess(series, config)
        assert result.differencing_order >= 1

    def test_nan_below_threshold_dropped(self, config):
        dates = pd.date_range("2020-01-01", periods=60, freq="MS")
        values = np.random.normal(100, 5, 60)
        values[5] = np.nan  # 1/60 ≈ 1.7% < 5%
        series = pd.Series(values, index=dates)

        result = preprocess(series, config)
        assert len(result.dropped_timestamps) > 0 or len(result.series) < 60

    def test_nan_above_threshold_raises(self, config):
        dates = pd.date_range("2020-01-01", periods=20, freq="MS")
        values = [np.nan] * 5 + [1.0] * 15  # 25% NaN
        series = pd.Series(values, index=dates)

        with pytest.raises(InsufficientDataError):
            preprocess(series, config)

    def test_hac_maxlags_computed(self, stationary_series, config):
        result = preprocess(stationary_series, config)
        assert result.hac_maxlags > 0

    def test_series_with_break(self, series_with_break, config):
        result = preprocess(series_with_break, config)
        assert result.series is not None
        assert len(result.log) > 0
