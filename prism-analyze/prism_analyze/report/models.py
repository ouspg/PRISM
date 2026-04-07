"""Result dataclasses for every pipeline stage."""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field

import pandas as pd


# --- Stage 1: Preprocessing ---


@dataclass
class StationarityResult:
    """Outcome of ADF + KPSS complementary testing."""

    adf_statistic: float
    adf_pvalue: float
    kpss_statistic: float
    kpss_pvalue: float
    is_stationary: bool
    decision: str  # human-readable explanation


@dataclass
class PreprocessingResult:
    """Full preprocessing output."""

    series: pd.Series  # the (possibly differenced) series used downstream
    original_series: pd.Series
    stationarity: StationarityResult
    differencing_order: int  # 0 = none, 1 = first-differenced, etc.
    inferred_frequency: str | None
    dropped_timestamps: list[pd.Timestamp] = field(default_factory=list)
    outlier_indices: list[pd.Timestamp] = field(default_factory=list)
    hac_maxlags: int = 0
    log: list[str] = field(default_factory=list)


# --- Stage 2: Structural break detection ---


@dataclass
class CatalogOverlap:
    """One catalog point and its relationship to a detected break."""

    inflection_id: str
    inflection_date: datetime.date
    nearest_break: pd.Timestamp | None
    distance_days: int | None  # None if no detected break nearby
    in_window: bool  # within overlap_tolerance_days


@dataclass
class BreakDetectionResult:
    """Agnostic break detection + catalog overlap."""

    detected_breaks: list[pd.Timestamp]
    catalog_overlaps: list[CatalogOverlap]
    penalty_used: float
    penalty_auto: bool  # True if penalty was computed from data
    model_used: str


# --- Stage 3: ITS ---


@dataclass
class ITSResult:
    """ITS regression output for one inflection point."""

    inflection_id: str
    inflection_date: datetime.date
    in_break_window: bool
    level_change: float
    level_change_se: float
    level_change_pvalue: float
    slope_change: float
    slope_change_se: float
    slope_change_pvalue: float
    intercept: float
    trend: float
    r_squared: float
    n_observations: int
    counterfactual: pd.Series  # projected trend absent the break


# --- Stage 4: DiD ---


@dataclass
class DiDResult:
    """Difference-in-Differences output for one inflection point."""

    inflection_id: str
    inflection_date: datetime.date
    att: float  # average treatment effect on treated
    att_se: float
    att_pvalue: float
    parallel_trends_f: float
    parallel_trends_pvalue: float
    parallel_trends_pass: bool
    n_treated: int
    n_control: int
    n_observations: int


# --- Stage 5: Multiple testing correction ---


@dataclass
class CorrectionResult:
    """FDR / multiple testing correction output."""

    method: str
    alpha: float
    raw_pvalues: dict[str, float]  # inflection_id -> p
    corrected_pvalues: dict[str, float]  # inflection_id -> adjusted p
    rejected: dict[str, bool]  # inflection_id -> significant after correction


# --- Stage 6: Full report ---


@dataclass
class AnalysisReport:
    """Top-level result composing all pipeline stages."""

    preprocessing: PreprocessingResult
    breaks: BreakDetectionResult
    its_results: list[ITSResult]
    did_results: list[DiDResult] = field(default_factory=list)
    correction: CorrectionResult | None = None
    summary_matrix: pd.DataFrame | None = None  # the publishable table
    log: list[str] = field(default_factory=list)
