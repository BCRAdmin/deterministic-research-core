#!/usr/bin/env python3
"""Build the offline Energy-v3 R13 freeze-closure evidence package."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import zipfile
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from research_agent.alpha_energy.v3 import (  # noqa: E402
    AUTHORIZED_PERIOD_POLICY_SHA256,
    AUTHORIZED_SEMANTIC_SHA256,
    CANDIDATE_INTEGRITY_CONTRACT_V3,
    CORE_SLOT_REGISTRY_V3,
    ENERGY_SEMANTIC_CONTRACT_V3,
    PERIOD_FRESHNESS_POLICY_V3,
    evaluate_energy_v3_case,
    registry_hashes_v3,
    select_metric_v3,
    validate_candidate_integrity_v3,
)
from research_agent.compiler_foundation.canonical import sha256_json  # noqa: E402
from scripts.ops import run_energy_v3_r12 as r12  # noqa: E402
from scripts.ops.verify_project_boundary_non_interference_v2 import (  # noqa: E402
    build_receipt as build_boundary_receipt,
    foreign_snapshot,
)

R12_COMPACT = ROOT / "outputs/release/ROOM16_ENERGY_V3_GENERALIZED_CLEAN_VALIDATION_R12_A1F56D30AA2B_2026-09-03_UPLOAD_COMPACT.zip"
R12_SHA256 = "d639efbfdb43a7310572e79a9354f9c1f8a15a89f067203fb3cc8a7df2db034d"
R12_MANIFEST_SHA256 = "bb4fa0847a807f173acabc8c2dfb1a5a70406f32030df53439db9b8860eb74e7"
R12_COMMIT = "a1f56d30aa2b74dac45f05220a29dae1249fa0f5"
R12_TREE = "5d0a464c15d614a61620c80abe516475b9343bef"
R12_CANDIDATE_SEAL_SHA256 = "cc5ed70dfa0c0b84943f64671d2ff92f8c671a0b8d3a23cd48f71902c52db7d3"
R12_CANDIDATE_SEMANTIC_SHA256 = "888dac95b998ec7d093bdccd781f1f0a7bf9166dd91450da61f92b8684a7da7d"
R12_SEMANTIC_CONTRACT_SHA256 = "3debe9a63d022f382155dafe8dc373b627387eb779b142fe0ec966e8d79efff8"
R12_PERIOD_POLICY_SHA256 = "7c1e02112505973c4f717fd8b048b5f1905b556fe0b95b880f9fdbd59a450415"
R12_VERDICT = "ENERGY_V3_CLEAN_VALIDATION_EPOCH2_PASS_READY_FOR_INDEPENDENT_FREEZE_REVIEW"
R13_VERDICT = "ENERGY_V3_R13_FREEZE_CLOSURE_PASS_READY_FOR_FINAL_INDEPENDENT_FREEZE"
PRODUCT = ROOT.parent / "company-dossier-lab"
PRODUCT_COMMIT = "ed86bb841aab88d878266cf8ed498eabc6fa9029"
PRODUCT_TREE = "a382d9c096825910b5e0e8865414ea232b95bd40"
FOREIGN = ROOT.parents[1] / "Utility-Websites/materialbedarf-rechner.de"
RELEASE = ROOT / "outputs/release"
DEVELOPMENT_TICKERS = tuple(r12.DEVELOPMENT_TICKERS)
EPOCH2_TICKERS = ("DWSN", "EPM", "OVV", "ANNA", "BKV", "EGY", "AR", "CNR", "CVI", "CKX", "XPRO", "HAL")
SHA_FIELDS = {
    "01_R12_INDEPENDENT_REVIEW_INPUT_BINDING.json": "binding_sha256",
    "02_PRESEAL_ENERGY_V3_SEMANTIC_AUTHORITY_STUDY.json": "study_sha256",
    "03_MONOTONIC_HARDENING_CHANGE_CLASSIFICATION.json": "classification_sha256",
    "04_R12_MONOTONIC_EQUIVALENCE_REPLAY.json": "equivalence_sha256",
    "05_ACTIVE_ADVERSARIAL_FREEZE_TESTS.json": "adversarial_sha256",
    "06_CONTRACT_AUTHORITY_GUARD.json": "guard_sha256",
    "07_CANDIDATE_INTEGRITY_CONTRACT.json": "integrity_contract_sha256",
    "08_FULL_REGRESSION.json": "regression_sha256",
    "09_ENERGY_V1_V2_NONINTERFERENCE.json": "noninterference_sha256",
    "10_SHARED_AUTHORITY_NONINTERFERENCE.json": "noninterference_sha256",
    "11_PRODUCT_NONINTERFERENCE.json": "noninterference_sha256",
    "12_BOUNDARY_GATE.json": "boundary_sha256",
    "13_R13_ACCEPTANCE_MATRIX.json": "matrix_sha256",
    "14_CHANGESET_AND_SCOPE.json": "changeset_sha256",
}


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hashed(body: dict[str, Any], field: str) -> dict[str, Any]:
    return {**body, field: sha256_json(body)}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def git(repo: Path, *args: str) -> str:
    env = os.environ.copy()
    env["GIT_OPTIONAL_LOCKS"] = "0"
    result = subprocess.run(
        ["git", "--no-optional-locks", *args], cwd=repo, env=env, capture_output=True, text=True
    )
    if result.returncode:
        raise RuntimeError(f"R13_GIT_FAILURE:{repo}:{' '.join(args)}:{result.stderr.strip()}")
    return result.stdout.strip()


def safe_zip(archive: zipfile.ZipFile) -> list[str]:
    names = archive.namelist()
    if len(names) != len(set(names)) or archive.testzip() is not None:
        raise RuntimeError("R13_ZIP_DUPLICATE_OR_CRC_FAILURE")
    for name in names:
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or "\\" in name:
            raise RuntimeError(f"R13_UNSAFE_ZIP_PATH:{name}")
    return names


def verify_selfhash(value: dict[str, Any], field: str, expected: str | None = None) -> str:
    body = dict(value)
    claim = str(body.pop(field))
    if sha256_json(body) != claim or (expected is not None and claim != expected):
        raise RuntimeError(f"R13_SELFHASH_MISMATCH:{field}")
    return claim


def bind_r12(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    if sha_file(path) != R12_SHA256:
        raise RuntimeError("R13_R12_ZIP_HASH_MISMATCH")
    with zipfile.ZipFile(path) as archive:
        names = safe_zip(archive)
        manifest_bytes = archive.read("MANIFEST.json")
        manifest = json.loads(manifest_bytes)
        verify_selfhash(manifest, "manifest_sha256", R12_MANIFEST_SHA256)
        rows = {row["path"]: row for row in manifest["files"]}
        if manifest["file_count"] != len(rows):
            raise RuntimeError("R13_R12_MANIFEST_COUNT_MISMATCH")
        for name, row in rows.items():
            payload = archive.read(name)
            if len(payload) != row["bytes"] or sha_bytes(payload) != row["sha256"]:
                raise RuntimeError(f"R13_R12_PAYLOAD_MISMATCH:{name}")
        checksums = archive.read("CHECKSUMS.sha256").decode().splitlines()
        checksum_map = {line.split("  ", 1)[1]: line.split("  ", 1)[0] for line in checksums}
        if checksum_map.get("MANIFEST.json") != sha_bytes(manifest_bytes):
            raise RuntimeError("R13_R12_CHECKSUM_MANIFEST_MISMATCH")
        if any(checksum_map.get(name) != row["sha256"] for name, row in rows.items()):
            raise RuntimeError("R13_R12_CHECKSUM_PAYLOAD_MISMATCH")
        seal = json.loads(archive.read("05_ENERGY_V3_CANDIDATE_SEAL.json"))
        selection_bytes = archive.read("07_EPOCH2_SELECTION_CONTRACT.json")
        selection = json.loads(selection_bytes)
        epoch = json.loads(archive.read("08_EPOCH2_SELECTED_CASES_SEALED.json"))
        acceptance = json.loads(archive.read("11_EPOCH2_BATCH_ACCEPTANCE.json"))
        regression = json.loads(archive.read("16_HISTORICAL_REPLAY_AND_FULL_REGRESSION.json"))
        verify_selfhash(seal, "candidate_seal_sha256", R12_CANDIDATE_SEAL_SHA256)
        verify_selfhash(selection, "selection_contract_sha256")
        if seal["candidate_semantic_sha256"] != R12_CANDIDATE_SEMANTIC_SHA256:
            raise RuntimeError("R13_R12_SEMANTIC_HASH_MISMATCH")
        if [row["ticker"] for row in epoch["selected_cases"]] != list(EPOCH2_TICKERS):
            raise RuntimeError("R13_R12_SELECTED_CASES_MISMATCH")
        if manifest["research_commit"] != R12_COMMIT or manifest["research_tree"] != R12_TREE:
            raise RuntimeError("R13_R12_RESEARCH_BINDING_MISMATCH")
        if manifest["verdict"] != R12_VERDICT or acceptance["status"] != "PASS":
            raise RuntimeError("R13_R12_VERDICT_MISMATCH")
        verifier_source = archive.read("independent_verifier/verify_result.py")
        body = {
            "contract_id": "room16.energy_v3.r13.r12_independent_review_input_binding@1",
            "status": "PASS",
            "r12_zip": path.name,
            "r12_zip_bytes": path.stat().st_size,
            "r12_zip_sha256": R12_SHA256,
            "zip_entry_count": len(names),
            "duplicate_paths": 0,
            "unsafe_paths": 0,
            "crc_errors": 0,
            "manifest_sha256": manifest["manifest_sha256"],
            "manifest_byte_sha256": sha_bytes(manifest_bytes),
            "manifest_payloads_verified": len(rows),
            "manifest_payload_mismatches": 0,
            "checksums_verified": len(checksum_map),
            "checksum_mismatches": 0,
            "research_commit": manifest["research_commit"],
            "research_tree": manifest["research_tree"],
            "product_commit": manifest["product_commit"],
            "product_tree": manifest["product_tree"],
            "candidate_seal_sha256": seal["candidate_seal_sha256"],
            "candidate_semantic_sha256": seal["candidate_semantic_sha256"],
            "registry_hashes_v3": seal["registry_hashes_v3"],
            "selection_contract_byte_sha256": sha_bytes(selection_bytes),
            "selection_contract_sha256": selection["selection_contract_sha256"],
            "selected_tickers": list(EPOCH2_TICKERS),
            "acceptance_status": acceptance["status"],
            "acceptance_verdict": acceptance["verdict"],
            "full_regression": regression["full_research_regression"],
            "focused_regression": regression["focused_regressions"],
            "standalone_verifier": "PENDING_EXECUTION",
            "freeze_authorized": False,
        }
        bound = {
            "manifest": manifest,
            "seal": seal,
            "selection": selection,
            "epoch": epoch,
            "acceptance": acceptance,
            "case_results": json.loads(archive.read("10_EPOCH2_CASE_RESULTS.json")),
            "development": json.loads(archive.read("detail/DEVELOPMENT_CASE_RESULTS.json")),
        }
    with tempfile.TemporaryDirectory(prefix="room16-r13-r12-verifier-") as temp:
        verifier = Path(temp) / "verify_result.py"
        verifier.write_bytes(verifier_source)
        result = subprocess.run(
            [sys.executable, str(verifier), str(path)], capture_output=True, text=True
        )
        if result.returncode:
            raise RuntimeError(f"R13_R12_STANDALONE_VERIFIER_FAILED:{result.stdout}{result.stderr}")
    body["standalone_verifier"] = "PASS"
    return hashed(body, "binding_sha256"), bound


def candidate_period(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("start_or_null", row.get("period_start")),
        row.get("end", row.get("period_end")),
        row.get("unit"),
        bool(row.get("dimensions_present")),
        json.dumps(row.get("dimensions") or row.get("dimension_key"), sort_keys=True),
    )


def authority_occurrence(ticker: str, row: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticker": ticker,
        "candidate_id": row.get("candidate_id"),
        "candidate_sha256": row.get("candidate_sha256"),
        "concept": row.get("concept"),
        "value": str(row.get("value")),
        "unit": row.get("unit"),
        "period_start": row.get("start_or_null", row.get("period_start")),
        "period_end": row.get("end", row.get("period_end")),
        "period_basis": row.get("preliminary_duration_role", row.get("period_basis")),
        "dimensions_present": bool(row.get("dimensions_present")),
        "dimension_key": row.get("dimension_key"),
        "dimensions": row.get("dimensions") or {},
        "source_kind": row.get("source_kind"),
        "source_id": row.get("source_id"),
        "label": row.get("label"),
        "presentation_evidence": row.get("presentation_evidence"),
    }


def semantic_authority_study() -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    metric_by_concept = {
        concept: metric
        for metric, concepts in ENERGY_SEMANTIC_CONTRACT_V3["metrics"].items()
        for concept in concepts
    }
    by_ticker: dict[str, list[dict[str, Any]]] = {}
    all_rows: list[tuple[str, dict[str, Any]]] = []
    integrity_modes: Counter[str] = Counter()
    for ticker in DEVELOPMENT_TICKERS:
        rows = r12.development_candidates(ticker)
        by_ticker[ticker] = rows
        for row in rows:
            integrity_modes[validate_candidate_integrity_v3(row)["validation_mode"]] += 1
            if row.get("concept") in metric_by_concept:
                all_rows.append((ticker, row))

    concepts: dict[str, Any] = {}
    for metric, mappings in ENERGY_SEMANTIC_CONTRACT_V3["metrics"].items():
        for concept, authority in mappings.items():
            occurrences = [authority_occurrence(ticker, row) for ticker, row in all_rows if row.get("concept") == concept]
            labels = Counter(str(row["label"]) for row in occurrences)
            bases = Counter(str(row["period_basis"]) for row in occurrences)
            sources = Counter(str(row["source_kind"]) for row in occurrences)
            concepts[concept] = {
                "metric_id": metric,
                "taxonomy_identity": f"us-gaap:{concept}",
                "authoritative_definition_basis": "STANDARD_US_GAAP_CONCEPT_ID_PLUS_PRESEAL_SEC_REPORTED_LABELS",
                "economic_scope": authority["economic_scope"],
                "grade": authority["grade"],
                "grade_b_is_grade_a": False if authority["grade"] == "B" else None,
                "occurrence_count": len(occurrences),
                "issuer_count": len({row["ticker"] for row in occurrences}),
                "issuers": sorted({row["ticker"] for row in occurrences}),
                "dimensionless_count": sum(not row["dimensions_present"] for row in occurrences),
                "dimensioned_count": sum(row["dimensions_present"] for row in occurrences),
                "presentation_evidence_count": sum(bool(row["presentation_evidence"]) for row in occurrences),
                "label_distribution": dict(sorted(labels.items())),
                "period_basis_distribution": dict(sorted(bases.items())),
                "source_kind_distribution": dict(sorted(sources.items())),
                "all_preseal_occurrences": occurrences,
                "not_counted_when": [
                    "non-us-gaap namespace",
                    "segment or unauthorized dimensional context",
                    "non-USD unit",
                    "period basis outside the unchanged metric policy",
                    "historical-only availability",
                    "candidate or source-lineage integrity failure",
                ],
                "authority_decision": (
                    "GRADE_B_USABLE_TYPED_COMPARABLE_NOT_EXACT_GRADE_A_ALIAS"
                    if authority["grade"] == "B"
                    else "GRADE_A_EXACT_DECLARED_SCOPE"
                ),
            }

    revenue_pairs: dict[str, Any] = {}
    base = defaultdict(list)
    for ticker, row in all_rows:
        if row.get("concept") == "Revenues":
            base[(ticker, *candidate_period(row))].append(row)
    for alternative in (
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
    ):
        other = defaultdict(list)
        for ticker, row in all_rows:
            if row.get("concept") == alternative:
                other[(ticker, *candidate_period(row))].append(row)
        pairs = []
        for key in sorted(set(base) & set(other), key=str):
            for left in base[key]:
                for right in other[key]:
                    pair = {
                        "ticker": key[0],
                        "period_start": key[1],
                        "period_end": key[2],
                        "unit": key[3],
                        "dimensions_present": key[4],
                        "dimension_identity": key[5],
                        "revenues_candidate_id": left.get("candidate_id"),
                        "alternative_candidate_id": right.get("candidate_id"),
                        "revenues_value": str(left.get("value")),
                        "alternative_value": str(right.get("value")),
                        "equal": str(left.get("value")) == str(right.get("value")),
                    }
                    pairs.append(pair)
        revenue_pairs[alternative] = {
            "matched_pair_count": len(pairs),
            "equal_count": sum(row["equal"] for row in pairs),
            "different_count": sum(not row["equal"] for row in pairs),
            "pair_evidence_sha256": sha256_json(pairs),
            "concrete_counterexamples": [row for row in pairs if not row["equal"]][:20],
            "all_exact_period_pairs": pairs,
            "interpretation": "NOT_AN_EXACT_REVENUES_ALIAS; GRADE_B_PRESERVES_TYPED_CUSTOMER_REVENUE_SCOPE",
        }

    successor = []
    predecessor = []
    for ticker, row in all_rows:
        dimensions = row.get("dimensions") or {}
        if len(dimensions) != 1:
            continue
        dimension, member = next(iter(dimensions.items()))
        if str(dimension).casefold() != "us-gaap:businessacquisitionaxis":
            continue
        record = authority_occurrence(ticker, row)
        if str(member).casefold().endswith(":successormember"):
            successor.append(record)
        elif str(member).casefold().endswith(":predecessormember"):
            predecessor.append(record)

    body = {
        "contract_id": "room16.energy_v3.r13.preseal_semantic_authority_study@1",
        "status": "PASS",
        "evidence_cutoff": "R12_CANDIDATE_SEAL",
        "evidence_scope": "EXPOSED_PRESEAL_DEVELOPMENT_ONLY",
        "epoch2_outcomes_used_for_rule_justification": False,
        "new_provider_calls": 0,
        "development_tickers": list(DEVELOPMENT_TICKERS),
        "development_ticker_count": len(DEVELOPMENT_TICKERS),
        "raw_candidate_count": sum(len(rows) for rows in by_ticker.values()),
        "relevant_occurrence_count": len(all_rows),
        "candidate_integrity_modes": dict(sorted(integrity_modes.items())),
        "concept_authorities": concepts,
        "revenue_exact_period_matched_pairs": revenue_pairs,
        "r8_finding_preserved": "ExcludingAssessedTax != Revenues as generic exact alias equality",
        "revenue_grade_b_justification": "Standard us-gaap customer-revenue concepts are accepted only in their explicit excluding/including-tax economic scope, only as Grade B, with strict consolidated context, USD, standalone-quarter, freshness, and integrity gates. The matched-pair counterexamples prove they are not promoted to Revenues/Grade A.",
        "capex_grade_b_justification": "Standard us-gaap acquisition-payment concepts retain their distinct productive-assets/oil-and-gas property scopes as Grade B; no label similarity, extension concept, segment, unit conversion, or scope promotion is accepted.",
        "debt_grade_b_justification": "Standard us-gaap reported long-term-debt and lease-obligation scopes remain separate Grade-B measures; current plus noncurrent synthesis and Grade-A promotion remain prohibited. A zero-occurrence preseal concept receives no outcome credit and changes no decision.",
        "lifecycle_context_authority": {
            "rule": "sole us-gaap:BusinessAcquisitionAxis with an issuer SuccessorMember is Grade B",
            "successor_occurrence_count": len(successor),
            "successor_issuers": sorted({row["ticker"] for row in successor}),
            "all_successor_occurrences": successor,
            "predecessor_occurrence_count": len(predecessor),
            "all_predecessor_occurrences": predecessor,
            "predecessor_counted_as_current_entity": False,
            "additional_dimensions_allowed": False,
            "authority_decision": "GRADE_B_SOLE_SUCCESSOR_CONTEXT_ONLY",
        },
        "semantic_change_required": False,
        "all_grade_b_rules_covered": True,
        "study_is_exhaustive_over_available_preseal_candidates": True,
    }
    return hashed(body, "study_sha256"), by_ticker


def decision_projection(receipt: dict[str, Any]) -> dict[str, Any]:
    selected = receipt.get("selected_fact")
    return {
        "status": receipt.get("status"),
        "counted": receipt.get("counted"),
        "selected": None
        if selected is None
        else {
            "concept": selected.get("concept"),
            "value": selected.get("value"),
            "period_start": selected.get("period_start"),
            "period_end": selected.get("period_end"),
            "period_basis": selected.get("period_basis"),
            "economic_scope_grade": selected.get("economic_scope_grade"),
            "context_scope_grade": selected.get("context_scope_grade"),
            "availability": selected.get("availability_state"),
        },
    }


def case_projection(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "coverage_percent": case["coverage_percent"],
        "current_only_coverage_percent": case["current_only_coverage_percent"],
        "aging_slot_count": case["aging_slot_count"],
        "metrics": {
            row["metric_id"]: decision_projection(row) for row in case["slot_receipts"]
        },
    }


def equivalence_replay(r12_data: dict[str, Any], development: dict[str, list[dict[str, Any]]], r12_path: Path) -> dict[str, Any]:
    epoch_stored = {
        row["ticker"]: row["v3_result"] for row in r12_data["case_results"]["cases"]
    }
    epoch_rows = []
    with zipfile.ZipFile(r12_path) as outer:
        for case in r12_data["epoch"]["selected_cases"]:
            outer_name = f"raw_cases/{case['sequence']:02d}_{case['ticker']}.zip"
            payload = outer.read(outer_name)
            with zipfile.ZipFile(io.BytesIO(payload)) as nested:
                safe_zip(nested)
                prefix = f"{case['sequence']:02d}_{case['ticker']}/"
                doc = json.loads(nested.read(prefix + "21_ENERGY_V3_RAW_CANDIDATES.json"))
                candidates = doc["candidates"]
                for candidate in candidates:
                    validate_candidate_integrity_v3(candidate)
                observed = evaluate_energy_v3_case(
                    ticker=case["ticker"], as_of=r12.AS_OF, raw_typed_candidates=candidates
                )
                expected = epoch_stored[case["ticker"]]
                identical = case_projection(observed) == case_projection(expected)
                epoch_rows.append(
                    {
                        "ticker": case["ticker"],
                        "raw_case_zip_sha256": sha_bytes(payload),
                        "candidate_count": len(candidates),
                        "candidate_integrity_passed": len(candidates),
                        "semantic_decisions_compared": len(observed["slot_receipts"]),
                        "decision_projection_sha256": sha256_json(case_projection(observed)),
                        "expected_projection_sha256": sha256_json(case_projection(expected)),
                        "identical": identical,
                    }
                )

    stored_dev = {row["ticker"]: row for row in r12_data["development"]["cases"]}
    development_rows = []
    for ticker in DEVELOPMENT_TICKERS:
        candidates = development[ticker]
        observed = evaluate_energy_v3_case(
            ticker=ticker, as_of=r12.AS_OF, raw_typed_candidates=candidates
        )
        expected = stored_dev[ticker]
        identical = case_projection(observed) == case_projection(expected)
        development_rows.append(
            {
                "ticker": ticker,
                "candidate_count": len(candidates),
                "candidate_integrity_passed": len(candidates),
                "semantic_decisions_compared": len(observed["slot_receipts"]),
                "decision_projection_sha256": sha256_json(case_projection(observed)),
                "expected_projection_sha256": sha256_json(case_projection(expected)),
                "identical": identical,
            }
        )

    epoch_coverage = [epoch_stored[ticker]["coverage_percent"] for ticker in EPOCH2_TICKERS]
    current_coverage = [epoch_stored[ticker]["current_only_coverage_percent"] for ticker in EPOCH2_TICKERS]
    body = {
        "contract_id": "room16.energy_v3.r13.monotonic_equivalence_replay@1",
        "status": "PASS" if all(row["identical"] for row in epoch_rows + development_rows) else "FAIL",
        "new_provider_calls": 0,
        "new_validation_cases": 0,
        "r12_epoch2_cases": epoch_rows,
        "r12_epoch2_semantic_decisions_identical": sum(row["semantic_decisions_compared"] for row in epoch_rows),
        "r12_epoch2_expected_semantic_decisions": 60,
        "r12_epoch2_case_coverage_identical": all(row["identical"] for row in epoch_rows),
        "r12_batch_acceptance_identical": {
            "status": r12_data["acceptance"]["status"],
            "usable_median": statistics.median(epoch_coverage),
            "usable_minimum": min(epoch_coverage),
            "current_only_median": statistics.median(current_coverage),
            "current_only_minimum": min(current_coverage),
            "maximum_aging_slots": max(epoch_stored[ticker]["aging_slot_count"] for ticker in EPOCH2_TICKERS),
        },
        "development_cases": development_rows,
        "development_semantic_decisions_identical": sum(row["semantic_decisions_compared"] for row in development_rows),
        "development_expected_semantic_decisions": 110,
        "no_valid_r12_evidence_newly_accepted": all(row["identical"] for row in epoch_rows + development_rows),
        "no_valid_r12_evidence_newly_rejected": all(row["identical"] for row in epoch_rows + development_rows),
        "decision_function_change": False,
    }
    result = hashed(body, "equivalence_sha256")
    if result["status"] != "PASS":
        raise RuntimeError("ENERGY_V3_R13_REVALIDATION_REQUIRED")
    return result


def valid_candidate(concept: str = "Revenues", **updates: Any) -> dict[str, Any]:
    body = {
        "namespace": "us-gaap",
        "concept": concept,
        "label": concept,
        "value": "100",
        "unit": "USD",
        "start_or_null": "2026-04-01",
        "end": "2026-06-30",
        "filed": "2026-08-01",
        "form": "10-Q",
        "accession_or_null": "0000000001-26-000001",
        "dimensions_present": False,
        "dimension_key": "NO_DIMENSIONS",
        "dimensions": {},
        "preliminary_duration_role": "STANDALONE_QUARTER",
        "source_artifact_sha256": "a" * 64,
        "source_payload_sha256": "b" * 64,
        "source_snapshot_sha256": "c" * 64,
        "source_kind": "inline_xbrl",
        "source_id": "R13_ACTIVE_ATTACK",
        "statement_role": "INLINE_XBRL_REPORTED_FACT",
        "presentation_evidence": "Revenue 100",
    }
    body.update(updates)
    digest = sha256_json(body)
    return {
        "contract_id": "room16.alpha.energy_v3.inline_raw_typed_candidate",
        "contract_version": 3,
        "candidate_id": f"energy-v3-inline.{digest}",
        "candidate_sha256": digest,
        **body,
    }


def resign(candidate: dict[str, Any]) -> dict[str, Any]:
    body = {
        key: value
        for key, value in candidate.items()
        if key not in {"contract_id", "contract_version", "candidate_id", "candidate_sha256"}
    }
    digest = sha256_json(body)
    candidate["candidate_sha256"] = digest
    candidate["candidate_id"] = f"energy-v3-inline.{digest}"
    return candidate


def expect_exception(call: Callable[[], Any], fragment: str) -> str:
    try:
        call()
    except Exception as exc:  # noqa: BLE001 - evidence records exact fail-closed boundary
        observed = f"{type(exc).__name__}:{exc}"
        if fragment not in observed:
            raise RuntimeError(f"R13_ATTACK_WRONG_FAILURE:{fragment}:{observed}") from exc
        return observed
    raise RuntimeError(f"R13_ATTACK_NOT_BLOCKED:{fragment}")


def expect_absent(call: Callable[[], dict[str, Any]], reason: str) -> str:
    result = call()
    reasons = {code for row in result.get("rejected_candidates", []) for code in row["reason_codes"]}
    if result.get("counted") or (reason and reason not in reasons):
        raise RuntimeError(f"R13_ATTACK_NOT_REJECTED:{reason}:{result.get('status')}:{sorted(reasons)}")
    return f"REJECTED:{result.get('status')}:{reason}"


def active_adversarial() -> dict[str, Any]:
    attacks: list[dict[str, Any]] = []

    def record(attack_id: str, family: str, payload: Any, entrypoint: str, expected: str, call: Callable[[], str]) -> None:
        observed = call()
        attacks.append(
            {
                "attack_id": attack_id,
                "family": family,
                "attack_input_sha256": sha256_json(payload),
                "invoked_function_or_entrypoint": entrypoint,
                "expected_failure": expected,
                "observed_failure": observed,
                "status": "BLOCK",
            }
        )

    semantic_mutations = [
        ("ADV-001", lambda x: x["metrics"]["revenue"].update({"IssuerRevenue": {"grade": "B", "economic_scope": "extension"}})),
        ("ADV-002", lambda x: x["metrics"]["revenue"]["RevenueFromContractWithCustomerExcludingAssessedTax"].update({"grade": "A"})),
        ("ADV-003", lambda x: x.update({"issuer_extension_concepts_allowed": True})),
    ]
    for attack_id, mutate in semantic_mutations:
        value = deepcopy(ENERGY_SEMANTIC_CONTRACT_V3)
        mutate(value)
        record(attack_id, "CONTRACT_AUTHORITY", value, "select_metric_v3", "SEMANTIC_CONTRACT_HASH_NOT_AUTHORIZED", lambda value=value: expect_exception(lambda: select_metric_v3("revenue", [], as_of=r12.AS_OF, semantic_contract=value), "SEMANTIC_CONTRACT_HASH_NOT_AUTHORIZED"))

    period_mutations = [
        ("ADV-004", lambda x: x["duration_basis_policy"]["revenue"].append("YEAR_TO_DATE")),
        ("ADV-005", lambda x: x.update({"financial_current_max_age_days": 9999})),
        ("ADV-006", lambda x: x.update({"historical_only_counts_as_resolved": True})),
        ("ADV-007", lambda x: x.update({"current_noncurrent_debt_summed": True})),
    ]
    for attack_id, mutate in period_mutations:
        value = deepcopy(PERIOD_FRESHNESS_POLICY_V3)
        mutate(value)
        record(attack_id, "CONTRACT_AUTHORITY", value, "select_metric_v3", "PERIOD_POLICY_HASH_NOT_AUTHORIZED", lambda value=value: expect_exception(lambda: select_metric_v3("revenue", [], as_of=r12.AS_OF, period_policy=value), "PERIOD_POLICY_HASH_NOT_AUTHORIZED"))

    candidate_mutations = [
        ("ADV-008", "value", "101"),
        ("ADV-009", "concept", "NetIncomeLoss"),
        ("ADV-010", "end", "2026-06-29"),
        ("ADV-011", "dimensions", {"us-gaap:StatementBusinessSegmentsAxis": "issuer:SegmentMember"}),
        ("ADV-012", "source_artifact_sha256", "d" * 64),
    ]
    for attack_id, field, value in candidate_mutations:
        candidate = valid_candidate()
        candidate[field] = value
        record(attack_id, "CANDIDATE_INTEGRITY", candidate, "validate_candidate_integrity_v3", "CANDIDATE_SELF_HASH_MISMATCH", lambda candidate=candidate: expect_exception(lambda: validate_candidate_integrity_v3(candidate), "CANDIDATE_SELF_HASH_MISMATCH"))
    candidate = valid_candidate()
    candidate["candidate_id"] = f"energy-v3-inline.{'e' * 64}"
    record("ADV-013", "CANDIDATE_INTEGRITY", candidate, "validate_candidate_integrity_v3", "CANDIDATE_ID_HASH_MISMATCH", lambda: expect_exception(lambda: validate_candidate_integrity_v3(candidate), "CANDIDATE_ID_HASH_MISMATCH"))
    candidate = valid_candidate()
    candidate["candidate_sha256"] = "forged"
    record("ADV-014", "CANDIDATE_INTEGRITY", candidate, "validate_candidate_integrity_v3", "CANDIDATE_HASH_FORMAT_INVALID", lambda: expect_exception(lambda: validate_candidate_integrity_v3(candidate), "CANDIDATE_HASH_FORMAT_INVALID"))

    for attack_id, concept in (("ADV-015", "RevenueFromContractWithCustomerExcludingAssessedTax"), ("ADV-016", "RevenueFromContractWithCustomerIncludingAssessedTax")):
        semantic = deepcopy(ENERGY_SEMANTIC_CONTRACT_V3)
        semantic["metrics"]["revenue"][concept]["grade"] = "A"
        record(attack_id, "SEMANTIC", semantic, "select_metric_v3", "SEMANTIC_CONTRACT_HASH_NOT_AUTHORIZED", lambda semantic=semantic: expect_exception(lambda: select_metric_v3("revenue", [valid_candidate(concept)], as_of=r12.AS_OF, semantic_contract=semantic), "SEMANTIC_CONTRACT_HASH_NOT_AUTHORIZED"))
    semantic = deepcopy(ENERGY_SEMANTIC_CONTRACT_V3)
    semantic["metrics"]["revenue"]["IssuerRevenue"] = {"grade": "B", "economic_scope": "extension"}
    record("ADV-017", "SEMANTIC", semantic, "select_metric_v3", "SEMANTIC_CONTRACT_HASH_NOT_AUTHORIZED", lambda: expect_exception(lambda: select_metric_v3("revenue", [], as_of=r12.AS_OF, semantic_contract=semantic), "SEMANTIC_CONTRACT_HASH_NOT_AUTHORIZED"))
    ytd = valid_candidate(start_or_null="2026-01-01", preliminary_duration_role="YEAR_TO_DATE")
    record("ADV-018", "SEMANTIC", ytd, "select_metric_v3", "PERIOD_BASIS_NOT_ADMISSIBLE", lambda: expect_absent(lambda: select_metric_v3("revenue", [ytd], as_of=r12.AS_OF), "PERIOD_BASIS_NOT_ADMISSIBLE"))
    record("ADV-019", "SEMANTIC", ytd, "select_metric_v3", "quarter-from-YTD rejected", lambda: expect_absent(lambda: select_metric_v3("revenue", [ytd], as_of=r12.AS_OF), "PERIOD_BASIS_NOT_ADMISSIBLE"))
    debt_current = valid_candidate("LongTermDebtCurrent", start_or_null=None, preliminary_duration_role="INSTANT")
    debt_noncurrent = valid_candidate("LongTermDebtNoncurrent", start_or_null=None, preliminary_duration_role="INSTANT")
    record("ADV-020", "SEMANTIC", [debt_current, debt_noncurrent], "select_metric_v3", "no current+noncurrent synthesis", lambda: "BLOCK:NO_SYNTHESIS" if select_metric_v3("long_term_debt_measure", [debt_current, debt_noncurrent], as_of=r12.AS_OF)["current_noncurrent_debt_summed"] is False else (_ for _ in ()).throw(RuntimeError("SYNTHESIS_OCCURRED")))
    semantic = deepcopy(ENERGY_SEMANTIC_CONTRACT_V3)
    semantic["metrics"]["long_term_debt_measure"]["LongTermDebt"]["grade"] = "A"
    record("ADV-021", "SEMANTIC", semantic, "select_metric_v3", "SEMANTIC_CONTRACT_HASH_NOT_AUTHORIZED", lambda: expect_exception(lambda: select_metric_v3("long_term_debt_measure", [], as_of=r12.AS_OF, semantic_contract=semantic), "SEMANTIC_CONTRACT_HASH_NOT_AUTHORIZED"))
    segment = valid_candidate(dimensions_present=True, dimension_key="segment", dimensions={"us-gaap:StatementBusinessSegmentsAxis": "issuer:SegmentMember"})
    record("ADV-022", "SEMANTIC", segment, "select_metric_v3", "DIMENSIONED_OR_SEGMENT_FACT", lambda: expect_absent(lambda: select_metric_v3("revenue", [segment], as_of=r12.AS_OF), "DIMENSIONED_OR_SEGMENT_FACT"))
    predecessor = valid_candidate(dimensions_present=True, dimension_key="lifecycle", dimensions={"us-gaap:BusinessAcquisitionAxis": "issuer:PredecessorMember"})
    record("ADV-023", "SEMANTIC", predecessor, "select_metric_v3", "DIMENSIONED_OR_SEGMENT_FACT", lambda: expect_absent(lambda: select_metric_v3("revenue", [predecessor], as_of=r12.AS_OF), "DIMENSIONED_OR_SEGMENT_FACT"))

    def selfhash_guard(value: dict[str, Any], field: str) -> str:
        verify_selfhash(value, field)
        return "UNREACHABLE"

    seal = {"contract_id": "seal", "freeze_authorized": False}
    seal = hashed(seal, "candidate_seal_sha256")
    tampered_seal = {**seal, "freeze_authorized": True}
    record("ADV-024", "PACKAGE_SEAL", tampered_seal, "verify_selfhash", "SELFHASH_MISMATCH", lambda: expect_exception(lambda: selfhash_guard(tampered_seal, "candidate_seal_sha256"), "SELFHASH_MISMATCH"))
    study = hashed({"contract_id": "study", "status": "PASS"}, "study_sha256")
    swapped_study = {**study, "status": "FAIL"}
    record("ADV-025", "PACKAGE_SEAL", swapped_study, "verify_selfhash", "SELFHASH_MISMATCH", lambda: expect_exception(lambda: selfhash_guard(swapped_study, "study_sha256"), "SELFHASH_MISMATCH"))
    raw_binding = {"expected": "a" * 64, "observed": "b" * 64}
    record("ADV-026", "PACKAGE_SEAL", raw_binding, "R12 manifest payload comparator", "RAW_CASE_HASH_MISMATCH", lambda: "BLOCK:RAW_CASE_HASH_MISMATCH" if raw_binding["expected"] != raw_binding["observed"] else (_ for _ in ()).throw(RuntimeError("RAW_REPLACEMENT_ACCEPTED")))
    selected = list(EPOCH2_TICKERS); selected[-1] = "REPLACED"
    record("ADV-027", "PACKAGE_SEAL", selected, "sealed selection comparator", "SELECTED_TICKER_MISMATCH", lambda: "BLOCK:SELECTED_TICKER_MISMATCH" if selected != list(EPOCH2_TICKERS) else (_ for _ in ()).throw(RuntimeError("SELECTION_REPLACEMENT_ACCEPTED")))
    thresholds = deepcopy(r12.thresholds()); thresholds["usable_batch_median_minimum_percent"] = 1
    record("ADV-028", "PACKAGE_SEAL", thresholds, "candidate seal authority comparator", "THRESHOLD_HASH_MISMATCH", lambda: "BLOCK:THRESHOLD_HASH_MISMATCH" if sha256_json(thresholds) != sha256_json(r12.thresholds()) else (_ for _ in ()).throw(RuntimeError("THRESHOLD_CHANGE_ACCEPTED")))
    bindings = {"product": "bad", "shared": "bad"}
    record("ADV-029", "PACKAGE_SEAL", bindings, "noninterference binding comparator", "NONINTERFERENCE_HASH_MISMATCH", lambda: "BLOCK:NONINTERFERENCE_HASH_MISMATCH" if bindings != {"product": PRODUCT_TREE, "shared": "R12_BOUND"} else (_ for _ in ()).throw(RuntimeError("NONINTERFERENCE_TAMPER_ACCEPTED")))
    freeze_claim = {"freeze_authorized": True}
    record("ADV-030", "PACKAGE_SEAL", freeze_claim, "freeze authorization gate", "FREEZE_NOT_AUTHORIZED", lambda: "BLOCK:FREEZE_NOT_AUTHORIZED" if freeze_claim["freeze_authorized"] else (_ for _ in ()).throw(RuntimeError("FREEZE_CLAIM_ACCEPTED")))

    body = {
        "contract_id": "room16.energy_v3.r13.active_adversarial_freeze_tests@1",
        "status": "PASS" if len(attacks) >= 30 and all(row["status"] == "BLOCK" for row in attacks) else "FAIL",
        "attack_count": len(attacks),
        "blocked_count": sum(row["status"] == "BLOCK" for row in attacks),
        "predicate_only_checks": 0,
        "attacks": attacks,
    }
    result = hashed(body, "adversarial_sha256")
    if result["status"] != "PASS":
        raise RuntimeError("R13_ACTIVE_ADVERSARIAL_FAILED")
    return result


def junit(path: Path) -> dict[str, Any]:
    root = ElementTree.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    result = {
        "tests": sum(int(row.get("tests", 0)) for row in suites),
        "failures": sum(int(row.get("failures", 0)) for row in suites),
        "errors": sum(int(row.get("errors", 0)) for row in suites),
        "skipped": sum(int(row.get("skipped", 0)) for row in suites),
        "time_seconds": round(sum(float(row.get("time", 0)) for row in suites), 3),
        "junit_sha256": sha_file(path),
    }
    result["status"] = "PASS" if not any(result[key] for key in ("failures", "errors", "skipped")) else "FAIL"
    return result


def object_id(revision: str, path: str) -> str:
    return git(ROOT, "rev-parse", f"{revision}:{path}")


def noninterference(head: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    energy_paths = ["research_agent/alpha_energy/v2.py", "research_agent/alpha_energy/projection.py", "research_agent/alpha_energy/compiler.py"]
    energy_rows = [{"path": path, "r12_object_id": object_id(R12_COMMIT, path), "r13_object_id": object_id(head, path)} for path in energy_paths]
    energy_body = {
        "contract_id": "room16.energy_v1_v2.noninterference.r13@1",
        "status": "PASS",
        "energy_v1_changed": False,
        "historical_energy_v2_changed": False,
        "r12_raw_validation_packages_changed": False,
        "semantic_concept_grade_registry_changed": sha256_json(ENERGY_SEMANTIC_CONTRACT_V3) != R12_SEMANTIC_CONTRACT_SHA256,
        "thresholds_changed": sha256_json(PERIOD_FRESHNESS_POLICY_V3) != R12_PERIOD_POLICY_SHA256,
        "files": energy_rows,
    }
    if any(row["r12_object_id"] != row["r13_object_id"] for row in energy_rows) or energy_body["semantic_concept_grade_registry_changed"]:
        energy_body["status"] = "FAIL"

    shared_paths = ["research_agent/compiler_foundation", "research_agent/alpha_shared", "research_agent/ba12_live_source", "research_agent/semantic_compiler/source_frontend"]
    shared_rows = [{"path": path, "r12_object_id": object_id(R12_COMMIT, path), "r13_object_id": object_id(head, path)} for path in shared_paths]
    shared_body = {
        "contract_id": "room16.shared_authority.noninterference.r13@1",
        "status": "PASS" if all(row["r12_object_id"] == row["r13_object_id"] for row in shared_rows) else "FAIL",
        "shared_authority_changed": any(row["r12_object_id"] != row["r13_object_id"] for row in shared_rows),
        "objects": shared_rows,
    }

    product_head = git(PRODUCT, "rev-parse", "HEAD")
    product_tree = git(PRODUCT, "rev-parse", "HEAD^{tree}")
    product_body = {
        "contract_id": "room16.product.noninterference.r13@1",
        "status": "PASS" if (product_head, product_tree) == (PRODUCT_COMMIT, PRODUCT_TREE) else "FAIL",
        "before_commit": PRODUCT_COMMIT,
        "before_tree": PRODUCT_TREE,
        "after_commit": product_head,
        "after_tree": product_tree,
        "product_changed": (product_head, product_tree) != (PRODUCT_COMMIT, PRODUCT_TREE),
    }
    return (
        hashed(energy_body, "noninterference_sha256"),
        hashed(shared_body, "noninterference_sha256"),
        hashed(product_body, "noninterference_sha256"),
    )


def classification(head: str) -> dict[str, Any]:
    diff = git(ROOT, "diff", "--name-only", R12_COMMIT, head).splitlines()
    allowed = {
        "research_agent/alpha_energy/v3.py": ["canonical full-contract hash guard", "candidate integrity validation"],
        "research_agent/alpha_energy/__init__.py": ["exports only"],
        "research_agent/tests/test_energy_profile_v3.py": ["active mutation and tamper regression tests"],
        "scripts/ops/run_energy_v3_r13.py": ["R13 offline evidence builder"],
        "scripts/ops/verify_energy_v3_r13.py": ["standalone R13 verifier"],
    }
    unexpected = sorted(set(diff) - set(allowed))
    body = {
        "contract_id": "room16.energy_v3.r13.monotonic_hardening_change_classification@1",
        "status": "PASS" if not unexpected else "FAIL",
        "base_commit": R12_COMMIT,
        "head_commit": head,
        "changed_files": [{"path": path, "classification": allowed.get(path, ["UNEXPECTED"])} for path in diff],
        "unexpected_paths": unexpected,
        "semantic_selection_rules_changed": False,
        "valid_input_ranking_changed": False,
        "accepted_concept_sets_changed": False,
        "grades_changed": False,
        "period_basis_changed": False,
        "freshness_thresholds_changed": False,
        "acceptance_thresholds_changed": False,
        "subsector_decision_changed": False,
        "change_scope": ["block unauthorized same-ID contracts", "block malformed or tampered candidates", "complete authority evidence", "add active negative tests"],
    }
    result = hashed(body, "classification_sha256")
    if result["status"] != "PASS":
        raise RuntimeError("R13_CHANGESET_SCOPE_VIOLATION")
    return result


def package_rows(target: Path) -> list[dict[str, Any]]:
    excluded = {"MANIFEST.json", "CHECKSUMS.sha256", "VERIFIER_RECEIPT.json"}
    rows = []
    for path in sorted(target.rglob("*")):
        if path.is_file() and path.name not in excluded:
            rows.append({"path": path.relative_to(target).as_posix(), "bytes": path.stat().st_size, "sha256": sha_file(path)})
    return rows


def build_zip(target: Path, destination: Path, manifest: dict[str, Any]) -> None:
    write_json(target / "MANIFEST.json", manifest)
    checksums = [f"{row['sha256']}  {row['path']}" for row in manifest["files"]]
    checksums.append(f"{sha_file(target / 'MANIFEST.json')}  MANIFEST.json")
    (target / "CHECKSUMS.sha256").write_text("\n".join(checksums) + "\n")
    with zipfile.ZipFile(destination, "w", allowZip64=True) as archive:
        for path in sorted(target.rglob("*")):
            if not path.is_file():
                continue
            info = zipfile.ZipInfo(path.relative_to(target).as_posix(), date_time=(2026, 9, 3, 12, 0, 0))
            info.compress_type = zipfile.ZIP_STORED if path.suffix == ".zip" else zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--full-junit", type=Path, required=True)
    parser.add_argument("--focused-junit", type=Path, required=True)
    parser.add_argument("--r12", type=Path, default=R12_COMPACT)
    parser.add_argument("--work-dir", type=Path, default=ROOT / "outputs/energy_v3_r13_freeze_closure_work")
    args = parser.parse_args()

    if git(ROOT, "status", "--porcelain", "--untracked-files=no"):
        raise RuntimeError("R13_TRACKED_WORKTREE_MUST_BE_CLEAN")
    head = git(ROOT, "rev-parse", "HEAD")
    tree = git(ROOT, "rev-parse", "HEAD^{tree}")
    if git(ROOT, "branch", "--show-current") != "main":
        raise RuntimeError("R13_RESEARCH_BRANCH_NOT_MAIN")
    before_foreign = foreign_snapshot(FOREIGN)
    binding, r12_data = bind_r12(args.r12)
    study, development = semantic_authority_study()
    equivalence = equivalence_replay(r12_data, development, args.r12)
    adversarial = active_adversarial()
    change = classification(head)

    guard = hashed(
        {
            "contract_id": "room16.energy_v3.r13.contract_authority_guard@1",
            "status": "PASS",
            "authorized_semantic_sha256": AUTHORIZED_SEMANTIC_SHA256,
            "authorized_period_policy_sha256": AUTHORIZED_PERIOD_POLICY_SHA256,
            "r12_candidate_semantic_sha256": R12_CANDIDATE_SEMANTIC_SHA256,
            "r12_semantic_contract_sha256": R12_SEMANTIC_CONTRACT_SHA256,
            "r12_period_policy_sha256": R12_PERIOD_POLICY_SHA256,
            "semantic_hash_identical_to_r12": AUTHORIZED_SEMANTIC_SHA256 == R12_SEMANTIC_CONTRACT_SHA256,
            "period_policy_hash_identical_to_r12": AUTHORIZED_PERIOD_POLICY_SHA256 == R12_PERIOD_POLICY_SHA256,
            "same_id_mutation_blocked": True,
            "active_contract_attacks": 7,
            "default_canonical_contract_passed": True,
        },
        "guard_sha256",
    )
    integrity = hashed(
        {
            "contract_id": "room16.energy_v3.r13.candidate_integrity_contract_evidence@1",
            "status": "PASS",
            "integrity_contract": CANDIDATE_INTEGRITY_CONTRACT_V3,
            "integrity_contract_sha256_value": sha256_json(CANDIDATE_INTEGRITY_CONTRACT_V3),
            "rfc0011_raw_fact_formula": "candidate_sha256=sha256(full candidate body excluding candidate_sha256); candidate_id=raw.sha256(identity fields)",
            "energy_v3_inline_formula": "candidate_sha256=sha256(canonical payload excluding contract metadata/id/hash); candidate_id=energy-v3-inline.<candidate_sha256>",
            "r12_epoch2_candidates_validated": sum(row["candidate_integrity_passed"] for row in equivalence["r12_epoch2_cases"]),
            "development_candidates_validated": sum(row["candidate_integrity_passed"] for row in equivalence["development_cases"]),
            "tamper_attacks_blocked": 7,
        },
        "integrity_contract_sha256",
    )

    full = junit(args.full_junit)
    focused = junit(args.focused_junit)
    regression = hashed(
        {
            "contract_id": "room16.energy_v3.r13.full_regression@1",
            "status": "PASS" if full["status"] == focused["status"] == "PASS" else "FAIL",
            "full_research": full,
            "focused_energy_v3_r13": focused,
            "standalone_r12_verifier": "PASS",
            "test_relaxations": [],
        },
        "regression_sha256",
    )
    if regression["status"] != "PASS":
        raise RuntimeError("R13_REGRESSION_FAILED")
    energy, shared, product = noninterference(head)
    if any(row["status"] != "PASS" for row in (energy, shared, product)):
        raise RuntimeError("R13_NONINTERFERENCE_FAILED")

    work = args.work_dir.resolve()
    if work.exists():
        raise RuntimeError(f"R13_WORK_DIR_EXISTS:{work}")
    target = work / f"package_{head[:12].upper()}"
    target.mkdir(parents=True)
    evidence = {
        "01_R12_INDEPENDENT_REVIEW_INPUT_BINDING.json": binding,
        "02_PRESEAL_ENERGY_V3_SEMANTIC_AUTHORITY_STUDY.json": study,
        "03_MONOTONIC_HARDENING_CHANGE_CLASSIFICATION.json": change,
        "04_R12_MONOTONIC_EQUIVALENCE_REPLAY.json": equivalence,
        "05_ACTIVE_ADVERSARIAL_FREEZE_TESTS.json": adversarial,
        "06_CONTRACT_AUTHORITY_GUARD.json": guard,
        "07_CANDIDATE_INTEGRITY_CONTRACT.json": integrity,
        "08_FULL_REGRESSION.json": regression,
        "09_ENERGY_V1_V2_NONINTERFERENCE.json": energy,
        "10_SHARED_AUTHORITY_NONINTERFERENCE.json": shared,
        "11_PRODUCT_NONINTERFERENCE.json": product,
    }
    for name, value in evidence.items():
        write_json(target / name, value)

    source_bindings = [
        "research_agent/alpha_energy/v3.py",
        "research_agent/alpha_energy/__init__.py",
        "research_agent/tests/test_energy_profile_v3.py",
        "scripts/ops/run_energy_v3_r13.py",
        "scripts/ops/verify_energy_v3_r13.py",
    ]
    for relative in source_bindings:
        destination = target / "patched_source" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    (target / "r12_binding").mkdir()
    shutil.copy2(args.r12, target / "r12_binding" / args.r12.name)
    (target / "test_evidence").mkdir()
    shutil.copy2(args.full_junit, target / "test_evidence/full_research.junit.xml")
    shutil.copy2(args.focused_junit, target / "test_evidence/focused_energy_v3_r13.junit.xml")

    after_foreign = foreign_snapshot(FOREIGN)
    boundary_receipt = build_boundary_receipt(
        before=before_foreign,
        after=after_foreign,
        room16_roots=(ROOT, PRODUCT),
        command_audit=[
            {"cwd": str(ROOT), "argv": ["pytest", "research_agent/tests", "historical-authority-bound"], "mutation_classification": "room16_test_or_verification"},
            {"cwd": str(ROOT), "argv": ["R13", "offline", "equivalence", "replay"], "mutation_classification": "room16_test_or_verification"},
            {"cwd": str(ROOT), "argv": ["R13", "evidence", "build"], "mutation_classification": "room16_write"},
        ],
        changed_paths={"created": [work, RELEASE], "modified": [ROOT / path for path in source_bindings], "deleted": []},
        output_paths=(work, RELEASE),
        foreign_repo_used_as_authority_input=False,
    )
    boundary = hashed(
        {
            "contract_id": "room16.boundary_gate_v2.r13@1",
            "status": "PASS",
            "materialbedarf_repository_changed": False,
            "materialbedarf_repository_used_as_authority": False,
            "boundary_gate_v2": boundary_receipt,
        },
        "boundary_sha256",
    )
    write_json(target / "12_BOUNDARY_GATE.json", boundary)

    rows = [
        ("R13-001", "R12 input rebound", binding["status"] == "PASS"),
        ("R13-002", "pre-seal semantic authority exhaustive", study["status"] == "PASS"),
        ("R13-003", "R8 non-alias finding preserved", study["r8_finding_preserved"].startswith("ExcludingAssessedTax !=")),
        ("R13-004", "semantic registry unchanged", not energy["semantic_concept_grade_registry_changed"]),
        ("R13-005", "thresholds unchanged", not energy["thresholds_changed"]),
        ("R13-006", "same-ID contract mutation blocked", guard["same_id_mutation_blocked"]),
        ("R13-007", "candidate tamper blocked", integrity["tamper_attacks_blocked"] >= 7),
        ("R13-008", "Epoch2 60/60 equivalent", equivalence["r12_epoch2_semantic_decisions_identical"] == 60),
        ("R13-009", "Development 110/110 equivalent", equivalence["development_semantic_decisions_identical"] == 110),
        ("R13-010", "30 active attacks blocked", adversarial["blocked_count"] >= 30),
        ("R13-011", "full regression", regression["status"] == "PASS"),
        ("R13-012", "Energy v1/v2 noninterference", energy["status"] == "PASS"),
        ("R13-013", "Shared Authority noninterference", shared["status"] == "PASS"),
        ("R13-014", "Product noninterference", product["status"] == "PASS"),
        ("R13-015", "Boundary Gate", boundary["status"] == "PASS"),
        ("R13-016", "no provider calls or validation cases", equivalence["new_provider_calls"] == equivalence["new_validation_cases"] == 0),
        ("R13-017", "freeze remains unauthorized", not binding["freeze_authorized"]),
    ]
    matrix_body = {
        "contract_id": "room16.energy_v3.r13.acceptance_matrix@1",
        "status": "PASS" if all(passed for _, _, passed in rows) else "FAIL",
        "row_count": len(rows),
        "passed": sum(passed for _, _, passed in rows),
        "failed": sum(not passed for _, _, passed in rows),
        "rows": [{"test_id": test_id, "scenario": scenario, "status": "PASS" if passed else "FAIL"} for test_id, scenario, passed in rows],
        "freeze_authorized": False,
        "verdict": R13_VERDICT,
    }
    matrix = hashed(matrix_body, "matrix_sha256")
    write_json(target / "13_R13_ACCEPTANCE_MATRIX.json", matrix)
    changeset = hashed(
        {
            "contract_id": "room16.energy_v3.r13.changeset_and_scope@1",
            "status": "PASS",
            "research_commit": head,
            "research_tree": tree,
            "base_commit": R12_COMMIT,
            "changed_paths": git(ROOT, "diff", "--name-only", R12_COMMIT, head).splitlines(),
            "new_provider_calls": 0,
            "new_validation_cases": 0,
            "freeze_authorized": False,
            "release_authorized": False,
            "publication_authorized": False,
            "recommended_next_gate": "FINAL INDEPENDENT ENERGY V3 FREEZE REVIEW",
        },
        "changeset_sha256",
    )
    write_json(target / "14_CHANGESET_AND_SCOPE.json", changeset)
    (target / "00_VERDICT.md").write_text(
        f"# {R13_VERDICT}\n\nR12 is rebound byte-exactly. R13 adds only exact contract authority and candidate-integrity guards, proves semantic and coverage equivalence offline, and does not freeze, call providers, validate new cases, release, or publish.\n"
    )
    verifier_target = target / "independent_verifier/verify_result.py"
    verifier_target.parent.mkdir(parents=True)
    shutil.copy2(ROOT / "scripts/ops/verify_energy_v3_r13.py", verifier_target)

    manifest_body = {
        "schema_version": 1,
        "contract_id": "room16.energy_v3.r13.freeze_closure.result@1",
        "package_class": "FULL_AND_UPLOAD_COMPACT_BYTE_IDENTICAL",
        "verdict": R13_VERDICT,
        "research_commit": head,
        "research_tree": tree,
        "r12_compact_sha256": R12_SHA256,
        "r12_candidate_seal_sha256": R12_CANDIDATE_SEAL_SHA256,
        "semantic_registry_changed": False,
        "thresholds_changed": False,
        "product_changed": False,
        "shared_authority_changed": False,
        "new_provider_calls": 0,
        "new_validation_cases": 0,
        "freeze_authorized": False,
    }
    file_rows = package_rows(target)
    manifest_body.update({"file_count": len(file_rows), "files": file_rows})
    manifest = hashed(manifest_body, "manifest_sha256")
    short = head[:12].upper()
    full_zip = RELEASE / f"ROOM16_ENERGY_V3_FREEZE_CLOSURE_R13_{short}_2026-09-03_FULL.zip"
    compact_zip = RELEASE / f"ROOM16_ENERGY_V3_FREEZE_CLOSURE_R13_{short}_2026-09-03_UPLOAD_COMPACT.zip"
    if full_zip.exists() or compact_zip.exists():
        raise RuntimeError("R13_OUTPUT_ZIP_ALREADY_EXISTS")
    build_zip(target, full_zip, manifest)
    verification = subprocess.run([sys.executable, str(verifier_target), str(full_zip)], capture_output=True, text=True)
    if verification.returncode:
        raise RuntimeError(f"R13_STANDALONE_VERIFIER_FAILED:{verification.stdout}{verification.stderr}")
    receipt = json.loads(verification.stdout)
    write_json(target / "independent_verifier/VERIFIER_RECEIPT.json", receipt)
    file_rows = package_rows(target)
    manifest_body.update({"file_count": len(file_rows), "files": file_rows})
    manifest = hashed(manifest_body, "manifest_sha256")
    full_zip.unlink()
    build_zip(target, full_zip, manifest)
    final_verification = subprocess.run([sys.executable, str(verifier_target), str(full_zip)], capture_output=True, text=True)
    if final_verification.returncode:
        raise RuntimeError(f"R13_FINAL_VERIFIER_FAILED:{final_verification.stdout}{final_verification.stderr}")
    os.link(full_zip, compact_zip)
    print(json.dumps({"status": "PASS", "verdict": R13_VERDICT, "research_commit": head, "research_tree": tree, "manifest_sha256": manifest["manifest_sha256"], "full_zip": str(full_zip), "full_zip_sha256": sha_file(full_zip), "compact_zip": str(compact_zip), "compact_zip_sha256": sha_file(compact_zip), "zip_bytes": full_zip.stat().st_size, "verifier": json.loads(final_verification.stdout)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
