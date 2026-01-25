# Data Dictionary - Sports Betting Models

## Overview

This document defines all data fields, their sources, and usage across sports betting models. Keep updated as new features are engineered.

---

## Universal Fields (All Sports)

### Game Identifiers

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| `game_id` | string | Various | Unique game identifier (format varies by sport) |
| `game_date` | date | Various | Date of game (YYYY-MM-DD) |
| `game_time` | datetime | Various | Scheduled start time (UTC) |
| `season` | int | Derived | Season year (e.g., 2025 for 2025-26 season) |
| `week` | int | Various | Week number (NFL/NCAAF) or null |
| `is_neutral_site` | bool | Various | True if neutral venue |
| `is_postseason` | bool | Various | True if playoff/tournament game |

### Team Identifiers

| Field | Type | Description |
|-------|------|-------------|
| `home_team_id` | string | Home team unique identifier |
| `away_team_id` | string | Away team unique identifier |
| `home_team_name` | string | Home team display name |
| `away_team_name` | string | Away team display name |
| `home_conference` | string | Conference affiliation |
| `away_conference` | string | Conference affiliation |

### Betting Lines

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| `spread_home` | float | Odds API/Covers | Home team spread (negative = favorite) |
| `spread_away` | float | Derived | Away spread = -1 × home spread |
| `total` | float | Odds API/Covers | Over/under total |
| `moneyline_home` | int | Odds API | Home team moneyline (American odds) |
| `moneyline_away` | int | Odds API | Away team moneyline (American odds) |
| `spread_odds_home` | int | Odds API | Juice on home spread (usually -110) |
| `spread_odds_away` | int | Odds API | Juice on away spread |
| `over_odds` | int | Odds API | Juice on over |
| `under_odds` | int | Odds API | Juice on under |
| `line_timestamp` | datetime | Derived | When line was captured |
| `is_closing_line` | bool | Derived | True if final line before game |

### Game Results

| Field | Type | Description |
|-------|------|-------------|
| `home_score` | int | Final home team score |
| `away_score` | int | Final away team score |
| `home_margin` | int | home_score - away_score |
| `total_points` | int | home_score + away_score |
| `spread_result` | string | 'home_cover', 'away_cover', 'push' |
| `total_result` | string | 'over', 'under', 'push' |
| `moneyline_result` | string | 'home', 'away' |

---

## NCAA Basketball (NCAAB)

### Team Statistics (Season-to-Date)

| Field | Type | Source | Description | Predictive Value |
|-------|------|--------|-------------|------------------|
| `adj_offensive_efficiency` | float | KenPom/calculated | Points per 100 possessions (adjusted) | ⭐⭐⭐⭐⭐ |
| `adj_defensive_efficiency` | float | KenPom/calculated | Points allowed per 100 possessions (adjusted) | ⭐⭐⭐⭐⭐ |
| `adj_tempo` | float | KenPom/calculated | Possessions per 40 minutes (adjusted) | ⭐⭐⭐⭐ |
| `effective_fg_pct` | float | sportsipy | (FG + 0.5 × 3PM) / FGA | ⭐⭐⭐⭐ |
| `turnover_pct` | float | sportsipy | Turnovers per 100 possessions | ⭐⭐⭐⭐ |
| `offensive_reb_pct` | float | sportsipy | % of available offensive rebounds grabbed | ⭐⭐⭐ |
| `ft_rate` | float | sportsipy | FTA / FGA | ⭐⭐⭐ |
| `three_pt_rate` | float | sportsipy | 3PA / FGA | ⭐⭐⭐ |
| `three_pt_pct` | float | sportsipy | 3PM / 3PA | ⭐⭐⭐ |
| `assist_rate` | float | sportsipy | Assists / FGM | ⭐⭐ |
| `block_pct` | float | sportsipy | Blocks per 100 opponent FGA | ⭐⭐ |
| `steal_pct` | float | sportsipy | Steals per 100 opponent possessions | ⭐⭐ |

### Elo Ratings

| Field | Type | Description |
|-------|------|-------------|
| `elo_rating` | float | Current Elo rating (1500 = average) |
| `elo_pre_game` | float | Rating before this game |
| `elo_post_game` | float | Rating after this game |
| `elo_change` | float | Rating change from this game |

### Situational Factors

| Field | Type | Description | Predictive Value |
|-------|------|-------------|------------------|
| `days_rest` | int | Days since last game | ⭐⭐⭐ |
| `is_back_to_back` | bool | Playing second day in a row | ⭐⭐⭐ |
| `travel_distance` | float | Miles traveled for away team | ⭐⭐ |
| `is_conference_game` | bool | Conference matchup | ⭐⭐ |
| `is_rivalry` | bool | Traditional rivalry game | ⭐ |
| `home_court_advantage` | float | Team-specific HCA (default ~3.5 pts) | ⭐⭐⭐⭐ |

### Tournament-Specific (March Madness)

| Field | Type | Description |
|-------|------|-------------|
| `seed` | int | Tournament seed (1-16) |
| `region` | string | Tournament region |
| `round` | int | Tournament round (1-6) |
| `seed_diff` | int | Difference in seeds (favorite perspective) |

---

## MLB

### Starting Pitcher Stats

| Field | Type | Source | Description | Predictive Value |
|-------|------|--------|-------------|------------------|
| `era` | float | pybaseball | Earned Run Average | ⭐⭐⭐ |
| `fip` | float | pybaseball | Fielding Independent Pitching | ⭐⭐⭐⭐ |
| `xfip` | float | pybaseball | Expected FIP (normalizes HR/FB) | ⭐⭐⭐⭐⭐ |
| `siera` | float | pybaseball | Skill-Interactive ERA | ⭐⭐⭐⭐⭐ |
| `whip` | float | pybaseball | Walks + Hits per Inning | ⭐⭐⭐ |
| `k_pct` | float | pybaseball | Strikeout percentage | ⭐⭐⭐⭐ |
| `bb_pct` | float | pybaseball | Walk percentage | ⭐⭐⭐⭐ |
| `k_bb` | float | Derived | K% - BB% | ⭐⭐⭐⭐ |
| `gb_pct` | float | pybaseball | Ground ball percentage | ⭐⭐⭐ |
| `hr_fb` | float | pybaseball | Home run to fly ball ratio | ⭐⭐⭐ |
| `innings_pitched` | float | pybaseball | Total IP this season | Context |
| `pitch_count_avg` | float | pybaseball | Average pitches per start | ⭐⭐ |

### Statcast Pitching Metrics

| Field | Type | Source | Description | Predictive Value |
|-------|------|--------|-------------|------------------|
| `stuff_plus` | float | Savant | Pitch quality metric (100 = avg) | ⭐⭐⭐⭐⭐ |
| `location_plus` | float | Savant | Command metric (100 = avg) | ⭐⭐⭐⭐ |
| `pitching_plus` | float | Savant | Combined metric (100 = avg) | ⭐⭐⭐⭐⭐ |
| `xera` | float | Savant | Expected ERA | ⭐⭐⭐⭐⭐ |
| `barrel_pct_against` | float | Savant | Barrel rate against | ⭐⭐⭐⭐ |
| `hard_hit_pct_against` | float | Savant | Hard hit rate against | ⭐⭐⭐⭐ |
| `avg_exit_velo_against` | float | Savant | Average EV against | ⭐⭐⭐⭐ |
| `whiff_pct` | float | Savant | Swinging strike rate | ⭐⭐⭐⭐ |
| `chase_pct` | float | Savant | Chase rate on pitches outside zone | ⭐⭐⭐ |

### Team Offense Stats

| Field | Type | Source | Description | Predictive Value |
|-------|------|--------|-------------|------------------|
| `woba` | float | pybaseball | Weighted On-Base Average | ⭐⭐⭐⭐⭐ |
| `wrc_plus` | float | pybaseball | Weighted Runs Created+ (100 = avg) | ⭐⭐⭐⭐⭐ |
| `ops` | float | pybaseball | On-base + Slugging | ⭐⭐⭐⭐ |
| `iso` | float | pybaseball | Isolated Power (SLG - AVG) | ⭐⭐⭐ |
| `bb_pct_offense` | float | pybaseball | Team walk rate | ⭐⭐⭐ |
| `k_pct_offense` | float | pybaseball | Team strikeout rate | ⭐⭐⭐ |
| `babip` | float | pybaseball | Batting Avg on Balls in Play | ⭐⭐ (noisy) |
| `runs_per_game` | float | pybaseball | Average runs scored | ⭐⭐⭐ |

### Statcast Team Offense

| Field | Type | Source | Description | Predictive Value |
|-------|------|--------|-------------|------------------|
| `xwoba` | float | Savant | Expected wOBA | ⭐⭐⭐⭐⭐ |
| `xba` | float | Savant | Expected Batting Average | ⭐⭐⭐⭐ |
| `xslg` | float | Savant | Expected Slugging | ⭐⭐⭐⭐ |
| `barrel_pct` | float | Savant | Barrel rate | ⭐⭐⭐⭐⭐ |
| `hard_hit_pct` | float | Savant | Hard hit rate (95+ mph EV) | ⭐⭐⭐⭐ |
| `avg_exit_velo` | float | Savant | Average exit velocity | ⭐⭐⭐⭐ |
| `avg_launch_angle` | float | Savant | Average launch angle | ⭐⭐⭐ |
| `sweet_spot_pct` | float | Savant | % of batted balls 8-32 degrees | ⭐⭐⭐ |

### Park Factors

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| `park_factor_runs` | float | FanGraphs | Park factor for runs (100 = neutral) |
| `park_factor_hr` | float | FanGraphs | Park factor for home runs |
| `park_factor_hits` | float | FanGraphs | Park factor for hits |

### Bullpen Stats

| Field | Type | Source | Description | Predictive Value |
|-------|------|--------|-------------|------------------|
| `bullpen_era` | float | pybaseball | Bullpen ERA | ⭐⭐⭐ |
| `bullpen_fip` | float | pybaseball | Bullpen FIP | ⭐⭐⭐⭐ |
| `bullpen_usage_recent` | float | Calculated | Innings pitched last 3 days | ⭐⭐⭐ |
| `closer_available` | bool | Calculated | Is closer available today | ⭐⭐ |

### Weather (Outdoor Parks)

| Field | Type | Source | Description | Predictive Value |
|-------|------|--------|-------------|------------------|
| `temperature` | float | Open-Meteo | Game-time temperature (°F) | ⭐⭐⭐ |
| `wind_speed` | float | Open-Meteo | Wind speed (mph) | ⭐⭐⭐ |
| `wind_direction` | string | Open-Meteo | Wind direction relative to field | ⭐⭐⭐ |
| `humidity` | float | Open-Meteo | Humidity percentage | ⭐⭐ |
| `precipitation_prob` | float | Open-Meteo | Rain probability | Context |
| `is_dome` | bool | Static | True if retractable/dome | Context |

### Player Props (Pitchers)

| Field | Type | Description |
|-------|------|-------------|
| `projected_k` | float | Model prediction for strikeouts |
| `k_line` | float | Sportsbook line for strikeouts |
| `k_over_odds` | int | Odds on over strikeouts |
| `k_under_odds` | int | Odds on under strikeouts |
| `projected_outs` | float | Model prediction for outs recorded |
| `outs_line` | float | Sportsbook line |

### Player Props (Batters)

| Field | Type | Description |
|-------|------|-------------|
| `projected_hits` | float | Model prediction for hits |
| `hits_line` | float | Sportsbook line |
| `projected_tb` | float | Model prediction for total bases |
| `tb_line` | float | Sportsbook line |
| `projected_rbi` | float | Model prediction for RBIs |
| `rbi_line` | float | Sportsbook line |

---

## NFL (Future Development)

### Team Efficiency

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| `epa_per_play` | float | nflfastR | Expected Points Added per play |
| `epa_pass` | float | nflfastR | EPA on passing plays |
| `epa_rush` | float | nflfastR | EPA on rushing plays |
| `success_rate` | float | nflfastR | % of plays with positive EPA |
| `yards_per_play` | float | nflfastR | Average yards per play |
| `dvoa_total` | float | FO (paid) | Defense-adjusted Value Over Average |

### Quarterback Metrics

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| `qb_epa_per_dropback` | float | nflfastR | EPA per dropback |
| `cpoe` | float | nflfastR | Completion % Over Expected |
| `air_yards_per_attempt` | float | nflfastR | Average depth of target |
| `passer_rating` | float | nflfastR | NFL passer rating |

---

## NCAAF (Future Development)

### Returning Production

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| `returning_ppa` | float | CFB Data | Returning production (PPA) |
| `returning_usage` | float | CFB Data | Returning usage % |
| `portal_additions` | int | Calculated | Transfer portal players added |
| `portal_ppa_added` | float | Calculated | PPA from portal additions |

---

## Derived/Calculated Features

### Game Environment

| Field | Formula | Description |
|-------|---------|-------------|
| `implied_total` | (home_implied + away_implied) | Total from moneylines |
| `spread_movement` | closing_spread - opening_spread | Line movement |
| `total_movement` | closing_total - opening_total | Total movement |
| `reverse_line_movement` | Calculated | Money vs line direction |

### Model Outputs

| Field | Type | Description |
|-------|------|-------------|
| `predicted_spread` | float | Model's predicted point spread |
| `predicted_total` | float | Model's predicted total |
| `win_probability` | float | Model's win probability (0-1) |
| `model_edge` | float | win_prob - implied_prob |
| `kelly_fraction` | float | Recommended bet size |
| `ev_dollars` | float | Expected value in dollars |

---

## Rolling & Temporal Features (All Sports)

### Recent Form Features

| Field | Type | Calculation | Window | Predictive Value |
|-------|------|-------------|--------|------------------|
| `wins_last_5` | int | Rolling wins | 5 games | ⭐⭐⭐⭐ |
| `wins_last_10` | int | Rolling wins | 10 games | ⭐⭐⭐⭐ |
| `points_rolling_5` | float | Average points | 5 games | ⭐⭐⭐⭐ |
| `points_rolling_10` | float | Average points | 10 games | ⭐⭐⭐⭐ |
| `points_allowed_rolling_5` | float | Average points allowed | 5 games | ⭐⭐⭐⭐ |
| `spread_cover_rolling_5` | float | Cover rate last 5 | 5 games | ⭐⭐⭐ |
| `ats_record_last_10` | string | ATS record (e.g. "7-3") | 10 games | ⭐⭐⭐ |
| `over_under_last_5` | int | Over count last 5 | 5 games | ⭐⭐⭐ |
| `margin_rolling_5` | float | Average point margin | 5 games | ⭐⭐⭐⭐ |
| `home_record_last_10` | string | Home record | 10 games | ⭐⭐⭐ |
| `away_record_last_10` | string | Away record | 10 games | ⭐⭐⭐ |

### Momentum & Streaks

| Field | Type | Description | Predictive Value |
|-------|------|-------------|------------------|
| `current_streak` | int | Win/loss streak (positive = wins) | ⭐⭐⭐ |
| `ats_streak` | int | ATS streak (positive = covers) | ⭐⭐⭐ |
| `days_since_win` | int | Days since last win | ⭐⭐ |
| `days_since_loss` | int | Days since last loss | ⭐⭐ |
| `games_over_500` | int | Games above/below .500 | ⭐⭐ |
| `playoff_position` | int | Current playoff seeding | ⭐⭐ |
| `elimination_number` | int | Games from playoff elimination | ⭐⭐ |

### Seasonal Context

| Field | Type | Description | Predictive Value |
|-------|------|-------------|------------------|
| `games_played` | int | Total games played this season | Context |
| `games_remaining` | int | Games left in season | Context |
| `pct_season_complete` | float | % of season completed | Context |
| `days_into_season` | int | Days since season start | Context |
| `is_early_season` | bool | First 10 games of season | ⭐⭐ |
| `is_late_season` | bool | Last 10 games of season | ⭐⭐ |
| `playoff_implications` | bool | Win impacts playoff chances | ⭐⭐⭐ |

---

## Betting-Specific Fields

### Bet Tracking (tracking.models.Bet)

| Field | Type | Description |
|-------|------|-------------|
| `bet_id` | int | Unique bet identifier (auto-increment) |
| `created_at` | datetime | When bet was logged |
| `game_id` | string | Foreign key to game |
| `sport` | string | ncaab, mlb, nfl, ncaaf |
| `league` | string | NCAA, MLB, NFL (redundant with sport) |
| `game_date` | date | Date of game |
| `bet_type` | string | spread, total, moneyline, prop |
| `selection` | string | Team name or "over"/"under" |
| `line` | float | Spread line or total line |
| `odds_placed` | int | American odds when bet placed |
| `odds_closing` | int | American odds at game time (for CLV) |
| `stake` | float | Bet amount in dollars |
| `sportsbook` | string | draftkings, fanduel, betmgm, caesars |
| `model_probability` | float | Model's win probability |
| `model_edge` | float | Edge over market (model_prob - market_prob) |
| `result` | string | win, loss, push, pending |
| `profit_loss` | float | Net profit/loss in dollars |
| `clv` | float | Closing line value as decimal |
| `clv_percent` | float | CLV as percentage |
| `notes` | text | Any special notes about bet |
| `is_live` | bool | True if placed during game |

### Prediction Tracking (tracking.models.Prediction)

| Field | Type | Description |
|-------|------|-------------|
| `prediction_id` | int | Unique prediction identifier |
| `created_at` | datetime | When prediction was generated |
| `sport` | string | Sport type |
| `game_id` | string | Foreign key to game |
| `game_date` | date | Date of game |
| `model_name` | string | elo, regression, ensemble |
| `prediction_type` | string | spread, total, moneyline, prop |
| `predicted_value` | float | Model's prediction |
| `market_value` | float | Market line when predicted |
| `closing_value` | float | Closing market line |
| `actual_value` | float | Actual game result |
| `prediction_error` | float | abs(predicted - actual) |
| `beat_market` | bool | True if closer to actual than market |

### Bankroll Log (tracking.models.BankrollLog)

| Field | Type | Description |
|-------|------|-------------|
| `date` | date | Daily snapshot date |
| `starting_balance` | float | Bankroll at start of day |
| `ending_balance` | float | Bankroll at end of day |
| `daily_pnl` | float | Net profit/loss for day |
| `deposits` | float | Money added |
| `withdrawals` | float | Money withdrawn |
| `bets_placed` | int | Number of bets placed |
| `bets_won` | int | Number winning bets |
| `bets_lost` | int | Number losing bets |
| `bets_pushed` | int | Number push bets |
| `avg_clv` | float | Average CLV for day |
| `roi_daily` | float | ROI for day |
| `sharpe_daily` | float | Sharpe ratio for day |

### Team Ratings (tracking.models.TeamRating)

| Field | Type | Description |
|-------|------|-------------|
| `rating_id` | int | Unique rating identifier |
| `updated_at` | datetime | Last update timestamp |
| `sport` | string | Sport type |
| `team_id` | string | Team identifier |
| `team_name` | string | Team display name |
| `season` | int | Season year |
| `rating_type` | string | elo, glicko, offensive_eff, defensive_eff |
| `rating_value` | float | Rating value |
| `rating_rank` | int | Rank among all teams |
| `games_used` | int | Games used for this rating |
| `last_game_id` | string | Most recent game included |

---

## Injury & Roster Data

### Injury Reports

| Field | Type | Source | Description | Predictive Value |
|-------|------|--------|-------------|------------------|
| `injuries_count` | int | ESPN/Covers | Number of injured players | ⭐⭐⭐ |
| `key_injuries` | int | Manual | Number of starters out | ⭐⭐⭐⭐⭐ |
| `injury_impact_rating` | float | Calculated | Estimated impact (0-10) | ⭐⭐⭐⭐ |
| `star_player_out` | bool | Manual | Best player unavailable | ⭐⭐⭐⭐⭐ |
| `starting_pg_status` | string | Reports | NCAAB: Point guard status | ⭐⭐⭐⭐ |
| `starting_qb_status` | string | Reports | NFL: Quarterback status | ⭐⭐⭐⭐⭐ |
| `starting_pitcher_status` | string | Reports | MLB: Starter status | ⭐⭐⭐⭐⭐ |

### Roster Changes (NCAAB/NCAAF)

| Field | Type | Description | Predictive Value |
|-------|------|-------------|------------------|
| `transfer_portal_in` | int | Players added via portal | ⭐⭐⭐ |
| `transfer_portal_out` | int | Players lost to portal | ⭐⭐⭐ |
| `returning_starters` | int | Starters returning from last season | ⭐⭐⭐⭐ |
| `nba_draft_losses` | int | NCAAB: Players to NBA draft | ⭐⭐⭐⭐ |
| `five_star_recruits` | int | Number of 5-star recruits | ⭐⭐⭐ |

---

## Market Efficiency Indicators

### Public Betting Data (When Available)

| Field | Type | Source | Description | Predictive Value |
|-------|------|--------|-------------|------------------|
| `public_bet_pct` | float | Action Network | % of bets on favorite | ⭐⭐⭐ |
| `public_money_pct` | float | Action Network | % of money on favorite | ⭐⭐⭐ |
| `sharp_action` | string | Manual | "sharp" or "public" | ⭐⭐⭐ |
| `reverse_line_movement` | bool | Calculated | Line moves against public | ⭐⭐⭐⭐ |
| `steam_move` | bool | Calculated | Rapid line movement (>1.5 pts) | ⭐⭐⭐⭐ |
| `line_freeze` | bool | Calculated | Books pulled line temporarily | ⭐⭐⭐ |

### Consensus & Line Shopping

| Field | Type | Description |
|-------|------|-------------|
| `consensus_spread` | float | Median spread across books |
| `consensus_total` | float | Median total across books |
| `spread_range` | float | Max spread - Min spread |
| `total_range` | float | Max total - Min total |
| `best_odds_available` | int | Best American odds found |
| `worst_odds_available` | int | Worst American odds found |
| `num_books_offering` | int | Number of books with line |

### Line Movement History

| Field | Type | Description | Predictive Value |
|-------|------|-------------|------------------|
| `opening_spread` | float | Spread when first posted | ⭐⭐ |
| `opening_total` | float | Total when first posted | ⭐⭐ |
| `spread_move_total` | float | Total spread movement | ⭐⭐⭐ |
| `total_move_total` | float | Total total movement | ⭐⭐⭐ |
| `num_line_moves` | int | Number of line changes | ⭐⭐ |
| `time_to_close` | int | Hours from open to close | Context |
| `biggest_move_time` | datetime | When biggest move occurred | ⭐⭐ |

---

## Advanced Metrics (Sport-Specific)

### NCAAB Advanced Stats

| Field | Type | Source | Description | Predictive Value |
|-------|------|--------|-------------|------------------|
| `bpi_rating` | float | ESPN | Basketball Power Index | ⭐⭐⭐⭐⭐ |
| `net_rating` | float | Calculated | Off Eff - Def Eff | ⭐⭐⭐⭐⭐ |
| `sos_rank` | int | KenPom | Strength of schedule rank | ⭐⭐⭐⭐ |
| `luck_rating` | float | KenPom | Luck metric (close game record) | ⭐⭐⭐ |
| `consistency` | float | Calculated | StdDev of point margins | ⭐⭐⭐ |
| `experience` | float | KenPom | Team experience rating | ⭐⭐⭐ |
| `bench_minutes_pct` | float | Calculated | % of minutes from bench | ⭐⭐ |

### MLB Platoon Splits

| Field | Type | Description | Predictive Value |
|-------|------|-------------|------------------|
| `woba_vs_lhp` | float | Team wOBA vs left-handed pitchers | ⭐⭐⭐⭐⭐ |
| `woba_vs_rhp` | float | Team wOBA vs right-handed pitchers | ⭐⭐⭐⭐⭐ |
| `starter_hand` | string | L or R for starting pitcher | Context |
| `platoon_advantage` | bool | Team has platoon advantage | ⭐⭐⭐⭐ |
| `lineup_woba_today` | float | Expected lineup wOBA vs today's pitcher | ⭐⭐⭐⭐⭐ |
| `pitcher_woba_vs_rhb` | float | Pitcher wOBA against RHB | ⭐⭐⭐⭐ |
| `pitcher_woba_vs_lhb` | float | Pitcher wOBA against LHB | ⭐⭐⭐⭐ |

### MLB Batted Ball Profiles

| Field | Type | Description | Predictive Value |
|-------|------|-------------|------------------|
| `pull_pct` | float | % of batted balls pulled | ⭐⭐⭐ |
| `cent_pct` | float | % of batted balls to center | ⭐⭐⭐ |
| `oppo_pct` | float | % of batted balls opposite field | ⭐⭐⭐ |
| `gb_fb_ratio` | float | Ground ball to fly ball ratio | ⭐⭐⭐⭐ |
| `ld_pct` | float | Line drive percentage | ⭐⭐⭐⭐ |
| `popup_pct` | float | Popup percentage | ⭐⭐⭐ |

---

## Model Metadata & Versioning

### Model Configuration

| Field | Type | Description |
|-------|------|-------------|
| `model_version` | string | Version identifier (e.g., "elo_v1.2.0") |
| `model_trained_date` | date | When model was last trained |
| `model_data_cutoff` | date | Latest data used in training |
| `hyperparameters` | json | Model hyperparameters |
| `feature_set` | json | List of features used |
| `backtest_roi` | float | ROI from most recent backtest |
| `backtest_clv` | float | Average CLV from backtest |
| `backtest_period` | string | Date range of backtest |
| `in_production` | bool | Currently used for live betting |

---

## Data Quality Rules

### Required Fields (Must Not Be Null)

- `game_id`
- `game_date`
- `home_team_id`
- `away_team_id`
- `spread_home` (for spread bets)
- `total` (for total bets)

### Validation Ranges

| Field | Min | Max | Flag If Outside |
|-------|-----|-----|-----------------|
| `spread_home` | -35 | 35 | Warning |
| `total` (NCAAB) | 100 | 200 | Warning |
| `total` (MLB) | 5 | 15 | Warning |
| `win_probability` | 0.01 | 0.99 | Error |
| `elo_rating` | 1000 | 2000 | Warning |

### Staleness Thresholds

| Data Type | Max Age | Action If Stale |
|-----------|---------|-----------------|
| Team ratings | 7 days | Warning |
| Player stats | 3 days | Warning |
| Betting lines | 1 hour | Re-fetch |
| Weather | 6 hours | Re-fetch |
