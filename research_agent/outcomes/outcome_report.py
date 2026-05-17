from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional, Union

import pandas as pd
from pydantic import BaseModel, Field

from research_agent.outcomes.action_evaluator import ActionEvaluation, evaluate_action_policy
from research_agent.outcomes.benchmark_outcome import (
    BenchmarkOutcome,
    calculate_benchmark_outcome,
    default_benchmark_for_tags,
)
from research_agent.outcomes.price_outcome import (
    PriceOutcomeReport,
    WindowOutcome,
    calculate_forward_return,
    calculate_price_outcomes,
)
from research_agent.outcomes.rating_evaluator import RatingEvaluation, evaluate_rating
from research_agent.outcomes.report_manifest import ReportManifest, load_report_manifest


class OutcomeReviewReport(BaseModel):
    report_id: str
    ticker: str
    rating: str
    price_outcomes: PriceOutcomeReport
    benchmark_outcomes: dict[str, BenchmarkOutcome] = Field(default_factory=dict)
    rating_evaluation_60d: Optional[RatingEvaluation] = None
    action_evaluation_60d: Optional[ActionEvaluation] = None

    @property
    def rating_success_60d(self) -> Optional[bool]:
        return self.rating_evaluation_60d.success if self.rating_evaluation_60d else None

    @property
    def action_success(self) -> Optional[bool]:
        return self.action_evaluation_60d.success if self.action_evaluation_60d else None


def build_outcome_report(
    manifest: ReportManifest,
    price_history: pd.DataFrame,
    benchmark_history: Optional[pd.DataFrame] = None,
    benchmark_ticker: Optional[str] = None,
    stop_loss: Optional[float] = None,
    target: Optional[float] = None,
    action_policy: Optional[dict[str, object]] = None,
) -> OutcomeReviewReport:
    price_outcomes = calculate_price_outcomes(
        manifest=manifest,
        price_history=price_history,
        stop_loss=stop_loss,
        target=target,
    )
    benchmark_outcomes = _calculate_benchmark_outcomes(
        manifest=manifest,
        price_outcomes=price_outcomes,
        benchmark_history=benchmark_history,
        benchmark_ticker=benchmark_ticker,
    )
    benchmark_60d = benchmark_outcomes.get("60d")
    rating_evaluation = evaluate_rating(
        rating=manifest.final_rating,
        outcome_20d=price_outcomes.outcomes.get("20d"),
        outcome_60d=price_outcomes.outcomes.get("60d"),
        benchmark_60d=benchmark_60d,
    )
    outcome_60d = price_outcomes.outcomes.get("60d")
    action_evaluation = (
        evaluate_action_policy(action_policy, outcome_60d)
        if action_policy and outcome_60d
        else None
    )
    return OutcomeReviewReport(
        report_id=manifest.report_id,
        ticker=manifest.ticker,
        rating=manifest.final_rating,
        price_outcomes=price_outcomes,
        benchmark_outcomes=benchmark_outcomes,
        rating_evaluation_60d=rating_evaluation,
        action_evaluation_60d=action_evaluation,
    )


def save_outcome_report(report: OutcomeReviewReport, path: Union[str, Path]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = report.model_dump(mode="json") if hasattr(report, "model_dump") else report.dict()
    target.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return target


def _calculate_benchmark_outcomes(
    manifest: ReportManifest,
    price_outcomes: PriceOutcomeReport,
    benchmark_history: Optional[pd.DataFrame],
    benchmark_ticker: Optional[str],
) -> dict[str, BenchmarkOutcome]:
    if benchmark_history is None:
        return {}

    benchmark_ticker = benchmark_ticker or default_benchmark_for_tags(manifest.tags)
    basis_price = _last_close_on_or_before(benchmark_history, manifest.price_basis_date)
    if basis_price is None:
        return {}

    benchmark_manifest = manifest.model_copy(update={
        "ticker": benchmark_ticker,
        "price_basis_close": basis_price,
    }) if hasattr(manifest, "model_copy") else manifest.copy(update={
        "ticker": benchmark_ticker,
        "price_basis_close": basis_price,
    })
    benchmark_price_outcomes = calculate_price_outcomes(benchmark_manifest, benchmark_history)

    outcomes: dict[str, BenchmarkOutcome] = {}
    for window, stock_outcome in price_outcomes.outcomes.items():
        benchmark_outcome = benchmark_price_outcomes.outcomes.get(window)
        if stock_outcome.return_pct is None or benchmark_outcome is None or benchmark_outcome.return_pct is None:
            continue
        outcomes[window] = calculate_benchmark_outcome(
            benchmark_ticker=benchmark_ticker,
            stock_return_pct=stock_outcome.return_pct,
            benchmark_return_pct=benchmark_outcome.return_pct,
        )
    return outcomes


def _last_close_on_or_before(price_history: pd.DataFrame, basis_date: str) -> Optional[float]:
    df = price_history.copy()
    df.columns = [str(column).strip().lower() for column in df.columns]
    if "date" not in df.columns or "close" not in df.columns:
        raise ValueError("benchmark history requires date and close columns.")
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    basis = pd.to_datetime(basis_date).date()
    eligible = df[df["date"] <= basis].sort_values("date")
    if eligible.empty:
        return None
    return float(eligible.iloc[-1]["close"])


def _load_csv(path: Union[str, Path]) -> pd.DataFrame:
    return pd.read_csv(path)


def _json_default(obj):
    if isinstance(obj, WindowOutcome):
        return obj.model_dump(mode="json") if hasattr(obj, "model_dump") else obj.dict()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate a research report manifest against future price outcomes.")
    parser.add_argument("--manifest", required=True, help="Path to report_manifest.json")
    parser.add_argument("--prices", required=True, help="CSV with stock date/open/high/low/close data")
    parser.add_argument("--benchmark", help="Optional benchmark CSV with date/open/high/low/close data")
    parser.add_argument("--benchmark-ticker", help="Benchmark ticker override")
    parser.add_argument("--stop-loss", type=float, help="Optional stop-loss level")
    parser.add_argument("--target", type=float, help="Optional target level")
    parser.add_argument("--output", help="Optional output JSON path")
    args = parser.parse_args(argv)

    manifest = load_report_manifest(args.manifest)
    price_history = _load_csv(args.prices)
    benchmark_history = _load_csv(args.benchmark) if args.benchmark else None
    report = build_outcome_report(
        manifest=manifest,
        price_history=price_history,
        benchmark_history=benchmark_history,
        benchmark_ticker=args.benchmark_ticker,
        stop_loss=args.stop_loss,
        target=args.target,
    )
    payload = report.model_dump(mode="json") if hasattr(report, "model_dump") else report.dict()
    if args.output:
        save_outcome_report(report, args.output)
    print(json.dumps(payload, indent=2, sort_keys=True, default=_json_default))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
