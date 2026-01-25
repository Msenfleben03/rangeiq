"""
SQLAlchemy ORM Models for Sports Betting Database

Mirrors the schema defined in scripts/init_database.sql
All timestamps stored in UTC (per ADR-012)
"""

from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


# =============================================================================
# CORE TABLES
# =============================================================================


class Team(Base):
    """Teams reference table."""

    __tablename__ = "teams"

    team_id = Column(String, primary_key=True)
    sport = Column(String, nullable=False)  # 'NCAAB', 'MLB', 'NFL', 'NCAAF'
    team_name = Column(String, nullable=False)
    team_abbrev = Column(String)
    conference = Column(String)
    division = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    home_games = relationship("Game", foreign_keys="Game.home_team_id", back_populates="home_team")
    away_games = relationship("Game", foreign_keys="Game.away_team_id", back_populates="away_team")
    ratings = relationship("TeamRating", back_populates="team")

    def __repr__(self):
        return f"<Team(team_id='{self.team_id}', name='{self.team_name}', sport='{self.sport}')>"


class Game(Base):
    """Games table - central fact table for all matchups."""

    __tablename__ = "games"

    game_id = Column(String, primary_key=True)
    sport = Column(String, nullable=False)
    season = Column(Integer, nullable=False)
    game_date = Column(Date, nullable=False)
    game_time = Column(DateTime)  # UTC

    # Teams
    home_team_id = Column(String, ForeignKey("teams.team_id"), nullable=False)
    away_team_id = Column(String, ForeignKey("teams.team_id"), nullable=False)

    # Location
    venue = Column(String)
    is_neutral_site = Column(Boolean, default=False)

    # Game type
    is_postseason = Column(Boolean, default=False)
    game_type = Column(String)  # 'regular', 'conference_tourney', 'ncaa_tourney', etc.

    # Results (filled after game)
    home_score = Column(Integer)
    away_score = Column(Integer)
    is_final = Column(Boolean, default=False)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    home_team = relationship("Team", foreign_keys=[home_team_id], back_populates="home_games")
    away_team = relationship("Team", foreign_keys=[away_team_id], back_populates="away_games")
    odds_snapshots = relationship("OddsSnapshot", back_populates="game")
    predictions = relationship("Prediction", back_populates="game")
    bets = relationship("Bet", back_populates="game")
    features = relationship("Feature", back_populates="game")
    player_props = relationship("PlayerProp", back_populates="game")

    @property
    def home_margin(self) -> Optional[int]:
        """Calculate home team margin (positive = home win)."""
        if self.home_score is not None and self.away_score is not None:
            return self.home_score - self.away_score
        return None

    @property
    def total_points(self) -> Optional[int]:
        """Calculate total points scored."""
        if self.home_score is not None and self.away_score is not None:
            return self.home_score + self.away_score
        return None

    def __repr__(self):
        return f"<Game(game_id='{self.game_id}', {self.away_team_id}@{self.home_team_id}, {self.game_date})>"


# =============================================================================
# BETTING LINES
# =============================================================================


class OddsSnapshot(Base):
    """Odds snapshots - track line movements over time."""

    __tablename__ = "odds_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(String, ForeignKey("games.game_id"), nullable=False)
    sportsbook = Column(String, nullable=False)
    captured_at = Column(DateTime, nullable=False)

    # Spread
    spread_home = Column(Float)
    spread_home_odds = Column(Integer)  # American odds
    spread_away_odds = Column(Integer)

    # Total
    total = Column(Float)
    over_odds = Column(Integer)
    under_odds = Column(Integer)

    # Moneyline
    moneyline_home = Column(Integer)
    moneyline_away = Column(Integer)

    # Is this the closing line?
    is_closing = Column(Boolean, default=False)

    # Relationship
    game = relationship("Game", back_populates="odds_snapshots")

    def __repr__(self):
        return f"<OddsSnapshot(game_id='{self.game_id}', book='{self.sportsbook}', spread={self.spread_home})>"


# =============================================================================
# TEAM RATINGS
# =============================================================================


class TeamRating(Base):
    """Team ratings over time - Elo, efficiency, etc."""

    __tablename__ = "team_ratings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    team_id = Column(String, ForeignKey("teams.team_id"), nullable=False)
    sport = Column(String, nullable=False)
    season = Column(Integer, nullable=False)

    # Rating details
    rating_type = Column(String, nullable=False)  # 'elo', 'efficiency_off', etc.
    rating_value = Column(Float, nullable=False)

    # When this rating was calculated
    as_of_date = Column(Date, nullable=False)
    as_of_game_id = Column(String, ForeignKey("games.game_id"))

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    team = relationship("Team", back_populates="ratings")

    __table_args__ = (UniqueConstraint("team_id", "season", "rating_type", "as_of_date"),)

    def __repr__(self):
        return f"<TeamRating(team='{self.team_id}', type='{self.rating_type}', value={self.rating_value})>"


# =============================================================================
# MODEL PREDICTIONS
# =============================================================================


class Prediction(Base):
    """Model predictions for games."""

    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(String, ForeignKey("games.game_id"), nullable=False)
    model_name = Column(String, nullable=False)
    model_version = Column(String, nullable=False)

    # Prediction details
    prediction_type = Column(String, nullable=False)  # 'spread', 'total', 'moneyline', etc.
    predicted_value = Column(Float, nullable=False)
    confidence = Column(Float)  # 0-1, if available

    # Market comparison (at time of prediction)
    market_value = Column(Float)
    market_timestamp = Column(DateTime)

    # For tracking
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship
    game = relationship("Game", back_populates="predictions")

    __table_args__ = (
        UniqueConstraint("game_id", "model_name", "model_version", "prediction_type"),
    )

    def __repr__(self):
        return f"<Prediction(game='{self.game_id}', model='{self.model_name}', pred={self.predicted_value})>"


# =============================================================================
# BETS TRACKING
# =============================================================================


class Bet(Base):
    """Individual bets tracking - core table for P&L."""

    __tablename__ = "bets"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Identification
    bet_uuid = Column(String, unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    game_id = Column(String, ForeignKey("games.game_id"))
    sport = Column(String, nullable=False)

    # Bet details
    bet_type = Column(String, nullable=False)  # 'spread', 'total', 'moneyline', 'prop', etc.
    selection = Column(String, nullable=False)  # 'home', 'away', 'over', 'under', player name
    line = Column(Float)  # Spread or total number (NULL for ML)

    # Odds
    odds_placed = Column(Integer, nullable=False)  # American odds when bet was placed
    odds_closing = Column(Integer)  # American odds at close (filled later)

    # Model data
    model_name = Column(String)
    model_version = Column(String)
    model_probability = Column(Float)  # Our estimated win probability
    model_edge = Column(Float)  # model_prob - implied_prob

    # Sizing
    kelly_recommended = Column(Float)  # What Kelly suggested
    stake = Column(Float, nullable=False)  # What we actually bet
    potential_profit = Column(Float)  # Stake * (decimal_odds - 1)

    # Execution
    sportsbook = Column(String, nullable=False)
    placed_at = Column(DateTime, nullable=False)

    # Results (filled after game)
    result = Column(String)  # 'win', 'loss', 'push', 'void'
    actual_profit_loss = Column(Float)
    clv = Column(Float)  # Closing line value
    settled_at = Column(DateTime)

    # Categorization
    is_live = Column(Boolean, default=False)  # FALSE = paper bet, TRUE = real money
    is_settled = Column(Boolean, default=False)

    # Notes
    notes = Column(Text)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    game = relationship("Game", back_populates="bets")

    def __repr__(self):
        return f"<Bet(id={self.id}, {self.bet_type} {self.selection} @ {self.odds_placed})>"


# =============================================================================
# BANKROLL TRACKING
# =============================================================================


class BankrollDaily(Base):
    """Daily bankroll snapshots."""

    __tablename__ = "bankroll_daily"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, unique=True)

    # Balances
    starting_balance = Column(Float, nullable=False)
    ending_balance = Column(Float, nullable=False)

    # Daily activity
    deposits = Column(Float, default=0)
    withdrawals = Column(Float, default=0)

    # Betting activity
    total_staked = Column(Float, default=0)
    total_returned = Column(Float, default=0)
    net_profit_loss = Column(Float, default=0)

    # Bet counts
    bets_placed = Column(Integer, default=0)
    bets_settled = Column(Integer, default=0)
    bets_won = Column(Integer, default=0)
    bets_lost = Column(Integer, default=0)
    bets_pushed = Column(Integer, default=0)

    # Performance metrics
    win_rate = Column(Float)
    roi = Column(Float)
    avg_clv = Column(Float)

    # Metadata
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<BankrollDaily(date={self.date}, balance=${self.ending_balance:.2f})>"


class SportsbookBalance(Base):
    """Per-sportsbook balance tracking."""

    __tablename__ = "sportsbook_balances"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    sportsbook = Column(String, nullable=False)
    balance = Column(Float, nullable=False)

    # Activity
    deposits = Column(Float, default=0)
    withdrawals = Column(Float, default=0)
    bonuses = Column(Float, default=0)

    # Status
    is_limited = Column(Boolean, default=False)
    limit_notes = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("date", "sportsbook"),)

    def __repr__(self):
        return (
            f"<SportsbookBalance(date={self.date}, book='{self.sportsbook}', ${self.balance:.2f})>"
        )


# =============================================================================
# MODEL METADATA
# =============================================================================


class Model(Base):
    """Model registry - track model versions and performance."""

    __tablename__ = "models"

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_name = Column(String, nullable=False)
    model_version = Column(String, nullable=False)
    sport = Column(String, nullable=False)

    # Description
    description = Column(Text)
    model_type = Column(String)  # 'elo', 'regression', 'ensemble', etc.

    # Configuration (JSON)
    config_json = Column(Text)

    # Backtest results
    backtest_start_date = Column(Date)
    backtest_end_date = Column(Date)
    backtest_n_bets = Column(Integer)
    backtest_clv = Column(Float)
    backtest_roi = Column(Float)

    # Status
    status = Column(String, default="development")  # 'development', 'paper', 'live', 'retired'
    deployed_at = Column(DateTime)
    retired_at = Column(DateTime)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (UniqueConstraint("model_name", "model_version"),)

    def __repr__(self):
        return f"<Model(name='{self.model_name}', version='{self.model_version}', status='{self.status}')>"


# =============================================================================
# FEATURES STORE
# =============================================================================


class Feature(Base):
    """Engineered features for games."""

    __tablename__ = "features"

    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(String, ForeignKey("games.game_id"), nullable=False)
    feature_set_version = Column(String, nullable=False)

    # Store features as JSON for flexibility
    features_json = Column(Text, nullable=False)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship
    game = relationship("Game", back_populates="features")

    __table_args__ = (UniqueConstraint("game_id", "feature_set_version"),)


# =============================================================================
# PLAYER PROPS
# =============================================================================


class PlayerProp(Base):
    """Player prop bets tracking."""

    __tablename__ = "player_props"

    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(String, ForeignKey("games.game_id"), nullable=False)
    player_name = Column(String, nullable=False)
    player_team = Column(String)

    # Prop details
    prop_type = Column(String, nullable=False)  # 'strikeouts', 'hits', 'passing_yards', etc.
    line = Column(Float, nullable=False)

    # Odds
    over_odds = Column(Integer)
    under_odds = Column(Integer)

    # Our prediction
    model_prediction = Column(Float)
    over_probability = Column(Float)
    under_probability = Column(Float)

    # Result
    actual_value = Column(Float)

    # Metadata
    captured_at = Column(DateTime, default=datetime.utcnow)
    is_closing = Column(Boolean, default=False)

    # Relationship
    game = relationship("Game", back_populates="player_props")

    def __repr__(self):
        return (
            f"<PlayerProp(player='{self.player_name}', prop='{self.prop_type}', line={self.line})>"
        )


# =============================================================================
# AUDIT LOG
# =============================================================================


class AuditLog(Base):
    """Audit trail for important changes."""

    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    table_name = Column(String, nullable=False)
    record_id = Column(String, nullable=False)
    action = Column(String, nullable=False)  # 'INSERT', 'UPDATE', 'DELETE'
    old_values = Column(Text)  # JSON
    new_values = Column(Text)  # JSON
    created_at = Column(DateTime, default=datetime.utcnow)


# =============================================================================
# SCHEMA VERSION
# =============================================================================


class SchemaVersion(Base):
    """Track database schema versions."""

    __tablename__ = "schema_version"

    version = Column(Integer, primary_key=True)
    applied_at = Column(DateTime, default=datetime.utcnow)
    description = Column(Text)
