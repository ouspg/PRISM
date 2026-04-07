"""Multiple testing correction (Benjamini-Hochberg FDR by default)."""

from __future__ import annotations

import numpy as np
from statsmodels.stats.multitest import multipletests

from prism_analyze.report.models import CorrectionResult


def apply_correction(
    pvalues: dict[str, float],
    method: str = "fdr_bh",
    alpha: float = 0.05,
) -> CorrectionResult:
    """Apply multiple testing correction to a set of p-values.

    Parameters
    ----------
    pvalues:
        Mapping of inflection_id → raw p-value.
    method:
        Correction method passed to ``statsmodels.stats.multitest.multipletests``.
    alpha:
        Family-wise significance level.

    Returns
    -------
    CorrectionResult
    """
    if not pvalues:
        return CorrectionResult(
            method=method,
            alpha=alpha,
            raw_pvalues={},
            corrected_pvalues={},
            rejected={},
        )

    ids = list(pvalues.keys())
    raw = np.array([pvalues[k] for k in ids])

    rejected_arr, corrected_arr, _, _ = multipletests(raw, alpha=alpha, method=method)

    return CorrectionResult(
        method=method,
        alpha=alpha,
        raw_pvalues=dict(zip(ids, raw.tolist())),
        corrected_pvalues=dict(zip(ids, corrected_arr.tolist())),
        rejected=dict(zip(ids, rejected_arr.tolist())),
    )
