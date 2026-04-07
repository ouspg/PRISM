# Preparing Your Data

prism-analyze accepts standard pandas data structures. If your data loads into pandas, it loads into this tool.

## Time Series (ITS analysis)

Provide a `pd.Series` with:

- **DatetimeIndex** — if your index is strings or integers, the validator will attempt `pd.to_datetime()` conversion
- **Numeric values** — float or int, no object dtype
- **One metric per series** — for multiple metrics, call `analyze()` once per metric
- **Sorted chronologically** — the validator will sort if needed, but sorted input is preferred

### Minimum requirements

- At least **24 observations** (two years of monthly data). The tool warns but does not block below this threshold.
- No more than **5% missing values** (configurable via `max_missing_pct`). NaN rows below this threshold are dropped and logged; above it, an error is raised.

### Example

```python
import pandas as pd

# Monthly commit counts
series = pd.Series(
    [120, 135, 128, ...],
    index=pd.date_range("2020-01-01", periods=48, freq="MS"),
    name="monthly_commits",
)
```

## Panel Data (DiD analysis)

For Difference-in-Differences, provide a `pd.DataFrame` with:

- **2-level MultiIndex** `(entity, time)` — entities are your units (repos, teams, projects), time is a DatetimeIndex
- **Numeric columns** — the first column is used as the outcome variable by default (override with `outcome_col`)
- **treatment_units** — a list of entity identifiers for the treatment group

### Example

```python
import pandas as pd
import numpy as np

entities = ["repo-a", "repo-b", "repo-c", "repo-d"]
dates = pd.date_range("2021-01-01", periods=36, freq="MS")

index = pd.MultiIndex.from_product([entities, dates], names=["entity", "time"])
data = pd.DataFrame({"commits": np.random.poisson(50, len(index))}, index=index)

treatment_units = ["repo-a", "repo-b"]  # high AI adoption
```

## Frequency

The tool infers frequency via `pd.infer_freq()`. Supported granularities include daily, weekly, and monthly. Irregular time series are accepted but may affect frequency-dependent calculations.

## What the validator checks

1. Index is or can become a DatetimeIndex
2. Values are numeric
3. Series is sorted by time
4. NaN fraction is within threshold
5. Minimum observation count
6. For panels: MultiIndex has exactly 2 levels, treatment units exist in the data
