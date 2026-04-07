"""Tests for the GitHub GraphQL API client."""

from prism.github_client import (
    RetryNeededError,
    build_batched_snapshot_query,
    build_combined_first_page_query,
    build_pr_page_query,
    build_snapshot_only_query,
)


class TestQueryBuilders:
    """Tests for GraphQL query string generation."""

    def test_combined_first_page_query_contains_repo(self):
        q = build_combined_first_page_query("torvalds", "linux", 100)
        assert 'owner: "torvalds"' in q
        assert 'name: "linux"' in q
        assert "first: 100" in q
        assert "stargazerCount" in q
        assert "pullRequests" in q

    def test_combined_query_escapes_quotes(self):
        q = build_combined_first_page_query('some"owner', 'some"repo', 50)
        assert r'some\"owner' in q
        assert r'some\"repo' in q

    def test_pr_page_query_with_cursor(self):
        q = build_pr_page_query("owner", "repo", 50, "abc123cursor")
        assert 'after: "abc123cursor"' in q
        assert "first: 50" in q
        assert "stargazerCount" not in q  # no snapshot in page query

    def test_pr_page_query_without_cursor(self):
        q = build_pr_page_query("owner", "repo", 100, None)
        assert "after:" not in q

    def test_snapshot_only_query(self):
        q = build_snapshot_only_query("microsoft", "vscode")
        assert 'owner: "microsoft"' in q
        assert "stargazerCount" in q
        # Snapshot has PR *counts* (openPRs/closedPRs) but no paginated nodes
        assert "pageInfo" not in q
        assert "nodes" not in q

    def test_batched_snapshot_query(self):
        repos = [("owner1", "repo1"), ("owner2", "repo2"), ("owner3", "repo3")]
        q = build_batched_snapshot_query(repos)
        assert "r0:" in q
        assert "r1:" in q
        assert "r2:" in q
        assert 'owner: "owner1"' in q
        assert 'owner: "owner3"' in q
        assert "rateLimit" in q

    def test_batched_snapshot_empty(self):
        q = build_batched_snapshot_query([])
        assert "rateLimit" in q


class TestRetryNeededError:
    def test_should_reduce_default_false(self):
        exc = RetryNeededError("test error")
        assert exc.should_reduce is False
        assert str(exc) == "test error"

    def test_should_reduce_true(self):
        exc = RetryNeededError("server error", should_reduce=True)
        assert exc.should_reduce is True
