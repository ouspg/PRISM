CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TYPE sync_status AS ENUM ('started', 'completed', 'failed');

-- Repos: mirrors repo_sample_list.csv structure
CREATE TABLE repos (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    owner               TEXT NOT NULL,
    repo                TEXT NOT NULL,
    slug                TEXT GENERATED ALWAYS AS (owner || '/' || repo) STORED,
    github_id           BIGINT,
    domain              TEXT NOT NULL,                -- agentic_coding_tools, devtools, ml_ai, security_critical, systems, web
    language            TEXT,
    stars               INTEGER,
    created_at          TIMESTAMPTZ,
    pushed_at           TIMESTAMPTZ,
    is_archived         BOOLEAN DEFAULT false,
    temporal_cohort     TEXT,                         -- pre_ai, ai_assisted_era, agentic_discourse_era, swe_agent_era, agentic_normalized
    star_tier           TEXT,                         -- tier1_anchor, tier2_midtier, tier3_longtail
    repo_age_days       INTEGER,
    selection_rationale TEXT,
    merged_pr_count     INTEGER,
    open_pr_count       INTEGER,
    contributor_count   INTEGER,
    enrichment_status   TEXT,
    selection_method    TEXT,                         -- purposive, stratified_random
    -- Cohort columns stored as JSONB for flexibility (18 inflection points + vibecoding)
    cohort_flags        JSONB DEFAULT '{}',
    metadata            JSONB DEFAULT '{}',           -- full repo API snapshot
    first_seen_at       TIMESTAMPTZ DEFAULT now(),
    last_synced_at      TIMESTAMPTZ,
    is_active           BOOLEAN DEFAULT true,
    UNIQUE (owner, repo)
);

-- Pull requests: mirrors the PR CSV schema from GraphQL collection
CREATE TABLE pull_requests (
    id                              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    repo_id                         UUID NOT NULL REFERENCES repos(id),
    pr_number                       INTEGER NOT NULL,
    github_id                       BIGINT,
    title                           TEXT,
    body                            TEXT,
    state                           TEXT,
    created_at                      TIMESTAMPTZ,
    merged_at                       TIMESTAMPTZ,
    closed_at                       TIMESTAMPTZ,
    was_merged                      BOOLEAN,
    author_login                    TEXT,
    author_type                     TEXT,             -- User, Bot, Mannequin, Organization
    author_association              TEXT,             -- MEMBER, CONTRIBUTOR, NONE, etc.
    author_account_created_at       TIMESTAMPTZ,
    changed_files                   INTEGER,
    additions                       INTEGER,
    deletions                       INTEGER,
    total_review_count              INTEGER,
    total_comment_count             INTEGER,
    total_review_comment_count      INTEGER,
    label_names                     TEXT[],
    has_closing_issue_reference     BOOLEAN,
    requested_reviewer_logins_and_types TEXT,
    first_review_submitted_at       TIMESTAMPTZ,
    first_review_author_login       TEXT,
    first_review_author_type        TEXT,
    all_reviewer_logins_and_types   TEXT,
    raw                             JSONB NOT NULL,
    collected_at                    TIMESTAMPTZ DEFAULT now(),
    UNIQUE (repo_id, pr_number)
);

-- Repo snapshots: point-in-time metadata from GraphQL collection
CREATE TABLE repo_snapshots (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    repo_id                 UUID NOT NULL REFERENCES repos(id),
    snapshot_collected_at   TIMESTAMPTZ NOT NULL,
    star_count              INTEGER,
    open_issue_count        INTEGER,
    closed_issue_count      INTEGER,
    open_pr_count           INTEGER,
    closed_pr_count         INTEGER,
    watcher_count           INTEGER,
    fork_count              INTEGER,
    pushed_at               TIMESTAMPTZ,
    is_archived             BOOLEAN,
    default_branch_name     TEXT,
    has_contributing_md     BOOLEAN,
    has_security_md         BOOLEAN,
    has_code_of_conduct_md  BOOLEAN,
    raw                     JSONB DEFAULT '{}'
);

CREATE TABLE sync_log (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    repo_id         UUID NOT NULL REFERENCES repos(id),
    collector       TEXT NOT NULL,
    status          sync_status NOT NULL,
    started_at      TIMESTAMPTZ NOT NULL,
    finished_at     TIMESTAMPTZ,
    items_collected INTEGER DEFAULT 0,
    error           TEXT,
    metadata        JSONB DEFAULT '{}'
);

-- Indexes
CREATE INDEX idx_repos_domain ON repos (domain);
CREATE INDEX idx_repos_temporal_cohort ON repos (temporal_cohort);
CREATE INDEX idx_repos_star_tier ON repos (star_tier);
CREATE INDEX idx_pr_repo_created ON pull_requests (repo_id, created_at);
CREATE INDEX idx_pr_author_type ON pull_requests (author_type);
CREATE INDEX idx_pr_merged_at ON pull_requests (merged_at) WHERE merged_at IS NOT NULL;
CREATE INDEX idx_pr_was_merged ON pull_requests (repo_id, was_merged);
CREATE INDEX idx_snapshots_repo ON repo_snapshots (repo_id, snapshot_collected_at);
CREATE INDEX idx_sync_log_repo ON sync_log (repo_id, started_at);
