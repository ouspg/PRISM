"""Stage 1: Preprocessing — stationarity tests, differencing, outlier flagging."""

from __future__ import annotations

import math
import warnings

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import adfuller, kpss

from prism_analyze.config import AnalysisConfig
from prism_analyze.data.validator import validate_series
from prism_analyze.report.models import PreprocessingResult, StationarityResult


def _test_stationarity(
    series: pd.Series, alpha: float
) -> StationarityResult:
    """Run ADF + KPSS complementary testing."""
    adf_stat, adf_p, *_ = adfuller(series.values, autolag="AIC")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # KPSS warns about p-value bounds
        kpss_stat, kpss_p, *_ = kpss(series.values, regression="c", nlags="auto")

    adf_rejects = adf_p < alpha  # rejects null of unit root → stationary
    kpss_rejects = kpss_p < alpha  # rejects null of stationarity → non-stationary

    if adf_rejects and not kpss_rejects:
        decision = "Stationary (ADF rejects unit root, KPSS does not reject stationarity)."
        is_stationary = True
    elif not adf_rejects and kpss_rejects:
        decision = "Non-stationary (ADF fails to reject unit root, KPSS rejects stationarity)."
        is_stationary = False
    elif adf_rejects and kpss_rejects:
        decision = (
            "Ambiguous: ADF rejects unit root but KPSS rejects stationarity. "
            "Treating as non-stationary (will difference)."
        )
        is_stationary = False
    else:
        decision = (
            "Ambiguous: ADF fails to reject unit root but KPSS does not reject "
            "stationarity. Treating as non-stationary (will difference)."
        )
        is_stationary = False

    return StationarityResult(
        adf_statistic=adf_stat,
        adf_pvalue=adf_p,
        kpss_statistic=kpss_stat,
        kpss_pvalue=kpss_p,
        is_stationary=is_stationary,
        decision=decision,
    )


def _flag_outliers(
    series: pd.Series, method: str, threshold: float
) -> list[pd.Timestamp]:
    """Return indices of outlier observations (flagged, not removed)."""
    if method != "iqr":
        return []

    q1 = series.quantile(0.25)
    q3 = series.quantile(0.75)
    iqr = q3 - q1
    lower = q1 - threshold * iqr
    upper = q3 + threshold * iqr
    mask = (series < lower) | (series > upper)
    return series.index[mask].tolist()


def _auto_hac_maxlags(n: int) -> int:
    """Compute default Newey-West max lags: floor(4*(T/100)^(2/9))."""
    return int(math.floor(4.0 * (n / 100.0) ** (2.0 / 9.0)))


def preprocess(
    series: pd.Series,
    config: AnalysisConfig,
) -> PreprocessingResult:
    """Run the full preprocessing stage.

    1. Validate input
    2. ADF + KPSS stationarity test
    3. Auto-differencing (up to order 2) if non-stationary
    4. Outlier flagging
    5. HAC maxlags calculation
    """
    validated, log = validate_series(series, config)
    original = validated.copy()
    freq = pd.infer_freq(validated.index)
    dropped = validated.index[series.reindex(validated.index).isna()].tolist() if len(validated) < len(series) else []

    # Stationarity testing + auto-differencing
    diff_order = 0
    current = validated.copy()

    stationarity = _test_stationarity(current, config.stationarity_alpha)

    if not stationarity.is_stationary:
        for order in range(1, 3):  # try up to 2nd-order differencing
            current = validated.diff(periods=order).dropna()
            diff_order = order
            stationarity = _test_stationarity(current, config.stationarity_alpha)
            log.append(
                f"Applied order-{order} differencing. "
                f"Stationarity: {stationarity.decision}"
            )
            if stationarity.is_stationary:
                break
        else:
            log.append(
                "WARNING: Series remains non-stationary after 2nd-order differencing. "
                "Proceeding with differenced series."
            )

    # Outlier flagging
    outliers = _flag_outliers(current, config.outlier_method, config.outlier_threshold)
    if outliers:
        log.append(f"Flagged {len(outliers)} outlier(s) (not removed).")

    # HAC maxlags
    hac_lags = config.hac_maxlags or _auto_hac_maxlags(len(current))

    return PreprocessingResult(
        series=current,
        original_series=original,
        stationarity=stationarity,
        differencing_order=diff_order,
        inferred_frequency=freq,
        dropped_timestamps=dropped,
        outlier_indices=outliers,
        hac_maxlags=hac_lags,
        log=log,
    )
