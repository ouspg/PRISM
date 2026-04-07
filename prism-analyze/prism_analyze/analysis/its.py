"""Stage 3: Interrupted Time Series — segmented OLS with HAC standard errors."""

from __future__ import annotations

import datetime

import numpy as np
import pandas as pd
from statsmodels.api import OLS, add_constant

from prism_analyze.config import AnalysisConfig
from prism_analyze.report.models import ITSResult


def _build_design_matrix(
    series: pd.Series,
    intervention_date: datetime.date,
) -> pd.DataFrame:
    """Build the ITS design matrix: [const, time, level_change, slope_change].

    - time: integer index 0..N-1
    - level_change: 1 for t >= intervention, 0 otherwise
    - slope_change: (t - T0) * level_change, where T0 is the intervention index
    """
    n = len(series)
    intervention_ts = pd.Timestamp(intervention_date)

    # Find the first index at or after the intervention date
    post_mask = series.index >= intervention_ts
    if not post_mask.any():
        # Intervention is after the entire series — everything is pre
        t0 = n
    else:
        t0 = post_mask.argmax()

    time_idx = np.arange(n, dtype=float)
    level_change = np.where(time_idx >= t0, 1.0, 0.0)
    slope_change = np.where(time_idx >= t0, time_idx - t0, 0.0)

    return pd.DataFrame(
        {
            "const": 1.0,
            "time": time_idx,
            "level_change": level_change,
            "slope_change": slope_change,
        },
        index=series.index,
    )


def run_its(
    series: pd.Series,
    inflection_id: str,
    inflection_date: datetime.date,
    config: AnalysisConfig,
    in_break_window: bool = False,
    hac_maxlags: int | None = None,
) -> ITSResult:
    """Run ITS regression for a single inflection point.

    Fits:  y = β₀ + β₁·time + β₂·level_change + β₃·slope_change + ε

    with Newey-West HAC standard errors.
    """
    X = _build_design_matrix(series, inflection_date)
    y = series.values.astype(float)

    maxlags = hac_maxlags or config.hac_maxlags or 1

    model = OLS(y, X)
    results = model.fit(
        cov_type="HAC",
        cov_kwds={"maxlags": maxlags, "kernel": "bartlett", "use_correction": True},
    )

    params = results.params
    bse = results.bse
    pvalues = results.pvalues

    # Counterfactual: project pre-intervention trend into post-period
    # counterfactual = β₀ + β₁·time (no level or slope change)
    counterfactual_values = params["const"] + params["time"] * X["time"].values
    counterfactual = pd.Series(counterfactual_values, index=series.index)

    return ITSResult(
        inflection_id=inflection_id,
        inflection_date=inflection_date,
        in_break_window=in_break_window,
        level_change=float(params["level_change"]),
        level_change_se=float(bse["level_change"]),
        level_change_pvalue=float(pvalues["level_change"]),
        slope_change=float(params["slope_change"]),
        slope_change_se=float(bse["slope_change"]),
        slope_change_pvalue=float(pvalues["slope_change"]),
        intercept=float(params["const"]),
        trend=float(params["time"]),
        r_squared=float(results.rsquared),
        n_observations=int(results.nobs),
        counterfactual=counterfactual,
    )
