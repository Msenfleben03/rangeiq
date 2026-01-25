# Sports Betting Model Development - Claude Flow Configuration

## Overview

Multi-agent orchestration for sports betting model development using claude-flow. This enables parallel development, specialized agents, and persistent memory across sessions.

---

## Claude Flow Configuration

### Swarm Settings

```yaml
topology: hierarchical
maxAgents: 8
strategy: parallel
memoryEnabled: true
reasoningBank: true
```

### Agent Types for Sports Betting Development

| Agent | Purpose | Primary Tasks |
|-------|---------|---------------|
| `architect` | System design, model architecture | Data pipeline design, model selection, feature engineering strategy |
| `modeler` | Statistical model implementation | Elo systems, regression models, probability calculations |
| `data-engineer` | Data pipelines, ETL | API integrations, data cleaning, feature extraction |
| `backtester` | Validation, performance analysis | Walk-forward validation, CLV analysis, overfitting detection |
| `betting-logic` | Bet sizing, risk management | Kelly criterion, bankroll allocation, exposure tracking |
| `tester` | Unit tests, integration tests | Model accuracy tests, data validation tests |
| `reviewer` | Code review, best practices | Leakage detection, statistical rigor checks |
| `documenter` | Documentation, context updates | CLAUDE.md updates, ADR writing, data dictionary |

### Memory Namespaces

```yaml
namespaces:
  coordination:
    purpose: "Agent state and task coordination (required)"
    retention: session

  sports-betting/decisions:
    purpose: "Architectural and strategic decisions"
    retention: permanent
    examples:
      - "ADR-001: CLV as primary metric"
      - "ADR-004: Elo before complex models"

  sports-betting/patterns:
    purpose: "Learned solutions and reusable code patterns"
    retention: permanent
    examples:
      - "walk-forward-validation-pattern"
      - "kelly-sizing-implementation"
      - "elo-update-with-mov"

  sports-betting/models:
    purpose: "Model configurations, hyperparameters, performance"
    retention: permanent
    examples:
      - "ncaab-elo-v1: K=20, HCA=100, regression=0.5"
      - "mlb-f5-v1: features=[xFIP, wOBA, park_factor]"

  sports-betting/bugs:
    purpose: "Known issues, fixes, and gotchas"
    retention: permanent
    examples:
      - "sportsipy-rate-limit: add 2s delay between calls"
      - "elo-leakage: must lag ratings by 1 game"

  sports-betting/data:
    purpose: "Data source notes, quality issues, transformations"
    retention: permanent
    examples:
      - "pybaseball-statcast: 2015+ only, use baseballr for older"
      - "covers-odds: scraping unreliable, prefer odds-api"
```

---

## Workflows

### New Model Development

```bash
# 1. Specification - Define what the model should do
npx claude-flow@alpha sparc run specification "NCAAB Elo rating system with margin of victory adjustments"

# 2. Architecture - Design the implementation
npx claude-flow@alpha sparc run architecture "NCAAB Elo model"

# 3. Implementation with TDD
npx claude-flow@alpha sparc tdd "NCAAB Elo model"

# 4. Or use swarm for complex multi-component models
npx claude-flow@alpha swarm init --topology hierarchical --max-agents 6
npx claude-flow@alpha swarm "Build complete NCAAB prediction pipeline: data ingestion, Elo ratings, spread predictions, CLV tracking" --agents 5
```

### Feature Engineering Pipeline

```bash
# Parallel feature development
npx claude-flow@alpha swarm init --topology parallel --max-agents 4

npx claude-flow@alpha agent spawn data-engineer --name "ncaab-features"
npx claude-flow@alpha agent spawn modeler --name "feature-selector"
npx claude-flow@alpha agent spawn backtester --name "feature-validator"
npx claude-flow@alpha agent spawn reviewer --name "leakage-detector"

# Coordinate feature engineering task
npx claude-flow@alpha swarm "Engineer predictive features for NCAAB spread model: efficiency metrics, tempo adjustments, home court, rest days" --agents 4
```

### Backtesting Workflow

```bash
# Store backtesting pattern for reuse
npx claude-flow@alpha memory store "walk-forward-validation" "
def walk_forward_backtest(model, data, start_year, end_year):
    results = []
    for year in range(start_year + 2, end_year + 1):
        train = data[data.season < year]
        test = data[data.season == year]
        model.fit(train)
        preds = model.predict(test)
        results.append(evaluate(preds, test))
    return pd.concat(results)
" --namespace sports-betting/patterns

# Query pattern when needed
npx claude-flow@alpha memory query "walk-forward" --namespace sports-betting/patterns
```

### Bug Fix Workflow

```bash
# Query for similar past fixes
npx claude-flow@alpha memory query "data leakage" --reasoningbank
npx claude-flow@alpha memory query "elo calculation error" --namespace sports-betting/bugs

# After fixing, store the pattern
npx claude-flow@alpha memory store "elo-mov-cap-bug" "
Issue: Uncapped MOV caused rating volatility
Fix: Apply MOV_CAP before Elo update: mov = min(mov, MOV_CAP)
Prevention: Always validate MOV is within expected range
" --namespace sports-betting/bugs
```

### Model Performance Tracking

```bash
# Store model configuration and results
npx claude-flow@alpha memory store "ncaab-elo-v1-results" "
Model: NCAAB Elo v1
Config: K=20, HCA=100, MOV_CAP=25, REGRESSION=0.5
Backtest: 2020-2025 seasons
Results: CLV=1.2%, ROI=2.8%, n=1,847 predictions
Status: Ready for paper betting
" --namespace sports-betting/models

# Query model history
npx claude-flow@alpha memory query "ncaab" --namespace sports-betting/models
```

---

## Task-Specific Agent Configurations

### Data Pipeline Development

```bash
npx claude-flow@alpha swarm init --topology hierarchical --max-agents 4

# Spawn specialized agents
npx claude-flow@alpha agent spawn data-engineer --name "api-integrator" \
  --context "Focus: nfl-data-py, sportsipy, pybaseball API integration"

npx claude-flow@alpha agent spawn data-engineer --name "data-cleaner" \
  --context "Focus: Missing data handling, outlier detection, validation"

npx claude-flow@alpha agent spawn tester --name "data-validator" \
  --context "Focus: Data quality tests, schema validation, freshness checks"

# Run coordinated task
npx claude-flow@alpha swarm "Build NCAAB data pipeline: fetch from sportsipy, clean, validate, store in SQLite" --agents 3
```

### Model Ensemble Development

```bash
npx claude-flow@alpha swarm init --topology parallel --max-agents 6

# Parallel model development
npx claude-flow@alpha agent spawn modeler --name "elo-model"
npx claude-flow@alpha agent spawn modeler --name "regression-model"
npx claude-flow@alpha agent spawn modeler --name "ensemble-combiner"
npx claude-flow@alpha agent spawn backtester --name "model-comparator"
npx claude-flow@alpha agent spawn reviewer --name "overfitting-detector"

npx claude-flow@alpha swarm "Build ensemble model combining Elo ratings and logistic regression for NCAAB spread predictions" --agents 5
```

### Betting System Implementation

```bash
npx claude-flow@alpha swarm init --topology hierarchical --max-agents 5

npx claude-flow@alpha agent spawn betting-logic --name "kelly-calculator"
npx claude-flow@alpha agent spawn betting-logic --name "exposure-tracker"
npx claude-flow@alpha agent spawn data-engineer --name "odds-fetcher"
npx claude-flow@alpha agent spawn tester --name "sizing-validator"

npx claude-flow@alpha swarm "Implement betting execution system: Kelly sizing, exposure limits, multi-book line shopping, bet logging" --agents 4
```

---

## Commands Cheatsheet

```bash
# ═══════════════════════════════════════════════════════════════════
# SETUP
# ═══════════════════════════════════════════════════════════════════
npx claude-flow@alpha init
npx claude-flow@alpha memory init --reasoningbank

# Initialize all sports betting namespaces
npx claude-flow@alpha memory init --namespace sports-betting/decisions
npx claude-flow@alpha memory init --namespace sports-betting/patterns
npx claude-flow@alpha memory init --namespace sports-betting/models
npx claude-flow@alpha memory init --namespace sports-betting/bugs
npx claude-flow@alpha memory init --namespace sports-betting/data

# ═══════════════════════════════════════════════════════════════════
# SWARM OPERATIONS
# ═══════════════════════════════════════════════════════════════════
# Initialize swarm
npx claude-flow@alpha swarm init --topology hierarchical --max-agents 8

# Run swarm task
npx claude-flow@alpha swarm "[task description]" --agents [n]

# Check swarm status
npx claude-flow@alpha swarm status

# Stop swarm
npx claude-flow@alpha swarm stop

# ═══════════════════════════════════════════════════════════════════
# AGENT MANAGEMENT
# ═══════════════════════════════════════════════════════════════════
# Spawn agent
npx claude-flow@alpha agent spawn [type] --name "[name]"

# List active agents
npx claude-flow@alpha agent list

# Stop specific agent
npx claude-flow@alpha agent stop [name]

# ═══════════════════════════════════════════════════════════════════
# MEMORY OPERATIONS
# ═══════════════════════════════════════════════════════════════════
# Store knowledge
npx claude-flow@alpha memory store [key] "[value]" --namespace [ns]

# Query knowledge
npx claude-flow@alpha memory query "[search]" --namespace [ns]
npx claude-flow@alpha memory query "[search]" --reasoningbank

# List stored items
npx claude-flow@alpha memory list --namespace [ns]

# Delete item
npx claude-flow@alpha memory delete [key] --namespace [ns]

# ═══════════════════════════════════════════════════════════════════
# SPARC METHODOLOGY
# ═══════════════════════════════════════════════════════════════════
# Specification phase
npx claude-flow@alpha sparc run specification "[task]"

# Architecture phase
npx claude-flow@alpha sparc run architecture "[task]"

# Pseudocode phase
npx claude-flow@alpha sparc run pseudocode "[task]"

# Refinement phase
npx claude-flow@alpha sparc run refinement "[task]"

# Completion phase
npx claude-flow@alpha sparc run completion "[task]"

# TDD workflow (combines phases)
npx claude-flow@alpha sparc tdd "[task]"

# ═══════════════════════════════════════════════════════════════════
# COMMON SPORTS BETTING TASKS
# ═══════════════════════════════════════════════════════════════════
# New model
npx claude-flow@alpha sparc run specification "[sport] [model-type] model"
npx claude-flow@alpha sparc tdd "[sport] [model-type] model"

# Debug data issue
npx claude-flow@alpha memory query "[data source] [issue]" --namespace sports-betting/bugs

# Store successful pattern
npx claude-flow@alpha memory store "[pattern-name]" "[implementation]" --namespace sports-betting/patterns

# Record model results
npx claude-flow@alpha memory store "[model-version]-results" "[config and metrics]" --namespace sports-betting/models
```

---

## Memory-First Development Pattern

### Before Starting Any Task

```bash
# 1. Query for existing patterns
npx claude-flow@alpha memory query "[task keywords]" --namespace sports-betting/patterns

# 2. Check for known bugs/gotchas
npx claude-flow@alpha memory query "[component]" --namespace sports-betting/bugs

# 3. Review relevant decisions
npx claude-flow@alpha memory query "[topic]" --namespace sports-betting/decisions
```

### After Completing Any Task

```bash
# 1. Store reusable patterns
npx claude-flow@alpha memory store "[pattern-name]" "[code/approach]" --namespace sports-betting/patterns

# 2. Document any bugs encountered
npx claude-flow@alpha memory store "[bug-key]" "[issue, fix, prevention]" --namespace sports-betting/bugs

# 3. Record model configurations if applicable
npx claude-flow@alpha memory store "[model-version]" "[config, results]" --namespace sports-betting/models

# 4. Update SESSION_HANDOFF.md with session summary
```

---

## Integration with Project Files

### CLAUDE.md Integration

The main `CLAUDE.md` file should reference this document:

```markdown
## Multi-Agent Development
See `CLAUDE-FLOW.md` for swarm configuration, agent types, and orchestration workflows.
```

### Session Handoff Updates

After each claude-flow session, update `SESSION_HANDOFF.md`:

```markdown
### Claude Flow Session [DATE]
**Swarm Used:** Yes/No
**Agents:** [list]
**Memory Items Stored:**
- [namespace]: [key]
**Task Completed:** [description]
```

---

## Recommended Workflow by Project Phase

### Phase 1-2: Foundation (Weeks 1-4)

```bash
# Single-agent or small swarm - building core components
npx claude-flow@alpha sparc tdd "NCAAB Elo rating system"
npx claude-flow@alpha sparc tdd "SQLite bet tracking database"
```

### Phase 3-4: Expansion (Weeks 5-8)

```bash
# Medium swarm - parallel model development
npx claude-flow@alpha swarm init --topology parallel --max-agents 4
npx claude-flow@alpha swarm "Build MLB F5 and player prop models" --agents 4
```

### Phase 5+: Full Operations (Weeks 9+)

```bash
# Large swarm - complex system integration
npx claude-flow@alpha swarm init --topology hierarchical --max-agents 6
npx claude-flow@alpha swarm "Integrate daily prediction pipeline: data refresh, model runs, odds comparison, bet recommendations, logging" --agents 6
```

---

## Troubleshooting

### Agent Not Responding

```bash
npx claude-flow@alpha agent list
npx claude-flow@alpha agent stop [stuck-agent]
npx claude-flow@alpha agent spawn [type] --name "[new-name]"
```

### Memory Query Returns Nothing

```bash
# Check namespace exists
npx claude-flow@alpha memory list --namespace [ns]

# Try broader search
npx claude-flow@alpha memory query "[single keyword]" --reasoningbank
```

### Swarm Task Incomplete

```bash
# Check status
npx claude-flow@alpha swarm status

# If stuck, stop and restart with fewer agents
npx claude-flow@alpha swarm stop
npx claude-flow@alpha swarm "[task]" --agents 3  # Reduced from original
```
