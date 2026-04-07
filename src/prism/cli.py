"""Click CLI entry point for PRISM."""

from __future__ import annotations

import csv
import logging
import sys
import time
from pathlib import Path

import click
import yaml

log = logging.getLogger("prism")


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="[%(asctime)s] %(levelname)-7s %(name)s — %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )


@click.group()
def cli():
    """OUSPG-PRISM: Platform for Repository Intelligence and Software Metrics."""
    pass


# ──────────────────────────────────────────────────────────────────────
# collect
# ──────────────────────────────────────────────────────────────────────


@cli.command()
@click.option(
    "--domain",
    type=click.Choice(
        ["all", "agentic_coding_tools", "devtools", "ml_ai",
         "security_critical", "systems", "web"],
    ),
    default="all",
    help="Filter repos by domain.",
)
@click.option("--repo", "single_repo", default=None, help="Single repo slug (owner/name)")
@click.option(
    "--collector",
    type=click.Choice(["pulls", "repo_meta", "all"]),
    default="all",
)
@click.option("--date-start", default=None, help="Override collection window start (ISO)")
@click.option("--date-end", default=None, help="Override collection window end (ISO)")
def collect(domain, single_repo, collector, date_start, date_end):
    """Run data collection from GitHub GraphQL API."""
    from prism.settings import Settings
    from prism.db import get_engine, get_session
    from prism.github_client import GitHubClient
    from prism.models import Repo

    settings = Settings()
    _setup_logging(settings.log_level)

    engine = get_engine(settings.database_url)
    session = get_session(engine)

    # Build list of repos to collect
    if single_repo:
        parts = single_repo.split("/", 1)
        if len(parts) != 2:
            click.echo(f"Error: repo must be owner/name, got '{single_repo}'", err=True)
            raise SystemExit(1)
        repos = session.query(Repo).filter(
            Repo.owner == parts[0], Repo.repo == parts[1], Repo.is_active.is_(True)
        ).all()
        if not repos:
            click.echo(f"Repo '{single_repo}' not found in database. Run 'prism seed' first.")
            raise SystemExit(1)
    elif domain == "all":
        repos = session.query(Repo).filter(Repo.is_active.is_(True)).all()
    else:
        repos = session.query(Repo).filter(
            Repo.domain == domain, Repo.is_active.is_(True)
        ).all()

    if not repos:
        click.echo("No repos found. Run 'prism seed' first.")
        raise SystemExit(1)

    log.info("Collecting %d repos (domain=%s, collector=%s)", len(repos), domain, collector)

    with GitHubClient(
        settings.github_pat,
        rate_limit_buffer=settings.rate_limit_buffer,
        rate_limit_sleep_secs=settings.rate_limit_sleep_secs,
        polite_sleep_secs=settings.polite_sleep_secs,
        max_retries=settings.max_retries,
        retry_backoff_base=settings.retry_backoff_base,
        request_timeout=settings.request_timeout,
        default_page_size=settings.default_page_size,
        min_page_size=settings.min_page_size,
    ) as client:
        # Probe rate limit
        try:
            rl = client.probe_rate_limit()
            log.info("PAT valid. Rate-limit: remaining=%s resetAt=%s",
                     rl.get("remaining", "?"), rl.get("resetAt", "?"))
        except Exception as exc:
            log.warning("PAT probe failed: %s — proceeding anyway", exc)

        # Run collectors
        total_collected = 0
        failed_repos: list[str] = []
        collection_start = time.monotonic()

        for idx, repo in enumerate(repos, 1):
            repo_key = f"{repo.owner}/{repo.repo}"

            if collector in ("pulls", "all"):
                from prism.collectors.pulls import PullsCollector

                pulls = PullsCollector(client, session)
                try:
                    count = pulls.collect(repo, date_start=date_start, date_end=date_end)
                    total_collected += count
                except Exception as exc:
                    log.error("[%s] PR collection failed: %s", repo_key, exc)
                    failed_repos.append(repo_key)

            if collector in ("repo_meta",) and collector != "all":
                # Standalone snapshot (not already done via combined query in pulls)
                from prism.collectors.repo_meta import RepoMetaCollector

                meta = RepoMetaCollector(client, session)
                try:
                    meta.collect(repo)
                except Exception as exc:
                    log.error("[%s] Snapshot collection failed: %s", repo_key, exc)
                    failed_repos.append(repo_key)

            elapsed = time.monotonic() - collection_start
            avg = elapsed / idx
            eta = avg * (len(repos) - idx)
            log.info(
                "PROGRESS [%d/%d] %s | total PRs: %d | elapsed: %.1fm | eta: %.1fm",
                idx, len(repos), repo_key, total_collected, elapsed / 60, eta / 60,
            )
            time.sleep(client.polite_sleep_secs)

    elapsed_total = time.monotonic() - collection_start
    click.echo(f"\nCollection complete: {total_collected} PRs from {len(repos)} repos "
               f"in {elapsed_total / 60:.1f}m")
    if failed_repos:
        click.echo(f"Failed repos ({len(failed_repos)}):")
        for r in failed_repos:
            click.echo(f"  - {r}")

    session.close()


# ──────────────────────────────────────────────────────────────────────
# seed
# ──────────────────────────────────────────────────────────────────────


@cli.command()
@click.option("--csv-file", "csv_path", type=click.Path(exists=True),
              help="Path to repo_sample_list.csv")
@click.option("--yaml-file", "yaml_path", type=click.Path(exists=True),
              help="Path to repos.yaml")
def seed(csv_path, yaml_path):
    """Load repos into the repos table from CSV or YAML."""
    from prism.settings import Settings
    from prism.db import get_engine, get_session

    settings = Settings()
    _setup_logging(settings.log_level)

    engine = get_engine(settings.database_url)
    session = get_session(engine)

    if csv_path:
        count = _seed_from_csv(session, Path(csv_path))
        click.echo(f"Seeded {count} repos from {csv_path}")
    elif yaml_path:
        count = _seed_from_yaml(session, Path(yaml_path))
        click.echo(f"Seeded {count} repos from {yaml_path}")
    else:
        # Default: look for config/repos.yaml
        default_yaml = Path("config/repos.yaml")
        if default_yaml.exists():
            count = _seed_from_yaml(session, default_yaml)
            click.echo(f"Seeded {count} repos from {default_yaml}")
        else:
            click.echo("No input specified. Use --csv-file or --yaml-file.", err=True)
            raise SystemExit(1)

    session.close()


def _seed_from_csv(session, csv_path: Path) -> int:
    """Load repos from repo_sample_list.csv format."""
    from sqlalchemy import text

    # Cohort columns to extract into JSONB
    cohort_columns = [f"cohort_INFL_{i:02d}" for i in range(1, 19)] + ["cohort_vibecoding_era"]

    count = 0
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Build cohort_flags JSONB from cohort columns
            cohort_flags = {}
            for col in cohort_columns:
                if col in row:
                    cohort_flags[col] = row[col]

            stars = row.get("stars")
            repo_age = row.get("repo_age_days")
            merged_prs = row.get("merged_pr_count")
            open_prs = row.get("open_pr_count")
            contributors = row.get("contributor_count")

            session.execute(
                text("""
                    INSERT INTO repos (
                        owner, repo, domain, language, stars, created_at, pushed_at,
                        is_archived, temporal_cohort, star_tier, repo_age_days,
                        selection_rationale, merged_pr_count, open_pr_count,
                        contributor_count, enrichment_status, selection_method,
                        cohort_flags
                    ) VALUES (
                        :owner, :repo, :domain, :language, :stars, :created_at, :pushed_at,
                        :is_archived, :temporal_cohort, :star_tier, :repo_age_days,
                        :selection_rationale, :merged_pr_count, :open_pr_count,
                        :contributor_count, :enrichment_status, :selection_method,
                        CAST(:cohort_flags AS jsonb)
                    )
                    ON CONFLICT (owner, repo) DO UPDATE SET
                        domain = EXCLUDED.domain,
                        language = EXCLUDED.language,
                        stars = EXCLUDED.stars,
                        temporal_cohort = EXCLUDED.temporal_cohort,
                        star_tier = EXCLUDED.star_tier,
                        repo_age_days = EXCLUDED.repo_age_days,
                        selection_rationale = EXCLUDED.selection_rationale,
                        merged_pr_count = EXCLUDED.merged_pr_count,
                        open_pr_count = EXCLUDED.open_pr_count,
                        contributor_count = EXCLUDED.contributor_count,
                        enrichment_status = EXCLUDED.enrichment_status,
                        selection_method = EXCLUDED.selection_method,
                        cohort_flags = EXCLUDED.cohort_flags
                """),
                {
                    "owner": row["owner"],
                    "repo": row["repo"],
                    "domain": row["domain"],
                    "language": row.get("language") or None,
                    "stars": int(stars) if stars else None,
                    "created_at": row.get("created_at") or None,
                    "pushed_at": row.get("pushed_at") or None,
                    "is_archived": row.get("is_archived", "").lower() == "true",
                    "temporal_cohort": row.get("temporal_cohort") or None,
                    "star_tier": row.get("star_tier") or None,
                    "repo_age_days": int(repo_age) if repo_age else None,
                    "selection_rationale": row.get("selection_rationale") or None,
                    "merged_pr_count": int(merged_prs) if merged_prs else None,
                    "open_pr_count": int(open_prs) if open_prs else None,
                    "contributor_count": int(contributors) if contributors else None,
                    "enrichment_status": row.get("enrichment_status") or None,
                    "selection_method": row.get("selection_method") or None,
                    "cohort_flags": __import__("json").dumps(cohort_flags),
                },
            )
            count += 1

    session.commit()
    return count


def _seed_from_yaml(session, yaml_path: Path) -> int:
    """Load repos from repos.yaml format."""
    from sqlalchemy import text

    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    repos = data.get("repos", [])
    count = 0

    for entry in repos:
        session.execute(
            text("""
                INSERT INTO repos (owner, repo, domain, language, stars,
                                   temporal_cohort, star_tier, selection_method)
                VALUES (:owner, :repo, :domain, :language, :stars,
                        :temporal_cohort, :star_tier, :selection_method)
                ON CONFLICT (owner, repo) DO UPDATE SET
                    domain = EXCLUDED.domain,
                    language = EXCLUDED.language,
                    stars = EXCLUDED.stars,
                    temporal_cohort = EXCLUDED.temporal_cohort,
                    star_tier = EXCLUDED.star_tier,
                    selection_method = EXCLUDED.selection_method
            """),
            {
                "owner": entry["owner"],
                "repo": entry["repo"],
                "domain": entry.get("domain", "unknown"),
                "language": entry.get("language"),
                "stars": entry.get("stars"),
                "temporal_cohort": entry.get("temporal_cohort"),
                "star_tier": entry.get("star_tier"),
                "selection_method": entry.get("selection_method"),
            },
        )
        count += 1

    session.commit()
    return count


# ──────────────────────────────────────────────────────────────────────
# status
# ──────────────────────────────────────────────────────────────────────


@cli.command()
def status():
    """Print sync status summary."""
    from sqlalchemy import text

    from prism.settings import Settings
    from prism.db import get_engine, get_session

    settings = Settings()
    _setup_logging(settings.log_level)
    engine = get_engine(settings.database_url)
    session = get_session(engine)

    # Repo counts by domain
    result = session.execute(text("""
        SELECT domain, count(*) as cnt,
               count(*) FILTER (WHERE last_synced_at IS NOT NULL) as synced
        FROM repos WHERE is_active = true
        GROUP BY domain ORDER BY domain
    """))
    rows = result.fetchall()

    click.echo("\n  Domain                     Total   Synced")
    click.echo("  " + "-" * 45)
    total_repos = 0
    total_synced = 0
    for row in rows:
        click.echo(f"  {row[0]:<28s} {row[1]:>5d}   {row[2]:>5d}")
        total_repos += row[1]
        total_synced += row[2]
    click.echo("  " + "-" * 45)
    click.echo(f"  {'TOTAL':<28s} {total_repos:>5d}   {total_synced:>5d}")

    # PR count
    result = session.execute(text("SELECT count(*) FROM pull_requests"))
    pr_count = result.scalar()
    click.echo(f"\n  Total PRs in database: {pr_count:,}")

    # Snapshot count
    result = session.execute(text("SELECT count(*) FROM repo_snapshots"))
    snap_count = result.scalar()
    click.echo(f"  Total snapshots: {snap_count:,}")

    # Recent sync activity
    result = session.execute(text("""
        SELECT s.collector, s.status, count(*), max(s.finished_at)
        FROM sync_log s
        WHERE s.started_at > now() - interval '24 hours'
        GROUP BY s.collector, s.status
        ORDER BY s.collector, s.status
    """))
    recent = result.fetchall()
    if recent:
        click.echo("\n  Last 24h sync activity:")
        for row in recent:
            click.echo(f"    {row[0]}/{row[1]}: {row[2]} runs (last: {row[3]})")

    click.echo()
    session.close()


# ──────────────────────────────────────────────────────────────────────
# db
# ──────────────────────────────────────────────────────────────────────


@cli.group()
def db():
    """Database management commands."""
    pass


@db.command("init")
def db_init():
    """Initialize database schema from sql/001_init.sql."""
    from prism.settings import Settings
    from prism.db import get_engine, init_db

    settings = Settings()
    _setup_logging(settings.log_level)
    engine = get_engine(settings.database_url)
    init_db(engine, settings.sql_init_path)
    click.echo("Database schema initialized.")
