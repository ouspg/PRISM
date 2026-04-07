#!/usr/bin/env python3
"""Import existing PR CSV files from example/github_prs/ into Postgres.

Usage:
    python scripts/import_csv_prs.py [--csv-dir example/github_prs]

Each CSV file is named {owner}__{repo}.csv. The script:
1. Looks up repo_id from the repos table (skips if not found)
2. Upserts all PR rows
3. Sets repos.last_synced_at to the max created_at per repo
   so incremental collection resumes from there
"""

import csv
import json
import sys
import time
from pathlib import Path

csv.field_size_limit(sys.maxsize)

import click
from sqlalchemy import text

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from prism.settings import Settings
from prism.db import get_engine, get_session


def _parse_bool(val: str) -> bool | None:
    if not val:
        return None
    return val.strip().lower() in ("true", "1", "yes")


def _parse_int(val: str) -> int | None:
    if not val:
        return None
    try:
        return int(val)
    except ValueError:
        return None


def _parse_labels(val: str) -> list[str]:
    """Parse comma-separated label string into a list."""
    if not val:
        return []
    return [part.strip() for part in val.split(",") if part.strip()]


def _parse_ts(val: str) -> str | None:
    """Return timestamp string or None."""
    if not val or val.strip() == "":
        return None
    return val.strip()


UPSERT_SQL = text("""
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
        :raw, now()
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
""")

UPDATE_LAST_SYNCED_SQL = text("""
    UPDATE repos SET last_synced_at = (
        SELECT max(created_at) FROM pull_requests WHERE repo_id = :repo_id
    ) WHERE id = :repo_id
""")


@click.command()
@click.option("--csv-dir", default="example/github_prs", help="Directory with PR CSV files")
def main(csv_dir: str):
    """Import PR CSVs into the pull_requests table."""
    csv_path = Path(csv_dir)
    if not csv_path.is_dir():
        click.echo(f"Error: {csv_dir} is not a directory", err=True)
        raise SystemExit(1)

    csv_files = sorted(csv_path.glob("*.csv"))
    click.echo(f"Found {len(csv_files)} CSV files in {csv_dir}")

    settings = Settings()
    engine = get_engine(settings.database_url)
    session = get_session(engine)

    # Pre-load repo_id lookup: (owner, repo) -> repo_id
    result = session.execute(text("SELECT id, owner, repo FROM repos"))
    repo_lookup: dict[tuple[str, str], str] = {}
    for row in result:
        repo_lookup[(row[1], row[2])] = str(row[0])
    click.echo(f"Loaded {len(repo_lookup)} repos from database")

    total_prs = 0
    imported_files = 0
    skipped_files = 0
    start = time.monotonic()

    for idx, csv_file in enumerate(csv_files, 1):
        # Parse owner/repo from filename: owner__repo.csv
        stem = csv_file.stem
        parts = stem.split("__", 1)
        if len(parts) != 2:
            click.echo(f"  SKIP {csv_file.name}: cannot parse owner__repo from filename")
            skipped_files += 1
            continue

        owner, repo = parts
        repo_id = repo_lookup.get((owner, repo))
        if not repo_id:
            click.echo(f"  SKIP {csv_file.name}: {owner}/{repo} not in repos table")
            skipped_files += 1
            continue

        # Read and upsert all PRs
        file_count = 0
        with open(csv_file, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Strip NUL bytes that PostgreSQL text columns reject
                row = {k: v.replace("\x00", "") if v else v for k, v in row.items()}

                pr_number = _parse_int(row.get("pr_number", ""))
                if pr_number is None:
                    continue

                # Build a minimal raw JSONB from CSV data
                raw = {k: v for k, v in row.items() if v}

                session.execute(UPSERT_SQL, {
                    "repo_id": repo_id,
                    "pr_number": pr_number,
                    "title": row.get("title") or None,
                    "body": row.get("body") or None,
                    "state": row.get("state") or None,
                    "created_at": _parse_ts(row.get("created_at", "")),
                    "merged_at": _parse_ts(row.get("merged_at", "")),
                    "closed_at": _parse_ts(row.get("closed_at", "")),
                    "was_merged": _parse_bool(row.get("was_merged", "")),
                    "author_login": row.get("author_login") or None,
                    "author_type": row.get("author_type") or None,
                    "author_association": row.get("author_association") or None,
                    "author_account_created_at": _parse_ts(
                        row.get("author_account_created_at", "")
                    ),
                    "changed_files": _parse_int(row.get("changed_files", "")),
                    "additions": _parse_int(row.get("additions", "")),
                    "deletions": _parse_int(row.get("deletions", "")),
                    "total_review_count": _parse_int(
                        row.get("total_review_count", "")
                    ),
                    "total_comment_count": _parse_int(
                        row.get("total_comment_count", "")
                    ),
                    "total_review_comment_count": _parse_int(
                        row.get("total_review_comment_count", "")
                    ),
                    "label_names": _parse_labels(row.get("label_names", "")),
                    "has_closing_issue_reference": _parse_bool(
                        row.get("has_closing_issue_reference", "")
                    ),
                    "requested_reviewer_logins_and_types": (
                        row.get("requested_reviewer_logins_and_types") or None
                    ),
                    "first_review_submitted_at": _parse_ts(
                        row.get("first_review_submitted_at", "")
                    ),
                    "first_review_author_login": (
                        row.get("first_review_author_login") or None
                    ),
                    "first_review_author_type": (
                        row.get("first_review_author_type") or None
                    ),
                    "all_reviewer_logins_and_types": (
                        row.get("all_reviewer_logins_and_types") or None
                    ),
                    "raw": json.dumps(raw),
                })
                file_count += 1

        # Commit per file and update last_synced_at
        session.execute(UPDATE_LAST_SYNCED_SQL, {"repo_id": repo_id})
        session.commit()

        total_prs += file_count
        imported_files += 1

        elapsed = time.monotonic() - start
        avg = elapsed / idx
        eta = avg * (len(csv_files) - idx)
        if idx % 50 == 0 or idx == len(csv_files):
            click.echo(
                f"  [{idx}/{len(csv_files)}] {owner}/{repo}: {file_count} PRs | "
                f"total: {total_prs:,} | elapsed: {elapsed:.0f}s | eta: {eta:.0f}s"
            )

    elapsed_total = time.monotonic() - start
    click.echo(
        f"\nDone: {total_prs:,} PRs from {imported_files} files "
        f"({skipped_files} skipped) in {elapsed_total:.1f}s"
    )
    session.close()


if __name__ == "__main__":
    main()
