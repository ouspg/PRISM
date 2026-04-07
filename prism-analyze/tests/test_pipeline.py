"""Integration tests for the full pipeline."""

import datetime

import numpy as np
import pandas as pd
import pytest

from prism_analyze.analysis.pipeline import run_pipeline
from prism_analyze.catalog.schema import Catalog, InflectionPoint
from prism_analyze.config import AnalysisConfig
from prism_analyze.core import Analyzer, analyze
from prism_analyze.report.models import AnalysisReport


@pytest.fixture
def integration_catalog():
    return Catalog(
        inflection_points=[
            InflectionPoint(
                id="break-point",
                date=datetime.date(2022, 1, 1),
                label="Known Break",
                category="llm-general",
            ),
        ]
    )


class TestPipeline:
    def test_full_pipeline(self, series_with_break, integration_catalog, config):
        report = run_pipeline(series_with_break, integration_catalog, config)

        assert isinstance(report, AnalysisReport)
        assert report.preprocessing is not None
        assert report.breaks is not None
        assert len(report.its_results) == 1
        assert report.correction is not None
        assert report.summary_matrix is not None
        assert len(report.log) > 0

    def test_pipeline_with_did(self, series_with_break, integration_catalog, config, synthetic_panel):
        panel, treatment_units = synthetic_panel
        # Override catalog to match panel date range
        catalog = Catalog(
            inflection_points=[
                InflectionPoint(
                    id="did-point",
                    date=datetime.date(2022, 7, 1),
                    label="DiD Break",
                    category="llm-general",
                ),
            ]
        )
        # Use panel's time range for the series
        dates = pd.date_range("2021-01-01", periods=36, freq="MS")
        np.random.seed(42)
        series = pd.Series(np.random.normal(50, 3, 36), index=dates)

        report = run_pipeline(
            series, catalog, config,
            panel=panel, treatment_units=treatment_units,
        )

        assert len(report.did_results) > 0

    def test_empty_catalog(self, series_with_break, config):
        catalog = Catalog(inflection_points=[])
        report = run_pipeline(series_with_break, catalog, config)

        assert len(report.its_results) == 0
        assert report.summary_matrix is not None

    def test_summary_matrix_columns(self, series_with_break, integration_catalog, config):
        report = run_pipeline(series_with_break, integration_catalog, config)

        expected_cols = {"inflection_date", "level_change", "slope_change", "r_squared"}
        assert expected_cols.issubset(set(report.summary_matrix.columns))


class TestAnalyzer:
    def test_analyzer_reuse(self, series_with_break, stationary_series, integration_catalog):
        analyzer = Analyzer(catalog=integration_catalog)

        r1 = analyzer.run(series_with_break)
        r2 = analyzer.run(stationary_series)

        assert isinstance(r1, AnalysisReport)
        assert isinstance(r2, AnalysisReport)
        # Different series should produce different results
        assert r1.its_results[0].level_change != r2.its_results[0].level_change
