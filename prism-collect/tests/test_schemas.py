"""Tests for Pydantic validation schemas."""

import pytest
from pydantic import ValidationError

from prism.schemas import PullRequestSchema, RepoSampleSchema, RepoSnapshotSchema


class TestPullRequestSchema:
    def test_valid_pr(self):
        pr = PullRequestSchema(
            repo_owner="acme",
            repo_name="widget",
            pr_number=42,
            state="MERGED",
            was_merged=True,
            author_login="alice",
            raw={"number": 42},
        )
        assert pr.pr_number == 42
        assert pr.was_merged is True

    def test_missing_required_field(self):
        with pytest.raises(ValidationError):
            PullRequestSchema(
                repo_owner="acme",
                # missing repo_name
                pr_number=1,
                raw={},
            )

    def test_optional_fields_default_none(self):
        pr = PullRequestSchema(
            repo_owner="o", repo_name="r", pr_number=1, raw={}
        )
        assert pr.title is None
        assert pr.merged_at is None
        assert pr.label_names == []


class TestRepoSnapshotSchema:
    def test_valid_snapshot(self):
        snap = RepoSnapshotSchema(
            owner="acme",
            repo="widget",
            snapshot_collected_at="2025-06-20T18:00:00Z",
            star_count=15000,
            fork_count=1200,
        )
        assert snap.star_count == 15000

    def test_missing_collected_at(self):
        with pytest.raises(ValidationError):
            RepoSnapshotSchema(owner="o", repo="r")


class TestRepoSampleSchema:
    def test_valid_sample(self):
        repo = RepoSampleSchema(
            owner="torvalds",
            repo="linux",
            domain="systems",
            language="C",
            stars=195000,
            temporal_cohort="pre_ai",
            star_tier="tier1_anchor",
            selection_method="purposive",
        )
        assert repo.owner == "torvalds"
        assert repo.domain == "systems"

    def test_minimal_sample(self):
        repo = RepoSampleSchema(owner="o", repo="r", domain="web")
        assert repo.language is None
        assert repo.is_archived is False
