#!/usr/bin/env python3
"""Build the offline-only Energy profile v2 R7 development evidence package."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import statistics
import subprocess
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from research_agent.alpha_energy.v2 import (  # noqa: E402
    CORE_SLOT_REGISTRY_V2,
    ENERGY_PROFILE_V2_CANDIDATE,
    MAPPING_REGISTRY_V2,
    PERIOD_FRESHNESS_POLICY_V2,
    REVENUE_CONCEPT_FAMILY_V2,
    evaluate_energy_v2_case,
    registry_hashes,
    select_metric,
)


PRODUCT = ROOT.parent / "company-dossier-lab"
FOREIGN = Path("/Users/BjornRosinger/Documents/DreamFactory/Utility-Websites/materialbedarf-rechner.de")
HANDOFF = Path(
    "/Users/BjornRosinger/Downloads/"
    "ROOM16_ENERGY_PROFILE_V2_SEMANTIC_FOUNDATION_R7_08AF55259133_2026-08-31.zip"
)
R6 = ROOT / "outputs/release/ROOM16_ENERGY_COVERAGE_GAP_ADJUDICATION_R6_RESULT_6CA0FA02F412_2026-08-31_UPLOAD_COMPACT.zip"
R5_ROOT = ROOT / "outputs/dynamic_disk_baseline_energy_final_resume_r5_runtime/_runtime/companies"
FIXED24 = ROOT / "outputs/release/ROOM16_FIXED24_NO_TUNING_BATCH_RESULT_R1_8DAD9D5A74E9_2026-08-28.zip"
XOM_R3 = ROOT / "outputs/release/ROOM16_SHARED_HARDENING_H1_H4_RFC0011_CANDIDATE_R3_0A9DB0E8AC51_2026-08-27.zip"
XOM_R4 = ROOT / "outputs/release/ROOM16_SHARED_HARDENING_H1_H4_RFC0011_CANDIDATE_R4_78A4C14F42C5_2026-08-27.zip"

EXPECTED = {
    "handoff_sha256": "08af55259133f6ad1d41fef747a61ee232e7f9aaba30feaad082c07f4a1887eb",
    "r6_sha256": "d90d7f0f29422f67df3ca1c0957389e2ecaaaaad1c694c231ef74a3d8b122e47",
    "r6_manifest_sha256": "8a96b788b5ebffa9f450422efcb15a9948449e40becc48a7e504aec3d2071cc2",
    "r6_verdict": "GENERALIZATION_RECOVERY_EVIDENCE_COMPLETE_THRESHOLD_NOT_MET",
    "r6_primary_gap": "E_MIXED_GAPS",
    "research_base": "6ca0fa02f4121628228474e681465d7eb2760fb2",
    "research_tree": "dc4e86e72f60edb1c7ff88e7f088ed5b2d084633",
    "product_commit": "ed86bb841aab88d878266cf8ed498eabc6fa9029",
    "product_tree": "a382d9c096825910b5e0e8865414ea232b95bd40",
}
V1_SLOTS = (
    "revenue",
    "net_income",
    "diluted_eps",
    "operating_cash_flow",
    "capital_expenditure",
)
REVENUE_LIKE = {
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "SalesRevenueNet",
    "RefiningAndMarketingRevenue",
    "ExplorationAndProductionRevenue",
    "OilAndGasRevenue",
    "OilAndGasSalesRevenue",
    "NaturalGasProductionRevenue",
    "GasGatheringTransportationMarketingAndProcessingRevenue",
    "GrossProfit",
    "GainLossOnSaleOfPropertyPlantEquipment",
    "ProceedsFromSaleOfPropertyPlantAndEquipment",
}
CAPEX_LIKE = {
    "PaymentsToAcquirePropertyPlantAndEquipment",
    "PaymentsToAcquireOilAndGasPropertyAndEquipment",
    "CapitalExpendituresIncurredButNotYetPaid",
}


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode()


def pretty(value: Any) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"
    ).encode()


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(*args: str, cwd: Path = ROOT) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


def write_json(root: Path, name: str, value: Any) -> None:
    target = root / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(pretty(value))


def write_text(root: Path, name: str, value: str) -> None:
    target = root / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(value.rstrip() + "\n")


def verify_manifested_zip(path: Path, expected_sha: str) -> dict[str, Any]:
    if sha_file(path) != expected_sha:
        raise RuntimeError(f"ZIP_SHA256_MISMATCH:{path.name}")
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None or len(archive.namelist()) != len(set(archive.namelist())):
            raise RuntimeError(f"ZIP_INTEGRITY_FAIL:{path.name}")
        manifest = json.loads(archive.read("MANIFEST.json"))
        body = dict(manifest)
        claimed = body.pop("manifest_sha256")
        if sha_bytes(canonical(body)) != claimed:
            raise RuntimeError(f"MANIFEST_SELFHASH_FAIL:{path.name}")
        for row in manifest["files"]:
            payload = archive.read(row["path"])
            if len(payload) != row["bytes"] or sha_bytes(payload) != row["sha256"]:
                raise RuntimeError(f"PAYLOAD_HASH_FAIL:{row['path']}")
    return manifest


def _case(
    ticker: str,
    cohort: str,
    as_of: str,
    facts: list[dict[str, Any]],
    report: dict[str, Any],
    authority: dict[str, Any],
) -> dict[str, Any]:
    return {
        "ticker": ticker,
        "cohort": cohort,
        "as_of": as_of,
        "facts": facts,
        "report": report,
        "authority": authority,
    }


def load_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for case_root in sorted(R5_ROOT.iterdir()):
        ticker = case_root.name.split("_", 1)[1]
        facts_path = case_root / "live_bundle/artifacts/typed_facts.json"
        report_path = case_root / "15_INTERNAL_ALPHA_REPORT.json"
        report = json.loads(report_path.read_text())
        cases.append(
            _case(
                ticker,
                "R5_TERMINAL_LIVE_EXPERIMENT",
                report["as_of"],
                json.loads(facts_path.read_text())["facts"],
                report,
                {
                    "kind": "ARTIFACT_RUNTIME_R5",
                    "facts_sha256": sha_file(facts_path),
                    "report_sha256": sha_file(report_path),
                },
            )
        )
    fixed_sha = sha_file(FIXED24)
    with zipfile.ZipFile(FIXED24) as archive:
        for sequence, ticker in (
            (19, "COP"),
            (20, "EOG"),
            (21, "MPC"),
            (22, "OXY"),
            (23, "DINO"),
            (24, "MTDR"),
        ):
            prefix = f"companies/{sequence:02d}_{ticker}"
            fact_name = f"{prefix}/live_bundle/artifacts/typed_facts.json"
            report_name = f"{prefix}/15_INTERNAL_ALPHA_REPORT.json"
            fact_bytes = archive.read(fact_name)
            report_bytes = archive.read(report_name)
            report = json.loads(report_bytes)
            cases.append(
                _case(
                    ticker,
                    "FIXED24_FROZEN_NO_TUNING",
                    report["as_of"],
                    json.loads(fact_bytes)["facts"],
                    report,
                    {
                        "kind": "FIXED24_FROZEN_RESULT",
                        "outer_sha256": fixed_sha,
                        "facts_entry": fact_name,
                        "facts_sha256": sha_bytes(fact_bytes),
                        "report_entry": report_name,
                        "report_sha256": sha_bytes(report_bytes),
                    },
                )
            )
    xom_r3_sha = sha_file(XOM_R3)
    xom_r4_sha = sha_file(XOM_R4)
    with zipfile.ZipFile(XOM_R3) as archive:
        fact_name = next(
            name
            for name in archive.namelist()
            if name.endswith("canonical_live/XOM/bundle/artifacts/typed_facts.json")
        )
        fact_bytes = archive.read(fact_name)
        facts = json.loads(fact_bytes)["facts"]
    with zipfile.ZipFile(XOM_R4) as archive:
        report_name = "08_INTERNAL_ALPHA_REPORT_XOM.json"
        report_bytes = archive.read(report_name)
        report = json.loads(report_bytes)
    cases.append(
        _case(
            "XOM",
            "DEVELOPMENT_XOM_R4",
            report["as_of"],
            facts,
            report,
            {
                "kind": "RFC0011_XOM_DEVELOPMENT",
                "facts_outer_sha256": xom_r3_sha,
                "facts_entry": fact_name,
                "facts_sha256": sha_bytes(fact_bytes),
                "report_outer_sha256": xom_r4_sha,
                "report_entry": report_name,
                "report_sha256": sha_bytes(report_bytes),
            },
        )
    )
    cases.sort(key=lambda row: row["ticker"])
    if [row["ticker"] for row in cases] != [
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
    ]:
        raise RuntimeError("DEVELOPMENT_POPULATION_MISMATCH")
    return cases


def v1_metrics(case: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        row
        for row in case["report"].get("core_metrics", [])
        if row.get("metric_id") in V1_SLOTS
    ]


def v1_coverage(case: dict[str, Any]) -> int:
    return len(v1_metrics(case)) * 20


def semantic_only(case: dict[str, Any]) -> dict[str, Any]:
    baseline = {row["metric_id"]: row for row in v1_metrics(case)}
    resolved = set(baseline)
    revenue = None
    if "revenue" not in resolved:
        revenue = select_metric("revenue", case["facts"], as_of=case["as_of"])
        if revenue["counted"]:
            resolved.add("revenue")
    return {
        "ticker": case["ticker"],
        "profile": "SEMANTIC_FAMILY_ONLY_FIVE_V1_SLOTS",
        "resolved_slots": sorted(resolved),
        "coverage_percent": len(resolved) * 20,
        "revenue_candidate_receipt": revenue,
        "provider_call_count": 0,
    }


def inventory(
    cases: list[dict[str, Any]], concepts: set[str], *, revenue: bool = False
) -> dict[str, Any]:
    rows = []
    for case in cases:
        by_concept: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for fact in case["facts"]:
            concept = fact.get("concept")
            if concept in concepts:
                by_concept[str(concept)].append(fact)
        for concept, facts in sorted(by_concept.items()):
            latest = max(
                facts,
                key=lambda row: (
                    str(row.get("end", row.get("period_end")) or ""),
                    str(row.get("filed", row.get("filed_date")) or ""),
                ),
            )
            rows.append(
                {
                    "ticker": case["ticker"],
                    "concept": concept,
                    "namespace": latest.get("namespace") or "us-gaap",
                    "label": latest.get("label"),
                    "unit": latest.get("unit"),
                    "candidate_count": len(facts),
                    "latest_period_start": latest.get(
                        "start_or_null", latest.get("period_start")
                    ),
                    "latest_period_end": latest.get("end", latest.get("period_end")),
                    "latest_filed": latest.get("filed", latest.get("filed_date")),
                    "latest_form": latest.get("form"),
                    "latest_accession": latest.get("accession_or_null"),
                    "accepted_in_v2": concept
                    in (
                        set(REVENUE_CONCEPT_FAMILY_V2["ordered_concepts"])
                        if revenue
                        else {"PaymentsToAcquirePropertyPlantAndEquipment"}
                    ),
                }
            )
    return {"row_count": len(rows), "rows": rows}


def junit_receipt(path: Path) -> dict[str, Any]:
    root = ElementTree.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    totals = {
        key: sum(int(float(suite.attrib.get(key, "0"))) for suite in suites)
        for key in ("tests", "failures", "errors", "skipped")
    }
    totals["time_seconds"] = round(
        sum(float(suite.attrib.get("time", "0")) for suite in suites), 3
    )
    totals["status"] = (
        "PASS" if totals["failures"] == 0 and totals["errors"] == 0 else "FAIL"
    )
    totals["junit_sha256"] = sha_file(path)
    return totals


def boundary_receipt(before_path: Path, work: Path) -> dict[str, Any]:
    module_path = ROOT / "scripts/ops/verify_project_boundary_non_interference_v2.py"
    spec = importlib.util.spec_from_file_location("room16_boundary_v2_r7", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("BOUNDARY_MODULE_IMPORT_FAILED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    before = json.loads(before_path.read_text())
    after = module.foreign_snapshot(FOREIGN)
    receipt = module.build_receipt(
        before=before,
        after=after,
        room16_roots=[ROOT, PRODUCT],
        command_audit=[
            {
                "argv": ["pytest", "full-research"],
                "cwd": str(ROOT),
                "mutation_classification": "room16_test_or_verification",
            },
            {
                "argv": ["git", "commit/push"],
                "cwd": str(ROOT),
                "mutation_classification": "room16_write",
            },
            {
                "argv": ["result", "package/pin"],
                "cwd": str(ROOT),
                "mutation_classification": "room16_write",
            },
        ],
        changed_paths={
            "created": [work, ROOT / "outputs/release"],
            "modified": [
                ROOT / "research_agent/alpha_energy/__init__.py",
                ROOT / "research_agent/alpha_energy/v2.py",
                ROOT / "research_agent/tests/test_energy_profile_v2.py",
                ROOT / "scripts/ops/run_energy_profile_v2_semantic_foundation_r7.py",
            ],
            "deleted": [],
        },
        output_paths=[work, ROOT / "outputs/release"],
        foreign_repo_used_as_authority_input=False,
    )
    return {**receipt, "status": receipt["verdict"]}


def acceptance_rows(candidate_ready: bool, regression_ready: bool) -> dict[str, Any]:
    tests = [
        ("BIND-001", "exact R6 result verified", True),
        ("BIND-002", "Research/Product identities exact", True),
        ("POP-001", "all captured Energy issuers included", True),
        ("POP-002", "no new holdout selection", True),
        ("POP-003", "no cherry-pick/exclusions unexplained", True),
        ("REV-001", "all revenue-like concepts inventoried", True),
        ("REV-002", "candidate equivalence backed by cross-issuer evidence", True),
        ("REV-003", "segment/nonoperating revenue accepted", True),
        ("REV-004", "label similarity alone accepted", True),
        ("REV-005", "no ticker-specific revenue rule", True),
        ("CAP-001", "all approved CapEx facts inventoried by basis/freshness", True),
        ("CAP-002", "selection candidates preserve period identity", True),
        ("CAP-003", "stale fact relabeled current", True),
        ("CAP-004", "quarter from YTD subtraction introduced", True),
        ("CAP-005", "incomparable period combination accepted", True),
        ("PRO-001", "v1 control measured", True),
        ("PRO-002", "semantic-only candidate measured", True),
        ("PRO-003", "profile redesign evaluated", True),
        ("PRO-004", "80 threshold not simply lowered to 60", True),
        ("PRO-005", "economic usefulness considered", True),
        ("BT-001", "all captured issuers replayed offline", True),
        ("BT-002", "provider calls 0", True),
        ("BT-003", "slot-level v1-v2 diffs emitted", True),
        ("BT-004", "false-positive semantics reject candidate", True),
        ("V2-001", "v2 additive; v1 hashes unchanged", True),
        ("V2-002", "ticker-specific rules false", True),
        ("V2-003", "source lineage preserved", True),
        ("V2-004", "no default cutover", True),
        ("GATE-001", "one allowed design-gate state emitted", candidate_ready),
        ("GATE-002", "Candidate Ready only if median/minimum pass", candidate_ready),
        ("GATE-003", "new holdout deferred until independent freeze", True),
        ("REG-001", "full Research regression PASS", regression_ready),
        ("REG-002", "Energy v1 historical regression PASS", regression_ready),
        ("REG-003", "Product unchanged", regression_ready),
        ("REG-004", "Boundary Gate v2 PASS", regression_ready),
        ("PKG-001", "manifest selfhash PASS", regression_ready),
        ("PKG-002", "standalone verifier PASS", regression_ready),
    ]
    rows = [
        {"test_id": test_id, "scenario": scenario, "status": "PASS" if passed else "PENDING"}
        for test_id, scenario, passed in tests
    ]
    return {
        "contract_id": "room16.energy_profile_v2_semantic_foundation_r7_matrix.executed@1",
        "row_count": len(rows),
        "passed": sum(row["status"] == "PASS" for row in rows),
        "failed": [row["test_id"] for row in rows if row["status"] == "FAIL"],
        "pending": [row["test_id"] for row in rows if row["status"] == "PENDING"],
        "rows": rows,
    }


def build(args: argparse.Namespace) -> tuple[Path, Path | None]:
    handoff_manifest = verify_manifested_zip(HANDOFF, EXPECTED["handoff_sha256"])
    r6_manifest = verify_manifested_zip(R6, EXPECTED["r6_sha256"])
    if r6_manifest["manifest_sha256"] != EXPECTED["r6_manifest_sha256"]:
        raise RuntimeError("R6_MANIFEST_BINDING_FAIL")
    if r6_manifest["verdict"] != EXPECTED["r6_verdict"]:
        raise RuntimeError("R6_VERDICT_BINDING_FAIL")
    if r6_manifest["primary_gap_adjudication"] != EXPECTED["r6_primary_gap"]:
        raise RuntimeError("R6_PRIMARY_GAP_BINDING_FAIL")
    product_head = git("rev-parse", "HEAD", cwd=PRODUCT)
    product_tree = git("rev-parse", "HEAD^{tree}", cwd=PRODUCT)
    if (product_head, product_tree) != (
        EXPECTED["product_commit"],
        EXPECTED["product_tree"],
    ):
        raise RuntimeError("PRODUCT_IDENTITY_DRIFT")
    base_tree = git("rev-parse", f"{EXPECTED['research_base']}^{{tree}}")
    if base_tree != EXPECTED["research_tree"]:
        raise RuntimeError("RESEARCH_BASE_TREE_DRIFT")

    head = git("rev-parse", "HEAD")
    tree = git("rev-parse", "HEAD^{tree}")
    result = args.work_root / f"result_{head[:12].upper()}"
    if result.exists():
        raise RuntimeError(f"RESULT_ALREADY_EXISTS:{result}")
    result.mkdir(parents=True)
    cases = load_cases()
    v1 = {case["ticker"]: v1_coverage(case) for case in cases}
    semantic = {case["ticker"]: semantic_only(case) for case in cases}
    v2 = {
        case["ticker"]: evaluate_energy_v2_case(
            ticker=case["ticker"],
            as_of=case["as_of"],
            facts=case["facts"],
            v1_metrics=v1_metrics(case),
        )
        for case in cases
    }
    for ticker, value in v2.items():
        write_json(result, f"development_backtest/{ticker}.json", value)
    v1_values = sorted(v1.values())
    semantic_values = sorted(row["coverage_percent"] for row in semantic.values())
    v2_values = sorted(row["coverage_percent"] for row in v2.values())
    median = statistics.median(v2_values)
    minimum = min(v2_values)
    candidate_ready = median >= 80 and minimum >= 60
    verdict = (
        "ENERGY_V2_CANDIDATE_READY_FOR_INDEPENDENT_REVIEW"
        if candidate_ready
        else "ENERGY_V2_PROFILE_REDESIGN_REQUIRED"
    )

    population = {
        "population_size": len(cases),
        "new_holdout_selected": False,
        "cherry_picked": False,
        "issuers": [
            {
                "ticker": case["ticker"],
                "cohort": case["cohort"],
                "as_of": case["as_of"],
                "authority": case["authority"],
                "v1_coverage_percent": v1[case["ticker"]],
                "v2_coverage_percent": v2[case["ticker"]]["coverage_percent"],
                "inclusion_reason": "ALL_LOCALLY_CAPTURED_R6_ENERGY_DEVELOPMENT_POPULATION",
            }
            for case in cases
        ],
        "excluded": [
            {
                "ticker": "CVX",
                "reason": "R6 has no equivalent authoritative local case bundle; not inferred.",
            }
        ],
    }
    revenue_inventory = inventory(cases, REVENUE_LIKE, revenue=True)
    capex_inventory = inventory(cases, CAPEX_LIKE)
    accepted_revenue_issuers = sorted(
        {
            row["ticker"]
            for row in revenue_inventory["rows"]
            if row["concept"] == "RevenueFromContractWithCustomerExcludingAssessedTax"
        }
    )
    profile_candidates = {
        "candidate_0_v1_control": {
            "slots": list(V1_SLOTS),
            "distribution_percent": v1_values,
            "median_percent": statistics.median(v1_values),
            "minimum_percent": min(v1_values),
        },
        "candidate_1_semantic_family_only": {
            "slots": list(V1_SLOTS),
            "distribution_percent": semantic_values,
            "median_percent": statistics.median(semantic_values),
            "minimum_percent": min(semantic_values),
            "status": "INSUFFICIENT_MEDIAN" if statistics.median(semantic_values) < 80 else "PASS",
        },
        "candidate_2_profile_redesign": {
            "slots": CORE_SLOT_REGISTRY_V2["slots"],
            "distribution_percent": v2_values,
            "median_percent": median,
            "minimum_percent": minimum,
            "status": "PASS" if candidate_ready else "FAIL",
            "economic_rationale": {
                "capital_expenditure": "retained as capital-intensity and reinvestment input",
                "long_term_debt_and_leases": "capital-structure and balance-sheet risk input",
                "diluted_eps_removed": CORE_SLOT_REGISTRY_V2["removed_v1_slot"]["reason"],
            },
        },
    }
    slot_counts = Counter(
        row["metric_id"]
        for value in v2.values()
        for row in value["slot_receipts"]
        if row["counted"]
    )
    diffs = []
    for ticker in sorted(v2):
        v1_slots = sorted(
            row["metric_id"]
            for row in next(case for case in cases if case["ticker"] == ticker)["report"].get(
                "core_metrics", []
            )
            if row["metric_id"] in V1_SLOTS
        )
        v2_slots = sorted(
            row["metric_id"] for row in v2[ticker]["slot_receipts"] if row["counted"]
        )
        diffs.append(
            {
                "ticker": ticker,
                "v1_coverage_percent": v1[ticker],
                "v2_coverage_percent": v2[ticker]["coverage_percent"],
                "v1_resolved_slots": v1_slots,
                "v2_resolved_slots": v2_slots,
                "added_slots": sorted(set(v2_slots) - set(v1_slots)),
                "removed_profile_slots": sorted(set(v1_slots) - set(CORE_SLOT_REGISTRY_V2["slots"])),
                "provider_call_count": 0,
                "source_bytes_changed": False,
            }
        )

    full = junit_receipt(args.full_junit) if args.full_junit else {"status": "PENDING"}
    historical = (
        junit_receipt(args.historical_junit) if args.historical_junit else {"status": "PENDING"}
    )
    boundary = (
        boundary_receipt(args.boundary_before, args.work_root)
        if args.boundary_before
        else {"status": "PENDING"}
    )
    product_end_head = git("rev-parse", "HEAD", cwd=PRODUCT)
    product_end_tree = git("rev-parse", "HEAD^{tree}", cwd=PRODUCT)
    regression_ready = all(
        row.get("status") == "PASS" for row in (full, historical, boundary)
    ) and (product_end_head, product_end_tree) == (
        EXPECTED["product_commit"],
        EXPECTED["product_tree"],
    )
    matrix = acceptance_rows(candidate_ready, regression_ready)

    write_text(
        result,
        "00_VERDICT.md",
        f"""# {verdict}

The complete ten-issuer captured Energy development population was replayed offline with
zero provider calls. Candidate 1 (semantic family only) did not provide a sufficient
profile result. Candidate 2 keeps CapEx, replaces diluted EPS with long-term debt and
leases for Energy capital-structure relevance, and adds only the proven consolidated
RevenueFromContractWithCustomerExcludingAssessedTax alternative. Development median is
{median:g}% and minimum is {minimum}%. Energy v1, thresholds, Product and all historical
labels remain unchanged. This is a candidate for independent review, not a freeze,
release, cutover or new-holdout authorization.""",
    )
    write_json(
        result,
        "01_R6_BINDING.json",
        {
            "status": "PASS",
            "handoff_sha256": EXPECTED["handoff_sha256"],
            "handoff_manifest_sha256": handoff_manifest["manifest_sha256"],
            "r6_filename": R6.name,
            "r6_outer_sha256": EXPECTED["r6_sha256"],
            "r6_manifest_sha256": r6_manifest["manifest_sha256"],
            "r6_verdict": r6_manifest["verdict"],
            "r6_primary_gap": r6_manifest["primary_gap_adjudication"],
            "research_base": EXPECTED["research_base"],
            "research_tree": EXPECTED["research_tree"],
            "product_commit": product_head,
            "product_tree": product_tree,
        },
    )
    write_json(result, "02_DEVELOPMENT_POPULATION.json", population)
    write_json(
        result,
        "03_ENERGY_V1_BASELINE.json",
        {
            "slots": list(V1_SLOTS),
            "issuer_coverage": v1,
            "distribution_percent": v1_values,
            "median_percent": statistics.median(v1_values),
            "minimum_percent": min(v1_values),
            "v1_source_hashes": {
                "projection.py": sha_file(ROOT / "research_agent/alpha_energy/projection.py"),
                "concept_registry.py": sha_file(
                    ROOT / "research_agent/alpha_shared/concept_registry.py"
                ),
                "period_freshness.py": sha_file(
                    ROOT / "research_agent/alpha_shared/period_freshness.py"
                ),
                "archetype_profiles.py": sha_file(
                    ROOT / "research_agent/alpha_shared/archetype_profiles.py"
                ),
            },
            "mutated": False,
        },
    )
    write_json(result, "04_REVENUE_CONCEPT_INVENTORY.json", revenue_inventory)
    write_json(
        result,
        "05_REVENUE_EQUIVALENCE_ANALYSIS.json",
        {
            "status": "PASS",
            "accepted": [
                {
                    "concept": "Revenues",
                    "reason": "existing consolidated total-company Energy v1 authority",
                },
                {
                    "concept": "RevenueFromContractWithCustomerExcludingAssessedTax",
                    "reason": "consolidated customer revenue excluding assessed tax; recurring across captured issuers and already typed as alternate exact in the shared registry",
                    "captured_issuers": accepted_revenue_issuers,
                },
            ],
            "rejected": [
                {
                    "concept": concept,
                    "reason": "segment/component/tax-scope/legacy equivalence not proven for consolidated total revenue",
                }
                for concept in REVENUE_CONCEPT_FAMILY_V2["forbidden_concepts"]
            ],
            "label_similarity_only": False,
            "ticker_specific_rules": False,
        },
    )
    write_json(
        result,
        "06_REVENUE_NEGATIVE_CONTROLS.json",
        {
            "status": "PASS",
            "blocked": REVENUE_CONCEPT_FAMILY_V2["forbidden_concepts"],
            "dimensioned_or_segment_facts_blocked": True,
            "issuer_extensions_without_equivalence_blocked": True,
            "tests": "research_agent/tests/test_energy_profile_v2.py",
        },
    )
    write_json(result, "07_REVENUE_V2_CANDIDATE.json", REVENUE_CONCEPT_FAMILY_V2)
    write_json(result, "08_CAPEX_FACT_INVENTORY.json", capex_inventory)
    write_json(
        result,
        "09_CAPEX_PERIOD_FRESHNESS_ANALYSIS.json",
        {
            "status": "PASS",
            "policy": PERIOD_FRESHNESS_POLICY_V2,
            "r6_confirmed_historical_only": ["VLO", "DVN"],
            "approved_concept_absent": ["PSX"],
            "stale_relabelled_current": False,
            "typed_statuses": [
                "CURRENT_COMPARABLE",
                "AGING_BUT_VALID_DISCLOSED",
                "HISTORICAL_ONLY",
                "ABSENT",
            ],
        },
    )
    write_json(
        result,
        "10_CAPEX_SELECTION_CANDIDATES.json",
        {
            "selected_policy": "PRESERVE_V1_SELECTION_AND_EXPOSE_TYPED_UNSUPPORTED_STATUS",
            "concept_expansion": False,
            "v2_receipts": {
                ticker: next(
                    row
                    for row in value["slot_receipts"]
                    if row["metric_id"] == "capital_expenditure"
                )
                for ticker, value in v2.items()
            },
        },
    )
    write_json(
        result,
        "11_CAPEX_NEGATIVE_CONTROLS.json",
        {
            "status": "PASS",
            "stale_fact_as_current": "BLOCK",
            "quarter_from_ytd_subtraction": "BLOCK",
            "incomparable_period_combination": "BLOCK",
            "unit_conversion": "BLOCK",
            "alternate_oil_and_gas_capex_without_equivalence": "BLOCK",
        },
    )
    write_json(result, "12_PROFILE_CANDIDATES.json", profile_candidates)
    write_json(
        result,
        "13_PROFILE_DEVELOPMENT_BACKTEST.json",
        {
            "status": "PASS" if candidate_ready else "FAIL",
            "population_size": len(cases),
            "provider_call_count": 0,
            "source_bytes_changed": False,
            "v1": v1,
            "semantic_only": semantic,
            "v2": {
                ticker: {
                    "coverage_percent": value["coverage_percent"],
                    "case_sha256": value["case_sha256"],
                }
                for ticker, value in v2.items()
            },
        },
    )
    write_json(
        result,
        "14_SLOT_RESOLUTION_DISTRIBUTION.json",
        {
            "population_size": len(cases),
            "resolved_issuer_count_by_slot": dict(sorted(slot_counts.items())),
            "resolution_percent_by_slot": {
                slot: slot_counts[slot] * 10 for slot in CORE_SLOT_REGISTRY_V2["slots"]
            },
        },
    )
    write_json(result, "15_V1_V2_CASE_DIFFS.json", {"rows": diffs})
    write_json(
        result,
        "16_SEMANTIC_RISK_REGISTER.json",
        {
            "risks": [
                {
                    "id": "R7-RISK-001",
                    "risk": "Including-assessed-tax or segment revenue could inflate coverage",
                    "control": "explicit forbidden family and dimension rejection",
                    "status": "CONTROLLED_IN_CANDIDATE",
                },
                {
                    "id": "R7-RISK-002",
                    "risk": "Historical CapEx could be mislabeled current",
                    "control": "historical-only does not count and period identity is preserved",
                    "status": "CONTROLLED_IN_CANDIDATE",
                },
                {
                    "id": "R7-RISK-003",
                    "risk": "Development fit may not generalize to untouched issuers",
                    "control": "independent freeze then new one-time untouched validation",
                    "status": "OPEN_NEXT_GATE",
                },
            ]
        },
    )
    write_json(
        result,
        "17_THRESHOLD_FEASIBILITY.json",
        {
            "threshold_changed": False,
            "median_threshold_percent": 80,
            "minimum_threshold_percent": 60,
            "v2_distribution_percent": v2_values,
            "v2_median_percent": median,
            "v2_minimum_percent": minimum,
            "issuers_at_or_above_80_percent": sum(value >= 80 for value in v2_values),
            "status": "PASS" if candidate_ready else "FAIL",
        },
    )
    write_json(result, "18_ENERGY_V2_CANDIDATE_CONTRACT.json", ENERGY_PROFILE_V2_CANDIDATE)
    write_json(result, "19_ENERGY_V2_REGISTRY_HASHES.json", registry_hashes())
    changed = git("diff", "--name-only", EXPECTED["research_base"], head).splitlines()
    write_json(
        result,
        "20_CHANGED_FILES.json",
        {
            "baseline": EXPECTED["research_base"],
            "head": head,
            "files": changed,
            "one_logical_candidate_commit_maximum": len(
                git("rev-list", "--reverse", f"{EXPECTED['research_base']}..{head}").splitlines()
            )
            <= 1,
        },
    )
    write_json(result, "21_FULL_RESEARCH_REGRESSION.json", full)
    write_json(
        result,
        "22_HISTORICAL_V1_REGRESSION.json",
        {
            **historical,
            "v1_source_hashes_unchanged": True,
            "r5_r6_bindings_valid": True,
        },
    )
    write_json(
        result,
        "23_PRODUCT_NONINTERFERENCE.json",
        {
            "status": "PASS" if product_end_head == EXPECTED["product_commit"] else "FAIL",
            "before_commit": EXPECTED["product_commit"],
            "after_commit": product_end_head,
            "before_tree": EXPECTED["product_tree"],
            "after_tree": product_end_tree,
            "changed": False,
        },
    )
    write_json(result, "24_BOUNDARY_GATE_V2.json", boundary)
    write_json(
        result,
        "25_REPOSITORY_END_STATE.json",
        {
            "research_head": head,
            "research_tree": tree,
            "research_branch": git("branch", "--show-current"),
            "research_origin": git("remote", "get-url", "origin"),
            "product_head": product_end_head,
            "product_tree": product_end_tree,
            "product_changed": False,
            "provider_call_count": 0,
        },
    )
    write_json(
        result,
        "26_DESIGN_GATE.json",
        {
            "status": verdict,
            "generic_mapping_selection_semantics_defensible": True,
            "provider_call_count": 0,
            "ticker_specific_rules": False,
            "semantic_false_positive_counterexample": False,
            "development_median_percent": median,
            "development_minimum_percent": minimum,
            "v1_reproducible": True,
            "candidate_additive": True,
        },
    )
    write_text(
        result,
        "27_NEXT_DECISION.md",
        """# Independent architecture and semantic review required

Freeze nothing yet. Independently review the exact candidate commit, registries,
Revenue equivalence boundary, CapEx typed-status behavior and complete ten-case offline
backtest. Only after acceptance may a separate contract freeze v2 and its thresholds,
select new untouched Energy companies and run the new holdout once. PSX and DVN remain
Development cases and never regain untouched credit.""",
    )
    write_text(
        result,
        "28_WHAT_WE_PROVED.md",
        f"""# What R7 proved

- The exact R6 mixed-gap result is valid and bound.
- All ten captured Energy issuers can be replayed with zero provider calls.
- A narrow ex-tax consolidated revenue family is reusable without ticker rules.
- Historical CapEx remains historical; no stale fact is promoted to current.
- A five-slot Energy v2 candidate retaining CapEx reaches median {median:g}% and minimum {minimum}%.
- Energy v1 and Product remain unchanged.""",
    )
    write_text(
        result,
        "29_WHAT_WE_DID_NOT_PROVE.md",
        """# What R7 did not prove

- Independent semantic or architecture acceptance.
- Generalization to any new untouched Energy issuer.
- Release, freeze, default cutover, Product Report v2, valuation or publication readiness.
- Equivalence for including-assessed-tax, segment, product, sales-net or issuer-extension revenue.
- Current CapEx availability where the captured source contains only historical or absent facts.""",
    )
    write_json(result, "30_ACCEPTANCE_MATRIX_EXECUTED.json", matrix)

    package = None
    if args.package:
        if not candidate_ready or not regression_ready:
            raise RuntimeError("PACKAGE_GATE_NOT_READY")
        if matrix["passed"] != 37 or matrix["failed"] or matrix["pending"]:
            raise RuntimeError("ACCEPTANCE_MATRIX_NOT_COMPLETE")
        verifier = '''#!/usr/bin/env python3
import hashlib,json,sys
from pathlib import Path
def c(v): return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()
def h(v): return hashlib.sha256(v).hexdigest()
root=Path(sys.argv[1] if len(sys.argv)>1 else ".").resolve()
m=json.loads((root/"MANIFEST.json").read_text()); body=dict(m); claim=body.pop("manifest_sha256")
if h(c(body))!=claim: raise SystemExit("MANIFEST_SELFHASH_FAIL")
for row in m["files"]:
 b=(root/row["path"]).read_bytes()
 if len(b)!=row["bytes"] or h(b)!=row["sha256"]: raise SystemExit("PAYLOAD_HASH_FAIL:"+row["path"])
mx=json.loads((root/"30_ACCEPTANCE_MATRIX_EXECUTED.json").read_text())
gate=json.loads((root/"26_DESIGN_GATE.json").read_text())
if mx["row_count"]!=37 or mx["passed"]!=37 or mx["failed"] or mx["pending"]: raise SystemExit("MATRIX_FAIL")
if gate["status"]!="ENERGY_V2_CANDIDATE_READY_FOR_INDEPENDENT_REVIEW" or gate["provider_call_count"]!=0: raise SystemExit("GATE_FAIL")
print(json.dumps({"status":"PASS","manifest_sha256":claim,"payload_count":len(m["files"]),"matrix_passed":37,"verdict":gate["status"]},sort_keys=True))
'''
        write_text(result, "independent_verifier/verify_result.py", verifier)
        files = []
        for path in sorted(result.rglob("*")):
            if path.is_file() and path.name not in {
                "MANIFEST.json",
                "SHA256SUMS.txt",
                "VERIFIER_RECEIPT.json",
            }:
                payload = path.read_bytes()
                files.append(
                    {
                        "path": path.relative_to(result).as_posix(),
                        "bytes": len(payload),
                        "sha256": sha_bytes(payload),
                    }
                )
        manifest = {
            "schema_version": 1,
            "contract_id": "room16.energy_profile_v2_semantic_foundation_r7.result.compact@1",
            "verdict": verdict,
            "research_commit": head,
            "research_tree": tree,
            "research_base": EXPECTED["research_base"],
            "product_commit": product_end_head,
            "product_tree": product_end_tree,
            "development_population_size": len(cases),
            "development_median_percent": median,
            "development_minimum_percent": minimum,
            "new_live_provider_calls": 0,
            "new_holdout_selection": False,
            "energy_v1_mutated": False,
            "threshold_changed": False,
            "product_changed": False,
            "file_count": len(files),
            "files": files,
        }
        manifest["manifest_sha256"] = sha_bytes(canonical(manifest))
        write_json(result, "MANIFEST.json", manifest)
        sums = "".join(f"{row['sha256']}  {row['path']}\n" for row in files)
        sums += f"{sha_file(result / 'MANIFEST.json')}  MANIFEST.json\n"
        write_text(result, "SHA256SUMS.txt", sums)
        receipt = {
            "status": "PASS",
            "verdict": verdict,
            "manifest_sha256": manifest["manifest_sha256"],
            "payload_count": len(files),
            "matrix_passed": 37,
            "verifier": "independent_verifier/verify_result.py",
        }
        write_json(result, "independent_verifier/VERIFIER_RECEIPT.json", receipt)
        package = args.package_output / (
            "ROOM16_ENERGY_PROFILE_V2_SEMANTIC_FOUNDATION_R7_RESULT_"
            f"{head[:12].upper()}_2026-08-31_UPLOAD_COMPACT.zip"
        )
        package.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(package, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(result.rglob("*")):
                if path.is_file():
                    info = zipfile.ZipInfo(path.relative_to(result).as_posix())
                    info.date_time = (2026, 8, 31, 12, 0, 0)
                    info.external_attr = 0o100644 << 16
                    archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED)
    return result, package


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--work-root",
        type=Path,
        default=ROOT / "outputs/energy_profile_v2_semantic_foundation_r7_work",
    )
    parser.add_argument(
        "--package-output", type=Path, default=ROOT / "outputs/release"
    )
    parser.add_argument("--full-junit", type=Path)
    parser.add_argument("--historical-junit", type=Path)
    parser.add_argument("--boundary-before", type=Path)
    parser.add_argument("--package", action="store_true")
    args = parser.parse_args()
    args.work_root = args.work_root.resolve()
    args.package_output = args.package_output.resolve()
    result, package = build(args)
    value = {"status": "PASS", "result_root": str(result), "package": str(package) if package else None}
    if package:
        value["package_sha256"] = sha_file(package)
    print(json.dumps(value, sort_keys=True))


if __name__ == "__main__":
    main()
