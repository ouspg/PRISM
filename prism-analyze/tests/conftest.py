"""Shared test fixtures."""

import datetime

import numpy as np
import pandas as pd
import pytest

from prism_analyze.catalog.schema import Catalog, InflectionPoint
from prism_analyze.config import AnalysisConfig


@pytest.fixture
def config():
    """Default analysis config."""
    return AnalysisConfig()


@pytest.fixture
def sample_catalog():
    """Catalog with 3 inflection points spanning 2021-2023."""
    return Catalog(
        inflection_points=[
            InflectionPoint(
                id="event-a",
                date=datetime.date(2022, 1, 15),
                label="Event A",
                category="llm-general",
            ),
            InflectionPoint(
                id="event-b",
                date=datetime.date(2022, 7, 1),
                label="Event B",
                category="ai-coding-assistant",
            ),
            InflectionPoint(
                id="event-c",
                date=datetime.date(2023, 1, 1),
                label="Event C",
                category="llm-general",
            ),
        ]
    )


@pytest.fixture
def stationary_series():
    """White noise — stationary by construction."""
    np.random.seed(42)
    dates = pd.date_range("2020-01-01", periods=60, freq="MS")
    values = np.random.normal(100, 5, size=60)
    return pd.Series(values, index=dates, name="stationary")


@pytest.fixture
def series_with_break():
    """Monthly series with a known level shift at month 24 (2022-01-01).

    Pre-period: mean ~100, trend +0.5/month
    Post-period: mean ~120 (level shift +20), trend +0.5/month
    """
    np.random.seed(42)
    dates = pd.date_range("2020-01-01", periods=48, freq="MS")
    noise = np.random.normal(0, 2, size=48)

    time = np.arange(48)
    values = 100 + 0.5 * time + noise
    # Apply level shift at t=24
    values[24:] += 20

    return pd.Series(values, index=dates, name="with_break")


@pytest.fixture
def synthetic_panel():
    """Panel DataFrame for DiD testing.

    4 entities × 36 months. Treatment applied to entity-a, entity-b
    at 2022-07-01 with ATT ≈ +10.
    """
    np.random.seed(42)
    entities = ["entity-a", "entity-b", "entity-c", "entity-d"]
    dates = pd.date_range("2021-01-01", periods=36, freq="MS")
    treatment_units = ["entity-a", "entity-b"]
    intervention = pd.Timestamp("2022-07-01")

    rows = []
    for entity in entities:
        for date in dates:
            base = 50 + np.random.normal(0, 3)
            if entity in treatment_units and date >= intervention:
                base += 10  # treatment effect
            rows.append({"entity": entity, "time": date, "metric": base})

    df = pd.DataFrame(rows)
    df = df.set_index(["entity", "time"])
    return df, treatment_units
