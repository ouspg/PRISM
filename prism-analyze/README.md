# prism-analyze

**Did AI actually change your metrics — and exactly when?**

prism-analyze is a statistical analysis engine for detecting whether AI inflection points caused structural breaks in any time-series data. It ships a curated, citable catalog of 20 AI events (Copilot GA, ChatGPT launch, GPT-4, etc.) and runs a rigorous pipeline — structural break detection, Interrupted Time Series regression, and optional Difference-in-Differences — against whatever data you bring.

Designed for researchers.

---

## What it does

1. **Detects structural breaks** using Bai-Perron (PELT algorithm) — agnostic, finds breaks the catalog might miss
2. **Tests each AI inflection point** with segmented OLS (ITS), reporting level change + slope change with Newey-West HAC standard errors
3. **Optionally runs DiD** if you have treatment/control groups
4. **Corrects for multiple testing** with Benjamini-Hochberg FDR across all catalog events
5. **Produces a comparison matrix** — rows are inflection points, columns are effect sizes and significance

---

## Interpreting results

The primary output is a **comparison matrix** — one row per catalog inflection point, one column per test statistic. Here is how to read it:

| Column | What it means |
|---|---|
| `level_change` | Immediate jump in the metric at the inflection date. Positive = metric went up. |
| `level_change_p` | p-value for the level change. Look at `p_corrected`, not this. |
| `slope_change` | Change in the trend *rate* after the inflection. Positive = accelerating growth. |
| `slope_change_p` | p-value for the slope change. Look at `p_corrected`, not this. |
| `p_corrected` | BH-corrected p-value across all events. **This is the headline number.** |
| `significant` | `True` if `p_corrected < fdr_alpha` (default 0.05). |
| `in_break_window` | Whether a data-driven break (PELT) was detected near this date. Strengthens the case when `True`. |
| `r_squared` | Variance explained by the full ITS model. |

**Key interpretive rules:**

- A **significant level change** means the metric shifted abruptly around that event. It does not prove causation — it proves timing alignment.
- A **significant slope change** means the *rate of change* shifted, which is often more meaningful than a one-time jump.
- **`significant=True` + `in_break_window=True`** is the strongest signal: the regression found an effect *and* the agnostic break detector independently found a break near the same date.
- **`significant=True` + `in_break_window=False`** means the regression found an effect but no agnostic break was nearby — interpret cautiously.
- A result is only as credible as the parallel trends test (DiD) or the counterfactual projection (ITS). The report renders both.

---

## Install

```bash
git clone https://github.com/ouspg/PRISM && cd PRISM/prism-analyze
uv sync
```

Or with pip:

```bash
pip install -e .
```

Requires Python ≥ 3.11.

---

## Where to put your script

After cloning, write your analysis scripts anywhere inside the repo and run them with `uv run`:

```
prism-analyze/
├── my_analysis.py     ← your script goes here (or in a subfolder)
├── prism_analyze/     ← the library (don't edit this)
├── examples/          ← ready-to-run demos
└── ...
```

```bash
# Run from the repo root
uv run python my_analysis.py

# Or run one of the included examples
uv run python examples/ai_jobs_demo.py
uv run python examples/nvidia_stock_demo.py
```

`uv run` ensures the virtual environment is active. If you prefer to activate it manually:

```bash
source .venv/bin/activate
python my_analysis.py
```

---

## Quick start

```python
import pandas as pd
from prism_analyze import analyze

# Any pd.Series with a DatetimeIndex
series = pd.read_csv("my_metric.csv", index_col="date", parse_dates=True).squeeze()

report = analyze(series)
```

That's it. The bundled catalog of AI events is loaded automatically.

### Print the report

```python
from prism_analyze.report.exporter import to_markdown
print(to_markdown(report))
```

### Save a plot

```python
from prism_analyze.report.visualizer import plot_series_with_breaks
fig = plot_series_with_breaks(report)
fig.savefig("breaks.png", dpi=150)
```

### Export results

```python
from prism_analyze.report.exporter import to_csv, to_json

# Both return strings — write them yourself
with open("results.csv", "w") as f:
    f.write(to_csv(report))   # the publishable comparison matrix

with open("results.json", "w") as f:
    f.write(to_json(report))  # full structured results
```

---

## Examples

### Monthly AI job postings

```python
import pandas as pd
from prism_analyze import Analyzer, AnalysisConfig, load_catalog

df = pd.read_csv("ai_jobs.csv")
df["date"] = pd.to_datetime(df["year"].astype(str) + "-" + df["month"].astype(str).str.zfill(2) + "-01")
series = df.groupby("date").size().sort_index()

catalog = load_catalog()
config = AnalysisConfig(
    break_penalty_auto=True,  # scales to data variance automatically
    break_min_size=6,         # at least 6-month segments for monthly data
    max_breaks=5,             # cap at 5 regime shifts over the period
    overlap_tolerance_days=60,
)

report = Analyzer(catalog, config).run(series)
```

### Reusing the analyzer across multiple metrics

```python
from prism_analyze import Analyzer, AnalysisConfig, load_catalog
from prism_analyze.report.exporter import to_markdown

analyzer = Analyzer(
    catalog=load_catalog(),
    config=AnalysisConfig(break_penalty_auto=True, break_min_size=6),
)

for metric_name, series in metrics.items():
    report = analyzer.run(series)
    print(f"\n--- {metric_name} ---")
    print(to_markdown(report))
```

### DiD with treatment and control groups

```python
import pandas as pd
from prism_analyze import Analyzer, AnalysisConfig, load_catalog

# Long-format DataFrame with 2-level MultiIndex (entity, time)
panel = df.set_index(["repo", "date"])
treatment_units = ["repo-a", "repo-b"]  # high AI adoption

report = Analyzer(load_catalog()).run(
    series=panel["commits"].groupby("date").mean(),  # aggregate for ITS
    panel=panel,
    treatment_units=treatment_units,
)
```

---

## Runnable examples

The `examples/` directory contains ready-to-run scripts you can use as starting points:

| Script | Dataset | What it demonstrates |
|---|---|---|
| `examples/ai_jobs_demo.py` | Monthly AI job postings | Monthly aggregated data, `break_min_size=6`, `max_breaks=5` |
| `examples/nvidia_stock_demo.py` | NVIDIA daily stock price | High-variance financial data, monthly resampling, `max_breaks=6` |

```bash
uv run python examples/ai_jobs_demo.py
uv run python examples/nvidia_stock_demo.py
```

Both scripts print the full Markdown report to stdout and save a break plot as a `.png` alongside the script.

---

## Tuning break detection

The penalty is auto-scaled by default (`break_penalty_auto=True`), which prevents the overfitting that occurs when a fixed penalty is applied to high-variance series. Most users should only need two knobs:

| Parameter | Effect | When to change |
|---|---|---|
| `break_min_size` | Minimum observations per segment | Set to 6 for monthly, 13 for weekly data |
| `max_breaks` | Hard cap on detected breaks | Set based on domain knowledge |
| `overlap_tolerance_days` | Catalog matching window | Widen for low-frequency data (monthly → 60) |

```python
# Weekly high-variance data (e.g. stock prices)
AnalysisConfig(break_penalty_auto=True, break_min_size=13, max_breaks=6)

# Monthly aggregated data
AnalysisConfig(break_penalty_auto=True, break_min_size=6, max_breaks=5, overlap_tolerance_days=60)

# Manual control if you know what you're doing
AnalysisConfig(break_penalty_auto=False, break_penalty=50.0)
```

---

## The inflection point catalog

The bundled catalog covers 20 AI events from 2021–2026 across four eras (Code Completion → Chat and Workspace → IDE and Open-Source Agent → Frontier Agentic), each with a tier rating, date, category, confidence level, and evidence URL. It is a standalone research artifact — a citable, versioned catalog of AI inflection points for OSS and software research.

```python
from datetime import date
from prism_analyze import load_catalog

catalog = load_catalog()

# Filter by category, date range, tier, or era
coding_events = catalog.filter_by_category("ai-coding-assistant")
recent = catalog.filter_by_date_range(date(2023, 1, 1), date(2024, 12, 31))
primary_only = catalog.filter_by_tier(1)          # tier 1 = primary ITS regressors
era1 = catalog.filter_by_era("Era 1 — Code Completion")
```

**Extend it** with your own events:

```python
# Add entries or override existing ones by id
catalog = load_catalog(user_overrides="my_events.yaml")
```

```yaml
# my_events.yaml
- id: "internal-copilot-rollout-2023-09"
  date: "2023-09-01"
  label: "Internal Copilot rollout"
  category: "ai-coding-assistant"
  scope: "org-specific"
  confidence: "high"
```

See [`docs/CATALOG_FORMAT.md`](docs/CATALOG_FORMAT.md) for the full schema and allowed categories.

---

## Data format

Input is a `pd.Series` with a `DatetimeIndex` and numeric values. If your data loads into pandas, it loads into this tool.

```python
# Minimum viable input
series = pd.Series(values, index=pd.to_datetime(dates))

# The validator handles: coercing string indices, sorting, dropping NaNs below
# the 5% threshold, inferring frequency, and warning on low observation counts.
```

**Minimum recommended:** 24 observations (two years of monthly data).

For DiD, see [`docs/PREPARING_YOUR_DATA.md`](docs/PREPARING_YOUR_DATA.md).

---

## Reference

### `AnalysisConfig`

| Parameter | Default | Description |
|---|---|---|
| `break_penalty_auto` | `True` | Auto-scale PELT penalty to data variance |
| `break_penalty` | `3.0` | Manual penalty (only used when `break_penalty_auto=False`) |
| `break_min_size` | `2` | Minimum segment length in observations |
| `max_breaks` | `None` | Hard cap on detected breaks |
| `overlap_tolerance_days` | `30` | Days tolerance for catalog–break matching |
| `stationarity_alpha` | `0.05` | ADF + KPSS significance level |
| `max_missing_pct` | `0.05` | Max fraction of NaN values before error |
| `hac_maxlags` | `None` | Newey-West lags (None = auto) |
| `fdr_alpha` | `0.05` | BH correction family-wise alpha |
| `correction_method` | `"fdr_bh"` | Multiple testing correction method |

### `AnalysisReport`

The return value of `.run()`. All intermediate results are accessible:

```python
report.preprocessing       # stationarity, differencing order, outliers
report.breaks              # detected break timestamps, catalog overlap
report.its_results         # list of ITSResult per inflection point
report.did_results         # list of DiDResult (if panel data provided)
report.correction          # BH-corrected p-values
report.summary_matrix      # pd.DataFrame — the publishable table
report.log                 # full pipeline log
```

---

## Statistical methods

See [`docs/METHODS.md`](docs/METHODS.md) for a full writeup covering:

- ADF + KPSS complementary stationarity testing and the 4-case decision matrix
- Birgé-Massart penalty criterion for PELT
- ITS design matrix specification and counterfactual projection
- Two-way fixed effects DiD and parallel pre-trends test
- Benjamini-Hochberg FDR correction rationale

---

## License

AGPL-3.0-or-later. See [LICENSE](LICENSE).
