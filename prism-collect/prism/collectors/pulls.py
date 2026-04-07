"""Pull request collector via GitHub GraphQL API.

Implements the combined snapshot+first-page query pattern, cursor-based
pagination, date-window filtering, and Postgres upsert.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text

from prism.collectors.base import BaseCollector
from prism.collectors.repo_meta import parse_snapshot_from_node
from prism.github_client import (
    build_combined_first_page_query,
    build_pr_page_query,
)
from prism.models import Repo

log = logging.getLogger("prism.collector.pulls")


# ──────────────────────────────────────────────────────────────────────
# PR node parsing (ported from collect_pr_data.py)
# ──────────────────────────────────────────────────────────────────────


def _safe(val: Any, default: str = "") -> str:
    if val is None:
        return default
    return str(val)


def parse_pr_node(node: dict[str, Any], owner: str, repo: str) -> dict[str, Any]:
    """Parse a single PR GraphQL node into a flat dict for DB insertion."""
    author = node.get("author") or {}
    author_login = author.get("login", "")
    author_typename = author.get("__typename", "")
    author_created_at = author.get("createdAt")

    # Reviews
    reviews_data = node.get("reviews") or {}
    review_nodes = reviews_data.get("nodes") or []
    total_review_count = reviews_data.get("totalCount", 0)

    # First review
    first_review_submitted_at = None
    first_review_author_login = ""
    first_review_author_type = ""
    if review_nodes:
        first = review_nodes[0]
        first_review_submitted_at = first.get("submittedAt")
        fr_author = first.get("author") or {}
        first_review_author_login = fr_author.get("login", "")
        first_review_author_type = fr_author.get("__typename", "")

    # All unique reviewers
    seen_reviewers: dict[str, str] = {}
    for rv in review_nodes:
        rv_author = rv.get("author") or {}
        rv_login = rv_author.get("login", "")
        rv_type = rv_author.get("__typename", "")
        if rv_login and rv_login not in seen_reviewers:
            seen_reviewers[rv_login] = rv_type
    all_reviewer_str = ",".join(f"{login}:{typ}" for login, typ in seen_reviewers.items())

    # Labels
    label_nodes = (node.get("labels") or {}).get("nodes") or []
    label_names = [ln.get("name", "") for ln in label_nodes if ln.get("name")]

    # Closing issue references
    closing_refs = node.get("closingIssuesReferences") or {}
    has_closing = closing_refs.get("totalCount", 0) > 0

    # Requested reviewers
    rr_nodes = (node.get("reviewRequests") or {}).get("nodes") or []
    rr_parts: list[str] = []
    for rr in rr_nodes:
        reviewer = rr.get("requestedReviewer") or {}
        rr_login = reviewer.get("login") or reviewer.get("name", "")
        rr_type = reviewer.get("__typename", "")
        if rr_login:
            rr_parts.append(f"{rr_login}:{rr_type}")
    requested_reviewer_str = ",".join(rr_parts)

    total_comment_count = (node.get("comments") or {}).get("totalCount", 0)
    total_review_comment_count = (node.get("reviewThreads") or {}).get("totalCount", 0)

    return {
        "repo_owner": owner,
        "repo_name": repo,
        "pr_number": node.get("number"),
        "title": node.get("title"),
        "body": node.get("body"),
        "state": node.get("state"),
        "created_at": node.get("createdAt"),
        "merged_at": node.get("mergedAt"),
        "closed_at": node.get("closedAt"),
        "was_merged": node.get("merged"),
        "author_login": author_login or None,
        "author_type": author_typename or None,
        "author_association": node.get("authorAssociation"),
        "author_account_created_at": author_created_at,
        "changed_files": node.get("changedFiles"),
        "additions": node.get("additions"),
        "deletions": node.get("deletions"),
        "total_review_count": total_review_count,
        "total_comment_count": total_comment_count,
        "total_review_comment_count": total_review_comment_count,
        "label_names": label_names,
        "has_closing_issue_reference": has_closing,
        "requested_reviewer_logins_and_types": requested_reviewer_str or None,
        "first_review_submitted_at": first_review_submitted_at,
        "first_review_author_login": first_review_author_login or None,
        "first_review_author_type": first_review_author_type or None,
        "all_reviewer_logins_and_types": all_reviewer_str or None,
        "raw": node,  # full GraphQL node as JSONB
    }


def _upsert_pr(session, repo_id: str, pr: dict[str, Any]) -> None:
    """Upsert a single PR record into the pull_requests table."""
    session.execute(
        text("""
            INSERT INTO pull_requests (
                repo_id, pr_number, title, body, state,
                created_at, merged_at, closed_at, was_merged,
                author_login, author_type, author_association,
                author_account_created_at, changed_files, additions, deletions,
                total_review_count, total_comment_count, total_review_comment_count,
                label_names, has_closing_issue_reference,
                requested_reviewer_logins_and_types,
                first_review_submitted_at, first_review_author_login,
                first_review_author_type, all_reviewer_logins_and_types,
                raw, collected_at
            ) VALUES (
                :repo_id, :pr_number, :title, :body, :state,
                :created_at, :merged_at, :closed_at, :was_merged,
                :author_login, :author_type, :author_association,
                :author_account_created_at, :changed_files, :additions, :deletions,
                :total_review_count, :total_comment_count, :total_review_comment_count,
                :label_names, :has_closing_issue_reference,
                :requested_reviewer_logins_and_types,
                :first_review_submitted_at, :first_review_author_login,
                :first_review_author_type, :all_reviewer_logins_and_types,
                :raw, :collected_at
            )
            ON CONFLICT (repo_id, pr_number) DO UPDATE SET
                title = EXCLUDED.title,
                body = EXCLUDED.body,
                state = EXCLUDED.state,
                merged_at = EXCLUDED.merged_at,
                closed_at = EXCLUDED.closed_at,
                was_merged = EXCLUDED.was_merged,
                author_login = EXCLUDED.author_login,
                author_type = EXCLUDED.author_type,
                author_association = EXCLUDED.author_association,
                changed_files = EXCLUDED.changed_files,
                additions = EXCLUDED.additions,
                deletions = EXCLUDED.deletions,
                total_review_count = EXCLUDED.total_review_count,
                total_comment_count = EXCLUDED.total_comment_count,
                total_review_comment_count = EXCLUDED.total_review_comment_count,
                label_names = EXCLUDED.label_names,
                has_closing_issue_reference = EXCLUDED.has_closing_issue_reference,
                requested_reviewer_logins_and_types = EXCLUDED.requested_reviewer_logins_and_types,
                first_review_submitted_at = EXCLUDED.first_review_submitted_at,
                first_review_author_login = EXCLUDED.first_review_author_login,
                first_review_author_type = EXCLUDED.first_review_author_type,
                all_reviewer_logins_and_types = EXCLUDED.all_reviewer_logins_and_types,
                raw = EXCLUDED.raw,
                collected_at = EXCLUDED.collected_at
        """),
        {
            "repo_id": repo_id,
            "pr_number": pr["pr_number"],
            "title": pr["title"],
            "body": pr["body"],
            "state": pr["state"],
            "created_at": pr["created_at"],
            "merged_at": pr["merged_at"],
            "closed_at": pr["closed_at"],
            "was_merged": pr["was_merged"],
            "author_login": pr["author_login"],
            "author_type": pr["author_type"],
            "author_association": pr["author_association"],
            "author_account_created_at": pr["author_account_created_at"],
            "changed_files": pr["changed_files"],
            "additions": pr["additions"],
            "deletions": pr["deletions"],
            "total_review_count": pr["total_review_count"],
            "total_comment_count": pr["total_comment_count"],
            "total_review_comment_count": pr["total_review_comment_count"],
            "label_names": pr["label_names"],
            "has_closing_issue_reference": pr["has_closing_issue_reference"],
            "requested_reviewer_logins_and_types": pr["requested_reviewer_logins_and_types"],
            "first_review_submitted_at": pr["first_review_submitted_at"],
            "first_review_author_login": pr["first_review_author_login"],
            "first_review_author_type": pr["first_review_author_type"],
            "all_reviewer_logins_and_types": pr["all_reviewer_logins_and_types"],
            "raw": json.dumps(pr["raw"]),
            "collected_at": datetime.now(UTC).isoformat(),
        },
    )


# ──────────────────────────────────────────────────────────────────────
# Collector
# ──────────────────────────────────────────────────────────────────────


class PullsCollector(BaseCollector):
    """Collects PR metadata via GraphQL, upserts into pull_requests table.

    Uses the combined snapshot+first-page query to save one round-trip per repo.
    Snapshots are stored via RepoMetaCollector's upsert logic.
    """

    collector_name = "pulls"

    def collect(
        self, repo: Repo, date_start: str | None = None, date_end: str | None = None,
    ) -> int:
        """Collect all PRs within the date window for a repository.

        Uses combined first-page query (snapshot + PRs), then paginates.
        Returns number of PRs collected.
        """
        from prism.settings import Settings

        settings = Settings()
        if date_start is None:
            date_start = settings.date_start
        if date_end is None:
            date_end = settings.date_end

        owner = repo.owner
        name = repo.repo
        repo_key = f"{owner}/{name}"
        repo_id = str(repo.id)

        sync_id = self.log_sync_start(repo)
        page_size_ref = [self.client.default_page_size]
        collected_count = 0

        try:
            # Step 1: Combined snapshot + first PR page
            log.info("[%s] Fetching snapshot + first PR page (page_size=%d)",
                     repo_key, page_size_ref[0])

            query = build_combined_first_page_query(owner, name, page_size_ref[0])
            body = self.client.execute_graphql(
                query,
                label=f"{repo_key}/combined-p1",
                page_size_ref=page_size_ref,
                owner=owner,
                repo=name,
                is_combined_query=True,
            )

            repo_node = body.get("data", {}).get("repository")
            if repo_node is None:
                log.warning("[%s] Repository not found (deleted/private/renamed)", repo_key)
                self.log_sync_complete(sync_id, 0, error="repository not found")
                return 0

            # Store snapshot
            snapshot = parse_snapshot_from_node(repo_node, owner, name)
            if snapshot:
                from prism.collectors.repo_meta import upsert_snapshot

                upsert_snapshot(self.session, repo_id, snapshot)
                log.info("[%s] Snapshot saved: stars=%s forks=%s",
                         repo_key, snapshot.get("star_count"), snapshot.get("fork_count"))

            # Extract first page of PRs
            pr_data = repo_node.get("pullRequests") or {}
            page_info = pr_data.get("pageInfo", {})
            has_next_page = page_info.get("hasNextPage", False)
            cursor: str | None = page_info.get("endCursor")
            total_pr_count = pr_data.get("totalCount", 0)
            nodes = pr_data.get("nodes") or []

            end_label = date_end[:10] if date_end else "now"
            log.info("[%s] Total PRs in repo (all time): %d | Window: %s to %s",
                     repo_key, total_pr_count, date_start[:10], end_label)

            # Process first page
            page_records, stopped = self._process_nodes(
                nodes, owner, name, date_start, date_end
            )
            for pr in page_records:
                _upsert_pr(self.session, repo_id, pr)
            self.session.commit()
            collected_count += len(page_records)

            log.info("[%s] page 1: fetched %d, kept %d (total: %d) hasNext=%s",
                     repo_key, len(nodes), len(page_records), collected_count, has_next_page)

            # Step 2: Paginate remaining PRs
            page_num = 1
            while has_next_page and not stopped:
                page_num += 1
                time.sleep(self.client.polite_sleep_secs)

                query = build_pr_page_query(owner, name, page_size_ref[0], cursor)
                try:
                    pr_body = self.client.execute_graphql(
                        query,
                        label=f"{repo_key}/page-{page_num}",
                        page_size_ref=page_size_ref,
                        owner=owner,
                        repo=name,
                        cursor=cursor,
                        is_pr_query=True,
                    )
                except RuntimeError as exc:
                    log.error("[%s] page %d failed: %s", repo_key, page_num, exc)
                    self.log_sync_complete(sync_id, collected_count, error=str(exc))
                    self.update_last_synced(repo)
                    return collected_count

                resp_data = pr_body.get("data") or {}
                pr_data = (resp_data.get("repository") or {}).get("pullRequests") or {}

                if not pr_data:
                    log.warning("[%s] page %d returned null — stopping", repo_key, page_num)
                    break

                page_info = pr_data.get("pageInfo", {})
                has_next_page = page_info.get("hasNextPage", False)
                cursor = page_info.get("endCursor")
                nodes = pr_data.get("nodes") or []

                page_records, stopped = self._process_nodes(
                    nodes, owner, name, date_start, date_end
                )
                for pr in page_records:
                    _upsert_pr(self.session, repo_id, pr)
                self.session.commit()
                collected_count += len(page_records)

                log.info("[%s] page %d: fetched %d, kept %d (total: %d) hasNext=%s",
                         repo_key, page_num, len(nodes), len(page_records),
                         collected_count, has_next_page)

            log.info("[%s] COMPLETE: %d PRs collected in window (%d pages)",
                     repo_key, collected_count, page_num)

            self.log_sync_complete(sync_id, collected_count)
            self.update_last_synced(repo)
            return collected_count

        except Exception as exc:
            log.error("[%s] Collection failed: %s", repo_key, exc)
            self.log_sync_complete(sync_id, collected_count, error=str(exc))
            raise

    def _process_nodes(
        self,
        nodes: list[dict],
        owner: str,
        repo: str,
        date_start: str,
        date_end: str | None,
    ) -> tuple[list[dict[str, Any]], bool]:
        """Parse and filter PR nodes by date window.

        Returns (records, stopped_before_window).
        """
        records: list[dict[str, Any]] = []
        stopped = False

        for node in nodes:
            created = node.get("createdAt", "")
            if created:
                if date_end and created > date_end:
                    continue
                if created < date_start:
                    stopped = True
                    break
            records.append(parse_pr_node(node, owner, repo))

        return records, stopped
