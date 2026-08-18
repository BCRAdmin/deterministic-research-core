#!/usr/bin/env python3
"""Build fully re-hashed RFC-0005-R2 adversarial bundle fixtures."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from research_agent.compiler_foundation.canonical import canonical_bytes, sha256_json
from research_agent.productization.trust_receipt import build_receipt_set


SECTION_KINDS = {
    "artifact_hashes": (), "claim_graph": ("claim_graph",),
    "compatibility_state": ("authority_v3_bridge",), "compile_identity": (),
    "compile_verdict": ("compile_verdict",), "compiler_version": (),
    "decision_graph": ("decision_graph",), "diagnostics": ("diagnostics",),
    "evidence_graph": ("evidence_graph",), "formula_evaluations": ("formula_evaluations",),
    "foundation_version": (), "ir_references": (), "metrics": ("metrics",),
    "pass_manifest": (), "registry_lock": ("registry_lock",),
    "source_provenance": ("source_provenance",), "typed_facts": ("typed_facts",),
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.write_bytes(canonical_bytes(value) + b"\n")


def artifact(manifest: dict[str, Any], kind: str) -> dict[str, Any]:
    matches = [item for item in manifest["artifacts"] if item["artifact_kind"] == kind]
    if len(matches) != 1:
        raise ValueError(f"artifact kind {kind} not unique")
    return matches[0]


def payload(root: Path, manifest: dict[str, Any], kind: str) -> Any:
    return read_json(root / artifact(manifest, kind)["relative_path"])


def mutate(root: Path, manifest: dict[str, Any], mutation: str) -> None:
    if mutation == "semantic_wave_lock_bypass":
        manifest["compiler_identity"]["semantic_wave_version"] = "9.9.9"
        manifest["compiler_identity"]["semantic_wave_version_lock"] = "0" * 64
    elif mutation == "unauthorized_gate_escalation":
        manifest["eligibility"].update(renderer_cutover=True, ba11_authorized=True, ba12_authorized=True)
    elif mutation == "compile_identity_relabeling":
        manifest["compile_identity"]["ticker"] = "FAKE"
        manifest["compile_identity"]["as_of_date"] = "2099-01-01"
    elif mutation == "execution_attestation_erasure":
        item = artifact(manifest, "execution_attestation")
        value = read_json(root / item["relative_path"])
        value["pass_execution_complete"] = False
        value["pass_execution_record_sha256s"] = []
        write_json(root / item["relative_path"], value)
    elif mutation == "projection_display_token_injection":
        item = artifact(manifest, "renderer_projection")
        value = read_json(root / item["relative_path"])
        value["display_tokens"].append({
            "token_id": "product.synthetic.display", "token_type": "numeric_span",
            "span_id": "span.synthetic", "visible_text_sha256": "0" * 64,
        })
        value["display_tokens"].sort(key=lambda row: row["token_id"])
        write_json(root / item["relative_path"], value)
    elif mutation == "fixed_required_artifact_removal":
        removed = {"parsed_table_ir", "verification_plan"}
        removed_ids = {item["artifact_id"] for item in manifest["artifacts"] if item["artifact_kind"] in removed}
        for item in list(manifest["artifacts"]):
            if item["artifact_id"] in removed_ids:
                (root / item["relative_path"]).unlink()
        manifest["artifacts"] = [item for item in manifest["artifacts"] if item["artifact_id"] not in removed_ids]
        manifest["required_sections"] = [item for item in manifest["required_sections"] if item not in removed]
    elif mutation == "authority_v3_boundary_promotion":
        bridge_item = artifact(manifest, "authority_v3_bridge")
        bridge = read_json(root / bridge_item["relative_path"])
        bridge["target_contract_id"] = "foreign.authority"
        bridge["target_contract_version"] = 4
        write_json(root / bridge_item["relative_path"], bridge)
        for item in manifest["artifacts"]:
            if item["artifact_kind"] in {"authority_v3_payload", "authority_v3_bridge", "legacy_render_input"}:
                item.update(authoritative=True, compatibility_only=False, compatibility_rule="exact_hash")
    elif mutation == "copied_emitter_identity_without_valid_receipt":
        manifest["extensions"] = {"foreign_producer_nonce": "fully-rehashed-copy"}
    elif mutation in {"truncated_pass_set", "substituted_pass_id", "reordered_passes", "pass_version_drift", "ordinal_shift"}:
        record_item = artifact(manifest, "pass_execution_records")
        record_path = root / record_item["relative_path"]
        record_set = read_json(record_path)
        records = record_set["records"]
        if mutation == "truncated_pass_set": records.pop()
        elif mutation == "substituted_pass_id": records[3]["pass_id"] = "fake.substituted.pass"
        elif mutation == "reordered_passes":
            records[0]["pass_id"], records[1]["pass_id"] = records[1]["pass_id"], records[0]["pass_id"]
        elif mutation == "pass_version_drift": records[4]["pass_version"] = 999
        elif mutation == "ordinal_shift":
            for row in records: row["ordinal"] += 100
        write_json(record_path, record_set)
        attestation_item = artifact(manifest, "execution_attestation")
        attestation_path = root / attestation_item["relative_path"]
        attestation = read_json(attestation_path)
        attestation["pass_execution_record_sha256s"] = [sha256_json(row) for row in records]
        write_json(attestation_path, attestation)
    elif mutation in {"empty_verification_plan_wrapper", "empty_parsed_table_wrapper"}:
        kind = "verification_plan" if mutation.startswith("empty_verification") else "parsed_table_ir"
        item = artifact(manifest, kind); value = read_json(root / item["relative_path"])
        value["artifacts"] = {}; value["artifact_sha256s"] = {}
        write_json(root / item["relative_path"], value)
    elif mutation == "missing_required_wrapper_key":
        item = artifact(manifest, "typed_facts"); value = read_json(root / item["relative_path"])
        value.pop("artifact_sha256s")
        write_json(root / item["relative_path"], value)
    elif mutation == "semantic_artifact_authority_demotion":
        artifact(manifest, "typed_facts").update(authoritative=False, compatibility_only=True)
    elif mutation == "producer_or_layer_drift":
        artifact(manifest, "metrics").update(producer_pass_id="product.fake.pass", layer="L11_emit")
    else:
        raise ValueError(f"unknown mutation:{mutation}")


def semantic_values(root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    semantic = {
        kind: payload(root, manifest, kind)["artifacts"]
        for kind in ("source_provenance", "typed_facts", "metrics", "formula_evaluations", "evidence_graph", "claim_graph", "decision_graph")
    }
    refs = {
        item["artifact_id"]: item["sha256"] for item in manifest["artifacts"]
        if item.get("authoritative") is True and str(item.get("layer", "")).startswith("L")
    }
    return {
        "artifact_hashes": manifest["artifacts"],
        "compile_identity": manifest["compile_identity"],
        "compiler_version": manifest["compiler_identity"]["compiler_version"],
        "foundation_version": manifest["compiler_identity"]["foundation_version"],
        "registry_lock": manifest["registry_lock"],
        "pass_manifest": manifest["compiler_identity"]["pass_manifest_sha256"],
        "source_provenance": semantic["source_provenance"]["source_inputs"],
        "ir_references": refs,
        "typed_facts": semantic["typed_facts"]["typed_facts"],
        "metrics": semantic["metrics"]["metrics"],
        "formula_evaluations": semantic["formula_evaluations"]["formula_evaluations"],
        "evidence_graph": semantic["evidence_graph"]["complete_evidence_graph"],
        "claim_graph": semantic["claim_graph"]["claim_graph"],
        "decision_graph": semantic["decision_graph"]["semantic_decision_graph"],
        "diagnostics": payload(root, manifest, "diagnostics")["diagnostics"],
        "compile_verdict": payload(root, manifest, "compile_verdict"),
        "compatibility_state": manifest["compatibility"],
    }


def rehash(root: Path, manifest: dict[str, Any]) -> None:
    previous_hashes = {item["sha256"]: item for item in manifest["artifacts"]}
    for item in manifest["artifacts"]:
        data = (root / item["relative_path"]).read_bytes()
        item["sha256"] = hashlib.sha256(data).hexdigest()
        item["byte_length"] = len(data)
    replacement_hashes = {
        previous: item["sha256"] for previous, item in previous_hashes.items()
    }
    for item in manifest["artifacts"]:
        item["dependency_sha256s"] = sorted(
            replacement_hashes.get(value, value) for value in item.get("dependency_sha256s", [])
        )
    manifest["artifacts"].sort(key=lambda row: row["artifact_id"])
    manifest["artifact_index_sha256"] = sha256_json(manifest["artifacts"])
    values = semantic_values(root, manifest)
    by_kind: dict[str, list[str]] = {}
    for item in manifest["artifacts"]:
        by_kind.setdefault(item["artifact_kind"], []).append(item["artifact_id"])
    for section in manifest["sections"]:
        section["artifact_ids"] = sorted(
            artifact_id for kind in SECTION_KINDS[section["section_id"]] for artifact_id in by_kind.get(kind, [])
        )
        section["sha256"] = sha256_json(values[section["section_id"]])
    manifest["sections"].sort(key=lambda row: row["section_id"])
    manifest["section_index_sha256"] = sha256_json(manifest["sections"])
    body = dict(manifest)
    body.pop("bundle_sha256", None)
    manifest["bundle_sha256"] = sha256_json(body)
    write_json(root / "BUNDLE_MANIFEST.json", manifest)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mutation", required=True)
    parser.add_argument("--receipt-output", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        shutil.rmtree(args.output)
    shutil.copytree(args.bundle, args.output)
    manifest = read_json(args.output / "BUNDLE_MANIFEST.json")
    mutate(args.output, manifest, args.mutation)
    rehash(args.output, manifest)
    result = {
        "mutation": args.mutation, "bundle_sha256": manifest["bundle_sha256"],
        "fully_rehashed": True, "artifact_index_valid": sha256_json(manifest["artifacts"]) == manifest["artifact_index_sha256"],
        "section_index_valid": sha256_json(manifest["sections"]) == manifest["section_index_sha256"],
    }
    if args.receipt_output:
        receipt_set = build_receipt_set(
            [manifest], issued_by_key_id="research:rfc-0005-r2-fixture",
            research_commit="fixture" * 5 + "12345",
        )
        write_json(args.receipt_output, receipt_set)
        result["receipt_set_sha256"] = receipt_set["receipt_set_sha256"]
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
