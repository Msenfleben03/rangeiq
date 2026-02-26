# Park Factors Research

## Key Insight: Event-Specific, Not Just Runs

Parks affect singles, doubles, triples, strikeouts, and walks INDEPENDENTLY.
A single run-scoring multiplier is insufficient.

## Notable Parks

| Park | Key Factor | Notes |
|------|-----------|-------|
| Coors Field | Balls travel ~9% farther | -3" breaking ball movement, thin air |
| Dodger Stadium | 132 HR factor | Leads MLB |
| Yankee Stadium | Short right-field porch | Disproportionately benefits LHB |
| Fenway Park | Green Monster | Suppresses HR to left, inflates doubles |
| Wrigley Field | Wind-dependent | Can shift total by full run |
| Oracle Park | Pitcher-friendly | Suppresses HR, cold + marine air |

## Handedness Interaction

Yankee Stadium example: short right-field porch means LHB pull HRs more.
Must model HR_factor_LHB and HR_factor_RHB separately.
Then weight by lineup handedness composition against the starter.

## Data Source

FanGraphs park factors (free via pybaseball):

- Updated annually
- Available by event type (HR, H, 2B, 3B, BB, SO)
- 100 = league average

## Implementation

Store in park_factors table per team per season.
Apply as multiplier to raw lambda in Poisson model.
Handedness-adjusted HR factors interact with lineup composition.
