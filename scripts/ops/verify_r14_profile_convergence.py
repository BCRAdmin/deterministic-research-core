#!/usr/bin/env python3
"""Standalone substantive verifier for the Room16 R14 evidence package."""

from __future__ import annotations

import hashlib
import json
import statistics
import sys
import zipfile
from pathlib import Path


def canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode()


def main() -> int:
    target = Path(sys.argv[1])
    with zipfile.ZipFile(target) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or any(
            name.startswith(("/", "../")) or "/../" in name for name in names
        ):
            raise ValueError("UNSAFE_ZIP")
        manifest = json.loads(archive.read("MANIFEST.json"))
        body = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
        if hashlib.sha256(canonical(body)).hexdigest() != manifest["manifest_sha256"]:
            raise ValueError("MANIFEST_SELFHASH")
        for row in manifest["files"]:
            if hashlib.sha256(archive.read(row["path"])).hexdigest() != row["sha256"]:
                raise ValueError("PAYLOAD_HASH")
        freeze = json.loads(archive.read("02_ENERGY_V3_FREEZE_AUTHORITY.json"))
        freeze_hash = freeze.pop("freeze_authority_sha256")
        if hashlib.sha256(canonical(freeze)).hexdigest() != freeze_hash:
            raise ValueError("FREEZE_SELFHASH")
        if (
            not freeze["immutable"]
            or freeze["product_cutover_authorized"]
            or freeze["release_authorized"]
        ):
            raise ValueError("FREEZE_SCOPE")
        if (
            freeze["independent_freeze_decision_sha256"]
            != "2f2c9a8ede99f195e9484ea3b58eae11ea3b507f6318e8704a5dbf607c82e045"
        ):
            raise ValueError("DECISION_BINDING")
        selection = json.loads(archive.read("16_REIT_SELECTED_CASES_SEALED.json"))
        selected_hash = selection.pop("selected_cases_sha256")
        if (
            hashlib.sha256(canonical(selection)).hexdigest() != selected_hash
            or len(selection["selected"]) != 12
        ):
            raise ValueError("SELECTION_SEAL")
        if (
            len({row["ticker"] for row in selection["selected"]}) != 12
            or selection["provider_calls_before_seal"] != 0
            or selection["replacement_authorized"]
        ):
            raise ValueError("SELECTION_POLICY")
        results = json.loads(archive.read("18_REIT_12_CASE_RESULTS.json"))["cases"]
        if len(results) != 12:
            raise ValueError("RESULT_CARDINALITY")
        coverage = [row["core_coverage_percent"] for row in results]
        recomputed = {
            "minimum_company_coverage": min(coverage) >= 60,
            "median_coverage": statistics.median(coverage) >= 80,
            "lineage": min(row["surfaced_fact_lineage_percent"] for row in results) == 100,
            "stale_zero": sum(row["stale_primary_metric_count"] for row in results) == 0,
            "replay_identity": min(row["replay_identity_percent"] for row in results) == 100,
            "replay_provider_calls_zero": sum(row["replay_provider_calls"] for row in results) == 0,
            "P0_zero": sum(row["P0"] for row in results) == 0,
            "P1_zero": sum(row["P1"] for row in results) == 0,
        }
        acceptance = json.loads(archive.read("19_REIT_BATCH_ACCEPTANCE.json"))
        if not all(recomputed.values()) or acceptance["status"] != "PASS":
            raise ValueError("ACCEPTANCE_RECOMPUTE")
        regression = json.loads(archive.read("21_FULL_REGRESSION.json"))
        if any(
            regression[k]["status"] != "PASS"
            or regression[k]["failures"]
            or regression[k]["errors"]
            or regression[k]["skipped"]
            for k in ("research", "product")
        ):
            raise ValueError("REGRESSION")
        attacks = json.loads(archive.read("22_ACTIVE_ADVERSARIAL_TESTS.json"))
        if attacks["active_attacks"] < 40 or attacks["status"] != "PASS":
            raise ValueError("ADVERSARIAL")
    print(
        json.dumps(
            {
                "status": "PASS",
                "verified_payloads": manifest["file_count"],
                "freeze_authority_sha256": freeze_hash,
                "selected_cases_sha256": selected_hash,
                "recomputed_acceptance": recomputed,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
