"""Load, merge, and validate inflection point catalogs."""

from __future__ import annotations

import importlib.resources
from pathlib import Path

import yaml

from prism_analyze.catalog.schema import Catalog, InflectionPoint
from prism_analyze.data.schema import CatalogError


def _load_categories() -> set[str]:
    """Load the controlled vocabulary of allowed categories."""
    ref = importlib.resources.files("prism_analyze.catalog").joinpath("categories.yaml")
    with importlib.resources.as_file(ref) as path:
        data = yaml.safe_load(path.read_text())
    return set(data.get("categories", {}).keys())


def _validate_categories(catalog: Catalog, allowed: set[str]) -> None:
    """Raise CatalogError if any point uses an unknown category."""
    for point in catalog.inflection_points:
        if point.category not in allowed:
            raise CatalogError(
                f"Inflection point '{point.id}' uses unknown category "
                f"'{point.category}'. Allowed: {sorted(allowed)}."
            )


def _parse_catalog_file(path: Path) -> list[InflectionPoint]:
    """Parse a YAML catalog file into a list of InflectionPoint objects."""
    data = yaml.safe_load(path.read_text())
    if data is None:
        return []

    raw_points = data if isinstance(data, list) else data.get("inflection_points", [])
    if not isinstance(raw_points, list):
        raise CatalogError(
            f"Expected a list of inflection points in {path}, "
            f"got {type(raw_points).__name__}."
        )

    return [InflectionPoint.model_validate(p) for p in raw_points]


def load_catalog(
    path: str | Path | None = None,
    user_overrides: str | Path | None = None,
) -> Catalog:
    """Load the inflection point catalog.

    Parameters
    ----------
    path:
        Path to the primary catalog YAML.  When ``None``, the bundled
        default (``prism_analyze/catalog/ai_inflections.yaml``) is used.
    user_overrides:
        Optional path to a user catalog that adds or overrides entries.
        Entries are matched by ``id``; user entries win on conflict.

    Returns
    -------
    Catalog
    """
    # Load primary catalog
    if path is None:
        ref = importlib.resources.files("prism_analyze.catalog").joinpath(
            "ai_inflections.yaml"
        )
        with importlib.resources.as_file(ref) as p:
            points = _parse_catalog_file(p)
    else:
        points = _parse_catalog_file(Path(path))

    # Merge user overrides
    if user_overrides is not None:
        override_points = _parse_catalog_file(Path(user_overrides))
        points_by_id = {p.id: p for p in points}
        for op in override_points:
            points_by_id[op.id] = op  # user wins
        points = list(points_by_id.values())

    catalog = Catalog(inflection_points=points)

    # Validate categories
    allowed = _load_categories()
    _validate_categories(catalog, allowed)

    return catalog
