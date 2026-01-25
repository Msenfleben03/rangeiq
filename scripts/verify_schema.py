#!/usr/bin/env python3
"""Verify the forecasting schema was created correctly."""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "betting.db"


def main():
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    # Get all tables
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [r[0] for r in cur.fetchall()]

    print("=" * 50)
    print("DATABASE SCHEMA VERIFICATION")
    print("=" * 50)
    print(f"\nDatabase: {DB_PATH}")
    print(f"Total tables: {len(tables)}")
    print("\nTables:")
    for t in tables:
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        count = cur.fetchone()[0]
        print(f"  - {t}: {count} rows")

    # Check for forecasting tables specifically
    forecasting_tables = [
        "forecasts",
        "belief_revisions",
        "reference_classes",
        "calibration_metrics",
        "question_decomposition",
        "pm_positions",
        "forecaster_metrics",
    ]

    print("\nForecasting Schema Status:")
    for ft in forecasting_tables:
        status = "✅" if ft in tables else "❌"
        print(f"  {status} {ft}")

    conn.close()


if __name__ == "__main__":
    main()
