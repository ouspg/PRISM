"""Barebone matplotlib visualizations."""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.figure import Figure

from prism_analyze.report.models import AnalysisReport


def plot_series_with_breaks(
    report: AnalysisReport,
    ax: plt.Axes | None = None,
    show_counterfactual: bool = True,
) -> Figure:
    """Plot the time series with detected breaks, catalog points, and counterfactuals.

    Parameters
    ----------
    report:
        A completed AnalysisReport.
    ax:
        Optional matplotlib Axes to draw on. Creates a new figure if None.
    show_counterfactual:
        Whether to overlay counterfactual projections from ITS.
    """
    if ax is None:
        fig, ax = plt.subplots(figsize=(12, 5))
    else:
        fig = ax.get_figure()

    series = report.preprocessing.series

    # Actual series
    ax.plot(series.index, series.values, color="black", linewidth=1.2, label="Observed")

    # Detected breaks (agnostic)
    for ts in report.breaks.detected_breaks:
        ax.axvline(ts, color="red", linestyle="--", alpha=0.5, linewidth=0.8)
    # Add one to legend
    if report.breaks.detected_breaks:
        ax.axvline(
            report.breaks.detected_breaks[0],
            color="red", linestyle="--", alpha=0.5, linewidth=0.8,
            label="Detected break",
        )

    # Catalog inflection points
    for overlap in report.breaks.catalog_overlaps:
        ts = pd.Timestamp(overlap.inflection_date)
        color = "blue" if overlap.in_window else "gray"
        ax.axvline(ts, color=color, linestyle=":", alpha=0.7, linewidth=0.8)
    # Legend entries
    ax.axvline(
        pd.Timestamp("2000-01-01"), color="blue", linestyle=":", alpha=0.7,
        linewidth=0.8, label="Catalog point (in window)",
    )
    ax.axvline(
        pd.Timestamp("2000-01-01"), color="gray", linestyle=":", alpha=0.7,
        linewidth=0.8, label="Catalog point (outside window)",
    )

    # Counterfactuals
    if show_counterfactual and report.its_results:
        for its in report.its_results:
            ax.plot(
                its.counterfactual.index,
                its.counterfactual.values,
                linestyle="--",
                alpha=0.4,
                linewidth=0.8,
            )

    ax.set_xlabel("Date")
    ax.set_ylabel("Value")
    ax.set_title("Time Series with Structural Breaks")
    ax.legend(loc="best", fontsize=8)
    ax.set_xlim(series.index[0], series.index[-1])
    fig.tight_layout()

    return fig


def plot_summary_matrix(
    report: AnalysisReport,
    ax: plt.Axes | None = None,
) -> Figure:
    """Plot the summary matrix as a heatmap of p-values.

    Cells are colored by corrected p-value significance.
    """
    if report.summary_matrix is None or report.summary_matrix.empty:
        fig, ax_new = plt.subplots()
        ax_new.text(0.5, 0.5, "No results to display", ha="center", va="center")
        return fig

    if ax is None:
        fig, ax = plt.subplots(figsize=(10, max(3, len(report.summary_matrix) * 0.5)))
    else:
        fig = ax.get_figure()

    matrix = report.summary_matrix

    # Extract p-value columns for heatmap
    p_cols = [c for c in matrix.columns if c.endswith("_p") or c == "p_corrected"]
    if not p_cols:
        ax.text(0.5, 0.5, "No p-value columns found", ha="center", va="center")
        return fig

    p_data = matrix[p_cols].apply(pd.to_numeric, errors="coerce")

    im = ax.imshow(p_data.values, cmap="RdYlGn", aspect="auto", vmin=0, vmax=0.1)
    ax.set_xticks(range(len(p_cols)))
    ax.set_xticklabels(p_cols, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(p_data)))
    ax.set_yticklabels(p_data.index, fontsize=8)

    # Annotate cells
    for i in range(len(p_data)):
        for j in range(len(p_cols)):
            val = p_data.iloc[i, j]
            if pd.notna(val):
                ax.text(j, i, f"{val:.3f}", ha="center", va="center", fontsize=7)

    ax.set_title("P-value Heatmap (green = significant)")
    fig.colorbar(im, ax=ax, label="p-value")
    fig.tight_layout()

    return fig
