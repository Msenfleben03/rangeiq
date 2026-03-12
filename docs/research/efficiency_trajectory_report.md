# Efficiency Trajectory Research Report

## Snapshot Frequency Audit

| Season | Unique Dates | Avg Gap (days) | Max Gap (days) | Date Range |
|--------|-------------|----------------|----------------|------------|
| 2021 | 134 | 1.0 | 1.0 | 2020-11-24 to 2021-04-06 |
| 2022 | 148 | 1.0 | 1.0 | 2021-11-08 to 2022-04-04 |
| 2023 | 149 | 1.0 | 1.0 | 2022-11-06 to 2023-04-03 |
| 2024 | 158 | 1.0 | 1.0 | 2023-11-05 to 2024-04-10 |
| 2025 | 232 | 1.0 | 8.0 | 2024-11-02 to 2025-06-30 |

## Feature Distributions

### Season 2021

|                          |    Mean |     Std |       Min |   Median |      Max |
|:-------------------------|--------:|--------:|----------:|---------:|---------:|
| adj_o_slope_10s          | -0.0084 |  0.2044 |   -1.3189 |   0.0192 |   0.7812 |
| adj_d_slope_10s          |  0.0107 |  0.1997 |   -1.0181 |  -0.0206 |   1.2628 |
| net_efficiency_slope_10s |  0.0023 |  0.1687 |   -1.1288 |  -0.0001 |   0.9742 |
| barthag_delta_10s        |  0.0004 |  0.035  |   -0.3036 |   0.0001 |   0.1666 |
| barthag_delta_20s        | -0.0002 |  0.0515 |   -0.3697 |   0.0004 |   0.2252 |
| rank_change_20s          | -0.004  | 21.6447 | -140      |   0      | 101      |

### Season 2022

|                          |    Mean |     Std |       Min |   Median |      Max |
|:-------------------------|--------:|--------:|----------:|---------:|---------:|
| adj_o_slope_10s          |  0.012  |  0.1959 |   -1.0499 |   0.0186 |   0.9007 |
| adj_d_slope_10s          | -0.0099 |  0.201  |   -0.929  |  -0.0168 |   1.3142 |
| net_efficiency_slope_10s |  0.0021 |  0.1737 |   -0.9317 |   0.0002 |   0.8315 |
| barthag_delta_10s        |  0.0001 |  0.0359 |   -0.1961 |   0.0001 |   0.2389 |
| barthag_delta_20s        | -0.0001 |  0.0512 |   -0.259  |  -0.0003 |   0.2796 |
| rank_change_20s          | -0.0367 | 22.3023 | -110      |   0      | 133      |

### Season 2023

|                          |    Mean |     Std |       Min |   Median |      Max |
|:-------------------------|--------:|--------:|----------:|---------:|---------:|
| adj_o_slope_10s          |  0.0346 |  0.1818 |   -1.302  |   0.0346 |   0.9391 |
| adj_d_slope_10s          | -0.0328 |  0.1831 |   -0.8511 |  -0.0297 |   0.9803 |
| net_efficiency_slope_10s |  0.0018 |  0.1741 |   -0.8559 |   0.003  |   0.7738 |
| barthag_delta_10s        | -0      |  0.0368 |   -0.1655 |   0.0009 |   0.187  |
| barthag_delta_20s        |  0.0002 |  0.0538 |   -0.2492 |   0.0009 |   0.2739 |
| rank_change_20s          |  0.2396 | 23.8041 | -103      |   0      | 124      |

### Season 2024

|                          |    Mean |     Std |       Min |   Median |      Max |
|:-------------------------|--------:|--------:|----------:|---------:|---------:|
| adj_o_slope_10s          |  0.0477 |  0.1667 |   -0.5659 |   0.0431 |   0.8104 |
| adj_d_slope_10s          | -0.0445 |  0.1656 |   -0.6859 |  -0.0412 |   0.6085 |
| net_efficiency_slope_10s |  0.0032 |  0.1539 |   -0.6955 |   0.0028 |   0.8622 |
| barthag_delta_10s        |  0.0001 |  0.0319 |   -0.1576 |   0.0006 |   0.1455 |
| barthag_delta_20s        | -0.0003 |  0.0485 |   -0.2277 |   0.0008 |   0.2238 |
| rank_change_20s          | -0.0018 | 21.5589 | -106      |   0      | 111      |

### Season 2025

|                          |    Mean |     Std |      Min |   Median |      Max |
|:-------------------------|--------:|--------:|---------:|---------:|---------:|
| adj_o_slope_10s          |  0.0441 |  0.1864 |  -0.7789 |   0.0291 |   1.4851 |
| adj_d_slope_10s          | -0.0411 |  0.1848 |  -1.3998 |  -0.0256 |   0.7255 |
| net_efficiency_slope_10s |  0.0031 |  0.1702 |  -0.8783 |   0.0038 |   0.8311 |
| barthag_delta_10s        |  0.0005 |  0.0316 |  -0.14   |   0.0008 |   0.1828 |
| barthag_delta_20s        |  0.0008 |  0.0455 |  -0.2028 |   0.0006 |   0.2393 |
| rank_change_20s          |  0.3564 | 20.6174 | -95      |   0      | 115      |

## Internal Correlation Matrix

Computed across all seasons combined. High internal correlation (>0.8) suggests redundant features.

## CLV Correlations by Season

| Season | Feature | Pearson r | p-value | N obs |
|--------|---------|-----------|---------|-------|
| 2021 | adj_o_slope_10s | nan | nan | 1138 |
| 2021 | adj_d_slope_10s | nan | nan | 1138 |
| 2021 | net_efficiency_slope_10s | nan | nan | 1138 |
| 2021 | barthag_delta_10s | nan | nan | 1072 |
| 2021 | barthag_delta_20s | nan | nan | 987 |
| 2021 | rank_change_20s | nan | nan | 987 |
| 2022 | adj_o_slope_10s | nan | nan | 484 |
| 2022 | adj_d_slope_10s | nan | nan | 484 |
| 2022 | net_efficiency_slope_10s | nan | nan | 484 |
| 2022 | barthag_delta_10s | nan | nan | 436 |
| 2022 | barthag_delta_20s | nan | nan | 369 |
| 2022 | rank_change_20s | nan | nan | 369 |
| 2023 | adj_o_slope_10s | nan | nan | 1198 |
| 2023 | adj_d_slope_10s | nan | nan | 1198 |
| 2023 | net_efficiency_slope_10s | nan | nan | 1198 |
| 2023 | barthag_delta_10s | nan | nan | 1108 |
| 2023 | barthag_delta_20s | nan | nan | 939 |
| 2023 | rank_change_20s | nan | nan | 939 |
| 2024 | adj_o_slope_10s | 0.0035 | 0.9027 | 1214 |
| 2024 | adj_d_slope_10s | 0.0041 | 0.8873 | 1214 |
| 2024 | net_efficiency_slope_10s | 0.0079 | 0.7846 | 1214 |
| 2024 | barthag_delta_10s | 0.0066 | 0.8226 | 1140 |
| 2024 | barthag_delta_20s | 0.0484 | 0.1332 | 962 |
| 2024 | rank_change_20s | 0.0451 | 0.1621 | 962 |
| 2025 | adj_o_slope_10s | 0.0083 | 0.7446 | 1562 |
| 2025 | adj_d_slope_10s | -0.0134 | 0.5963 | 1562 |
| 2025 | net_efficiency_slope_10s | -0.0059 | 0.8159 | 1562 |
| 2025 | barthag_delta_10s | 0.0604 | 0.0204 | 1473 |
| 2025 | barthag_delta_20s | 0.0303 | 0.2842 | 1255 |
| 2025 | rank_change_20s | 0.0317 | 0.2617 | 1255 |

## Recommendation

*Placeholder: Analyze correlations above to determine which trajectory
features add predictive value beyond the base Elo+Barttorvik model.
Features with consistent positive CLV correlation across seasons
are candidates for inclusion.*
