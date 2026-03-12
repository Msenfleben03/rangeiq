# Tournament Research — Promotion Gate Evaluation

Walk-forward OOS evaluation across seasons [2021, 2022, 2023, 2024, 2025]

## Candidate Features (5 selected)

### Decision: **REJECT**

### Per-Season Results

| Season | Bets | Base ROI | Aug ROI | ROI Lift | Base Brier | Aug Brier | Brier Δ | Edge ρ | Monotonic |
|--------|------|----------|---------|----------|------------|-----------|---------|--------|----------|
| 2021 | 390 | 23.93% | 16.45% | -7.48% | 0.2302 | 0.2302 | +0.000000 | -0.2599 | Yes |
| 2022 | 216 | 40.42% | 21.07% | -19.35% | 0.2246 | 0.2843 | -0.059636 | -0.1019 | Yes |
| 2023 | 455 | 37.45% | 29.64% | -7.81% | 0.1974 | 0.1961 | +0.001220 | -0.0804 | Yes |
| 2024 | 513 | 31.16% | 22.72% | -8.45% | 0.2135 | 0.2326 | -0.019104 | -0.0507 | Yes |
| 2025 | 737 | 74.92% | 27.76% | -47.16% | 0.2082 | 0.2115 | -0.003311 | 0.0598 | Yes |

### Walk-Forward Learned Weights

- **2021**: no weights (first season)
**2022** (trained on [2021]):

| Feature | Weight |
|---------|--------|
| barthag_delta_10s | 3.399775 |
| home_loss_rate_10g | -0.126381 |
| late_loss_count_10g | -0.026447 |
| loss_margin_mean_10g | -0.000640 |
| weighted_quality_loss_10g | -0.152895 |

**2023** (trained on [2021, 2022]):

| Feature | Weight |
|---------|--------|
| barthag_delta_10s | 2.382587 |
| home_loss_rate_10g | 0.024359 |
| late_loss_count_10g | -0.006007 |
| loss_margin_mean_10g | 0.000124 |
| weighted_quality_loss_10g | -0.020170 |

**2024** (trained on [2021, 2022, 2023]):

| Feature | Weight |
|---------|--------|
| barthag_delta_10s | 1.971843 |
| home_loss_rate_10g | -0.064289 |
| late_loss_count_10g | -0.015295 |
| loss_margin_mean_10g | -0.001973 |
| weighted_quality_loss_10g | -0.169513 |

**2025** (trained on [2021, 2022, 2023, 2024]):

| Feature | Weight |
|---------|--------|
| barthag_delta_10s | 2.377215 |
| home_loss_rate_10g | -0.048045 |
| late_loss_count_10g | -0.010304 |
| loss_margin_mean_10g | -0.002299 |
| weighted_quality_loss_10g | -0.081824 |

### Primary Gates (ALL must pass)

- [FAIL] **pooled_roi_lift_positive**: -0.21526376094715047
- [FAIL] **roi_consistency_3_of_5**: 0/5
- [FAIL] **do_no_harm**: -0.47163777055352785
- [FAIL] **brier_improvement_pooled**: -0.016166330350203633
- [FAIL] **brier_consistency_3_of_5**: 1/5
- [PASS] **sample_size_200**: 216

### Structural Gates (at least 1 must pass)

- [FAIL] **edge_rho_positive**: -0.08662717518436426
- [PASS] **edge_monotonicity**: 5

### Hard Blocks

- [TRIGGERED] **rho_negative_reject**: -0.08662717518436426
- [clear] **covid_sensitivity**: stable

### Edge-Bucket ROI (Median Split)

| Season | Low Edge ROI | High Edge ROI | Monotonic? |
|--------|-------------|---------------|------------|
| 2021 | 4.80% | 28.09% | Yes |
| 2022 | 5.29% | 33.94% | Yes |
| 2023 | 8.70% | 47.42% | Yes |
| 2024 | 5.49% | 37.96% | Yes |
| 2025 | 7.76% | 44.35% | Yes |

---

## All 12 Features

### Decision: **REJECT**

### Per-Season Results

| Season | Bets | Base ROI | Aug ROI | ROI Lift | Base Brier | Aug Brier | Brier Δ | Edge ρ | Monotonic |
|--------|------|----------|---------|----------|------------|-----------|---------|--------|----------|
| 2021 | 390 | 23.93% | 16.45% | -7.48% | 0.2302 | 0.2302 | +0.000000 | -0.2599 | Yes |
| 2022 | 216 | 40.42% | 19.15% | -21.27% | 0.2246 | 0.3459 | -0.121294 | -0.1061 | Yes |
| 2023 | 455 | 37.45% | 37.43% | -0.03% | 0.1974 | 0.2313 | -0.033893 | 0.0118 | Yes |
| 2024 | 513 | 31.16% | 24.16% | -7.00% | 0.2135 | 0.2570 | -0.043521 | -0.0268 | Yes |
| 2025 | 737 | 74.92% | 29.80% | -45.12% | 0.2082 | 0.2310 | -0.022779 | 0.0759 | Yes |

### Walk-Forward Learned Weights

- **2021**: no weights (first season)
**2022** (trained on [2021]):

| Feature | Weight |
|---------|--------|
| adj_d_slope_10s | 0.059482 |
| adj_o_slope_10s | 0.314646 |
| bad_loss_weighted_10g | -0.548592 |
| barthag_delta_10s | 3.399775 |
| barthag_delta_20s | 2.168916 |
| home_loss_rate_10g | -0.126381 |
| late_loss_count_10g | -0.026447 |
| late_loss_count_5g | -0.053464 |
| loss_margin_mean_10g | -0.000640 |
| net_efficiency_slope_10s | 0.570108 |
| rank_change_20s | 0.004822 |
| weighted_quality_loss_10g | -0.152895 |

**2023** (trained on [2021, 2022]):

| Feature | Weight |
|---------|--------|
| adj_d_slope_10s | 0.003902 |
| adj_o_slope_10s | 0.216079 |
| bad_loss_weighted_10g | -0.104149 |
| barthag_delta_10s | 2.382587 |
| barthag_delta_20s | 1.958478 |
| home_loss_rate_10g | 0.024359 |
| late_loss_count_10g | -0.006007 |
| late_loss_count_5g | -0.032851 |
| loss_margin_mean_10g | 0.000124 |
| net_efficiency_slope_10s | 0.338093 |
| rank_change_20s | 0.004259 |
| weighted_quality_loss_10g | -0.020170 |

**2024** (trained on [2021, 2022, 2023]):

| Feature | Weight |
|---------|--------|
| adj_d_slope_10s | 0.041925 |
| adj_o_slope_10s | 0.164481 |
| bad_loss_weighted_10g | -0.236082 |
| barthag_delta_10s | 1.971843 |
| barthag_delta_20s | 1.310725 |
| home_loss_rate_10g | -0.064289 |
| late_loss_count_10g | -0.015295 |
| late_loss_count_5g | -0.033598 |
| loss_margin_mean_10g | -0.001973 |
| net_efficiency_slope_10s | 0.280956 |
| rank_change_20s | 0.002774 |
| weighted_quality_loss_10g | -0.169513 |

**2025** (trained on [2021, 2022, 2023, 2024]):

| Feature | Weight |
|---------|--------|
| adj_d_slope_10s | 0.071922 |
| adj_o_slope_10s | 0.174296 |
| bad_loss_weighted_10g | -0.207588 |
| barthag_delta_10s | 2.377215 |
| barthag_delta_20s | 1.289095 |
| home_loss_rate_10g | -0.048045 |
| late_loss_count_10g | -0.010304 |
| late_loss_count_5g | -0.019361 |
| loss_margin_mean_10g | -0.002299 |
| net_efficiency_slope_10s | 0.318415 |
| rank_change_20s | 0.002863 |
| weighted_quality_loss_10g | -0.081824 |

### Primary Gates (ALL must pass)

- [FAIL] **pooled_roi_lift_positive**: -0.19198356004397582
- [FAIL] **roi_consistency_3_of_5**: 0/5
- [FAIL] **do_no_harm**: -0.4511735719626946
- [FAIL] **brier_improvement_pooled**: -0.044297498567085807
- [FAIL] **brier_consistency_3_of_5**: 0/5
- [PASS] **sample_size_200**: 216

### Structural Gates (at least 1 must pass)

- [FAIL] **edge_rho_positive**: -0.06100418440759725
- [PASS] **edge_monotonicity**: 5

### Hard Blocks

- [TRIGGERED] **rho_negative_reject**: -0.06100418440759725
- [clear] **covid_sensitivity**: stable

### Edge-Bucket ROI (Median Split)

| Season | Low Edge ROI | High Edge ROI | Monotonic? |
|--------|-------------|---------------|------------|
| 2021 | 4.80% | 28.09% | Yes |
| 2022 | -8.43% | 36.44% | Yes |
| 2023 | 14.78% | 48.55% | Yes |
| 2024 | 4.24% | 37.73% | Yes |
| 2025 | 4.76% | 43.87% | Yes |

---

## Interpretation Notes

- **Walk-forward OOS**: Feature weights trained on prior seasons only
- **ROI lift**: Same bet set, Kelly re-sized with adjusted probabilities
- **Brier**: Computed on betted subset (not all games)
- **Edge ρ**: Spearman correlation of augmented edge with outcome
- **Monotonic**: High-edge bets have higher ROI than low-edge bets
- First test season (2021) uses zero weights (no prior training data)

### Limitations

- Bet SET is unchanged — only Kelly sizing adjusts with new probabilities
- True ROI lift requires full re-backtest with augmented model
- Feature weights are simple OLS residualization, not the full model
