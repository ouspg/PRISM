"""Rate-limit-aware synchronous GitHub GraphQL API client.

Ported from the proven collect_pr_data.py patterns:
- Combined snapshot + first PR page queries (saves 1 request/repo)
- Cursor-based pagination with adaptive page-size reduction
- Exponential backoff on 403/429/502/503
- Proactive rate-limit sleep when remaining budget is low
"""

from __future__ import annotations

import logging
import time
from typing import Any

import requests

log = logging.getLogger("prism.github")

# ──────────────────────────────────────────────────────────────────────
# GraphQL fragments
# ──────────────────────────────────────────────────────────────────────

PR_NODE_FIELDS = """
        number
        title
        body
        state
        createdAt
        mergedAt
        closedAt
        merged
        author {
          login
          ... on User {
            __typename
            createdAt
          }
          ... on Bot {
            __typename
          }
          ... on EnterpriseUserAccount {
            __typename
          }
          ... on Mannequin {
            __typename
          }
        }
        authorAssociation
        changedFiles
        additions
        deletions
        reviews(first: 100) {
          totalCount
          nodes {
            submittedAt
            author {
              login
              ... on User { __typename }
              ... on Bot { __typename }
              ... on EnterpriseUserAccount { __typename }
              ... on Mannequin { __typename }
            }
          }
        }
        comments {
          totalCount
        }
        reviewThreads {
          totalCount
        }
        labels(first: 50) {
          nodes {
            name
          }
        }
        closingIssuesReferences(first: 1) {
          totalCount
        }
        reviewRequests(first: 50) {
          nodes {
            requestedReviewer {
              ... on User {
                login
                __typename
              }
              ... on Bot {
                login
                __typename
              }
              ... on Team {
                name
                __typename
              }
              ... on Mannequin {
                login
                __typename
              }
            }
          }
        }
"""

REPO_SNAPSHOT_FIELDS_GQL = """
    stargazerCount
    openIssues: issues(states: OPEN) { totalCount }
    closedIssues: issues(states: CLOSED) { totalCount }
    openPRs: pullRequests(states: OPEN) { totalCount }
    closedPRs: pullRequests(states: [CLOSED, MERGED]) { totalCount }
    watchers { totalCount }
    forkCount
    pushedAt
    isArchived
    defaultBranchRef {
      name
      target {
        ... on Commit {
          contributingMd: file(path: "CONTRIBUTING.md") { oid }
          securityMd: file(path: "SECURITY.md") { oid }
          codeOfConductMd: file(path: "CODE_OF_CONDUCT.md") { oid }
        }
      }
    }
"""

GRAPHQL_ENDPOINT = "https://api.github.com/graphql"


# ──────────────────────────────────────────────────────────────────────
# Query builders
# ──────────────────────────────────────────────────────────────────────


def build_combined_first_page_query(owner: str, repo: str, page_size: int) -> str:
    """Repo snapshot + first page of PRs in a single request."""
    o = owner.replace('"', '\\"')
    r = repo.replace('"', '\\"')
    return f"""query CombinedFirstPage {{
  rateLimit {{ remaining cost resetAt }}
  repository(owner: "{o}", name: "{r}") {{
{REPO_SNAPSHOT_FIELDS_GQL}
    pullRequests(
      first: {page_size}
      orderBy: {{field: CREATED_AT, direction: DESC}}
    ) {{
      totalCount
      pageInfo {{
        hasNextPage
        endCursor
      }}
      nodes {{
{PR_NODE_FIELDS}
      }}
    }}
  }}
}}"""


def build_pr_page_query(
    owner: str, repo: str, page_size: int, cursor: str | None
) -> str:
    """Subsequent page of PRs (page 2+)."""
    o = owner.replace('"', '\\"')
    r = repo.replace('"', '\\"')
    after = f', after: "{cursor}"' if cursor else ""
    return f"""query PRPage {{
  rateLimit {{ remaining cost resetAt }}
  repository(owner: "{o}", name: "{r}") {{
    pullRequests(
      first: {page_size}
      orderBy: {{field: CREATED_AT, direction: DESC}}
      {after}
    ) {{
      totalCount
      pageInfo {{
        hasNextPage
        endCursor
      }}
      nodes {{
{PR_NODE_FIELDS}
      }}
    }}
  }}
}}"""


def build_snapshot_only_query(owner: str, repo: str) -> str:
    """Lightweight snapshot-only query for fallback."""
    o = owner.replace('"', '\\"')
    r = repo.replace('"', '\\"')
    return f"""query RepoSnapshot {{
  rateLimit {{ remaining cost resetAt }}
  repository(owner: "{o}", name: "{r}") {{
{REPO_SNAPSHOT_FIELDS_GQL}
  }}
}}"""


def build_batched_snapshot_query(repos: list[tuple[str, str]]) -> str:
    """Aliased batch snapshot query for up to N repos in one request."""
    fragments: list[str] = []
    for idx, (owner, repo) in enumerate(repos):
        o = owner.replace('"', '\\"')
        r = repo.replace('"', '\\"')
        fragments.append(
            f'  r{idx}: repository(owner: "{o}", name: "{r}") '
            f"{{\n{REPO_SNAPSHOT_FIELDS_GQL}  }}"
        )
    body = "\n".join(fragments)
    return f"query SnapshotBatch {{\n  rateLimit {{ remaining cost resetAt }}\n{body}\n}}"


# ──────────────────────────────────────────────────────────────────────
# Retry infrastructure
# ──────────────────────────────────────────────────────────────────────


class RetryNeededError(Exception):
    """Raised when the caller should retry, possibly with a smaller page."""

    def __init__(self, message: str, *, should_reduce: bool = False) -> None:
        super().__init__(message)
        self.should_reduce = should_reduce


def _parse_wait_from_headers(resp: requests.Response, *, default: float) -> float:
    """Extract wait time from rate-limit or Retry-After headers."""
    retry_after = resp.headers.get("Retry-After")
    if retry_after:
        try:
            return max(int(retry_after), 1)
        except (ValueError, TypeError):
            pass
    reset_at = resp.headers.get("X-RateLimit-Reset")
    if reset_at:
        try:
            return max(int(reset_at) - int(time.time()), 1) + 1
        except (ValueError, TypeError):
            pass
    return default


# ──────────────────────────────────────────────────────────────────────
# Client
# ──────────────────────────────────────────────────────────────────────


class GitHubClient:
    """Synchronous GitHub GraphQL client with rate-limit handling and retry."""

    def __init__(
        self,
        token: str,
        *,
        rate_limit_buffer: int = 300,
        rate_limit_sleep_secs: int = 60,
        polite_sleep_secs: float = 0.5,
        max_retries: int = 10,
        retry_backoff_base: int = 2,
        request_timeout: int = 90,
        default_page_size: int = 100,
        min_page_size: int = 5,
    ):
        self.rate_limit_buffer = rate_limit_buffer
        self.rate_limit_sleep_secs = rate_limit_sleep_secs
        self.polite_sleep_secs = polite_sleep_secs
        self.max_retries = max_retries
        self.retry_backoff_base = retry_backoff_base
        self.request_timeout = request_timeout
        self.default_page_size = default_page_size
        self.min_page_size = min_page_size

        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "ouspg-prism/0.1",
        })

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.session.close()

    def close(self):
        self.session.close()

    # ── Low-level GraphQL POST ──

    def _post_graphql(
        self, query: str, *, label: str = "", attempt: int = 1
    ) -> dict[str, Any]:
        """Single-shot GraphQL POST. Raises NeedsRetry on transient errors."""
        try:
            resp = self.session.post(
                GRAPHQL_ENDPOINT,
                json={"query": query},
                timeout=self.request_timeout,
            )
        except requests.exceptions.ConnectionError as exc:
            raise RetryNeededError(
                f"[{label}] Connection error: {exc}", should_reduce=False
            ) from exc
        except requests.exceptions.Timeout as exc:
            raise RetryNeededError(
                f"[{label}] Timeout after {self.request_timeout}s", should_reduce=True
            ) from exc
        except requests.exceptions.RequestException as exc:
            raise RetryNeededError(
                f"[{label}] Request error: {exc}", should_reduce=False
            ) from exc

        # Rate-limit (403/429)
        if resp.status_code in (403, 429):
            wait = _parse_wait_from_headers(
                resp, default=self.retry_backoff_base**attempt
            )
            log.warning(
                "[%s] Rate-limited (HTTP %d). Sleeping %ds",
                label, resp.status_code, wait,
            )
            time.sleep(wait)
            raise RetryNeededError(f"HTTP {resp.status_code} rate-limit", should_reduce=False)

        # Transient server errors (502/503)
        if resp.status_code in (502, 503):
            wait = _parse_wait_from_headers(
                resp, default=self.retry_backoff_base**attempt
            )
            log.warning(
                "[%s] Server error (HTTP %d). Sleeping %ds",
                label, resp.status_code, wait,
            )
            time.sleep(wait)
            raise RetryNeededError(
                f"HTTP {resp.status_code} server error", should_reduce=True
            )

        try:
            resp.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            raise RetryNeededError(
                f"[{label}] HTTP {resp.status_code}", should_reduce=False
            ) from exc

        body: dict[str, Any] = resp.json()

        # GraphQL-level errors
        if "errors" in body:
            err_msgs = [e.get("message", str(e)) for e in body["errors"]]
            unique_msgs = list(dict.fromkeys(err_msgs))

            is_resource_limit = any(
                any(kw in m.lower() for kw in ("resource limit", "something went wrong"))
                for m in unique_msgs
            )
            is_transient = any(
                any(kw in m.lower() for kw in ("loading", "timeout", "abuse", "fetching"))
                for m in unique_msgs
            )

            if is_resource_limit or is_transient:
                wait = self.retry_backoff_base**attempt
                log.warning(
                    "[%s] GraphQL transient errors: %s — sleeping %ds",
                    label, unique_msgs, wait,
                )
                time.sleep(wait)
                raise RetryNeededError(
                    f"GraphQL transient: {unique_msgs}",
                    should_reduce=is_resource_limit,
                )

            # Non-transient errors with data are partial results — OK
            if body.get("data"):
                log.debug("[%s] GraphQL partial errors (non-fatal): %s", label, unique_msgs)
                return body

            raise RuntimeError(
                f"[{label}] Non-transient GraphQL errors with no data: {unique_msgs}"
            )

        return body

    # ── High-level execute with retry + adaptive page-size ──

    def execute_graphql(
        self,
        query: str,
        *,
        label: str = "",
        page_size_ref: list[int] | None = None,
        owner: str = "",
        repo: str = "",
        cursor: str | None = None,
        is_pr_query: bool = False,
        is_combined_query: bool = False,
    ) -> dict[str, Any]:
        """Execute a GraphQL query with full retry and adaptive page-size reduction."""
        current_page_size = page_size_ref[0] if page_size_ref else self.default_page_size

        for attempt in range(1, self.max_retries + 1):
            try:
                body = self._post_graphql(query, label=label, attempt=attempt)

                # Log rate limit
                rl = body.get("data", {}).get("rateLimit", {})
                remaining = rl.get("remaining")
                log.info(
                    "[%s] OK rate_limit remaining=%s cost=%s resetAt=%s",
                    label, remaining, rl.get("cost", "?"), rl.get("resetAt", "?"),
                )

                # Proactive sleep when budget is low
                if remaining is not None and int(remaining) < self.rate_limit_buffer:
                    log.warning(
                        "Rate-limit remaining (%s) below %d — sleeping %ds",
                        remaining, self.rate_limit_buffer, self.rate_limit_sleep_secs,
                    )
                    time.sleep(self.rate_limit_sleep_secs)

                return body

            except RetryNeededError as exc:
                log.warning("[%s] attempt %d/%d: %s", label, attempt, self.max_retries, exc)

                if (
                    exc.should_reduce
                    and (is_pr_query or is_combined_query)
                    and page_size_ref is not None
                ):
                    new_size = max(current_page_size // 2, self.min_page_size)
                    if new_size < current_page_size:
                        log.warning(
                            "[%s] Reducing page_size %d -> %d",
                            label, current_page_size, new_size,
                        )
                        current_page_size = new_size
                        page_size_ref[0] = new_size
                        if is_combined_query:
                            query = build_combined_first_page_query(owner, repo, new_size)
                        else:
                            query = build_pr_page_query(owner, repo, new_size, cursor)

                wait = min(self.retry_backoff_base**attempt, 120)
                log.info("[%s] Sleeping %ds before retry", label, wait)
                time.sleep(wait)

            except RuntimeError:
                raise

        raise RuntimeError(f"[{label}] Exhausted {self.max_retries} retries")

    # ── Convenience: probe rate limit ──

    def probe_rate_limit(self) -> dict[str, Any]:
        """Check current rate-limit budget. Returns rateLimit dict."""
        resp = self.session.post(
            GRAPHQL_ENDPOINT,
            json={"query": "{ rateLimit { remaining cost resetAt } }"},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json().get("data", {}).get("rateLimit", {})
