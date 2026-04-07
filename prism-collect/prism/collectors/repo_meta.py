"""Repository snapshot collector via GitHub GraphQL API.

Captures point-in-time metrics. Can run standalone or as part of the
combined first-page query in the pulls collector.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from prism.collectors.base import BaseCollector
from prism.github_client import (
    build_batched_snapshot_query,
    build_snapshot_only_query,
)
from prism.models import Repo

log = logging.getLogger("prism.collector.repo_meta")


# ──────────────────────────────────────────────────────────────────────
# Snapshot parsing (ported from collect_pr_data.py)
# ──────────────────────────────────────────────────────────────────────


def parse_snapshot_from_node(
    repo_node: dict[str, Any], owner: str, repo: str
) -> dict[str, Any] | None:
    """Parse repository snapshot fields from a GraphQL repository node."""
    if repo_node is None:
        return None

    dbr = repo_node.get("defaultBranchRef") or {}
    db_name = dbr.get("name", "")
    target = dbr.get("target") or {}

    return {
        "owner": owner,
        "repo": repo,
        "snapshot_collected_at": datetime.now(UTC).isoformat(),
        "star_count": repo_node.get("stargazerCount"),
        "open_issue_count": (repo_node.get("openIssues") or {}).get("totalCount"),
        "closed_issue_count": (repo_node.get("closedIssues") or {}).get("totalCount"),
        "open_pr_count": (repo_node.get("openPRs") or {}).get("totalCount"),
        "closed_pr_count": (repo_node.get("closedPRs") or {}).get("totalCount"),
        "watcher_count": (repo_node.get("watchers") or {}).get("totalCount"),
        "fork_count": repo_node.get("forkCount"),
        "pushed_at": repo_node.get("pushedAt"),
        "is_archived": repo_node.get("isArchived"),
        "default_branch_name": db_name or None,
        "has_contributing_md": bool(target.get("contributingMd")),
        "has_security_md": bool(target.get("securityMd")),
        "has_code_of_conduct_md": bool(target.get("codeOfConductMd")),
    }


def upsert_snapshot(
    session: Session, repo_id: str, snapshot: dict[str, Any]
) -> None:
    """Insert a new snapshot row into repo_snapshots.

    Snapshots are append-only (each collection run creates a new row)
    to build time-series data.
    """
    session.execute(
        text("""
            INSERT INTO repo_snapshots (
                repo_id, snapshot_collected_at, star_count,
                open_issue_count, closed_issue_count,
                open_pr_count, closed_pr_count,
                watcher_count, fork_count, pushed_at, is_archived,
                default_branch_name, has_contributing_md,
                has_security_md, has_code_of_conduct_md, raw
            ) VALUES (
                :repo_id, :snapshot_collected_at, :star_count,
                :open_issue_count, :closed_issue_count,
                :open_pr_count, :closed_pr_count,
                :watcher_count, :fork_count, :pushed_at, :is_archived,
                :default_branch_name, :has_contributing_md,
                :has_security_md, :has_code_of_conduct_md, :raw
            )
        """),
        {
            "repo_id": repo_id,
            "snapshot_collected_at": snapshot["snapshot_collected_at"],
            "star_count": snapshot["star_count"],
            "open_issue_count": snapshot["open_issue_count"],
            "closed_issue_count": snapshot["closed_issue_count"],
            "open_pr_count": snapshot["open_pr_count"],
            "closed_pr_count": snapshot["closed_pr_count"],
            "watcher_count": snapshot["watcher_count"],
            "fork_count": snapshot["fork_count"],
            "pushed_at": snapshot["pushed_at"],
            "is_archived": snapshot["is_archived"],
            "default_branch_name": snapshot["default_branch_name"],
            "has_contributing_md": snapshot["has_contributing_md"],
            "has_security_md": snapshot["has_security_md"],
            "has_code_of_conduct_md": snapshot["has_code_of_conduct_md"],
            "raw": json.dumps({}),
        },
    )
    session.commit()


# ──────────────────────────────────────────────────────────────────────
# Collector
# ──────────────────────────────────────────────────────────────────────


class RepoMetaCollector(BaseCollector):
    """Standalone snapshot collector. Also used for batch follow-up."""

    collector_name = "repo_meta"

    def collect(self, repo: Repo) -> int:
        """Fetch snapshot for a single repo."""
        owner = repo.owner
        name = repo.repo
        repo_key = f"{owner}/{name}"
        sync_id = self.log_sync_start(repo)

        try:
            query = build_snapshot_only_query(owner, name)
            body = self.client.execute_graphql(query, label=f"{repo_key}/snapshot")

            repo_node = body.get("data", {}).get("repository")
            if repo_node is None:
                log.warning("[%s] Not found for snapshot", repo_key)
                self.log_sync_complete(sync_id, 0, error="not found")
                return 0

            snapshot = parse_snapshot_from_node(repo_node, owner, name)
            if snapshot:
                upsert_snapshot(self.session, str(repo.id), snapshot)
                log.info("[%s] Snapshot: stars=%s forks=%s",
                         repo_key, snapshot["star_count"], snapshot["fork_count"])
                self.log_sync_complete(sync_id, 1)
                return 1

            self.log_sync_complete(sync_id, 0, error="empty snapshot")
            return 0

        except Exception as exc:
            self.log_sync_complete(sync_id, 0, error=str(exc))
            raise

    def collect_batch_missing(self, repos: list[Repo]) -> int:
        """Fetch snapshots for multiple repos using batched GraphQL queries."""
        if not repos:
            return 0

        log.info("Batched snapshot follow-up: %d repos", len(repos))
        batch_size = self.client.default_page_size  # reuse as batch size (10 in settings)
        from prism.settings import Settings

        batch_size = Settings().snapshot_batch_size
        collected = 0

        repo_tuples = [(r.owner, r.repo) for r in repos]
        repo_map = {f"{r.owner}/{r.repo}": r for r in repos}

        for i in range(0, len(repo_tuples), batch_size):
            batch = repo_tuples[i : i + batch_size]
            label = f"snapshot-batch-{i // batch_size + 1}"
            query = build_batched_snapshot_query(batch)

            try:
                body = self.client.execute_graphql(query, label=label)
            except RuntimeError as exc:
                log.error("[%s] Batch query failed: %s — falling back", label, exc)
                for owner, name in batch:
                    key = f"{owner}/{name}"
                    r = repo_map[key]
                    try:
                        self.collect(r)
                        collected += 1
                    except Exception as fb_exc:
                        log.error("[%s] Fallback also failed: %s", key, fb_exc)
                    time.sleep(self.client.polite_sleep_secs)
                continue

            data = body.get("data", {})
            for idx, (owner, name) in enumerate(batch):
                node = data.get(f"r{idx}")
                if node is not None:
                    snapshot = parse_snapshot_from_node(node, owner, name)
                    if snapshot:
                        key = f"{owner}/{name}"
                        upsert_snapshot(self.session, str(repo_map[key].id), snapshot)
                        collected += 1
                        log.debug("[%s] Snapshot OK for %s", label, key)
                else:
                    log.warning("[%s] No data for %s/%s", label, owner, name)

            time.sleep(self.client.polite_sleep_secs)

        log.info("Batched snapshot follow-up complete: %d recovered", collected)
        return collected
