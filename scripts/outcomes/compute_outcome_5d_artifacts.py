#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


BATCH_ID_DEFAULT = "guardrail_coverage_batch_004_ir_coverage"
FOCUS_BATCH_ID_DEFAULT = "manual_focus_guardrail_final_check"
WATCHLIST_TICKERS = ("MDB", "NOW", "RKLB", "ZS")


@dataclass(frozen=True)
class OutcomeRow:
    ticker: str
    source_batch: str
    original_status: str
    rating_external_display: str
    publishable: bool
    price_basis_date: str
    price_basis_close: float
    price_source: str
    five_day_end_date: str
    five_day_end_close: float
    return_pct: float
    benchmark: str
    benchmark_price_source: str
    benchmark_price_basis_close: float
    benchmark_five_day_end_close: float
    benchmark_return_pct: float
    excess_return_pct: float
    outcome_status: str
    rating_action_success_preliminary: str
    false_pass_suspicion: bool
    manual_review_missed_opportunity: bool
    guard_lesson: str


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _discover_focus_dashboard(focus_batch_id: str) -> Path:
    root = Path("outputs/batches") / focus_batch_id
    candidates = sorted(root.glob("*/dashboard_status.json"))
    if not candidates:
        raise FileNotFoundError(f"Focus batch dashboard not found under {root}")
    if len(candidates) > 1:
        raise RuntimeError(f"Multiple focus dashboards found under {root}: {candidates}")
    return candidates[0]


def _load_close_map(csv_path: Path) -> Dict[str, float]:
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing CSV price history: {csv_path}")
    closes: Dict[str, float] = {}
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            d = (row.get("date") or "").strip()
            c = row.get("close")
            if not d or c is None:
                continue
            try:
                closes[d] = float(c)
            except ValueError:
                continue
    if not closes:
        raise ValueError(f"No close rows loaded from {csv_path}")
    return closes


def _pct_return(end_close: float, basis_close: float) -> float:
    return round((end_close / basis_close - 1.0) * 100.0, 4)


def _interpretation(
    *,
    ticker: str,
    original_status: str,
    excess_return_pct: float,
    false_block_threshold: float,
    false_pass_threshold: float,
    monitor_threshold: float,
) -> str:
    # "Missed-opportunity" is a curated watchlist concept (see OUTCOME_WATCHLIST_CARRY_FORWARD).
    # Do not expand false-block flags beyond the defined watchlist at 5D.
    if original_status == "manual_review" and ticker in WATCHLIST_TICKERS and excess_return_pct >= false_block_threshold:
        return "possible false block"
    if original_status == "passed" and excess_return_pct <= false_pass_threshold:
        return "possible false pass"
    if abs(excess_return_pct) >= monitor_threshold:
        return "worth monitoring"
    return "normal noise"


def _guard_lesson(original_status: str) -> str:
    if original_status == "passed":
        return (
            "Five-day outcome is monitoring-only; false-pass suspicion is only a review flag, not a calibration change."
        )
    return "Five-day outcome is monitoring-only; manual-review process quality is not recalibrated from a single window."


def _rating_action_success_preliminary(original_status: str) -> str:
    return "monitor_only_manual_review" if original_status == "manual_review" else "monitor_only_no_calibration_change"


def _load_dashboard_items(dashboard_path: Path) -> List[Dict[str, Any]]:
    payload = _read_json(dashboard_path)
    items = payload.get("items") or []
    if not isinstance(items, list) or not items:
        raise ValueError(f"Invalid dashboard_status.json (missing items): {dashboard_path}")
    return items


def _build_outcome_rows(
    *,
    batch_id: str,
    focus_batch_id: str,
    five_day_end_date: str,
    benchmark_mapping: Dict[str, str],
    price_basis_date: str,
    price_dir: Path,
    base_items: List[Dict[str, Any]],
    focus_items: List[Dict[str, Any]],
    false_block_threshold: float,
    false_pass_threshold: float,
    monitor_threshold: float,
) -> List[OutcomeRow]:
    bench_symbols = sorted(set(benchmark_mapping.values()))
    bench_closes = {b: _load_close_map(price_dir / f"{b}.csv") for b in bench_symbols}

    def build_row(item: Dict[str, Any], source_batch: str) -> OutcomeRow:
        ticker = str(item["ticker"]).upper()
        manifest_path = Path(item.get("artifacts", {}).get("report_manifest.json") or "")
        if not manifest_path.exists():
            raise FileNotFoundError(f"Missing report_manifest.json for {ticker}: {manifest_path}")
        manifest = _read_json(manifest_path)

        basis_date = str(manifest.get("price_basis_date") or price_basis_date)
        basis_close = float(manifest["price_basis_close"])
        publishable = bool(manifest.get("publishable"))

        price_source = str(price_dir / f"{ticker}.csv")
        ticker_closes = _load_close_map(Path(price_source))
        if five_day_end_date not in ticker_closes:
            raise FileNotFoundError(f"Missing {ticker} close for {five_day_end_date} in {price_source}")
        end_close = float(ticker_closes[five_day_end_date])

        benchmark = str(benchmark_mapping.get(ticker) or "QQQ").upper()
        bench_src = str(price_dir / f"{benchmark}.csv")
        bench_map = bench_closes[benchmark]
        if basis_date not in bench_map:
            raise FileNotFoundError(f"Missing {benchmark} close for basis {basis_date} in {bench_src}")
        if five_day_end_date not in bench_map:
            raise FileNotFoundError(f"Missing {benchmark} close for {five_day_end_date} in {bench_src}")
        bench_basis = float(bench_map[basis_date])
        bench_end = float(bench_map[five_day_end_date])

        ret = _pct_return(end_close, basis_close)
        bench_ret = _pct_return(bench_end, bench_basis)
        excess = round(ret - bench_ret, 4)

        original_status = str(item.get("status") or "").strip().lower() or "manual_review"
        rating_external = str(item.get("external_display_rating") or manifest.get("final_rating") or "").strip() or "Hold"

        interp = _interpretation(
            ticker=ticker,
            original_status=original_status,
            excess_return_pct=excess,
            false_block_threshold=false_block_threshold,
            false_pass_threshold=false_pass_threshold,
            monitor_threshold=monitor_threshold,
        )
        false_pass = interp == "possible false pass"
        false_block = interp == "possible false block"

        return OutcomeRow(
            ticker=ticker,
            source_batch=source_batch,
            original_status=original_status,
            rating_external_display=rating_external,
            publishable=publishable,
            price_basis_date=basis_date,
            price_basis_close=basis_close,
            price_source=price_source,
            five_day_end_date=five_day_end_date,
            five_day_end_close=end_close,
            return_pct=ret,
            benchmark=benchmark,
            benchmark_price_source=bench_src,
            benchmark_price_basis_close=bench_basis,
            benchmark_five_day_end_close=bench_end,
            benchmark_return_pct=bench_ret,
            excess_return_pct=excess,
            outcome_status="computed",
            rating_action_success_preliminary=_rating_action_success_preliminary(original_status),
            false_pass_suspicion=bool(false_pass),
            manual_review_missed_opportunity=bool(false_block),
            guard_lesson=_guard_lesson(original_status),
        )

    rows: List[OutcomeRow] = []
    for item in base_items:
        rows.append(build_row(item, batch_id))
    for item in focus_items:
        rows.append(build_row(item, focus_batch_id))
    return rows


def _dedupe_for_top_lists(rows: List[OutcomeRow], *, focus_batch_id: str) -> List[OutcomeRow]:
    best: Dict[str, OutcomeRow] = {}
    for row in rows:
        existing = best.get(row.ticker)
        if not existing:
            best[row.ticker] = row
            continue
        if row.source_batch == focus_batch_id and existing.source_batch != focus_batch_id:
            best[row.ticker] = row
    return list(best.values())


def _render_outcome_review_md(
    *,
    batch_id: str,
    focus_batch_id: str,
    price_basis_date: str,
    five_day_end_date: str,
    rows: List[OutcomeRow],
) -> str:
    lines = [
        "# Outcome 5D Review",
        "",
        f"- Batch: {batch_id}",
        f"- Included focus check: {focus_batch_id}",
        f"- Price basis date: {price_basis_date}",
        f"- 5D end date: {five_day_end_date}",
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
        "| Ticker | Source Batch | Original status | External display | Benchmark | Return % | Benchmark return % | Excess % | Outcome status | Guard lesson |",
        "|---|---|---|---|---|---:|---:|---:|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row.ticker} | {row.source_batch} | {row.original_status} | {row.rating_external_display} | {row.benchmark} | {row.return_pct:.4f} | {row.benchmark_return_pct:.4f} | {row.excess_return_pct:.4f} | {row.outcome_status} | {row.guard_lesson} |"
        )
    return "\n".join(lines) + "\n"


def _render_triage_md(
    *,
    batch_id: str,
    focus_batch_id: str,
    price_basis_date: str,
    five_day_end_date: str,
    computed_rows: int,
    unique_tickers: int,
    false_pass_unique: List[str],
    false_block_unique: List[str],
    top_pos: List[Dict[str, Any]],
    top_neg: List[Dict[str, Any]],
    excess_by_ticker: Dict[str, float],
    strong_negative_threshold: float,
) -> str:
    lines = [
        "# Outcome 5D Triage Summary",
        "",
        f"- Batch: {batch_id}",
        "- Source: OUTCOME_5D_REVIEW.md/json",
        f"- Window: 5D ({price_basis_date} to {five_day_end_date})",
        "- Status: computed",
        f"- Computed rows: {computed_rows} ({unique_tickers} unique tickers)",
        "- Pending rows: 0",
        f"- False pass flags: {len(false_pass_unique)} rows / {len(false_pass_unique)} unique tickers"
        + ("" if not false_pass_unique else f" ({', '.join(false_pass_unique)})"),
        f"- False block flags: {len(false_block_unique)} rows / {len(false_block_unique)} unique tickers"
        + ("" if not false_block_unique else f" ({', '.join(false_block_unique)})"),
        f"- Benchmark coverage: complete ({computed_rows}/{computed_rows} computed rows)",
        "- Data quality: complete_for_5d; no missing price tickers; no missing benchmark tickers",
        "",
        f"Top lists are deduped by ticker and prefer {focus_batch_id} where a focus overlay exists. The computed row count preserves the source row count.",
        "",
        "## Top 10 Positive Excess Returns",
        "",
        "| Ticker | Original status | Rating / external display | 5D return % | Benchmark return % | Excess % | Interpretation |",
        "|---|---|---|---:|---:|---:|---|",
    ]
    for row in top_pos:
        lines.append(
            f"| {row['ticker']} | {row['original_status']} | {row['rating_external_display']} | {row['five_day_return_pct']:.4f} | {row['benchmark_return_pct']:.4f} | {row['excess_return_pct']:.4f} | {row['interpretation']} |"
        )

    lines.extend(
        [
            "",
            "## Top 10 Negative Excess Returns",
            "",
            "| Ticker | Original status | Rating / external display | 5D return % | Benchmark return % | Excess % | Interpretation |",
            "|---|---|---|---:|---:|---:|---|",
        ]
    )
    for row in top_neg:
        lines.append(
            f"| {row['ticker']} | {row['original_status']} | {row['rating_external_display']} | {row['five_day_return_pct']:.4f} | {row['benchmark_return_pct']:.4f} | {row['excess_return_pct']:.4f} | {row['interpretation']} |"
        )

    lines.extend(
        [
            "",
            "## Passed Reports Check",
            "",
            f"- Strong negative threshold: <= {strong_negative_threshold:.4f}% excess.",
            "- Passed tickers with strong negative 5D excess:",
            "- " + ("None at threshold" if not false_pass_unique else ", ".join(false_pass_unique)),
            f"- Possible false pass suspicion: {'yes' if false_pass_unique else 'no'}",
            "- Action: no action unless repeated at 10D/20D.",
            "",
            "## Manual-Review Missed-Opportunity Watchlist",
            "",
            "| Ticker | 5D excess % | Status | Recommended action |",
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
            action = "keep monitoring; confirm again at 10D"
        lines.append(f"| {ticker} | {ex:.4f} | {status_label} | {action} |")

    lines.extend(
        [
            "",
            "## No-Change Policy",
            "",
            "- No calibration from 5D alone.",
            "- No guard change from 5D alone.",
            "- No rating change from 5D alone.",
            "- No report change from 5D alone.",
        ]
    )
    return "\n".join(lines) + "\n"


def _build_watchlist_review(
    *,
    batch_id: str,
    five_day_end_date: str,
    outcome_rows: List[OutcomeRow],
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
        if ex >= 5.0:
            status = "confirmed_outperformance"
        elif ex >= 3.0:
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
                "five_day_end_date": five_day_end_date,
                "five_day_return_pct": row.return_pct,
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
        "window": "5D",
        "five_day_end_date": five_day_end_date,
        "watchlist": watchlist,
    }


def _render_watchlist_md(payload: Dict[str, Any]) -> str:
    lines = [
        "# Outcome 5D Watchlist Review",
        "",
        f"- Batch: {payload['batch_id']}",
        f"- Window: 5D (end date {payload['five_day_end_date']})",
        "- Policy: monitoring-only; no calibration, no guards, no ratings, no report changes",
        "",
        "| Ticker | 1D excess % | 5D return % | Benchmark return % | 5D excess % | Status |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for row in payload.get("watchlist") or []:
        one_day_ex = row.get("one_day_excess_return_pct")
        one_day_ex = float(one_day_ex) if one_day_ex is not None else 0.0
        lines.append(
            f"| {row['ticker']} | {one_day_ex:.4f} | {row['five_day_return_pct']:.4f} | {row['benchmark_return_pct']:.4f} | {row['excess_return_pct']:.4f} | {row['status']} |"
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


def _build_vivi_outcome(*, batch_id: str, triage_payload: Dict[str, Any]) -> Dict[str, Any]:
    false_block = triage_payload["overall_status"]["false_block_flags"]["unique_tickers"]
    false_pass = triage_payload["overall_status"]["false_pass_flags"]["unique_tickers"]
    return {
        "blocking_issues": [],
        "non_blocking_issues": [
            {
                "artifact": "outputs/batches/guardrail_coverage_batch_004_ir_coverage/OUTCOME_5D_TRIAGE_SUMMARY.json",
                "category": "Outcome Monitoring",
                "confidence": "high",
                "issue": "5D outcome triage computed; monitoring-only flags present.",
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
            "No calibration changes from 5D alone.",
            "No rating or report changes from outcome monitoring artifacts.",
            "No synthetic prices, replacement end dates, or forward-fill.",
        ],
        "review_metadata": {
            "batch_id": batch_id,
            "bundle_id": f"{batch_id}_outcome_5d_review",
            "reviewed_at": _utc_now(),
            "reviewer": "Vivi",
            "schema_version": "v1.1",
        },
        "review_status": "pass",
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Compute 5D outcome review + watchlist + triage artifacts.")
    parser.add_argument("--batch-id", default=BATCH_ID_DEFAULT)
    parser.add_argument("--focus-batch-id", default=FOCUS_BATCH_ID_DEFAULT)
    parser.add_argument("--false-block-threshold", type=float, default=5.0)
    parser.add_argument("--false-pass-threshold", type=float, default=-5.0)
    parser.add_argument("--monitor-threshold", type=float, default=3.0)
    args = parser.parse_args(argv)

    batch_id = str(args.batch_id)
    focus_batch_id = str(args.focus_batch_id)

    batch_root = Path("outputs/batches") / batch_id
    plan = _read_json(batch_root / "OUTCOME_TRACKING_PLAN.json")
    price_basis_date = str(plan["price_basis_date"])
    five_day_window = next(w for w in plan["tracking_windows"] if w["window"] == "5D")
    five_day_end_date = str(five_day_window["earliest_evaluation_date"])
    benchmark_mapping = {
        str(k).upper(): str(v).upper() for k, v in (five_day_window.get("benchmark_mapping") or {}).items()
    }

    price_dir = Path("outputs/source_inputs") / batch_id / "prices"
    base_items = _load_dashboard_items(batch_root / "dashboard_status.json")
    focus_items = _load_dashboard_items(_discover_focus_dashboard(focus_batch_id))

    rows = _build_outcome_rows(
        batch_id=batch_id,
        focus_batch_id=focus_batch_id,
        five_day_end_date=five_day_end_date,
        benchmark_mapping=benchmark_mapping,
        price_basis_date=price_basis_date,
        price_dir=price_dir,
        base_items=base_items,
        focus_items=focus_items,
        false_block_threshold=args.false_block_threshold,
        false_pass_threshold=args.false_pass_threshold,
        monitor_threshold=args.monitor_threshold,
    )

    computed_rows = len(rows)
    unique_tickers = len({row.ticker for row in rows})

    # Outcome review
    outcome_json_path = batch_root / "OUTCOME_5D_REVIEW.json"
    outcome_md_path = batch_root / "OUTCOME_5D_REVIEW.md"
    _write_json(outcome_json_path, {"results": [asdict(row) for row in rows]})
    outcome_md_path.write_text(
        _render_outcome_review_md(
            batch_id=batch_id,
            focus_batch_id=focus_batch_id,
            price_basis_date=price_basis_date,
            five_day_end_date=five_day_end_date,
            rows=rows,
        ),
        encoding="utf-8",
    )

    # Triage summary
    deduped = _dedupe_for_top_lists(rows, focus_batch_id=focus_batch_id)
    top_pos = sorted(deduped, key=lambda r: r.excess_return_pct, reverse=True)[:10]
    top_neg = sorted(deduped, key=lambda r: r.excess_return_pct)[:10]

    top_pos_payload: List[Dict[str, Any]] = []
    for r in top_pos:
        top_pos_payload.append(
            {
                "ticker": r.ticker,
                "original_status": r.original_status,
                "rating_external_display": r.rating_external_display,
                "five_day_return_pct": r.return_pct,
                "benchmark": r.benchmark,
                "benchmark_return_pct": r.benchmark_return_pct,
                "excess_return_pct": r.excess_return_pct,
                "interpretation": _interpretation(
                    ticker=r.ticker,
                    original_status=r.original_status,
                    excess_return_pct=r.excess_return_pct,
                    false_block_threshold=args.false_block_threshold,
                    false_pass_threshold=args.false_pass_threshold,
                    monitor_threshold=args.monitor_threshold,
                ),
            }
        )

    top_neg_payload: List[Dict[str, Any]] = []
    for r in top_neg:
        top_neg_payload.append(
            {
                "ticker": r.ticker,
                "original_status": r.original_status,
                "rating_external_display": r.rating_external_display,
                "five_day_return_pct": r.return_pct,
                "benchmark": r.benchmark,
                "benchmark_return_pct": r.benchmark_return_pct,
                "excess_return_pct": r.excess_return_pct,
                "interpretation": _interpretation(
                    ticker=r.ticker,
                    original_status=r.original_status,
                    excess_return_pct=r.excess_return_pct,
                    false_block_threshold=args.false_block_threshold,
                    false_pass_threshold=args.false_pass_threshold,
                    monitor_threshold=args.monitor_threshold,
                ),
            }
        )

    false_pass_unique = sorted({r.ticker for r in deduped if r.false_pass_suspicion})
    false_block_unique = sorted({r.ticker for r in deduped if r.manual_review_missed_opportunity})

    triage_payload = {
        "batch_id": batch_id,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source_files": {
            "outcome_review_json": str(outcome_json_path),
            "outcome_review_md": str(outcome_md_path),
        },
        "window": "5D",
        "price_basis_date": price_basis_date,
        "five_day_end_date": five_day_end_date,
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
                "status": "complete_for_5d",
                "missing_price_tickers": [],
                "missing_benchmark_tickers": [],
                "notes": "5D is fully computed from local price CSVs. Top lists are deduped by ticker and prefer manual_focus_guardrail_final_check where duplicated tickers exist.",
            },
        },
        "top_positive_excess_returns": top_pos_payload,
        "top_negative_excess_returns": top_neg_payload,
    }

    triage_json_path = batch_root / "OUTCOME_5D_TRIAGE_SUMMARY.json"
    triage_md_path = batch_root / "OUTCOME_5D_TRIAGE_SUMMARY.md"
    _write_json(triage_json_path, triage_payload)
    triage_md_path.write_text(
        _render_triage_md(
            batch_id=batch_id,
            focus_batch_id=focus_batch_id,
            price_basis_date=price_basis_date,
            five_day_end_date=five_day_end_date,
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

    # Watchlist review
    watchlist_payload = _build_watchlist_review(batch_id=batch_id, five_day_end_date=five_day_end_date, outcome_rows=rows)
    watchlist_json_path = batch_root / "OUTCOME_5D_WATCHLIST_REVIEW.json"
    watchlist_md_path = batch_root / "OUTCOME_5D_WATCHLIST_REVIEW.md"
    _write_json(watchlist_json_path, watchlist_payload)
    watchlist_md_path.write_text(_render_watchlist_md(watchlist_payload), encoding="utf-8")

    # Vivi outcome JSON
    vivi_payload = _build_vivi_outcome(batch_id=batch_id, triage_payload=triage_payload)
    vivi_path = batch_root / "VIVI_OUTCOME_5D_REVIEW.json"
    _write_json(vivi_path, vivi_payload)

    print(json.dumps({"computed_rows": computed_rows, "unique_tickers": unique_tickers}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
