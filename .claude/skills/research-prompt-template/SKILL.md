---
name: research-prompt-template
description: Structure comprehensive research prompts for multi-agent orchestration in sports betting model development. Use when creating research briefs for data source evaluation, model feature investigation, odds provider analysis, or market inefficiency studies. Provides XML-based template with dependency graphs, orchestration hints, domain-specific quality standards, and integration with project pipelines.
triggers:
  - research prompt
  - research brief
  - research template
  - investigate data source
  - evaluate feature
  - research integration
---

# Research Prompt Template

## Overview

Structured template for creating research prompts that enable effective multi-agent decomposition
for sports betting research. Provides dependency signaling, parallelization hints, domain-specific
quality standards, and integration with the project's existing pipeline architecture.

## When to Use

- Evaluating new data sources (KenPom, Barttorvik, Sagarin, etc.)
- Investigating model features (efficiency ratings, tempo, SOS)
- Analyzing odds providers or sportsbook APIs
- Researching market inefficiencies or betting strategies
- Designing multi-phase research workflows for any complex investigation
- Documenting research requirements for orchestration skills

## When NOT to Use

- Simple factual lookups (use WebSearch directly)
- Single-source API documentation reads (use context7 or WebFetch)
- Quick odds checks (use `/fetch-odds` skill instead)

---

## Template Structure

```xml
<research_stance>
[Analytical framing - expertise required, posture (skeptical, exploratory, comparative)]
[Reference technologies/sources for comparative context]
</research_stance>

<background>
<researcher_profile>
[Who is requesting, their domain expertise, active workflows]
[Tech stack: Python 3.11+, pandas, scikit-learn, SQLite]
</researcher_profile>

<discovery_context>
[How topic was discovered, preliminary findings]
[Hypotheses to validate or challenge]
</discovery_context>

<existing_pipeline_context>
<!-- CRITICAL: Always reference what's already built to avoid redundant research -->
[Current data sources: ESPN Site API (scores), ESPN Core API (odds)]
[Current model: Elo ratings with walk-forward backtest]
[Current pipeline: unified_fetcher.py → SQLite → backtest_ncaab_elo.py]
[Known gaps: efficiency ratings, conference strength, injuries]
</existing_pipeline_context>

<known_sources>
[Pre-researched URLs to consult]
[Reduces redundant discovery]
</known_sources>
</background>

<task>
<objective>
[Primary goal in 1-2 sentences]
</objective>

<orchestration_hints>
<!--
  INDEPENDENT (parallelizable):
    - List questions with no cross-dependencies

  DEPENDENT:
    - List questions requiring prior outputs
    - Identify terminal synthesis nodes

  RESEARCH INTENSITY:
    - High: Multiple queries across sources
    - Moderate: Focused documentation review
    - Low: Single source or gated information
-->
</orchestration_hints>

<research_questions>
  <question id="1" priority="high" depends_on="none">
    <title>[Question title]</title>
    <instructions>
    [Specific sub-questions to address]
    [Output format requirements]
    </instructions>
  </question>

  <question id="2" priority="high" depends_on="none" shared_context="3">
    <!-- shared_context signals co-assignment efficiency -->
  </question>

  <question id="N" priority="critical" depends_on="1,2,3">
    <!-- Terminal synthesis node - executes last -->
  </question>
</research_questions>
</task>

<quality_standards>
[Global constraints propagated to all sub-agents]
- Citation requirements
- Confidence level assignments
- Vendor vs independent source distinction
- Handling of unavailable information
</quality_standards>

<final_output_specification>
[Merged deliverable structure]
[Section headings and content requirements]
[Expected word count range]
</final_output_specification>
```

---

## Question Attributes

| Attribute | Values | Purpose |
|-----------|--------|---------|
| `id` | Integer | Unique identifier for dependency references |
| `priority` | `critical`, `high`, `medium`, `low` | Execution priority and resource allocation |
| `depends_on` | `none` or comma-separated IDs | Dependency graph for sequencing |
| `shared_context` | Question ID | Signals efficient co-assignment |

---

## Orchestration Hints Pattern

```xml
<orchestration_hints>
<!--
  Questions 1-4: Fully independent, parallelizable
  Questions 5-6: Independent but share research surface (co-assign)
  Question 7: Terminal node - depends on ALL others (1-6)

  Execution waves:
  Wave 1: Q1, Q2, Q3, Q4 (parallel)
  Wave 2: Q5+Q6 (shared context)
  Wave 3: Q7 (synthesis after all complete)
-->
</orchestration_hints>
```

---

## Domain-Specific Quality Standards

### Sports Betting Research Standards

```xml
<quality_standards>
<!-- General -->
- Cite sources for all factual claims with URLs
- Assign confidence levels: [HIGH] multiple sources, [MEDIUM] single source, [LOW] inferred
- Distinguish vendor marketing from independently verified facts
- If information unavailable, state explicitly - do not fabricate
- Use quantitative, no-nonsense language

<!-- Sports Betting Domain-Specific -->
- DATA TEMPORALITY: Can data be obtained point-in-time (pre-game) or only end-of-season?
  Look-ahead bias is the #1 risk in sports modeling.
- COST: Classify as FREE / FREEMIUM / PAID with exact pricing
- COVERAGE: Report % of games/teams/seasons covered
- API ACCESS: Document rate limits, auth requirements, reliability, TOS compliance
- LEGAL: Note any scraping/TOS restrictions vs legitimate API access
- INTEGRATION EFFORT: Estimate lines of code and pipeline changes needed
- HISTORICAL DEPTH: How many seasons back does the data go?
</quality_standards>
```

### Data Source Evaluation Checklist

When researching any new data source, ALL of these must be answered:

| Criterion | Must Answer |
|-----------|-------------|
| Point-in-time? | Can we get ratings/stats AS OF a specific date (not end-of-season)? |
| Free or paid? | Exact cost, free tier limits |
| API or scrape? | Official API, undocumented API, or HTML scraping? |
| Coverage | % of D1 teams, seasons available |
| Update frequency | Daily, weekly, end-of-season? |
| Rate limits | Requests/min, daily caps |
| Auth required? | API key, OAuth, none? |
| TOS compliance | Does usage comply with terms of service? |
| Python library? | Existing package or custom code needed? |
| Historical data? | How far back (2015? 2010? 2000?)? |

---

## Output Specification Templates

### For Data Source Evaluation

```xml
<final_output_specification>
## 1. Executive Summary (2-3 paragraphs)
Quick-hit: Is this source viable for our pipeline? Cost? Coverage?

## 2. Data Description
What metrics/features does this source provide?
Schema sample with field names and types

## 3. Access Method
API details, authentication, rate limits, Python code snippet

## 4. Historical Coverage
Seasons available, games per season, team coverage %

## 5. Point-in-Time Availability (CRITICAL)
Can we reconstruct pre-game state? Or only final ratings?
Impact on look-ahead bias if not point-in-time

## 6. Integration Plan
Pipeline changes needed, estimated effort, dependency on existing code
How it fits into: unified_fetcher.py → SQLite → backtest pipeline

## 7. Cost-Benefit Analysis
Free alternatives vs paid option, expected model improvement

## 8. Recommendation
GO / NO-GO / CONDITIONAL with specific conditions

## 9. Sources & Confidence Log
Every source cited with confidence level
</final_output_specification>
```

### For Model Feature Investigation

```xml
<final_output_specification>
## 1. Feature Overview
What the feature measures, academic basis, prior art

## 2. Predictive Evidence
Published research on predictive power for game outcomes
Effect sizes, R-squared contributions, feature importance rankings

## 3. Data Availability
Where to obtain, cost, coverage, point-in-time access

## 4. Correlation with Existing Features
Does this add signal beyond Elo? Expected multicollinearity?

## 5. Implementation Approach
Feature engineering steps, code changes, backtest plan

## 6. Expected Impact
Sharpe improvement estimate, CLV improvement, confidence interval

## 7. Recommendation
ADD / SKIP / DEFER with reasoning
</final_output_specification>
```

### For General Research

```xml
<final_output_specification>
## 1. Executive Summary (2-3 paragraphs)
Quick-hit answer to primary question

## 2. [Topic] Explanation
Progressive detail (simple to technical)

## 3. Quantitative Evidence
Table with source citations and confidence levels

## 4. Limitations/Shortcomings
Organized by severity

## 5. [Domain-Specific Section]
Tailored to research topic

## 6. Competitive/Comparative Analysis
Side-by-side matrix

## 7. Bottom Line Verdict
Direct assessment with scores/ratings

## 8. Sources & Confidence Log
Every source cited with confidence level
</final_output_specification>
```

---

## Worked Example: KenPom Integration Research

This example shows a complete research prompt for the project's next TODO item.

```xml
<research_stance>
Skeptical of "magic bullet" features. Compare KenPom against free alternatives.
Reference: Current Elo model achieves 6.54% ROI pooled — new features must justify
integration effort and cost. Expect diminishing returns.
</research_stance>

<background>
<researcher_profile>
Sports betting model developer. Building NCAAB Elo model with walk-forward backtest.
Python 3.11+, pandas, scikit-learn, SQLite. ESPN API for scores and odds.
</researcher_profile>

<discovery_context>
Elo model shows 6.54% ROI (p=0.0002) but Sharpe only 0.62 at 5% edge.
Hypothesis: Adding efficiency ratings (AdjEM, AdjO, AdjD, AdjT) should improve
Sharpe to 1.0+ by capturing team quality beyond win/loss record.
KenPom is the gold standard but costs $25/yr.
</discovery_context>

<existing_pipeline_context>
- Scores: ESPN Site API (pipelines/espn_ncaab_fetcher.py)
- Odds: ESPN Core API (pipelines/espn_core_odds_provider.py)
- Pipeline: unified_fetcher.py → data/odds/ → SQLite
- Model: models/elo.py + models/sport_specific/ncaab/team_ratings.py
- Backtest: scripts/backtest_ncaab_elo.py (walk-forward, deepcopy-verified)
- Coverage: 6 seasons (2020-2025), 35,719 games, 91.6% odds coverage
</existing_pipeline_context>

<known_sources>
- https://kenpom.com/ (paid, $25/yr)
- https://barttorvik.com/ (free, T-Rank)
- https://www.warrennolan.com/ (free, various metrics)
- https://haslametrics.com/ (free)
- R package cbbdata (Barttorvik wrapper)
</known_sources>
</background>

<task>
<objective>
Determine the best source for NCAAB efficiency ratings (AdjEM, AdjO, AdjD, AdjT)
that provides point-in-time historical data and integrates into our Python pipeline.
</objective>

<orchestration_hints>
<!--
  Questions 1-3: Fully independent, parallelizable
  Question 4: Independent but shares context with Q3
  Question 5: Terminal synthesis — depends on all others

  Execution waves:
  Wave 1: Q1, Q2, Q3 (parallel)
  Wave 2: Q4 (after Q3 provides free alternatives)
  Wave 3: Q5 (synthesis)
-->
</orchestration_hints>

<research_questions>
  <question id="1" priority="high" depends_on="none">
    <title>KenPom API capabilities and limitations</title>
    <instructions>
    - Does KenPom have an official API? Undocumented endpoints?
    - Can historical ratings be queried by date (point-in-time)?
    - Rate limits, auth method, Python client libraries?
    - TOS: Is automated access permitted for personal use?
    - Output: API spec summary, example response, access constraints
    </instructions>
  </question>

  <question id="2" priority="high" depends_on="none">
    <title>Academic evidence for efficiency ratings in prediction</title>
    <instructions>
    - Published papers using AdjEM/AdjO/AdjD for game prediction
    - Effect size: How much does AdjEM improve over pure Elo?
    - Feature importance: AdjEM vs SOS vs tempo vs other features
    - Output: Table of papers with year, method, improvement metric
    </instructions>
  </question>

  <question id="3" priority="high" depends_on="none">
    <title>Free alternatives to KenPom</title>
    <instructions>
    - Barttorvik T-Rank: API/scraping access, historical depth, Python access
    - Haslametrics, WarrenNolan, Sagarin: data availability
    - ESPN BPI/FPI: accessible via Core API?
    - R cbbdata package: can we call from Python via rpy2?
    - Output: Comparison table (source, cost, coverage, API, point-in-time)
    </instructions>
  </question>

  <question id="4" priority="medium" depends_on="none" shared_context="3">
    <title>Barttorvik T-Rank deep dive</title>
    <instructions>
    - How closely does T-Rank correlate with KenPom AdjEM?
    - Historical data: how far back? Daily snapshots available?
    - Data format: CSV download, API, or scraping only?
    - Output: Feasibility assessment for pipeline integration
    </instructions>
  </question>

  <question id="5" priority="critical" depends_on="1,2,3,4">
    <title>Recommendation: Best path to efficiency ratings</title>
    <instructions>
    - Synthesize findings from Q1-Q4
    - Recommend: KenPom ($25) vs Barttorvik (free) vs other
    - Include: integration effort estimate, expected model improvement
    - Decision criteria: cost, coverage, point-in-time, ease of integration
    - Output: GO/NO-GO recommendation with implementation plan
    </instructions>
  </question>
</research_questions>
</task>

<quality_standards>
- Cite sources for all factual claims with URLs
- Assign confidence: [HIGH] tested/verified, [MEDIUM] documented, [LOW] inferred
- Distinguish official documentation from community reports
- DATA TEMPORALITY: Flag if source only provides end-of-season ratings
- COST: Exact pricing for paid sources
- Report Python accessibility (library, API, scraping complexity)
</quality_standards>

<final_output_specification>
## 1. Executive Summary
Best source for efficiency ratings, cost, expected impact on model

## 2. KenPom Assessment
API access, point-in-time availability, TOS compliance

## 3. Free Alternatives Comparison
Side-by-side matrix of all evaluated sources

## 4. Academic Evidence
Feature importance of efficiency ratings for prediction

## 5. Integration Plan
Pipeline changes, code estimate, timeline

## 6. Cost-Benefit Analysis
$25/yr KenPom vs free alternative vs expected Sharpe improvement

## 7. Recommendation
GO/NO-GO with specific next steps

## 8. Sources & Confidence Log
</final_output_specification>
```

---

## Integration with research-orchestration

This template produces prompts consumed by the `research-orchestration` skill
(located at `~/.claude/skills/research-orchestration/`):

1. **Create prompt** using this template
2. **Invoke** `/research-orchestration` with the prompt
3. **Orchestrator** parses `<orchestration_hints>` for task decomposition
4. **Specialists** receive individual questions with `<quality_standards>`
5. **Synthesis** follows `<final_output_specification>` structure

---

## Where Research Outputs Go

Research results should feed into project artifacts:

| Output Type | Destination |
|-------------|-------------|
| Data source decisions | `docs/DECISIONS.md` |
| Pipeline integration plans | Issue/TODO in MEMORY.md |
| API details/credentials | `.env` (secrets) or `config/` (non-sensitive) |
| Feature evaluation results | `docs/DECISIONS.md` + backtest validation |
| Reusable reference data | `docs/` directory |

---

## Validation Checklist

- [ ] `<research_stance>` defines analytical posture
- [ ] `<researcher_profile>` provides domain context
- [ ] `<existing_pipeline_context>` references current pipeline state
- [ ] Questions have unique IDs and priority levels
- [ ] Dependencies correctly mapped (terminal node depends on all)
- [ ] Parallelizable questions marked `depends_on="none"`
- [ ] Quality standards include confidence level requirements
- [ ] Quality standards include domain checks (point-in-time, cost, coverage)
- [ ] Output specification matches expected deliverable type
- [ ] Output destination identified (DECISIONS.md, MEMORY.md, etc.)
