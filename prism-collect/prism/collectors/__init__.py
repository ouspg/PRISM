"""Collector registry — maps collector names to their classes."""

from prism.collectors.pulls import PullsCollector
from prism.collectors.repo_meta import RepoMetaCollector

COLLECTORS: dict[str, type] = {
    "pulls": PullsCollector,
    "repo_meta": RepoMetaCollector,
}
