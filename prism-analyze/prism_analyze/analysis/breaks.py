"""Stage 2: Agnostic structural break detection + catalog overlap."""

from __future__ import annotations

import datetime
import math

import numpy as np
import pandas as pd
from ruptures import Pelt

from prism_analyze.catalog.schema import Catalog
from prism_analyze.config import AnalysisConfig
from prism_analyze.report.models import BreakDetectionResult, CatalogOverlap


def _auto_penalty(series: pd.Series) -> float:
    """Compute a data-adaptive PELT penalty using the Birgé-Massart criterion.

    penalty = log(n) * σ²

    σ is estimated via the median absolute deviation of first differences,
    which is robust to the breaks themselves inflating the variance estimate.
    """
    n = len(series)
    diffs = np.diff(series.values)
    # MAD-based sigma: divide by 0.6745 to get consistent estimator of std dev
    mad = float(np.median(np.abs(diffs - np.median(diffs))))
    sigma = mad / 0.6745
    # Avoid degenerate case of near-zero variance (e.g. constant series)
    sigma = max(sigma, 1e-6)
    return math.log(n) * sigma ** 2


def _find_nearest_break(
    inflection_date: datetime.date,
    detected_breaks: list[pd.Timestamp],
) -> tuple[pd.Timestamp | None, int | None]:
    """Find the detected break nearest to a catalog inflection date."""
    if not detected_breaks:
        return None, None

    target = pd.Timestamp(inflection_date)
    distances = [(b, abs((b - target).days)) for b in detected_breaks]
    nearest, dist = min(distances, key=lambda x: x[1])
    return nearest, dist


def detect_breaks(
    series: pd.Series,
    catalog: Catalog,
    config: AnalysisConfig,
) -> BreakDetectionResult:
    """Run Bai-Perron (PELT) break detection, then compute catalog overlap.

    The detection is fully agnostic — it knows nothing about the catalog.
    Overlap is computed afterwards.
    """
    # --- Compute penalty ---
    if config.break_penalty_auto:
        penalty = _auto_penalty(series)
        penalty_auto = True
    else:
        penalty = config.break_penalty
        penalty_auto = False

    # --- Agnostic break detection ---
    signal = series.values.reshape(-1, 1)
    algo = Pelt(model=config.break_model, min_size=config.break_min_size, jump=1)
    raw_breaks = algo.fit_predict(signal, pen=penalty)

    # ruptures returns indices with the last element == len(signal); strip it
    break_indices = [i for i in raw_breaks if i < len(series)]

    # Apply max_breaks cap: keep only the N indices with the largest cost reduction.
    # We approximate cost reduction by the gap to the nearest neighbours.
    if config.max_breaks is not None and len(break_indices) > config.max_breaks:
        values = series.values
        costs = []
        all_idx = [0] + break_indices + [len(series)]
        for k, idx in enumerate(break_indices):
            seg_start = all_idx[k]
            seg_end = all_idx[k + 2]
            left = values[seg_start:idx]
            right = values[idx:seg_end]
            combined = values[seg_start:seg_end]
            cost_before = float(np.var(combined) * len(combined)) if len(combined) > 1 else 0.0
            cost_after = (
                float(np.var(left) * len(left)) if len(left) > 1 else 0.0
            ) + (
                float(np.var(right) * len(right)) if len(right) > 1 else 0.0
            )
            costs.append((cost_before - cost_after, idx))
        costs.sort(reverse=True)
        break_indices = sorted(idx for _, idx in costs[: config.max_breaks])

    detected_breaks = [series.index[i] for i in break_indices]

    # --- Catalog overlap ---
    overlaps: list[CatalogOverlap] = []
    for point in catalog.inflection_points:
        nearest, dist = _find_nearest_break(point.date, detected_breaks)
        in_window = dist is not None and dist <= config.overlap_tolerance_days
        overlaps.append(
            CatalogOverlap(
                inflection_id=point.id,
                inflection_date=point.date,
                nearest_break=nearest,
                distance_days=dist,
                in_window=in_window,
            )
        )

    return BreakDetectionResult(
        detected_breaks=detected_breaks,
        catalog_overlaps=overlaps,
        penalty_used=penalty,
        penalty_auto=penalty_auto,
        model_used=config.break_model,
    )
