"""Pytest fixtures for PRISM tests."""

import pytest

# ──────────────────────────────────────────────────────────────────────
# Sample GraphQL response nodes for testing parsers
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture
def sample_pr_node():
    """A realistic PR node as returned by the GitHub GraphQL API."""
    return {
        "number": 42,
        "title": "Fix rate limiting in collector",
        "body": "This PR fixes the rate limiting logic.",
        "state": "MERGED",
        "createdAt": "2025-06-15T10:30:00Z",
        "mergedAt": "2025-06-16T14:00:00Z",
        "closedAt": "2025-06-16T14:00:00Z",
        "merged": True,
        "author": {
            "login": "alice",
            "__typename": "User",
            "createdAt": "2020-01-01T00:00:00Z",
        },
        "authorAssociation": "MEMBER",
        "changedFiles": 3,
        "additions": 45,
        "deletions": 12,
        "reviews": {
            "totalCount": 2,
            "nodes": [
                {
                    "submittedAt": "2025-06-15T12:00:00Z",
                    "author": {"login": "bob", "__typename": "User"},
                },
                {
                    "submittedAt": "2025-06-15T14:00:00Z",
                    "author": {"login": "carol", "__typename": "User"},
                },
            ],
        },
        "comments": {"totalCount": 5},
        "reviewThreads": {"totalCount": 3},
        "labels": {
            "nodes": [
                {"name": "bug"},
                {"name": "priority:high"},
            ]
        },
        "closingIssuesReferences": {"totalCount": 1},
        "reviewRequests": {
            "nodes": [
                {
                    "requestedReviewer": {
                        "login": "dave",
                        "__typename": "User",
                    }
                }
            ]
        },
    }


@pytest.fixture
def sample_pr_node_bot():
    """A PR node authored by a bot."""
    return {
        "number": 99,
        "title": "Bump dependency X from 1.0 to 2.0",
        "body": "Automated dependency update.",
        "state": "MERGED",
        "createdAt": "2025-07-01T08:00:00Z",
        "mergedAt": "2025-07-01T09:00:00Z",
        "closedAt": "2025-07-01T09:00:00Z",
        "merged": True,
        "author": {
            "login": "dependabot[bot]",
            "__typename": "Bot",
        },
        "authorAssociation": "NONE",
        "changedFiles": 1,
        "additions": 2,
        "deletions": 2,
        "reviews": {"totalCount": 0, "nodes": []},
        "comments": {"totalCount": 0},
        "reviewThreads": {"totalCount": 0},
        "labels": {"nodes": [{"name": "dependencies"}]},
        "closingIssuesReferences": {"totalCount": 0},
        "reviewRequests": {"nodes": []},
    }


@pytest.fixture
def sample_pr_node_minimal():
    """A PR node with many null/missing fields."""
    return {
        "number": 1,
        "title": None,
        "body": None,
        "state": "OPEN",
        "createdAt": "2024-01-01T00:00:00Z",
        "mergedAt": None,
        "closedAt": None,
        "merged": False,
        "author": None,
        "authorAssociation": None,
        "changedFiles": None,
        "additions": None,
        "deletions": None,
        "reviews": None,
        "comments": None,
        "reviewThreads": None,
        "labels": None,
        "closingIssuesReferences": None,
        "reviewRequests": None,
    }


@pytest.fixture
def sample_repo_snapshot_node():
    """A repository node with snapshot fields from GraphQL."""
    return {
        "stargazerCount": 15000,
        "openIssues": {"totalCount": 120},
        "closedIssues": {"totalCount": 800},
        "openPRs": {"totalCount": 25},
        "closedPRs": {"totalCount": 2500},
        "watchers": {"totalCount": 300},
        "forkCount": 1200,
        "pushedAt": "2025-06-20T18:00:00Z",
        "isArchived": False,
        "defaultBranchRef": {
            "name": "main",
            "target": {
                "contributingMd": {"oid": "abc123"},
                "securityMd": {"oid": "def456"},
                "codeOfConductMd": None,
            },
        },
    }
