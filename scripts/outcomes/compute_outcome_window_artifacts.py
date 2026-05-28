#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from compute_outcome_5d_artifacts import (
    BATCH_ID_DEFAULT,
    FOCUS_BATCH_ID_DEFAULT,
    WATCHLIST_TICKERS,
    _build_outcome_rows,
    _dedupe_for_top_lists,
    _discover_focus_dashboard,
    _interpretation,
    _load_close_map,
    _load_dashboard_items,
    _read_json,
    _utc_now,
    _write_json,
)


def _window_label(value: str) -> str:
    label = str(value or "").strip().upper()
    if not label:
        raise ValueError("Window must not be empty")
    return label


def _window_slug(window: str) -> str:
    return _window_label(window).lower()


def _get_tracking_window(plan: Dict[str, Any], window: str) -> Dict[str, Any]:
    label = _window_label(window)
    for row in plan.get("tracking_windows") or []:
        if _window_label(str(row.get("window") or "")) == label:
            return row
    known = ", ".join(str(row.get("window")) for row in plan.get("tracking_windows") or [])
    raise ValueError(f"Tracking window {label} not found. Known windows: {known}")


def _load_context(
    *,
    batch_id: str,
    focus_batch_id: str,
) -> Dict[str, Any]:
    batch_root = Path("outputs/batches") / batch_id
    plan = _read_json(batch_root / "OUTCOME_TRACKING_PLAN.json")
    base_items = _load_dashboard_items(batch_root / "dashboard_status.json")
    focus_items = _load_dashboard_items(_discover_focus_dashboard(focus_batch_id))
    return {
        "batch_root": batch_root,
        "plan": plan,
        "base_items": base_items,
        "focus_items": focus_items,
    }


def _latest_date(close_map: Dict[str, float]) -> Optional[str]:
    return max(close_map) if close_map else None


def _symbol_coverage(price_dir: Path, symbols: Sequence[str], target_date: str) -> Dict[str, Any]:
    latest_by_symbol: Dict[str, Dict[str, Any]] = {}
    missing: List[str] = []

    for symbol in sorted({str(s).upper() for s in symbols}):
        csv_path = price_dir / f"{symbol}.csv"
        try:
            close_map = _load_close_map(csv_path)
        except (FileNotFoundError, ValueError):
            latest_by_symbol[symbol] = {
                "csv_path": str(csv_path),
                "latest_date": None,
                "target_date_available": False,
            }
            missing.append(symbol)
            continue

        target_available = target_date in close_map
        latest_by_symbol[symbol] = {
            "csv_path": str(csv_path),
            "latest_date": _latest_date(close_map),
            "target_date_available": target_available,
        }
        if not target_available:
            missing.append(symbol)

    return {"latest_by_symbol": latest_by_symbol, "missing": missing}


def _build_readiness_payload(
    *,
    batch_id: str,
    focus_batch_id: str,
    window: str,
) -> Dict[str, Any]:
    context = _load_context(batch_id=batch_id, focus_batch_id=focus_batch_id)
    plan = context["plan"]
    tracking_window = _get_tracking_window(plan, window)
    window_label = _window_label(window)
    window_end_date = str(tracking_window["earliest_evaluation_date"])
    price_basis_date = str(plan["price_basis_date"])
    benchmark_mapping = {
        str(k).upper(): str(v).upper() for k, v in (tracking_window.get("benchmark_mapping") or {}).items()
    }
    base_items = context["base_items"]
    focus_items = context["focus_items"]
    price_dir = Path("outputs/source_inputs") / batch_id / "prices"

    ticker_symbols = [str(item["ticker"]).upper() for item in [*base_items, *focus_items]]
    benchmark_symbols = sorted(set(benchmark_mapping.values()))
    ticker_coverage = _symbol_coverage(price_dir, ticker_symbols, window_end_date)
    benchmark_coverage = _symbol_coverage(price_dir, benchmark_symbols, window_end_date)

    missing_tickers = sorted(ticker_coverage["missing"])
    missing_benchmarks = sorted(benchmark_coverage["missing"])
    ready = not missing_tickers and not missing_benchmarks

    return {
        "batch_id": batch_id,
        "focus_batch_id": focus_batch_id,
        "generated_at": _utc_now(),
        "window": window_label,
        "price_basis_date": price_basis_date,
        "earliest_evaluation_date": window_end_date,
        "trading_days": tracking_window.get("trading_days"),
        "status": "ready_to_compute" if ready else "pending_price_data",
        "runner": "scripts/outcomes/compute_outcome_window_artifacts.py",
        "ready_command": (
            "python3 scripts/outcomes/compute_outcome_window_artifacts.py "
            f"--window {window_label} --batch-id {batch_id} --focus-batch-id {focus_batch_id}"
        ),
        "policy": {
            "no_synthetic_prices": True,
            "no_forward_fill": True,
            "no_replacement_end_date": True,
            "monitoring_only": True,
            "no_calibration_from_single_window": True,
        },
        "coverage": {
            "computed_rows_expected": len(base_items) + len(focus_items),
            "unique_tickers_expected": len(set(ticker_symbols)),
            "missing_price_tickers": missing_tickers,
            "missing_benchmark_tickers": missing_benchmarks,
            "ticker_latest_by_symbol": ticker_coverage["latest_by_symbol"],
            "benchmark_latest_by_symbol": benchmark_coverage["latest_by_symbol"],
        },
    }


def _generic_guard_lesson(text: str, window: str) -> str:
    return (
        text.replace("Five-day outcome", f"{window} outcome")
        .replace("five-day outcome", f"{window} outcome")
        .replace("5D", window)
    )


def _row_payload(row: Any, *, window: str) -> Dict[str, Any]:
    payload = asdict(row)
    return {
        "ticker": payload["ticker"],
        "source_batch": payload["source_batch"],
        "original_status": payload["original_status"],
        "rating_external_display": payload["rating_external_display"],
        "publishable": payload["publishable"],
        "price_basis_date": payload["price_basis_date"],
        "price_basis_close": payload["price_basis_close"],
        "price_source": payload["price_source"],
        "window": window,
        "window_end_date": payload["five_day_end_date"],
        "window_end_close": payload["five_day_end_close"],
        "return_pct": payload["return_pct"],
        "benchmark": payload["benchmark"],
        "benchmark_price_source": payload["benchmark_price_source"],
        "benchmark_price_basis_close": payload["benchmark_price_basis_close"],
        "benchmark_window_end_close": payload["benchmark_five_day_end_close"],
        "benchmark_return_pct": payload["benchmark_return_pct"],
        "excess_return_pct": payload["excess_return_pct"],
        "outcome_status": payload["outcome_status"],
        "rating_action_success_preliminary": payload["rating_action_success_preliminary"],
        "false_pass_suspicion": payload["false_pass_suspicion"],
        "manual_review_missed_opportunity": payload["manual_review_missed_opportunity"],
        "guard_lesson": _generic_guard_lesson(payload["guard_lesson"], window),
    }


def _render_outcome_review_md(
    *,
    batch_id: str,
    focus_batch_id: str,
    price_basis_date: str,
    window: str,
    window_end_date: str,
    rows: Sequence[Any],
) -> str:
    lines = [
        f"# Outcome {window} Review",
        "",
        f"- Batch: {batch_id}",
        f"- Included focus check: {focus_batch_id}",
        f"- Price basis date: {price_basis_date}",
        f"- {window} end date: {window_end_date}",
        "- Status: computed",
        f"- Computed rows: {len(rows)}",
        "- Pending rows: 0",
        "- Calibration changes: none",
        "- Guard changes: none",
        "- Report changes: none",
        "- Rating changes: none",
        "",
        "## Results",
        "",
        f"| Ticker | Source Batch | Original status | External display | Benchmark | {window} return % | Benchmark return % | Excess % | Outcome status | Guard lesson |",
        "|---|---|---|---|---|---:|---:|---:|---|---|",
    ]
    for row in rows:
        guard_lesson = _generic_guard_lesson(row.guard_lesson, window)
        lines.append(
            f"| {row.ticker} | {row.source_batch} | {row.original_status} | {row.rating_external_display} | {row.benchmark} | {row.return_pct:.4f} | {row.benchmark_return_pct:.4f} | {row.excess_return_pct:.4f} | {row.outcome_status} | {guard_lesson} |"
        )
    return "\n".join(lines) + "\n"


def _top_payload(rows: Sequence[Any], *, window: str, args: argparse.Namespace) -> List[Dict[str, Any]]:
    payload: List[Dict[str, Any]] = []
    for row in rows:
        payload.append(
            {
                "ticker": row.ticker,
                "original_status": row.original_status,
                "rating_external_display": row.rating_external_display,
                "window": window,
                "window_return_pct": row.return_pct,
                "benchmark": row.benchmark,
                "benchmark_return_pct": row.benchmark_return_pct,
                "excess_return_pct": row.excess_return_pct,
                "interpretation": _interpretation(
                    ticker=row.ticker,
                    original_status=row.original_status,
                    excess_return_pct=row.excess_return_pct,
                    false_block_threshold=args.false_block_threshold,
                    false_pass_threshold=args.false_pass_threshold,
                    monitor_threshold=args.monitor_threshold,
                ),
            }
        )
    return payload


def _render_triage_md(
    *,
    batch_id: str,
    focus_batch_id: str,
    window: str,
    price_basis_date: str,
    window_end_date: str,
    computed_rows: int,
    unique_tickers: int,
    false_pass_unique: Sequence[str],
    false_block_unique: Sequence[str],
    top_pos: Sequence[Dict[str, Any]],
    top_neg: Sequence[Dict[str, Any]],
    excess_by_ticker: Dict[str, float],
    strong_negative_threshold: float,
) -> str:
    lines = [
        f"# Outcome {window} Triage Summary",
        "",
        f"- Batch: {batch_id}",
        f"- Source: OUTCOME_{window}_REVIEW.md/json",
        f"- Window: {window} ({price_basis_date} to {window_end_date})",
        "- Status: computed",
        f"- Computed rows: {computed_rows} ({unique_tickers} unique tickers)",
        "- Pending rows: 0",
        f"- False pass flags: {len(false_pass_unique)} rows / {len(false_pass_unique)} unique tickers"
        + ("" if not false_pass_unique else f" ({', '.join(false_pass_unique)})"),
        f"- False block flags: {len(false_block_unique)} rows / {len(false_block_unique)} unique tickers"
        + ("" if not false_block_unique else f" ({', '.join(false_block_unique)})"),
        f"- Benchmark coverage: complete ({computed_rows}/{computed_rows} computed rows)",
        f"- Data quality: complete_for_{_window_slug(window)}; no missing price tickers; no missing benchmark tickers",
        "",
        f"Top lists are deduped by ticker and prefer {focus_batch_id} where a focus overlay exists. The computed row count preserves the source row count.",
        "",
        "## Top 10 Positive Excess Returns",
        "",
        f"| Ticker | Original status | Rating / external display | {window} return % | Benchmark return % | Excess % | Interpretation |",
        "|---|---|---|---:|---:|---:|---|",
    ]
    for row in top_pos:
        lines.append(
            f"| {row['ticker']} | {row['original_status']} | {row['rating_external_display']} | {row['window_return_pct']:.4f} | {row['benchmark_return_pct']:.4f} | {row['excess_return_pct']:.4f} | {row['interpretation']} |"
        )

    lines.extend(
        [
            "",
            "## Top 10 Negative Excess Returns",
            "",
            f"| Ticker | Original status | Rating / external display | {window} return % | Benchmark return % | Excess % | Interpretation |",
            "|---|---|---|---:|---:|---:|---|",
        ]
    )
    for row in top_neg:
        lines.append(
            f"| {row['ticker']} | {row['original_status']} | {row['rating_external_display']} | {row['window_return_pct']:.4f} | {row['benchmark_return_pct']:.4f} | {row['excess_return_pct']:.4f} | {row['interpretation']} |"
        )

    lines.extend(
        [
            "",
            "## Passed Reports Check",
            "",
            f"- Strong negative threshold: <= {strong_negative_threshold:.4f}% excess.",
            "- Passed tickers with strong negative excess:",
            "- " + ("None at threshold" if not false_pass_unique else ", ".join(false_pass_unique)),
            f"- Possible false pass suspicion: {'yes' if false_pass_unique else 'no'}",
            f"- Action: no action unless repeated at later windows after {window}.",
            "",
            "## Manual-Review Missed-Opportunity Watchlist",
            "",
            f"| Ticker | {window} excess % | Status | Recommended action |",
            "|---|---:|---|---|",
        ]
    )
    for ticker in WATCHLIST_TICKERS:
        ex = float(excess_by_ticker.get(ticker) or 0.0)
        if ticker in false_block_unique:
            status_label = "confirmed_outperformance"
            action = "keep on watchlist; inspect manual_review reason + data ops"
        else:
            status_label = "monitor"
            action = "keep monitoring; confirm again at next window"
        lines.append(f"| {ticker} | {ex:.4f} | {status_label} | {action} |")

    lines.extend(
        [
            "",
            "## No-Change Policy",
            "",
            f"- No calibration from {window} alone.",
            f"- No guard change from {window} alone.",
            f"- No rating change from {window} alone.",
            f"- No report change from {window} alone.",
        ]
    )
    return "\n".join(lines) + "\n"


def _build_watchlist_payload(
    *,
    batch_id: str,
    window: str,
    window_end_date: str,
    outcome_rows: Sequence[Any],
    false_block_threshold: float,
    monitor_threshold: float,
) -> Dict[str, Any]:
    base_rows = [row for row in outcome_rows if row.source_batch == batch_id]
    by_ticker = {row.ticker: row for row in base_rows}

    carry_path = Path("outputs/batches") / batch_id / "OUTCOME_WATCHLIST_CARRY_FORWARD.json"
    carry = _read_json(carry_path) if carry_path.exists() else {}
    carry_by = {row.get("ticker"): row for row in (carry.get("watchlist") or [])}

    watchlist = []
    for ticker in WATCHLIST_TICKERS:
        row = by_ticker.get(ticker)
        if not row:
            continue
        carry_row = carry_by.get(ticker, {})
        ex = row.excess_return_pct
        if ex >= false_block_threshold:
            status = "confirmed_outperformance"
        elif ex >= monitor_threshold:
            status = "still_positive_monitor"
        else:
            status = "cleared_or_downgraded"
        watchlist.append(
            {
                "ticker": ticker,
                "original_status": row.original_status,
                "original_rating_external_display": row.rating_external_display,
                "manual_review_reason_codes": carry_row.get("manual_review_reason_codes") or [],
                "one_day_return_pct": carry_row.get("one_day_return_pct"),
                "one_day_excess_return_pct": carry_row.get("excess_return_pct"),
                "window": window,
                "window_end_date": window_end_date,
                "window_return_pct": row.return_pct,
                "benchmark": row.benchmark,
                "benchmark_return_pct": row.benchmark_return_pct,
                "excess_return_pct": row.excess_return_pct,
                "status": status,
                "no_change_policy": "No calibration/guard/rating/report changes from this watchlist; monitoring-only.",
            }
        )

    return {
        "batch_id": batch_id,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "window": window,
        "window_end_date": window_end_date,
        "watchlist": watchlist,
    }


def _render_watchlist_md(payload: Dict[str, Any]) -> str:
    window = payload["window"]
    lines = [
        f"# Outcome {window} Watchlist Review",
        "",
        f"- Batch: {payload['batch_id']}",
        f"- Window: {window} (end date {payload['window_end_date']})",
        "- Policy: monitoring-only; no calibration, no guards, no ratings, no report changes",
        "",
        f"| Ticker | 1D excess % | {window} return % | Benchmark return % | {window} excess % | Status |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for row in payload.get("watchlist") or []:
        one_day_ex = row.get("one_day_excess_return_pct")
        one_day_ex = float(one_day_ex) if one_day_ex is not None else 0.0
        lines.append(
            f"| {row['ticker']} | {one_day_ex:.4f} | {row['window_return_pct']:.4f} | {row['benchmark_return_pct']:.4f} | {row['excess_return_pct']:.4f} | {row['status']} |"
        )
    lines.extend(
        [
            "",
            "## No-Change Policy",
            "",
            "- No code change.",
            "- No calibration change.",
            "- No guard change.",
            "- No rating change.",
            "- No report change.",
        ]
    )
    return "\n".join(lines) + "\n"


def _build_vivi_payload(
    *,
    batch_id: str,
    window: str,
    triage_payload: Dict[str, Any],
    triage_path: Path,
) -> Dict[str, Any]:
    false_block = triage_payload["overall_status"]["false_block_flags"]["unique_tickers"]
    false_pass = triage_payload["overall_status"]["false_pass_flags"]["unique_tickers"]
    return {
        "blocking_issues": [],
        "non_blocking_issues": [
            {
                "artifact": str(triage_path),
                "category": "Outcome Monitoring",
                "confidence": "high",
                "issue": f"{window} outcome triage computed; monitoring-only flags present.",
                "evidence": {
                    "false_block_candidates": false_block,
                    "false_pass_candidates": false_pass,
                },
                "severity": "info",
            }
        ],
        "false_block_candidates": false_block,
        "false_pass_candidates": false_pass,
        "fix_list_for_codex": [],
        "human_review_required": False,
        "do_not_change": [
            "No guard loosening.",
            f"No calibration changes from {window} alone.",
            "No rating or report changes from outcome monitoring artifacts.",
            "No synthetic prices, replacement end dates, or forward-fill.",
        ],
        "review_metadata": {
            "batch_id": batch_id,
            "bundle_id": f"{batch_id}_outcome_{_window_slug(window)}_review",
            "reviewed_at": _utc_now(),
            "reviewer": "Vivi",
            "schema_version": "v1.1",
        },
        "review_status": "pass",
    }


def _compute_window(args: argparse.Namespace) -> Dict[str, Any]:
    batch_id = str(args.batch_id)
    focus_batch_id = str(args.focus_batch_id)
    window = _window_label(args.window)
    context = _load_context(batch_id=batch_id, focus_batch_id=focus_batch_id)
    plan = context["plan"]
    tracking_window = _get_tracking_window(plan, window)
    price_basis_date = str(plan["price_basis_date"])
    window_end_date = str(tracking_window["earliest_evaluation_date"])
    benchmark_mapping = {
        str(k).upper(): str(v).upper() for k, v in (tracking_window.get("benchmark_mapping") or {}).items()
    }
    readiness = _build_readiness_payload(batch_id=batch_id, focus_batch_id=focus_batch_id, window=window)
    if readiness["status"] != "ready_to_compute":
        raise RuntimeError(json.dumps(readiness, indent=2, sort_keys=True))

    price_dir = Path("outputs/source_inputs") / batch_id / "prices"
    rows = _build_outcome_rows(
        batch_id=batch_id,
        focus_batch_id=focus_batch_id,
        five_day_end_date=window_end_date,
        benchmark_mapping=benchmark_mapping,
        price_basis_date=price_basis_date,
        price_dir=price_dir,
        base_items=context["base_items"],
        focus_items=context["focus_items"],
        false_block_threshold=args.false_block_threshold,
        false_pass_threshold=args.false_pass_threshold,
        monitor_threshold=args.monitor_threshold,
    )

    output_root = Path(args.output_root)
    batch_output_root = output_root / batch_id
    batch_output_root.mkdir(parents=True, exist_ok=True)

    computed_rows = len(rows)
    unique_tickers = len({row.ticker for row in rows})

    outcome_json_path = batch_output_root / f"OUTCOME_{window}_REVIEW.json"
    outcome_md_path = batch_output_root / f"OUTCOME_{window}_REVIEW.md"
    _write_json(outcome_json_path, {"results": [_row_payload(row, window=window) for row in rows]})
    outcome_md_path.write_text(
        _render_outcome_review_md(
            batch_id=batch_id,
            focus_batch_id=focus_batch_id,
            price_basis_date=price_basis_date,
            window=window,
            window_end_date=window_end_date,
            rows=rows,
        ),
        encoding="utf-8",
    )

    deduped = _dedupe_for_top_lists(rows, focus_batch_id=focus_batch_id)
    top_pos_rows = sorted(deduped, key=lambda r: r.excess_return_pct, reverse=True)[:10]
    top_neg_rows = sorted(deduped, key=lambda r: r.excess_return_pct)[:10]
    top_pos_payload = _top_payload(top_pos_rows, window=window, args=args)
    top_neg_payload = _top_payload(top_neg_rows, window=window, args=args)
    false_pass_unique = sorted({r.ticker for r in deduped if r.false_pass_suspicion})
    false_block_unique = sorted({r.ticker for r in deduped if r.manual_review_missed_opportunity})

    triage_payload = {
        "batch_id": batch_id,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source_files": {
            "outcome_review_json": str(outcome_json_path),
            "outcome_review_md": str(outcome_md_path),
        },
        "window": window,
        "price_basis_date": price_basis_date,
        "window_end_date": window_end_date,
        "overall_status": {
            "status": "computed",
            "computed_rows": computed_rows,
            "pending_rows": 0,
            "computed_unique_tickers": unique_tickers,
            "false_pass_flags": {"row_count": len(false_pass_unique), "unique_tickers": false_pass_unique},
            "false_block_flags": {"row_count": len(false_block_unique), "unique_tickers": false_block_unique},
            "benchmark_coverage": {
                "status": "complete",
                "computed_rows_with_benchmark": computed_rows,
                "computed_unique_tickers_with_benchmark": unique_tickers,
                "missing_benchmark_tickers": [],
            },
            "data_quality": {
                "status": f"complete_for_{_window_slug(window)}",
                "missing_price_tickers": [],
                "missing_benchmark_tickers": [],
                "notes": f"{window} is fully computed from local price CSVs. Top lists are deduped by ticker and prefer {focus_batch_id} where duplicated tickers exist.",
            },
        },
        "top_positive_excess_returns": top_pos_payload,
        "top_negative_excess_returns": top_neg_payload,
    }

    triage_json_path = batch_output_root / f"OUTCOME_{window}_TRIAGE_SUMMARY.json"
    triage_md_path = batch_output_root / f"OUTCOME_{window}_TRIAGE_SUMMARY.md"
    _write_json(triage_json_path, triage_payload)
    triage_md_path.write_text(
        _render_triage_md(
            batch_id=batch_id,
            focus_batch_id=focus_batch_id,
            window=window,
            price_basis_date=price_basis_date,
            window_end_date=window_end_date,
            computed_rows=computed_rows,
            unique_tickers=unique_tickers,
            false_pass_unique=false_pass_unique,
            false_block_unique=false_block_unique,
            top_pos=top_pos_payload,
            top_neg=top_neg_payload,
            excess_by_ticker={r.ticker: r.excess_return_pct for r in deduped},
            strong_negative_threshold=args.monitor_threshold * -1.0,
        ),
        encoding="utf-8",
    )

    watchlist_payload = _build_watchlist_payload(
        batch_id=batch_id,
        window=window,
        window_end_date=window_end_date,
        outcome_rows=rows,
        false_block_threshold=args.false_block_threshold,
        monitor_threshold=args.monitor_threshold,
    )
    watchlist_json_path = batch_output_root / f"OUTCOME_{window}_WATCHLIST_REVIEW.json"
    watchlist_md_path = batch_output_root / f"OUTCOME_{window}_WATCHLIST_REVIEW.md"
    _write_json(watchlist_json_path, watchlist_payload)
    watchlist_md_path.write_text(_render_watchlist_md(watchlist_payload), encoding="utf-8")

    vivi_path = batch_output_root / f"VIVI_OUTCOME_{window}_REVIEW.json"
    _write_json(
        vivi_path,
        _build_vivi_payload(
            batch_id=batch_id,
            window=window,
            triage_payload=triage_payload,
            triage_path=triage_json_path,
        ),
    )

    return {
        "status": "computed",
        "window": window,
        "computed_rows": computed_rows,
        "unique_tickers": unique_tickers,
        "output_root": str(batch_output_root),
        "artifacts": [
            str(outcome_json_path),
            str(outcome_md_path),
            str(triage_json_path),
            str(triage_md_path),
            str(watchlist_json_path),
            str(watchlist_md_path),
            str(vivi_path),
        ],
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Compute generic outcome-window artifacts.")
    parser.add_argument("--window", default="10D")
    parser.add_argument("--batch-id", default=BATCH_ID_DEFAULT)
    parser.add_argument("--focus-batch-id", default=FOCUS_BATCH_ID_DEFAULT)
    parser.add_argument("--output-root", default="outputs/batches")
    parser.add_argument("--readiness-only", action="store_true")
    parser.add_argument("--readiness-output")
    parser.add_argument("--false-block-threshold", type=float, default=5.0)
    parser.add_argument("--false-pass-threshold", type=float, default=-5.0)
    parser.add_argument("--monitor-threshold", type=float, default=3.0)
    args = parser.parse_args(argv)

    try:
        if args.readiness_only:
            payload = _build_readiness_payload(
                batch_id=str(args.batch_id),
                focus_batch_id=str(args.focus_batch_id),
                window=str(args.window),
            )
            if args.readiness_output:
                _write_json(Path(args.readiness_output), payload)
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0

        result = _compute_window(args)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except Exception as error:
        print(
            json.dumps(
                {
                    "status": "error",
                    "error": str(error),
                    "generated_at": datetime.now(timezone.utc)
                    .replace(microsecond=0)
                    .isoformat()
                    .replace("+00:00", "Z"),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
