"""Export analysis results to Markdown, JSON, and CSV."""

from __future__ import annotations

import json
from dataclasses import asdict

import pandas as pd

from prism_analyze.report.models import AnalysisReport


def _sanitize_for_json(obj):
    """Recursively convert non-serializable types."""
    if isinstance(obj, pd.Series):
        return {str(k): v for k, v in obj.to_dict().items()}
    if isinstance(obj, pd.DataFrame):
        return obj.to_dict(orient="index")
    if isinstance(obj, pd.Timestamp):
        return str(obj)
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    return obj


def to_markdown(report: AnalysisReport) -> str:
    """Render the analysis report as Markdown."""
    lines: list[str] = []

    lines.append("# prism-analyze Report\n")

    # Preprocessing
    p = report.preprocessing
    lines.append("## Preprocessing\n")
    lines.append(f"- **Inferred frequency:** {p.inferred_frequency or 'unknown'}")
    lines.append(f"- **Differencing order:** {p.differencing_order}")
    lines.append(f"- **Stationarity:** {p.stationarity.decision}")
    lines.append(f"- **Outliers flagged:** {len(p.outlier_indices)}")
    lines.append(f"- **Observations dropped (NaN):** {len(p.dropped_timestamps)}")
    lines.append("")

    # Break detection
    b = report.breaks
    lines.append("## Structural Break Detection\n")
    penalty_note = "auto (Birgé-Massart)" if b.penalty_auto else "manual"
    lines.append(f"- **Model:** {b.model_used}, **Penalty:** {b.penalty_used:.4f} ({penalty_note})")
    lines.append(f"- **Detected breaks:** {len(b.detected_breaks)}")
    for ts in b.detected_breaks:
        lines.append(f"  - {ts.date()}")
    lines.append("")

    if b.catalog_overlaps:
        lines.append("### Catalog Overlap\n")
        lines.append("| Inflection ID | Date | Nearest Break | Distance (days) | In Window |")
        lines.append("|---|---|---|---|---|")
        for o in b.catalog_overlaps:
            nb = str(o.nearest_break.date()) if o.nearest_break else "—"
            dist = str(o.distance_days) if o.distance_days is not None else "—"
            lines.append(f"| {o.inflection_id} | {o.inflection_date} | {nb} | {dist} | {'Yes' if o.in_window else 'No'} |")
        lines.append("")

    # ITS results
    if report.its_results:
        lines.append("## ITS Results\n")
        lines.append("| Inflection ID | Level Change | p-value | Slope Change | p-value | R² | In Break Window |")
        lines.append("|---|---|---|---|---|---|---|")
        for r in report.its_results:
            lines.append(
                f"| {r.inflection_id} | {r.level_change:.4f} (±{r.level_change_se:.4f}) "
                f"| {r.level_change_pvalue:.4f} | {r.slope_change:.4f} (±{r.slope_change_se:.4f}) "
                f"| {r.slope_change_pvalue:.4f} | {r.r_squared:.3f} | {'Yes' if r.in_break_window else 'No'} |"
            )
        lines.append("")

    # DiD results
    if report.did_results:
        lines.append("## DiD Results\n")
        lines.append("| Inflection ID | ATT | p-value | Parallel Trends |")
        lines.append("|---|---|---|---|")
        for d in report.did_results:
            flag = "Pass" if d.parallel_trends_pass else "**FAIL**"
            lines.append(
                f"| {d.inflection_id} | {d.att:.4f} (±{d.att_se:.4f}) "
                f"| {d.att_pvalue:.4f} | {flag} |"
            )
        lines.append("")

    # Correction
    if report.correction:
        c = report.correction
        lines.append("## Multiple Testing Correction\n")
        lines.append(f"- **Method:** {c.method}, **Alpha:** {c.alpha}")
        lines.append("")
        lines.append("| Inflection ID | Raw p | Corrected p | Significant |")
        lines.append("|---|---|---|---|")
        for pid in c.raw_pvalues:
            lines.append(
                f"| {pid} | {c.raw_pvalues[pid]:.4f} | {c.corrected_pvalues[pid]:.4f} "
                f"| {'Yes' if c.rejected[pid] else 'No'} |"
            )
        lines.append("")

    # Log
    if report.log:
        lines.append("## Pipeline Log\n")
        for entry in report.log:
            lines.append(f"- {entry}")

    return "\n".join(lines)


def to_json(report: AnalysisReport) -> str:
    """Serialize the full report to JSON."""
    raw = asdict(report)

    def _clean(obj):
        if isinstance(obj, dict):
            return {k: _clean(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_clean(v) for v in obj]
        return _sanitize_for_json(obj)

    return json.dumps(_clean(raw), indent=2, default=str)


def to_csv(report: AnalysisReport) -> str:
    """Export the summary matrix as CSV."""
    if report.summary_matrix is None or report.summary_matrix.empty:
        return ""
    return report.summary_matrix.to_csv()
