"""Public API: Analyzer class and analyze() convenience function."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from prism_analyze.analysis.pipeline import run_pipeline
from prism_analyze.catalog.loader import load_catalog
from prism_analyze.catalog.schema import Catalog
from prism_analyze.config import AnalysisConfig
from prism_analyze.report.models import AnalysisReport


class Analyzer:
    """Reusable analysis runner.

    Holds the catalog and config (reused across metrics);
    ``.run()`` accepts the data that varies per analysis.

    Example::

        analyzer = Analyzer(catalog=load_catalog(), config=AnalysisConfig())
        report = analyzer.run(my_series)
    """

    def __init__(
        self,
        catalog: Catalog,
        config: AnalysisConfig | None = None,
    ) -> None:
        self.catalog = catalog
        self.config = config or AnalysisConfig()

    def run(
        self,
        series: pd.Series,
        panel: pd.DataFrame | None = None,
        treatment_units: list[str] | None = None,
    ) -> AnalysisReport:
        """Run the full analysis pipeline on *series*."""
        return run_pipeline(
            series=series,
            catalog=self.catalog,
            config=self.config,
            panel=panel,
            treatment_units=treatment_units,
        )


def analyze(
    series: pd.Series,
    catalog_path: str | Path | None = None,
    panel: pd.DataFrame | None = None,
    treatment_units: list[str] | None = None,
    **config_kwargs,
) -> AnalysisReport:
    """One-shot analysis — load catalog, build config, run pipeline.

    Example::

        report = analyze(my_series, fdr_alpha=0.10)
    """
    catalog = load_catalog(path=catalog_path)
    config = AnalysisConfig(**config_kwargs)
    analyzer = Analyzer(catalog=catalog, config=config)
    return analyzer.run(series, panel=panel, treatment_units=treatment_units)
