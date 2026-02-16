"""Run Gatekeeper Validation on Backtest Results.

Loads backtest results and runs the full 5-dimension validation pipeline.
The model MUST get GateDecision.PASS before deployment.

Usage:
    python scripts/run_gatekeeper_validation.py
    python scripts/run_gatekeeper_validation.py --backtest data/backtests/ncaab_elo_backtest_2025.parquet
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def load_backtest(path: Path) -> pd.DataFrame:
    """Load backtest results from parquet."""
    if not path.exists():
        raise FileNotFoundError(f"Backtest file not found: {path}")
    df = pd.read_parquet(path)
    logger.info("Loaded backtest: %d bets from %s", len(df), path)
    return df


def prepare_gatekeeper_inputs(df: pd.DataFrame) -> tuple[dict, dict]:
    """Convert backtest DataFrame to Gatekeeper input format.

    Returns:
        Tuple of (backtest_results dict, model_metadata dict).
    """
    backtest_results = {
        "profit_loss": df["profit_loss"].tolist(),
        "stake": df["stake"].tolist(),
        "clv_values": df["clv"].tolist(),
        "game_date": df["date"].tolist() if "date" in df.columns else [],
        "result": df["result"].tolist(),
        "odds_placed": df["odds_placed"].tolist() if "odds_placed" in df.columns else [],
        "model_prob": df["model_prob"].tolist() if "model_prob" in df.columns else [],
        "edge": df["edge"].tolist() if "edge" in df.columns else [],
    }

    # Calculate summary stats for metadata
    # Use flat-stake ROI (mean per-bet return) to isolate model edge quality
    # from Kelly compound growth. Compound ROI inflates the overfit check
    # because bankroll growth amplifies later-season bets.
    per_bet_returns = df["profit_loss"] / df["stake"]
    flat_roi = float(per_bet_returns.mean())

    model_metadata = {
        "n_features": 5,  # Elo + HCA + conference + MOV + games_played
        "n_samples": len(df),
        "in_sample_roi": flat_roi,
        "model_type": "elo",
        "sport": "ncaab",
    }

    return backtest_results, model_metadata


def run_validation(backtest_path: Path, model_name: str = "ncaab_elo_v1") -> dict:
    """Run full Gatekeeper validation.

    Args:
        backtest_path: Path to backtest parquet file.
        model_name: Name for the model being validated.

    Returns:
        Validation report as dict.
    """
    df = load_backtest(backtest_path)
    backtest_results, model_metadata = prepare_gatekeeper_inputs(df)

    try:
        from backtesting.validators.gatekeeper import Gatekeeper

        gk = Gatekeeper()
        gk.load_validators()

        report = gk.generate_report(
            model_name=model_name,
            backtest_results=backtest_results,
            model_metadata=model_metadata,
        )

        # Save report
        output_dir = Path("data/validation")
        output_dir.mkdir(parents=True, exist_ok=True)
        report_path = output_dir / f"{model_name}_gatekeeper_report.json"
        report_dict = report.to_dict()
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report_dict, f, indent=2, default=str)
        logger.info("Report saved to %s", report_path)

        return report_dict

    except ImportError as e:
        logger.warning("Gatekeeper not fully available: %s", e)
        logger.info("Running simplified validation instead...")
        return _simplified_validation(df, model_name)


def _simplified_validation(df: pd.DataFrame, model_name: str) -> dict:
    """Simplified validation when full Gatekeeper is unavailable.

    Checks the key blocking thresholds directly.
    """
    total_bets = len(df)
    total_staked = df["stake"].sum()
    total_pnl = df["profit_loss"].sum()
    roi = total_pnl / total_staked if total_staked > 0 else 0
    avg_clv = df["clv"].mean()
    win_rate = (df["result"] == "win").mean()

    # Sharpe
    import numpy as np

    daily_pnl = df.groupby(pd.to_datetime(df["date"]).dt.date)["profit_loss"].sum()
    sharpe = (
        (daily_pnl.mean() / daily_pnl.std()) * np.sqrt(150)
        if len(daily_pnl) > 1 and daily_pnl.std() > 0
        else 0.0
    )

    checks = {
        "sample_size_adequate": {
            "passed": total_bets >= 200,
            "value": total_bets,
            "threshold": 200,
        },
        "sharpe_adequate": {"passed": sharpe >= 0.5, "value": round(sharpe, 3), "threshold": 0.5},
        "roi_not_suspicious": {"passed": roi <= 0.15, "value": round(roi, 4), "threshold": 0.15},
        "clv_positive": {
            "passed": avg_clv >= 0.015,
            "value": round(avg_clv, 4),
            "threshold": 0.015,
        },
    }

    all_passed = all(c["passed"] for c in checks.values())
    decision = "PASS" if all_passed else "QUARANTINE"
    blocking = [k for k, v in checks.items() if not v["passed"]]

    report = {
        "model_name": model_name,
        "decision": decision,
        "mode": "simplified",
        "blocking_failures": blocking,
        "checks": checks,
        "summary": {
            "total_bets": total_bets,
            "win_rate": round(win_rate, 4),
            "roi": round(roi, 4),
            "avg_clv": round(avg_clv, 4),
            "sharpe": round(sharpe, 3),
        },
    }

    # Save
    output_dir = Path("data/validation")
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"{model_name}_gatekeeper_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    logger.info("Simplified report saved to %s", report_path)

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Gatekeeper validation")
    parser.add_argument(
        "--backtest",
        type=str,
        default="data/backtests/ncaab_elo_backtest_2025.parquet",
        help="Path to backtest parquet file",
    )
    parser.add_argument(
        "--model-name",
        type=str,
        default="ncaab_elo_v1",
        help="Model name for the report",
    )
    args = parser.parse_args()

    backtest_path = Path(args.backtest)
    report = run_validation(backtest_path, args.model_name)

    decision = report.get("decision", "UNKNOWN")
    blocking = report.get("blocking_failures", [])

    print(f"\n{'=' * 60}")
    print(f"GATEKEEPER DECISION: {decision}")
    print(f"{'=' * 60}")

    if decision == "PASS":
        print("Model approved for deployment!")
    elif decision == "QUARANTINE":
        print(f"Model quarantined. Blocking failures: {blocking}")
    else:
        print(f"Decision: {decision}")

    if "checks" in report:
        print(f"\n{'=' * 60}")
        print("DETAILED CHECKS")
        print(f"{'=' * 60}")
        for check_name, check_data in report["checks"].items():
            status = "PASS" if check_data["passed"] else "FAIL"
            print(
                f"  [{status}] {check_name}: {check_data['value']} "
                f"(threshold: {check_data['threshold']})"
            )

    if "summary" in report:
        summary = report["summary"]
        print(f"\nSummary: {summary}")


if __name__ == "__main__":
    main()
