# MLB Models

## Purpose

Major League Baseball specific prediction models, including pitcher matchups, team offense/defense ratings, first 5 innings (F5) betting, and player props. MLB offers high betting volume (162 games per team) and data-rich environment ideal for statistical modeling.

## MLB Specifics

**Season Structure**:

- Regular season: April-September (162 games × 30 teams = 2,430 games)
- Playoffs: October (Wild Card, Division Series, Championship Series, World Series)

**Betting Opportunities**:

- **Starting Pitcher Dependency**: Pitcher quality drives 60%+ of game outcome
- **F5 Betting (First 5 Innings)**: Isolate starting pitcher performance
- **Player Props**: Hits, HRs, RBIs, Ks (high volume, inefficient markets)
- **Run Totals**: Park factors and weather create edges

**Key Metrics**:

- **Pitcher**: ERA, FIP, xFIP, SIERA, K/9, BB/9, WHIP
- **Team Offense**: wOBA, wRC+, ISO, BB%, K%
- **Defense**: UZR, DRS, shift positioning
- **Statcast**: Exit velocity, launch angle, barrel rate

## Models

### Pitcher Model (`pitcher_model.py` - Planned)

- Starter ERA, FIP, recent form (last 3 starts)
- Platoon splits (vs LHB/RHB)
- Pitch mix and usage trends
- Rest days and workload

### Team Offense (`team_offense.py` - Planned)

- Team wOBA vs LHP/RHP
- Recent form (last 7/14 days)
- Platoon matchup advantages
- Home/road splits

### F5 Model (`f5_model.py` - Planned)

- Starting pitcher only (bullpen doesn't matter)
- First 5 innings run totals
- Lower variance than full game

### Player Props (`player_props.py` - Planned)

- Batter vs pitcher matchups
- Historical H2H stats
- Ballpark factors
- Weather conditions

## Quick Start

```python
from models.sport_specific.mlb.pitcher_model import MLBPitcherModel

# Initialize pitcher-focused model
model = MLBPitcherModel()

# Predict Yankees vs Red Sox (Gerrit Cole vs Chris Sale)
prediction = model.predict_game(
    home_team='yankees',
    away_team='red_sox',
    home_pitcher='gerrit_cole',
    away_pitcher='chris_sale',
    ballpark='yankee_stadium',
    temperature=75,
    wind_mph=10,
    wind_direction='out_to_left'
)

print(f"Home win prob: {prediction['home_win_prob']:.1%}")
print(f"Total runs: {prediction['total_runs']:.1f}")
print(f"F5 total: {prediction['f5_total']:.1f}")
```

## MLB-Specific Considerations

**Park Factors**:

```python
park_factors = {
    'coors_field': 1.30,     # Extreme hitter's park (altitude)
    'oracle_park': 0.85,     # Extreme pitcher's park (cold, wind)
    'fenway_park': 1.05,     # Slightly favors hitters (Green Monster)
    'yankee_stadium': 1.08,  # Favors HR (short right field porch)
}
```

**Weather Impact**:

- Hot weather (>85°F): +0.3 runs per game
- Wind out to CF (>10 mph): +0.5 runs
- Wind in from CF: -0.4 runs
- Cold (<50°F): -0.2 runs

**Platoon Splits**:

```python
# Adjust for batter vs pitcher handedness
if batter_hand != pitcher_hand:  # Opposite (favorable for batter)
    batter_woba *= 1.08
else:  # Same hand (favorable for pitcher)
    batter_woba *= 0.92
```

**F5 vs Full Game**:

- F5 isolates starting pitchers (more predictable)
- Bullpen variance eliminated
- Lower correlation with game result (~70%)

## Data Sources

- **pybaseball**: Stats from Baseball Reference, FanGraphs
- **Statcast**: MLB's tracking data (exit velo, launch angle)
- **Vegas Odds**: Pinnacle, DraftKings, FanDuel

## References

- [FanGraphs](https://www.fangraphs.com/) - Advanced metrics
- [Baseball Savant](https://baseballsavant.mlb.com/) - Statcast data
- [Baseball Reference](https://www.baseball-reference.com/) - Historical stats

---

**Status**: 🔄 Planned - Phase 2 (Weeks 3-4)
**Priority**: Medium (MLB season starts April)
