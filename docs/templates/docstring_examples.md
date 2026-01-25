# Docstring Standards & Examples

## Purpose

This document provides comprehensive examples of docstring formatting for the sports betting project. We follow **Google Style** Python docstrings for consistency and compatibility with documentation generation tools (Sphinx, pdoc).

---

## Why Good Docstrings Matter

1. **Self-Documenting Code**: Function purpose clear without reading implementation
2. **API Generation**: Auto-generate documentation with Sphinx/pdoc
3. **IDE Support**: Better autocomplete and inline help
4. **Onboarding**: New developers understand code faster
5. **Testing**: Examples in docstrings can be tested with `pytest-examples`

---

## General Principles

### Must-Have Elements

Every public function/class should have:

- **One-line summary**: What it does (imperative mood: "Calculate", not "Calculates")
- **Extended description**: Why it exists, when to use it (optional for obvious functions)
- **Args**: All parameters with types and descriptions
- **Returns**: What it returns with type
- **Raises**: Exceptions that can be raised (if applicable)
- **Example**: Working code demonstrating usage
- **Note/Warning**: Important caveats (e.g., data leakage risks)

### Optional But Recommended

- **See Also**: Related functions
- **References**: Research papers, ADRs, external docs
- **Todo**: Known limitations or planned improvements

---

## Template Structure

```python
def function_name(param1: type, param2: type, optional_param: type = default) -> return_type:
    """One-line summary ending with period.

    Extended description explaining what this function does, why it exists,
    and when to use it. Can span multiple paragraphs if needed.

    Important domain-specific context (e.g., for betting: why CLV matters,
    why we prevent data leakage, how this integrates with bankroll management).

    Args:
        param1: Description of first parameter. Include units if relevant
            (e.g., "in dollars", "as percentage", "American odds format").
        param2: Description of second parameter. Can span multiple lines
            if you need to explain details.
        optional_param: Description with default value mentioned if not
            obvious from signature. Defaults to {default}.

    Returns:
        Description of return value. If returning dict/object, specify keys:
            - key1: What it means
            - key2: What it represents

        For simple returns, just: "Type and what it represents"

    Raises:
        ValueError: When this is raised and why
        TypeError: When this is raised and why

    Example:
        >>> result = function_name(param1=value1, param2=value2)
        >>> result
        expected_output

        Or multi-line example:
        >>> instance = MyClass()
        >>> result = instance.function_name(param1=value1)
        >>> result['key1']
        expected_value

    Note:
        Important caveats, gotchas, or warnings. For betting code, mention:
        - Data leakage risks
        - CLV calculation assumptions
        - Performance considerations

    See Also:
        related_function: How it relates
        AnotherClass.method: Why you might use that instead

    References:
        .. [1] Author Name, "Paper Title", Journal, Year
        .. [2] ADR-XXX: Why We Chose This Approach
    """
```

---

## Examples by Function Type

### 1. Simple Utility Function

```python
def american_to_decimal(american: int) -> float:
    """Convert American odds to decimal odds.

    American odds (e.g., -110, +150) are converted to decimal format
    (e.g., 1.91, 2.50) for easier probability calculations.

    Args:
        american: American odds format. Negative for favorites (e.g., -110),
            positive for underdogs (e.g., +150).

    Returns:
        Decimal odds. Always >= 1.0.

    Raises:
        ValueError: If american odds are 0 or invalid.

    Example:
        >>> american_to_decimal(-110)
        1.9090909090909092
        >>> american_to_decimal(+150)
        2.5

    Note:
        Decimal odds include the stake. A $100 bet at 2.5 decimal returns
        $250 total ($150 profit + $100 stake).

    See Also:
        decimal_to_american: Inverse conversion
        american_to_implied_prob: Convert to probability
    """
    if american == 0:
        raise ValueError("American odds cannot be 0")

    if american > 0:
        return (american / 100) + 1
    return (100 / abs(american)) + 1
```

---

### 2. Domain-Specific Calculation (Betting Logic)

```python
def calculate_clv(
    odds_placed: int,
    odds_closing: int,
    stake: float = 100.0
) -> dict[str, float]:
    """Calculate Closing Line Value for a bet.

    CLV measures if you got better odds than the market closed at. It's the
    #1 predictor of long-term profitability, even more important than win rate.
    Positive CLV indicates you're consistently beating the market.

    This calculation assumes:
    - Both odds are in American format
    - Closing line represents true market probability
    - No vig adjustment (uses raw odds)

    Args:
        odds_placed: American odds when your bet was placed (e.g., -105).
        odds_closing: American odds when the market closed (e.g., -110).
        stake: Bet amount in dollars. Defaults to 100.0.

    Returns:
        Dictionary with CLV metrics:
            - clv_percent: CLV as percentage. Positive = good.
            - dollar_value: Dollar value of your edge vs closing line.
            - would_bet: True if CLV exceeds minimum threshold (0.5%).
            - closing_prob: Market's final implied probability.
            - placed_prob: Implied probability when you bet.

    Raises:
        ValueError: If odds are invalid (zero, extreme values >10000).

    Example:
        >>> clv = calculate_clv(odds_placed=-105, odds_closing=-110, stake=100)
        >>> clv['clv_percent']
        0.95
        >>> clv['would_bet']
        True

        Negative CLV (bad):
        >>> clv = calculate_clv(odds_placed=-115, odds_closing=-110)
        >>> clv['clv_percent']
        -0.95
        >>> clv['would_bet']
        False

    Note:
        A CLV of +1% sustained over 1000 bets is worth approximately $1000 in
        expected value. Even 0.5% CLV is profitable long-term.

        CLV can be misleading for:
        - Very large line moves (5+ points) due to injury news
        - Low-liquidity markets (small college sports)
        - Odds taken hours before closing

    See Also:
        track_clv_history: Store CLV for performance analysis
        expected_value: Calculate EV given win probability

    References:
        .. [1] Spanias, D. (2019). "Closing Line Value in Sports Betting"
        .. [2] ADR-003: Why CLV is Primary Success Metric
    """
```

---

### 3. Class Docstring

```python
class EloRating:
    """Elo rating system for team strength estimation.

    Implements a basic Elo rating algorithm with sport-specific adjustments
    for margin of victory, home field advantage, and seasonal regression.

    The Elo system provides:
    - Real-time updating based on game results
    - Probabilistic win expectations
    - Interpretable team strength ratings
    - Fast computation (no model training required)

    Attributes:
        k_factor: Learning rate for rating updates. Higher = faster adjustment.
        base_rating: Starting rating for new teams. Default: 1500.
        ratings: Dict mapping team_id -> current Elo rating.
        home_advantage: Points added to home team's rating. Default: 100.

    Example:
        >>> elo = EloRating(k_factor=20)
        >>> elo.update_rating('team_a', expected_prob=0.6, actual=1.0)
        >>> elo.get_rating('team_a')
        1508.0

        Predict game outcome:
        >>> prob = elo.predict_game('team_a', 'team_b', home='team_a')
        >>> prob
        0.64

    Note:
        Elo ratings assume:
        - All games are equally important (no playoff weighting)
        - Margin of victory is secondary (see EloMOV for alternative)
        - Ratings regress to mean each season

        For NCAA Basketball, typical K-factors: 20-32
        For NFL: 20-25

    See Also:
        EloMOV: Elo with margin of victory adjustments
        GlickoRating: Alternative rating system with uncertainty

    References:
        .. [1] Elo, A. (1978). The Rating of Chessplayers, Past and Present
        .. [2] FiveThirtyEight NFL Elo: https://fivethirtyeight.com/methodology/
        .. [3] ADR-001: Why Elo Before Complex Models
    """

    def __init__(
        self,
        k_factor: int = 20,
        base_rating: float = 1500.0,
        home_advantage: float = 100.0
    ):
        """Initialize Elo rating system.

        Args:
            k_factor: How quickly ratings update. Range: 10-40. Higher values
                make the system more reactive to recent results.
            base_rating: Starting rating for new teams. Default: 1500.
            home_advantage: Points to add to home team rating. Default: 100
                (roughly 3-4 point spread in basketball).
        """
        self.k_factor = k_factor
        self.base_rating = base_rating
        self.home_advantage = home_advantage
        self.ratings: dict[str, float] = {}
```

---

### 4. Data Processing Function (Data Leakage Warning)

```python
def create_rolling_features(
    df: pd.DataFrame,
    columns: list[str],
    windows: list[int],
    min_periods: int = 1
) -> pd.DataFrame:
    """Create rolling window features with proper time-shifting to prevent data leakage.

    Generates rolling statistics (mean, std, min, max) for specified columns
    and window sizes. CRITICAL: All rolling features are shifted by 1 to ensure
    we only use past data for predictions.

    Args:
        df: DataFrame with datetime index, sorted chronologically.
        columns: Column names to create rolling features for.
        windows: Window sizes in number of periods (e.g., [5, 10, 20]).
        min_periods: Minimum observations required for calculation. Defaults to 1.

    Returns:
        Original DataFrame with added rolling feature columns. New columns
        follow naming: "{column}_rolling_{window}_{stat}" (e.g., "points_rolling_5_mean")

    Raises:
        ValueError: If df is not sorted by date or lacks datetime index.
        KeyError: If specified columns don't exist in df.

    Example:
        >>> import pandas as pd
        >>> df = pd.DataFrame({
        ...     'date': pd.date_range('2024-01-01', periods=10),
        ...     'points': [100, 105, 98, 102, 108, 95, 103, 107, 99, 104]
        ... }).set_index('date')
        >>>
        >>> df_features = create_rolling_features(df, ['points'], [3], min_periods=1)
        >>> df_features[['points', 'points_rolling_3_mean']].head()
                    points  points_rolling_3_mean
        2024-01-01     100                    NaN
        2024-01-02     105                  100.0
        2024-01-03      98                  102.5
        2024-01-04     102                  101.0

    Warning:
        **DATA LEAKAGE PREVENTION**: This function applies `.shift(1)` to all
        rolling features. Without shifting, you'd use data from the current row
        in your prediction, which creates look-ahead bias and inflated backtest results.

        Example of leakage:
        ```python
        # ❌ WRONG - This leaks data
        df['rolling_mean'] = df['points'].rolling(5).mean()

        # ✅ CORRECT - This prevents leakage
        df['rolling_mean'] = df['points'].rolling(5).mean().shift(1)
        ```

    Note:
        - First `window - 1` rows will have NaN for that window size
        - Use `min_periods=window` if you require full windows
        - For team-level rolling stats, group by team first:
          ```python
          df.groupby('team_id').apply(
              lambda g: create_rolling_features(g, cols, windows)
          )
          ```

    See Also:
        create_expanding_features: For cumulative statistics
        validate_no_leakage: Test function to check for leakage

    References:
        .. [1] Betancourt, M. "Common Mistakes in Time Series Forecasting"
        .. [2] docs/RUNBOOK.md#data-leakage-checklist
    """
```

---

### 5. Async Function

```python
async def fetch_odds_async(
    game_ids: list[str],
    sportsbook: str = 'draftkings',
    timeout: float = 30.0
) -> dict[str, dict]:
    """Asynchronously fetch current odds for multiple games.

    Fetches odds concurrently to reduce total API call time. Useful for
    rapid line movement tracking during live betting.

    Args:
        game_ids: List of game identifiers to fetch odds for.
        sportsbook: Which sportsbook's odds to fetch. Options: 'draftkings',
            'fanduel', 'betmgm'. Defaults to 'draftkings'.
        timeout: Max seconds to wait for all requests. Defaults to 30.0.

    Returns:
        Dictionary mapping game_id -> odds data:
            {
                'game_123': {
                    'spread': -3.5,
                    'spread_odds': -110,
                    'total': 145.5,
                    'moneyline_home': -150,
                    'moneyline_away': +130,
                    'timestamp': '2026-01-24T10:30:00Z'
                },
                ...
            }

    Raises:
        asyncio.TimeoutError: If requests exceed timeout.
        APIRateLimitError: If API rate limit exceeded (60/min for most books).
        ValueError: If sportsbook not supported.

    Example:
        >>> import asyncio
        >>> game_ids = ['game_123', 'game_456']
        >>> odds = asyncio.run(fetch_odds_async(game_ids, sportsbook='fanduel'))
        >>> odds['game_123']['spread']
        -3.5

    Note:
        - Respects API rate limits (max 10 concurrent requests)
        - Retries failed requests up to 3 times with exponential backoff
        - Logs all API calls for CLV tracking

    See Also:
        fetch_odds_sync: Synchronous version for single game
        track_line_movement: Store fetched odds for CLV calculation
    """
```

---

### 6. Generator Function

```python
def walk_forward_splits(
    df: pd.DataFrame,
    train_size: int,
    test_size: int,
    step_size: int = None
) -> Iterator[tuple[pd.DataFrame, pd.DataFrame]]:
    """Generate train/test splits for walk-forward validation.

    Walk-forward validation simulates realistic betting: train on past data,
    test on future data, never look ahead. Essential for preventing overfitting
    and getting accurate backtest results.

    Args:
        df: DataFrame with datetime index, sorted chronologically.
        train_size: Number of periods for training window.
        test_size: Number of periods for test window.
        step_size: How many periods to move forward each iteration. If None,
            defaults to test_size (no overlap). Defaults to None.

    Yields:
        Tuple of (train_df, test_df) for each split. Train data always comes
        before test data chronologically.

    Raises:
        ValueError: If df is not sorted by date or too small for splits.

    Example:
        >>> import pandas as pd
        >>> df = pd.DataFrame({
        ...     'date': pd.date_range('2020-01-01', periods=100),
        ...     'points': range(100)
        ... }).set_index('date')
        >>>
        >>> for train, test in walk_forward_splits(df, train_size=50, test_size=10):
        ...     print(f"Train: {train.index[0]} to {train.index[-1]}")
        ...     print(f"Test: {test.index[0]} to {test.index[-1]}")
        Train: 2020-01-01 to 2020-02-19
        Test: 2020-02-20 to 2020-02-29
        Train: 2020-01-11 to 2020-03-01
        Test: 2020-03-02 to 2020-03-11
        ...

    Note:
        For sports betting backtests:
        - Use full season as train_size for initial model
        - Use 1-2 weeks as test_size for regular retraining
        - Set step_size=7 for weekly model updates

        Walk-forward is critical because:
        1. Prevents look-ahead bias (can't use future to predict past)
        2. Simulates realistic model deployment
        3. Reveals if model degrades over time

    See Also:
        backtest_strategy: Run full backtest with walk-forward splits
        cross_validation: Alternative validation (not recommended for time series)

    References:
        .. [1] Prado, M. (2018). "Advances in Financial Machine Learning", Ch. 7
        .. [2] ADR-002: Why Walk-Forward Validation
    """
```

---

## Docstring Anti-Patterns

### ❌ Bad: Vague Description

```python
def process_data(data):
    """Processes the data."""
    # What processing? Why? What format? What output?
```

### ✅ Good: Specific Description

```python
def process_data(df: pd.DataFrame) -> pd.DataFrame:
    """Clean game data and add rolling features to prevent data leakage.

    Applies the following transformations:
    1. Remove duplicate games
    2. Fill missing scores with 0 (forfeits)
    3. Add rolling 5-game averages (shifted by 1)

    Args:
        df: Raw game data with columns: game_id, date, team_id, points.

    Returns:
        Cleaned DataFrame with additional rolling_5_avg column.
    """
```

---

### ❌ Bad: No Type Hints

```python
def calculate_ev(prob, odds, stake):
    """Calculate expected value."""
```

### ✅ Good: Type Hints + Example

```python
def calculate_ev(prob: float, odds: int, stake: float) -> float:
    """Calculate expected value of a bet.

    EV = (win_prob × profit) - (lose_prob × stake)

    Args:
        prob: Win probability as decimal (0.0 to 1.0).
        odds: American odds (e.g., -110, +150).
        stake: Bet amount in dollars.

    Returns:
        Expected value in dollars. Positive = profitable bet.

    Example:
        >>> calculate_ev(prob=0.55, odds=-110, stake=100)
        4.09
    """
```

---

### ❌ Bad: No Examples

```python
def kelly_criterion(win_prob, decimal_odds, fraction=0.25):
    """Calculate Kelly criterion bet sizing."""
    # How do I use this? What's the output format?
```

### ✅ Good: Working Example

```python
def kelly_criterion(
    win_prob: float,
    decimal_odds: float,
    fraction: float = 0.25
) -> float:
    """Calculate fractional Kelly bet size as percentage of bankroll.

    Args:
        win_prob: Probability of winning (0.0 to 1.0).
        decimal_odds: Decimal odds (e.g., 1.91, 2.50).
        fraction: Kelly fraction to use. 0.25 = quarter Kelly. Defaults to 0.25.

    Returns:
        Recommended bet size as decimal percentage of bankroll (0.0 to 1.0).
        E.g., 0.03 = bet 3% of bankroll.

    Example:
        >>> kelly_criterion(win_prob=0.55, decimal_odds=1.91, fraction=0.25)
        0.0267
        >>> # This means bet 2.67% of your bankroll
    """
```

---

## Special Cases

### Private Functions (Single Underscore)

Private functions can have shorter docstrings:

```python
def _validate_odds(odds: int) -> None:
    """Validate American odds format.

    Raises:
        ValueError: If odds are invalid.
    """
```

### Properties

```python
@property
def win_rate(self) -> float:
    """Win rate as decimal (0.0 to 1.0).

    Calculated as: wins / total_bets
    Returns NaN if no bets placed yet.
    """
```

### Dataclasses

```python
@dataclass
class BetRecord:
    """Record of a single bet placement.

    Attributes:
        game_id: Unique identifier for the game.
        bet_type: Type of bet ('spread', 'total', 'moneyline').
        selection: What was bet on (team name or 'over'/'under').
        odds: American odds when bet was placed.
        stake: Amount bet in dollars.
        result: Outcome ('win', 'loss', 'push', None if pending).
        clv: Closing line value as percentage (None if game not closed).

    Example:
        >>> bet = BetRecord(
        ...     game_id='ncaab_2026_001',
        ...     bet_type='spread',
        ...     selection='Duke',
        ...     odds=-110,
        ...     stake=100.0,
        ...     result=None,
        ...     clv=None
        ... )
    """
    game_id: str
    bet_type: str
    selection: str
    odds: int
    stake: float
    result: str | None = None
    clv: float | None = None
```

---

## Docstring Checklist

Before committing code, verify:

- [ ] Every public function/class has a docstring
- [ ] One-line summary uses imperative mood ("Calculate", not "Calculates")
- [ ] All parameters documented in Args section
- [ ] Return value documented
- [ ] Type hints match docstring descriptions
- [ ] At least one working example provided
- [ ] Data leakage warnings included (if applicable)
- [ ] Domain context explained (why this matters for betting)
- [ ] Related functions/ADRs linked
- [ ] Raises section lists exceptions
- [ ] No spelling/grammar errors

---

## Tools for Validation

### Check Docstring Coverage

```bash
# Install interrogate
pip install interrogate

# Check coverage
interrogate -v models/

# Require 90% coverage
interrogate --fail-under 90 models/
```

### Validate Docstring Style

```bash
# Install pydocstyle
pip install pydocstyle

# Check style
pydocstyle models/

# Auto-fix some issues
pydocstyle --add-ignore=D100,D104 models/
```

### Test Examples in Docstrings

```bash
# Install pytest-examples
pip install pytest-examples

# Run docstring examples as tests
pytest --examples models/
```

---

## References

- [Google Python Style Guide - Docstrings](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings)
- [PEP 257 - Docstring Conventions](https://peps.python.org/pep-0257/)
- [Sphinx Documentation](https://www.sphinx-doc.org/)
- [NumPy Docstring Guide](https://numpydoc.readthedocs.io/)

---

**Last Updated**: 2026-01-24
**Maintained By**: Documentation Engineer Agent
