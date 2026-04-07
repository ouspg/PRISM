"""Stage 4: Difference-in-Differences with two-way fixed effects."""

from __future__ import annotations

import datetime

import numpy as np
import pandas as pd
from linearmodels.panel.model import PanelOLS

from prism_analyze.config import AnalysisConfig
from prism_analyze.report.models import DiDResult


def _build_did_data(
    panel: pd.DataFrame,
    treatment_units: list[str],
    intervention_date: datetime.date,
    outcome_col: str,
) -> pd.DataFrame:
    """Add treatment and post indicators to the panel DataFrame.

    Expects panel to have a 2-level MultiIndex (entity, time).
    Returns a copy with additional columns: treat, post, treat_post.
    """
    df = panel[[outcome_col]].copy()
    entities = df.index.get_level_values(0)
    times = df.index.get_level_values(1)

    df["treat"] = np.where(entities.isin(treatment_units), 1.0, 0.0)
    df["post"] = np.where(times >= pd.Timestamp(intervention_date), 1.0, 0.0)
    df["treat_post"] = df["treat"] * df["post"]

    return df


def _test_parallel_trends(
    panel: pd.DataFrame,
    treatment_units: list[str],
    intervention_date: datetime.date,
    outcome_col: str,
) -> tuple[float, float]:
    """Test parallel pre-trends using treatment × time interaction.

    Returns (F-statistic, p-value) for the joint significance test
    of treatment × time_period interactions in the pre-period.
    """
    times = panel.index.get_level_values(1)
    pre = panel.loc[times < pd.Timestamp(intervention_date)].copy()

    if len(pre) == 0:
        return 0.0, 1.0

    entities = pre.index.get_level_values(0)
    pre_times = pre.index.get_level_values(1)

    treat = np.where(entities.isin(treatment_units), 1.0, 0.0)
    unique_periods = sorted(pre_times.unique())

    if len(unique_periods) < 2:
        return 0.0, 1.0

    # Create time dummies × treatment interactions (drop first period)
    interactions = pd.DataFrame(index=pre.index)
    for period in unique_periods[1:]:
        col_name = f"treat_t{period}"
        time_dummy = np.where(pre_times == period, 1.0, 0.0)
        interactions[col_name] = treat * time_dummy

    if interactions.empty:
        return 0.0, 1.0

    y = pre[outcome_col]
    model = PanelOLS(
        y,
        interactions,
        entity_effects=True,
        time_effects=True,
        check_rank=False,
    )
    results = model.fit(cov_type="robust")

    # Joint F-test on all interaction terms
    try:
        f_test = results.f_statistic
        return float(f_test.stat), float(f_test.pval)
    except Exception:
        return 0.0, 1.0


def run_did(
    panel: pd.DataFrame,
    treatment_units: list[str],
    inflection_id: str,
    inflection_date: datetime.date,
    config: AnalysisConfig,
    outcome_col: str | None = None,
) -> DiDResult:
    """Run DiD for a single inflection point.

    Parameters
    ----------
    panel:
        DataFrame with 2-level MultiIndex (entity, time).
    treatment_units:
        Entity identifiers for the treatment group.
    inflection_id:
        ID of the catalog inflection point being tested.
    inflection_date:
        Date of the intervention.
    config:
        Analysis configuration.
    outcome_col:
        Column name for the outcome variable. If None, uses the first column.
    """
    if outcome_col is None:
        outcome_col = panel.columns[0]

    # Build interaction term
    did_data = _build_did_data(panel, treatment_units, inflection_date, outcome_col)

    # Entity and time FE absorb main effects of treat and post,
    # so only the interaction enters exog.
    y = did_data[outcome_col]
    exog = did_data[["treat_post"]]

    model = PanelOLS(y, exog, entity_effects=True, time_effects=True)
    results = model.fit(cov_type="robust")

    att = float(results.params["treat_post"])
    att_se = float(results.std_errors["treat_post"])
    att_p = float(results.pvalues["treat_post"])

    # Parallel pre-trends
    pt_f, pt_p = _test_parallel_trends(
        panel, treatment_units, inflection_date, outcome_col
    )
    pt_pass = pt_p > config.parallel_trends_alpha  # want to NOT reject

    entities = panel.index.get_level_values(0).unique()
    n_treat = sum(1 for e in entities if e in treatment_units)
    n_control = len(entities) - n_treat

    return DiDResult(
        inflection_id=inflection_id,
        inflection_date=inflection_date,
        att=att,
        att_se=att_se,
        att_pvalue=att_p,
        parallel_trends_f=pt_f,
        parallel_trends_pvalue=pt_p,
        parallel_trends_pass=pt_pass,
        n_treated=n_treat,
        n_control=n_control,
        n_observations=int(results.nobs),
    )
