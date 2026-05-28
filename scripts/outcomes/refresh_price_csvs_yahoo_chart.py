#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import time
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


YAHOO_CHART_BASE = "https://query1.finance.yahoo.com/v8/finance/chart"
DEFAULT_BENCHMARKS = ("QQQ", "SMH", "SPY")


@dataclass(frozen=True)
class RefreshResult:
    symbol: str
    csv_path: str
    existed_before: bool
    latest_before: Optional[str]
    target_date_present_before: bool
    fetched_rows: int
    appended_rows: int
    latest_after: Optional[str]
    target_date_present_after: bool
    status: str
    issue: Optional[str]


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _iso(d: Optional[date]) -> Optional[str]:
    return d.isoformat() if d else None


def _read_existing_dates(csv_path: Path) -> Tuple[Optional[date], bool, set[str]]:
    if not csv_path.exists():
        return None, False, set()
    dates: set[str] = set()
    latest: Optional[date] = None
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            d = (row.get("date") or "").strip()
            if not d:
                continue
            dates.add(d)
            try:
                parsed = _parse_date(d)
            except ValueError:
                continue
            if latest is None or parsed > latest:
                latest = parsed
    return latest, False, dates


def _fetch_yahoo_history(symbol: str, start: date, end_inclusive: date) -> List[Dict[str, Any]]:
    period1 = int(datetime(start.year, start.month, start.day, tzinfo=timezone.utc).timestamp())
    # Yahoo chart period2 is effectively exclusive; add one day to include end_inclusive.
    end_exclusive = end_inclusive + timedelta(days=1)
    period2 = int(datetime(end_exclusive.year, end_exclusive.month, end_exclusive.day, tzinfo=timezone.utc).timestamp())
    url = (
        f"{YAHOO_CHART_BASE}/{symbol}"
        f"?period1={period1}&period2={period2}&interval=1d&events=history&includeAdjustedClose=true"
    )
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    result = (payload.get("chart", {}).get("result") or [None])[0]
    if not result:
        error = payload.get("chart", {}).get("error")
        raise RuntimeError(f"Yahoo chart returned no result for {symbol}: {error}")
    timestamps = result.get("timestamp") or []
    quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    adjclose = ((result.get("indicators") or {}).get("adjclose") or [{}])[0].get("adjclose") or []

    def _at(values: Optional[Sequence[Any]], index: int) -> Any:
        if not values:
            return None
        try:
            return values[index]
        except IndexError:
            return None

    rows: List[Dict[str, Any]] = []
    for index, ts in enumerate(timestamps):
        open_ = _at(quote.get("open"), index)
        high = _at(quote.get("high"), index)
        low = _at(quote.get("low"), index)
        close = _at(quote.get("close"), index)
        volume = _at(quote.get("volume"), index)
        if close is None or open_ is None or high is None or low is None or volume is None:
            continue
        d = datetime.fromtimestamp(int(ts), tz=timezone.utc).date()
        if d < start or d > end_inclusive:
            continue
        rows.append(
            {
                "date": d.isoformat(),
                "open": float(open_),
                "high": float(high),
                "low": float(low),
                "close": float(close),
                "volume": int(volume or 0),
                "adjusted_close": float(_at(adjclose, index) or close),
            }
        )
    if not rows:
        raise RuntimeError(f"Yahoo chart returned no usable OHLCV rows for {symbol} in {start}..{end_inclusive}")
    rows.sort(key=lambda r: r["date"])
    return rows


def _append_rows(csv_path: Path, new_rows: List[Dict[str, Any]], *, existing_dates: set[str]) -> int:
    rows_to_append = [row for row in new_rows if row["date"] not in existing_dates]
    if not rows_to_append:
        return 0
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = csv_path.exists()
    with csv_path.open("a" if file_exists else "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["date", "open", "high", "low", "close", "volume", "adjusted_close"],
            lineterminator="\n",
        )
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows_to_append)
    return len(rows_to_append)


def _discover_universe_json(batch_dir: Path) -> Path:
    candidates = sorted(batch_dir.glob("*_UNIVERSE.json"))
    if not candidates:
        raise FileNotFoundError(f"No *_UNIVERSE.json found under {batch_dir}")
    if len(candidates) > 1:
        raise RuntimeError(f"Multiple *_UNIVERSE.json files found under {batch_dir}: {candidates}")
    return candidates[0]


def _load_universe_tickers(universe_json: Path) -> List[str]:
    payload = json.loads(universe_json.read_text(encoding="utf-8"))
    tickers = payload.get("included_tickers") or []
    if not isinstance(tickers, list) or not tickers:
        raise ValueError(f"Universe JSON missing included_tickers list: {universe_json}")
    return [str(t).upper() for t in tickers]


def _latest_local_date(csv_path: Path) -> Optional[date]:
    if not csv_path.exists():
        return None
    latest: Optional[date] = None
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            d = (row.get("date") or "").strip()
            if not d:
                continue
            try:
                parsed = _parse_date(d)
            except ValueError:
                continue
            if latest is None or parsed > latest:
                latest = parsed
    return latest


def refresh_symbol(
    symbol: str,
    *,
    price_dir: Path,
    target_date: date,
    start_date: date,
    lookback_days: int,
    sleep_seconds: float,
) -> RefreshResult:
    csv_path = price_dir / f"{symbol}.csv"
    existed_before = csv_path.exists()
    latest_before = _latest_local_date(csv_path)
    existing_dates: set[str] = set()
    target_present_before = False
    if existed_before:
        with csv_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                d = (row.get("date") or "").strip()
                if not d:
                    continue
                existing_dates.add(d)
                if d == target_date.isoformat():
                    target_present_before = True

    if target_present_before:
        return RefreshResult(
            symbol=symbol,
            csv_path=str(csv_path),
            existed_before=True,
            latest_before=_iso(latest_before),
            target_date_present_before=True,
            fetched_rows=0,
            appended_rows=0,
            latest_after=_iso(latest_before),
            target_date_present_after=True,
            status="already_complete",
            issue=None,
        )

    fetch_start = start_date
    if latest_before:
        fetch_start = max(start_date, latest_before - timedelta(days=lookback_days))

    issue: Optional[str] = None
    fetched_rows = 0
    appended_rows = 0
    try:
        history = _fetch_yahoo_history(symbol, fetch_start, target_date)
        fetched_rows = len(history)
        appended_rows = _append_rows(csv_path, history, existing_dates=existing_dates)
        time.sleep(sleep_seconds)
    except Exception as exc:  # noqa: BLE001 - script must report per-symbol provider failures.
        issue = str(exc)

    latest_after = _latest_local_date(csv_path)
    target_present_after = False
    if csv_path.exists():
        with csv_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                if (row.get("date") or "").strip() == target_date.isoformat():
                    target_present_after = True
                    break

    if issue:
        status = "error"
    elif target_present_after:
        status = "updated" if appended_rows else "no_new_rows_but_now_complete"
    else:
        status = "not_ready"
        issue = issue or f"Target date {target_date.isoformat()} still missing after refresh attempt."

    return RefreshResult(
        symbol=symbol,
        csv_path=str(csv_path),
        existed_before=existed_before,
        latest_before=_iso(latest_before),
        target_date_present_before=target_present_before,
        fetched_rows=fetched_rows,
        appended_rows=appended_rows,
        latest_after=_iso(latest_after),
        target_date_present_after=target_present_after,
        status=status,
        issue=issue,
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Refresh local OHLCV CSVs via Yahoo Finance chart API.")
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--target-date", required=True, help="Required local bar date (YYYY-MM-DD) to reach.")
    parser.add_argument("--start-date", default="2024-01-01", help="Lower bound for fetch window (YYYY-MM-DD).")
    parser.add_argument("--price-dir", help="Defaults to outputs/source_inputs/<batch-id>/prices")
    parser.add_argument("--universe-json", help="Defaults to outputs/batches/<batch-id>/*_UNIVERSE.json")
    parser.add_argument("--benchmarks", default=",".join(DEFAULT_BENCHMARKS))
    parser.add_argument("--lookback-days", type=int, default=14, help="Refetch overlap window when appending.")
    parser.add_argument("--sleep-seconds", type=float, default=0.05, help="Polite delay between provider calls.")
    parser.add_argument("--write-report-json", help="Optional path to write a refresh summary JSON report.")
    args = parser.parse_args(argv)

    target_date = _parse_date(args.target_date)
    start_date = _parse_date(args.start_date)

    batch_dir = Path("outputs/batches") / args.batch_id
    universe_json = Path(args.universe_json) if args.universe_json else _discover_universe_json(batch_dir)
    tickers = _load_universe_tickers(universe_json)
    benchmarks = [b.strip().upper() for b in str(args.benchmarks).split(",") if b.strip()]
    symbols = sorted(set(tickers + benchmarks))

    price_dir = Path(args.price_dir) if args.price_dir else (Path("outputs/source_inputs") / args.batch_id / "prices")
    price_dir.mkdir(parents=True, exist_ok=True)

    results: List[RefreshResult] = []
    for symbol in symbols:
        results.append(
            refresh_symbol(
                symbol,
                price_dir=price_dir,
                target_date=target_date,
                start_date=start_date,
                lookback_days=args.lookback_days,
                sleep_seconds=args.sleep_seconds,
            )
        )

    missing = sorted([r.symbol for r in results if not r.target_date_present_after])
    updated = sorted([r.symbol for r in results if r.appended_rows])
    errored = sorted([r.symbol for r in results if r.status == "error"])
    payload = {
        "batch_id": args.batch_id,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "target_date": target_date.isoformat(),
        "start_date": start_date.isoformat(),
        "price_dir": str(price_dir),
        "benchmarks": benchmarks,
        "summary": {
            "symbol_count": len(results),
            "updated_symbol_count": len(updated),
            "error_symbol_count": len(errored),
            "missing_symbol_count": len(missing),
            "missing_symbols": missing,
        },
        "results": [r.__dict__ for r in results],
    }

    if args.write_report_json:
        Path(args.write_report_json).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    print(json.dumps(payload["summary"], indent=2, sort_keys=True))
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
