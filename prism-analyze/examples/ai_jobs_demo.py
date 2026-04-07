"""Demo: Run prism-analyze on monthly AI job postings (2020–2026).

https://www.kaggle.com/datasets/shree0910/ai-and-data-science-job-market-dataset-20202026
This is an intentionally relevant dataset — AI job market demand should
plausibly respond to major LLM/AI model launches. We test whether catalog
inflection points align with structural breaks in hiring volume.
"""

from pathlib import Path

import pandas as pd

from prism_analyze import Analyzer, AnalysisConfig, load_catalog
from prism_analyze.report.exporter import to_markdown
from prism_analyze.report.visualizer import plot_series_with_breaks

# --- Load and prepare data ---
csv_path = Path(__file__).parent / "AI Job Market Dataset.csv" # Download from kaggle first
df = pd.read_csv(csv_path)

# Aggregate to monthly job posting counts
df["date"] = pd.to_datetime(
    df["job_posting_year"].astype(str) + "-"
    + df["job_posting_month"].astype(str).str.zfill(2) + "-01"
)
series = df.groupby("date").size().sort_index()
series.name = "monthly_ai_job_postings"

print(f"Series: {series.name}")
print(f"Range:  {series.index[0].date()} → {series.index[-1].date()}")
print(f"Points: {len(series)}")
print()

# --- Run analysis ---
catalog = load_catalog()
config = AnalysisConfig(
    # Auto-penalty scales to this series' variance — no manual tuning needed
    break_penalty_auto=True,
    # Monthly data: require at least 6-month segments to qualify as a regime shift
    break_min_size=6,
    # Cap at 5 breaks — we don't expect more than ~5 paradigm shifts in 6 years
    max_breaks=5,
    # Monthly data: widen the catalog overlap window to ±60 days
    overlap_tolerance_days=60,
)
analyzer = Analyzer(catalog=catalog, config=config)
report = analyzer.run(series)

# --- Print results ---
print(to_markdown(report))

# --- Save plot ---
fig = plot_series_with_breaks(report)
out_path = Path(__file__).parent / "ai_jobs_breaks.png"
fig.savefig(out_path, dpi=150)
print(f"\nPlot saved to {out_path}")
