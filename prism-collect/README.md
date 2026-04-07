# prism-collect

Data collection engine for OUSPG-PRISM. Mirrors structured PR metadata and repository snapshots from the GitHub GraphQL API into a local PostgreSQL database, tracking ~1,380 repositories across six analytical domains and five temporal cohorts.

Raw API responses are stored verbatim as JSONB for archival fidelity, while extracted columns are indexed for fast analytical queries. The database can be queried directly via SQL, attached to DuckDB for columnar analytics, or accessed from Python through SQLAlchemy.

## Sample selection

The 1,383 tracked repositories were selected from an exhaustive API-driven population census of ~11,200 GitHub repos using a reproducible three-layer strategy:

1. **Stratified random sampling** (1,376 repos) -- from the eligible population, up to 80 repos drawn per (domain x star\_tier) cell. Eligibility requires at least 20 merged PRs, a push after 2020-01-01, enrichment\_status=ok, and not archived. The 6 domains and 3 star tiers produce 18 cells, ensuring balanced coverage across project types and popularity levels.

### Sample composition

| Domain | Tier 1 (anchor) | Tier 2 (midtier) | Tier 3 (longtail) | Total |
|--------|:---:|:---:|:---:|:---:|
| agentic\_coding\_tools | 29 | 76 | 80 | 185 |
| devtools | 80 | 80 | 80 | 240 |
| ml\_ai | 80 | 80 | 80 | 240 |
| security\_critical | 71 | 80 | 80 | 231 |
| systems | 80 | 80 | 80 | 240 |
| web | 80 | 80 | 80 | 240 |

Top languages: Python (420), TypeScript (283), Go (262), Rust (147), JavaScript (86), C (75), C++ (63), Java (35).

### Temporal cohorts

The sample spans five eras aligned with AI-tooling inflection points, enabling difference-in-differences analysis:

| Cohort | Repos | Share | Era boundary |
|--------|:---:|:---:|------|
| pre\_ai | 984 | 71.1% | Created before Copilot GA (2022-06-21) |
| ai\_assisted\_era | 181 | 13.1% | Copilot GA to Devin announcement (2024-03-12) |
| swe\_agent\_era | 175 | 12.7% | SWE-agent ecosystem to normalization (2026-01-15) |
| agentic\_normalized | 22 | 1.6% | After agentic normalization |
| agentic\_discourse\_era | 21 | 1.5% | Devin to SWE-agent ecosystem (2024-07-01) |

The pre\_ai cohort (71.1%) well exceeds the 40% minimum needed for the treated group in the difference-in-differences design. Each repo also carries 18 per-inflection-point cohort flags and a vibecoding-era marker stored as JSONB in `repos.cohort_flags`.

## Architecture

```
                    GitHub GraphQL API
                           |
                           v
┌──────────────────────────────────────────────────────┐
│  Host machine                                        │
│                                                      │
│  ┌────────────┐       ┌────────────┐                 │
│  │  Postgres   │<──────│   PRISM    │                 │
│  │  (JSONB +   │       │   CLI /    │                 │
│  │   indexed)  │       │   Worker   │                 │
│  └─────┬──────┘       └────────────┘                 │
│        │                                             │
│        │  postgres_scanner / psycopg2                 │
│        v                                             │
│  ┌───────────┐    ┌───────────┐    ┌───────────────┐ │
│  │  DuckDB   │    │  psql /   │    │  Python       │ │
│  │ (columnar │    │  pgAdmin  │    │ (SQLAlchemy / │ │
│  │  queries) │    │           │    │  pandas)      │ │
│  └───────────┘    └───────────┘    └───────────────┘ │
└──────────────────────────────────────────────────────┘
```

## Quickstart

```bash
git clone <repo-url> && cd PRISM/prism-collect
cp .env.example .env
# Edit .env -- set GITHUB_PAT to a GitHub PAT with repo + read:org scope

# Start Postgres
docker compose up db -d

# Install Python dependencies
uv sync

# Initialize database schema
prism db init

# Seed the repo tracking list
prism seed --csv-file example/repo_sample_list.csv

# (Optional) Import previously collected PR CSVs so collection resumes
# from where it left off rather than re-fetching everything
python scripts/import_csv_prs.py --csv-dir example/github_prs

# Start collecting
prism collect --domain all
```

## Database schema

PRISM uses four core tables:

| Table | Purpose |
|-------|---------|
| `repos` | Tracked repositories with domain, temporal cohort, star tier, selection metadata, and cohort flags |
| `pull_requests` | PR metadata (author, dates, review counts, labels, diffs) plus the full raw API response as JSONB |
| `repo_snapshots` | Point-in-time repository metrics (stars, forks, issues, PRs, community files) |
| `sync_log` | Audit trail for each collection run (status, item count, errors) |

The schema is defined in `sql/001_init.sql` and applied idempotently by `prism db init`.

### Key columns on `pull_requests`

`author_login`, `author_type` (User/Bot/Mannequin), `author_association`, `was_merged`, `created_at`, `merged_at`, `additions`, `deletions`, `changed_files`, `total_review_count`, `total_comment_count`, `label_names`, `has_closing_issue_reference`, `first_review_submitted_at`, plus the complete `raw` JSONB.

### Key columns on `repos`

`domain` (agentic_coding_tools, devtools, ml_ai, security_critical, systems, web), `temporal_cohort` (pre_ai, ai_assisted_era, agentic_discourse_era, swe_agent_era, agentic_normalized), `star_tier` (tier1_anchor, tier2_midtier, tier3_longtail), `selection_method` (purposive, stratified_random), `cohort_flags` (JSONB with per-inflection-point pre/post markers).

## CLI reference

| Command | Description |
|---------|-------------|
| `prism db init` | Initialize (or re-initialize) the database schema |
| `prism seed --csv-file path/to/repos.csv` | Load the repo tracking list into the `repos` table |
| `prism seed --yaml-file path/to/repos.yaml` | Load repos from YAML format |
| `prism collect --domain all` | Collect PR data and repo snapshots for all active repos |
| `prism collect --domain ml_ai` | Collect for a single domain |
| `prism collect --repo owner/name` | Collect for a single repository |
| `prism collect --collector pulls` | Run only the PR collector (skip snapshots) |
| `prism status` | Print sync status: repo counts by domain, total PRs, snapshots, recent activity |

### Importing pre-collected data

If you have PR data from a previous collection run (CSV files in `example/github_prs/`), import them before running `prism collect` so that incremental collection resumes from `last_synced_at` instead of re-fetching:

```bash
python scripts/import_csv_prs.py --csv-dir example/github_prs
```

Each CSV file is named `{owner}__{repo}.csv`. The script upserts all PR rows and sets `repos.last_synced_at` to the max `created_at` per repo.

## Querying the data

### Direct SQL (psql)

```bash
psql -h localhost -U prism -d prism
```

```sql
-- PR merge throughput by domain, monthly
SELECT r.domain, date_trunc('month', pr.merged_at) AS month, count(*)
FROM pull_requests pr JOIN repos r ON r.id = pr.repo_id
WHERE pr.was_merged = true
GROUP BY r.domain, month
ORDER BY r.domain, month;

-- Bot-authored PR fraction by temporal cohort
SELECT r.temporal_cohort,
       count(*) FILTER (WHERE pr.author_type = 'Bot') AS bot_prs,
       count(*) AS total_prs,
       round(100.0 * count(*) FILTER (WHERE pr.author_type = 'Bot') / count(*), 2) AS bot_pct
FROM pull_requests pr JOIN repos r ON r.id = pr.repo_id
GROUP BY r.temporal_cohort
ORDER BY r.temporal_cohort;

-- Repos with highest review-to-PR ratio
SELECT r.owner || '/' || r.repo AS slug,
       count(*) AS prs,
       round(avg(pr.total_review_count), 1) AS avg_reviews
FROM pull_requests pr JOIN repos r ON r.id = pr.repo_id
WHERE pr.was_merged = true
GROUP BY r.owner, r.repo HAVING count(*) > 50
ORDER BY avg_reviews DESC LIMIT 20;
```

Pre-built query examples are available in `sql/queries/`.

### DuckDB (columnar analytics)

DuckDB can attach directly to the running Postgres instance via the `postgres_scanner` extension, giving you columnar query performance without data export:

```python
import duckdb

con = duckdb.connect()
con.sql("INSTALL postgres; LOAD postgres;")
con.sql("""
    ATTACH 'dbname=prism user=prism password=changeme host=localhost port=5432'
    AS prism (TYPE POSTGRES);
""")

# Now query as if tables were local
df = con.sql("""
    SELECT r.domain, r.temporal_cohort,
           count(*) AS pr_count,
           avg(pr.additions + pr.deletions) AS avg_churn
    FROM prism.pull_requests pr
    JOIN prism.repos r ON r.id = pr.repo_id
    WHERE pr.was_merged = true
    GROUP BY r.domain, r.temporal_cohort
""").df()

print(df)
```

### Python (SQLAlchemy / pandas)

```python
from prism.settings import Settings
from prism.db import get_engine, get_session
from prism.models import PullRequest, Repo

settings = Settings()
engine = get_engine(settings.database_url)
session = get_session(engine)

# ORM query
bot_prs = (
    session.query(PullRequest)
    .filter(PullRequest.author_type == "Bot")
    .limit(10)
    .all()
)

# Or use pandas with raw SQL
import pandas as pd
df = pd.read_sql("SELECT * FROM pull_requests LIMIT 1000", engine)
```

## Configuration

| File | Purpose |
|------|---------|
| `.env` | Environment variables (see `.env.example`) |
| `example/repo_sample_list.csv` | Canonical list of 1,383 tracked repositories with selection metadata |
| `config/repos.yaml` | Alternative YAML repo list (generated from CSV via `scripts/csv_to_repos_yaml.py`) |
| `sql/001_init.sql` | Database DDL (tables, indexes, enums) |

### Environment variables

Settings are loaded via `pydantic-settings`. Variables prefixed `PRISM_` map to collection tuning parameters. Core variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `GITHUB_PAT` | (required) | GitHub personal access token |
| `POSTGRES_USER` | `prism` | Postgres username |
| `POSTGRES_PASSWORD` | `changeme` | Postgres password |
| `POSTGRES_DB` | `prism` | Database name |
| `POSTGRES_HOST` | `localhost` | Hostname (`db` inside Docker) |
| `PRISM_LOG_LEVEL` | `INFO` | Logging verbosity |
| `PRISM_DEFAULT_PAGE_SIZE` | `100` | GraphQL pagination page size |
| `PRISM_RATE_LIMIT_BUFFER` | `300` | Stop this many requests before GitHub's limit |
| `PRISM_MAX_RETRIES` | `10` | Max retries on transient failures |
| `PRISM_REQUEST_TIMEOUT` | `90` | HTTP request timeout (seconds) |

## Docker usage

```bash
# Postgres only (recommended for local development)
docker compose up db -d

# With pgAdmin for visual inspection
docker compose --profile debug up -d
# pgAdmin at http://localhost:5050 (admin@local.dev / admin)

# Run collection via the Docker worker
docker compose --profile worker run --rm worker prism collect --domain all
```

## Continuous collection

PRISM collects incrementally -- each run picks up where the last left off using `repos.last_synced_at`. To keep the database current, schedule periodic collection via cron or systemd.

### Cron (simplest)

```bash
# Edit your crontab
crontab -e

# Run collection every 6 hours, logging to a file
0 */6 * * * cd /path/to/PRISM/prism-collect && /path/to/.venv/bin/prism collect --domain all >> /var/log/prism-collect.log 2>&1
```

Or if running via Docker:

```bash
0 */6 * * * cd /path/to/PRISM/prism-collect && docker compose --profile worker run --rm worker prism collect --domain all >> /var/log/prism-collect.log 2>&1
```

### Systemd timer (recommended for servers)

Create two files:

```ini
# /etc/systemd/system/prism-collect.service
[Unit]
Description=PRISM data collection run
After=network-online.target postgresql.service

[Service]
Type=oneshot
User=prism
WorkingDirectory=/path/to/PRISM/prism-collect
ExecStart=/path/to/.venv/bin/prism collect --domain all
Environment=GITHUB_PAT=ghp_your_token
Environment=POSTGRES_HOST=localhost
StandardOutput=append:/var/log/prism-collect.log
StandardError=append:/var/log/prism-collect.log
```

```ini
# /etc/systemd/system/prism-collect.timer
[Unit]
Description=Run PRISM collection every 6 hours

[Timer]
OnCalendar=*-*-* 00/6:00:00
Persistent=true
RandomizedDelaySec=300

[Install]
WantedBy=timers.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now prism-collect.timer

# Check status
systemctl status prism-collect.timer
journalctl -u prism-collect.service --since "6 hours ago"
```

### Monitoring collection progress

```bash
# Quick status check
prism status

# Watch the sync log for recent failures
psql -h localhost -U prism -d prism -c "
  SELECT r.owner || '/' || r.repo AS repo, s.collector, s.status,
         s.items_collected, s.error, s.finished_at
  FROM sync_log s JOIN repos r ON r.id = s.repo_id
  WHERE s.started_at > now() - interval '24 hours'
  ORDER BY s.finished_at DESC LIMIT 20;
"
```

### Rate limits

PRISM uses a single GitHub PAT. With the default `PRISM_RATE_LIMIT_BUFFER=300`, it stops 300 requests before hitting the GitHub rate ceiling and sleeps until the reset window. A full collection run across all 1,383 repos typically takes 2--4 hours depending on PR volume. The `PRISM_POLITE_SLEEP_SECS=0.5` delay between repos avoids hammering the API.

## Development

```bash
uv add <package>        # Add a runtime dependency
uv add --dev <package>  # Add a dev dependency
ruff check src/ tests/  # Lint
pytest                  # Test
```

## License

AGPL-3.0-or-later. See [LICENSE](LICENSE).
