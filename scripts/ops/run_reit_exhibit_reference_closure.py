#!/usr/bin/env python3
"""Run the Room16 REIT explicit Exhibit-reference Development6 Wave3."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_agent.alpha_shared.archetype_profiles import archetype_profile_registry
from research_agent.alpha_shared.contracts import (
    DiscoveryCaptureReceiptIR,
    DiscoveryRequestIR,
    DiscoveredSourceCandidateIR,
    DiscoveredSourceSetIR,
    DocumentObservationIR,
    SecFilingIntentIR,
    SecFilingIntentSetIR,
    SharedBaseInputIR,
    SupplementalCaptureReceiptIR,
    SupplementalCompileInputIR,
    SupplementalSourcePolicyIR,
)
from research_agent.alpha_shared.core_slots import (
    REIT_OPERATING_PERFORMANCE_GRADES,
    core_slot_registry,
)
from research_agent.alpha_shared.document_normalizer import (
    discover_observations,
    normalize_document,
)
from research_agent.alpha_shared.execution_authority import (
    AuthorizationReceiptIR,
    BatchExecutionAuthorityIR,
    RuntimeIdentityIR,
    authorize_case_before_network,
)
from research_agent.alpha_shared.observation_registry import label_profiles
from research_agent.alpha_shared.runner import run_canonical_alpha_case
from research_agent.alpha_shared.source_authority import (
    SupplementalSourceAuthority,
    is_sec_index_page,
    is_strict_filed_exhibit_name,
)
from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.semantic_compiler.source_frontend.contracts import SourceSnapshotIR
ROOT = Path(__file__).resolve().parents[2]
RUNNER = Path(__file__).resolve()
_WAVE2_SPEC = importlib.util.spec_from_file_location(
    "room16_reit_wave2_runner",
    ROOT / "scripts/ops/run_reit_supplemental_source_table_closure.py",
)
if _WAVE2_SPEC is None or _WAVE2_SPEC.loader is None:
    raise RuntimeError("REIT_EXHIBIT_WAVE2_RUNNER_IMPORT_FAILED")
wave2 = importlib.util.module_from_spec(_WAVE2_SPEC)
_WAVE2_SPEC.loader.exec_module(wave2)
AS_OF = "2026-08-28"
PRIOR_RESULT_SHA = "9b3eda09dd4d926727ae137d9bacaac338122bc5eeb58cb533fd6082cfa0b92f"
PRIOR_MANIFEST_SHA = "fdf615c6c637297294cbbe72a24c292d5e110b6415cd82a1d5b27805a39e78cf"
EXPECTED_REFS_SHA = "687a235a8542e0e16194463d8f780ece2f49e4e0b5b57a50650aa1d8c4fe6927"
HOLDOUT12_SHA = wave2.HOLDOUT12_SHA
PRODUCT_COMMIT = wave2.PRODUCT_COMMIT
PRODUCT_TREE = wave2.PRODUCT_TREE
DEV6 = wave2.DEV6
SUPPLEMENTAL_METRICS = wave2.SUPPLEMENTAL_METRICS
FROZEN_SOURCES = (
    "research_agent/alpha_shared/contracts.py",
    "research_agent/alpha_shared/source_authority.py",
    "research_agent/alpha_shared/document_normalizer.py",
    "research_agent/alpha_shared/supplemental_semantics.py",
    "research_agent/tests/test_reit_exhibit_reference_closure.py",
    "research_agent/tests/test_reit_supplemental_source_table_closure.py",
    "scripts/ops/run_reit_exhibit_reference_closure.py",
    "scripts/ops/run_reit_supplemental_source_table_closure.py",
)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _sha(path: Path) -> str:
    block = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            block.update(chunk)
    return block.hexdigest()


def _validate_documents(contract_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    expected = _read_json(contract_root / "02_EXPECTED_EXHIBIT_REFERENCES.json")
    expected_body = {key: value for key, value in expected.items() if key != "document_sha256"}
    holdout = _read_json(contract_root / "17_HOLDOUT12_BINDING.json")
    holdout_body = {key: value for key, value in holdout.items() if key != "frozen_list_sha256"}
    if (
        expected.get("document_sha256") != EXPECTED_REFS_SHA
        or sha256_json(expected_body) != EXPECTED_REFS_SHA
        or expected.get("reference_count") != 8
    ):
        raise RuntimeError("REIT_EXHIBIT_EXPECTED_REFERENCES_DRIFT")
    if (
        holdout.get("frozen_list_sha256") != HOLDOUT12_SHA
        or sha256_json(holdout_body) != HOLDOUT12_SHA
    ):
        raise RuntimeError("REIT_EXHIBIT_HOLDOUT12_DRIFT")
    if {item[1] for item in DEV6} & {item["ticker"] for item in holdout["companies"]}:
        raise RuntimeError("REIT_EXHIBIT_DEV6_HOLDOUT_OVERLAP")
    return expected, holdout


def _capture_path(case_root: Path, payload_sha256: str) -> Path:
    return (
        case_root
        / "captures/rfc0011/captures/sha256"
        / payload_sha256[:2]
        / payload_sha256
    )


def _offline_fixtures(contract_root: Path, output: Path) -> int:
    expected, _ = _validate_documents(contract_root)
    authority_root = contract_root / "authority_extract"
    expected_by_ticker: dict[str, list[dict[str, Any]]] = {}
    for item in expected["references"]:
        expected_by_ticker.setdefault(item["ticker"], []).append(item)
    cases = []
    before = []
    for sequence, ticker, _ in DEV6:
        extracted = authority_root / "companies_wave2" / f"{sequence:02d}_{ticker}"
        report = _read_json(extracted / "09_RFC0011_SUPPLEMENTAL_REPORT.json")
        policy = SupplementalSourcePolicyIR.model_validate(report["policy"])
        authority = SupplementalSourceAuthority(policy, output / ".offline" / ticker)
        intent_set = SecFilingIntentSetIR.model_validate(report["filing_intent_set"])
        parent = SecFilingIntentIR.model_validate(report["item202_index_parents"][0])
        candidate_set = DiscoveredSourceSetIR.model_validate(report["candidate_set"])
        parent_candidate = next(
            item
            for item in candidate_set.candidates
            if item.accession_number == parent.accession_number
            and item.document_name == parent.primary_document
        )
        parent_receipt = next(
            SupplementalCaptureReceiptIR.model_validate(item)
            for item in report["evidence_set"]["capture_receipts"]
            if item["candidate_id"] == parent_candidate.candidate_id
        )
        index_receipt = next(
            DiscoveryCaptureReceiptIR.model_validate(item)
            for item in report["discovery_receipts"]
            if item["original_locator"].endswith("/index.json")
        )
        for receipt in (parent_receipt, index_receipt):
            payload = _capture_path(extracted, receipt.payload_sha256).read_bytes()
            artifact = authority.store.persist(
                payload,
                media_type=receipt.media_type,
                write_completed_at_utc=receipt.fetched_at_utc,
            )
            if (
                artifact.content_sha256 != receipt.payload_sha256
                or artifact.artifact_sha256 != receipt.capture_artifact_sha256
            ):
                raise RuntimeError(f"REIT_EXHIBIT_OFFLINE_CAPTURE_BINDING_DRIFT:{ticker}")
        references = authority.derive_sec_exhibit_references(
            parent_intent=parent,
            parent_candidate=parent_candidate,
            parent_capture=parent_receipt,
        )
        candidates, bindings = authority.derive_referenced_exhibit_candidates(
            parent_intent=parent,
            reference_set=references,
            filing_index_receipt=index_receipt,
            issuer_cik=policy.issuer_cik,
        )
        actual = {
            (item.exhibit_number, item.referenced_document_name, item.description)
            for item in references.references
        }
        projected = {
            (item["exhibit_number"], item["href"], item["description_contains"])
            for item in expected_by_ticker[ticker]
        }
        if len(actual) != len(projected) or any(
            not any(
                number == expected_number
                and name == expected_name
                and expected_description.casefold() in description.casefold()
                for number, name, description in actual
            )
            for expected_number, expected_name, expected_description in projected
        ):
            raise RuntimeError(f"REIT_EXHIBIT_OFFLINE_REFERENCE_MISMATCH:{ticker}")
        cases.append(
            {
                "sequence": sequence,
                "ticker": ticker,
                "status": "PASS",
                "parent_accession": parent.accession_number,
                "parent_intent_sha256": parent.intent_sha256,
                "parent_document_sha256": parent_receipt.payload_sha256,
                "index_payload_sha256": index_receipt.payload_sha256,
                "reference_set": references.model_dump(mode="json"),
                "candidates": [item.model_dump(mode="json") for item in candidates],
                "bindings": [item.model_dump(mode="json") for item in bindings],
                "network_calls": 0,
            }
        )
        if ticker in {"AMT", "CUBE"}:
            expected_name = expected_by_ticker[ticker][0]["href"]
            before.append(
                {
                    "ticker": ticker,
                    "parent_accession": parent.accession_number,
                    "referenced_document_name": expected_name,
                    "captured_index_membership": True,
                    "parent_html_explicit_reference": True,
                    "strict_filename_heuristic_match": is_strict_filed_exhibit_name(
                        expected_name
                    ),
                    "candidate_present_before": any(
                        item.document_name == expected_name for item in candidate_set.candidates
                    ),
                }
            )
        if intent_set.policy_sha256 != policy.policy_sha256:
            raise RuntimeError(f"REIT_EXHIBIT_OFFLINE_INTENT_POLICY_DRIFT:{ticker}")
    if any(
        item["strict_filename_heuristic_match"] or item["candidate_present_before"]
        for item in before
    ):
        raise RuntimeError("REIT_EXHIBIT_BEFORE_DEFECT_NOT_REPRODUCED")
    _write_json(
        output / "02_BEFORE_DEFECT_REPRODUCTION.json",
        {
            "status": "PASS",
            "network_calls": 0,
            "root_cause": "explicit parent reference not used as separate candidate authority",
            "filename_heuristic_relaxed": False,
            "cases": before,
        },
    )
    _write_json(
        output / "05_EXPECTED_REFERENCE_FIXTURES.json",
        {
            "status": "PASS",
            "expected_references_sha256": EXPECTED_REFS_SHA,
            "reference_count": sum(len(item["reference_set"]["references"]) for item in cases),
            "network_calls": 0,
            "cases": cases,
        },
    )
    print(json.dumps({"status": "PASS", "cases": 6, "references": 8, "network": 0}))
    return 0


def _profile_slots() -> dict[str, tuple[str, ...]]:
    return {
        str(item["archetype_profile_id"]): tuple(item["required_core_metrics"])
        for item in archetype_profile_registry()["profiles"]
    }


def _prestart(contract_root: Path, product_root: Path, output: Path) -> int:
    expected, holdout = _validate_documents(contract_root)
    if not (output / "02_BEFORE_DEFECT_REPRODUCTION.json").is_file() or not (
        output / "05_EXPECTED_REFERENCE_FIXTURES.json"
    ).is_file():
        raise RuntimeError("REIT_EXHIBIT_OFFLINE_GATE_MISSING")
    runtime = wave2._runtime(product_root)
    if (runtime.product_commit, runtime.product_tree) != (PRODUCT_COMMIT, PRODUCT_TREE):
        raise RuntimeError("PRODUCT_IDENTITY_DRIFT")
    if not wave2._tracked_clean(ROOT) or not wave2._tracked_clean(product_root):
        raise RuntimeError("TRACKED_WORKTREE_NOT_CLEAN")
    if wave2._git(ROOT, "rev-parse", "@{u}") != runtime.research_commit:
        raise RuntimeError("RESEARCH_REMOTE_DRIFT")
    authority = wave2._authority(runtime)
    receipts = tuple(
        authorize_case_before_network(
            ticker=case.ticker,
            archetype_profile_id=case.archetype_profile_id,
            sequence=case.sequence,
            authority=authority,
            runtime_identity=runtime,
        )
        for case in authority.ordered_cases
    )
    slot_registry = core_slot_registry(_profile_slots())
    freeze_body = {
        "contract_id": "room16.reit.exhibit_reference_wave3_prestart_freeze",
        "contract_version": 1,
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "as_of_date": AS_OF,
        "runtime_identity": runtime.model_dump(mode="json"),
        "research_origin": wave2.RESEARCH_ORIGIN,
        "research_remote_head": wave2._git(ROOT, "rev-parse", "@{u}"),
        "product_origin": wave2.PRODUCT_ORIGIN,
        "product_changed": False,
        "prior_result_sha256": PRIOR_RESULT_SHA,
        "prior_manifest_sha256": PRIOR_MANIFEST_SHA,
        "prior_wave2_freeze_sha256": "eda801a6da87759ee54b56bbd232b73aa807cb15d4d034791a27199f7563ce7f",
        "expected_exhibit_references_sha256": EXPECTED_REFS_SHA,
        "holdout12_list_sha256": HOLDOUT12_SHA,
        "core_slot_registry_sha256": slot_registry["registry_sha256"],
        "frozen_source_hashes": {item: _sha(ROOT / item) for item in FROZEN_SOURCES},
        "offline_fixture_sha256": _sha(output / "05_EXPECTED_REFERENCE_FIXTURES.json"),
        "authority": authority.model_dump(mode="json"),
        "authorization_receipts": [item.model_dump(mode="json") for item in receipts],
        "authorized_tickers_in_order": [item[1] for item in DEV6],
        "expected_references": expected,
        "holdout12_binding": holdout,
        "core_slot_policy_changed": False,
        "threshold_changed": False,
        "base_reit_mapping_changed": False,
        "filename_heuristic_relaxed": False,
        "holdout12_queries": 0,
        "holdout12_runs": 0,
        "network_queries_before_freeze": 0,
        "foreign_repository_before": wave2._foreign_snapshot(),
        "no_tuning_required": True,
        "semantic_changes_after_freeze_authorized": False,
    }
    freeze = {**freeze_body, "freeze_sha256": sha256_json(freeze_body)}
    _write_json(output / "10_WAVE3_PRESTART_FREEZE.json", freeze)
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/ops/verify_project_boundary_non_interference_v2.py"),
            "snapshot",
            "--foreign-root",
            str(wave2.FOREIGN_ROOT),
            "--output",
            str(output / ".boundary_before.json"),
        ],
        check=True,
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
    )
    print(json.dumps({"status": "PASS", "freeze_sha256": freeze["freeze_sha256"]}))
    return 0


def _verify_freeze(product_root: Path, output: Path) -> tuple[dict[str, Any], RuntimeIdentityIR]:
    freeze = _read_json(output / "10_WAVE3_PRESTART_FREEZE.json")
    if sha256_json({key: value for key, value in freeze.items() if key != "freeze_sha256"}) != freeze[
        "freeze_sha256"
    ]:
        raise RuntimeError("REIT_EXHIBIT_WAVE3_FREEZE_SELFHASH_DRIFT")
    runtime = wave2._runtime(product_root)
    if runtime.model_dump(mode="json") != freeze["runtime_identity"]:
        raise RuntimeError("REIT_EXHIBIT_WAVE3_RUNTIME_DRIFT")
    if not wave2._tracked_clean(ROOT) or not wave2._tracked_clean(product_root):
        raise RuntimeError("REIT_EXHIBIT_WAVE3_TRACKED_WORKTREE_DRIFT")
    for relative, expected in freeze["frozen_source_hashes"].items():
        if _sha(ROOT / relative) != expected:
            raise RuntimeError(f"REIT_EXHIBIT_WAVE3_SOURCE_DRIFT:{relative}")
    if wave2._foreign_snapshot() != freeze["foreign_repository_before"]:
        raise RuntimeError("REIT_EXHIBIT_WAVE3_FOREIGN_BOUNDARY_DRIFT")
    return freeze, runtime


def _supplemental(
    case_root: Path,
    request_sha: str,
    ticker: str,
    company: str,
    cik: str,
    fetch_log: list[dict[str, Any]],
) -> tuple[SupplementalCompileInputIR, dict[str, Any]]:
    policy = SupplementalSourcePolicyIR.create(
        base_request_sha256=request_sha,
        ticker=ticker,
        canonical_company_name=company,
        issuer_cik=cik,
        as_of_date=AS_OF,
        allowed_source_family_ids=(
            "sec_filed_exhibit",
            "sec_primary_document",
            "structured_regulatory_dataset",
        ),
        allowed_domains=("data.sec.gov", "www.sec.gov"),
        allowed_media_types=(
            "application/json",
            "application/xhtml+xml",
            "text/html",
            "text/plain",
        ),
        allowed_sec_forms=("10-K", "10-Q", "8-K"),
        max_discovery_requests=4,
        max_candidates=250,
        max_selected_documents=3,
        max_bytes_per_document=20_000_000,
        discovery_lookback_days=550,
        paid_provider_ids_allowed=(),
        network_mode="live_acquisition",
    )
    authority = SupplementalSourceAuthority(policy, case_root / "captures/rfc0011")
    fetcher = wave2.SupplementalFetcher(fetch_log)
    submissions_request = DiscoveryRequestIR.create(
        request_id=f"reit.wave3.discovery.submissions.{ticker.lower()}",
        policy_sha256=policy.policy_sha256,
        source_family_id="sec_primary_document",
        locator=f"https://data.sec.gov/submissions/CIK{cik.zfill(10)}.json",
    )
    submissions = authority.capture_discovery(submissions_request, fetcher)
    primary_candidates = authority.derive_sec_submission_candidates(submissions)
    primary_set = authority.candidate_set((submissions,), primary_candidates)
    intent_set = authority.derive_sec_filing_intents(submissions)
    parents = authority.select_item202_index_parents(primary_set, intent_set)
    discovery = [submissions]
    strict_exhibits: list[DiscoveredSourceCandidateIR] = []
    referenced: list[DiscoveredSourceCandidateIR] = []
    bindings = []
    reference_sets = []
    parent_capture_receipts = []
    for parent in parents:
        index_request = DiscoveryRequestIR.create(
            request_id=f"reit.wave3.discovery.item202-index.{ticker.lower()}.{parent.accession_number}",
            policy_sha256=policy.policy_sha256,
            source_family_id="sec_filed_exhibit",
            locator=(
                f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
                f"{parent.accession_number.replace('-', '')}/index.json"
            ),
        )
        index_receipt = authority.capture_discovery(index_request, fetcher)
        discovery.append(index_receipt)
        strict_exhibits.extend(
            authority.derive_filing_index_candidates(
                index_receipt,
                issuer_cik=cik,
                accession_number=parent.accession_number,
                filing_date=parent.filing_date,
                report_date=parent.report_date,
                form=parent.form,
                primary_document=parent.primary_document,
            )
        )
        parent_candidate = next(
            item
            for item in primary_candidates
            if item.accession_number == parent.accession_number
            and item.document_name == parent.primary_document
        )
        preliminary = authority.candidate_set(
            tuple(discovery), tuple(primary_candidates) + tuple(strict_exhibits)
        )
        parent_evidence = authority.capture_selected(preliminary, (parent_candidate,), fetcher)
        parent_capture = parent_evidence.capture_receipts[0]
        parent_capture_receipts.append(parent_capture)
        reference_set = authority.derive_sec_exhibit_references(
            parent_intent=parent,
            parent_candidate=parent_candidate,
            parent_capture=parent_capture,
        )
        new_candidates, new_bindings = authority.derive_referenced_exhibit_candidates(
            parent_intent=parent,
            reference_set=reference_set,
            filing_index_receipt=index_receipt,
            issuer_cik=cik,
        )
        reference_sets.append(reference_set)
        referenced.extend(new_candidates)
        bindings.extend(new_bindings)
    candidate_by_id = {
        item.candidate_id: item
        for item in (*primary_candidates, *strict_exhibits, *referenced)
    }
    candidate_set = authority.candidate_set(tuple(discovery), tuple(candidate_by_id.values()))
    context = authority.selection_context_v3(
        candidate_set,
        intent_set,
        parents,
        tuple(reference_sets),
        tuple({item.candidate_id: item for item in bindings}.values()),
    )
    selected = authority.select(candidate_set, context)
    if any(is_sec_index_page(item.document_name) for item in selected):
        raise RuntimeError(f"REIT_EXHIBIT_INDEX_PAGE_SELECTED:{ticker}")
    evidence = authority.capture_selected(candidate_set, selected, fetcher)
    requested = {metric: label_profiles()[metric] for metric in SUPPLEMENTAL_METRICS}
    observations: list[DocumentObservationIR] = []
    normalized = []
    for receipt in evidence.capture_receipts:
        candidate = candidate_by_id[receipt.candidate_id]
        _, payload = authority.store.load_verified(receipt.payload_sha256)
        document = normalize_document(
            payload,
            document_id=candidate.candidate_id,
            accession_number=candidate.accession_number,
            report_date=candidate.report_date,
            filing_date=candidate.filing_date,
            document_name=candidate.document_name,
            media_type=receipt.media_type,
        )
        normalized.append(document.model_dump(mode="json"))
        observations.extend(discover_observations(document, requested))
    replay = authority.replay(candidate_set, evidence.capture_receipts)
    if replay.evidence_set_sha256 != evidence.evidence_set_sha256:
        raise RuntimeError(f"REIT_EXHIBIT_SUPPLEMENTAL_REPLAY_DRIFT:{ticker}")
    supplemental = SupplementalCompileInputIR.create(
        supplemental_policy_sha256=policy.policy_sha256,
        discovery_set_sha256=candidate_set.set_sha256,
        supplemental_evidence_set_sha256=evidence.evidence_set_sha256,
        observations=tuple(observations),
    )
    tags = dict(context.candidate_tags)
    selected_reference_names = [
        item.document_name
        for item in selected
        if tags[item.candidate_id] == "ITEM_2_02_REFERENCED_EXHIBIT"
    ]
    return supplemental, {
        "status": "PASS",
        "policy": policy.model_dump(mode="json"),
        "discovery_receipts": [item.model_dump(mode="json") for item in discovery],
        "candidate_set": candidate_set.model_dump(mode="json"),
        "filing_intent_set": intent_set.model_dump(mode="json"),
        "item202_index_parents": [item.model_dump(mode="json") for item in parents],
        "parent_capture_receipts": [
            item.model_dump(mode="json") for item in parent_capture_receipts
        ],
        "exhibit_reference_sets": [item.model_dump(mode="json") for item in reference_sets],
        "reference_candidate_bindings": [item.model_dump(mode="json") for item in bindings],
        "selection_context_v3": context.model_dump(mode="json"),
        "selected_documents": [item.model_dump(mode="json") for item in selected],
        "selected_reference_documents": selected_reference_names,
        "filename_heuristic_relaxed": False,
        "index_or_header_selected": False,
        "evidence_set": evidence.model_dump(mode="json"),
        "normalized_documents": normalized,
        "observations": [item.model_dump(mode="json") for item in observations],
        "supplemental_input": supplemental.model_dump(mode="json"),
        "offline_replay_network_calls": 0,
    }


def _replay_case(case_root: Path, research_commit: str, research_tree: str, counter: int) -> int:
    base_report = _read_json(case_root / "08_SOURCE_SNAPSHOT.json")
    base = SharedBaseInputIR.from_snapshot(
        snapshot=SourceSnapshotIR.model_validate(base_report["snapshot"]),
        snapshot_root=Path(base_report["snapshot_root"]),
    )
    supplemental = SupplementalCompileInputIR.model_validate(
        _read_json(case_root / "09_RFC0011_SUPPLEMENTAL_REPORT.json")["supplemental_input"]
    )
    result = wave2.replay_canonical_alpha_case(
        base_input=base,
        supplemental_input=supplemental,
        archetype_profile_id="reit",
        output_root=case_root / "replay_bundle",
        ledger_path=case_root / "replay_operations.jsonl",
        research_commit=research_commit,
        research_tree=research_tree,
        monotonic_counter=counter,
    )
    _write_json(
        case_root / "18_OFFLINE_REPLAY_REPORT.json",
        {
            "status": "PASS",
            "network_provider_calls": 0,
            "bundle_sha256": result.compiled.manifest["bundle_sha256"],
            "signed_receipt_sha256": result.compiled.receipt["receipt_sha256"],
            "internal_report_sha256": result.compiled.internal_report.report_sha256,
            "runner_report": result.report,
        },
    )
    return 0


def _execute_case(
    output: Path,
    sequence: int,
    ticker: str,
    company: str,
    receipt: AuthorizationReceiptIR,
    runtime: RuntimeIdentityIR,
) -> dict[str, Any]:
    case_root = output / "companies_wave3" / f"{sequence:02d}_{ticker}"
    if case_root.exists():
        raise RuntimeError(f"REIT_EXHIBIT_CASE_OUTPUT_EXISTS:{ticker}")
    case_root.mkdir(parents=True)
    _write_json(case_root / "01_AUTHORIZATION_RECEIPT.json", receipt.model_dump(mode="json"))
    retry_log: list[dict[str, Any]] = []
    supplemental_log: list[dict[str, Any]] = []
    base, identity, request, details = wave2._base_capture(
        case_root, ticker, company, retry_log
    )
    _write_json(case_root / "03_IDENTITY_PREFLIGHT.json", identity)
    _write_json(case_root / "04_COMPILE_REQUEST.json", request)
    _write_json(case_root / "05_SOURCE_PLAN.json", details["plan"])
    _write_json(
        case_root / "06_BASE_LIVE_ACQUISITION.json",
        {"status": "PASS", "records": details["capture"]["records"], "retry_log": retry_log},
    )
    _write_json(case_root / "07_RFC0010_CAPTURE_REPORT.json", details["capture"])
    _write_json(
        case_root / "08_SOURCE_SNAPSHOT.json",
        {
            "status": "PASS",
            "snapshot": base.snapshot_ir.model_dump(mode="json"),
            "snapshot_root": base.snapshot_root,
            "base_input_sha256": base.base_input_sha256,
        },
    )
    supplemental, supplemental_report = _supplemental(
        case_root,
        request["request_sha256"],
        ticker,
        company,
        str(identity["cik"]),
        supplemental_log,
    )
    _write_json(
        case_root / "09_RFC0011_SUPPLEMENTAL_REPORT.json",
        {**supplemental_report, "network_log": supplemental_log},
    )
    result = run_canonical_alpha_case(
        base_input=base,
        supplemental_input=supplemental,
        archetype_profile_id="reit",
        output_root=case_root / "live_bundle",
        ledger_path=case_root / "live_operations.jsonl",
        research_commit=runtime.research_commit,
        research_tree=runtime.research_tree,
        monotonic_counter=sequence,
        acquisition_mode="verified_live_capture",
        authorization_receipt=receipt,
    )
    report = result.compiled.internal_report
    _write_json(case_root / "15_INTERNAL_ALPHA_REPORT.json", report.model_dump(mode="json"))
    _write_json(
        case_root / "16_BUNDLE_BINDING.json",
        {
            "status": "PASS",
            "bundle_sha256": result.compiled.manifest["bundle_sha256"],
            "signed_receipt_sha256": result.compiled.receipt["receipt_sha256"],
            "verification": result.compiled.verification,
        },
    )
    _write_json(
        case_root / "17_LIVE_LEDGER.json",
        {
            "status": "PASS",
            "authorization_precedes_provider": True,
            "events": result.compiled.ledger_report["events"],
            "base_retry_log": retry_log,
            "supplemental_network_log": supplemental_log,
        },
    )
    subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "replay-case",
            "--case-root",
            str(case_root),
            "--research-commit",
            runtime.research_commit,
            "--research-tree",
            runtime.research_tree,
            "--counter",
            str(sequence),
        ],
        check=True,
        cwd=ROOT,
    )
    replay = _read_json(case_root / "18_OFFLINE_REPLAY_REPORT.json")
    live_identity = (
        result.compiled.manifest["bundle_sha256"],
        result.compiled.receipt["receipt_sha256"],
        report.report_sha256,
    )
    replay_identity = (
        replay["bundle_sha256"],
        replay["signed_receipt_sha256"],
        replay["internal_report_sha256"],
    )
    if live_identity != replay_identity:
        raise RuntimeError(f"REIT_EXHIBIT_REPLAY_IDENTITY_DRIFT:{ticker}")
    slots = list(report.core_slot_resolutions)
    operating = next(
        item for item in slots if item["slot_id"] == "reit_operating_performance_measure"
    )
    ffo_candidates = [
        item
        for item in supplemental_report["observations"]
        if item.get("label_id") in REIT_OPERATING_PERFORMANCE_GRADES
    ]
    summary = {
        "sequence": sequence,
        "ticker": ticker,
        "company_name": company,
        "archetype": "REIT",
        "archetype_profile_id": "reit",
        "status": "COMPLETE",
        "P0": 0,
        "P1": 0,
        "P2": len(report.important_unsupported_metrics),
        "infrastructure_incomplete": False,
        "core_slot_coverage_percent": report.source_coverage["core_slot_coverage_percent"],
        "required_core_slot_count": report.source_coverage["required_core_slot_count"],
        "covered_core_slot_count": report.source_coverage["covered_core_slot_count"],
        "required_section_completeness_percent": report.report_completeness[
            "required_section_completeness_percent"
        ],
        "surfaced_fact_lineage_percent": report.evidence_lineage[
            "surfaced_fact_lineage_rate_percent"
        ],
        "stale_primary_metric_count": report.evidence_lineage["stale_primary_metric_count"],
        "core_slot_resolutions": slots,
        "operating_measure_slot": operating,
        "ffo_family_candidate_count": len(ffo_candidates),
        "ffo_family_candidates": ffo_candidates,
        "selected_documents": supplemental_report["selected_documents"],
        "selected_reference_documents": supplemental_report["selected_reference_documents"],
        "explicit_exhibit_reference_authority": True,
        "filename_heuristic_relaxed": False,
        "index_or_header_selected": False,
        "live_provider_calls": 1 + len(details["capture"]["records"]) + len(supplemental_log),
        "replay_provider_calls": 0,
        "replay_identity_match": True,
        "bundle_sha256": live_identity[0],
        "signed_receipt_sha256": live_identity[1],
        "internal_report_sha256": live_identity[2],
        "authorization_receipt_sha256": receipt.receipt_sha256,
    }
    _write_json(case_root / "00_CASE_VERDICT.json", summary)
    return summary


def _infrastructure_failure(exc: Exception) -> bool:
    text = str(exc).upper()
    return isinstance(
        exc,
        (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ConnectionError, OSError),
    ) or any(token in text for token in ("NASDAQ RETURNED NO", "SEC REQUEST FAILED", "TIMEOUT"))


def _run(product_root: Path, output: Path) -> int:
    freeze, runtime = _verify_freeze(product_root, output)
    authority = BatchExecutionAuthorityIR.model_validate(freeze["authority"])
    receipts = {
        item.ticker: item
        for item in (
            AuthorizationReceiptIR.model_validate(raw) for raw in freeze["authorization_receipts"]
        )
    }
    summaries = []
    for sequence, ticker, company in DEV6:
        _verify_freeze(product_root, output)
        try:
            summary = _execute_case(
                output, sequence, ticker, company, receipts[ticker], runtime
            )
        except Exception as exc:
            infrastructure = _infrastructure_failure(exc)
            summary = {
                "sequence": sequence,
                "ticker": ticker,
                "company_name": company,
                "archetype": "REIT",
                "status": "INFRASTRUCTURE_INCOMPLETE" if infrastructure else "STOPPED_P1",
                "P0": 0,
                "P1": 0 if infrastructure else 1,
                "P2": 1 if infrastructure else 0,
                "infrastructure_incomplete": infrastructure,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "replay_provider_calls": 0,
            }
            case_root = output / "companies_wave3" / f"{sequence:02d}_{ticker}"
            case_root.mkdir(parents=True, exist_ok=True)
            _write_json(case_root / "00_CASE_VERDICT.json", summary)
            summaries.append(summary)
            if not infrastructure:
                break
            continue
        summaries.append(summary)
    _verify_freeze(product_root, output)
    ledger = {
        "contract_id": "room16.reit.exhibit_reference_wave3_run_ledger",
        "contract_version": 1,
        "status": "STOPPED_P0_P1"
        if any(item.get("P0") or item.get("P1") for item in summaries)
        else "COMPLETE",
        "freeze_sha256": freeze["freeze_sha256"],
        "authority_sha256": authority.authority_sha256,
        "attempted_tickers": [item["ticker"] for item in summaries],
        "authorized_tickers": [item[1] for item in DEV6],
        "cases": summaries,
        "no_tuning": True,
        "tracked_changes_between_cases": 0,
        "core_slot_policy_changed": False,
        "threshold_changed": False,
        "base_reit_mapping_changed": False,
        "filename_heuristic_relaxed": False,
        "fixed24_non_reit_live_queries": 0,
        "holdout12_queries": 0,
        "holdout12_runs": 0,
    }
    _write_json(output / "11_WAVE3_RUN_LEDGER.json", ledger)
    print(json.dumps({"status": ledger["status"], "attempted": len(summaries)}, sort_keys=True))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)
    offline = sub.add_parser("offline-fixtures")
    offline.add_argument("--contract-root", type=Path, required=True)
    offline.add_argument("--output", type=Path, required=True)
    prestart = sub.add_parser("prestart")
    prestart.add_argument("--contract-root", type=Path, required=True)
    prestart.add_argument("--product-root", type=Path, required=True)
    prestart.add_argument("--output", type=Path, required=True)
    run = sub.add_parser("run")
    run.add_argument("--product-root", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    replay = sub.add_parser("replay-case")
    replay.add_argument("--case-root", type=Path, required=True)
    replay.add_argument("--research-commit", required=True)
    replay.add_argument("--research-tree", required=True)
    replay.add_argument("--counter", type=int, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.mode == "offline-fixtures":
        return _offline_fixtures(args.contract_root, args.output)
    if args.mode == "prestart":
        return _prestart(args.contract_root, args.product_root, args.output)
    if args.mode == "run":
        return _run(args.product_root, args.output)
    return _replay_case(args.case_root, args.research_commit, args.research_tree, args.counter)


if __name__ == "__main__":
    raise SystemExit(main())
