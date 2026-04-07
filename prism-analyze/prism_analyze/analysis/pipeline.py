"""Pipeline orchestrator — runs stages 1-6 in fixed order."""

from __future__ import annotations

import pandas as pd

from prism_analyze.analysis.breaks import detect_breaks
from prism_analyze.analysis.correction import apply_correction
from prism_analyze.analysis.did import run_did
from prism_analyze.analysis.its import run_its
from prism_analyze.analysis.preprocessor import preprocess
from prism_analyze.catalog.schema import Catalog
from prism_analyze.config import AnalysisConfig
from prism_analyze.data.validator import validate_panel
from prism_analyze.report.models import AnalysisReport, DiDResult, ITSResult


def _build_summary_matrix(
    its_results: list[ITSResult],
    did_results: list[DiDResult],
    correction: dict[str, float] | None,
    rejected: dict[str, bool] | None,
) -> pd.DataFrame:
    """Build the publishable comparison matrix."""
    rows = []
    for r in its_results:
        row = {
            "inflection_id": r.inflection_id,
            "inflection_date": str(r.inflection_date),
            "in_break_window": r.in_break_window,
            "level_change": r.level_change,
            "level_change_se": r.level_change_se,
            "level_change_p": r.level_change_pvalue,
            "slope_change": r.slope_change,
            "slope_change_se": r.slope_change_se,
            "slope_change_p": r.slope_change_pvalue,
            "r_squared": r.r_squared,
            "n_obs": r.n_observations,
        }
        if correction and r.inflection_id in correction:
            row["p_corrected"] = correction[r.inflection_id]
            row["significant"] = rejected.get(r.inflection_id, False) if rejected else False
        rows.append(row)

    for d in did_results:
        # Find the matching ITS row and augment it
        for row in rows:
            if row["inflection_id"] == d.inflection_id:
                row["att"] = d.att
                row["att_se"] = d.att_se
                row["att_p"] = d.att_pvalue
                row["parallel_trends_pass"] = d.parallel_trends_pass
                break

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows).set_index("inflection_id")


def run_pipeline(
    series: pd.Series,
    catalog: Catalog,
    config: AnalysisConfig,
    panel: pd.DataFrame | None = None,
    treatment_units: list[str] | None = None,
) -> AnalysisReport:
    """Execute the full analysis pipeline.

    Stages:
    1. Preprocess (validate, stationarity, differencing, outliers)
    2. Detect structural breaks (PELT) + catalog overlap
    3. ITS per catalog inflection point in date range
    4. DiD per inflection point (if panel data provided)
    5. Multiple testing correction
    6. Build summary matrix
    """
    log: list[str] = []

    # --- Stage 1: Preprocessing ---
    prep = preprocess(series, config)
    log.extend(prep.log)

    # Filter catalog to the series date range
    start_date = prep.series.index[0].date()
    end_date = prep.series.index[-1].date()
    active_catalog = catalog.filter_by_date_range(start_date, end_date)
    log.append(
        f"Catalog: {len(active_catalog)} of {len(catalog)} inflection points "
        f"fall within data range [{start_date}, {end_date}]."
    )

    # --- Stage 2: Break detection ---
    breaks = detect_breaks(prep.series, active_catalog, config)
    log.append(f"Detected {len(breaks.detected_breaks)} agnostic break(s).")

    # Build overlap lookup
    overlap_map = {o.inflection_id: o.in_window for o in breaks.catalog_overlaps}

    # --- Stage 3: ITS ---
    its_results: list[ITSResult] = []
    for point in active_catalog.inflection_points:
        its_result = run_its(
            series=prep.series,
            inflection_id=point.id,
            inflection_date=point.date,
            config=config,
            in_break_window=overlap_map.get(point.id, False),
            hac_maxlags=prep.hac_maxlags,
        )
        its_results.append(its_result)
        log.append(
            f"ITS [{point.id}]: level_change={its_result.level_change:.4f} "
            f"(p={its_result.level_change_pvalue:.4f}), "
            f"slope_change={its_result.slope_change:.4f} "
            f"(p={its_result.slope_change_pvalue:.4f})"
        )

    # --- Stage 4: DiD (optional) ---
    did_results: list[DiDResult] = []
    if panel is not None and treatment_units is not None:
        panel_validated, panel_log = validate_panel(panel, treatment_units, config)
        log.extend(panel_log)

        for point in active_catalog.inflection_points:
            did_result = run_did(
                panel=panel_validated,
                treatment_units=treatment_units,
                inflection_id=point.id,
                inflection_date=point.date,
                config=config,
            )
            did_results.append(did_result)
            flag = "" if did_result.parallel_trends_pass else " [TRENDS FAIL]"
            log.append(
                f"DiD [{point.id}]: ATT={did_result.att:.4f} "
                f"(p={did_result.att_pvalue:.4f}){flag}"
            )

    # --- Stage 5: Multiple testing correction ---
    correction_result = None
    if its_results:
        # Use the minimum p-value from level_change and slope_change per point
        pvalues = {
            r.inflection_id: min(r.level_change_pvalue, r.slope_change_pvalue)
            for r in its_results
        }
        correction_result = apply_correction(
            pvalues, method=config.correction_method, alpha=config.fdr_alpha
        )

    # --- Stage 6: Summary matrix ---
    corrected_p = correction_result.corrected_pvalues if correction_result else None
    rejected = correction_result.rejected if correction_result else None
    summary = _build_summary_matrix(its_results, did_results, corrected_p, rejected)

    return AnalysisReport(
        preprocessing=prep,
        breaks=breaks,
        its_results=its_results,
        did_results=did_results,
        correction=correction_result,
        summary_matrix=summary,
        log=log,
    )
