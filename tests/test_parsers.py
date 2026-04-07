"""Tests for PR and snapshot parsing logic."""

from prism.collectors.pulls import parse_pr_node
from prism.collectors.repo_meta import parse_snapshot_from_node


class TestParsePrNode:
    """Tests for parse_pr_node — the core PR data extraction."""

    def test_full_pr_node(self, sample_pr_node):
        result = parse_pr_node(sample_pr_node, "acme", "widget")

        assert result["repo_owner"] == "acme"
        assert result["repo_name"] == "widget"
        assert result["pr_number"] == 42
        assert result["title"] == "Fix rate limiting in collector"
        assert result["state"] == "MERGED"
        assert result["was_merged"] is True
        assert result["author_login"] == "alice"
        assert result["author_type"] == "User"
        assert result["author_association"] == "MEMBER"
        assert result["author_account_created_at"] == "2020-01-01T00:00:00Z"
        assert result["changed_files"] == 3
        assert result["additions"] == 45
        assert result["deletions"] == 12
        assert result["created_at"] == "2025-06-15T10:30:00Z"
        assert result["merged_at"] == "2025-06-16T14:00:00Z"

    def test_review_extraction(self, sample_pr_node):
        result = parse_pr_node(sample_pr_node, "o", "r")

        assert result["total_review_count"] == 2
        assert result["first_review_submitted_at"] == "2025-06-15T12:00:00Z"
        assert result["first_review_author_login"] == "bob"
        assert result["first_review_author_type"] == "User"
        assert "bob:User" in result["all_reviewer_logins_and_types"]
        assert "carol:User" in result["all_reviewer_logins_and_types"]

    def test_comment_counts(self, sample_pr_node):
        result = parse_pr_node(sample_pr_node, "o", "r")
        assert result["total_comment_count"] == 5
        assert result["total_review_comment_count"] == 3

    def test_labels(self, sample_pr_node):
        result = parse_pr_node(sample_pr_node, "o", "r")
        assert result["label_names"] == ["bug", "priority:high"]

    def test_closing_issues(self, sample_pr_node):
        result = parse_pr_node(sample_pr_node, "o", "r")
        assert result["has_closing_issue_reference"] is True

    def test_requested_reviewers(self, sample_pr_node):
        result = parse_pr_node(sample_pr_node, "o", "r")
        assert "dave:User" in result["requested_reviewer_logins_and_types"]

    def test_raw_preserved(self, sample_pr_node):
        result = parse_pr_node(sample_pr_node, "o", "r")
        assert result["raw"] is sample_pr_node

    def test_bot_author(self, sample_pr_node_bot):
        result = parse_pr_node(sample_pr_node_bot, "dep", "core")

        assert result["author_login"] == "dependabot[bot]"
        assert result["author_type"] == "Bot"
        assert result["author_association"] == "NONE"
        assert result["total_review_count"] == 0
        assert result["first_review_submitted_at"] is None
        assert result["first_review_author_login"] is None
        assert result["all_reviewer_logins_and_types"] is None
        assert result["label_names"] == ["dependencies"]
        assert result["has_closing_issue_reference"] is False

    def test_minimal_node_null_safety(self, sample_pr_node_minimal):
        """Ensure parser doesn't crash on null/missing fields."""
        result = parse_pr_node(sample_pr_node_minimal, "x", "y")

        assert result["pr_number"] == 1
        assert result["state"] == "OPEN"
        assert result["was_merged"] is False
        assert result["author_login"] is None
        assert result["author_type"] is None
        assert result["total_review_count"] == 0
        assert result["total_comment_count"] == 0
        assert result["label_names"] == []
        assert result["has_closing_issue_reference"] is False
        assert result["requested_reviewer_logins_and_types"] is None


class TestParseSnapshotFromNode:
    """Tests for parse_snapshot_from_node."""

    def test_full_snapshot(self, sample_repo_snapshot_node):
        result = parse_snapshot_from_node(sample_repo_snapshot_node, "acme", "widget")

        assert result is not None
        assert result["owner"] == "acme"
        assert result["repo"] == "widget"
        assert result["star_count"] == 15000
        assert result["open_issue_count"] == 120
        assert result["closed_issue_count"] == 800
        assert result["open_pr_count"] == 25
        assert result["closed_pr_count"] == 2500
        assert result["watcher_count"] == 300
        assert result["fork_count"] == 1200
        assert result["pushed_at"] == "2025-06-20T18:00:00Z"
        assert result["is_archived"] is False
        assert result["default_branch_name"] == "main"
        assert result["has_contributing_md"] is True
        assert result["has_security_md"] is True
        assert result["has_code_of_conduct_md"] is False
        assert "snapshot_collected_at" in result

    def test_null_node_returns_none(self):
        assert parse_snapshot_from_node(None, "o", "r") is None

    def test_missing_default_branch(self):
        node = {
            "stargazerCount": 100,
            "openIssues": {"totalCount": 5},
            "closedIssues": {"totalCount": 10},
            "openPRs": {"totalCount": 1},
            "closedPRs": {"totalCount": 20},
            "watchers": {"totalCount": 10},
            "forkCount": 3,
            "pushedAt": None,
            "isArchived": True,
            "defaultBranchRef": None,
        }
        result = parse_snapshot_from_node(node, "o", "r")

        assert result["star_count"] == 100
        assert result["is_archived"] is True
        assert result["default_branch_name"] is None
        assert result["has_contributing_md"] is False
        assert result["has_security_md"] is False
        assert result["has_code_of_conduct_md"] is False
