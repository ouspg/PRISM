"""Demo: Run prism-analyze on NVIDIA monthly closing price (2019–2026).

https://www.kaggle.com/datasets/alitaqishah/nvidia-stock-data-19992026-the-ai-mega-stock
NVIDIA's stock is a direct proxy for market conviction in the AI build-out.
We test whether AI inflection points in the catalog align with structural
breaks in NVDA's price trend — a plausible hypothesis given the company's
role supplying GPU compute for every major LLM.

Data is resampled from daily to monthly (last close of each month) and
scoped to 2019–2026 so the catalog's AI events fall inside the analysis window.
"""

from pathlib import Path

import pandas as pd

from prism_analyze import Analyzer, AnalysisConfig, load_catalog
from prism_analyze.report.exporter import to_markdown
from prism_analyze.report.visualizer import plot_series_with_breaks

# --- Load and prepare data ---
csv_path = Path(__file__).parent / "nvidia_stock_data_1999_2026.csv" # Download from caggle first
df = pd.read_csv(csv_path, parse_dates=["date"], dayfirst=True)

# Resample daily closes to monthly, scoped to the AI era window
monthly = (
    df.set_index("date")["close"]
    .sort_index()
    .loc["2019-01-01":]
    .resample("MS")
    .last()
    .dropna()
)
monthly.name = "nvda_monthly_close_usd"

print(f"Series: {monthly.name}")
print(f"Range:  {monthly.index[0].date()} → {monthly.index[-1].date()}")
print(f"Points: {len(monthly)}")
print()

# --- Run analysis ---
catalog = load_catalog()
config = AnalysisConfig(
    # Auto-penalty scales to NVDA's high variance — essential here
    break_penalty_auto=True,
    # Monthly data: at least 6-month segments to qualify as a regime shift
    break_min_size=6,
    # NVDA moves fast; cap at 6 breaks over ~7 years
    max_breaks=6,
    # Monthly data: widen catalog overlap to ±60 days
    overlap_tolerance_days=60,
)

analyzer = Analyzer(catalog=catalog, config=config)
report = analyzer.run(monthly)

# --- Print results ---
print(to_markdown(report))

# --- Save plot ---
fig = plot_series_with_breaks(report)
out_path = Path(__file__).parent / "nvidia_breaks.png"
fig.savefig(out_path, dpi=150)
print(f"\nPlot saved to {out_path}")
