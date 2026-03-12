# Consolidated Tournament Research Report

Generated from 5 loss seasons + 5 trajectory seasons

## Cross-Correlation Matrix

```text
                           late_loss_count_5g  late_loss_count_10g  loss_margin_mean_10g  weighted_quality_loss_10g  bad_loss_weighted_10g  home_loss_rate_10g  adj_o_slope_10s  adj_d_slope_10s  net_efficiency_slope_10s  barthag_delta_10s  barthag_delta_20s  rank_change_20s
late_loss_count_5g                      1.000                0.830                 0.272                        NaN                    NaN               0.656           -0.101           -0.124                    -0.226             -0.214             -0.301           -0.278
late_loss_count_10g                     0.830                1.000                 0.324                        NaN                    NaN               0.794           -0.066           -0.058                    -0.126             -0.108             -0.182           -0.163
loss_margin_mean_10g                    0.272                0.324                 1.000                        NaN                    NaN               0.119           -0.045           -0.058                    -0.106             -0.081             -0.123           -0.107
weighted_quality_loss_10g                 NaN                  NaN                   NaN                        NaN                    NaN                 NaN              NaN              NaN                       NaN                NaN                NaN              NaN
bad_loss_weighted_10g                     NaN                  NaN                   NaN                        NaN                    NaN                 NaN              NaN              NaN                       NaN                NaN                NaN              NaN
home_loss_rate_10g                      0.656                0.794                 0.119                        NaN                    NaN               1.000           -0.057           -0.028                    -0.086             -0.083             -0.137           -0.126
adj_o_slope_10s                        -0.101               -0.066                -0.045                        NaN                    NaN              -0.057            1.000           -0.595                     0.449              0.416              0.313            0.303
adj_d_slope_10s                        -0.124               -0.058                -0.058                        NaN                    NaN              -0.028           -0.595            1.000                     0.451              0.442              0.321            0.301
net_efficiency_slope_10s               -0.226               -0.126                -0.106                        NaN                    NaN              -0.086            0.449            0.451                     1.000              0.858              0.635            0.606
barthag_delta_10s                      -0.214               -0.108                -0.081                        NaN                    NaN              -0.083            0.416            0.442                     0.858              1.000              0.746            0.724
barthag_delta_20s                      -0.301               -0.182                -0.123                        NaN                    NaN              -0.137            0.313            0.321                     0.635              0.746              1.000            0.968
rank_change_20s                        -0.278               -0.163                -0.107                        NaN                    NaN              -0.126            0.303            0.301                     0.606              0.724              0.968            1.000
```

## High Correlations (|r| > 0.7)

- **late_loss_count_5g** vs **late_loss_count_10g**: r=0.830 — REDUNDANCY FLAG
- **late_loss_count_10g** vs **home_loss_rate_10g**: r=0.794 — REDUNDANCY FLAG
- **net_efficiency_slope_10s** vs **barthag_delta_10s**: r=0.858 — REDUNDANCY FLAG
- **barthag_delta_10s** vs **barthag_delta_20s**: r=0.746 — REDUNDANCY FLAG
- **barthag_delta_10s** vs **rank_change_20s**: r=0.724 — REDUNDANCY FLAG
- **barthag_delta_20s** vs **rank_change_20s**: r=0.968 — REDUNDANCY FLAG

## VIF Analysis

| Feature | VIF | Flag |
|---------|-----|------|
| late_loss_count_5g | nan |  |
| late_loss_count_10g | nan |  |
| loss_margin_mean_10g | nan |  |
| weighted_quality_loss_10g | nan |  |
| bad_loss_weighted_10g | nan |  |
| home_loss_rate_10g | nan |  |
| adj_o_slope_10s | nan |  |
| adj_d_slope_10s | nan |  |
| net_efficiency_slope_10s | nan |  |
| barthag_delta_10s | nan |  |
| barthag_delta_20s | nan |  |
| rank_change_20s | nan |  |

## Combined Feature Evaluation vs Baseline

### Season 2021 (n=875)

- Baseline CLV: 0.0000
- Baseline ROI: 62.42%

- CLV has zero variance (simulated odds) — correlations not meaningful

### Season 2022 (n=478)

- Baseline CLV: 0.0000
- Baseline ROI: 72.59%

- CLV has zero variance (simulated odds) — correlations not meaningful

### Season 2023 (n=1122)

- Baseline CLV: 0.0000
- Baseline ROI: 62.94%

- CLV has zero variance (simulated odds) — correlations not meaningful

### Season 2024 (n=1130)

- Baseline CLV: 0.0011
- Baseline ROI: 56.97%

| Feature | r(CLV) | p-value | Sig? |
|---------|--------|---------|------|
| late_loss_count_5g | -0.0182 | 0.6016 |  |
| late_loss_count_10g | -0.0444 | 0.2816 |  |
| loss_margin_mean_10g | -0.0332 | 0.4203 |  |
| home_loss_rate_10g | -0.0055 | 0.8948 |  |
| adj_o_slope_10s | 0.0081 | 0.7893 |  |
| adj_d_slope_10s | 0.0049 | 0.8716 |  |
| net_efficiency_slope_10s | 0.0132 | 0.6621 |  |
| barthag_delta_10s | 0.0130 | 0.6751 |  |
| barthag_delta_20s | 0.0489 | 0.1488 |  |
| rank_change_20s | 0.0416 | 0.2194 |  |

### Season 2025 (n=1564)

- Baseline CLV: 0.0013
- Baseline ROI: 102.96%

| Feature | r(CLV) | p-value | Sig? |
|---------|--------|---------|------|
| late_loss_count_5g | -0.0611 | 0.0326 | **YES** |
| late_loss_count_10g | -0.1178 | 0.0005 | **YES** |
| loss_margin_mean_10g | -0.0569 | 0.0931 |  |
| home_loss_rate_10g | -0.1089 | 0.0013 | **YES** |
| adj_o_slope_10s | 0.0131 | 0.6201 |  |
| adj_d_slope_10s | -0.0265 | 0.3146 |  |
| net_efficiency_slope_10s | -0.0148 | 0.5737 |  |
| barthag_delta_10s | 0.0618 | 0.0226 | **YES** |
| barthag_delta_20s | 0.0259 | 0.3763 |  |
| rank_change_20s | 0.0270 | 0.3578 |  |

## Promotion Readiness Checklist

- [ ] Marginal CLV lift >= +0.5% (pooled)
- [ ] OOS ROI delta >= +2% (pooled)
- [ ] Feature importance stable in >=4/5 seasons
- [ ] No feature correlated >0.7 with existing model features
- [ ] VIF < 5 for all selected features
- [ ] In-sample ROI <= 2x OOS ROI
- [ ] >=200 bets per test season
- [ ] User review completed
