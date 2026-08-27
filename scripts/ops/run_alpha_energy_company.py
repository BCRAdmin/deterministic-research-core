#!/usr/bin/env python3
"""Run one live company through the Alpha Energy successor."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


EXPECTED_ORIGIN = "https://github.com/BCRAdmin/deterministic-research-core.git"


def _configured_research_root() -> Path:
    try:
        index = sys.argv.index("--research-root")
        configured = Path(sys.argv[index + 1]).expanduser().resolve()
    except (ValueError, IndexError):
        raise SystemExit("--research-root is required") from None
    try:
        top = Path(
            subprocess.check_output(
                ["git", "-C", str(configured), "rev-parse", "--show-toplevel"],
                text=True,
            ).strip()
        ).resolve()
        origin = subprocess.check_output(
            ["git", "-C", str(top), "remote", "get-url", "origin"], text=True
        ).strip()
    except subprocess.CalledProcessError as exc:
        raise SystemExit("configured research root is not a Git checkout") from exc
    if top != configured or origin != EXPECTED_ORIGIN:
        raise SystemExit("configured research root identity mismatch")
    sys.path.insert(0, str(top))
    return top


ROOT = _configured_research_root()

from research_agent.alpha_energy.compiler import build_alpha_energy_bundle  # noqa: E402
from research_agent.ba12_live_source import (  # noqa: E402
    ExistingAdapterHarness,
    LiveCaptureExecutor,
    bridge_capture_set_to_ba3,
    verify_live_bridge,
)
from research_agent.semantic_compiler.source_frontend.planner import (  # noqa: E402
    build_compile_request,
    plan_source_acquisition,
)
from research_agent.sources.prices.nasdaq_price_provider import NasdaqPriceProvider  # noqa: E402
from research_agent.sources.sec.sec_client import SecClient, SecClientConfig  # noqa: E402


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n"
    )


def _git(*args: str) -> str:
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode()


def _resolve(args: argparse.Namespace, sec: SecClient) -> tuple[dict[str, Any], dict[str, Any]]:
    if args.resolve_cik_from_sec:
        payload = sec.get_company_tickers()
        raw = _canonical_json(payload)
        matches = [
            row
            for row in payload.values()
            if isinstance(row, dict)
            and str(row.get("ticker") or "").upper() == args.ticker
        ]
        if len(matches) != 1:
            raise ValueError("ALPHA_ENERGY_RESOLUTION_NOT_UNIQUE")
        match = matches[0]
        cik, company_name = str(match["cik_str"]), str(match["title"])
        report = {
            "status": "PASS",
            "resolution_source": "SEC company_tickers.json",
            "provider_query_count": 1,
            "payload_sha256": hashlib.sha256(raw).hexdigest(),
            "payload_bytes": len(raw),
            "matches": 1,
            "matched_record": match,
        }
    else:
        if not args.cik or not args.company_name:
            raise ValueError("ALPHA_ENERGY_RESOLUTION_INPUT_MISSING")
        cik, company_name = args.cik, args.company_name
        report = {
            "status": "PASS",
            "resolution_source": args.resolution_source,
            "provider_query_count": 0,
            "matches": 1,
            "matched_record": {
                "ticker": args.ticker,
                "cik_str": cik,
                "title": company_name,
            },
        }
    resolution = {
        "status": "supported",
        "runtimeReady": True,
        "inputKind": "ticker",
        "input": args.ticker,
        "ticker": args.ticker,
        "companyName": company_name,
        "exchange": args.exchange,
        "exchangeCode": args.exchange_code,
        "jurisdiction": "US",
        "isin": args.isin,
        "source": args.resolution_source,
    }
    return resolution, {**report, "resolution": resolution, "cik": cik}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--research-root", required=True, type=Path)
    parser.add_argument("--ticker", required=True, type=str.upper)
    parser.add_argument("--company-name")
    parser.add_argument("--cik")
    parser.add_argument("--exchange", required=True)
    parser.add_argument("--exchange-code", required=True)
    parser.add_argument("--isin")
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--bundle-parent", required=True, type=Path)
    parser.add_argument("--monotonic-counter", required=True, type=int)
    parser.add_argument(
        "--resolution-source", default="room16_alpha_energy_development_contract_v1"
    )
    parser.add_argument("--resolve-cik-from-sec", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    bundle_root = args.bundle_parent / args.ticker
    if args.run_root.exists() or bundle_root.exists():
        raise SystemExit("run root or bundle root already exists")
    user_agent = os.environ.get("ROOM16_SEC_USER_AGENT", "")
    if "@" not in user_agent:
        raise SystemExit("ROOM16_SEC_USER_AGENT must contain a contact email")
    evidence = args.run_root / "evidence"
    timings: dict[str, float] = {}
    total_started = time.monotonic()
    sec = SecClient(SecClientConfig(user_agent=user_agent, use_cache=False))

    stage = time.monotonic()
    resolution, resolution_report = _resolve(args, sec)
    timings["instrument_resolution_seconds"] = round(time.monotonic() - stage, 6)
    cik = resolution_report["cik"]
    _write_json(evidence / "00_RESOLUTION_REPORT.json", resolution_report)

    stage = time.monotonic()
    request = build_compile_request(
        resolution,
        as_of_date=args.as_of_date,
        allowed_provider_ids=("nasdaq", "sec"),
        available_configuration_ids=("ROOM16_SEC_USER_AGENT",),
        network_mode="live_acquisition",
    )
    plan = plan_source_acquisition(request, price_provider_id="nasdaq")
    timings["compile_request_and_plan_seconds"] = round(time.monotonic() - stage, 6)
    _write_json(evidence / "01_COMPILE_REQUEST.json", request.model_dump(mode="json"))
    _write_json(evidence / "02_SOURCE_PLAN.json", plan.model_dump(mode="json"))

    live_root = args.run_root / "runtime/live"
    executor = LiveCaptureExecutor(live_root)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    cutoff = datetime.combine(
        date.fromisoformat(args.as_of_date), datetime.max.time(), tzinfo=timezone.utc
    ).replace(microsecond=0)
    authority_time = min(now, cutoff).isoformat().replace("+00:00", "Z")
    start_date = (date.fromisoformat(args.as_of_date) - timedelta(days=400)).isoformat()
    nasdaq = NasdaqPriceProvider()
    adapters = {
        "sec": ExistingAdapterHarness(
            provider_id="sec",
            adapter=sec,
            method_name="get_companyfacts",
            source_id=f"SEC_COMPANYFACTS_CIK{str(cik).zfill(10)}",
            source_type="sec_filing",
            original_locator=f"https://data.sec.gov/api/xbrl/companyfacts/CIK{str(cik).zfill(10)}.json",
            final_locator=f"https://data.sec.gov/api/xbrl/companyfacts/CIK{str(cik).zfill(10)}.json",
            raw_status="200",
            media_type="application/json",
            fetched_at_utc=authority_time,
            available_at_utc=authority_time,
            args=(cik,),
        ),
        "nasdaq": ExistingAdapterHarness(
            provider_id="nasdaq",
            adapter=nasdaq,
            method_name="get_history",
            source_id=f"NASDAQ_OHLCV_{args.ticker}",
            source_type="exchange_ohlcv",
            original_locator=(
                f"https://www.nasdaq.com/market-activity/stocks/"
                f"{args.ticker.lower()}/historical"
            ),
            final_locator=f"https://api.nasdaq.com/api/quote/{args.ticker}/historical",
            raw_status="200",
            media_type="application/json",
            fetched_at_utc=authority_time,
            available_at_utc=authority_time,
            args=(args.ticker, start_date, args.as_of_date),
        ),
    }
    stage = time.monotonic()
    records = tuple(
        executor.capture(
            request=request,
            plan=plan,
            acquisition_id=item.acquisition_id,
            attempt_id=(
                f"alpha.energy.{args.ticker.lower()}.{item.provider_id}.1"
            ),
            adapter=adapters[item.provider_id],
        )
        for item in plan.acquisitions
    )
    timings["live_acquisition_seconds"] = round(time.monotonic() - stage, 6)

    snapshot_root = args.run_root / "runtime/ba3_snapshot"
    stage = time.monotonic()
    bridge = bridge_capture_set_to_ba3(
        request=request,
        plan=plan,
        records=records,
        capture_store_root=executor.capture_store.root,
        snapshot_root=snapshot_root,
        staged_at_utc=authority_time,
    )
    bridge_verification = verify_live_bridge(
        records=records,
        result=bridge,
        capture_store_root=executor.capture_store.root,
    )
    timings["capture_to_ba3_seconds"] = round(time.monotonic() - stage, 6)

    stage = time.monotonic()
    research_commit, research_tree = _git("rev-parse", "HEAD"), _git(
        "rev-parse", "HEAD^{tree}"
    )
    compiled = build_alpha_energy_bundle(
        snapshot=bridge.snapshot,
        snapshot_root=snapshot_root,
        output_root=bundle_root,
        research_commit=research_commit,
        research_tree=research_tree,
        monotonic_counter=args.monotonic_counter,
    )
    timings["alpha_energy_native_compile_seconds"] = round(
        time.monotonic() - stage, 6
    )
    acquisition_rows: list[dict[str, Any]] = []
    receipt_rows: list[dict[str, Any]] = []
    for record in records:
        receipt = record.receipt.model_dump(mode="json")
        artifact = record.artifact.model_dump(mode="json")
        acquisition_rows.append(
            {
                "provider_id": receipt["provider_id"],
                "source_id": receipt["source_id"],
                "source_type": receipt["source_type"],
                "status": receipt["http_status_or_provider_status"],
                "normalized_outcome": receipt["normalized_outcome"],
                "variable_cost_incurred": receipt["variable_cost_incurred"],
                "payload_sha256": receipt["payload_sha256"],
                "payload_bytes": receipt["payload_bytes"],
            }
        )
        receipt_rows.append({"receipt": receipt, "artifact": artifact})
    _write_json(
        evidence / "03_LIVE_SOURCE_REPORT.json",
        {
            "status": "PASS",
            "ticker": args.ticker,
            "company": resolution["companyName"],
            "network_mode": "live_acquisition",
            "paid_provider_used": False,
            "silent_fallback_used": False,
            "manual_intervention_count": 0,
            "sources": acquisition_rows,
        },
    )
    _write_json(
        evidence / "04_CAPTURE_REPORT.json",
        {
            "status": "PASS",
            "capture_before_semantic_parse": True,
            "records": receipt_rows,
            "capture_set": bridge.capture_set.model_dump(mode="json"),
            "closure": bridge.closure.model_dump(mode="json"),
        },
    )
    _write_json(
        evidence / "05_SNAPSHOT_REPORT.json",
        {
            "status": "PASS",
            "snapshot": bridge.snapshot.model_dump(mode="json"),
            "bindings": [item.model_dump(mode="json") for item in bridge.bindings],
            "bridge_verification": bridge_verification,
            "snapshot_root": str(snapshot_root),
        },
    )
    _write_json(
        evidence / "06_BUNDLE_REPORT.json",
        {
            "status": "PASS",
            "bundle_root": str(compiled.bundle_root),
            "bundle_sha256": compiled.manifest["bundle_sha256"],
            "receipt_sha256": compiled.receipt["receipt_sha256"],
            "manifest_file_sha256": hashlib.sha256(
                (compiled.bundle_root / "BUNDLE_MANIFEST.json").read_bytes()
            ).hexdigest(),
            "receipt_file_sha256": hashlib.sha256(
                (compiled.bundle_root / "RECEIPT.json").read_bytes()
            ).hexdigest(),
            "verification": compiled.verification,
            "research_commit": research_commit,
            "research_tree": research_tree,
        },
    )
    timings["normal_evidence_export_seconds"] = round(time.monotonic() - stage, 6)
    timings["total_seconds"] = round(time.monotonic() - total_started, 6)
    context = {
        "authority_time": authority_time,
        "request": request.model_dump(mode="json"),
        "plan": plan.model_dump(mode="json"),
        "live_root": str(live_root),
        "snapshot_root": str(snapshot_root),
        "closure_sha256": bridge.closure.closure_sha256,
        "bundle_root": str(compiled.bundle_root),
        "bundle_sha256": compiled.manifest["bundle_sha256"],
        "receipt_sha256": compiled.receipt["receipt_sha256"],
        "monotonic_counter": args.monotonic_counter,
        "research_root": str(ROOT),
        "timings_seconds": timings,
    }
    _write_json(args.run_root / "run_context.json", context)
    _write_json(
        evidence / "07_STAGE_TIMINGS.json",
        {
            "status": "PASS",
            "manual_intervention_count": 0,
            "provider_outcomes": {
                row["provider_id"]: row["status"] for row in acquisition_rows
            },
            "timings_seconds": timings,
        },
    )
    print(
        json.dumps(
            {
                "status": "PASS",
                "ticker": args.ticker,
                "snapshot_sha256": bridge.snapshot.snapshot_sha256,
                "closure_sha256": bridge.closure.closure_sha256,
                "bundle_sha256": compiled.manifest["bundle_sha256"],
                "receipt_sha256": compiled.receipt["receipt_sha256"],
                "bundle_root": str(compiled.bundle_root),
                "timings_seconds": timings,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
