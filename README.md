# OUSPG-PRISM

**Platform for Repository Intelligence and Software Metrics**

PRISM is a suite of tools for studying the impact of AI inflection points on measurable outcomes. The primary application is open-source software development — tracking ~1,380 GitHub repositories across six analytical domains and five temporal cohorts — but the analysis tools are data-agnostic and can be applied to any time-series data (financial markets, job postings, industry trends, etc.).

## Tools

| Tool | Description |
|------|-------------|
| [`prism-collect`](prism-collect/) | Data collection engine — mirrors PR metadata and repository snapshots from the GitHub GraphQL API into a local PostgreSQL database |
| [`prism-analyze`](prism-analyze/) | Statistical analysis engine — detects whether AI inflection points caused structural breaks in any time-series data (ITS, DiD, Bai-Perron) |
| `prism-dashboard` | _(coming soon)_ Visualization and reporting interface |

## Repository structure

```
PRISM/
├── prism-collect/   # Collection engine (CLI + PostgreSQL backend)
├── prism-analyze/   # Analysis engine (ITS / DiD / structural break detection)
└── prism-dashboard/ # Dashboard / reporting
```

## License

AGPL-3.0-or-later.

## Citation

```bibtex
@software{ouspg_prism,
  title  = {OUSPG-PRISM: Platform for Repository Intelligence and Software Metrics},
  author = {OUSPG},
  year   = {2026},
  url    = {https://github.com/ouspg/prism}
}
```
