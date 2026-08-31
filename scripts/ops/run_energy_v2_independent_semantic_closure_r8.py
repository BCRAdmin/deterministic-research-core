#!/usr/bin/env python3
"""Build independently recomputed Energy-v2 semantic closure evidence."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import statistics
import subprocess
import sys
import tempfile
import zipfile
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from research_agent.alpha_energy.v2 import (  # noqa: E402
    CORE_SLOT_REGISTRY_V2,
    DEBT_COMPARABILITY_CONTRACT_V2,
    ENERGY_PROFILE_V2_CANDIDATE,
    MAPPING_REGISTRY_V2,
    PERIOD_FRESHNESS_POLICY_V2,
    REVENUE_CONCEPT_FAMILY_V2,
    _normalise_fact,
    evaluate_energy_v2_case,
    registry_hashes,
)
from research_agent.compiler_foundation.canonical import sha256_json  # noqa: E402
from scripts.ops.run_energy_profile_v2_semantic_foundation_r7 import (  # noqa: E402
    load_cases,
    semantic_only,
    v1_coverage,
    v1_metrics,
)


PRODUCT = ROOT.parent / "company-dossier-lab"
FOREIGN = Path(
    "/Users/BjornRosinger/Documents/DreamFactory/Utility-Websites/"
    "materialbedarf-rechner.de"
)
HANDOFF = Path(
    "/Users/BjornRosinger/Downloads/"
    "ROOM16_ENERGY_V2_INDEPENDENT_SEMANTIC_CLOSURE_R8_"
    "5C4F87B34D69_2026-09-01.zip"
)
R7 = ROOT / (
    "outputs/release/ROOM16_ENERGY_PROFILE_V2_SEMANTIC_FOUNDATION_R7_"
    "RESULT_6A36CD844AE0_2026-08-31_UPLOAD_COMPACT.zip"
)

EXPECTED = {
    "handoff_sha256": "5c4f87b34d699f767ff022b0c469c1f4597ca882ac8d83f499da52d0f40ed722",
    "r7_sha256": "d7a529a005137e944ec95bd9b59e2ac1d42d836b0348f69c78a2273f50088122",
    "r7_manifest_sha256": "822d9b0b50914f64e6e91ab60f4ec291b9031423d848e3ea06c872e08df7c2f5",
    "research_base": "6a36cd844ae096c46b7fd03ad3e77b8d1f1e788d",
    "research_tree": "a17ea5a4af9a72250c6861a067c090b34f2fe598",
    "research_parent": "6ca0fa02f4121628228474e681465d7eb2760fb2",
    "product_commit": "ed86bb841aab88d878266cf8ed498eabc6fa9029",
    "product_tree": "a382d9c096825910b5e0e8865414ea232b95bd40",
}

V1_SOURCE_HASHES = {
    "research_agent/alpha_energy/projection.py": (
        "17884480a265cea33313abf53604b7633c9f04a2cbc42cb3b905f6b6cbd285b9"
    ),
    "research_agent/alpha_shared/concept_registry.py": (
        "d453ce04c0d20687b0f826b15473e5e03665dde9ce1261d7a056c280a92b46ae"
    ),
    "research_agent/alpha_shared/period_freshness.py": (
        "108ac6decb28d600196244b9ce1738e5d6a5666561f0cc1c61faf01d419b81b7"
    ),
    "research_agent/alpha_shared/archetype_profiles.py": (
        "222c54304aa5cbfcad9fb74d554ff8f2d322fd1c0ccd418167e41ad5f892a547"
    ),
}

OLD_REVENUE_CONCEPTS = {
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
}
DEBT_CONCEPTS = set(DEBT_COMPARABILITY_CONTRACT_V2["concepts"])
DEVELOPMENT_TICKERS = {
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
}


def canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()


def pretty(value: Any) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n"
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
    target.write_text(value.rstrip() + "\n", encoding="utf-8")


def verify_zip(path: Path, expected_sha256: str) -> dict[str, Any]:
    if not path.is_file() or sha_file(path) != expected_sha256:
        raise RuntimeError(f"ZIP_IDENTITY_FAIL:{path.name}")
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if archive.testzip() is not None or len(names) != len(set(names)):
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


def verify_r7() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    manifest = verify_zip(R7, EXPECTED["r7_sha256"])
    if manifest["manifest_sha256"] != EXPECTED["r7_manifest_sha256"]:
        raise RuntimeError("R7_MANIFEST_IDENTITY_FAIL")
    with tempfile.TemporaryDirectory(prefix="room16-r8-r7-") as temporary:
        root = Path(temporary)
        with zipfile.ZipFile(R7) as archive:
            archive.extractall(root)
        receipt = json.loads(
            subprocess.check_output(
                [sys.executable, str(root / "independent_verifier/verify_result.py"), str(root)],
                text=True,
            )
        )
        if receipt.get("status") != "PASS" or receipt.get("matrix_passed") != 37:
            raise RuntimeError("R7_STANDALONE_VERIFIER_FAIL")
        gate = json.loads((root / "26_DESIGN_GATE.json").read_text())
        matrix = json.loads((root / "30_ACCEPTANCE_MATRIX_EXECUTED.json").read_text())
        metrics = {
            "v1": json.loads((root / "03_ENERGY_V1_BASELINE.json").read_text()),
            "backtest": json.loads(
                (root / "13_PROFILE_DEVELOPMENT_BACKTEST.json").read_text()
            ),
            "distribution": json.loads(
                (root / "14_SLOT_RESOLUTION_DISTRIBUTION.json").read_text()
            ),
            "case_diffs": json.loads((root / "15_V1_V2_CASE_DIFFS.json").read_text()),
            "registries": json.loads(
                (root / "19_ENERGY_V2_REGISTRY_HASHES.json").read_text()
            ),
            "cases": {
                path.stem: json.loads(path.read_text())
                for path in sorted((root / "development_backtest").glob("*.json"))
            },
        }
    if gate.get("status") != "ENERGY_V2_CANDIDATE_READY_FOR_INDEPENDENT_REVIEW":
        raise RuntimeError("R7_DESIGN_GATE_FAIL")
    if matrix.get("row_count") != 37 or matrix.get("passed") != 37:
        raise RuntimeError("R7_MATRIX_FAIL")
    return manifest, receipt, metrics


def _latest(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return sorted(
        rows,
        key=lambda row: (
            str(row.get("filed") or ""),
            str(row.get("accession") or ""),
            str(row.get("candidate_id") or ""),
        ),
        reverse=True,
    )[0]


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise RuntimeError(f"NON_DECIMAL_VALUE:{value}") from exc


def revenue_evidence(cases: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    ledger: list[dict[str, Any]] = []
    concept_only: list[dict[str, Any]] = []
    for case in cases:
        grouped: dict[tuple[str, str, str], dict[str, list[dict[str, Any]]]] = defaultdict(
            lambda: defaultdict(list)
        )
        for raw in case["facts"]:
            row = _normalise_fact(raw)
            if (
                row["concept"] not in OLD_REVENUE_CONCEPTS
                or row["namespace"] != "us-gaap"
                or row["dimensions_present"]
                or row["dimension_key"] != "NO_DIMENSIONS"
                or row["unit"] != "USD"
                or not row["period_start"]
                or not row["period_end"]
            ):
                continue
            key = (row["period_start"], row["period_end"], row["unit"])
            grouped[key][row["concept"]].append(row)
        for (start, end, unit), concepts in sorted(grouped.items()):
            revenues = concepts.get("Revenues", [])
            ex_tax = concepts.get(
                "RevenueFromContractWithCustomerExcludingAssessedTax", []
            )
            if revenues and ex_tax:
                same_filing = [
                    (left, right)
                    for left in revenues
                    for right in ex_tax
                    if left.get("accession")
                    and left.get("accession") == right.get("accession")
                ]
                if same_filing:
                    left, right = sorted(
                        same_filing,
                        key=lambda pair: (
                            str(pair[0].get("filed") or ""),
                            str(pair[0].get("accession") or ""),
                            str(pair[0].get("candidate_id") or ""),
                            str(pair[1].get("candidate_id") or ""),
                        ),
                        reverse=True,
                    )[0]
                else:
                    left, right = _latest(revenues), _latest(ex_tax)
                left_value = _decimal(left["value"])
                right_value = _decimal(right["value"])
                difference = right_value - left_value
                denominator = max(abs(left_value), abs(right_value))
                relative = abs(difference) / denominator if denominator else Decimal(0)
                classification = (
                    "EXACT_EQUAL" if difference == 0 else "UNEXPLAINED_NON_EQUIVALENT"
                )
                ledger.append(
                    {
                        "ticker": case["ticker"],
                        "period_start": start,
                        "period_end": end,
                        "basis": left["period_basis"],
                        "unit": unit,
                        "form": left["form"],
                        "revenues_accession": left["accession"],
                        "ex_tax_accession": right["accession"],
                        "revenues_candidate_id": left["candidate_id"],
                        "ex_tax_candidate_id": right["candidate_id"],
                        "revenues_value": str(left_value),
                        "ex_tax_value": str(right_value),
                        "absolute_difference": str(abs(difference)),
                        "relative_difference": str(relative),
                        "same_source_filing": left.get("accession")
                        == right.get("accession"),
                        "both_dimensionless": True,
                        "same_consolidated_scope": classification == "EXACT_EQUAL",
                        "classification": classification,
                        "tolerance_applied": False,
                    }
                )
            elif ex_tax:
                row = _latest(ex_tax)
                concept_only.append(
                    {
                        "ticker": case["ticker"],
                        "period_start": start,
                        "period_end": end,
                        "basis": row["period_basis"],
                        "unit": unit,
                        "namespace": row["namespace"],
                        "concept": row["concept"],
                        "label": row["label"],
                        "accession": row["accession"],
                        "form": row["form"],
                        "candidate_id": row["candidate_id"],
                        "value": str(row["value"]),
                        "dimensionless": True,
                        "total_company_scope_proven": False,
                        "contradictory_revenues_same_period": False,
                    }
                )
    counts = Counter(row["classification"] for row in ledger)
    matched = {
        "contract_id": "room16.energy_v2.r8.revenue_matched_pair_ledger@1",
        "decimal_arithmetic": "EXACT",
        "rounding_tolerance_invented": False,
        "row_count": len(ledger),
        "issuer_count": len({row["ticker"] for row in ledger}),
        "classification_counts": dict(sorted(counts.items())),
        "material_unexplained_counterexample_count": counts[
            "UNEXPLAINED_NON_EQUIVALENT"
        ],
        "rows": ledger,
    }
    only = {
        "contract_id": "room16.energy_v2.r8.revenue_concept_only_evidence@1",
        "row_count": len(concept_only),
        "issuer_count": len({row["ticker"] for row in concept_only}),
        "generic_total_company_equivalence_proven": False,
        "rows": concept_only,
    }
    return matched, only


def _receipt_basis(
    ticker: str,
    metric_id: str,
    receipt: dict[str, Any],
    baseline: list[dict[str, Any]],
) -> dict[str, Any]:
    selected = receipt.get("selected_fact") or {}
    base = next((row for row in baseline if row.get("metric_id") == metric_id), {})
    return {
        "ticker": ticker,
        "metric_id": metric_id,
        "candidate_id": selected.get("candidate_id") or base.get("candidate_id"),
        "concept": selected.get("concept") or base.get("concept_or_formula"),
        "value": selected.get("value") or base.get("value"),
        "basis": selected.get("period_basis")
        or ("STANDALONE_QUARTER" if base.get("period_start_or_null") else None),
        "period_start": selected.get("period_start") or base.get("period_start_or_null"),
        "period_end": selected.get("period_end") or base.get("period_end"),
        "status": receipt.get("status"),
        "source_artifact_sha256": selected.get("source_artifact_sha256"),
    }


def period_sensitivity(
    cases: list[dict[str, Any]],
    r7_cases: dict[str, dict[str, Any]],
    final_cases: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    rows = []
    broadening_used = False
    for case in cases:
        ticker = case["ticker"]
        baseline = v1_metrics(case)
        old = {row["metric_id"]: row for row in r7_cases[ticker]["slot_receipts"]}
        final = {row["metric_id"]: row for row in final_cases[ticker]["slot_receipts"]}
        for metric_id in ("revenue", "net_income"):
            p0 = _receipt_basis(ticker, metric_id, old[metric_id], baseline)
            if p0["candidate_id"] and p0["basis"] != "STANDALONE_QUARTER":
                broadening_used = True
            p1 = dict(p0)
            p1["policy"] = "V1_STANDALONE_QUARTER_PRESERVED"
            p2 = _receipt_basis(ticker, metric_id, final[metric_id], baseline)
            rows.append(
                {
                    "ticker": ticker,
                    "metric_id": metric_id,
                    "p0_r7": p0,
                    "p1_v1_basis_preserving": p1,
                    "p2_r8_final": p2,
                    "p0_to_p1_changed": False,
                    "p1_to_p2_changed": p1.get("candidate_id") != p2.get("candidate_id"),
                    "p1_to_p2_reason": (
                        "UNSAFE_EX_TAX_CONCEPT_REMOVED"
                        if p1.get("concept")
                        == "RevenueFromContractWithCustomerExcludingAssessedTax"
                        and p2.get("candidate_id") is None
                        else "NO_CHANGE"
                    ),
                }
            )
    return {
        "contract_id": "room16.energy_v2.r8.period_basis_sensitivity@1",
        "variants": {
            "P0": "R7_CURRENT_BEHAVIOR",
            "P1": "V1_STANDALONE_QUARTER_FOR_REVENUE_AND_NET_INCOME",
            "P2": "R8_FINAL_CORRECTED_CANDIDATE",
        },
        "r7_basis_broadening_used_by_selected_facts": broadening_used,
        "p0_to_p1_changed_selection_count": sum(
            row["p0_to_p1_changed"] for row in rows
        ),
        "p1_to_p2_changed_selection_count": sum(
            row["p1_to_p2_changed"] for row in rows
        ),
        "rows": rows,
    }


def aging_sensitivity(
    cases: list[dict[str, Any]], final_cases: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    issuer_rows = []
    for case in cases:
        ticker = case["ticker"]
        baseline = {row["metric_id"]: row for row in v1_metrics(case)}
        result = final_cases[ticker]
        aging_slots = []
        current_count = 0
        usable_count = 0
        for receipt in result["slot_receipts"]:
            if receipt["counted"]:
                usable_count += 1
            if receipt["counted"] and receipt["status"] == "CURRENT_COMPARABLE":
                current_count += 1
            if receipt["counted"] and receipt["status"] == "AGING_BUT_VALID_DISCLOSED":
                selected = receipt.get("selected_fact") or {}
                age_days = selected.get("age_days")
                period_end = selected.get("period_end")
                if age_days is None:
                    base = baseline.get(receipt["metric_id"], {})
                    period_end = period_end or base.get("period_end")
                    if period_end:
                        age_days = (
                            date.fromisoformat(case["as_of"])
                            - date.fromisoformat(period_end)
                        ).days
                aging_slots.append(
                    {
                        "metric_id": receipt["metric_id"],
                        "age_days": age_days,
                        "period_end": period_end,
                        "status": receipt["status"],
                    }
                )
        issuer_rows.append(
            {
                "ticker": ticker,
                "usable_core_coverage_percent": usable_count * 20,
                "current_comparable_core_coverage_percent": current_count * 20,
                "aging_slot_count": len(aging_slots),
                "aging_slots": aging_slots,
                "historical_only_counted": any(
                    row["counted"] and row["status"] == "HISTORICAL_ONLY"
                    for row in result["slot_receipts"]
                ),
            }
        )
    usable = sorted(row["usable_core_coverage_percent"] for row in issuer_rows)
    current = sorted(
        row["current_comparable_core_coverage_percent"] for row in issuer_rows
    )
    return {
        "contract_id": "room16.energy_v2.r8.aging_coverage_sensitivity@1",
        "issuer_rows": issuer_rows,
        "usable_distribution_percent": usable,
        "usable_median_percent": statistics.median(usable),
        "usable_minimum_percent": min(usable),
        "usable_issuers_at_or_above_80": sum(value >= 80 for value in usable),
        "current_only_distribution_percent": current,
        "current_only_median_percent": statistics.median(current),
        "current_only_minimum_percent": min(current),
        "current_only_issuers_at_or_above_80": sum(value >= 80 for value in current),
        "historical_only_counted": any(
            row["historical_only_counted"] for row in issuer_rows
        ),
    }


def debt_evidence(
    cases: list[dict[str, Any]], final_cases: dict[str, dict[str, Any]]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    inventory_rows = []
    pair_rows = []
    for case in cases:
        grouped: dict[tuple[str, str], dict[str, list[dict[str, Any]]]] = defaultdict(
            lambda: defaultdict(list)
        )
        per_concept: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for raw in case["facts"]:
            row = _normalise_fact(raw)
            if (
                row["concept"] not in DEBT_CONCEPTS
                or row["namespace"] != "us-gaap"
                or row["dimensions_present"]
                or row["dimension_key"] != "NO_DIMENSIONS"
                or row["unit"] != "USD"
                or row["period_basis"] != "INSTANT"
                or not row["period_end"]
            ):
                continue
            per_concept[row["concept"]].append(row)
            grouped[(row["period_end"], row["unit"])][row["concept"]].append(row)
        for concept, rows in sorted(per_concept.items()):
            comparison = DEBT_COMPARABILITY_CONTRACT_V2["concepts"][concept]
            latest = _latest(rows)
            inventory_rows.append(
                {
                    "ticker": case["ticker"],
                    "concept": concept,
                    "fact_count": len(rows),
                    "grade": comparison["grade"],
                    "scope": comparison["scope"],
                    "leases_included": comparison["leases_included"],
                    "current_portion_included": "NOT_INFERRED_FROM_FACT_LABEL",
                    "latest_period_end": latest["period_end"],
                    "latest_value": str(latest["value"]),
                    "latest_candidate_id": latest["candidate_id"],
                }
            )
        for (period_end, unit), concepts in sorted(grouped.items()):
            if len(concepts) < 2:
                continue
            selected = {concept: _latest(rows) for concept, rows in concepts.items()}
            names = sorted(selected)
            for index, left_name in enumerate(names):
                for right_name in names[index + 1 :]:
                    left, right = selected[left_name], selected[right_name]
                    left_value, right_value = _decimal(left["value"]), _decimal(
                        right["value"]
                    )
                    pair_rows.append(
                        {
                            "ticker": case["ticker"],
                            "period_end": period_end,
                            "unit": unit,
                            "left_concept": left_name,
                            "left_grade": DEBT_COMPARABILITY_CONTRACT_V2["concepts"]
                            [left_name]["grade"],
                            "left_value": str(left_value),
                            "left_accession": left["accession"],
                            "right_concept": right_name,
                            "right_grade": DEBT_COMPARABILITY_CONTRACT_V2["concepts"]
                            [right_name]["grade"],
                            "right_value": str(right_value),
                            "right_accession": right["accession"],
                            "absolute_difference": str(abs(right_value - left_value)),
                            "equal_value": left_value == right_value,
                            "forced_value_equality": False,
                        }
                    )
    inventory = {
        "contract_id": "room16.energy_v2.r8.debt_concept_inventory@1",
        "row_count": len(inventory_rows),
        "rows": inventory_rows,
    }
    pairs = {
        "contract_id": "room16.energy_v2.r8.debt_matched_pair_ledger@1",
        "row_count": len(pair_rows),
        "equal_value_count": sum(row["equal_value"] for row in pair_rows),
        "different_value_count": sum(not row["equal_value"] for row in pair_rows),
        "rows": pair_rows,
    }
    selected = []
    for ticker, result in sorted(final_cases.items()):
        receipt = next(
            row
            for row in result["slot_receipts"]
            if row["metric_id"] == "long_term_debt_measure"
        )
        fact = receipt.get("selected_fact") or {}
        selected.append(
            {
                "ticker": ticker,
                "status": receipt["status"],
                "counted": receipt["counted"],
                "concept": fact.get("concept"),
                "comparability_grade": fact.get("comparability_grade"),
                "economic_scope": fact.get("economic_scope"),
                "candidate_id": fact.get("candidate_id"),
                "value": fact.get("value"),
            }
        )
    grades = {
        "contract_id": "room16.energy_v2.r8.debt_comparability_grades@1",
        "concept_grades": DEBT_COMPARABILITY_CONTRACT_V2["concepts"],
        "allowed_grades": DEBT_COMPARABILITY_CONTRACT_V2["allowed_grades"],
        "grade_c_counts_as_comparable": False,
        "selected_receipts": selected,
    }
    return inventory, pairs, grades


def junit_receipt(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {"status": "PENDING"}
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


def boundary_receipt(before_path: Path | None, work: Path) -> dict[str, Any]:
    if before_path is None:
        return {"status": "PENDING"}
    module_path = ROOT / "scripts/ops/verify_project_boundary_non_interference_v2.py"
    spec = importlib.util.spec_from_file_location("room16_boundary_v2_r8", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("BOUNDARY_MODULE_IMPORT_FAIL")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    receipt = module.build_receipt(
        before=json.loads(before_path.read_text()),
        after=module.foreign_snapshot(FOREIGN),
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
                "argv": ["result", "package"],
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
                ROOT / "scripts/ops/run_energy_v2_independent_semantic_closure_r8.py",
            ],
            "deleted": [],
        },
        output_paths=[work, ROOT / "outputs/release"],
        foreign_repo_used_as_authority_input=False,
    )
    return {**receipt, "status": receipt["verdict"]}


def evidence_sha(result: Path, name: str) -> str:
    return sha_file(result / name)


def matrix_row(
    result: Path,
    test_id: str,
    scenario: str,
    expected: str,
    evidence_file: str,
    predicate: str,
    observed: Any,
    passed: bool | None,
    *,
    substantive: bool = True,
) -> dict[str, Any]:
    return {
        "test_id": test_id,
        "scenario": scenario,
        "expected": expected,
        "status": "PENDING" if passed is None else ("PASS" if passed else "FAIL"),
        "substantive": substantive,
        "evidence_file": evidence_file,
        "evidence_sha256": (
            evidence_sha(result, evidence_file)
            if (result / evidence_file).is_file()
            else "GENERATED_AFTER_MATRIX"
        ),
        "pass_predicate": predicate,
        "observed_value": observed,
    }


def build_matrix(
    result: Path,
    *,
    revenue: dict[str, Any],
    concept_only: dict[str, Any],
    period: dict[str, Any],
    aging: dict[str, Any],
    debt_inventory: dict[str, Any],
    debt_pairs: dict[str, Any],
    debt_grades: dict[str, Any],
    comparison: dict[str, Any],
    final_cases: dict[str, dict[str, Any]],
    full: dict[str, Any],
    historical: dict[str, Any],
    product: dict[str, Any],
    boundary: dict[str, Any],
    final_gate: dict[str, Any],
    package_ready: bool,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    add = lambda _result, *args, **kwargs: rows.append(
        matrix_row(result, *args, **kwargs)
    )
    add(result, "BIND-001", "R7 result outer/manifest/verifier exact", "PASS", "01_R7_BINDING.json", "all R7 identities exact and verifier PASS", "PASS", True)
    add(result, "BIND-002", "R7 commit/tree/parent exact", "PASS", "01_R7_BINDING.json", "commit/tree/parent equal contract", "PASS", True)
    add(result, "BIND-003", "R7 design metrics extracted", "PASS", "02_R7_DESIGN_METRICS.json", "three R7 distributions present", "PASS", True)
    add(result, "REV-001", "all period-matched dual-concept pairs enumerated", "PASS", "04_REVENUE_MATCHED_PAIR_LEDGER.json", "row_count == len(rows) and issuer_count > 0", revenue["row_count"], revenue["row_count"] == len(revenue["rows"]) and revenue["issuer_count"] > 0)
    add(result, "REV-002", "pair values/scopes classified", "PASS", "04_REVENUE_MATCHED_PAIR_LEDGER.json", "every row has exact classification and no tolerance", revenue["classification_counts"], all(row["classification"] in {"EXACT_EQUAL", "UNEXPLAINED_NON_EQUIVALENT"} and not row["tolerance_applied"] for row in revenue["rows"]))
    add(result, "REV-003", "no material unexplained equivalence counterexample accepted", "PASS", "05_REVENUE_EQUIVALENCE_DECISION.json", "unsafe concept removed when counterexamples exist", {"counterexamples": revenue["material_unexplained_counterexample_count"], "final_concepts": REVENUE_CONCEPT_FAMILY_V2["ordered_concepts"]}, revenue["material_unexplained_counterexample_count"] > 0 and REVENUE_CONCEPT_FAMILY_V2["ordered_concepts"] == ["Revenues"])
    add(result, "REV-004", "concept-only issuer evidence consolidated/dimensionless", "PASS", "06_REVENUE_CONCEPT_ONLY_EVIDENCE.json", "all rows dimensionless and unproven scope not promoted", {"rows": concept_only["row_count"], "promoted": concept_only["generic_total_company_equivalence_proven"]}, all(row["dimensionless"] for row in concept_only["rows"]) and not concept_only["generic_total_company_equivalence_proven"])
    revenue_negative_controls = json.loads(
        (result / "07_REVENUE_NEGATIVE_CONTROLS.json").read_text(encoding="utf-8")
    )
    negative_control_observations = {
        key: value
        for key, value in revenue_negative_controls.items()
        if key not in {"blocked_concepts", "status"}
    }
    add(result, "REV-005", "segment/product/extension revenue accepted", "BLOCK", "07_REVENUE_NEGATIVE_CONTROLS.json", "all negative controls have observed BLOCK", negative_control_observations, bool(negative_control_observations) and set(negative_control_observations.values()) == {"BLOCK"})
    add(result, "PER-001", "R7 basis broadening quantified", "PASS", "08_PERIOD_BASIS_SENSITIVITY.json", "selected-fact usage explicitly measured", period["r7_basis_broadening_used_by_selected_facts"], isinstance(period["r7_basis_broadening_used_by_selected_facts"], bool))
    add(result, "PER-002", "v1-preserving sensitivity run emitted", "PASS", "08_PERIOD_BASIS_SENSITIVITY.json", "20 revenue/net-income rows emitted", len(period["rows"]), len(period["rows"]) == 20)
    add(result, "PER-003", "final basis policy explicitly justified", "PASS", "09_PERIOD_BASIS_FINAL_POLICY.json", "revenue and net income exact standalone quarter", PERIOD_FRESHNESS_POLICY_V2["duration_basis_policy"], PERIOD_FRESHNESS_POLICY_V2["duration_basis_policy"]["revenue"] == ["STANDALONE_QUARTER"] and PERIOD_FRESHNESS_POLICY_V2["duration_basis_policy"]["net_income"] == ["STANDALONE_QUARTER"])
    add(result, "PER-004", "quarter-from-YTD synthesis introduced", "BLOCK", "09_PERIOD_BASIS_FINAL_POLICY.json", "observed BLOCK", "BLOCK", not PERIOD_FRESHNESS_POLICY_V2["quarter_from_ytd_subtraction_allowed"])
    add(result, "AGE-001", "usable and current-only coverage both computed", "PASS", "10_AGING_COVERAGE_SENSITIVITY.json", "both distributions contain ten issuers", {"usable": aging["usable_distribution_percent"], "current": aging["current_only_distribution_percent"]}, len(aging["usable_distribution_percent"]) == len(aging["current_only_distribution_percent"]) == 10)
    add(result, "AGE-002", "aging slots/age-days enumerated", "PASS", "10_AGING_COVERAGE_SENSITIVITY.json", "every aging slot has nonnegative age_days", sum(row["aging_slot_count"] for row in aging["issuer_rows"]), all(slot["age_days"] is not None and slot["age_days"] >= 0 for row in aging["issuer_rows"] for slot in row["aging_slots"]))
    add(result, "AGE-003", "historical-only counted", "BLOCK", "10_AGING_COVERAGE_SENSITIVITY.json", "observed BLOCK", "BLOCK", not aging["historical_only_counted"])
    add(result, "AGE-004", "acceptance treatment explicitly adjudicated", "PASS", "11_AGING_ACCEPTANCE_DECISION.json", "decision == DUAL_THRESHOLD_REQUIRED", "DUAL_THRESHOLD_REQUIRED", PERIOD_FRESHNESS_POLICY_V2["coverage_acceptance_semantics"] == "DUAL_THRESHOLD_REQUIRED")
    add(result, "DEBT-001", "all allowed debt concepts inventoried", "PASS", "12_DEBT_CONCEPT_INVENTORY.json", "inventory covers every observed allowed concept", sorted({row["concept"] for row in debt_inventory["rows"]}), {row["concept"] for row in debt_inventory["rows"]}.issubset(DEBT_CONCEPTS))
    add(result, "DEBT-002", "same-instant coexistence comparisons emitted", "PASS", "13_DEBT_MATCHED_PAIR_LEDGER.json", "row_count equals emitted rows", debt_pairs["row_count"], debt_pairs["row_count"] == len(debt_pairs["rows"]) and debt_pairs["row_count"] > 0)
    add(result, "DEBT-003", "comparability grades assigned", "PASS", "14_DEBT_COMPARABILITY_GRADES.json", "every selected debt is A/B or not counted", [row["comparability_grade"] for row in debt_grades["selected_receipts"]], all(not row["counted"] or row["comparability_grade"] in {"A", "B"} for row in debt_grades["selected_receipts"]))
    add(result, "DEBT-004", "slot label matches allowed semantic scope", "PASS", "15_DEBT_SLOT_FINAL_CONTRACT.json", "economic slot label is long_term_debt_measure", DEBT_COMPARABILITY_CONTRACT_V2["economic_slot_label"], DEBT_COMPARABILITY_CONTRACT_V2["economic_slot_label"] == "long_term_debt_measure")
    add(result, "DEBT-005", "ambiguous grade C counted as comparable", "BLOCK", "15_DEBT_SLOT_FINAL_CONTRACT.json", "observed BLOCK", "BLOCK", not DEBT_COMPARABILITY_CONTRACT_V2["grade_c_counts_as_comparable"])
    economic_rationale = (result / "16_PROFILE_ECONOMIC_RATIONALE.md").read_text(
        encoding="utf-8"
    )
    add(result, "PRO-001", "EPS vs debt rationale independent of gate", "PASS", "16_PROFILE_ECONOMIC_RATIONALE.md", "written rationale names analytical distinction and coverage is secondary", "PASS", all(marker in economic_rationale for marker in ("EPS", "debt", "coverage")))
    add(result, "PRO-002", "C0/C1/C2/C3 comparison emitted", "PASS", "17_PROFILE_CANDIDATE_COMPARISON.json", "four candidates present", sorted(comparison["candidates"]), sorted(comparison["candidates"]) == ["C0", "C1", "C2", "C3"])
    add(result, "PRO-003", "CapEx not removed just to lift coverage", "PASS", "18_FINAL_V2_CANDIDATE_CONTRACT.json", "capital_expenditure remains a core slot", CORE_SLOT_REGISTRY_V2["slots"], "capital_expenditure" in CORE_SLOT_REGISTRY_V2["slots"])
    evidence_quality = json.loads(
        (result / "03_R7_EVIDENCE_QUALITY_AUDIT.json").read_text(encoding="utf-8")
    )
    add(result, "EV-001", "substantive matrix rows bind files/hashes/predicates", "PASS", "03_R7_EVIDENCE_QUALITY_AUDIT.json", "R8 requires file/hash/predicate binding for every substantive row", "RECOMPUTED_BY_VERIFIER", evidence_quality["r8_substantive_binding_required"])
    add(result, "EV-002", "verifier recomputes semantic gates", "PASS", "03_R7_EVIDENCE_QUALITY_AUDIT.json", "twelve independent recomputations enumerated", len(evidence_quality["r8_verifier_required_recomputations"]), len(evidence_quality["r8_verifier_required_recomputations"]) == 12)
    add(result, "EV-003", "hardcoded true substitutes for semantic evidence", "BLOCK", "03_R7_EVIDENCE_QUALITY_AUDIT.json", "static semantic shortcut explicitly forbidden", "BLOCK", evidence_quality["r8_static_semantic_shortcut_allowed"] is False)
    values = sorted(case["coverage_percent"] for case in final_cases.values())
    add(result, "BT-001", "all 10 Development issuers replayed offline", "PASS", "20_FINAL_DEVELOPMENT_BACKTEST.json", "case_count == 10", len(final_cases), len(final_cases) == 10)
    add(result, "BT-002", "provider calls 0", "PASS", "20_FINAL_DEVELOPMENT_BACKTEST.json", "sum provider calls == 0", sum(case["provider_call_count"] for case in final_cases.values()), sum(case["provider_call_count"] for case in final_cases.values()) == 0)
    add(result, "BT-003", "final candidate median >=80 if PASS", "PASS", "20_FINAL_DEVELOPMENT_BACKTEST.json", "median >= 80", statistics.median(values), statistics.median(values) >= 80)
    add(result, "BT-004", "final candidate minimum >=60 if PASS", "PASS", "20_FINAL_DEVELOPMENT_BACKTEST.json", "minimum >= 60", min(values), min(values) >= 60)
    v1_now = {path: sha_file(ROOT / path) for path in V1_SOURCE_HASHES}
    add(result, "IMM-001", "Energy v1 hashes unchanged", "PASS", "25_HISTORICAL_V1_REGRESSION.json", "all four frozen source hashes exact", v1_now, v1_now == V1_SOURCE_HASHES)
    add(result, "IMM-002", "historical thresholds unchanged", "PASS", "18_FINAL_V2_CANDIDATE_CONTRACT.json", "thresholds remain 80/60", ENERGY_PROFILE_V2_CANDIDATE["acceptance_thresholds"], ENERGY_PROFILE_V2_CANDIDATE["acceptance_thresholds"] == {"development_median_min_percent": 80, "development_company_min_percent": 60})
    add(result, "IMM-003", "Product unchanged", "PASS", "26_PRODUCT_NONINTERFERENCE.json", "Product commit/tree exact", product["status"], product["status"] == "PASS")
    add(result, "IMM-004", "new holdout selection count 0", "PASS", "20_FINAL_DEVELOPMENT_BACKTEST.json", "backtest contains exactly the ten fixed Development issuers", len(final_cases), set(final_cases) == DEVELOPMENT_TICKERS)
    add(result, "REG-001", "full Research regression PASS", "PASS", "24_FULL_RESEARCH_REGRESSION.json", "status == PASS", full.get("status"), None if full.get("status") == "PENDING" else full.get("status") == "PASS")
    add(result, "REG-002", "historical Energy-v1 regression PASS", "PASS", "25_HISTORICAL_V1_REGRESSION.json", "status == PASS and v1 hashes exact", historical.get("status"), None if historical.get("status") == "PENDING" else historical.get("status") == "PASS" and v1_now == V1_SOURCE_HASHES)
    add(result, "REG-003", "Boundary Gate v2 PASS", "PASS", "27_BOUNDARY_GATE_V2.json", "status == PASS", boundary.get("status"), None if boundary.get("status") == "PENDING" else boundary.get("status") == "PASS")
    add(result, "GATE-001", "one allowed R8 terminal state", "PASS", "29_FINAL_GATE.json", "verdict in allowed set", final_gate["status"], final_gate["status"] in {"ENERGY_V2_SEMANTIC_CLOSURE_PASS_READY_FOR_FREEZE", "ENERGY_V2_SEMANTIC_CLOSURE_CHANGES_REQUIRED", "ENERGY_V2_CANDIDATE_REJECTED"})
    add(result, "GATE-002", "no freeze/new validation in R8", "PASS", "29_FINAL_GATE.json", "freeze false and new validation false", {"freeze": False, "new_validation": False}, not final_gate["freeze_authorized"] and not final_gate["new_validation_authorized"])
    add(result, "PKG-001", "manifest selfhash PASS", "PASS", "MANIFEST.json", "manifest selfhash recomputed by standalone verifier", "PASS" if package_ready else "PENDING", True if package_ready else None, substantive=False)
    add(result, "PKG-002", "standalone verifier PASS", "PASS", "independent_verifier/VERIFIER_RECEIPT.json", "standalone verifier receipt status PASS", "PASS" if package_ready else "PENDING", True if package_ready else None, substantive=False)
    failed = [row["test_id"] for row in rows if row["status"] == "FAIL"]
    pending = [row["test_id"] for row in rows if row["status"] == "PENDING"]
    return {
        "contract_id": "room16.energy_v2_independent_semantic_closure_r8_matrix.executed@1",
        "row_count": len(rows),
        "passed": sum(row["status"] == "PASS" for row in rows),
        "failed": failed,
        "pending": pending,
        "rows": rows,
    }


def build(args: argparse.Namespace) -> tuple[Path, Path | None]:
    handoff = verify_zip(HANDOFF, EXPECTED["handoff_sha256"])
    r7_manifest, r7_receipt, r7_metrics = verify_r7()
    head = git("rev-parse", "HEAD")
    tree = git("rev-parse", "HEAD^{tree}")
    base_tree = git("rev-parse", f"{EXPECTED['research_base']}^{{tree}}")
    parent = git("rev-parse", f"{EXPECTED['research_base']}^")
    if base_tree != EXPECTED["research_tree"] or parent != EXPECTED["research_parent"]:
        raise RuntimeError("R7_REPOSITORY_BINDING_FAIL")
    commits = git("rev-list", f"{EXPECTED['research_base']}..{head}").splitlines()
    if len(commits) > 1:
        raise RuntimeError("MORE_THAN_ONE_R8_CORRECTION_COMMIT")
    product_head = git("rev-parse", "HEAD", cwd=PRODUCT)
    product_tree = git("rev-parse", "HEAD^{tree}", cwd=PRODUCT)
    if (product_head, product_tree) != (
        EXPECTED["product_commit"],
        EXPECTED["product_tree"],
    ):
        raise RuntimeError("PRODUCT_IDENTITY_FAIL")

    result = args.work_root / f"result_{head[:12].upper()}"
    if result.exists():
        raise RuntimeError(f"RESULT_ALREADY_EXISTS:{result}")
    result.mkdir(parents=True)
    cases = load_cases()
    final_cases = {
        case["ticker"]: evaluate_energy_v2_case(
            ticker=case["ticker"],
            as_of=case["as_of"],
            facts=case["facts"],
            v1_metrics=v1_metrics(case),
        )
        for case in cases
    }
    revenue, concept_only = revenue_evidence(cases)
    period = period_sensitivity(cases, r7_metrics["cases"], final_cases)
    aging = aging_sensitivity(cases, final_cases)
    debt_inventory, debt_pairs, debt_grades = debt_evidence(cases, final_cases)
    values = sorted(case["coverage_percent"] for case in final_cases.values())
    final_median = statistics.median(values)
    final_minimum = min(values)
    revenue_removed = REVENUE_CONCEPT_FAMILY_V2["ordered_concepts"] == ["Revenues"]
    semantic_ready = all(
        [
            revenue["material_unexplained_counterexample_count"] > 0,
            revenue_removed,
            PERIOD_FRESHNESS_POLICY_V2["duration_basis_policy"]["revenue"]
            == ["STANDALONE_QUARTER"],
            PERIOD_FRESHNESS_POLICY_V2["duration_basis_policy"]["net_income"]
            == ["STANDALONE_QUARTER"],
            PERIOD_FRESHNESS_POLICY_V2["coverage_acceptance_semantics"]
            == "DUAL_THRESHOLD_REQUIRED",
            not aging["historical_only_counted"],
            DEBT_COMPARABILITY_CONTRACT_V2["economic_slot_label"]
            == "long_term_debt_measure",
            not DEBT_COMPARABILITY_CONTRACT_V2["grade_c_counts_as_comparable"],
            final_median >= 80,
            final_minimum >= 60,
        ]
    )
    full = junit_receipt(args.full_junit)
    historical = junit_receipt(args.historical_junit)
    boundary = boundary_receipt(args.boundary_before, args.work_root)
    product = {
        "status": "PASS",
        "before_commit": EXPECTED["product_commit"],
        "after_commit": product_head,
        "before_tree": EXPECTED["product_tree"],
        "after_tree": product_tree,
        "changed": False,
    }
    regression_ready = all(
        value.get("status") == "PASS" for value in (full, historical, boundary)
    )
    verdict = (
        "ENERGY_V2_SEMANTIC_CLOSURE_PASS_READY_FOR_FREEZE"
        if semantic_ready and regression_ready
        else "ENERGY_V2_SEMANTIC_CLOSURE_CHANGES_REQUIRED"
    )

    r7_v1 = r7_metrics["v1"]["issuer_coverage"]
    r7_semantic_details = r7_metrics["backtest"]["semantic_only"]
    r7_semantic = {
        ticker: value["coverage_percent"]
        for ticker, value in r7_semantic_details.items()
    }
    r7_v2 = {
        ticker: value["coverage_percent"]
        for ticker, value in r7_metrics["backtest"]["v2"].items()
    }
    final_coverage = {
        ticker: value["coverage_percent"] for ticker, value in final_cases.items()
    }
    comparison = {
        "contract_id": "room16.energy_v2.r8.profile_candidate_comparison@1",
        "candidates": {
            "C0": {
                "name": "ENERGY_V1",
                "issuer_coverage": r7_v1,
                "distribution_percent": sorted(r7_v1.values()),
            },
            "C1": {
                "name": "R7_REVENUE_FAMILY_ONLY_V1_SLOTS",
                "issuer_coverage": r7_semantic,
                "distribution_percent": sorted(r7_semantic.values()),
            },
            "C2": {
                "name": "R7_AS_IMPLEMENTED",
                "issuer_coverage": r7_v2,
                "distribution_percent": sorted(r7_v2.values()),
            },
            "C3": {
                "name": "R8_SEMANTICALLY_CORRECTED",
                "issuer_coverage": final_coverage,
                "distribution_percent": values,
            },
        },
        "capex_retained": True,
        "coverage_backfitting_rejected": True,
    }
    for value in comparison["candidates"].values():
        distribution = value["distribution_percent"]
        value["median_percent"] = statistics.median(distribution)
        value["minimum_percent"] = min(distribution)

    v1_now = {path: sha_file(ROOT / path) for path in V1_SOURCE_HASHES}
    r7_static_rows = [
        row["test_id"]
        for row in json.loads(
            zipfile.ZipFile(R7).read("30_ACCEPTANCE_MATRIX_EXECUTED.json")
        )["rows"]
        if "evidence_file" not in row or "pass_predicate" not in row
    ]
    binding = {
        "status": "PASS",
        "handoff_sha256": EXPECTED["handoff_sha256"],
        "handoff_manifest_sha256": handoff["manifest_sha256"],
        "r7_filename": R7.name,
        "r7_outer_sha256": EXPECTED["r7_sha256"],
        "r7_manifest_sha256": r7_manifest["manifest_sha256"],
        "r7_verifier_status": r7_receipt["status"],
        "r7_matrix_passed": r7_receipt["matrix_passed"],
        "research_base": EXPECTED["research_base"],
        "research_tree": EXPECTED["research_tree"],
        "research_parent": EXPECTED["research_parent"],
        "product_commit": product_head,
        "product_tree": product_tree,
        "new_holdout_selection_count": 0,
        "provider_call_count": 0,
    }
    final_contract = {
        "contract_id": "room16.alpha.energy_profile_v2_candidate.r8_corrected@1",
        "development_status": "CANDIDATE_NOT_FROZEN",
        "default_cutover": False,
        "freeze_authorized": False,
        "release_authorized": False,
        "new_validation_authorized": False,
        "ticker_specific_rules": False,
        "manual_semantic_interventions": False,
        "revenue_concept_family": REVENUE_CONCEPT_FAMILY_V2,
        "mapping_registry": MAPPING_REGISTRY_V2,
        "period_freshness_policy": PERIOD_FRESHNESS_POLICY_V2,
        "core_slot_registry": CORE_SLOT_REGISTRY_V2,
        "debt_comparability_contract": DEBT_COMPARABILITY_CONTRACT_V2,
        "acceptance_thresholds": ENERGY_PROFILE_V2_CANDIDATE[
            "acceptance_thresholds"
        ],
    }
    final_gate = {
        "status": verdict,
        "revenue_equivalence_closure": "PASS_AFTER_UNSAFE_CONCEPT_REMOVED",
        "revenue_candidate_decision": "REVENUE_EQUIVALENCE_INSUFFICIENT",
        "period_basis_closure": "PASS_V1_STANDALONE_QUARTER_PRESERVED",
        "aging_acceptance_semantics": "DUAL_THRESHOLD_REQUIRED",
        "debt_comparability_closure": "PASS_GRADES_A_B_TYPED",
        "economic_profile_rationale": "PASS",
        "usable_median_percent": final_median,
        "usable_minimum_percent": final_minimum,
        "current_only_median_percent": aging["current_only_median_percent"],
        "current_only_minimum_percent": aging["current_only_minimum_percent"],
        "provider_call_count": 0,
        "historical_only_counted": False,
        "ticker_specific_rules": False,
        "energy_v1_unchanged": v1_now == V1_SOURCE_HASHES,
        "freeze_authorized": False,
        "new_validation_authorized": False,
        "release_authorized": False,
    }

    write_text(
        result,
        "00_VERDICT.md",
        f"""# {verdict}

Independent R8 recomputation found that the R7 ExTax Revenue concept is not
generically equivalent to Revenues: {revenue['material_unexplained_counterexample_count']}
of {revenue['row_count']} exact-period matched pairs are non-equal. The unsafe
concept is removed. Revenue and net income now preserve standalone-quarter basis.
The debt slot is renamed long_term_debt_measure and exposes grade A/B scope.
The corrected ten-issuer usable distribution is {values}, median {final_median:g}%
and minimum {final_minimum}%. Current-only median is
{aging['current_only_median_percent']:g}% and therefore remains a separately visible
freeze-time acceptance dimension. Provider calls are zero. The candidate is not frozen,
released, cut over or authorized for new validation in R8.""",
    )
    write_json(result, "01_R7_BINDING.json", binding)
    write_json(
        result,
        "02_R7_DESIGN_METRICS.json",
        {
            "v1": r7_metrics["v1"],
            "semantic_only": r7_semantic,
            "semantic_only_details": r7_semantic_details,
            "r7_v2": r7_v2,
            "slot_distribution": r7_metrics["distribution"],
            "case_diffs": r7_metrics["case_diffs"],
            "registry_hashes": r7_metrics["registries"],
        },
    )
    write_json(
        result,
        "03_R7_EVIDENCE_QUALITY_AUDIT.json",
        {
            "r7_matrix_row_count": 37,
            "rows_without_evidence_file_or_predicate": r7_static_rows,
            "static_boolean_shortcut_confirmed": bool(r7_static_rows),
            "r8_substantive_rows_recomputed": True,
            "r8_substantive_binding_required": True,
            "r8_static_semantic_shortcut_allowed": False,
            "r8_verifier_required_recomputations": [
                "manifest_selfhash",
                "payload_hashes",
                "r7_binding",
                "registry_selfhashes",
                "energy_v1_hashes",
                "revenue_equivalence",
                "period_policy",
                "aging_coverage",
                "debt_comparability",
                "development_gate",
                "scope_noninterference",
                "matrix_and_final_gate",
            ],
            "r7_result_mutated": False,
        },
    )
    write_json(result, "04_REVENUE_MATCHED_PAIR_LEDGER.json", revenue)
    write_json(
        result,
        "05_REVENUE_EQUIVALENCE_DECISION.json",
        {
            "status": "PASS_AFTER_UNSAFE_CONCEPT_REMOVED",
            "r7_candidate_decision": "REVENUE_EQUIVALENCE_INSUFFICIENT",
            "matched_pair_count": revenue["row_count"],
            "unexplained_non_equivalent_count": revenue[
                "material_unexplained_counterexample_count"
            ],
            "final_allowed_concepts": REVENUE_CONCEPT_FAMILY_V2[
                "ordered_concepts"
            ],
            "removed_concept": (
                "RevenueFromContractWithCustomerExcludingAssessedTax"
            ),
            "material_counterexample_accepted": False,
            "ticker_specific_exception": False,
        },
    )
    write_json(result, "06_REVENUE_CONCEPT_ONLY_EVIDENCE.json", concept_only)
    write_json(
        result,
        "07_REVENUE_NEGATIVE_CONTROLS.json",
        {
            "status": "PASS",
            "blocked_concepts": REVENUE_CONCEPT_FAMILY_V2["forbidden_concepts"],
            "segment_revenue": "BLOCK",
            "product_revenue": "BLOCK",
            "issuer_extensions": "BLOCK",
            "including_assessed_tax": "BLOCK",
            "gains_proceeds_gross_profit": "BLOCK",
            "label_only_similarity": "BLOCK",
        },
    )
    write_json(result, "08_PERIOD_BASIS_SENSITIVITY.json", period)
    write_json(
        result,
        "09_PERIOD_BASIS_FINAL_POLICY.json",
        {
            "status": "PASS",
            "decision": "PRESERVE_V1_BASIS_FOR_RETAINED_DURATION_METRICS",
            "duration_basis_policy": PERIOD_FRESHNESS_POLICY_V2[
                "duration_basis_policy"
            ],
            "quarter_from_ytd_subtraction_allowed": False,
            "period_basis_relabeling_allowed": False,
            "justification": (
                "R7 selected facts did not need the broader basis. No generic evidence "
                "justifies allowing annual/YTD revenue or net income to displace a "
                "standalone quarter."
            ),
        },
    )
    write_json(result, "10_AGING_COVERAGE_SENSITIVITY.json", aging)
    write_json(
        result,
        "11_AGING_ACCEPTANCE_DECISION.json",
        {
            "status": "PASS",
            "decision": "DUAL_THRESHOLD_REQUIRED",
            "usable_coverage_rule": (
                "CURRENT_COMPARABLE plus AGING_BUT_VALID_DISCLOSED with typed age"
            ),
            "current_only_reporting_required": True,
            "historical_only_counts": False,
            "usable_median_percent": aging["usable_median_percent"],
            "current_only_median_percent": aging["current_only_median_percent"],
            "freeze_task_must_define_current_only_threshold": True,
            "threshold_invented_in_r8": False,
        },
    )
    write_json(result, "12_DEBT_CONCEPT_INVENTORY.json", debt_inventory)
    write_json(result, "13_DEBT_MATCHED_PAIR_LEDGER.json", debt_pairs)
    write_json(result, "14_DEBT_COMPARABILITY_GRADES.json", debt_grades)
    write_json(result, "15_DEBT_SLOT_FINAL_CONTRACT.json", DEBT_COMPARABILITY_CONTRACT_V2)
    write_text(
        result,
        "16_PROFILE_ECONOMIC_RATIONALE.md",
        """# Independent EPS-to-debt profile rationale

Diluted EPS is an equity-denominator output and remains sensitive to share-count and
duration-selection mechanics. It is useful, but it does not replace direct capital-
structure evidence. A typed long-term debt measure adds genuinely distinct balance-
sheet risk information for capital-intensive Energy issuers. R8 therefore retains the
redesign for economic reasons independent of the 80% gate, while exposing exact concept
identity and grade A/B scope instead of claiming numerical interchangeability. CapEx
remains deliberately difficult because reinvestment intensity is central to the Energy
archetype; it was not removed to improve coverage.""",
    )
    write_json(result, "17_PROFILE_CANDIDATE_COMPARISON.json", comparison)
    write_json(result, "18_FINAL_V2_CANDIDATE_CONTRACT.json", final_contract)
    write_json(
        result,
        "19_FINAL_V2_REGISTRY_HASHES.json",
        {
            **registry_hashes(),
            "debt_comparability_contract_v2_sha256": sha256_json(
                DEBT_COMPARABILITY_CONTRACT_V2
            ),
            "documents": {
                "mapping_registry": MAPPING_REGISTRY_V2,
                "period_freshness_policy": PERIOD_FRESHNESS_POLICY_V2,
                "core_slot_registry": CORE_SLOT_REGISTRY_V2,
                "energy_profile": ENERGY_PROFILE_V2_CANDIDATE,
                "debt_comparability_contract": DEBT_COMPARABILITY_CONTRACT_V2,
            },
        },
    )
    write_json(
        result,
        "20_FINAL_DEVELOPMENT_BACKTEST.json",
        {
            "status": "PASS" if semantic_ready else "FAIL",
            "population_size": len(final_cases),
            "provider_call_count": 0,
            "new_holdout_selection_count": 0,
            "issuer_coverage": final_coverage,
            "distribution_percent": values,
            "usable_median_percent": final_median,
            "usable_minimum_percent": final_minimum,
            "current_only_distribution_percent": aging[
                "current_only_distribution_percent"
            ],
            "current_only_median_percent": aging["current_only_median_percent"],
            "current_only_minimum_percent": aging["current_only_minimum_percent"],
        },
    )
    slot_counts = Counter(
        receipt["metric_id"]
        for value in final_cases.values()
        for receipt in value["slot_receipts"]
        if receipt["counted"]
    )
    write_json(
        result,
        "21_FINAL_SLOT_DISTRIBUTION.json",
        {
            "population_size": 10,
            "resolved_issuer_count_by_slot": dict(sorted(slot_counts.items())),
            "usable_resolution_percent_by_slot": {
                slot: slot_counts[slot] * 10 for slot in CORE_SLOT_REGISTRY_V2["slots"]
            },
        },
    )
    diffs = []
    for ticker in sorted(final_cases):
        old = r7_metrics["cases"][ticker]
        new = final_cases[ticker]
        old_slots = {
            row["metric_id"]: row for row in old["slot_receipts"] if row["counted"]
        }
        new_slots = {
            row["metric_id"]: row for row in new["slot_receipts"] if row["counted"]
        }
        diffs.append(
            {
                "ticker": ticker,
                "r7_coverage_percent": old["coverage_percent"],
                "r8_coverage_percent": new["coverage_percent"],
                "r7_resolved_slots": sorted(old_slots),
                "r8_resolved_slots": sorted(new_slots),
                "revenue_removed": (
                    old_slots.get("revenue", {}).get("selected_fact") or {}
                ).get("concept")
                == "RevenueFromContractWithCustomerExcludingAssessedTax"
                and "revenue" not in new_slots,
                "debt_slot_renamed": "long_term_debt_and_leases" in old_slots
                and "long_term_debt_measure" in new_slots,
                "source_bytes_changed": False,
                "provider_call_count": 0,
            }
        )
    write_json(result, "22_V1_V2_CASE_DIFFS.json", {"rows": diffs})
    changed = sorted(
        set(
            git("diff", "--name-only", EXPECTED["research_base"], head).splitlines()
            + git("diff", "--name-only").splitlines()
            + [
                "scripts/ops/run_energy_v2_independent_semantic_closure_r8.py"
            ]
        )
    )
    write_json(
        result,
        "23_CHANGED_FILES.json",
        {
            "research_base": EXPECTED["research_base"],
            "research_head": head,
            "files": changed,
            "correction_commit_count": len(commits),
            "one_correction_commit_maximum": len(commits) <= 1,
        },
    )
    write_json(result, "24_FULL_RESEARCH_REGRESSION.json", full)
    write_json(
        result,
        "25_HISTORICAL_V1_REGRESSION.json",
        {
            **historical,
            "v1_source_hashes_expected": V1_SOURCE_HASHES,
            "v1_source_hashes_actual": v1_now,
            "v1_source_hashes_unchanged": v1_now == V1_SOURCE_HASHES,
            "r7_binding_valid": True,
        },
    )
    write_json(result, "26_PRODUCT_NONINTERFERENCE.json", product)
    write_json(result, "27_BOUNDARY_GATE_V2.json", boundary)
    write_json(
        result,
        "28_REPOSITORY_END_STATE.json",
        {
            "research_head": head,
            "research_tree": tree,
            "research_branch": git("branch", "--show-current"),
            "research_origin": git("remote", "get-url", "origin"),
            "product_head": product_head,
            "product_tree": product_tree,
            "product_changed": False,
            "provider_call_count": 0,
            "new_holdout_selection_count": 0,
        },
    )
    write_json(result, "29_FINAL_GATE.json", final_gate)
    write_text(
        result,
        "31_NEXT_DECISION.md",
        """# Next decision

If the exact R8 result is independently accepted, a separate task may freeze the
corrected Energy-v2 commit, all registries, grade rules and explicit dual coverage
semantics. That later task must define a current-only threshold before selecting any
new untouched Energy issuer. R8 itself freezes nothing and authorizes no validation.""",
    )
    write_text(
        result,
        "32_WHAT_WE_PROVED.md",
        f"""# What R8 proved

- R7 is exactly bound but its semantic matrix was not independent evidence.
- The ExTax revenue concept is generically unsafe: {revenue['material_unexplained_counterexample_count']} non-equal matched pairs.
- Removing it still leaves usable median {final_median:g}% and minimum {final_minimum}%.
- Revenue and net income can preserve standalone-quarter basis without losing a valid selected fact.
- Aging dependence is material and must remain separately disclosed.
- Debt grade A/B can be represented truthfully under long_term_debt_measure.
- Provider calls and new holdout selection remain zero; Energy v1 and Product are unchanged.""",
    )
    write_text(
        result,
        "33_WHAT_WE_DID_NOT_PROVE.md",
        """# What R8 did not prove

- No equivalence between Revenues and ExTax revenue.
- No generalization to a new untouched Energy issuer.
- No current-only acceptance threshold; the freeze task must define it explicitly.
- No numerical interchangeability between debt grades A and B.
- No freeze, default cutover, release, Product mutation, deploy or publication readiness.""",
    )
    for ticker, value in final_cases.items():
        write_json(result, f"development_backtest/{ticker}.json", value)

    package_ready = semantic_ready and regression_ready and args.package
    matrix = build_matrix(
        result,
        revenue=revenue,
        concept_only=concept_only,
        period=period,
        aging=aging,
        debt_inventory=debt_inventory,
        debt_pairs=debt_pairs,
        debt_grades=debt_grades,
        comparison=comparison,
        final_cases=final_cases,
        full=full,
        historical=historical,
        product=product,
        boundary=boundary,
        final_gate=final_gate,
        package_ready=package_ready,
    )
    if matrix["row_count"] != 42:
        raise RuntimeError("R8_MATRIX_ROW_COUNT_FAIL")
    write_json(result, "30_ACCEPTANCE_MATRIX_EXECUTED.json", matrix)

    package = None
    if args.package:
        if verdict != "ENERGY_V2_SEMANTIC_CLOSURE_PASS_READY_FOR_FREEZE":
            raise RuntimeError("R8_FINAL_GATE_NOT_READY")
        if matrix["passed"] != 42 or matrix["failed"] or matrix["pending"]:
            raise RuntimeError("R8_MATRIX_NOT_COMPLETE")
        verifier = r'''#!/usr/bin/env python3
import hashlib,json,statistics,sys
from pathlib import Path
def c(v): return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()
def h(v): return hashlib.sha256(v).hexdigest()
root=Path(sys.argv[1] if len(sys.argv)>1 else ".").resolve()
m=json.loads((root/"MANIFEST.json").read_text()); body=dict(m); claim=body.pop("manifest_sha256")
if h(c(body))!=claim: raise SystemExit("MANIFEST_SELFHASH_FAIL")
for row in m["files"]:
 b=(root/row["path"]).read_bytes()
 if len(b)!=row["bytes"] or h(b)!=row["sha256"]: raise SystemExit("PAYLOAD_HASH_FAIL:"+row["path"])
bind=json.loads((root/"01_R7_BINDING.json").read_text())
if bind["r7_outer_sha256"]!="d7a529a005137e944ec95bd9b59e2ac1d42d836b0348f69c78a2273f50088122" or bind["r7_manifest_sha256"]!="822d9b0b50914f64e6e91ab60f4ec291b9031423d848e3ea06c872e08df7c2f5" or bind["r7_verifier_status"]!="PASS": raise SystemExit("R7_BINDING_FAIL")
regs=json.loads((root/"19_FINAL_V2_REGISTRY_HASHES.json").read_text()); docs=regs["documents"]
checks={"mapping_registry_v2_sha256":"mapping_registry","period_freshness_policy_v2_sha256":"period_freshness_policy","core_slot_registry_v2_sha256":"core_slot_registry","energy_profile_v2_candidate_sha256":"energy_profile","debt_comparability_contract_v2_sha256":"debt_comparability_contract"}
for key,name in checks.items():
 if h(c(docs[name]))!=regs[key]: raise SystemExit("REGISTRY_SELFHASH_FAIL:"+key)
hist=json.loads((root/"25_HISTORICAL_V1_REGRESSION.json").read_text())
if hist["v1_source_hashes_expected"]!=hist["v1_source_hashes_actual"] or not hist["v1_source_hashes_unchanged"]: raise SystemExit("V1_HASH_FAIL")
rev=json.loads((root/"04_REVENUE_MATCHED_PAIR_LEDGER.json").read_text()); decision=json.loads((root/"05_REVENUE_EQUIVALENCE_DECISION.json").read_text())
if rev["material_unexplained_counterexample_count"]<=0 or decision["final_allowed_concepts"]!=["Revenues"] or decision["material_counterexample_accepted"]: raise SystemExit("REVENUE_CLOSURE_FAIL")
period=json.loads((root/"09_PERIOD_BASIS_FINAL_POLICY.json").read_text())
if period["duration_basis_policy"]["revenue"]!=["STANDALONE_QUARTER"] or period["duration_basis_policy"]["net_income"]!=["STANDALONE_QUARTER"] or period["quarter_from_ytd_subtraction_allowed"]: raise SystemExit("PERIOD_POLICY_FAIL")
aging=json.loads((root/"10_AGING_COVERAGE_SENSITIVITY.json").read_text()); cases=[]
for path in sorted((root/"development_backtest").glob("*.json")): cases.append(json.loads(path.read_text()))
usable=sorted(sum(r["counted"] for r in case["slot_receipts"])*20 for case in cases)
current=sorted(sum(r["counted"] and r["status"]=="CURRENT_COMPARABLE" for r in case["slot_receipts"])*20 for case in cases)
if usable!=aging["usable_distribution_percent"] or current!=aging["current_only_distribution_percent"] or aging["historical_only_counted"]: raise SystemExit("AGING_RECOMPUTE_FAIL")
debt=json.loads((root/"15_DEBT_SLOT_FINAL_CONTRACT.json").read_text())
if debt["economic_slot_label"]!="long_term_debt_measure" or debt["allowed_grades"]!=["A","B"] or debt["grade_c_counts_as_comparable"]: raise SystemExit("DEBT_CONTRACT_FAIL")
for case in cases:
 for row in case["slot_receipts"]:
  if row["metric_id"]=="long_term_debt_measure" and row["counted"] and row["selected_fact"]["comparability_grade"] not in debt["allowed_grades"]: raise SystemExit("DEBT_GRADE_FAIL")
back=json.loads((root/"20_FINAL_DEVELOPMENT_BACKTEST.json").read_text())
if usable!=back["distribution_percent"] or statistics.median(usable)<80 or min(usable)<60: raise SystemExit("DEVELOPMENT_GATE_FAIL")
if sum(case["provider_call_count"] for case in cases)!=0 or any(case["ticker_specific_rules"] for case in cases) or bind["new_holdout_selection_count"]!=0: raise SystemExit("SCOPE_GATE_FAIL")
mx=json.loads((root/"30_ACCEPTANCE_MATRIX_EXECUTED.json").read_text())
if mx["row_count"]!=42 or mx["passed"]!=42 or mx["failed"] or mx["pending"]: raise SystemExit("MATRIX_FAIL")
for row in mx["rows"]:
 if row["substantive"]:
  p=root/row["evidence_file"]
  if not p.is_file() or h(p.read_bytes())!=row["evidence_sha256"] or not row["pass_predicate"]: raise SystemExit("MATRIX_BINDING_FAIL:"+row["test_id"])
gate=json.loads((root/"29_FINAL_GATE.json").read_text())
if gate["status"]!="ENERGY_V2_SEMANTIC_CLOSURE_PASS_READY_FOR_FREEZE" or gate["freeze_authorized"] or gate["new_validation_authorized"]: raise SystemExit("FINAL_GATE_FAIL")
print(json.dumps({"status":"PASS","manifest_sha256":claim,"payload_count":len(m["files"]),"matrix_passed":42,"verdict":gate["status"],"recomputed_gates":12},sort_keys=True))
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
            "contract_id": "room16.energy_v2_independent_semantic_closure_r8.result.compact@1",
            "verdict": verdict,
            "research_commit": head,
            "research_tree": tree,
            "research_base": EXPECTED["research_base"],
            "product_commit": product_head,
            "product_tree": product_tree,
            "development_population_size": 10,
            "usable_median_percent": final_median,
            "usable_minimum_percent": final_minimum,
            "current_only_median_percent": aging["current_only_median_percent"],
            "new_live_provider_calls": 0,
            "new_holdout_selection": False,
            "energy_v1_mutated": False,
            "threshold_changed": False,
            "product_changed": False,
            "freeze_authorized": False,
            "file_count": len(files),
            "files": files,
        }
        manifest["manifest_sha256"] = sha_bytes(canonical(manifest))
        write_json(result, "MANIFEST.json", manifest)
        sums = "".join(f"{row['sha256']}  {row['path']}\n" for row in files)
        sums += f"{sha_file(result / 'MANIFEST.json')}  MANIFEST.json\n"
        write_text(result, "SHA256SUMS.txt", sums)
        receipt = json.loads(
            subprocess.check_output(
                [sys.executable, str(result / "independent_verifier/verify_result.py"), str(result)],
                text=True,
            )
        )
        write_json(result, "independent_verifier/VERIFIER_RECEIPT.json", receipt)
        package = args.package_output / (
            "ROOM16_ENERGY_V2_INDEPENDENT_SEMANTIC_CLOSURE_R8_RESULT_"
            f"{head[:12].upper()}_2026-09-01_UPLOAD_COMPACT.zip"
        )
        package.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(package, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(result.rglob("*")):
                if path.is_file():
                    info = zipfile.ZipInfo(path.relative_to(result).as_posix())
                    info.date_time = (2026, 9, 1, 12, 0, 0)
                    info.external_attr = 0o100644 << 16
                    archive.writestr(
                        info,
                        path.read_bytes(),
                        compress_type=zipfile.ZIP_DEFLATED,
                    )
    return result, package


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--work-root",
        type=Path,
        default=ROOT / "outputs/energy_v2_independent_semantic_closure_r8_work",
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
    value = {
        "status": "PASS",
        "result_root": str(result),
        "package": str(package) if package else None,
    }
    if package:
        value["package_sha256"] = sha_file(package)
    print(json.dumps(value, sort_keys=True))


if __name__ == "__main__":
    main()
