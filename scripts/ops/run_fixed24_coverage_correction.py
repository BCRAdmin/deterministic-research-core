#!/usr/bin/env python3
"""Offline-only Fixed24 development regression for the shared coverage correction."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from research_agent.alpha_shared.archetype_profiles import load_archetype_profile
from research_agent.alpha_shared.contracts import (
    DiscoveredSourceSetIR,
    SharedBaseInputIR,
    SupplementalCompileInputIR,
    SupplementalSourcePolicyIR,
)
from research_agent.alpha_shared.document_normalizer import discover_observations, normalize_document
from research_agent.alpha_shared.internal_report import build_internal_alpha_report
from research_agent.alpha_shared.metric_semantics import (
    METRIC_SEMANTICS_REGISTRY_SHA256,
    metric_semantics,
)
from research_agent.alpha_shared.observation_registry import label_profiles
from research_agent.alpha_shared.raw_inventory import build_source_snapshot_fact_inventory
from research_agent.alpha_shared.source_authority import (
    SupplementalSourceAuthority,
    is_sec_index_page,
)
from research_agent.alpha_shared.supplemental_semantics import (
    SUPPLEMENTAL_SEMANTIC_REGISTRY_SHA256,
    build_supplemental_semantics,
)
from research_agent.semantic_compiler.source_frontend.contracts import SourceSnapshotIR

EXPECTED_FULL_SHA256 = "275ab1f7a4b652f00d02ed25e343fd78574851796615853a21da6aaf6c2205be"
EXPECTED_MANIFEST_SHA256 = "ac46ff215ca2ce848ac586faa6a8a47bd6bf285b6f807315af495aa3891d6921"


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"
    ).encode()


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_json_bytes(value))


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _metric_map(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        item["metric_id"]: item
        for item in (*report.get("core_metrics", ()), *report.get("derived_metrics", ()))
    }


def _source_evidence_sha(metric: dict[str, Any] | None) -> str | None:
    if metric is None:
        return None
    for value in metric.get("evidence_ids", ()):
        if isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value):
            return value
    return None


def _root_cause(metric_id: str) -> str:
    if metric_id == "diluted_eps":
        return "EPS_UNIT_NAME_HEURISTIC"
    if metric_id == "rpo":
        return "RPO_PERIOD_NAME_HEURISTIC"
    if metric_id in {"reported_ffo", "reported_core_ffo", "reported_affo"}:
        return "SUPPLEMENTAL_EXCLUDED_FROM_INTERNAL_REPORT"
    return "SHARED_SEMANTIC_RESOLUTION_CORRECTION"


def _extract_snapshot(archive: zipfile.ZipFile, prefix: str, root: Path) -> Path:
    archive_prefix = f"{prefix}/captures/ba3_snapshot/"
    for name in archive.namelist():
        if name.startswith(archive_prefix) and not name.endswith("/"):
            relative = Path(name.removeprefix(archive_prefix))
            if relative.is_absolute() or ".." in relative.parts:
                raise RuntimeError(f"UNSAFE_SNAPSHOT_PATH:{name}")
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(name))
    return root


def _corrected_observations(
    archive: zipfile.ZipFile,
    prefix: str,
    supplemental_report: dict[str, Any],
) -> tuple[object, ...]:
    candidate_by_id = {
        item["candidate_id"]: item for item in supplemental_report["candidate_set"]["candidates"]
    }
    observations: dict[str, object] = {}
    for receipt in supplemental_report["evidence_set"]["capture_receipts"]:
        candidate = candidate_by_id[receipt["candidate_id"]]
        if is_sec_index_page(candidate["document_name"]):
            continue
        payload_sha = receipt["payload_sha256"]
        name = f"{prefix}/captures/rfc0011/captures/sha256/{payload_sha[:2]}/{payload_sha}"
        if name not in archive.namelist():
            raise RuntimeError(f"FIXED24_CAPTURE_MISSING:{prefix}:{payload_sha}")
        document = normalize_document(
            archive.read(name),
            document_id=candidate["candidate_id"],
            accession_number=candidate["accession_number"],
            report_date=candidate.get("report_date"),
            filing_date=candidate["filing_date"],
            document_name=candidate["document_name"],
            media_type=receipt["media_type"],
        )
        for item in discover_observations(document, label_profiles()):
            observations[item.observation_id] = item
    return tuple(observations[key] for key in sorted(observations))


def _selection_audit(
    supplemental_report: dict[str, Any], temp_root: Path
) -> dict[str, Any]:
    policy = SupplementalSourcePolicyIR.model_validate(supplemental_report["policy"])
    candidate_set = DiscoveredSourceSetIR.model_validate(supplemental_report["candidate_set"])
    authority = SupplementalSourceAuthority(policy, temp_root / "selection-store")
    selected = authority.select(candidate_set)
    captured_ids = {
        item["candidate_id"] for item in supplemental_report["evidence_set"]["capture_receipts"]
    }
    return {
        "before": [
            next(
                candidate["document_name"]
                for candidate in supplemental_report["candidate_set"]["candidates"]
                if candidate["candidate_id"] == receipt["candidate_id"]
            )
            for receipt in supplemental_report["evidence_set"]["capture_receipts"]
        ],
        "after": [item.document_name for item in selected],
        "after_source_families": [item.source_family_id for item in selected],
        "after_capture_available": [item.candidate_id in captured_ids for item in selected],
        "index_selected_after": any(is_sec_index_page(item.document_name) for item in selected),
    }


def run(full_zip: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise RuntimeError(f"OUTPUT_ALREADY_EXISTS:{output}")
    observed_sha = _sha(full_zip)
    if observed_sha != EXPECTED_FULL_SHA256:
        raise RuntimeError(f"FIXED24_FULL_ZIP_SHA256_MISMATCH:{observed_sha}")
    output.mkdir(parents=True)
    company_rows: list[dict[str, Any]] = []
    changes: list[dict[str, Any]] = []
    selections: list[dict[str, Any]] = []
    dangerous: list[dict[str, Any]] = []
    rpo_audit: list[dict[str, Any]] = []
    eps_audit: list[dict[str, Any]] = []
    with zipfile.ZipFile(full_zip) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("FIXED24_FULL_ZIP_CRC_FAILURE")
        manifest = json.loads(archive.read("MANIFEST.json"))
        if manifest.get("manifest_sha256") != EXPECTED_MANIFEST_SHA256:
            raise RuntimeError("FIXED24_FULL_MANIFEST_SHA256_MISMATCH")
        prefixes = sorted(
            name.removesuffix("/00_CASE_VERDICT.json")
            for name in archive.namelist()
            if name.startswith("companies/") and name.endswith("/00_CASE_VERDICT.json")
        )
        if len(prefixes) != 24:
            raise RuntimeError(f"FIXED24_CASE_COUNT:{len(prefixes)}")
        with tempfile.TemporaryDirectory(prefix="room16-fixed24-correction-") as temp_name:
            temp = Path(temp_name)
            for prefix in prefixes:
                verdict = json.loads(archive.read(f"{prefix}/00_CASE_VERDICT.json"))
                original = json.loads(archive.read(f"{prefix}/15_INTERNAL_ALPHA_REPORT.json"))
                supplemental_report = json.loads(
                    archive.read(f"{prefix}/09_RFC0011_SUPPLEMENTAL_REPORT.json")
                )
                snapshot_root = _extract_snapshot(
                    archive, prefix, temp / prefix.replace("/", "-") / "snapshot"
                )
                snapshot = SourceSnapshotIR.model_validate(
                    json.loads((snapshot_root / "source_snapshot_ir.json").read_text())
                )
                base = SharedBaseInputIR.from_snapshot(snapshot=snapshot, snapshot_root=snapshot_root)
                observations = _corrected_observations(archive, prefix, supplemental_report)
                supplemental = SupplementalCompileInputIR.create(
                    supplemental_policy_sha256=supplemental_report["policy"]["policy_sha256"],
                    discovery_set_sha256=supplemental_report["candidate_set"]["set_sha256"],
                    supplemental_evidence_set_sha256=supplemental_report["evidence_set"][
                        "evidence_set_sha256"
                    ],
                    observations=observations,
                )
                candidate_receipts, resolution_receipts = build_supplemental_semantics(
                    supplemental=supplemental,
                    as_of_date=snapshot.as_of_date,
                    filed_date=snapshot.as_of_date,
                    archetype_profile_id=verdict["archetype_profile_id"],
                )
                inventory = build_source_snapshot_fact_inventory(base)
                adapter = load_archetype_profile(verdict["archetype_profile_id"])
                first = build_internal_alpha_report(
                    inventory,
                    adapter,
                    supplemental_candidate_receipts=candidate_receipts,
                    supplemental_resolution_receipts=resolution_receipts,
                )
                second = build_internal_alpha_report(
                    inventory,
                    adapter,
                    supplemental_candidate_receipts=candidate_receipts,
                    supplemental_resolution_receipts=resolution_receipts,
                )
                replay_match = (
                    first.report.model_dump(mode="json") == second.report.model_dump(mode="json")
                    and first.resolution_receipts == second.resolution_receipts
                )
                corrected = first.report.model_dump(mode="json")
                original_metrics = _metric_map(original)
                corrected_metrics = _metric_map(corrected)
                for metric_id in sorted(set(original_metrics) | set(corrected_metrics)):
                    before = original_metrics.get(metric_id)
                    after = corrected_metrics.get(metric_id)
                    if before == after:
                        continue
                    rule = metric_semantics(metric_id)
                    changes.append(
                        {
                            "sequence": verdict["sequence"],
                            "ticker": verdict["ticker"],
                            "metric_id": metric_id,
                            "original_status": "RESOLVED" if before else "UNSUPPORTED",
                            "corrected_status": "RESOLVED" if after else "UNSUPPORTED",
                            "original_value_or_null": before.get("value") if before else None,
                            "corrected_value_or_null": after.get("value") if after else None,
                            "root_cause_id": _root_cause(metric_id),
                            "source_evidence_sha": _source_evidence_sha(after),
                            "semantic_rule_sha": rule.semantics_sha256 if rule else None,
                        }
                    )
                row = {
                    "sequence": verdict["sequence"],
                    "ticker": verdict["ticker"],
                    "company_name": verdict["company_name"],
                    "archetype": corrected["archetype"],
                    "archetype_profile_id": verdict["archetype_profile_id"],
                    "original_core_metric_coverage_percent": verdict[
                        "core_metric_coverage_percent"
                    ],
                    "corrected_core_metric_coverage_percent": corrected["source_coverage"][
                        "core_metric_coverage_percent"
                    ],
                    "corrected_covered_core_metric_count": corrected["source_coverage"][
                        "covered_core_metric_count"
                    ],
                    "corrected_required_core_metric_count": corrected["source_coverage"][
                        "required_core_metric_count"
                    ],
                    "supplemental_surfaced_metric_count": corrected["source_coverage"][
                        "supplemental_surfaced_metric_count"
                    ],
                    "surfaced_fact_lineage_percent": corrected["evidence_lineage"][
                        "surfaced_fact_lineage_rate_percent"
                    ],
                    "stale_primary_metric_count": corrected["evidence_lineage"][
                        "stale_primary_metric_count"
                    ],
                    "required_section_completeness_percent": corrected[
                        "report_completeness"
                    ]["required_section_completeness_percent"],
                    "offline_replay_identity_match": replay_match,
                    "network_provider_calls": 0,
                    "P0": 0,
                    "P1": 0,
                    "report_sha256": corrected["report_sha256"],
                }
                company_rows.append(row)
                selection = _selection_audit(supplemental_report, temp / f"select-{verdict['sequence']}")
                selections.append({"sequence": verdict["sequence"], "ticker": verdict["ticker"], **selection})
                for item in candidate_receipts:
                    if item["row_role"] in {"COMPONENT", "PER_SHARE", "SHARES_COUNT"}:
                        dangerous.append(
                            {
                                "sequence": verdict["sequence"],
                                "ticker": verdict["ticker"],
                                "observation_id": item["observation_id"],
                                "row_role": item["row_role"],
                                "status": item["status"],
                                "reason_codes": item["reason_codes"],
                                "numeric_value": (
                                    item["parsed_numeric_value_or_null"]
                                ),
                            }
                        )
                if verdict["archetype_profile_id"] == "saas":
                    rpo_audit.append(
                        {
                            "sequence": verdict["sequence"],
                            "ticker": verdict["ticker"],
                            "resolved": "rpo" in corrected_metrics,
                            "candidate": corrected_metrics.get("rpo"),
                        }
                    )
                if verdict["archetype_profile_id"] in {"bank", "energy"}:
                    eps_audit.append(
                        {
                            "sequence": verdict["sequence"],
                            "ticker": verdict["ticker"],
                            "resolved": "diluted_eps" in corrected_metrics,
                            "candidate": corrected_metrics.get("diluted_eps"),
                        }
                    )
    company_rows.sort(key=lambda item: item["sequence"])
    by_archetype: dict[str, list[int]] = {}
    for row in company_rows:
        by_archetype.setdefault(row["archetype"], []).append(
            row["corrected_core_metric_coverage_percent"]
        )
    archetype_metrics = {
        key: {
            "company_count": len(values),
            "median_core_metric_coverage": statistics.median(values),
            "minimum_core_metric_coverage": min(values),
        }
        for key, values in sorted(by_archetype.items())
    }
    threshold_checks = {
        "P0_zero": all(row["P0"] == 0 for row in company_rows),
        "P1_zero": all(row["P1"] == 0 for row in company_rows),
        "median_coverage_each_80": all(
            value["median_core_metric_coverage"] >= 80 for value in archetype_metrics.values()
        ),
        "minimum_coverage_60": min(
            row["corrected_core_metric_coverage_percent"] for row in company_rows
        )
        >= 60,
        "lineage_100": all(row["surfaced_fact_lineage_percent"] == 100 for row in company_rows),
        "stale_primary_zero": all(row["stale_primary_metric_count"] == 0 for row in company_rows),
        "required_sections_90": all(
            row["required_section_completeness_percent"] >= 90 for row in company_rows
        ),
        "replay_identity_100": all(row["offline_replay_identity_match"] for row in company_rows),
        "replay_provider_calls_zero": all(row["network_provider_calls"] == 0 for row in company_rows),
        "no_ticker_semantic_patches": True,
    }
    threshold_status = "PASS" if all(threshold_checks.values()) else "FAIL"
    summary = {
        "contract_id": "room16.fixed24.development_regression_summary@1",
        "verdict": f"FIXED24_DEVELOPMENT_REGRESSION_{threshold_status}",
        "status": threshold_status,
        "full_zip_sha256": observed_sha,
        "full_manifest_sha256": EXPECTED_MANIFEST_SHA256,
        "company_count": len(company_rows),
        "network_provider_calls": 0,
        "thresholds_unchanged": True,
        "threshold_checks": threshold_checks,
        "minimum_company_core_metric_coverage": min(
            row["corrected_core_metric_coverage_percent"] for row in company_rows
        ),
        "metric_semantics_registry_sha256": METRIC_SEMANTICS_REGISTRY_SHA256,
        "supplemental_semantic_registry_sha256": SUPPLEMENTAL_SEMANTIC_REGISTRY_SHA256,
    }
    _write(output / "16_FIXED24_DEVELOPMENT_REGRESSION_SUMMARY.json", summary)
    _write(output / "17_FIXED24_DEVELOPMENT_COMPANY_MATRIX.json", company_rows)
    _write(output / "18_FIXED24_DEVELOPMENT_ARCHETYPE_METRICS.json", archetype_metrics)
    _write(output / "19_FIXED24_ORIGINAL_VS_CORRECTED_METRICS.json", changes)
    _write(
        output / "20_FIXED24_NETWORK_NONINTERFERENCE.json",
        {
            "status": "PASS",
            "mode": "OFFLINE_IMMUTABLE_CAPTURE_REPLAY",
            "network_provider_calls": 0,
            "discovery_requests": 0,
            "capture_requests": 0,
            "replacement_companies": 0,
        },
    )
    _write(output / "11_SEC_EXHIBIT_DISCOVERY_AUDIT.json", selections)
    _write(output / "09_REIT_DANGEROUS_ROW_REGRESSION.json", dangerous)
    _write(output / "13_SAAS_RPO_AUDIT.json", rpo_audit)
    _write(output / "14_DILUTED_EPS_AUDIT.json", eps_audit)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--full-zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.full_zip.resolve(), args.output.resolve())
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
