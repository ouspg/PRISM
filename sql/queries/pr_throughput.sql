-- PR merge throughput over time (monthly buckets), grouped by domain and temporal cohort
SELECT
    r.domain,
    r.temporal_cohort,
    r.slug,
    date_trunc('month', pr.merged_at) AS month,
    count(*) AS merged_count
FROM pull_requests pr
JOIN repos r ON r.id = pr.repo_id
WHERE pr.was_merged = true
GROUP BY r.domain, r.temporal_cohort, r.slug, month
ORDER BY r.domain, r.slug, month;
