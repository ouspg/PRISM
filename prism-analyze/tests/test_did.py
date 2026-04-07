"""Tests for DiD estimation."""

import datetime

import numpy as np
import pandas as pd
import pytest

from prism_analyze.analysis.did import run_did
from prism_analyze.config import AnalysisConfig


class TestRunDiD:
    def test_detects_treatment_effect(self, synthetic_panel):
        panel, treatment_units = synthetic_panel
        config = AnalysisConfig()

        result = run_did(
            panel=panel,
            treatment_units=treatment_units,
            inflection_id="test-did",
            inflection_date=datetime.date(2022, 7, 1),
            config=config,
            outcome_col="metric",
        )

        # Known ATT of +10 should be detected
        assert result.att > 5  # allow for noise
        assert result.att_pvalue < 0.05
        assert result.n_treated == 2
        assert result.n_control == 2

    def test_parallel_trends_pass(self, synthetic_panel):
        panel, treatment_units = synthetic_panel
        config = AnalysisConfig()

        result = run_did(
            panel=panel,
            treatment_units=treatment_units,
            inflection_id="test-did",
            inflection_date=datetime.date(2022, 7, 1),
            config=config,
            outcome_col="metric",
        )

        # Synthetic data has parallel pre-trends by construction
        assert result.parallel_trends_pass is True

    def test_default_outcome_col(self, synthetic_panel):
        panel, treatment_units = synthetic_panel
        config = AnalysisConfig()

        result = run_did(
            panel=panel,
            treatment_units=treatment_units,
            inflection_id="test-did",
            inflection_date=datetime.date(2022, 7, 1),
            config=config,
        )

        # Should use first column by default
        assert result.att != 0
