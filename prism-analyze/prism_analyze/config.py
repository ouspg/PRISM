"""Analysis configuration with documented defaults."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AnalysisConfig(BaseModel):
    """All tunable parameters for the analysis pipeline.

    Every field has a defensible default. Researchers can use
    ``AnalysisConfig()`` unchanged and get peer-reviewable results.
    """

    # --- Stationarity / preprocessing ---
    stationarity_alpha: float = Field(
        default=0.05,
        description="Significance level for ADF and KPSS tests.",
    )
    max_missing_pct: float = Field(
        default=0.05,
        description="Maximum fraction of NaN values allowed before raising.",
    )
    outlier_method: Literal["iqr"] = Field(
        default="iqr",
        description="Outlier detection method.",
    )
    outlier_threshold: float = Field(
        default=1.5,
        description="IQR multiplier for outlier flagging.",
    )
    min_observations: int = Field(
        default=24,
        description="Minimum number of observations required (warns below, does not block).",
    )

    # --- Structural break detection ---
    break_penalty_auto: bool = Field(
        default=True,
        description=(
            "When True, penalty is computed from the data as log(n) * σ² "
            "(Birgé-Massart criterion). Scales automatically with series variance "
            "and length — prevents overfitting on high-variance or high-frequency data. "
            "Set to False to use break_penalty directly."
        ),
    )
    break_penalty: float = Field(
        default=3.0,
        description=(
            "Manual PELT penalty (only used when break_penalty_auto=False). "
            "Higher = fewer breaks. Must be in the same units as the cost function "
            "(squared deviations for L2), so it scales with your data's magnitude."
        ),
    )
    break_model: Literal["l2", "l1", "rbf"] = Field(
        default="l2",
        description="Cost model for PELT change-point detection.",
    )
    break_min_size: int = Field(
        default=2,
        description=(
            "Minimum segment length between breaks. Increase for coarser granularity "
            "(e.g., break_min_size=6 for monthly data enforces at least 6-month segments)."
        ),
    )
    max_breaks: int | None = Field(
        default=None,
        description=(
            "Hard cap on the number of detected breaks. "
            "When set, only the top-N breaks (by largest cost reduction) are kept. "
            "Useful when domain knowledge bounds the number of plausible regime shifts."
        ),
    )
    overlap_tolerance_days: int = Field(
        default=30,
        description="Days of tolerance when matching catalog points to detected breaks.",
    )

    # --- ITS estimation ---
    hac_maxlags: int | None = Field(
        default=None,
        description="Max lags for Newey-West HAC SEs. None = auto: floor(4*(T/100)^(2/9)).",
    )

    # --- DiD ---
    parallel_trends_alpha: float = Field(
        default=0.05,
        description="Significance level for the parallel pre-trends test.",
    )

    # --- Multiple testing correction ---
    fdr_alpha: float = Field(
        default=0.05,
        description="Family-wise alpha for Benjamini-Hochberg correction.",
    )
    correction_method: str = Field(
        default="fdr_bh",
        description="Method passed to statsmodels multipletests (e.g. 'fdr_bh', 'bonferroni').",
    )
