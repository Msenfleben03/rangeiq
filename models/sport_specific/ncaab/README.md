# NCAAB Models

## Purpose

NCAA Men's Basketball specific prediction models, including Elo ratings, tournament forecasting, and conference-adjusted metrics. NCAAB is ideal for sports betting due to high game volume, inefficient markets in mid-major conferences, and abundant statistical data.

## NCAAB Specifics

**Season Structure**:

- Regular season: ~November-March (350+ D1 teams)
- Conference tournaments: Early March
- March Madness: 68-team single-elimination (mid-March to early April)

**Betting Opportunities**:

- **High Volume**: 5,000+ games per season
- **Market Inefficiencies**: Mid-major and low-tier conferences underpriced
- **Tournament Variance**: Upsets create value opportunities

**Key Metrics**:

- **Tempo/Pace**: Possessions per game (affects totals betting)
- **Four Factors**: eFG%, TOV%, ORB%, FT Rate
- **Strength of Schedule**: Conference strength varies wildly

## Models

### Team Ratings (`team_ratings.py` - Planned)

- Elo ratings with NCAAB-specific K-factor (20-32)
- BPI-style efficiency ratings
- Conference adjustments
- Tournament seeding integration

### Player Impact (`player_impact.py` - Planned)

- Star player injury/absence modeling
- NBA-prospect impact on team strength
- Transfer portal adjustments

### Tournament Models (`tournament.py` - Planned)

- Bracket simulation
- Upset probability based on seeding
- Conference tournament fatigue factors

## Quick Start

```python
from models.sport_specific.ncaab.team_ratings import NCAABElo

# Initialize NCAAB Elo
elo = NCAABElo(
    k_factor=24,           # NCAAB standard
    base_rating=1500,
    home_advantage=80      # ~2.5 point spread
)

# Predict Duke vs UNC
win_prob = elo.predict_game('duke', 'unc', neutral_site=False)
```

## NCAAB-Specific Considerations

**Conference Strength**:

- Power conferences (ACC, Big Ten, SEC, Big 12, Big East, Pac-12)
- Mid-majors (A-10, WCC, MVC)
- Low-majors (America East, MEAC, SWAC)

**Tempo Adjustments**:

```python
# Adjust for pace in totals betting
expected_total = (team_ppg * opp_pace / 100) + (opp_ppg * team_pace / 100)
```

**March Madness Patterns**:

- 12 seeds beat 5 seeds ~36% (historical)
- 1 seeds are 99%+ to reach Sweet 16
- Conference tournament winners often undervalued

## References

- [KenPom Ratings](https://kenpom.com/) - Efficiency metrics
- [BartTorvik](https://barttorvik.com/) - T-Rank ratings
- Data Source: sportsipy, sports-reference.com

---

**Status**: 🔄 Planned - Phase 1 (Weeks 1-2)
**Priority**: High (primary betting focus)
