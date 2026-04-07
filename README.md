# OUSPG-PRISM

**Platform for Repository Intelligence and Software Metrics**

PRISM is a suite of tools for studying how AI-mediated contributions reshape open-source ecosystems. It tracks ~1,380 GitHub repositories across six analytical domains and five temporal cohorts spanning from pre-AI (before Copilot GA) to the present.

## Tools

| Tool | Description |
|------|-------------|
| [`prism-collect`](prism-collect/) | Data collection engine — mirrors PR metadata and repository snapshots from the GitHub GraphQL API into a local PostgreSQL database |
| `prism-analyze` | _(coming soon)_ Statistical analysis and feature engineering on collected data |
| `prism-dashboard` | _(coming soon)_ Visualization and reporting interface |

## Repository structure

```
PRISM/
├── prism-collect/   # Collection engine (CLI + PostgreSQL backend)
├── prism-analyze/   # Analysis pipeline
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
