"""Data validation for time-series and panel inputs."""

from __future__ import annotations

import pandas as pd

from prism_analyze.config import AnalysisConfig
from prism_analyze.data.schema import InsufficientDataError, ValidationError


def validate_series(
    series: pd.Series,
    config: AnalysisConfig,
) -> tuple[pd.Series, list[str]]:
    """Validate and clean a time-series for analysis.

    Returns the validated series and a log of actions taken.

    Raises
    ------
    ValidationError
        If the series cannot be coerced into a valid format.
    InsufficientDataError
        If too many values are missing.
    """
    log: list[str] = []

    # --- Must be a Series ---
    if not isinstance(series, pd.Series):
        raise ValidationError(f"Expected pd.Series, got {type(series).__name__}.")

    series = series.copy()

    # --- DatetimeIndex ---
    if not isinstance(series.index, pd.DatetimeIndex):
        try:
            series.index = pd.to_datetime(series.index)
            log.append("Coerced index to DatetimeIndex.")
        except Exception as exc:
            raise ValidationError(
                f"Index could not be converted to DatetimeIndex: {exc}"
            ) from exc

    # --- Numeric dtype ---
    if not pd.api.types.is_numeric_dtype(series):
        try:
            series = pd.to_numeric(series, errors="raise")
            log.append("Coerced values to numeric.")
        except Exception as exc:
            raise ValidationError(
                f"Values could not be converted to numeric: {exc}"
            ) from exc

    # --- Sort by index ---
    if not series.index.is_monotonic_increasing:
        series = series.sort_index()
        log.append("Sorted series by DatetimeIndex.")

    # --- Infer frequency ---
    freq = pd.infer_freq(series.index)
    if freq:
        log.append(f"Inferred frequency: {freq}.")
    else:
        log.append("Could not infer frequency — irregular time series.")

    # --- NaN handling ---
    nan_count = series.isna().sum()
    if nan_count > 0:
        nan_frac = nan_count / len(series)
        if nan_frac > config.max_missing_pct:
            raise InsufficientDataError(
                f"{nan_frac:.1%} of values are NaN "
                f"(threshold: {config.max_missing_pct:.1%})."
            )
        dropped = series.index[series.isna()].tolist()
        series = series.dropna()
        log.append(
            f"Dropped {len(dropped)} NaN value(s) "
            f"({nan_frac:.1%} of series): {[str(t) for t in dropped]}."
        )

    # --- Minimum observations ---
    if len(series) < config.min_observations:
        log.append(
            f"WARNING: Only {len(series)} observations "
            f"(recommended minimum: {config.min_observations})."
        )

    return series, log


def validate_panel(
    df: pd.DataFrame,
    treatment_units: list[str],
    config: AnalysisConfig,
) -> tuple[pd.DataFrame, list[str]]:
    """Validate a panel DataFrame for DiD analysis.

    Expects a DataFrame with a 2-level MultiIndex ``(entity, time)``.

    Returns the validated DataFrame and a log of actions taken.
    """
    log: list[str] = []

    if not isinstance(df, pd.DataFrame):
        raise ValidationError(f"Expected pd.DataFrame, got {type(df).__name__}.")

    # --- MultiIndex check ---
    if not isinstance(df.index, pd.MultiIndex):
        raise ValidationError(
            "Panel DataFrame must have a 2-level MultiIndex (entity, time). "
            "Got a flat index."
        )

    if df.index.nlevels != 2:
        raise ValidationError(
            f"Panel MultiIndex must have exactly 2 levels, got {df.index.nlevels}."
        )

    # --- Entity / time levels ---
    entities = df.index.get_level_values(0).unique()
    times = df.index.get_level_values(1)

    if not isinstance(times, pd.DatetimeIndex):
        try:
            new_level = pd.to_datetime(df.index.get_level_values(1))
            df.index = df.index.set_levels(new_level, level=1)
            log.append("Coerced time level of MultiIndex to DatetimeIndex.")
        except Exception as exc:
            raise ValidationError(
                f"Time level could not be converted to DatetimeIndex: {exc}"
            ) from exc

    # --- Treatment units exist ---
    missing = set(treatment_units) - set(entities)
    if missing:
        raise ValidationError(
            f"Treatment units not found in panel entities: {missing}. "
            f"Available entities: {sorted(entities)}."
        )

    if not treatment_units:
        raise ValidationError("treatment_units list must not be empty.")

    n_treat = len(treatment_units)
    n_control = len(entities) - n_treat
    log.append(
        f"Panel: {len(entities)} entities ({n_treat} treated, {n_control} control), "
        f"{df.index.get_level_values(1).nunique()} time periods."
    )

    # --- Numeric check ---
    for col in df.columns:
        if not pd.api.types.is_numeric_dtype(df[col]):
            raise ValidationError(f"Column '{col}' is not numeric.")

    # --- NaN check ---
    nan_frac = df.isna().sum().sum() / df.size
    if nan_frac > config.max_missing_pct:
        raise InsufficientDataError(
            f"{nan_frac:.1%} of panel values are NaN "
            f"(threshold: {config.max_missing_pct:.1%})."
        )
    if nan_frac > 0:
        df = df.dropna()
        log.append(f"Dropped rows with NaN ({nan_frac:.1%} of panel).")

    return df, log
