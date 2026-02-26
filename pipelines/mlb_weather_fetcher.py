"""Open-Meteo weather client for MLB game conditions.

Provides both forecast (for live predictions) and historical weather
(for backtesting 2023-2025). Free, no API key, no rate limits.

API: https://open-meteo.com/
    - Forecast: https://api.open-meteo.com/v1/forecast
    - Historical: https://archive-api.open-meteo.com/v1/archive

Parameters needed per game:
    - temperature_2m (°F)
    - wind_speed_10m (mph)
    - wind_direction_10m (degrees, 0=N, 90=E)
    - relative_humidity_2m (%)
    - precipitation_probability (%)

Query with stadium latitude/longitude at scheduled game time.
Skip for domed stadiums (is_dome flag in teams table).

References:
    - Weather research: docs/mlb/research/weather-effects.md
    - Stadium coordinates: teams table in mlb_data.db
"""

# TODO: Phase 2 implementation (after core moneyline model)
# - OpenMeteoClient class
# - fetch_game_weather(lat, lon, game_datetime) → forecast
# - fetch_historical_weather(lat, lon, date, hour) → archive
# - batch_fetch_historical(games_df) → enriched with weather
# - Stadium coordinate lookup from teams table
# - Dome detection: skip weather fetch for domed stadiums
# - Convert Celsius → Fahrenheit, m/s → mph
# - Cache layer to avoid re-fetching same coordinates/dates
