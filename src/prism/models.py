"""SQLAlchemy 2.0 ORM models mirroring the PRISM database schema."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Repo(Base):
    """Tracked GitHub repository from repo_sample_list.csv."""

    __tablename__ = "repos"

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    owner: Mapped[str] = mapped_column(Text, nullable=False)
    repo: Mapped[str] = mapped_column(Text, nullable=False)
    # slug is GENERATED ALWAYS in Postgres; read-only here
    github_id: Mapped[int | None] = mapped_column(BigInteger)
    domain: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str | None] = mapped_column(Text)
    stars: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    pushed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    temporal_cohort: Mapped[str | None] = mapped_column(Text)
    star_tier: Mapped[str | None] = mapped_column(Text)
    repo_age_days: Mapped[int | None] = mapped_column(Integer)
    selection_rationale: Mapped[str | None] = mapped_column(Text)
    merged_pr_count: Mapped[int | None] = mapped_column(Integer)
    open_pr_count: Mapped[int | None] = mapped_column(Integer)
    contributor_count: Mapped[int | None] = mapped_column(Integer)
    enrichment_status: Mapped[str | None] = mapped_column(Text)
    selection_method: Mapped[str | None] = mapped_column(Text)
    cohort_flags: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, default=dict)
    first_seen_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    last_synced_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class PullRequest(Base):
    """GitHub pull request — matches PR CSV schema from GraphQL collection."""

    __tablename__ = "pull_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    repo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("repos.id"), nullable=False)
    pr_number: Mapped[int] = mapped_column(Integer, nullable=False)
    github_id: Mapped[int | None] = mapped_column(BigInteger)
    title: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    merged_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    was_merged: Mapped[bool | None] = mapped_column(Boolean)
    author_login: Mapped[str | None] = mapped_column(Text)
    author_type: Mapped[str | None] = mapped_column(Text)
    author_association: Mapped[str | None] = mapped_column(Text)
    author_account_created_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    changed_files: Mapped[int | None] = mapped_column(Integer)
    additions: Mapped[int | None] = mapped_column(Integer)
    deletions: Mapped[int | None] = mapped_column(Integer)
    total_review_count: Mapped[int | None] = mapped_column(Integer)
    total_comment_count: Mapped[int | None] = mapped_column(Integer)
    total_review_comment_count: Mapped[int | None] = mapped_column(Integer)
    label_names: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    has_closing_issue_reference: Mapped[bool | None] = mapped_column(Boolean)
    requested_reviewer_logins_and_types: Mapped[str | None] = mapped_column(Text)
    first_review_submitted_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    first_review_author_login: Mapped[str | None] = mapped_column(Text)
    first_review_author_type: Mapped[str | None] = mapped_column(Text)
    all_reviewer_logins_and_types: Mapped[str | None] = mapped_column(Text)
    raw: Mapped[dict] = mapped_column(JSONB, nullable=False)
    collected_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))


class RepoSnapshot(Base):
    """Point-in-time repository snapshot from GraphQL collection."""

    __tablename__ = "repo_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    repo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("repos.id"), nullable=False)
    snapshot_collected_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    star_count: Mapped[int | None] = mapped_column(Integer)
    open_issue_count: Mapped[int | None] = mapped_column(Integer)
    closed_issue_count: Mapped[int | None] = mapped_column(Integer)
    open_pr_count: Mapped[int | None] = mapped_column(Integer)
    closed_pr_count: Mapped[int | None] = mapped_column(Integer)
    watcher_count: Mapped[int | None] = mapped_column(Integer)
    fork_count: Mapped[int | None] = mapped_column(Integer)
    pushed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    is_archived: Mapped[bool | None] = mapped_column(Boolean)
    default_branch_name: Mapped[str | None] = mapped_column(Text)
    has_contributing_md: Mapped[bool | None] = mapped_column(Boolean)
    has_security_md: Mapped[bool | None] = mapped_column(Boolean)
    has_code_of_conduct_md: Mapped[bool | None] = mapped_column(Boolean)
    raw: Mapped[dict | None] = mapped_column(JSONB, default=dict)


class SyncLog(Base):
    """Log entry for a collection sync run."""

    __tablename__ = "sync_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    repo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("repos.id"), nullable=False)
    collector: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    items_collected: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, default=dict)
