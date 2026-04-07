"""Pydantic v2 schemas for validating GitHub API responses before DB insertion."""

from datetime import datetime

from pydantic import BaseModel


class PullRequestSchema(BaseModel):
    """Validated pull request — matches PR CSV schema from GraphQL collection."""

    repo_owner: str
    repo_name: str
    pr_number: int
    title: str | None = None
    body: str | None = None
    state: str | None = None
    created_at: datetime | None = None
    merged_at: datetime | None = None
    closed_at: datetime | None = None
    was_merged: bool | None = None
    author_login: str | None = None
    author_type: str | None = None
    author_association: str | None = None
    author_account_created_at: datetime | None = None
    changed_files: int | None = None
    additions: int | None = None
    deletions: int | None = None
    total_review_count: int | None = None
    total_comment_count: int | None = None
    total_review_comment_count: int | None = None
    label_names: list[str] = []
    has_closing_issue_reference: bool | None = None
    requested_reviewer_logins_and_types: str | None = None
    first_review_submitted_at: datetime | None = None
    first_review_author_login: str | None = None
    first_review_author_type: str | None = None
    all_reviewer_logins_and_types: str | None = None
    raw: dict


class RepoSnapshotSchema(BaseModel):
    """Validated repository snapshot from GraphQL collection."""

    owner: str
    repo: str
    snapshot_collected_at: datetime
    star_count: int | None = None
    open_issue_count: int | None = None
    closed_issue_count: int | None = None
    open_pr_count: int | None = None
    closed_pr_count: int | None = None
    watcher_count: int | None = None
    fork_count: int | None = None
    pushed_at: datetime | None = None
    is_archived: bool | None = None
    default_branch_name: str | None = None
    has_contributing_md: bool | None = None
    has_security_md: bool | None = None
    has_code_of_conduct_md: bool | None = None
    raw: dict = {}


class RepoSampleSchema(BaseModel):
    """Validated repo entry from repo_sample_list.csv."""

    owner: str
    repo: str
    domain: str
    language: str | None = None
    stars: int | None = None
    created_at: datetime | None = None
    pushed_at: datetime | None = None
    is_archived: bool = False
    temporal_cohort: str | None = None
    star_tier: str | None = None
    repo_age_days: int | None = None
    selection_rationale: str | None = None
    merged_pr_count: int | None = None
    open_pr_count: int | None = None
    contributor_count: int | None = None
    enrichment_status: str | None = None
    selection_method: str | None = None
