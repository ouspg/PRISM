#!/usr/bin/env python3
"""Read example/repo_sample_list.csv and write config/repos.yaml."""

import csv
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_CSV = PROJECT_ROOT / "example" / "repo_sample_list.csv"
OUTPUT_YAML = PROJECT_ROOT / "config" / "repos.yaml"

COHORT_COLS = [f"cohort_INFL_{i:02d}" for i in range(1, 19)] + ["cohort_vibecoding_era"]


def _yaml_str(val: str) -> str:
    """Quote a YAML string only when necessary."""
    if not val:
        return '""'
    # Quote if it contains characters that could confuse a YAML parser
    if any(c in val for c in ":#{}[]|>,\n\"'") or val.strip() != val:
        escaped = val.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return val


def main() -> None:
    csv.field_size_limit(sys.maxsize)

    with open(INPUT_CSV, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    print(f"Read {len(rows)} repos from {INPUT_CSV}")

    lines: list[str] = []

    # Header / collection config (preserved from current repos.yaml)
    lines.append("# OUSPG-PRISM repository sample list")
    lines.append(f"# Auto-generated from {INPUT_CSV.name} ({len(rows)} repos)")
    lines.append("#")
    lines.append("# Domains: " + ", ".join(sorted({r["domain"] for r in rows})))
    lines.append("# Temporal cohorts: " + ", ".join(sorted({r["temporal_cohort"] for r in rows})))
    lines.append("# Star tiers: " + ", ".join(sorted({r["star_tier"] for r in rows})))
    lines.append("# Selection methods: " + ", ".join(sorted({r["selection_method"] for r in rows})))
    lines.append("")
    lines.append("collection:")
    lines.append('  date_range:')
    lines.append('    start: "2019-01-01T00:00:00Z"')
    lines.append('    end: "2026-03-01T00:00:00Z"')
    lines.append('  graphql_endpoint: "https://api.github.com/graphql"')
    lines.append("  default_page_size: 100")
    lines.append("  min_page_size: 5")
    lines.append("  snapshot_batch_size: 10")
    lines.append("  max_retries: 10")
    lines.append("  rate_limit_low_threshold: 300")
    lines.append("  request_timeout_secs: 90")
    lines.append("")
    lines.append("repos:")

    for row in rows:
        lines.append(f"  - owner: {_yaml_str(row['owner'])}")
        lines.append(f"    repo: {_yaml_str(row['repo'])}")
        lines.append(f"    domain: {row['domain']}")
        lines.append(f"    language: {row.get('language') or 'Unknown'}")
        lines.append(f"    stars: {row.get('stars', 0)}")
        lines.append(f"    created_at: {_yaml_str(row.get('created_at', ''))}")
        lines.append(f"    pushed_at: {_yaml_str(row.get('pushed_at', ''))}")
        lines.append(f"    is_archived: {row.get('is_archived', 'false')}")
        lines.append(f"    temporal_cohort: {row.get('temporal_cohort', '')}")
        lines.append(f"    star_tier: {row.get('star_tier', '')}")
        lines.append(f"    repo_age_days: {row.get('repo_age_days', 0)}")
        lines.append(f"    merged_pr_count: {row.get('merged_pr_count', 0)}")
        lines.append(f"    open_pr_count: {row.get('open_pr_count', 0)}")
        lines.append(f"    contributor_count: {row.get('contributor_count', 0)}")
        lines.append(f"    enrichment_status: {row.get('enrichment_status', '')}")
        lines.append(f"    selection_method: {row.get('selection_method', '')}")

        # Cohort flags as a nested map
        cohort_vals = {col: row.get(col, "") for col in COHORT_COLS if row.get(col)}
        if cohort_vals:
            lines.append("    cohort_flags:")
            for k, v in cohort_vals.items():
                lines.append(f"      {k}: {v}")

        lines.append("")

    OUTPUT_YAML.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_YAML.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUTPUT_YAML} ({len(rows)} repos)")


if __name__ == "__main__":
    main()
