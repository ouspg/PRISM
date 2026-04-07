# Statistical Methods

This document describes the analysis pipeline implemented by prism-analyze. The pipeline runs in a fixed order. Each stage's output feeds the next.

## Stage 1: Preprocessing

### Stationarity Testing

Two complementary tests run together:

- **Augmented Dickey-Fuller (ADF)**: Null hypothesis = unit root (non-stationary). Rejection suggests stationarity.
- **KPSS**: Null hypothesis = stationarity. Rejection suggests non-stationarity.

Decision matrix at α = 0.05:

| ADF rejects | KPSS rejects | Conclusion |
|---|---|---|
| Yes | No | Stationary |
| No | Yes | Non-stationary → difference |
| Yes | Yes | Ambiguous → difference (conservative) |
| No | No | Ambiguous → difference (conservative) |

### Auto-differencing

If non-stationary, the series is first-differenced. If still non-stationary, second-order differencing is applied. The differencing order is recorded in the results.

### Outlier Flagging

Outliers are detected using the IQR method (Q1 - 1.5·IQR, Q3 + 1.5·IQR). Outliers are **flagged but not removed** — the report lists them for researcher review.

### HAC Bandwidth

Newey-West maximum lags are computed as: `floor(4 · (T/100)^(2/9))` where T is the number of observations. This follows the Andrews (1991) automatic bandwidth selection rule.

## Stage 2: Structural Break Detection

### Bai-Perron via PELT

The PELT (Pruned Exact Linear Time) algorithm detects an unknown number of change points by minimizing a penalized cost function. This is **agnostic** — it knows nothing about the catalog.

- Cost model: L2 (least squares) by default
- Penalty: Controls sensitivity (higher = fewer breaks)
- Minimum segment length: 2 observations

### Catalog Overlap

After detection, each catalog inflection point is compared against detected breaks. A point is "in window" if a detected break falls within ±30 days (configurable). This comparison is reported explicitly — it does not gate subsequent analysis.

## Stage 3: Interrupted Time Series (ITS)

For each catalog inflection point in the data range, a segmented OLS regression is estimated:

```
y_t = β₀ + β₁·time + β₂·level_change + β₃·slope_change + ε_t
```

Where:
- `time` = integer index (0, 1, ..., T-1)
- `level_change` = 1 if t ≥ intervention, 0 otherwise
- `slope_change` = (t - T₀) · level_change

**β₂** captures the immediate level shift at the intervention.
**β₃** captures the change in trend slope after the intervention.

Standard errors are Newey-West HAC (heteroscedasticity and autocorrelation consistent) with Bartlett kernel.

### Counterfactual

The counterfactual projection estimates what the series would have been without the intervention: `ŷ = β₀ + β₁·time` extended into the post-period.

## Stage 4: Difference-in-Differences (DiD)

Optional. Requires panel data with treatment and control groups.

### Model

Two-way fixed effects panel regression via `PanelOLS`:

```
y_it = α_i + γ_t + δ·(treat_i × post_t) + ε_it
```

Where:
- `α_i` = entity fixed effects
- `γ_t` = time fixed effects
- `δ` = Average Treatment Effect on the Treated (ATT)

Standard errors are heteroscedasticity-robust.

### Parallel Pre-Trends

A mandatory check. In the pre-intervention period, treatment × time-period interactions are jointly tested for significance. If significant (p < 0.05), the parallel trends assumption is violated and the DiD result is flagged as unreliable.

## Stage 5: Multiple Testing Correction

Because multiple inflection points are tested against the same series, p-values are corrected using **Benjamini-Hochberg FDR** (False Discovery Rate) by default.

- Corrected p-values are the headline numbers in the report
- Raw p-values are preserved for transparency
- Alternative methods (e.g., Bonferroni) are configurable but not recommended for exploratory analysis

The per-inflection p-value used for correction is the minimum of the level-change and slope-change p-values from ITS.

## Stage 6: Effect Summary

A comparison matrix is produced:

| Inflection ID | Level Change | p-value | Slope Change | p-value | R² | In Break Window | p (corrected) | Significant |
|---|---|---|---|---|---|---|---|---|

This table is the primary scientific output — rows are inflection points, columns are test statistics. It can be exported as CSV, Markdown, or rendered as a heatmap.

## References

- Andrews, D.W.K. (1991). "Heteroskedasticity and Autocorrelation Consistent Covariance Matrix Estimation." *Econometrica*, 59(3), 817-858.
- Bai, J. & Perron, P. (1998). "Estimating and Testing Linear Models with Multiple Structural Changes." *Econometrica*, 66(1), 47-78.
- Benjamini, Y. & Hochberg, Y. (1995). "Controlling the False Discovery Rate." *JRSS-B*, 57(1), 289-300.
- Killick, R., Fearnhead, P. & Eckley, I.A. (2012). "Optimal Detection of Changepoints with a Linear Computational Cost." *JASA*, 107(500), 1590-1598.
