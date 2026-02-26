# Weather Effects Research

## Wind: The Most Consistently Profitable Simple Variable

**Wind blowing IN from center field at 5+ mph:**

- Unders hit at 55.5% rate (764-613-76) since 2005
- Only ONE losing season in 14 years
- Works because books sometimes don't adjust until wind confirmed on game morning

**Wind blowing OUT:**

- Correlates with overs but LESS consistently than wind-in correlates with unders
- Wrigley Field: 10 mph wind speed change shifts average HR distance ~61 feet

## Temperature

Modest effect: ball hit at 45°F travels only ~20 feet shorter than at 95°F.
Hot air is less dense → ball travels farther. Real but not huge.

## Humidity (Counterintuitive)

Humid air is LESS dense (water vapor lighter than nitrogen/oxygen).
BUT: humidity makes the ball heavier and less elastic, slightly reducing distance.
Net effect is small — secondary to wind.

## Dome Stadiums (Skip Weather)

Must identify domed/retractable roof stadiums and skip weather features.
Retractable roofs: need to determine if open or closed (weather-dependent).

## Stadium Orientation

Raw wind direction (degrees) must be converted to field-relative bearing.
Each stadium's home plate faces a different compass direction.
Wind "in" at Wrigley ≠ same compass bearing as wind "in" at Fenway.

## Implementation Priority

Phase 2 (after core moneyline model). Add weather for totals model.
Open-Meteo provides both forecast AND historical data (back to 1940).

## Sources

- Ballpark Pal: ML model trained on 1M+ batted balls, 20K games
- Wrigley wind study: Cubs-specific analysis
