#!/usr/bin/env python3
"""Execute RFC-0011 R4 canonical XOM live-binding/replay and JPM period proof."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from research_agent.alpha_shared.contracts import SharedBaseInputIR, SupplementalCompileInputIR
from research_agent.alpha_shared.raw_inventory import build_source_snapshot_fact_inventory
from research_agent.alpha_shared.runner import replay_canonical_alpha_case, run_canonical_alpha_case
from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.semantic_compiler.source_frontend.contracts import SourceSnapshotIR


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _base(snapshot_report_path: Path) -> SharedBaseInputIR:
    report = json.loads(snapshot_report_path.read_text(encoding="utf-8"))
    snapshot = SourceSnapshotIR.model_validate(report["snapshot"])
    return SharedBaseInputIR.from_snapshot(
        snapshot=snapshot,
        snapshot_root=Path(report["snapshot_root"]),
    )


def _compile(args: argparse.Namespace) -> int:
    base = _base(args.xom_snapshot_report)
    prior = json.loads(args.r3_result.read_text(encoding="utf-8"))
    supplemental = SupplementalCompileInputIR.model_validate(prior["supplemental_input"])
    common = {
        "base_input": base,
        "supplemental_input": supplemental,
        "archetype_profile_id": "energy",
        "output_root": args.output / "bundle",
        "ledger_path": args.output / "operations.jsonl",
        "research_commit": args.research_commit,
        "research_tree": args.research_tree,
        "monotonic_counter": args.counter,
    }
    result = (
        run_canonical_alpha_case(**common, acquisition_mode="verified_live_capture")
        if args.case_mode == "live"
        else replay_canonical_alpha_case(**common)
    )
    manifest_bytes = (result.compiled.bundle_root / "BUNDLE_MANIFEST.json").read_bytes()
    receipt_bytes = (result.compiled.bundle_root / "RECEIPT.json").read_bytes()
    raw = result.compiled.raw_inventory
    duration_concepts = {
        "Revenues": "revenue",
        "RevenueFromContractWithCustomerExcludingAssessedTax": "revenue",
        "NetIncomeLoss": "net_income",
        "EarningsPerShareDiluted": "eps",
        "NetCashProvidedByUsedInOperatingActivities": "operating_cash_flow",
        "PaymentsToAcquirePropertyPlantAndEquipment": "capital_expenditure",
    }
    duration_rows = [
        item
        for item in raw.candidates
        if item.concept in duration_concepts and item.preliminary_duration_role != "INSTANT"
    ]
    report = {
        "contract_id": "room16.rfc0011.r4.canonical_case_execution",
        "contract_version": 1,
        "status": "PASS",
        "case_mode": args.case_mode,
        "base_input": base.model_dump(mode="json"),
        "supplemental_input_sha256": supplemental.input_sha256,
        "runner_report": result.report,
        "compile_identity": result.compiled.manifest["compile_identity"],
        "bundle_sha256": result.compiled.manifest["bundle_sha256"],
        "bundle_manifest_file_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "receipt_sha256": result.compiled.receipt["receipt_sha256"],
        "receipt_file_sha256": hashlib.sha256(receipt_bytes).hexdigest(),
        "internal_report": result.compiled.internal_report.model_dump(mode="json"),
        "raw_inventory": {
            "inventory_sha256": raw.inventory_sha256,
            "candidate_count": len(raw.candidates),
            "market_candidate_count": sum(
                item.source_kind == "market_price" for item in raw.candidates
            ),
            "excluded_count": len(raw.exclusions),
            "duplicate_count": raw.dedupe_receipt.duplicate_count,
            "duration_proof_count": len(duration_rows),
            "duration_proof_by_metric": {
                metric: sum(duration_concepts[item.concept] == metric for item in duration_rows)
                for metric in sorted(set(duration_concepts.values()))
            },
            "instant_misclassification_count": sum(
                item.start_or_null is not None and item.preliminary_duration_role == "INSTANT"
                for item in raw.candidates
            ),
        },
        "ledger_report": result.compiled.ledger_report,
    }
    _write_json(args.output / "result.json", report)
    print(json.dumps({"status": "PASS", "case_mode": args.case_mode}, sort_keys=True))
    return 0


def _jpm_proof(path: Path) -> dict[str, object]:
    inventory = build_source_snapshot_fact_inventory(_base(path))
    groups: dict[tuple[str, str, str], set[str]] = {}
    for item in inventory.candidates:
        if item.preliminary_duration_role in {"STANDALONE_QUARTER", "YEAR_TO_DATE"}:
            groups.setdefault((item.concept, item.unit, item.end), set()).add(
                item.preliminary_duration_role
            )
    dual = sorted((key, sorted(roles)) for key, roles in groups.items() if len(roles) == 2)
    if not dual:
        raise RuntimeError("R4_JPM_QUARTER_YTD_PROOF_MISSING")
    return {
        "contract_id": "room16.rfc0011.r4.jpm_period_basis_proof",
        "contract_version": 1,
        "status": "PASS",
        "snapshot_sha256": inventory.source_snapshot_sha256,
        "inventory_sha256": inventory.inventory_sha256,
        "candidate_count": len(inventory.candidates),
        "excluded_count": len(inventory.exclusions),
        "quarter_ytd_same_concept_unit_end_count": len(dual),
        "examples": [
            {"concept": key[0], "unit": key[1], "end": key[2], "roles": roles}
            for key, roles in dual[:25]
        ],
        "network_query_count": 0,
    }


def _parent(args: argparse.Namespace) -> int:
    if args.output.exists():
        raise SystemExit(f"output already exists: {args.output}")
    results = []
    for case_mode in ("live", "replay"):
        destination = args.output / case_mode
        subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "--mode",
                "compile",
                "--case-mode",
                case_mode,
                "--output",
                str(destination),
                "--xom-snapshot-report",
                str(args.xom_snapshot_report),
                "--jpm-snapshot-report",
                str(args.jpm_snapshot_report),
                "--r3-result",
                str(args.r3_result),
                "--research-commit",
                args.research_commit,
                "--research-tree",
                args.research_tree,
                "--counter",
                str(args.counter),
            ],
            check=True,
        )
        results.append(json.loads((destination / "result.json").read_text(encoding="utf-8")))
    live, replay = results
    comparison_fields = (
        "bundle_sha256",
        "bundle_manifest_file_sha256",
        "receipt_sha256",
        "receipt_file_sha256",
        "internal_report",
        "raw_inventory",
    )
    comparisons = {
        field: {
            "live_sha256": sha256_json(live[field]),
            "replay_sha256": sha256_json(replay[field]),
            "match": live[field] == replay[field],
        }
        for field in comparison_fields
    }
    if not all(item["match"] for item in comparisons.values()):
        raise RuntimeError("R4_CANONICAL_LIVE_REPLAY_SEMANTIC_DRIFT")
    if live["runner_report"]["live_network_call_count"] < 2:
        raise RuntimeError("R4_LIVE_PROVIDER_TELEMETRY_MISSING")
    if replay["runner_report"]["live_network_call_count"] != 0:
        raise RuntimeError("R4_REPLAY_PROVIDER_CALLS_NONZERO")
    jpm = _jpm_proof(args.jpm_snapshot_report)
    summary = {
        "contract_id": "room16.rfc0011.r4.integrated_validation",
        "contract_version": 1,
        "status": "PASS",
        "xom_live_base_capture_query_count": 2,
        "xom_live": live,
        "xom_replay": replay,
        "live_replay_comparisons": comparisons,
        "jpm_period_proof": jpm,
        "holdout_live_query_count": 0,
        "fixed24_query_count": 0,
        "fixed24_run_count": 0,
        "fixed24_batch_authorized": False,
        "product_report_v2": False,
    }
    _write_json(args.output / "INTEGRATED_VALIDATION_SUMMARY.json", summary)
    print(json.dumps({"status": "PASS", "ticker": "XOM"}, sort_keys=True))
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("parent", "compile"), default="parent")
    parser.add_argument("--case-mode", choices=("live", "replay"), default="replay")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--xom-snapshot-report", required=True, type=Path)
    parser.add_argument("--jpm-snapshot-report", required=True, type=Path)
    parser.add_argument("--r3-result", required=True, type=Path)
    parser.add_argument("--research-commit", required=True)
    parser.add_argument("--research-tree", required=True)
    parser.add_argument("--counter", required=True, type=int)
    return parser


def main() -> int:
    args = _parser().parse_args()
    return _compile(args) if args.mode == "compile" else _parent(args)


if __name__ == "__main__":
    raise SystemExit(main())
