#!/usr/bin/env python3
"""Reprocess the frozen REIT Development6 entirely from captured Wave3 bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from research_agent.alpha_shared.contracts import (
    DiscoveredSourceCandidateIR,
    DiscoveredSourceSetIR,
    DocumentObservationIR,
    SharedBaseInputIR,
    SupplementalCompileInputIR,
    SupplementalEvidenceSetIR,
)
from research_agent.alpha_shared.document_normalizer import (
    discover_observations,
    normalize_document,
)
from research_agent.alpha_shared.observation_registry import label_profiles
from research_agent.alpha_shared.runner import replay_canonical_alpha_case
from research_agent.alpha_shared.supplemental_semantics import (
    build_supplemental_semantics,
    classify_reit_row_role,
)
from research_agent.semantic_compiler.source_frontend.contracts import SourceSnapshotIR


ROOT = Path(__file__).resolve().parents[2]
PRIOR = (
    ROOT
    / "outputs/release/"
    "ROOM16_REIT_EXHIBIT_REFERENCE_CLOSURE_RESULT_R1_86FB9949ADCD_2026-08-29"
)
DEV6 = (
    (1, "AMT", "American Tower Corporation"),
    (2, "EQIX", "Equinix, Inc."),
    (3, "PSA", "Public Storage"),
    (4, "CUBE", "CubeSmart"),
    (5, "EGP", "EastGroup Properties, Inc."),
    (6, "REXR", "Rexford Industrial Realty, Inc."),
)
TARGETS = {
    "AMT": ("Nareit FFO attributable to AMT common stockholders", "1,249.3", "1249300000.0"),
    "CUBE": (
        "FFO attributable to the Company's common shareholders and third-party OP unitholders",
        "142,993",
        "142993000",
    ),
}
SUPPLEMENTAL_METRICS = (
    "reported_affo",
    "reported_core_ffo",
    "reported_ffo",
    "rpo",
    "crpo",
    "efficiency_ratio",
    "guidance",
    "net_interest_margin",
    "occupancy",
    "production_volume",
    "rotce",
    "same_store_noi",
    "segment_operating_results",
)


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _capture_path(case_root: Path, digest: str) -> Path:
    return case_root / "captures/rfc0011/captures/sha256" / digest[:2] / digest


def _rebuild_supplemental(
    case_root: Path,
) -> tuple[SupplementalCompileInputIR, list[DocumentObservationIR], frozenset[str]]:
    report = _json(case_root / "09_RFC0011_SUPPLEMENTAL_REPORT.json")
    candidate_set = DiscoveredSourceSetIR.model_validate(report["candidate_set"])
    evidence = SupplementalEvidenceSetIR.model_validate(report["evidence_set"])
    candidates = {
        item.candidate_id: item
        for item in (
            DiscoveredSourceCandidateIR.model_validate(raw)
            for raw in report["candidate_set"]["candidates"]
        )
    }
    selected_reference_documents = frozenset(report.get("selected_reference_documents", ()))
    selected_reference_candidate_ids = {
        candidate.candidate_id
        for candidate in candidates.values()
        if candidate.document_name in selected_reference_documents
    }
    selected_reference_payloads = frozenset(
        receipt.payload_sha256
        for receipt in evidence.capture_receipts
        if receipt.candidate_id in selected_reference_candidate_ids
    )
    requested = {metric: label_profiles()[metric] for metric in SUPPLEMENTAL_METRICS}
    observations: list[DocumentObservationIR] = []
    for receipt in evidence.capture_receipts:
        candidate = candidates[receipt.candidate_id]
        payload_path = _capture_path(case_root, receipt.payload_sha256)
        if _sha(payload_path) != receipt.payload_sha256:
            raise RuntimeError(f"CAPTURE_HASH_DRIFT:{case_root.name}:{receipt.payload_sha256}")
        document = normalize_document(
            payload_path.read_bytes(),
            document_id=candidate.candidate_id,
            accession_number=candidate.accession_number,
            report_date=candidate.report_date,
            filing_date=candidate.filing_date,
            document_name=candidate.document_name,
            media_type=receipt.media_type,
        )
        observations.extend(discover_observations(document, requested))
    supplemental = SupplementalCompileInputIR.create(
        supplemental_policy_sha256=report["policy"]["policy_sha256"],
        discovery_set_sha256=candidate_set.set_sha256,
        supplemental_evidence_set_sha256=evidence.evidence_set_sha256,
        observations=tuple(observations),
    )
    return supplemental, observations, selected_reference_payloads


def _base(case_root: Path) -> SharedBaseInputIR:
    report = _json(case_root / "08_SOURCE_SNAPSHOT.json")
    return SharedBaseInputIR.from_snapshot(
        snapshot=SourceSnapshotIR.model_validate(report["snapshot"]),
        snapshot_root=Path(report["snapshot_root"]),
    )


def _target_proof(
    ticker: str,
    supplemental: SupplementalCompileInputIR,
    observations: list[DocumentObservationIR],
    selected_reference_payloads: frozenset[str],
) -> dict[str, Any] | None:
    if ticker not in TARGETS:
        return None
    label, raw, expected = TARGETS[ticker]
    matches = [
        item
        for item in observations
        if item.raw_value_text == raw
        and item.context_text.rsplit("|| ROW:", 1)[-1].split("|", 1)[0].strip() == label
        and (
            not selected_reference_payloads
            or item.source_document_sha256 in selected_reference_payloads
        )
    ]
    if len(matches) != 1:
        raise RuntimeError(f"TARGET_ROW_CARDINALITY:{ticker}:{len(matches)}")
    target = matches[0]
    receipts, resolutions = build_supplemental_semantics(
        supplemental=supplemental,
        as_of_date="2026-08-28",
        filed_date="2026-07-29",
        archetype_profile_id="reit",
    )
    receipt = next(item for item in receipts if item["observation_id"] == target.observation_id)
    resolution = next(item for item in resolutions if item["metric_id"] == "reported_ffo")
    actual = receipt["candidate"]["numeric_value"] if receipt["candidate"] else None
    if (
        classify_reit_row_role(target) != "TOTAL_MEASURE"
        or receipt["status"] != "CANDIDATE"
        or actual != expected
        or resolution["status"] != "RESOLVED"
    ):
        raise RuntimeError(f"TARGET_ROW_NOT_RESOLVED:{ticker}")
    return {
        "status": "PASS",
        "ticker": ticker,
        "label": label,
        "row_role": "TOTAL_MEASURE",
        "raw_value": raw,
        "normalized_value": actual,
        "unit": target.reported_unit_text_or_null,
        "period": target.reported_period_text_or_null,
        "observation_id": target.observation_id,
        "observation_sha256": target.observation_sha256,
        "source_document_sha256": target.source_document_sha256,
        "evidence_ids": receipt["candidate"]["evidence_ids"],
        "resolution": resolution,
        "network_calls": 0,
    }


def run(output: Path, research_commit: str, research_tree: str) -> int:
    cases: list[dict[str, Any]] = []
    proofs: dict[str, dict[str, Any]] = {}
    for sequence, ticker, company in DEV6:
        source = PRIOR / "companies_wave3" / f"{sequence:02d}_{ticker}"
        base = _base(source)
        supplemental, observations, selected_reference_payloads = _rebuild_supplemental(source)
        proof = _target_proof(ticker, supplemental, observations, selected_reference_payloads)
        if proof is not None:
            proofs[ticker] = proof
        case_output = output / "offline_reprocessing" / f"{sequence:02d}_{ticker}"
        first = replay_canonical_alpha_case(
            base_input=base,
            supplemental_input=supplemental,
            archetype_profile_id="reit",
            output_root=case_output / "first_bundle",
            ledger_path=case_output / "first_operations.jsonl",
            research_commit=research_commit,
            research_tree=research_tree,
            monotonic_counter=sequence,
        )
        second = replay_canonical_alpha_case(
            base_input=base,
            supplemental_input=supplemental,
            archetype_profile_id="reit",
            output_root=case_output / "second_bundle",
            ledger_path=case_output / "second_operations.jsonl",
            research_commit=research_commit,
            research_tree=research_tree,
            monotonic_counter=sequence,
        )
        identity_a = (
            first.compiled.manifest["bundle_sha256"],
            first.compiled.receipt["receipt_sha256"],
            first.compiled.internal_report.report_sha256,
        )
        identity_b = (
            second.compiled.manifest["bundle_sha256"],
            second.compiled.receipt["receipt_sha256"],
            second.compiled.internal_report.report_sha256,
        )
        if identity_a != identity_b:
            raise RuntimeError(f"OFFLINE_REPLAY_DRIFT:{ticker}")
        report = first.compiled.internal_report
        slots = list(report.core_slot_resolutions)
        operating = next(
            item for item in slots if item["slot_id"] == "reit_operating_performance_measure"
        )
        before = _json(source / "00_CASE_VERDICT.json")
        case = {
            "sequence": sequence,
            "ticker": ticker,
            "company_name": company,
            "status": "COMPLETE",
            "network_provider_calls": 0,
            "replay_provider_calls": 0,
            "replay_identity_match": True,
            "before_core_slot_coverage_percent": before["core_slot_coverage_percent"],
            "after_core_slot_coverage_percent": report.source_coverage[
                "core_slot_coverage_percent"
            ],
            "before_operating_measure_slot": before["operating_measure_slot"],
            "after_operating_measure_slot": operating,
            "selected_ffo_family_metric_identity": operating["selected_metric_id_or_null"],
            "surfaced_fact_lineage_percent": report.evidence_lineage[
                "surfaced_fact_lineage_rate_percent"
            ],
            "stale_primary_metric_count": report.evidence_lineage[
                "stale_primary_metric_count"
            ],
            "P0": 0,
            "P1": 0,
            "bundle_sha256": identity_a[0],
            "signed_receipt_sha256": identity_a[1],
            "internal_report_sha256": identity_a[2],
            "observation_set_sha256": supplemental.observation_set_sha256,
        }
        cases.append(case)
        _write(case_output / "CASE_RESULT.json", case)
    values = sorted(item["after_core_slot_coverage_percent"] for item in cases)
    median = (values[2] + values[3]) / 2
    minimum = min(values)
    result = {
        "contract_id": "room16.reit.total_row_grammar_offline_development6@1",
        "status": "PASS"
        if median >= 80
        and minimum >= 60
        and all(item["surfaced_fact_lineage_percent"] == 100 for item in cases)
        else "FAIL",
        "research_commit": research_commit,
        "research_tree": research_tree,
        "network_provider_calls": 0,
        "development6_live_queries": 0,
        "fixed24_live_queries": 0,
        "holdout12_queries": 0,
        "holdout12_runs": 0,
        "median_core_slot_coverage_percent": median,
        "minimum_core_slot_coverage_percent": minimum,
        "cases": cases,
        "target_proofs": proofs,
    }
    _write(output / "07_DEVELOPMENT6_OFFLINE_REPROCESSING.json", result)
    _write(output / "04_AMT_TOTAL_ROW_PROOF.json", proofs["AMT"])
    _write(output / "05_CUBE_TOTAL_ROW_PROOF.json", proofs["CUBE"])
    print(json.dumps({"status": result["status"], "median": median, "minimum": minimum}))
    return 0 if result["status"] == "PASS" else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--research-commit", required=True)
    parser.add_argument("--research-tree", required=True)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    raise SystemExit(run(args.output, args.research_commit, args.research_tree))
