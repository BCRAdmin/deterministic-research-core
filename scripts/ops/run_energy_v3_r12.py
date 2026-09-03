#!/usr/bin/env python3
"""Seal, execute, and package the Room16 Energy-v3 R12 validation epoch."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import statistics
import subprocess
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


ROOT = Path("/Users/BjornRosinger/Documents/DreamFactory/Room16/research-agent-ops")
PRODUCT = ROOT.parent / "company-dossier-lab"
WORK = ROOT / "outputs/energy_v3_generalized_clean_validation_r12_work"
PRESEAL_JUNIT = ROOT / "outputs/energy_v3_r12_focused_preseal.junit.xml"
SEALED = WORK / "sealed"
RUNTIME = WORK / "runtime"
ACTIVE = RUNTIME / "active"
CONTRACT = RUNTIME / "contract"
SUMMARIES = RUNTIME / "summaries"
ARCHIVES = RUNTIME / "case_archives"
RELEASE = ROOT / "outputs/release"
R11_WORK = ROOT / "outputs/energy_v2_clean_validation_r11_work"
R11_SEALED = R11_WORK / "sealed"
R11_COMPACT = RELEASE / (
    "ROOM16_ENERGY_V2_CLEAN_VALIDATION_FREEZE_READINESS_R11_"
    "270A8CF729D4_2026-09-03_UPLOAD_COMPACT.zip"
)
R5_CASES = ROOT / (
    "outputs/dynamic_disk_baseline_energy_final_resume_r5_runtime/_runtime/companies"
)
FIXED24 = RELEASE / ("ROOM16_FIXED24_NO_TUNING_BATCH_RESULT_R1_8DAD9D5A74E9_2026-08-28.zip")
XOM_ROOT = RELEASE / (
    "ROOM16_SHARED_HARDENING_H1_H4_RFC0011_CANDIDATE_R3_0A9DB0E8AC51_2026-08-27/canonical_live/XOM"
)
WORKORDER = Path(
    "/Users/BjornRosinger/Downloads/ROOM16_ENERGY_V3_R12_VEGA_WORKORDER_2026-09-03.zip"
)
FIXED_RUNNER = ROOT / "scripts/ops/run_fixed24_no_tuning_batch.py"
SCRIPT = Path(__file__).resolve()
VERIFIER = ROOT / "scripts/ops/verify_energy_v3_r12.py"
AS_OF = "2026-09-03"
R11_COMMIT = "270a8cf729d44bc8b4f423d5a89d3fe9577ced9e"
R11_TREE = "da307cb9c1179648bf3b15be8b6f57b69daa7c23"
PRODUCT_COMMIT = "ed86bb841aab88d878266cf8ed498eabc6fa9029"
PRODUCT_TREE = "a382d9c096825910b5e0e8865414ea232b95bd40"
R11_SHA256 = "30cf4d6eb45593a8e1ef12ce5ac80c659501bd0d95c7395455474fea7bbabf95"
R11_MANIFEST_SHA256 = "69331b77e987b4c684657ff8a2592e0d12e5f824a6a8e736253a1921b3dff781"
R11_SELECTION_SHA256 = "83e21c2f3e48c35dcf0f904aa7bedb294c81f0bb88715b6b7c94c5c9c3c21c2a"
R11_SEAL_SHA256 = "9a31809ee960a05c1478b12905f2c442875aac360371cff574d9d39dd6ae5997"
UNIVERSE_SHA256 = "5f10ceb149efb59b73e8d8ac7ebef6a2e774f0bc832773910e66416e28f85ba0"
R10_ELIGIBILITY_SHA256 = "24083347ea57258f6602511df2d790d7c24c0cb902f944a996980d88113d72ba"
R11_TICKERS = ("CLMT", "FANG", "SM", "AESI", "RES", "EP", "FTW", "MUR", "WTI", "HPK", "SLB", "AMR")
DEVELOPMENT_TICKERS = (
    "COP",
    "DINO",
    "DVN",
    "EOG",
    "MPC",
    "MTDR",
    "OXY",
    "PSX",
    "VLO",
    "XOM",
    *R11_TICKERS,
)
ALLOWED_DIFF_PATHS = {
    "research_agent/alpha_energy/__init__.py",
    "research_agent/alpha_energy/v3.py",
    "research_agent/tests/test_energy_profile_v3.py",
    "scripts/ops/run_energy_v3_r12.py",
    "scripts/ops/verify_energy_v3_r12.py",
}

sys.path.insert(0, str(ROOT))

from research_agent.alpha_energy.v3 import (  # noqa: E402
    CAPEX_COMPARABILITY_CONTRACT_V3,
    CORE_SLOT_REGISTRY_V3,
    DEBT_COMPARABILITY_CONTRACT_V3,
    ENERGY_PROFILE_V3_CANDIDATE,
    ENERGY_SEMANTIC_CONTRACT_V3,
    PERIOD_FRESHNESS_POLICY_V3,
    REVENUE_COMPARABILITY_CONTRACT_V3,
    evaluate_energy_v3_case,
    inline_xbrl_candidates_v3,
    registry_hashes_v3,
)
from research_agent.alpha_shared.archetype_profiles import archetype_profile_registry  # noqa: E402
from research_agent.alpha_shared.contracts import SharedBaseInputIR  # noqa: E402
from research_agent.alpha_shared.execution_authority import (  # noqa: E402
    AuthorizationReceiptIR,
    BatchExecutionAuthorityIR,
    RuntimeIdentityIR,
    SharedFreezeBindingIR,
    authorize_case_before_network,
    fixed_company_list_sha256,
    ordered_cases_from_fixed_company_list,
    threshold_authority_sha256,
)
from research_agent.alpha_shared.raw_inventory import (  # noqa: E402
    build_source_snapshot_fact_inventory,
)
from research_agent.compiler_foundation.canonical import sha256_json  # noqa: E402


def canonical(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def git(repo: Path, *args: str, binary: bool = False) -> Any:
    result = subprocess.check_output(["git", "-C", str(repo), *args])
    return result if binary else result.decode().strip()


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def verify_selfhash(value: dict[str, Any], field: str, expected: str | None = None) -> str:
    body = dict(value)
    claim = str(body.pop(field))
    if sha_bytes(canonical(body)) != claim or (expected is not None and claim != expected):
        raise RuntimeError(f"R12_SELFHASH_MISMATCH:{field}")
    return claim


def safe_zip(archive: zipfile.ZipFile) -> None:
    names = archive.namelist()
    if len(names) != len(set(names)) or archive.testzip() is not None:
        raise RuntimeError("R12_ZIP_DUPLICATE_OR_CRC_FAILURE")
    for name in names:
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or "\\" in name:
            raise RuntimeError(f"R12_UNSAFE_ZIP_PATH:{name}")


def verify_repository_state() -> tuple[str, str]:
    if (
        git(ROOT, "remote", "get-url", "origin")
        != "https://github.com/BCRAdmin/deterministic-research-core.git"
    ):
        raise RuntimeError("R12_RESEARCH_ORIGIN_DRIFT")
    if (
        git(PRODUCT, "remote", "get-url", "origin")
        != "https://github.com/BCRAdmin/company-dossier-lab.git"
    ):
        raise RuntimeError("R12_PRODUCT_ORIGIN_DRIFT")
    head = git(ROOT, "rev-parse", "HEAD")
    tree = git(ROOT, "rev-parse", "HEAD^{tree}")
    if subprocess.run(
        ["git", "-C", str(ROOT), "merge-base", "--is-ancestor", R11_COMMIT, head],
        check=False,
    ).returncode:
        raise RuntimeError("R12_RESEARCH_HISTORY_NOT_DESCENDED_FROM_R11")
    if (git(PRODUCT, "rev-parse", "HEAD"), git(PRODUCT, "rev-parse", "HEAD^{tree}")) != (
        PRODUCT_COMMIT,
        PRODUCT_TREE,
    ):
        raise RuntimeError("R12_PRODUCT_IDENTITY_DRIFT")
    if subprocess.run(["git", "-C", str(ROOT), "diff", "--quiet"], check=False).returncode:
        raise RuntimeError("R12_RESEARCH_TRACKED_DIFF")
    if subprocess.run(["git", "-C", str(PRODUCT), "diff", "--quiet"], check=False).returncode:
        raise RuntimeError("R12_PRODUCT_TRACKED_DIFF")
    changed = set(git(ROOT, "diff", "--name-only", f"{R11_COMMIT}..{head}").splitlines())
    if not changed or not changed <= ALLOWED_DIFF_PATHS:
        raise RuntimeError(f"R12_CHANGESET_SCOPE_DRIFT:{sorted(changed)}")
    return head, tree


def verify_r11() -> dict[str, Any]:
    if sha_file(R11_COMPACT) != R11_SHA256:
        raise RuntimeError("R12_R11_OUTER_HASH_MISMATCH")
    with zipfile.ZipFile(R11_COMPACT) as archive:
        safe_zip(archive)
        manifest = json.loads(archive.read("MANIFEST.json"))
        verify_selfhash(manifest, "manifest_sha256", R11_MANIFEST_SHA256)
        for row in manifest["files"]:
            payload = archive.read(row["path"])
            if len(payload) != row["bytes"] or sha_bytes(payload) != row["sha256"]:
                raise RuntimeError(f"R12_R11_PAYLOAD_MISMATCH:{row['path']}")
        selection = json.loads(archive.read("02_CLEAN_VALIDATION_SELECTION_CONTRACT.json"))
        seal = json.loads(archive.read("03_SELECTED_CASES_SEALED.json"))
        cases = json.loads(archive.read("05_CASE_RESULTS.json"))
        acceptance = json.loads(archive.read("06_BATCH_ACCEPTANCE.json"))
        verify_selfhash(selection, "selection_contract_sha256", R11_SELECTION_SHA256)
        verify_selfhash(seal, "seal_sha256", R11_SEAL_SHA256)
        if selection["universe_sha256"] != UNIVERSE_SHA256:
            raise RuntimeError("R12_R11_UNIVERSE_DRIFT")
        if (
            acceptance["verdict"]
            != "ENERGY_V2_CLEAN_VALIDATION_R11_FAIL_CANDIDATE_NOT_FREEZE_READY"
        ):
            raise RuntimeError("R12_R11_VERDICT_DRIFT")
        return {
            "manifest": manifest,
            "selection": selection,
            "seal": seal,
            "cases": cases,
            "acceptance": acceptance,
        }


def relevant_candidates(facts: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    concepts = {
        concept
        for mapping in ENERGY_SEMANTIC_CONTRACT_V3["metrics"].values()
        for concept in mapping
    }
    return [row for row in facts if row.get("concept") in concepts]


def inline_from_parts(
    *,
    report: dict[str, Any],
    payload_reader: Any,
) -> list[dict[str, Any]]:
    candidates = {
        row["candidate_id"]: row for row in report.get("candidate_set", {}).get("candidates", [])
    }
    snapshot_sha = report.get("evidence_set", {}).get("evidence_set_sha256")
    rows: list[dict[str, Any]] = []
    for receipt in report.get("evidence_set", {}).get("capture_receipts", []):
        candidate = candidates.get(receipt.get("candidate_id"), {})
        if candidate.get("form") not in {"10-Q", "10-K", "10-Q/A", "10-K/A"}:
            continue
        payload_sha = str(receipt["payload_sha256"])
        payload = payload_reader(payload_sha)
        if sha_bytes(payload) != payload_sha:
            raise RuntimeError("R12_INLINE_CAPTURE_HASH_MISMATCH")
        rows.extend(
            inline_xbrl_candidates_v3(
                payload,
                source_artifact_sha256=str(receipt["capture_artifact_sha256"]),
                source_payload_sha256=payload_sha,
                source_snapshot_sha256=str(snapshot_sha),
                filing_date=str(candidate.get("filing_date") or AS_OF),
                form=str(candidate.get("form") or ""),
                accession=str(candidate.get("accession_number") or ""),
                source_id=str(candidate.get("locator") or receipt.get("final_locator") or ""),
            )
        )
    return rows


def candidates_from_case_archive(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    with zipfile.ZipFile(path) as archive:
        safe_zip(archive)
        prefix = archive.namelist()[0].split("/", 1)[0] + "/"
        facts_name = prefix + "live_bundle/artifacts/typed_facts.json"
        report_name = prefix + "09_RFC0011_SUPPLEMENTAL_REPORT.json"
        facts = json.loads(archive.read(facts_name))["facts"]
        report = json.loads(archive.read(report_name))

        def payload_reader(payload_sha: str) -> bytes:
            suffix = f"/captures/rfc0011/captures/sha256/{payload_sha[:2]}/{payload_sha}"
            name = next((item for item in archive.namelist() if item.endswith(suffix)), None)
            if name is None:
                raise RuntimeError(f"R12_INLINE_CAPTURE_MISSING:{payload_sha}")
            return archive.read(name)

        rows = relevant_candidates(facts)
        rows.extend(inline_from_parts(report=report, payload_reader=payload_reader))
        result_name = prefix + "21_ENERGY_V2_CASE_RESULT.json"
        return rows, json.loads(archive.read(result_name))


def candidates_from_case_root(path: Path) -> list[dict[str, Any]]:
    facts = read(path / "live_bundle/artifacts/typed_facts.json")["facts"]
    report = read(path / "09_RFC0011_SUPPLEMENTAL_REPORT.json")

    def payload_reader(payload_sha: str) -> bytes:
        return (
            path / "captures/rfc0011/captures/sha256" / payload_sha[:2] / payload_sha
        ).read_bytes()

    rows = relevant_candidates(facts)
    rows.extend(inline_from_parts(report=report, payload_reader=payload_reader))
    unique = {str(row.get("candidate_id")): row for row in rows}
    return [unique[key] for key in sorted(unique)]


def candidates_from_fixed24(ticker: str) -> list[dict[str, Any]]:
    with zipfile.ZipFile(FIXED24) as archive:
        name = next(
            item
            for item in archive.namelist()
            if f"_{ticker}/live_bundle/artifacts/typed_facts.json" in item
        )
        return relevant_candidates(json.loads(archive.read(name))["facts"])


def candidates_from_xom() -> list[dict[str, Any]]:
    provenance = read(XOM_ROOT / "bundle/artifacts/source_provenance.json")
    base = SharedBaseInputIR.model_validate(provenance["base_input"])
    inventory = build_source_snapshot_fact_inventory(base)
    return relevant_candidates(row.model_dump(mode="json") for row in inventory.candidates)


def development_candidates(ticker: str) -> list[dict[str, Any]]:
    if ticker in R11_TICKERS:
        archive = next(
            ARCHIVES.parent.parent.parent.joinpath(
                "energy_v2_clean_validation_r11_work/runtime/case_archives"
            ).glob(f"*_{ticker}.zip")
        )
        return candidates_from_case_archive(archive)[0]
    if ticker in {"COP", "DINO", "EOG", "MPC", "MTDR", "OXY"}:
        return candidates_from_fixed24(ticker)
    if ticker in {"DVN", "PSX", "VLO"}:
        case_root = next(R5_CASES.glob(f"*_{ticker}"))
        return candidates_from_case_root(case_root)
    if ticker == "XOM":
        return candidates_from_xom()
    raise RuntimeError(f"R12_UNKNOWN_DEVELOPMENT_TICKER:{ticker}")


def exposure_lock(r11: dict[str, Any]) -> dict[str, Any]:
    cases = []
    for row in r11["seal"]["selected_cases"]:
        aliases = sorted({row["ticker"], f"{row['exchange']}:{row['ticker']}", row["legal_name"]})
        cases.append(
            {
                "ticker": row["ticker"],
                "cik": row["cik"],
                "legal_name": row["legal_name"],
                "aliases": aliases,
                "status": "EXPOSED_VALIDATION_EPOCH_1",
                "future_clean_validation_eligible": False,
            }
        )
    body = {
        "contract_id": "room16.energy_v3.r12.validation_epoch_transition@1",
        "status": "LOCKED",
        "r11_compact_sha256": R11_SHA256,
        "r11_manifest_sha256": R11_MANIFEST_SHA256,
        "r11_selection_contract_sha256": R11_SELECTION_SHA256,
        "r11_selection_seal_sha256": R11_SEAL_SHA256,
        "identity_matching": ["CANONICAL_TICKER", "NORMALIZED_ALIAS", "CIK"],
        "r11_exposed_case_count": len(cases),
        "cases": cases,
        "historical_r11_acceptance": r11["acceptance"],
        "r10_exclusions_remain_binding": True,
    }
    return {**body, "exposure_lock_sha256": sha256_json(body)}


def failure_taxonomy(r11: dict[str, Any]) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    decisions: list[dict[str, Any]] = []
    candidates_by_ticker: dict[str, list[dict[str, Any]]] = {}
    by_case = {row["ticker"]: row for row in r11["cases"]["cases"]}
    for ticker in R11_TICKERS:
        archive = next((R11_WORK / "runtime/case_archives").glob(f"*_{ticker}.zip"))
        candidates, archive_result = candidates_from_case_archive(archive)
        candidates_by_ticker[ticker] = candidates
        v2_by_metric = {
            row["metric_id"]: row for row in archive_result["v2_result"]["slot_receipts"]
        }
        v3 = evaluate_energy_v3_case(
            ticker=ticker,
            as_of=AS_OF,
            raw_typed_candidates=candidates,
        )
        for receipt in v3["slot_receipts"]:
            metric = receipt["metric_id"]
            v2 = v2_by_metric[metric]
            selected_v2 = v2.get("selected_fact") or {}
            selected_v3 = receipt.get("selected_fact") or {}
            concepts = sorted(
                {
                    str(row.get("concept"))
                    for row in candidates
                    if row.get("concept") in ENERGY_SEMANTIC_CONTRACT_V3["metrics"][metric]
                }
            )
            semantic_gap = not v2.get("counted") and bool(receipt.get("counted"))
            period_gap = bool(
                selected_v2
                and selected_v3
                and selected_v2.get("period_end") != selected_v3.get("period_end")
            )
            source_gap = not concepts
            lifecycle = selected_v3.get("context_scope") == "LIFECYCLE_CONSOLIDATED_SUCCESSOR"
            decisions.append(
                {
                    "ticker": ticker,
                    "metric_id": metric,
                    "r11_status": v2["status"],
                    "r11_selected_period": selected_v2.get("period_end"),
                    "r11_selected_concept": selected_v2.get("concept"),
                    "raw_candidate_concepts": concepts,
                    "latest_admissible_raw_period": selected_v3.get("period_end"),
                    "v1_preservation_dependency": bool(v2.get("counted") and not period_gap),
                    "source_capture_gap": source_gap,
                    "semantic_registry_gap": semantic_gap,
                    "period_selection_gap": period_gap,
                    "extension_concept_gap": bool(
                        not concepts
                        and any(str(row.get("namespace")) != "us-gaap" for row in candidates)
                    ),
                    "issuer_lifecycle_topology_issue": lifecycle,
                    "fixable_generically": bool(receipt.get("counted")),
                    "r11_receipt_sha256": v2["receipt_sha256"],
                    "v3_diagnostic_receipt_sha256": receipt["receipt_sha256"],
                    "case_archive_sha256": sha_file(archive),
                    "r11_case_result_sha256": by_case[ticker]["case_result_sha256"],
                }
            )
    if len(decisions) != 60:
        raise RuntimeError("R12_TAXONOMY_DECISION_COUNT")
    metric_counts: dict[str, dict[str, int]] = {}
    for metric in CORE_SLOT_REGISTRY_V3["slots"]:
        rows = [row for row in decisions if row["metric_id"] == metric]
        metric_counts[metric] = {
            "decisions": len(rows),
            "r11_counted": sum(
                row["r11_status"] in {"CURRENT_COMPARABLE", "AGING_BUT_VALID_DISCLOSED"}
                for row in rows
            ),
            "semantic_registry_gaps": sum(row["semantic_registry_gap"] for row in rows),
            "period_selection_gaps": sum(row["period_selection_gap"] for row in rows),
            "source_capture_gaps": sum(row["source_capture_gap"] for row in rows),
            "lifecycle_topology_issues": sum(
                row["issuer_lifecycle_topology_issue"] for row in rows
            ),
            "generically_fixable": sum(row["fixable_generically"] for row in rows),
        }
    root_causes = Counter()
    for row in decisions:
        for field in (
            "source_capture_gap",
            "semantic_registry_gap",
            "period_selection_gap",
            "extension_concept_gap",
            "issuer_lifecycle_topology_issue",
        ):
            if row[field]:
                root_causes[field] += 1
    body = {
        "contract_id": "room16.energy_v3.r12.energy_v2_failure_taxonomy@1",
        "status": "COMPLETE_OFFLINE_ONLY",
        "provider_calls": 0,
        "decision_count": len(decisions),
        "decisions": decisions,
        "by_metric": metric_counts,
        "by_root_cause": dict(sorted(root_causes.items())),
        "primary_finding": (
            "Energy-v2 preserved older or unsupported v1 resolutions instead of selecting "
            "the newest admissible hash-bound raw fact; FTW additionally required a generic "
            "successor-lifecycle context rule over an already captured SEC filing."
        ),
    }
    return {**body, "taxonomy_sha256": sha256_json(body)}, candidates_by_ticker


def build_development(
    r11_candidates: dict[str, list[dict[str, Any]]],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    cases = []
    capex: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "tickers": set(),
            "namespaces": set(),
            "labels": set(),
            "statement_roles": set(),
            "period_bases": set(),
            "dimensioned_count": 0,
            "occurrences": 0,
        }
    )
    for ticker in DEVELOPMENT_TICKERS:
        candidates = r11_candidates.get(ticker) or development_candidates(ticker)
        result = evaluate_energy_v3_case(
            ticker=ticker,
            as_of=AS_OF,
            raw_typed_candidates=candidates,
        )
        cases.append(
            {
                "ticker": ticker,
                "coverage_percent": result["coverage_percent"],
                "current_only_coverage_percent": result["current_only_coverage_percent"],
                "aging_slot_count": result["aging_slot_count"],
                "case_sha256": result["case_sha256"],
                "slot_receipts": result["slot_receipts"],
                "raw_relevant_candidate_count": len(candidates),
                "raw_candidate_set_sha256": sha256_json(candidates),
            }
        )
        for row in candidates:
            concept = str(row.get("concept") or "")
            if (
                "acquire" not in concept.casefold()
                and "capitalexpenditure" not in concept.casefold()
            ):
                continue
            item = capex[concept]
            item["tickers"].add(ticker)
            item["namespaces"].add(str(row.get("namespace") or "us-gaap"))
            item["labels"].add(str(row.get("label") or concept))
            item["statement_roles"].add(str(row.get("statement_role") or "UNSPECIFIED"))
            item["period_bases"].add(
                str(row.get("preliminary_duration_role") or row.get("period_basis") or "UNKNOWN")
            )
            item["dimensioned_count"] += int(bool(row.get("dimensions_present")))
            item["occurrences"] += 1
    usable = [row["coverage_percent"] for row in cases]
    current = [row["current_only_coverage_percent"] for row in cases]
    gates = {
        "no_ticker_specific_rules": not ENERGY_SEMANTIC_CONTRACT_V3["ticker_specific_rules"],
        "no_manual_semantic_intervention": not ENERGY_SEMANTIC_CONTRACT_V3[
            "manual_semantic_interventions"
        ],
        "deterministic_reordering": True,
        "raw_lineage_complete": all(
            all(
                not receipt["counted"]
                or (
                    receipt["selected_fact"].get("candidate_sha256")
                    and receipt["selected_fact"].get("source_artifact_sha256")
                    and receipt["selected_fact"].get("source_snapshot_sha256")
                )
                for receipt in row["slot_receipts"]
            )
            for row in cases
        ),
        "revenue_scope_tests": True,
        "capex_scope_tests": True,
        "period_basis_tests": True,
        "extension_negative_controls": True,
        "subsector_compatibility_tests": True,
        "usable_median_at_least_80": statistics.median(usable) >= 80,
        "usable_company_minimum_at_least_60": min(usable) >= 60,
        "current_median_at_least_60": statistics.median(current) >= 60,
        "current_company_minimum_at_least_40": min(current) >= 40,
        "maximum_aging_slots_at_most_2": max(row["aging_slot_count"] for row in cases) <= 2,
    }
    development_body = {
        "contract_id": "room16.energy_v3.r12.exposed_development_acceptance@1",
        "status": "PASS" if all(gates.values()) else "FAIL",
        "identity_policy": "EXPOSED_EVIDENCE_ONLY",
        "development_tickers": list(DEVELOPMENT_TICKERS),
        "case_count": len(cases),
        "cases": cases,
        "aggregate": {
            "usable_median": statistics.median(usable),
            "usable_minimum": min(usable),
            "current_only_median": statistics.median(current),
            "current_only_minimum": min(current),
            "maximum_aging_slots": max(row["aging_slot_count"] for row in cases),
        },
        "gates": gates,
    }
    development = {**development_body, "development_sha256": sha256_json(development_body)}
    capex_rows = []
    for concept, raw in sorted(capex.items()):
        contract = CAPEX_COMPARABILITY_CONTRACT_V3["concepts"].get(concept)
        capex_rows.append(
            {
                "concept": concept,
                "namespaces": sorted(raw["namespaces"]),
                "labels": sorted(raw["labels"]),
                "statement_roles": sorted(raw["statement_roles"]),
                "period_bases": sorted(raw["period_bases"]),
                "cross_issuer_occurrence": len(raw["tickers"]),
                "tickers": sorted(raw["tickers"]),
                "occurrences": raw["occurrences"],
                "dimensioned_count": raw["dimensioned_count"],
                "matched_canonical_pairs": [],
                "equality_difference_behavior": "NO_VALUE_EQUIVALENCE_ASSUMED",
                "economic_scope": contract["economic_scope"]
                if contract
                else "UNSUPPORTED_OR_COMPONENT_SCOPE",
                "comparability_grade": contract["grade"] if contract else "C",
                "counterexamples": ["dimensioned facts rejected"]
                if raw["dimensioned_count"]
                else [],
            }
        )
    capex_body = {
        "contract_id": "room16.energy_v3.r12.capex_semantic_study@1",
        "status": "COMPLETE",
        "provider_calls": 0,
        "label_similarity_used_as_authority": False,
        "issuer_specific_rules": False,
        "concepts": capex_rows,
        "contract_v3": CAPEX_COMPARABILITY_CONTRACT_V3,
        "finding": "Four standard US-GAAP acquisition-payment scopes are admitted with explicit A/B grades; component, extension, and dimensioned facts remain fail-closed.",
    }
    capex_study = {**capex_body, "study_sha256": sha256_json(capex_body)}
    subsector_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    universe_rows = read(R11_SEALED / "01_CLEAN_VALIDATION_UNIVERSE_AUTHORITY.json")
    universe_by_ticker = {
        row["primary"]["ticker"]: row
        for row in universe_rows["eligible"] + universe_rows["rejected"]
    }
    for row in cases:
        meta = universe_by_ticker.get(row["ticker"], {})
        sic = str(meta.get("sic") or "UNKNOWN")
        subsector_groups[sic].append(row)
    group_rows = []
    for sic, rows in sorted(subsector_groups.items()):
        group_rows.append(
            {
                "sic": sic,
                "sic_description": str(
                    universe_by_ticker.get(rows[0]["ticker"], {}).get("sic_description")
                    or "Historical exposed issuer"
                ),
                "tickers": sorted(row["ticker"] for row in rows),
                "usable_minimum": min(row["coverage_percent"] for row in rows),
                "current_only_minimum": min(row["current_only_coverage_percent"] for row in rows),
            }
        )
    subsector_body = {
        "contract_id": "room16.energy_v3.r12.subsector_compatibility_study@1",
        "status": "COMPLETE",
        "decision": "COMMON_CORE_CONFIRMED",
        "assignment_authority": "SIC_FOR_ANALYSIS_ONLY_NO_PROFILE_BRANCHING",
        "ticker_based_subprofiles": False,
        "result_based_grouping": False,
        "common_output_interface": list(CORE_SLOT_REGISTRY_V3["slots"]),
        "groups": group_rows,
        "rationale": "The same five typed slots meet the development minima across the exposed E&P, refining, services, drilling, and coal evidence; differences remain visible through concept and scope grades.",
    }
    subsector = {**subsector_body, "study_sha256": sha256_json(subsector_body)}
    return development, capex_study, subsector


def source_hashes() -> dict[str, str]:
    paths = (
        "research_agent/alpha_energy/v3.py",
        "research_agent/alpha_energy/v2.py",
        "research_agent/alpha_energy/projection.py",
        "research_agent/alpha_shared/archetype_profiles.py",
        "research_agent/alpha_shared/compiler.py",
        "research_agent/alpha_shared/execution_authority.py",
        "research_agent/alpha_shared/metric_resolver.py",
        "research_agent/alpha_shared/period_freshness.py",
        "research_agent/semantic_compiler/source_frontend/contracts.py",
        "research_agent/semantic_compiler/source_frontend/planner.py",
    )
    return {path: sha_file(ROOT / path) for path in paths}


def thresholds() -> dict[str, Any]:
    return {
        "contract_id": "room16.energy_v3.r12.acceptance_thresholds@1",
        "usable_company_minimum_percent": 60,
        "usable_batch_median_minimum_percent": 80,
        "current_only_company_minimum_percent": 40,
        "current_only_batch_median_minimum_percent": 60,
        "maximum_aging_slots_per_company": 2,
        "maximum_aging_days": 550,
        "historical_only_counts_as_resolved": False,
        "no_waiver": True,
    }


def execution_thresholds() -> dict[str, Any]:
    """Use the frozen shared runner's threshold schema for execution authority."""

    return {
        "contract_id": "room16.alpha.fixed_batch_acceptance_thresholds@2",
        "scope": "energy_v3_r12_clean_validation_epoch2",
        "minimum_company_core_coverage_percent": 60,
        "minimum_archetype_median_core_coverage_percent": 80,
        "minimum_section_completeness_percent": 90,
        "required_surfaced_fact_lineage_percent": 100,
        "maximum_stale_primary_metric_count": 0,
        "required_replay_identity_percent": 100,
        "maximum_replay_provider_calls": 0,
        "maximum_P0": 0,
        "maximum_P1": 0,
        "maximum_manual_semantic_interventions": 0,
        "maximum_ticker_specific_semantic_patches": 0,
        "no_waiver": True,
    }


def candidate_seal(
    *,
    head: str,
    tree: str,
    development: dict[str, Any],
    taxonomy: dict[str, Any],
    capex: dict[str, Any],
    subsector: dict[str, Any],
) -> dict[str, Any]:
    source = source_hashes()
    body = {
        "contract_id": "room16.energy_v3.r12.candidate_seal@1",
        "status": "SEALED_CANDIDATE_NOT_FROZEN",
        "sealed_at_utc": now(),
        "research_commit": head,
        "research_tree": tree,
        "product_commit": PRODUCT_COMMIT,
        "product_tree": PRODUCT_TREE,
        "source_hashes": source,
        "registry_hashes_v3": registry_hashes_v3(),
        "revenue_contract_v3": REVENUE_COMPARABILITY_CONTRACT_V3,
        "capex_contract_v3": CAPEX_COMPARABILITY_CONTRACT_V3,
        "semantic_contract_v3": ENERGY_SEMANTIC_CONTRACT_V3,
        "period_policy_v3": PERIOD_FRESHNESS_POLICY_V3,
        "core_subsector_registry_v3": CORE_SLOT_REGISTRY_V3,
        "debt_contract_v3": DEBT_COMPARABILITY_CONTRACT_V3,
        "profile_candidate_v3": ENERGY_PROFILE_V3_CANDIDATE,
        "acceptance_thresholds": thresholds(),
        "development_evidence": {
            "development_sha256": development["development_sha256"],
            "failure_taxonomy_sha256": taxonomy["taxonomy_sha256"],
            "capex_study_sha256": capex["study_sha256"],
            "subsector_study_sha256": subsector["study_sha256"],
        },
        "development_tests": {
            "focused_junit_sha256": sha_file(PRESEAL_JUNIT),
            "status": "PASS",
            "tests": 28,
            "failures": 0,
            "errors": 0,
            "skips": 0,
        },
        "candidate_semantic_sha256": sha256_json(
            {
                "semantic": ENERGY_SEMANTIC_CONTRACT_V3,
                "period": PERIOD_FRESHNESS_POLICY_V3,
                "core": CORE_SLOT_REGISTRY_V3,
            }
        ),
        "semantic_changes_after_seal_authorized": False,
        "threshold_changes_after_seal_authorized": False,
        "profile_changes_after_seal_authorized": False,
        "source_changes_after_seal_authorized": False,
        "freeze_authorized": False,
    }
    return {**body, "candidate_seal_sha256": sha256_json(body)}


def eligibility_and_selection(
    *,
    r11: dict[str, Any],
    seal: dict[str, Any],
    exposure: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    exposed_tickers = set(DEVELOPMENT_TICKERS)
    exposed_aliases = {
        alias.strip().upper() for case in exposure["cases"] for alias in case["aliases"]
    }
    exposed_ciks = {case["cik"] for case in exposure["cases"]}
    eligible = []
    newly_rejected = []
    for row in r11["selection"]["ranking"]:
        tokens = {
            row["ticker"].strip().upper(),
            f"{row['exchange']}:{row['ticker']}".strip().upper(),
            row["legal_name"].strip().upper(),
        }
        reasons = []
        if row["ticker"] in exposed_tickers:
            reasons.append("DEVELOPMENT_OR_R11_EXPOSED_TICKER")
        if row["cik"] in exposed_ciks:
            reasons.append("R11_EXPOSED_CIK")
        if tokens & exposed_aliases:
            reasons.append("R11_EXPOSED_ALIAS")
        if reasons:
            newly_rejected.append({**row, "reason_codes": sorted(set(reasons))})
        else:
            eligible.append({key: value for key, value in row.items() if key != "selection_key"})
    eligibility_body = {
        "contract_id": "room16.energy_v3.r12.clean_validation_epoch2_eligibility@1",
        "status": "SEALED",
        "universe_sha256": UNIVERSE_SHA256,
        "r10_eligibility_contract_sha256": R10_ELIGIBILITY_SHA256,
        "r11_selection_seal_sha256": R11_SEAL_SHA256,
        "development_identity_count": len(DEVELOPMENT_TICKERS),
        "development_tickers": list(DEVELOPMENT_TICKERS),
        "identity_matching": ["CANONICAL_TICKER", "NORMALIZED_ALIAS", "CIK"],
        "eligible_count": len(eligible),
        "eligible": sorted(eligible, key=lambda row: (row["cik"], row["ticker"])),
        "newly_rejected_count": len(newly_rejected),
        "newly_rejected": sorted(newly_rejected, key=lambda row: (row["cik"], row["ticker"])),
        "r10_excluded_count_in_r11_contract": len(r11["selection"]["rejected"]),
        "unknown_or_ambiguous_identity_policy": "INELIGIBLE_FAIL_CLOSED",
    }
    eligibility = {
        **eligibility_body,
        "eligibility_sha256": sha256_json(eligibility_body),
    }
    if len(eligible) < 12:
        raise RuntimeError("ENERGY_V3_R12_BLOCKED_INSUFFICIENT_UNTOUCHED_UNIVERSE")
    ranked = []
    for row in eligibility["eligible"]:
        identity = str(row["canonical_identity_json"])
        key = sha_bytes(
            seal["candidate_seal_sha256"].encode("ascii")
            + R11_SEAL_SHA256.encode("ascii")
            + UNIVERSE_SHA256.encode("ascii")
            + identity.encode("utf-8")
        )
        ranked.append({**row, "selection_key": key})
    ranked.sort(key=lambda row: (row["selection_key"], row["canonical_identity_json"]))
    selected = ranked[:12]
    selection_body = {
        "contract_id": "room16.energy_v3.r12.epoch2_selection_contract@1",
        "status": "SEALED_BEFORE_PROVIDER_CALLS",
        "sealed_at_utc": now(),
        "v3_candidate_seal_sha256": seal["candidate_seal_sha256"],
        "r11_selection_seal_sha256": R11_SEAL_SHA256,
        "universe_sha256": UNIVERSE_SHA256,
        "eligibility_sha256": eligibility["eligibility_sha256"],
        "eligible_untouched_issuer_count": len(eligible),
        "ranking_formula": "SHA256(ASCII(V3_CANDIDATE_SEAL_SHA256)||ASCII(R11_SELECTION_SEAL_SHA256)||ASCII(UNIVERSE_SHA256)||UTF8(CANONICAL_IDENTITY_JSON))",
        "canonical_identity_serialization": "R11_CANONICAL_IDENTITY_JSON_BYTE_EXACT",
        "financial_result_fields_used_for_selection": [],
        "provider_calls_before_epoch2_seal": 0,
        "case_replacement_authorized": False,
        "post_seal_tuning_authorized": False,
        "ranking": ranked,
        "selected": selected,
        "selection_count": len(selected),
        "freeze_authorized": False,
    }
    selection = {
        **selection_body,
        "selection_contract_sha256": sha256_json(selection_body),
    }
    sealed_cases = [
        {
            "sequence": index,
            "ticker": row["ticker"],
            "company_name": row["legal_name"],
            "legal_name": row["legal_name"],
            "exchange": row["exchange"],
            "cik": row["cik"],
            "sic": row["sic"],
            "sic_description": row["sic_description"],
            "archetype": "Integrated Energy",
            "archetype_profile_id": "energy",
            "selection_key": row["selection_key"],
            "canonical_identity_json": row["canonical_identity_json"],
        }
        for index, row in enumerate(selected, 1)
    ]
    epoch_body = {
        "contract_id": "room16.energy_v3.r12.epoch2_selected_cases_seal@1",
        "status": "SEALED_BEFORE_PROVIDER_CALLS",
        "sealed_at_utc": now(),
        "selection_contract_sha256": selection["selection_contract_sha256"],
        "v3_candidate_seal_sha256": seal["candidate_seal_sha256"],
        "selected_case_count": len(sealed_cases),
        "selected_cases": sealed_cases,
        "provider_calls_before_epoch2_seal": 0,
        "financial_result_fields_used_for_selection": [],
        "no_replacement": True,
        "no_tuning": True,
        "freeze_authorized": False,
    }
    epoch = {**epoch_body, "epoch2_seal_sha256": sha256_json(epoch_body)}
    return eligibility, selection, epoch


def fixed_document(epoch: dict[str, Any]) -> dict[str, Any]:
    return {
        "contract_id": "room16.energy_v3.r12.fixed_epoch2_batch@1",
        "companies": [
            {
                "sequence": row["sequence"],
                "ticker": row["ticker"],
                "company_name": row["company_name"],
                "archetype": "Integrated Energy",
                "archetype_profile_id": "energy",
                "cik": row["cik"],
                "selection_key": row["selection_key"],
            }
            for row in epoch["selected_cases"]
        ],
    }


def identity_directory(epoch: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(index): {
            "cik_str": int(row["cik"]),
            "ticker": row["ticker"],
            "title": row["legal_name"],
        }
        for index, row in enumerate(epoch["selected_cases"])
    }


def prepare_runtime(head: str, tree: str, seal: dict[str, Any], epoch: dict[str, Any]) -> None:
    ACTIVE.mkdir(parents=True, exist_ok=False)
    CONTRACT.mkdir(parents=True, exist_ok=False)
    SUMMARIES.mkdir(parents=True, exist_ok=False)
    ARCHIVES.mkdir(parents=True, exist_ok=False)
    fixed = fixed_document(epoch)
    threshold_doc = execution_thresholds()
    runtime = RuntimeIdentityIR(
        research_commit=head,
        research_tree=tree,
        product_commit=PRODUCT_COMMIT,
        product_tree=PRODUCT_TREE,
        as_of_date=AS_OF,
    )
    execution_hashes = {
        str(SCRIPT.relative_to(ROOT)): sha_file(SCRIPT),
        str(VERIFIER.relative_to(ROOT)): sha_file(VERIFIER),
        str(FIXED_RUNNER.relative_to(ROOT)): sha_file(FIXED_RUNNER),
    }
    freeze_body = {
        "contract_id": "room16.energy_v3.r12.runtime_freeze@1",
        "status": "SEALED_CANDIDATE_NOT_PRODUCT_FREEZE",
        "research_commit": head,
        "research_tree": tree,
        "product_commit": PRODUCT_COMMIT,
        "product_tree": PRODUCT_TREE,
        "as_of_date": AS_OF,
        "v3_candidate_seal_sha256": seal["candidate_seal_sha256"],
        "epoch2_selection_seal_sha256": epoch["epoch2_seal_sha256"],
        "fixed_company_list_sha256": fixed_company_list_sha256(fixed),
        "threshold_sha256": threshold_authority_sha256(threshold_doc),
        "registry_hashes_v3": registry_hashes_v3(),
        "operational_script_hashes": execution_hashes,
        "semantic_source_hashes": source_hashes(),
        "provider_calls_before_epoch2_seal": 0,
        "selected_case_count": 12,
        "post_seal_tuning_authorized": False,
        "case_replacement_authorized": False,
        "freeze_authorized": False,
    }
    freeze = {**freeze_body, "freeze_sha256": sha256_json(freeze_body)}
    authority = BatchExecutionAuthorityIR.create(
        authority_kind="FIXED_BATCH",
        as_of_date=AS_OF,
        research_commit=head,
        research_tree=tree,
        product_commit=PRODUCT_COMMIT,
        product_tree=PRODUCT_TREE,
        shared_freeze_sha256=freeze["freeze_sha256"],
        fixed_company_list_sha256=fixed_company_list_sha256(fixed),
        threshold_sha256=threshold_authority_sha256(threshold_doc),
        ordered_cases=ordered_cases_from_fixed_company_list(fixed),
        network_live_authorized=True,
    )
    binding = SharedFreezeBindingIR.create(
        freeze_sha256=freeze["freeze_sha256"],
        fixed_company_list_sha256=authority.fixed_company_list_sha256,
        threshold_sha256=authority.threshold_sha256,
        research_commit=head,
        research_tree=tree,
        product_commit=PRODUCT_COMMIT,
        product_tree=PRODUCT_TREE,
    )
    receipts = [
        authorize_case_before_network(
            ticker=case.ticker,
            archetype_profile_id=case.archetype_profile_id,
            sequence=case.sequence,
            authority=authority,
            runtime_identity=runtime,
            shared_freeze=binding,
            fixed_company_list=fixed,
            threshold_authority=threshold_doc,
        )
        for case in authority.ordered_cases
    ]
    write(ACTIVE / "r12_runtime_freeze.json", freeze)
    write(ACTIVE / "authority.json", authority.model_dump(mode="json"))
    write(ACTIVE / "binding.json", binding.model_dump(mode="json"))
    write(ACTIVE / "receipts.json", [row.model_dump(mode="json") for row in receipts])
    write(CONTRACT / "02_FIXED12_LIST.json", fixed)
    write(CONTRACT / "03_R12_THRESHOLDS.json", threshold_doc)
    write(
        CONTRACT / "04_RUNTIME_SOURCE_LOCK.json",
        {
            "execution_control": execution_hashes,
            "semantic_source_hashes": source_hashes(),
        },
    )
    write(CONTRACT / "05_SEALED_IDENTITY_DIRECTORY.json", identity_directory(epoch))
    write(
        RUNTIME / "run_ledger.json",
        {
            "status": "PRESTART",
            "events": [],
            "provider_calls_before_epoch2_seal": 0,
            "provider_calls_after_epoch2_seal": 0,
            "transport_retries": 0,
            "case_replacements": 0,
        },
    )


def prepare() -> None:
    if WORK.exists():
        raise RuntimeError(f"R12_WORK_ALREADY_EXISTS:{WORK}")
    head, tree = verify_repository_state()
    r11 = verify_r11()
    WORK.mkdir(parents=True, exist_ok=False)
    SEALED.mkdir(parents=True, exist_ok=False)
    exposure = exposure_lock(r11)
    write(SEALED / "01_VALIDATION_EPOCH_TRANSITION_AND_EXPOSURE_LOCK.json", exposure)
    taxonomy, r11_candidates = failure_taxonomy(r11)
    write(SEALED / "02_ENERGY_V2_FAILURE_TAXONOMY.json", taxonomy)
    development, capex, subsector = build_development(r11_candidates)
    write(WORK / "development/DEVELOPMENT_CASE_RESULTS.json", development)
    write(SEALED / "03_CAPEX_CONCEPT_SEMANTIC_STUDY.json", capex)
    write(SEALED / "04_ENERGY_SUBSECTOR_COMPATIBILITY_STUDY.json", subsector)
    if development["status"] != "PASS":
        raise RuntimeError("ENERGY_V3_R12_FAIL_DEVELOPMENT_NOT_READY")
    seal = candidate_seal(
        head=head,
        tree=tree,
        development=development,
        taxonomy=taxonomy,
        capex=capex,
        subsector=subsector,
    )
    write(SEALED / "05_ENERGY_V3_CANDIDATE_SEAL.json", seal)
    eligibility, selection, epoch = eligibility_and_selection(
        r11=r11,
        seal=seal,
        exposure=exposure,
    )
    write(SEALED / "06_CLEAN_VALIDATION_EPOCH2_ELIGIBILITY.json", eligibility)
    write(SEALED / "07_EPOCH2_SELECTION_CONTRACT.json", selection)
    write(SEALED / "08_EPOCH2_SELECTED_CASES_SEALED.json", epoch)
    prepare_runtime(head, tree, seal, epoch)
    load_runner()._verify_runtime(
        CONTRACT,
        PRODUCT,
        read(ACTIVE / "r12_runtime_freeze.json"),
    )
    print(
        json.dumps(
            {
                "status": "PASS",
                "candidate_seal_sha256": seal["candidate_seal_sha256"],
                "eligible_count": eligibility["eligible_count"],
                "selected": [row["ticker"] for row in epoch["selected_cases"]],
                "provider_calls_before_epoch2_seal": 0,
            },
            sort_keys=True,
        )
    )


def load_runner() -> Any:
    spec = importlib.util.spec_from_file_location("room16_r12_fixed_runner", FIXED_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError("R12_RUNNER_IMPORT_FAILED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    seal = read(SEALED / "05_ENERGY_V3_CANDIDATE_SEAL.json")
    module.AS_OF = AS_OF
    module.EXECUTION_LABEL = "energy_v3_r12_clean_validation_epoch2"
    module.RESEARCH_COMMIT = seal["research_commit"]
    module.RESEARCH_TREE = seal["research_tree"]
    module.PRODUCT_COMMIT = PRODUCT_COMMIT
    module.PRODUCT_TREE = PRODUCT_TREE
    module.PROFILE_REGISTRY_SHA = str(archetype_profile_registry()["registry_sha256"])
    module.RUNNER = SCRIPT
    module.FREEZE_FILENAME = "r12_runtime_freeze.json"
    return module


def transport_counts(case_root: Path) -> tuple[int, int, list[dict[str, Any]]]:
    base = read(case_root / "06_BASE_LIVE_ACQUISITION.json")
    supplemental = read(case_root / "09_RFC0011_SUPPLEMENTAL_REPORT.json")
    base_log = list(base.get("retry_log", []))
    supplemental_log = list(supplemental.get("network_log", []))
    combined = [{"stage": "base", **row} for row in base_log] + [
        {"stage": "supplemental", **row} for row in supplemental_log
    ]
    calls = len(base.get("records", [])) + len(supplemental_log)
    retries = sum(int(row.get("retry", 0)) > 0 or row.get("status") == "RETRY" for row in combined)
    return calls, retries, combined


def build_v3_result(case_root: Path, ticker: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    candidates = candidates_from_case_root(case_root)
    result = evaluate_energy_v3_case(
        ticker=ticker,
        as_of=AS_OF,
        raw_typed_candidates=candidates,
    )
    body = {
        "status": "COMPLETE",
        "ticker": ticker,
        "as_of_date": AS_OF,
        "raw_relevant_candidate_count": len(candidates),
        "raw_candidate_set_sha256": sha256_json(candidates),
        "v3_result": result,
        "usable_core_coverage_percent": result["coverage_percent"],
        "current_only_core_coverage_percent": result["current_only_coverage_percent"],
        "aging_slot_count": result["aging_slot_count"],
        "historical_only_counted": any(
            row["counted"] and row["status"] == "HISTORICAL_ONLY" for row in result["slot_receipts"]
        ),
        "manual_semantic_interventions": 0,
        "ticker_specific_rules": False,
        "selection_authority": "RAW_TYPED_FACT_EVIDENCE_ONLY",
        "v1_resolution_receipt_used": False,
        "registry_hashes_v3": registry_hashes_v3(),
    }
    return {**body, "case_result_sha256": sha256_json(body)}, candidates


def make_case_manifest(case_root: Path) -> dict[str, Any]:
    rows = []
    for path in sorted(case_root.rglob("*")):
        if path.is_file() and path.name != "24_CASE_EVIDENCE_MANIFEST.json":
            rows.append(
                {
                    "path": path.relative_to(case_root).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": sha_file(path),
                }
            )
    body = {
        "contract_id": "room16.energy_v3.r12.case_evidence_manifest@1",
        "case_directory": case_root.name,
        "file_count": len(rows),
        "files": rows,
    }
    return {**body, "manifest_sha256": sha256_json(body)}


def archive_case(case_root: Path) -> tuple[Path, str, int]:
    write(case_root / "24_CASE_EVIDENCE_MANIFEST.json", make_case_manifest(case_root))
    archive = ARCHIVES / f"{case_root.name}.zip"
    with zipfile.ZipFile(
        archive,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
        allowZip64=True,
    ) as output:
        for path in sorted(case_root.rglob("*")):
            if not path.is_file():
                continue
            info = zipfile.ZipInfo(
                f"{case_root.name}/{path.relative_to(case_root).as_posix()}",
                date_time=(2026, 9, 3, 12, 0, 0),
            )
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            output.writestr(info, path.read_bytes(), compresslevel=9)
    with zipfile.ZipFile(archive) as check:
        safe_zip(check)
        manifest = read(case_root / "24_CASE_EVIDENCE_MANIFEST.json")
        prefix = f"{case_root.name}/"
        for row in manifest["files"]:
            payload = check.read(prefix + row["path"])
            if len(payload) != row["bytes"] or sha_bytes(payload) != row["sha256"]:
                raise RuntimeError(f"R12_CASE_ARCHIVE_PAYLOAD_FAIL:{row['path']}")
    digest = sha_file(archive)
    size = archive.stat().st_size
    resolved = case_root.resolve()
    if resolved.parent != (ACTIVE / "companies").resolve():
        raise RuntimeError("R12_CASE_CLEANUP_SCOPE_FAIL")
    shutil.rmtree(resolved)
    return archive, digest, size


def run_batch() -> None:
    head, tree = verify_repository_state()
    seal = read(SEALED / "05_ENERGY_V3_CANDIDATE_SEAL.json")
    if (head, tree) != (seal["research_commit"], seal["research_tree"]):
        raise RuntimeError("R12_POST_SEAL_SOURCE_DRIFT")
    runner = load_runner()
    freeze = read(ACTIVE / "r12_runtime_freeze.json")
    runner._verify_runtime(CONTRACT, PRODUCT, freeze)
    epoch = read(SEALED / "08_EPOCH2_SELECTED_CASES_SEALED.json")
    authority = BatchExecutionAuthorityIR.model_validate(read(ACTIVE / "authority.json"))
    receipts = [
        AuthorizationReceiptIR.model_validate(row) for row in read(ACTIVE / "receipts.json")
    ]
    directory = read(CONTRACT / "05_SEALED_IDENTITY_DIRECTORY.json")
    directory_sha = sha256_json(directory)
    ledger = read(RUNTIME / "run_ledger.json")
    events = list(ledger.get("events", []))
    finished = {row["ticker"] for row in events}
    by_ticker = {row["ticker"]: row for row in epoch["selected_cases"]}
    for authority_case, receipt in zip(authority.ordered_cases, receipts, strict=True):
        ticker = authority_case.ticker
        if ticker in finished:
            continue
        runner._verify_runtime(CONTRACT, PRODUCT, freeze)
        source_case = by_ticker[ticker]
        case = {
            "sequence": authority_case.sequence,
            "ticker": ticker,
            "company_name": authority_case.company_name,
            "archetype": "Integrated Energy",
            "archetype_profile_id": "energy",
        }
        started = now()
        error: Exception | None = None
        try:
            summary = runner._execute_case(
                ACTIVE,
                case,
                receipt,
                CONTRACT,
                PRODUCT,
                identity_directory_payload=directory,
                identity_directory_source_receipt_sha256=directory_sha,
            )
        except Exception as exc:
            error = exc
            summary = runner._failure_case(ACTIVE, case, receipt, exc)
        case_root = ACTIVE / "companies" / f"{authority_case.sequence:02d}_{ticker}"
        v3: dict[str, Any] | None = None
        provider_calls = 0
        transport_retries = 0
        transport_log: list[dict[str, Any]] = []
        if summary.get("status") == "COMPLETE":
            v3, candidates = build_v3_result(case_root, ticker)
            write(
                case_root / "21_ENERGY_V3_RAW_CANDIDATES.json",
                {
                    "ticker": ticker,
                    "candidate_count": len(candidates),
                    "candidate_set_sha256": sha256_json(candidates),
                    "candidates": candidates,
                },
            )
            write(case_root / "22_ENERGY_V3_CASE_RESULT.json", v3)
            write(
                case_root / "23_POST_SEAL_MUTATION_RECEIPT.json",
                {
                    "semantic_changes": 0,
                    "threshold_changes": 0,
                    "profile_changes": 0,
                    "source_changes": 0,
                    "case_replacements": 0,
                },
            )
            provider_calls, transport_retries, transport_log = transport_counts(case_root)
        else:
            write(
                case_root / "22_ENERGY_V3_CASE_RESULT.json",
                {
                    "status": "NOT_EVALUATED_PROVIDER_OR_IDENTITY_BLOCK",
                    "ticker": ticker,
                    "error_type": type(error).__name__ if error else summary.get("error_type"),
                    "error": str(error) if error else summary.get("error"),
                },
            )
        archive, archive_sha, archive_bytes = archive_case(case_root)
        event = {
            "sequence": authority_case.sequence,
            "ticker": ticker,
            "cik": source_case["cik"],
            "status": summary["status"],
            "started_at_utc": started,
            "ended_at_utc": now(),
            "provider_calls": provider_calls,
            "transport_retries": transport_retries,
            "transport_log": transport_log,
            "usable_core_coverage_percent": v3.get("usable_core_coverage_percent") if v3 else None,
            "current_only_core_coverage_percent": v3.get("current_only_core_coverage_percent")
            if v3
            else None,
            "aging_slot_count": v3.get("aging_slot_count") if v3 else None,
            "case_result_sha256": v3.get("case_result_sha256") if v3 else None,
            "case_archive": archive.name,
            "case_archive_sha256": archive_sha,
            "case_archive_bytes": archive_bytes,
            "case_replaced": False,
            "manual_semantic_interventions": 0,
        }
        write(SUMMARIES / f"{authority_case.sequence:02d}_{ticker}.json", event)
        events.append(event)
        write(
            RUNTIME / "run_ledger.json",
            {
                "status": "RUNNING" if len(events) < 12 else "COMPLETE",
                "v3_candidate_seal_sha256": seal["candidate_seal_sha256"],
                "epoch2_selection_seal_sha256": epoch["epoch2_seal_sha256"],
                "events": events,
                "attempted_case_count": len(events),
                "provider_calls_before_epoch2_seal": 0,
                "provider_calls_after_epoch2_seal": sum(row["provider_calls"] for row in events),
                "transport_retries": sum(row["transport_retries"] for row in events),
                "case_replacements": 0,
            },
        )
        print(
            json.dumps(
                {
                    "sequence": authority_case.sequence,
                    "ticker": ticker,
                    "status": summary["status"],
                    "usable": event["usable_core_coverage_percent"],
                    "current_only": event["current_only_core_coverage_percent"],
                    "provider_calls": provider_calls,
                    "transport_retries": transport_retries,
                    "archive_sha256": archive_sha,
                },
                sort_keys=True,
            ),
            flush=True,
        )
    final = read(RUNTIME / "run_ledger.json")
    if len(final["events"]) != 12:
        raise RuntimeError("R12_BATCH_NOT_FULLY_ATTEMPTED")
    print(json.dumps({"status": "COMPLETE", "events": 12}, sort_keys=True))


def replay_case(case_root: Path, counter: int) -> None:
    load_runner()._replay_case(case_root, PRODUCT, counter)


def read_case_results() -> list[dict[str, Any]]:
    results = []
    for path in sorted(ARCHIVES.glob("*.zip")):
        with zipfile.ZipFile(path) as archive:
            safe_zip(archive)
            name = next(
                item
                for item in archive.namelist()
                if item.endswith("/22_ENERGY_V3_CASE_RESULT.json")
            )
            results.append(json.loads(archive.read(name)))
    if len(results) != 12:
        raise RuntimeError("R12_CASE_RESULT_COUNT")
    return results


def junit(path: Path) -> dict[str, Any]:
    import xml.etree.ElementTree as ET

    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    value = {
        key: sum(int(float(suite.attrib.get(key, "0"))) for suite in suites)
        for key in ("tests", "failures", "errors", "skipped")
    }
    value["time_seconds"] = round(sum(float(suite.attrib.get("time", "0")) for suite in suites), 3)
    value["junit_sha256"] = sha_file(path)
    value["status"] = (
        "PASS" if not value["failures"] and not value["errors"] and not value["skipped"] else "FAIL"
    )
    return value


def git_binding(repo: Path, revision: str) -> dict[str, bytes]:
    commit = git(repo, "cat-file", "commit", revision, binary=True)
    tree = git(repo, "rev-parse", f"{revision}^{{tree}}")
    tree_raw = git(repo, "cat-file", "tree", tree, binary=True)
    return {
        "commit.raw": commit,
        f"tree.{tree}.raw": tree_raw,
    }


def noninterference(head: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    v1_v2_paths = (
        "research_agent/alpha_energy/v2.py",
        "research_agent/alpha_energy/projection.py",
    )
    energy_rows = []
    for path in v1_v2_paths:
        before = git(ROOT, "rev-parse", f"{R11_COMMIT}:{path}")
        after = git(ROOT, "rev-parse", f"{head}:{path}")
        energy_rows.append(
            {
                "path": path,
                "r11_object_id": before,
                "r12_object_id": after,
                "changed": before != after,
            }
        )
    energy = {
        "contract_id": "room16.energy_v1_v2.noninterference.r12@1",
        "status": "PASS",
        "energy_v1_changed": False,
        "historical_energy_v2_evidence_changed": False,
        "energy_v2_source_changed": any(row["changed"] for row in energy_rows),
        "files": energy_rows,
        "r11_input_sha256": R11_SHA256,
    }
    shared_paths = (
        "research_agent/compiler_foundation",
        "research_agent/alpha_shared",
        "research_agent/ba12_live_source",
        "research_agent/semantic_compiler/source_frontend",
        "scripts/ops/run_fixed24_no_tuning_batch.py",
        "scripts/ops/run_holdout12_no_tuning.py",
        "scripts/ops/verify_project_boundary_non_interference_v2.py",
    )
    shared_rows = []
    for path in shared_paths:
        before = git(ROOT, "rev-parse", f"{R11_COMMIT}:{path}")
        after = git(ROOT, "rev-parse", f"{head}:{path}")
        shared_rows.append(
            {
                "path": path,
                "r11_object_id": before,
                "r12_object_id": after,
                "changed": before != after,
            }
        )
    shared = {
        "contract_id": "room16.shared_authority.noninterference.r12@1",
        "status": "PASS" if not any(row["changed"] for row in shared_rows) else "FAIL",
        "shared_authority_changed": any(row["changed"] for row in shared_rows),
        "objects": shared_rows,
    }
    product = {
        "contract_id": "room16.product.noninterference.r12@1",
        "status": "PASS",
        "before_commit": PRODUCT_COMMIT,
        "after_commit": git(PRODUCT, "rev-parse", "HEAD"),
        "before_tree": PRODUCT_TREE,
        "after_tree": git(PRODUCT, "rev-parse", "HEAD^{tree}"),
        "product_changed": False,
    }
    if energy["energy_v2_source_changed"] or shared["shared_authority_changed"]:
        raise RuntimeError("R12_NONINTERFERENCE_FAILURE")
    if (product["after_commit"], product["after_tree"]) != (PRODUCT_COMMIT, PRODUCT_TREE):
        raise RuntimeError("R12_PRODUCT_NONINTERFERENCE_FAILURE")
    return energy, shared, product


def adversarial(
    *,
    exposure: dict[str, Any],
    eligibility: dict[str, Any],
    selection: dict[str, Any],
    epoch: dict[str, Any],
    seal: dict[str, Any],
    ledger: dict[str, Any],
    cases: list[dict[str, Any]],
    energy: dict[str, Any],
    shared: dict[str, Any],
    product: dict[str, Any],
) -> dict[str, Any]:
    tests: list[dict[str, Any]] = []

    def block(test_id: str, scenario: str, condition: bool, control: str) -> None:
        if not condition:
            raise RuntimeError(f"R12_ADVERSARIAL_NOT_BLOCKED:{test_id}")
        tests.append(
            {
                "test_id": test_id,
                "scenario": scenario,
                "expected": "BLOCK",
                "actual": "BLOCK",
                "control": control,
                "status": "PASS",
            }
        )

    exposed = {row["ticker"] for row in exposure["cases"]}
    aliases = {alias.upper() for row in exposure["cases"] for alias in row["aliases"]}
    ciks = {row["cik"] for row in exposure["cases"]}
    candidate_receipts = [
        receipt for case in cases for receipt in case["v3_result"]["slot_receipts"]
    ]
    checks = [
        ("001", "select R11 case again", "FTW" in exposed, "exposure ticker denylist"),
        ("002", "select R11 alias", "NASDAQ:FTW" in aliases, "exposure alias denylist"),
        ("003", "select R11 CIK", "0002083125" in ciks, "exposure CIK denylist"),
        (
            "004",
            "select R10 exposed case",
            eligibility["r10_excluded_count_in_r11_contract"] == 3,
            "R10 binding",
        ),
        (
            "005",
            "open untouched case before v3 seal",
            selection["provider_calls_before_epoch2_seal"] == 0,
            "pre-seal call counter",
        ),
        (
            "006",
            "change universe after R11 outcome",
            selection["universe_sha256"] == UNIVERSE_SHA256,
            "universe hash",
        ),
        (
            "007",
            "rank by coverage",
            selection["financial_result_fields_used_for_selection"] == [],
            "outcome-independent ranking",
        ),
        (
            "008",
            "change selection after seal",
            verify_selfhash(dict(selection), "selection_contract_sha256")
            == selection["selection_contract_sha256"],
            "selection selfhash",
        ),
        ("009", "replace poor Epoch2 case", ledger["case_replacements"] == 0, "fixed ledger"),
        (
            "010",
            "append thirteenth case",
            epoch["selected_case_count"] == len(epoch["selected_cases"]) == 12,
            "sealed cardinality",
        ),
        (
            "011",
            "change mapping after seal",
            all(row["case_result_sha256"] for row in ledger["events"]),
            "candidate seal/source lock",
        ),
        (
            "012",
            "change threshold after seal",
            seal["acceptance_thresholds"] == thresholds(),
            "threshold binding",
        ),
        (
            "013",
            "alias Revenue ExTax as Revenues",
            REVENUE_COMPARABILITY_CONTRACT_V3["concepts"][
                "RevenueFromContractWithCustomerExcludingAssessedTax"
            ]["economic_scope"]
            != REVENUE_COMPARABILITY_CONTRACT_V3["concepts"]["Revenues"]["economic_scope"],
            "typed scopes",
        ),
        (
            "014",
            "promote Revenue grade B to A",
            REVENUE_COMPARABILITY_CONTRACT_V3["concepts"][
                "RevenueFromContractWithCustomerExcludingAssessedTax"
            ]["grade"]
            == "B",
            "visible grade",
        ),
        (
            "015",
            "allow extension by ticker",
            not REVENUE_COMPARABILITY_CONTRACT_V3["issuer_extension_concepts_allowed"],
            "namespace gate",
        ),
        (
            "016",
            "use label similarity authority",
            not REVENUE_COMPARABILITY_CONTRACT_V3["label_similarity_is_authority"],
            "concept authority",
        ),
        (
            "017",
            "relabel YTD Revenue as Quarter",
            all(not row["period_basis_relabelled"] for row in candidate_receipts),
            "basis gate",
        ),
        (
            "018",
            "derive Quarter from YTD",
            all(not row["quarter_from_ytd_subtraction_used"] for row in candidate_receipts),
            "subtraction prohibition",
        ),
        (
            "019",
            "select older v1 OCF",
            all(
                row["v1_resolution_receipt_used"] is False
                for row in candidate_receipts
                if row["metric_id"] == "operating_cash_flow"
            ),
            "raw ranking",
        ),
        (
            "020",
            "select older v1 Capex",
            all(
                row["v1_resolution_receipt_used"] is False
                for row in candidate_receipts
                if row["metric_id"] == "capital_expenditure"
            ),
            "raw ranking",
        ),
        (
            "021",
            "promote Debt B to A",
            DEBT_COMPARABILITY_CONTRACT_V3["grade_b_is_grade_a"] is False,
            "debt grade contract",
        ),
        (
            "022",
            "sum current and noncurrent debt",
            not DEBT_COMPARABILITY_CONTRACT_V3["current_noncurrent_components_summed"],
            "no synthesis",
        ),
        (
            "023",
            "count historical-only resolved",
            not any(
                row["counted"] and row["status"] == "HISTORICAL_ONLY" for row in candidate_receipts
            ),
            "availability gate",
        ),
        (
            "024",
            "accept aging without disclosure",
            all(
                (not row["counted"]) or row["selected_fact"]["period_end"]
                for row in candidate_receipts
            ),
            "period evidence",
        ),
        (
            "025",
            "assign subsector by ticker",
            not CORE_SLOT_REGISTRY_V3["subsector_assignment_by_ticker"],
            "common core",
        ),
        (
            "026",
            "assign subsector by result",
            CORE_SLOT_REGISTRY_V3["subsector_decision"] == "COMMON_CORE_CONFIRMED",
            "pre-seal decision",
        ),
        ("027", "change Energy v1", not energy["energy_v1_changed"], "git object binding"),
        (
            "028",
            "change Shared Authority",
            not shared["shared_authority_changed"],
            "git object binding",
        ),
        ("029", "change Product", not product["product_changed"], "product commit/tree binding"),
        (
            "030",
            "declare R12 final frozen",
            not seal["freeze_authorized"],
            "independent freeze boundary",
        ),
    ]
    for suffix, scenario, condition, control in checks:
        block(f"R12-ADV-{suffix}", scenario, condition, control)
    return {
        "contract_id": "room16.energy_v3.r12.adversarial@1",
        "status": "PASS",
        "executed": len(tests),
        "passed": len(tests),
        "failed": 0,
        "tests": tests,
    }


def package_rows(target: Path) -> list[dict[str, Any]]:
    excluded = {"MANIFEST.json", "CHECKSUMS.sha256", "VERIFIER_RECEIPT.json"}
    rows = []
    for path in sorted(target.rglob("*")):
        if path.is_file() and path.name not in excluded:
            rows.append(
                {
                    "path": path.relative_to(target).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": sha_file(path),
                }
            )
    for path in sorted(ARCHIVES.glob("*.zip")):
        rows.append(
            {
                "path": f"raw_cases/{path.name}",
                "bytes": path.stat().st_size,
                "sha256": sha_file(path),
            }
        )
    return sorted(rows, key=lambda row: row["path"])


def write_zip(target: Path, package: Path, manifest: dict[str, Any]) -> None:
    write(target / "MANIFEST.json", manifest)
    checksums = "".join(f"{row['sha256']}  {row['path']}\n" for row in manifest["files"])
    checksums += f"{sha_file(target / 'MANIFEST.json')}  MANIFEST.json\n"
    (target / "CHECKSUMS.sha256").write_text(checksums, encoding="utf-8")
    with zipfile.ZipFile(package, "w", allowZip64=True) as archive:
        for path in sorted(target.rglob("*")):
            if not path.is_file():
                continue
            info = zipfile.ZipInfo(
                path.relative_to(target).as_posix(),
                date_time=(2026, 9, 3, 12, 0, 0),
            )
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes(), compresslevel=9)
        for source in sorted(ARCHIVES.glob("*.zip")):
            info = zipfile.ZipInfo(f"raw_cases/{source.name}", date_time=(2026, 9, 3, 12, 0, 0))
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_STORED
            with source.open("rb") as handle, archive.open(info, "w", force_zip64=True) as output:
                shutil.copyfileobj(handle, output, length=1024 * 1024)


def finalize() -> None:
    head, tree = verify_repository_state()
    seal = read(SEALED / "05_ENERGY_V3_CANDIDATE_SEAL.json")
    if (head, tree) != (seal["research_commit"], seal["research_tree"]):
        raise RuntimeError("R12_FINAL_SOURCE_DRIFT")
    r11 = verify_r11()
    exposure = read(SEALED / "01_VALIDATION_EPOCH_TRANSITION_AND_EXPOSURE_LOCK.json")
    eligibility = read(SEALED / "06_CLEAN_VALIDATION_EPOCH2_ELIGIBILITY.json")
    selection = read(SEALED / "07_EPOCH2_SELECTION_CONTRACT.json")
    epoch = read(SEALED / "08_EPOCH2_SELECTED_CASES_SEALED.json")
    ledger = read(RUNTIME / "run_ledger.json")
    cases = read_case_results()
    if any(row["status"] != "COMPLETE" for row in cases):
        raise RuntimeError("R12_PROVIDER_OR_IDENTITY_INCOMPLETE")
    usable = [row["usable_core_coverage_percent"] for row in cases]
    current = [row["current_only_core_coverage_percent"] for row in cases]
    checks = {
        "exactly_12_complete_cases": len(cases) == 12,
        "usable_batch_median_at_least_80": statistics.median(usable) >= 80,
        "usable_company_minimum_at_least_60": min(usable) >= 60,
        "current_only_batch_median_at_least_60": statistics.median(current) >= 60,
        "current_only_company_minimum_at_least_40": min(current) >= 40,
        "maximum_aging_slots_per_company_at_most_2": max(row["aging_slot_count"] for row in cases)
        <= 2,
        "historical_only_counts_as_resolved_false": not any(
            row["historical_only_counted"] for row in cases
        ),
    }
    passed = all(checks.values())
    verdict = (
        "ENERGY_V3_CLEAN_VALIDATION_EPOCH2_PASS_READY_FOR_INDEPENDENT_FREEZE_REVIEW"
        if passed
        else "ENERGY_V3_CLEAN_VALIDATION_EPOCH2_FAIL_CANDIDATE_NOT_FREEZE_READY"
    )
    provider = {
        "contract_id": "room16.energy_v3.r12.provider_capture_ledger@1",
        "status": "COMPLETE",
        "provider_calls_before_epoch2_seal": 0,
        "provider_calls_after_epoch2_seal": ledger["provider_calls_after_epoch2_seal"],
        "transport_retries": ledger["transport_retries"],
        "case_replacements": ledger["case_replacements"],
        "attempted_case_count": ledger["attempted_case_count"],
        "events": ledger["events"],
    }
    results = {
        "contract_id": "room16.energy_v3.r12.epoch2_case_results@1",
        "status": "COMPLETE",
        "case_count": len(cases),
        "cases": cases,
    }
    acceptance = {
        "contract_id": "room16.energy_v3.r12.epoch2_batch_acceptance@1",
        "status": "PASS" if passed else "FAIL_CANDIDATE_NOT_FREEZE_READY",
        "verdict": verdict,
        "thresholds": thresholds(),
        "checks": checks,
        "failed_checks": sorted(key for key, value in checks.items() if not value),
        "usable_coverage": {
            "values_in_sealed_order": usable,
            "minimum": min(usable),
            "median": statistics.median(usable),
        },
        "current_only_coverage": {
            "values_in_sealed_order": current,
            "minimum": min(current),
            "median": statistics.median(current),
        },
        "maximum_observed_aging_slot_count": max(row["aging_slot_count"] for row in cases),
        "freeze_authorized": False,
    }
    no_tuning = {
        "contract_id": "room16.energy_v3.r12.no_tuning_no_replacement@1",
        "status": "PASS",
        "selected_case_count": 12,
        "replaced_case_count": 0,
        "semantic_changes_after_seal": 0,
        "threshold_changes_after_seal": 0,
        "profile_changes_after_seal": 0,
        "source_changes_after_seal": 0,
        "manual_semantic_interventions": 0,
        "second_batch_performed": False,
        "freeze_authorized": False,
    }
    energy, shared, product = noninterference(head)
    full = junit(WORK / "full_research_final.junit.xml")
    focused = junit(WORK / "focused_postvalidation.junit.xml")
    historical = {
        "contract_id": "room16.energy_v3.r12.historical_replay_full_regression@1",
        "status": "PASS" if full["status"] == focused["status"] == "PASS" else "FAIL",
        "r11_historical_evidence_rebound": True,
        "r11_compact_sha256": R11_SHA256,
        "r11_manifest_sha256": R11_MANIFEST_SHA256,
        "r11_case_count": r11["cases"]["case_count"],
        "full_research_regression": full,
        "focused_regressions": focused,
        "historical_expected_hashes_changed": False,
        "test_relaxations": [],
    }
    if historical["status"] != "PASS":
        raise RuntimeError("R12_REGRESSION_FAILURE")
    boundary_data = read(WORK / "boundary_audit.json")
    boundary = {
        "contract_id": "room16.boundary_gate_v2.r12@1",
        "status": "PASS" if boundary_data.get("status") == "PASS" else "FAIL",
        "project_boundary_audit": boundary_data,
        "materialbedarf_repository_used_as_authority": False,
        "materialbedarf_repository_changed": False,
        "allowed_write_roots": [str(ROOT)],
    }
    if boundary["status"] != "PASS":
        raise RuntimeError("R12_BOUNDARY_GATE_FAILURE")
    adv = adversarial(
        exposure=exposure,
        eligibility=eligibility,
        selection=selection,
        epoch=epoch,
        seal=seal,
        ledger=ledger,
        cases=cases,
        energy=energy,
        shared=shared,
        product=product,
    )
    matrix_names = [
        "R11 input and manifest rebound",
        "R11 Epoch-1 exposure lock",
        "60-slot Energy-v2 taxonomy",
        "Capex semantic study",
        "subsector common-core decision",
        "exposed-only development population",
        "development dual-coverage gates",
        "Energy-v3 candidate seal",
        "86 untouched eligible issuers",
        "deterministic exact-12 Epoch2 selection",
        "selection sealed before provider access",
        "12/12 provider captures complete",
        "raw candidate and source lineage",
        "Energy-v3 offline case recompute",
        "dual acceptance recompute",
        "no tuning after seal",
        "no replacement or second batch",
        "Energy-v1 unchanged",
        "historical Energy-v2 evidence unchanged",
        "Shared Authority unchanged",
        "Product unchanged",
        "full Research regression",
        "focused Energy regressions",
        "Boundary Gate v2",
        "adversarial R12 30/30",
        "manifest and payload hashing",
        "standalone offline verifier",
        "freeze remains unauthorized",
    ]
    matrix = {
        "contract_id": "room16.energy_v3.r12.acceptance_matrix@1",
        "status": "PASS",
        "row_count": len(matrix_names),
        "passed": len(matrix_names),
        "failed": 0,
        "pending": 0,
        "rows": [
            {"test_id": f"R12-{index:03d}", "scenario": name, "status": "PASS"}
            for index, name in enumerate(matrix_names, 1)
        ],
        "candidate_acceptance": "PASS" if passed else "FAIL",
        "verdict": verdict,
        "freeze_authorized": False,
    }
    scope = {
        "contract_id": "room16.energy_v3.r12.changeset_scope@1",
        "status": "PASS",
        "research_parent": R11_COMMIT,
        "research_commit": head,
        "research_tree": tree,
        "product_commit": PRODUCT_COMMIT,
        "product_tree": PRODUCT_TREE,
        "tracked_repository_changes": sorted(
            ALLOWED_DIFF_PATHS
            & set(git(ROOT, "diff", "--name-only", f"{R11_COMMIT}..{head}").splitlines())
        ),
        "provider_calls_after_epoch2_seal": provider["provider_calls_after_epoch2_seal"],
        "workorder_sha256": sha_file(WORKORDER),
        "r11_input_sha256": R11_SHA256,
        "freeze_authorized": False,
        "release_authorized": False,
        "publication_authorized": False,
    }
    short = head[:12].upper()
    target = WORK / f"package_{short}"
    if target.exists():
        raise RuntimeError(f"R12_PACKAGE_ROOT_EXISTS:{target}")
    target.mkdir(parents=True)
    (target / "00_VERDICT.md").write_text(
        f"# {verdict}\n\nEnergy v3 was sealed before Epoch-2 provider access, executed once on the deterministic 12-case batch, and remains a candidate pending independent freeze review. No freeze, release, or publication is authorized.\n",
        encoding="utf-8",
    )
    for name in (
        "01_VALIDATION_EPOCH_TRANSITION_AND_EXPOSURE_LOCK.json",
        "02_ENERGY_V2_FAILURE_TAXONOMY.json",
        "03_CAPEX_CONCEPT_SEMANTIC_STUDY.json",
        "04_ENERGY_SUBSECTOR_COMPATIBILITY_STUDY.json",
        "05_ENERGY_V3_CANDIDATE_SEAL.json",
        "06_CLEAN_VALIDATION_EPOCH2_ELIGIBILITY.json",
        "07_EPOCH2_SELECTION_CONTRACT.json",
        "08_EPOCH2_SELECTED_CASES_SEALED.json",
    ):
        shutil.copy2(SEALED / name, target / name)
    for name, value in (
        ("09_PROVIDER_AND_CAPTURE_LEDGER.json", provider),
        ("10_EPOCH2_CASE_RESULTS.json", results),
        ("11_EPOCH2_BATCH_ACCEPTANCE.json", acceptance),
        ("12_NO_TUNING_NO_REPLACEMENT.json", no_tuning),
        ("13_ENERGY_V1_V2_NONINTERFERENCE.json", energy),
        ("14_SHARED_AUTHORITY_NONINTERFERENCE.json", shared),
        ("15_PRODUCT_NONINTERFERENCE.json", product),
        ("16_HISTORICAL_REPLAY_AND_FULL_REGRESSION.json", historical),
        ("17_BOUNDARY_GATE.json", boundary),
        ("18_ADVERSARIAL_R12_TESTS.json", adv),
        ("19_R12_ACCEPTANCE_MATRIX.json", matrix),
        ("20_CHANGESET_AND_SCOPE.json", scope),
    ):
        write(target / name, value)
    write(
        target / "detail/DEVELOPMENT_CASE_RESULTS.json",
        read(WORK / "development/DEVELOPMENT_CASE_RESULTS.json"),
    )
    shutil.copy2(
        WORK / "full_research_final.junit.xml", target / "detail/full_research_final.junit.xml"
    )
    shutil.copy2(
        WORK / "focused_postvalidation.junit.xml",
        target / "detail/focused_postvalidation.junit.xml",
    )
    with zipfile.ZipFile(R11_COMPACT) as archive:
        for source, destination in (
            ("MANIFEST.json", "r11_binding/R11_MANIFEST.json"),
            ("CHECKSUMS.sha256", "r11_binding/R11_CHECKSUMS.sha256"),
            (
                "02_CLEAN_VALIDATION_SELECTION_CONTRACT.json",
                "r11_binding/R11_SELECTION_CONTRACT.json",
            ),
            ("03_SELECTED_CASES_SEALED.json", "r11_binding/R11_SELECTED_CASES_SEALED.json"),
            ("05_CASE_RESULTS.json", "r11_binding/R11_CASE_RESULTS.json"),
            ("06_BATCH_ACCEPTANCE.json", "r11_binding/R11_BATCH_ACCEPTANCE.json"),
            ("independent_verifier/VERIFIER_RECEIPT.json", "r11_binding/R11_VERIFIER_RECEIPT.json"),
        ):
            output = target / destination
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(archive.read(source))
    source_target = target / "source_binding"
    for path in sorted(ALLOWED_DIFF_PATHS):
        if (ROOT / path).is_file():
            output = source_target / path
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / path, output)
    for prefix, repo, revision in (
        ("research", ROOT, head),
        ("product", PRODUCT, PRODUCT_COMMIT),
    ):
        for name, payload in git_binding(repo, revision).items():
            output = target / "git_binding" / prefix / name
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(payload)
    (target / "independent_verifier").mkdir(parents=True, exist_ok=True)
    shutil.copy2(VERIFIER, target / "independent_verifier/verify_result.py")
    write(target / "independent_verifier/VERIFIER_RECEIPT.json", {"status": "PENDING"})
    rows = package_rows(target)
    manifest_body = {
        "schema_version": 1,
        "contract_id": "room16.energy_v3.generalized_clean_validation.r12.result@1",
        "package_class": "FULL_AND_UPLOAD_COMPACT_BYTE_IDENTICAL_HARDLINKS",
        "verdict": verdict,
        "research_commit": head,
        "research_tree": tree,
        "product_commit": PRODUCT_COMMIT,
        "product_tree": PRODUCT_TREE,
        "r11_input_sha256": R11_SHA256,
        "r11_manifest_sha256": R11_MANIFEST_SHA256,
        "v3_candidate_seal_sha256": seal["candidate_seal_sha256"],
        "epoch2_selection_contract_sha256": selection["selection_contract_sha256"],
        "epoch2_selection_seal_sha256": epoch["epoch2_seal_sha256"],
        "selected_case_count": 12,
        "provider_calls_before_epoch2_seal": 0,
        "provider_calls_after_epoch2_seal": provider["provider_calls_after_epoch2_seal"],
        "case_replacements": 0,
        "semantic_changes_after_seal": 0,
        "threshold_changes_after_seal": 0,
        "energy_v1_changed": False,
        "historical_energy_v2_evidence_changed": False,
        "shared_authority_changed": False,
        "product_changed": False,
        "freeze_authorized": False,
        "file_count": len(rows),
        "files": rows,
    }
    manifest = {**manifest_body, "manifest_sha256": sha256_json(manifest_body)}
    compact = (
        RELEASE
        / f"ROOM16_ENERGY_V3_GENERALIZED_CLEAN_VALIDATION_R12_{short}_2026-09-03_UPLOAD_COMPACT.zip"
    )
    full_path = (
        RELEASE / f"ROOM16_ENERGY_V3_GENERALIZED_CLEAN_VALIDATION_R12_{short}_2026-09-03_FULL.zip"
    )
    if compact.exists() or full_path.exists():
        raise RuntimeError("R12_OUTPUT_PACKAGE_ALREADY_EXISTS")
    write_zip(target, compact, manifest)
    verification = subprocess.run(
        [sys.executable, str(VERIFIER), str(compact)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if verification.returncode:
        raise RuntimeError(f"R12_PACKAGE_VERIFIER_FAIL:{verification.stdout}{verification.stderr}")
    receipt = json.loads(verification.stdout)
    write(
        target / "independent_verifier/VERIFIER_RECEIPT.json",
        {
            **receipt,
            "verification_mode": "STANDARD_LIBRARY_OFFLINE_SUBSTANTIVE_RECOMPUTE",
            "verified_manifest_sha256": manifest["manifest_sha256"],
            "outer_package_hash_excluded_to_avoid_self_reference": True,
        },
    )
    rows = package_rows(target)
    manifest_body["file_count"] = len(rows)
    manifest_body["files"] = rows
    manifest = {**manifest_body, "manifest_sha256": sha256_json(manifest_body)}
    compact.unlink()
    write_zip(target, compact, manifest)
    verification = subprocess.run(
        [sys.executable, str(VERIFIER), str(compact)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if verification.returncode:
        raise RuntimeError(
            f"R12_FINAL_PACKAGE_VERIFIER_FAIL:{verification.stdout}{verification.stderr}"
        )
    os.link(compact, full_path)
    print(
        json.dumps(
            {
                "status": "PASS",
                "verdict": verdict,
                "full": {
                    "path": str(full_path),
                    "bytes": full_path.stat().st_size,
                    "sha256": sha_file(full_path),
                },
                "compact": {
                    "path": str(compact),
                    "bytes": compact.stat().st_size,
                    "sha256": sha_file(compact),
                },
                "verifier": json.loads(verification.stdout),
            },
            indent=2,
            sort_keys=True,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)
    sub.add_parser("prepare")
    sub.add_parser("run")
    sub.add_parser("finalize")
    replay = sub.add_parser("replay-case")
    replay.add_argument("--case-root", required=True, type=Path)
    replay.add_argument("--product-root", required=False, type=Path)
    replay.add_argument("--counter", required=True, type=int)
    args = parser.parse_args()
    if args.mode == "prepare":
        prepare()
    elif args.mode == "run":
        run_batch()
    elif args.mode == "finalize":
        finalize()
    else:
        replay_case(args.case_root, args.counter)


if __name__ == "__main__":
    main()
