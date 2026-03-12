# Late-Season Loss Features — Research Report

## Overview

Seasons analyzed: [2021, 2022, 2023, 2024, 2025]
Features computed: 6

## Feature Distributions

| Feature | Mean | Std | Min | Max |
|---------|------|-----|-----|-----|
| late_loss_count_5g | 2.4707 | 1.3650 | 0.0000 | 5.0000 |
| late_loss_count_10g | 4.9516 | 2.2769 | 0.0000 | 10.0000 |
| loss_margin_mean_10g | 9.8383 | 5.1273 | 0.0000 | 40.1250 |
| weighted_quality_loss_10g | 0.2732 | 0.1407 | 0.0000 | 0.8645 |
| bad_loss_weighted_10g | 0.2055 | 0.1414 | 0.0000 | 0.7572 |
| home_loss_rate_10g | 0.3672 | 0.2769 | 0.0000 | 1.0000 |

## Internal Correlation Matrix

| | late_loss_count_5g | late_loss_count_10g | loss_margin_mean_10g | weighted_quality_loss_10g | bad_loss_weighted_10g | home_loss_rate_10g |
|---|---|---|---|---|---|---|
| late_loss_count_5g | 1.000 | 0.832 | 0.276 | 0.683 | 0.645 | 0.661 |
| late_loss_count_10g | 0.832 | 1.000 | 0.329 | 0.801 | 0.803 | 0.797 |
| loss_margin_mean_10g | 0.276 | 0.329 | 1.000 | 0.305 | 0.209 | 0.124 |
| weighted_quality_loss_10g | 0.683 | 0.801 | 0.305 | 1.000 | 0.286 | 0.608 |
| bad_loss_weighted_10g | 0.645 | 0.803 | 0.209 | 0.286 | 1.000 | 0.661 |
| home_loss_rate_10g | 0.661 | 0.797 | 0.124 | 0.608 | 0.661 | 1.000 |

## Per-Season Univariate CLV Correlations

| Season | Feature | Pearson r | p-value | n |
|--------|---------|-----------|---------|---|
| 2021 | late_loss_count_5g | N/A | N/A | 318 |
| 2021 | late_loss_count_10g | N/A | N/A | 215 |
| 2021 | loss_margin_mean_10g | N/A | N/A | 215 |
| 2021 | weighted_quality_loss_10g | N/A | N/A | 183 |
| 2021 | bad_loss_weighted_10g | N/A | N/A | 183 |
| 2021 | home_loss_rate_10g | N/A | N/A | 215 |
| 2022 | late_loss_count_5g | N/A | N/A | 150 |
| 2022 | late_loss_count_10g | N/A | N/A | 122 |
| 2022 | loss_margin_mean_10g | N/A | N/A | 122 |
| 2022 | weighted_quality_loss_10g | N/A | N/A | 97 |
| 2022 | bad_loss_weighted_10g | N/A | N/A | 97 |
| 2022 | home_loss_rate_10g | N/A | N/A | 121 |
| 2023 | late_loss_count_5g | N/A | N/A | 358 |
| 2023 | late_loss_count_10g | N/A | N/A | 254 |
| 2023 | loss_margin_mean_10g | N/A | N/A | 254 |
| 2023 | weighted_quality_loss_10g | N/A | N/A | 231 |
| 2023 | bad_loss_weighted_10g | N/A | N/A | 231 |
| 2023 | home_loss_rate_10g | N/A | N/A | 254 |
| 2024 | late_loss_count_5g | -0.1164 | 0.0209 | 394 |
| 2024 | late_loss_count_10g | 0.0295 | 0.6389 | 256 |
| 2024 | loss_margin_mean_10g | -0.0116 | 0.8541 | 256 |
| 2024 | weighted_quality_loss_10g | -0.0145 | 0.8294 | 223 |
| 2024 | bad_loss_weighted_10g | -0.0163 | 0.8087 | 223 |
| 2024 | home_loss_rate_10g | 0.0040 | 0.9498 | 256 |
| 2025 | late_loss_count_5g | -0.1186 | 0.0037 | 597 |
| 2025 | late_loss_count_10g | -0.1480 | 0.0022 | 427 |
| 2025 | loss_margin_mean_10g | -0.1213 | 0.0121 | 427 |
| 2025 | weighted_quality_loss_10g | -0.1869 | 0.0002 | 405 |
| 2025 | bad_loss_weighted_10g | -0.0454 | 0.3626 | 405 |
| 2025 | home_loss_rate_10g | -0.1110 | 0.0219 | 426 |

## Pooled CLV Correlations (All Seasons)

| Feature | Pearson r | p-value | n |
|---------|-----------|---------|---|
| late_loss_count_5g | -0.1177 | — | 991 |
| late_loss_count_10g | -0.0815 | — | 683 |
| loss_margin_mean_10g | -0.0802 | — | 683 |
| weighted_quality_loss_10g | -0.1257 | — | 628 |
| bad_loss_weighted_10g | -0.0350 | — | 628 |
| home_loss_rate_10g | -0.0679 | — | 682 |

## Recommendations

_TODO: Review correlations and decide which features to include in_
_the tournament model. Key questions:_

1. Which features show consistent positive CLV correlation across seasons?
2. Are any features redundant (high internal correlation)?
3. What is the marginal lift over the base Elo+Barttorvik model?
4. Should features be used raw or as interaction terms?
