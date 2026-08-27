#!/usr/bin/env python3
"""Execute RFC-0011 R2 evidence-grounded shared-successor validation offline."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from research_agent.alpha_shared.compiler import compile_shared_successor
from research_agent.alpha_shared.contracts import DocumentObservationIR
from research_agent.alpha_shared.document_normalizer import (
    discover_observations,
    normalize_document,
)
from research_agent.alpha_shared.frozen_evidence import load_frozen_evidence
from research_agent.alpha_shared.observation_registry import label_profiles
from research_agent.ba12_live_source.capture_store import ContentAddressedCaptureStore
from research_agent.compiler_foundation.canonical import sha256_json

DEVELOPMENT = {
    "CRM": ("crpo", "guidance"),
    "JPM": ("efficiency_ratio", "net_interest_margin", "rotce"),
    "PLD": ("adjusted_ffo", "occupancy", "same_store_noi"),
    "XOM": ("production_volume", "segment_operating_results"),
}
HOLDOUTS = ("NOW", "O", "BAC", "CVX")
ARCHETYPE = {
    "CRM": "saas",
    "NOW": "saas",
    "PLD": "reit",
    "O": "reit",
    "JPM": "bank",
    "BAC": "bank",
    "XOM": "energy",
    "CVX": "energy",
}
ZIP_MARKER = {
    "CRM": "CRM_DEVELOPMENT",
    "NOW": "SAAS_WAVE1",
    "PLD": "PLD_REIT",
    "O": "REIT_WAVE2",
    "JPM": "JPM_BANK",
    "BAC": "BANK_WAVE3",
    "XOM": "XOM_ENERGY",
    "CVX": "ENERGY_WAVE4",
}
EXTERNAL_BUNDLE = {
    "O": "RUNS/REIT-WAVE2-CLOSURE-2026-08-26-R1/O/runtime/replay_bundle",
    "BAC": "RUNS/BANK-WAVE3-CLOSURE-2026-08-26-R1/BAC/runtime/replay_bundle",
    "CVX": "RUNS/ENERGY-WAVE4-CLOSURE-2026-08-27-R1/CVX-HOLDOUT/runtime/replay_bundle",
}


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _zip_for(authority_dir: Path, ticker: str) -> Path:
    matches = sorted(
        path for path in authority_dir.glob("*.zip") if ZIP_MARKER[ticker] in path.name
    )
    if len(matches) != 1:
        raise RuntimeError(f"{ticker}: expected one frozen evidence ZIP, found {len(matches)}")
    return matches[0]


def _reprocess_development(
    r1_root: Path,
    output_root: Path,
) -> dict[str, tuple[DocumentObservationIR, ...]]:
    profiles = label_profiles()
    observations_by_ticker: dict[str, tuple[DocumentObservationIR, ...]] = {}
    results = []
    for ticker, metric_ids in sorted(DEVELOPMENT.items()):
        issuer_root = r1_root / ticker
        prior = json.loads((issuer_root / "validation.json").read_text(encoding="utf-8"))
        candidates = {item["candidate_id"]: item for item in prior["candidate_set"]["candidates"]}
        store = ContentAddressedCaptureStore(issuer_root / "capture_store")
        requested = {metric_id: profiles[metric_id] for metric_id in metric_ids}
        observations: list[DocumentObservationIR] = []
        documents = []
        for receipt in prior["evidence_set"]["capture_receipts"]:
            artifact, payload = store.load_verified(receipt["payload_sha256"])
            candidate = candidates[receipt["candidate_id"]]
            document = normalize_document(
                payload,
                document_id=candidate["candidate_id"],
                accession_number=candidate["accession_number"],
                report_date=candidate["report_date"],
                filing_date=candidate["filing_date"],
                document_name=candidate["document_name"],
                media_type=receipt["media_type"],
            )
            if document.source_document_sha256 != artifact.content_sha256:
                raise RuntimeError(f"{ticker}: captured source hash drift")
            issuer_observations = discover_observations(document, requested)
            observations.extend(issuer_observations)
            documents.append(
                {
                    "document_id": document.document_id,
                    "source_document_sha256": document.source_document_sha256,
                    "normalizer_sha256": document.normalizer_sha256,
                    "observation_count": len(issuer_observations),
                    "trusted_numeric_count": sum(
                        item.trusted_numeric for item in issuer_observations
                    ),
                }
            )
        ordered = tuple(sorted(observations, key=lambda item: item.observation_id))
        observations_by_ticker[ticker] = ordered
        trusted = tuple(item for item in ordered if item.trusted_numeric)
        results.append(
            {
                "ticker": ticker,
                "source_mode": "existing_r1_durable_capture_offline_reprocessing",
                "source_evidence_set_sha256": prior["evidence_set_sha256"],
                "network_query_count": 0,
                "documents": documents,
                "observation_count": len(ordered),
                "trusted_numeric_count": len(trusted),
                "positive_result": (
                    "STRUCTURE_BOUND_TRUSTED_NUMERIC"
                    if trusted
                    else "SOURCE_CAPTURED_NUMERIC_EXTRACTION_UNSUPPORTED"
                ),
                "trusted_observations": [item.model_dump(mode="json") for item in trusted],
                "audit_observations": [item.model_dump(mode="json") for item in ordered],
            }
        )
    report = {
        "contract_id": "room16.rfc0011.r2_development_capture_revalidation",
        "contract_version": 1,
        "status": "PASS",
        "queried_tickers": [],
        "network_query_count": 0,
        "holdout_live_query_count": 0,
        "fixed24_query_count": 0,
        "results": results,
    }
    _write_json(output_root / "development_capture_revalidation.json", report)
    return observations_by_ticker


def _compile_child(args: argparse.Namespace) -> int:
    supplemental = tuple(
        DocumentObservationIR.model_validate(item)
        for item in json.loads(args.supplemental.read_text(encoding="utf-8"))
    )
    inventory = load_frozen_evidence(
        args.evidence_zip,
        ticker=args.ticker,
        as_of_date=args.as_of_date,
        artifact_root=args.artifact_root,
    )
    result = compile_shared_successor(
        inventory=inventory,
        archetype_profile_id=args.archetype,
        supplemental_observations=supplemental,
        output_root=args.output / "bundle",
        ledger_path=args.output / "operations.jsonl",
        research_commit=args.research_commit,
        research_tree=args.research_tree,
        monotonic_counter=args.counter,
    )
    report = {
        "status": "PASS",
        "ticker": args.ticker,
        "process_mode": "fresh_process_offline",
        "network_query_count": 0,
        "inventory": inventory.model_dump(mode="json"),
        "bundle_sha256": result.manifest["bundle_sha256"],
        "receipt_sha256": result.receipt["receipt_sha256"],
        "verification": result.verification,
        "period_receipts": list(result.period_receipts),
        "resolution_receipts": list(result.resolution_receipts),
        "ledger_report": result.ledger_report,
    }
    _write_json(args.output / "result.json", report)
    print(json.dumps({"status": "PASS", "ticker": args.ticker}, sort_keys=True))
    return 0


def _run_parent(args: argparse.Namespace) -> int:
    if args.output.exists():
        raise SystemExit(f"output already exists: {args.output}")
    args.output.mkdir(parents=True)
    supplemental = _reprocess_development(args.r1_validation_root, args.output)
    compile_results: dict[str, dict[str, object]] = {}
    for index, ticker in enumerate(sorted((*DEVELOPMENT, *HOLDOUTS)), start=1):
        supplemental_path = args.output / "supplemental" / f"{ticker}.json"
        _write_json(
            supplemental_path,
            [item.model_dump(mode="json") for item in supplemental.get(ticker, ())],
        )
        evidence_zip = _zip_for(args.authority_dir, ticker)
        artifact_root = (
            args.alpha_root / EXTERNAL_BUNDLE[ticker] if ticker in EXTERNAL_BUNDLE else None
        )
        run_reports = []
        for replay in ("run_a", "run_b"):
            destination = args.output / replay / ticker
            command = [
                sys.executable,
                str(Path(__file__).resolve()),
                "--mode",
                "compile",
                "--ticker",
                ticker,
                "--archetype",
                ARCHETYPE[ticker],
                "--evidence-zip",
                str(evidence_zip),
                "--supplemental",
                str(supplemental_path),
                "--output",
                str(destination),
                "--as-of-date",
                args.as_of_date,
                "--research-commit",
                args.research_commit,
                "--research-tree",
                args.research_tree,
                "--counter",
                str(1300 + index),
            ]
            if artifact_root is not None:
                command.extend(("--artifact-root", str(artifact_root)))
            subprocess.run(command, check=True, cwd=Path.cwd())
            run_reports.append(
                json.loads((destination / "result.json").read_text(encoding="utf-8"))
            )
        first, second = run_reports
        if (
            first["bundle_sha256"] != second["bundle_sha256"]
            or first["receipt_sha256"] != second["receipt_sha256"]
            or sha256_json(first["resolution_receipts"])
            != sha256_json(second["resolution_receipts"])
        ):
            raise RuntimeError(f"{ticker}: fresh-process replay identity drift")
        compile_results[ticker] = {
            "status": "PASS",
            "ticker": ticker,
            "mode": "development_capture_plus_frozen_base"
            if ticker in DEVELOPMENT
            else "holdout_frozen_base_only",
            "network_query_count": 0,
            "bundle_sha256": first["bundle_sha256"],
            "receipt_sha256": first["receipt_sha256"],
            "inventory_sha256": first["inventory"]["inventory_sha256"],
            "actual_fact_count": len(first["inventory"]["facts"]),
            "h3_receipt_count": len(first["period_receipts"]),
            "h2_receipt_count": len(first["resolution_receipts"]),
            "h4_event_count": len(first["ledger_report"]["events"]),
            "fresh_process_replay_identical": True,
        }
    summary = {
        "contract_id": "room16.rfc0011.r2_integrated_validation",
        "contract_version": 1,
        "status": "PASS",
        "research_commit": args.research_commit,
        "research_tree": args.research_tree,
        "development_live_query_count": 0,
        "development_existing_capture_replay_count": 4,
        "holdout_live_query_count": 0,
        "fixed24_query_count": 0,
        "fixed24_batch_authorized": False,
        "results": [compile_results[ticker] for ticker in sorted(compile_results)],
    }
    _write_json(args.output / "INTEGRATED_VALIDATION_SUMMARY.json", summary)
    print(json.dumps({"status": "PASS", "issuers": 8}, sort_keys=True))
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("parent", "compile"), default="parent")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--as-of-date", default="2026-08-27")
    parser.add_argument("--research-commit", required=True)
    parser.add_argument("--research-tree", required=True)
    parser.add_argument("--authority-dir", type=Path)
    parser.add_argument("--r1-validation-root", type=Path)
    parser.add_argument("--alpha-root", type=Path)
    parser.add_argument("--ticker")
    parser.add_argument("--archetype")
    parser.add_argument("--evidence-zip", type=Path)
    parser.add_argument("--artifact-root", type=Path)
    parser.add_argument("--supplemental", type=Path)
    parser.add_argument("--counter", type=int)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.mode == "compile":
        return _compile_child(args)
    required = (args.authority_dir, args.r1_validation_root, args.alpha_root)
    if any(value is None for value in required):
        raise SystemExit("parent mode requires authority, R1 validation, and Alpha roots")
    return _run_parent(args)


if __name__ == "__main__":
    raise SystemExit(main())
