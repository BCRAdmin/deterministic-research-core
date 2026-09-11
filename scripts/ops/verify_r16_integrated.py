#!/usr/bin/env python3
"""Standalone fail-closed verifier for the Room16 R16 integrated result."""

from __future__ import annotations

import hashlib
import json
import statistics
import sys
import zipfile
from decimal import Decimal
from pathlib import Path, PurePosixPath

SHA256 = __import__("re").compile(r"^[0-9a-f]{64}$")


def canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode()


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def selfhash(value: dict, field: str) -> str:
    claimed = str(value.get(field, ""))
    if not SHA256.fullmatch(claimed) or digest(
        {key: item for key, item in value.items() if key != field}
    ) != claimed:
        raise ValueError(f"SELFHASH:{field}")
    return claimed


def read_json(archive: zipfile.ZipFile, name: str) -> dict:
    value = json.loads(archive.read(name))
    if not isinstance(value, dict):
        raise ValueError(f"JSON_OBJECT_REQUIRED:{name}")
    return value


def validate_candidate(candidate: dict) -> None:
    claimed = str(candidate.get("candidate_sha256", ""))
    if digest({k: v for k, v in candidate.items() if k != "candidate_sha256"}) != claimed:
        raise ValueError("CANDIDATE_HASH")
    identity = digest(
        {
            k: v
            for k, v in candidate.items()
            if k not in {"candidate_id", "candidate_identity_payload_sha256", "candidate_sha256"}
        }
    )
    if (
        candidate.get("candidate_identity_payload_sha256") != identity
        or candidate.get("candidate_id") != f"room16.reit.v4.primary.{identity}"
        or candidate.get("synthetic")
        or candidate.get("ticker_specific_rule")
    ):
        raise ValueError("CANDIDATE_IDENTITY_OR_POLICY")
    reported = Decimal(str(candidate["reported_numeric_value"]))
    multiplier = Decimal(str(candidate["scale_multiplier"]))
    if reported * multiplier != Decimal(str(candidate["numeric_value"])):
        raise ValueError("CANDIDATE_SCALE_ARITHMETIC")
    scale_proof = {
        "locator": candidate["scale_authority_locator"],
        "text": " ".join(str(candidate["scale_authority_text"]).split()),
        "scale": str(candidate["scale"]).lower(),
    }
    if digest(scale_proof) != candidate["scale_authority_sha256"]:
        raise ValueError("CANDIDATE_SCALE_PROOF")
    reconciliation = candidate.get("reconciliation_authority")
    label = str(candidate["reported_label"]).lower()
    explicit = "nareit" in label or "as defined by nareit" in label
    expected_grade = "A" if explicit or reconciliation is not None else "B"
    if candidate["metric_id"] != "reported_ffo":
        expected_grade = "C"
    if candidate["economic_scope_grade"] != expected_grade:
        raise ValueError("CANDIDATE_GRADE")
    if reconciliation is None:
        return
    selfhash(reconciliation, "authority_sha256")
    stages = reconciliation.get("stages")
    target = reconciliation.get("target")
    if not isinstance(stages, list) or not stages or not isinstance(target, dict):
        raise ValueError("RECONCILIATION_SHAPE")
    previous = None
    for index, stage in enumerate(stages):
        base = stage["base"]
        components = stage["components"]
        stage_target = stage["target"]
        if not components:
            raise ValueError("RECONCILIATION_EMPTY_STAGE")
        records = [base, *components, stage_target]
        binding = (
            candidate["period_end"],
            candidate["period_basis"],
            candidate["column_header_sha256"],
        )
        if any(
            (row["period_end"], row["period_basis"], row["column_header_sha256"])
            != binding
            for row in records
        ):
            raise ValueError("RECONCILIATION_BINDING")
        if [row["row_index"] for row in records] != sorted(
            {row["row_index"] for row in records}
        ):
            raise ValueError("RECONCILIATION_ORDER")
        calculated = Decimal(str(base["reported_numeric_value"])) + sum(
            (Decimal(str(row["reported_numeric_value"])) for row in components), Decimal(0)
        )
        if calculated != Decimal(str(stage_target["reported_numeric_value"])):
            raise ValueError("RECONCILIATION_ARITHMETIC")
        if index == 0:
            if (
                stage["stage_type"] != "GAAP_NET_INCOME_TO_FFO"
                or base["role"] != "GAAP_NET_INCOME_OR_LOSS"
                or not any(row["role"] == "DEPRECIATION_OR_AMORTIZATION" for row in components)
            ):
                raise ValueError("RECONCILIATION_GAAP_BASE")
        elif stage["stage_type"] != "FFO_TO_ATTRIBUTABLE_FFO" or base != previous:
            raise ValueError("RECONCILIATION_CHAIN")
        previous = stage_target
    if previous != target or any(
        target[key] != candidate[key]
        for key in (
            "row_locator",
            "value_cell_locator",
            "value_grid_columns",
            "reported_numeric_value",
            "period_end",
            "period_basis",
            "column_header_sha256",
        )
    ):
        raise ValueError("RECONCILIATION_TARGET")


def main() -> int:
    target = Path(sys.argv[1])
    with zipfile.ZipFile(target) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("DUPLICATE_ZIP_MEMBER")
        if any(
            PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts
            for name in names
        ):
            raise ValueError("UNSAFE_ZIP_MEMBER")
        manifest = read_json(archive, "MANIFEST.json")
        selfhash(manifest, "manifest_sha256")
        for row in manifest["files"]:
            if (
                hashlib.sha256(archive.read(row["path"])).hexdigest() != row["sha256"]
                or len(archive.read(row["path"])) != row["bytes"]
            ):
                raise ValueError(f"MANIFEST_PAYLOAD:{row['path']}")
        checksum_lines = archive.read("CHECKSUMS.sha256").decode().splitlines()
        expected_lines = [f"{row['sha256']}  {row['path']}" for row in manifest["files"]]
        expected_lines.append(
            f"{hashlib.sha256(archive.read('MANIFEST.json')).hexdigest()}  MANIFEST.json"
        )
        if checksum_lines != expected_lines:
            raise ValueError("CHECKSUMS")

        identity = read_json(archive, "01_START_AND_FINAL_IDENTITY.json")
        commit = identity["final"]["commit"]
        tree = identity["final"]["tree"]
        if (
            not SHA256.fullmatch(commit)
            or not SHA256.fullmatch(tree)
            or manifest["research_commit"] != commit
            or manifest["research_tree"] != tree
            or identity.get("freeze_authorized") is not False
        ):
            raise ValueError("IDENTITY")
        for name in (
            "03_HERMETIC_TEST_CORRECTION.json",
            "04_HERMETICITY_GUARD_RESULTS.json",
            "05_REMOTE_GITHUB_CI_RECEIPT.json",
            "08_EXPOSED_REPLAY_RESULTS.json",
            "09_REIT_V4_DEVELOPMENT_GATE.json",
            "11_RAW_EVIDENCE_VERIFIER_RECEIPT.json",
            "18_BANK_DEVELOPMENT_GATE.json",
            "19_SAAS_DEVELOPMENT_GATE.json",
            "20_FULL_REGRESSION_AND_NONINTERFERENCE.json",
            "21_ADVERSARIAL_TEST_RESULTS.json",
        ):
            if read_json(archive, name).get("status") != "PASS":
                raise ValueError(f"REQUIRED_PASS:{name}")

        seal = read_json(archive, "10_REIT_V4_CANDIDATE_SEAL.json")
        seal_hash = selfhash(seal, "candidate_seal_sha256")
        if (
            seal["research_commit"] != commit
            or seal["research_tree"] != tree
            or seal.get("freeze_authorized") is not False
        ):
            raise ValueError("CANDIDATE_SEAL")
        contract = read_json(archive, "12_EPOCH3_SELECTION_CONTRACT.json")
        selfhash(contract, "selection_contract_sha256")
        selected_doc = read_json(archive, "13_EPOCH3_SELECTED_CASES_SEALED.json")
        selfhash(selected_doc, "selected_cases_sha256")
        if (
            contract["provider_calls_before_selection_seal"] != 0
            or selected_doc["provider_calls_before_selection_seal"] != 0
            or selected_doc["replacement_authorized"]
            or len(selected_doc["selected"]) != 12
        ):
            raise ValueError("SELECTION_POLICY")
        ranked = sorted(
            contract["eligible"],
            key=lambda row: hashlib.sha256(
                seal_hash.encode()
                + contract["universe_sha256"].encode()
                + canonical(
                    {
                        "ticker": row["ticker"],
                        "cik": row["cik"],
                        "company_name": row["company_name"],
                        "exchange": row["exchange"],
                        "aliases": row.get("aliases", []),
                    }
                )
            ).hexdigest(),
        )[:12]
        if ranked != selected_doc["selected"]:
            raise ValueError("SELECTION_RECOMPUTE")

        case_results = read_json(archive, "15_EPOCH3_CASE_RESULTS.json")["cases"]
        if len(case_results) != 12:
            raise ValueError("CASE_CARDINALITY")
        for index, row in enumerate(selected_doc["selected"], start=1):
            prefix = f"epoch3_cases/{index:02d}_{row['ticker']}/primary_text"
            discovery = read_json(archive, f"{prefix}/DISCOVERED_SOURCE_SET_RECEIPT.json")
            selfhash(discovery, "discovered_source_set_sha256")
            submissions = archive.read(f"{prefix}/captures/sec_submissions/submissions.json")
            if hashlib.sha256(submissions).hexdigest() != discovery["submissions_sha256"]:
                raise ValueError("SUBMISSIONS_HASH")
            candidates = read_json(archive, f"{prefix}/PRIMARY_TEXT_CANDIDATES.json")[
                "candidates"
            ]
            for candidate in candidates:
                validate_candidate(candidate)
                lineage = candidate["source_lineage"]
                matches = [
                    name
                    for name in names
                    if name.startswith(f"{prefix}/captures/sec_documents/")
                    and name.endswith("/" + candidate["document_identity"])
                ]
                if not matches or all(
                    hashlib.sha256(archive.read(name)).hexdigest()
                    != lineage["source_artifact_sha256"]
                    for name in matches
                ):
                    raise ValueError("RAW_DOCUMENT_HASH")
            receipt = read_json(archive, f"{prefix}/FFO_SELECTION_RECEIPT.json")
            if receipt["receipt_sha256"] != digest(
                {key: value for key, value in receipt.items() if key != "receipt_sha256"}
            ):
                raise ValueError("SELECTION_RECEIPT_HASH")

        acceptance = read_json(archive, "16_EPOCH3_BATCH_ACCEPTANCE.json")
        coverage = [row["core_coverage_percent"] for row in case_results]
        recomputed = {
            "case_count_12": len(case_results) == 12,
            "minimum_company_coverage": min(coverage) >= 60,
            "median_coverage": statistics.median(coverage) >= 80,
            "section_completeness": min(
                row["section_completeness_percent"] for row in case_results
            )
            >= 90,
            "lineage": min(row["surfaced_fact_lineage_percent"] for row in case_results)
            == 100,
            "stale_zero": sum(row["stale_primary_metric_count"] for row in case_results) == 0,
            "replay_identity": min(row["replay_identity_percent"] for row in case_results)
            == 100,
            "replay_provider_calls_zero": sum(
                row["replay_provider_calls"] for row in case_results
            )
            == 0,
            "P0_zero": sum(row["P0"] for row in case_results) == 0,
            "P1_zero": sum(row["P1"] for row in case_results) == 0,
            "manual_zero": sum(row["manual_semantic_interventions"] for row in case_results)
            == 0,
            "ticker_patches_zero": sum(
                row["ticker_specific_semantic_patches"] for row in case_results
            )
            == 0,
        }
        if acceptance["checks"] != recomputed or acceptance["status"] != (
            "PASS" if all(recomputed.values()) else "FAIL"
        ):
            raise ValueError("ACCEPTANCE")
        no_tuning = read_json(archive, "17_NO_TUNING_NO_REPLACEMENT_RECEIPT.json")
        if no_tuning["replacements"] or no_tuning["semantic_or_selection_mutations_after_seal"]:
            raise ValueError("NO_TUNING")
        expected = (
            "ROOM16_R16_PASS_READY_FOR_INDEPENDENT_REVIEW"
            if acceptance["status"] == "PASS"
            else "ROOM16_R16_CLEAN_VALIDATION_FAIL_CANDIDATE_NOT_FREEZE_READY"
        )
        if manifest["verdict"] != expected:
            raise ValueError("VERDICT")
    print(
        json.dumps(
            {
                "status": "PASS",
                "verdict": expected,
                "verified_payloads": manifest["file_count"],
                "selected": [row["ticker"] for row in ranked],
                "minimum_coverage": min(coverage),
                "median_coverage": statistics.median(coverage),
                "raw_cases_verified": 12,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
