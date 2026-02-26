"""Weather impact feature engineering for MLB totals.

Weather is the most consistently profitable simple variable for totals
betting. Wind blowing in from center field at 5+ mph produced unders
at 55.5% rate since 2005 with only one losing season in 14 years.

Key variables:
    - Wind speed (mph) and direction relative to field orientation
    - Temperature (modest effect: ~20 ft difference at 45°F vs 95°F)
    - Humidity (counterintuitive: humid air less dense but ball heavier)
    - Dome flag (override all weather features)

Wind bearing categories:
    - 'in': blowing toward home plate → suppresses scoring (UNDERS)
    - 'out': blowing toward outfield → boosts scoring (OVERS, less consistent)
    - 'cross_l' / 'cross_r': crosswind effects on fly balls

Stadium orientation matters: must convert raw wind direction (degrees)
to field-relative bearing using each stadium's home plate orientation.

Data source: Open-Meteo API (free, no key, historical + forecast)

References:
    - Research doc: docs/mlb/research/weather-effects.md
    - Park interaction: docs/mlb/research/park-factors.md
"""

# TODO: Phase 2 implementation (after core moneyline model)
# - compute_weather_features(game_pk)
# - convert_wind_to_field_bearing(wind_deg, stadium_orientation_deg)
# - compute_scoring_adjustment(wind_bearing, wind_speed, temp)
# - Stadium orientation lookup table (30 MLB stadiums)
# - Dome detection (skip weather for retractable roofs when closed)
