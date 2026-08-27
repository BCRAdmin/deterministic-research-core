#!/usr/bin/env python3
"""Execute canonical RFC-0011 R3 XOM compile and fresh-process replay."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from research_agent.alpha_shared.contracts import (
    DocumentObservationIR,
    SharedBaseInputIR,
    SupplementalCompileInputIR,
)
from research_agent.alpha_shared.runner import run_shared_case
from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.semantic_compiler.source_frontend.contracts import SourceSnapshotIR


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _compile(args: argparse.Namespace) -> int:
    snapshot_report = json.loads(args.snapshot_report.read_text(encoding="utf-8"))
    snapshot = SourceSnapshotIR.model_validate(snapshot_report["snapshot"])
    base = SharedBaseInputIR.from_snapshot(
        snapshot=snapshot,
        snapshot_root=Path(snapshot_report["snapshot_root"]),
    )
    authority = json.loads(args.supplemental_authority.read_text(encoding="utf-8"))
    observations = tuple(
        DocumentObservationIR.model_validate(item)
        for item in json.loads(args.supplemental_observations.read_text(encoding="utf-8"))
    )
    supplemental = SupplementalCompileInputIR.create(
        supplemental_policy_sha256=authority["policy"]["policy_sha256"],
        discovery_set_sha256=authority["candidate_set"]["set_sha256"],
        supplemental_evidence_set_sha256=authority["evidence_set"]["evidence_set_sha256"],
        observations=observations,
    )
    result = run_shared_case(
        base_input=base,
        supplemental_input=supplemental,
        archetype_profile_id="energy",
        output_root=args.output / "bundle",
        ledger_path=args.output / "operations.jsonl",
        research_commit=args.research_commit,
        research_tree=args.research_tree,
        monotonic_counter=args.counter,
    )
    manifest_bytes = (result.compiled.bundle_root / "BUNDLE_MANIFEST.json").read_bytes()
    receipt_bytes = (result.compiled.bundle_root / "RECEIPT.json").read_bytes()
    report = {
        "contract_id": "room16.rfc0011.r3.canonical_live_case_report",
        "contract_version": 1,
        "status": "PASS",
        "ticker": base.ticker,
        "process_mode": "fresh_process_offline_from_immutable_live_capture",
        "network_query_count": 0,
        "base_input": base.model_dump(mode="json"),
        "supplemental_input": supplemental.model_dump(mode="json"),
        "compile_identity": result.compiled.manifest["compile_identity"],
        "bundle_sha256": result.compiled.manifest["bundle_sha256"],
        "bundle_manifest_file_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "receipt_sha256": result.compiled.receipt["receipt_sha256"],
        "receipt_file_sha256": hashlib.sha256(receipt_bytes).hexdigest(),
        "verification": result.compiled.verification,
        "period_receipts": list(result.compiled.period_receipts),
        "resolution_receipts": list(result.compiled.resolution_receipts),
        "supplemental_candidate_receipts": list(result.compiled.supplemental_candidate_receipts),
        "runner_report": result.report,
        "ledger_report": result.compiled.ledger_report,
    }
    _write_json(args.output / "result.json", report)
    print(json.dumps({"status": "PASS", "ticker": base.ticker}, sort_keys=True))
    return 0


def _parent(args: argparse.Namespace) -> int:
    if args.output.exists():
        raise SystemExit(f"output already exists: {args.output}")
    results = []
    for name in ("live_compile", "fresh_process_replay"):
        destination = args.output / name
        command = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--mode",
            "compile",
            "--output",
            str(destination),
            "--snapshot-report",
            str(args.snapshot_report),
            "--supplemental-authority",
            str(args.supplemental_authority),
            "--supplemental-observations",
            str(args.supplemental_observations),
            "--research-commit",
            args.research_commit,
            "--research-tree",
            args.research_tree,
            "--counter",
            str(args.counter),
        ]
        subprocess.run(command, check=True, cwd=Path.cwd())
        results.append(json.loads((destination / "result.json").read_text(encoding="utf-8")))
    first, replay = results
    comparison_fields = (
        "bundle_sha256",
        "bundle_manifest_file_sha256",
        "receipt_sha256",
        "receipt_file_sha256",
    )
    comparisons = {
        field: {
            "live": first[field],
            "replay": replay[field],
            "match": first[field] == replay[field],
        }
        for field in comparison_fields
    }
    comparisons["supplemental_candidate_receipts"] = {
        "live": sha256_json(first["supplemental_candidate_receipts"]),
        "replay": sha256_json(replay["supplemental_candidate_receipts"]),
        "match": first["supplemental_candidate_receipts"]
        == replay["supplemental_candidate_receipts"],
    }
    comparisons["resolution_receipts"] = {
        "live": sha256_json(first["resolution_receipts"]),
        "replay": sha256_json(replay["resolution_receipts"]),
        "match": first["resolution_receipts"] == replay["resolution_receipts"],
    }
    if not all(item["match"] for item in comparisons.values()):
        raise RuntimeError("RFC0011_R3_FRESH_PROCESS_REPLAY_DRIFT")
    identity = first["compile_identity"]
    base = first["base_input"]
    identity_rows = [
        {
            "field": "compile_request_sha256",
            "source_contract_object": "SourceSnapshotIR.request_sha256",
            "expected_sha": base["snapshot_ir"]["request_sha256"],
            "bundle_compile_identity_sha": identity["compile_request_sha256"],
        },
        {
            "field": "source_acquisition_sha256",
            "source_contract_object": "SourceSnapshotIR.acquisition_plan_sha256",
            "expected_sha": base["snapshot_ir"]["acquisition_plan_sha256"],
            "bundle_compile_identity_sha": identity["source_acquisition_sha256"],
        },
        {
            "field": "retrieval_receipt_set_sha256",
            "source_contract_object": "canonical SourceSnapshotIR.retrieval_receipts",
            "expected_sha": base["retrieval_receipt_set_sha256"],
            "bundle_compile_identity_sha": identity["retrieval_receipt_set_sha256"],
        },
        {
            "field": "source_snapshot_sha256",
            "source_contract_object": "SourceSnapshotIR.snapshot_sha256",
            "expected_sha": base["snapshot_ir"]["snapshot_sha256"],
            "bundle_compile_identity_sha": identity["source_snapshot_sha256"],
        },
    ]
    for row in identity_rows:
        row["match"] = row["expected_sha"] == row["bundle_compile_identity_sha"]
    if not all(row["match"] for row in identity_rows):
        raise RuntimeError("RFC0011_R3_COMPILE_IDENTITY_DRIFT")
    summary = {
        "contract_id": "room16.rfc0011.r3.canonical_live_validation",
        "contract_version": 1,
        "status": "PASS",
        "ticker": "XOM",
        "live_base_capture_query_count": 2,
        "supplemental_capture_mode": "existing_durable_rfc0011_capture",
        "supplemental_replay_network_query_count": 0,
        "holdout_live_query_count": 0,
        "fixed24_query_count": 0,
        "fixed24_batch_authorized": False,
        "identity_rows": identity_rows,
        "fresh_process_comparisons": comparisons,
        "bundle_sha256": first["bundle_sha256"],
        "receipt_sha256": first["receipt_sha256"],
        "supplemental_candidate_receipts": first["supplemental_candidate_receipts"],
        "runner_report": first["runner_report"],
        "h4_ledger": first["ledger_report"],
    }
    _write_json(args.output / "INTEGRATED_VALIDATION_SUMMARY.json", summary)
    print(json.dumps({"status": "PASS", "ticker": "XOM"}, sort_keys=True))
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("parent", "compile"), default="parent")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--snapshot-report", required=True, type=Path)
    parser.add_argument("--supplemental-authority", required=True, type=Path)
    parser.add_argument("--supplemental-observations", required=True, type=Path)
    parser.add_argument("--research-commit", required=True)
    parser.add_argument("--research-tree", required=True)
    parser.add_argument("--counter", required=True, type=int)
    return parser


def main() -> int:
    args = _parser().parse_args()
    return _compile(args) if args.mode == "compile" else _parent(args)


if __name__ == "__main__":
    raise SystemExit(main())
