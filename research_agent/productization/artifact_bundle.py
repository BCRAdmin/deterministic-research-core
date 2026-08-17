"""BA10 compiler artifact bundle emission, verification and v3 bridge.

The emitter consumes the frozen RFC-0004 replay result and packages it at L11.
It never mutates the L0-L10 IR or promotes Authority Bundle v3 to compiler
truth.  In compatibility shadow mode the exact v3 bytes are retained only as
a marked compatibility view.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import unicodedata
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from research_agent.compiler_foundation.canonical import (
    canonical_bytes,
    sha256_bytes,
    sha256_json,
)
from research_agent.semantic_compiler.semantic_spine.rfc_0004 import (
    replay_rfc_0004_archive,
)

from .contracts import (
    REQUIRED_ARTIFACT_KINDS,
    REQUIRED_BUNDLE_SECTION_IDS,
    ArtifactRecord,
    BundleSectionRecord,
    CompatibilityState,
    CompileIdentity,
    CompilerArtifactBundleManifest,
    CompilerIdentity,
    ConsumerCapabilities,
    EligibilityState,
)

BUNDLE_MANIFEST = "BUNDLE_MANIFEST.json"
BRIDGE_PATH = "bridge/authority_v3_compatibility_view.json"
RENDERER_PROJECTION_PATH = "presentation/renderer_projection.json"
FREEZE_RECORD = (
    Path(__file__).resolve().parents[1]
    / "semantic_compiler/freeze/semantic_compiler_wave_freeze_v1.json"
)


class ArtifactBundleError(ValueError):
    """Stable fail-closed Artifact ABI error."""

    def __init__(self, diagnostic_code: str, detail: str) -> None:
        super().__init__(f"{diagnostic_code}:{detail}")
        self.diagnostic_code = diagnostic_code
        self.detail = detail


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _nfc_required(value: Any, *, path: str = "$") -> None:
    if isinstance(value, str):
        if unicodedata.normalize("NFC", value) != value:
            raise ArtifactBundleError("ABI_UNICODE_NOT_NFC", path)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            _nfc_required(key, path=f"{path}.<key>")
            _nfc_required(item, path=f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _nfc_required(item, path=f"{path}[{index}]")


def _safe_relative(value: str) -> str:
    pure = PurePosixPath(value)
    if pure.is_absolute() or not value or ".." in pure.parts:
        raise ArtifactBundleError("ABI_ARTIFACT_PATH_UNSAFE", value)
    return pure.as_posix()


def _write_json(path: Path, value: Any) -> bytes:
    _nfc_required(value)
    payload = canonical_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return payload


def _artifact_contract(value: Any, fallback: str) -> tuple[str, int | str]:
    if isinstance(value, dict):
        return (
            str(value.get("contract_id") or fallback),
            value.get("contract_version", 1),
        )
    return fallback, 1


def _record(
    *,
    artifact_id: str,
    artifact_kind: str,
    relative_path: str,
    payload: bytes,
    contract_id: str,
    contract_version: int | str,
    layer: str,
    producer_pass_id: str,
    media_type: str = "application/json",
    required: bool = True,
    authoritative: bool = True,
    compatibility_only: bool = False,
    compatibility_rule: str = "exact_hash",
    dependencies: Iterable[str] = (),
    provenance: Iterable[str] = (),
) -> ArtifactRecord:
    return ArtifactRecord(
        artifact_id=artifact_id,
        artifact_kind=artifact_kind,
        contract_id=contract_id,
        contract_version=contract_version,
        layer=layer,
        producer_pass_id=producer_pass_id,
        relative_path=_safe_relative(relative_path),
        media_type=media_type,
        sha256=sha256_bytes(payload),
        byte_length=len(payload),
        required=required,
        compatibility_rule=compatibility_rule,
        authoritative=authoritative,
        compatibility_only=compatibility_only,
        dependency_sha256s=tuple(sorted(set(dependencies))),
        provenance_refs=tuple(sorted(set(provenance))),
    )


def _add_json(
    root: Path,
    records: list[ArtifactRecord],
    *,
    artifact_id: str,
    artifact_kind: str,
    relative_path: str,
    value: Any,
    layer: str,
    producer_pass_id: str,
    required: bool = True,
    authoritative: bool = True,
    compatibility_only: bool = False,
    compatibility_rule: str = "exact_hash",
    dependencies: Iterable[str] = (),
    provenance: Iterable[str] = (),
) -> ArtifactRecord:
    contract_id, contract_version = _artifact_contract(value, artifact_kind)
    payload = _write_json(root / relative_path, value)
    item = _record(
        artifact_id=artifact_id,
        artifact_kind=artifact_kind,
        relative_path=relative_path,
        payload=payload,
        contract_id=contract_id,
        contract_version=contract_version,
        layer=layer,
        producer_pass_id=producer_pass_id,
        required=required,
        authoritative=authoritative,
        compatibility_only=compatibility_only,
        compatibility_rule=compatibility_rule,
        dependencies=dependencies,
        provenance=provenance,
    )
    records.append(item)
    return item


def _one_member(names: list[str], suffix: str) -> str:
    matches = [name for name in names if name.endswith(suffix)]
    if len(matches) != 1:
        raise ArtifactBundleError("ABI_COMPATIBILITY_SOURCE_INVALID", suffix)
    return matches[0]


def _semantic_ids(artifacts: dict[str, Any], legacy_markdown_sha256: str | None) -> dict[str, Any]:
    facts = tuple(sorted({str(item["fact_id"]) for item in artifacts["typed_facts"]}))
    metrics = tuple(
        sorted({str(item["metric_instance_id"]) for item in artifacts["metrics"]})
    )
    claim_graph = artifacts["claim_graph"]
    claim_ids = tuple(
        sorted(
            {
                str(node.get("subject_ref") or node.get("node_id"))
                for node in claim_graph.get("nodes", [])
                if str(node.get("node_kind") or "").lower() == "claim"
            }
        )
    )
    semantic_decision = artifacts["semantic_decision_graph"]
    decision_ids = tuple(
        sorted(
            str(node["node_id"])
            for node in semantic_decision.get("nodes", [])
            if node.get("instance_presence") == "present"
        )
    )
    display_tokens = []
    for item in sorted(artifacts["typed_facts"], key=lambda row: str(row["fact_id"])):
        if item.get("value_state") not in {"value", "zero"}:
            continue
        display_tokens.append(
            {
                "token_id": f"fact.{item['fact_id']}.value",
                "fact_id": str(item["fact_id"]),
                "value": item.get("value"),
                "unit": str(item.get("unit") or ""),
                "currency": str(item.get("currency") or ""),
                "scale": str(item.get("scale") or ""),
                "period_start": item.get("period_start"),
                "period_end": item.get("period_end"),
            }
        )
    return {
        "contract_id": "room16.compiler.renderer_projection",
        "contract_version": 1,
        "projection_mode": "legacy_markdown_compatibility_shadow",
        "fact_ids": facts,
        "metric_instance_ids": metrics,
        "claim_ids": claim_ids,
        "decision_ids": decision_ids,
        "display_tokens": display_tokens,
        "legacy_markdown_sha256": legacy_markdown_sha256,
        "allowed_formats": ["api", "docx", "json", "markdown", "pdf", "ui"],
        "renderer_may_create_semantic_truth": False,
        "release_ready": False,
        "publication_allowed": False,
    }


def _write_semantic_artifacts(
    root: Path, replay: dict[str, Any], records: list[ArtifactRecord]
) -> tuple[dict[str, Any], dict[str, ArtifactRecord]]:
    compile_state = replay["compile_state"]
    artifacts = compile_state["artifacts"]
    written: dict[str, ArtifactRecord] = {}
    written["compile_state"] = _add_json(
        root, records, artifact_id="compiler.compile_state", artifact_kind="compile_state",
        relative_path="artifacts/compiler/compile_state.json", value=compile_state,
        layer="L10_verification", producer_pass_id="ba10.l11.emit_bundle",
    )
    written["pass_execution_records"] = _add_json(
        root, records, artifact_id="compiler.pass_execution_records",
        artifact_kind="pass_execution_records",
        relative_path="artifacts/compiler/pass_execution_records.json",
        value={"contract_id": "room16.compiler.pass_execution_record_set", "contract_version": 1,
               "records": replay["pass_execution_records"]},
        layer="L10_verification", producer_pass_id="ba10.l11.emit_bundle",
        dependencies=(written["compile_state"].sha256,),
    )
    written["execution_attestation"] = _add_json(
        root, records, artifact_id="compiler.execution_attestation",
        artifact_kind="execution_attestation",
        relative_path="artifacts/compiler/execution_attestation.json",
        value=replay["execution_attestation"], layer="L10_verification",
        producer_pass_id="ba10.l11.emit_bundle",
        dependencies=(written["compile_state"].sha256, written["pass_execution_records"].sha256),
    )

    groups = {
        "source_provenance": ("L2_source_snapshot", ["source_inputs"]),
        "parsed_table_ir": ("L3_parse_discover", ["parsed_payload_refs", "table_discovery_summaries", "table_refs", "cell_refs", "legacy_table_cell_mappings"]),
        "typed_facts": ("L5_typed_fact", ["normalized_records", "typed_facts"]),
        "metrics": ("L6_metric_formula", ["signatures", "metrics"]),
        "formula_evaluations": ("L6_metric_formula", ["formula_operand_facts", "formula_operands", "formula_evaluations", "policy_parameters"]),
        "evidence_graph": ("L7_evidence_graph", ["complete_evidence_graph"]),
        "claim_graph": ("L8_claim_graph", ["claim_graph"]),
        "decision_graph": ("L9_decision_graph", ["decision_graph", "semantic_decision_graph"]),
        "verification_plan": ("L10_verification", ["verification_plan"]),
    }
    previous = written["compile_state"].sha256
    for kind, (layer, keys) in groups.items():
        value = {
            "contract_id": f"room16.compiler.bundle_section.{kind}",
            "contract_version": 1,
            "artifacts": {key: artifacts[key] for key in keys},
            "artifact_sha256s": {key: compile_state["artifact_sha256s"][key] for key in keys},
        }
        item = _add_json(
            root, records, artifact_id=f"semantic.{kind}", artifact_kind=kind,
            relative_path=f"artifacts/semantic/{kind}.json", value=value, layer=layer,
            producer_pass_id="ba10.l11.emit_bundle", dependencies=(previous,),
        )
        written[kind] = item
        previous = item.sha256

    verification = replay["verification_report"]
    written["diagnostics"] = _add_json(
        root, records, artifact_id="verification.diagnostics", artifact_kind="diagnostics",
        relative_path="artifacts/verification/diagnostics.json",
        value={"contract_id": "room16.compiler.diagnostic_set", "contract_version": 1,
               "diagnostics": verification["diagnostics"]},
        layer="L10_verification", producer_pass_id="ba10.l11.emit_bundle",
        dependencies=(written["verification_plan"].sha256,),
    )
    written["compile_verdict"] = _add_json(
        root, records, artifact_id="verification.compile_verdict", artifact_kind="compile_verdict",
        relative_path="artifacts/verification/compile_verdict.json",
        value=verification["verdict"], layer="L10_verification",
        producer_pass_id="ba10.l11.emit_bundle",
        dependencies=(written["diagnostics"].sha256,),
    )
    written["verification_report"] = _add_json(
        root, records, artifact_id="verification.report", artifact_kind="verification_report",
        relative_path="artifacts/verification/verification_report.json",
        value=verification, layer="L10_verification",
        producer_pass_id="ba10.l11.emit_bundle",
        dependencies=(written["diagnostics"].sha256, written["compile_verdict"].sha256),
    )
    _add_json(
        root, records, artifact_id="compiler.registry_lock", artifact_kind="registry_lock",
        relative_path="artifacts/compiler/registry_lock.json",
        value=compile_state["semantic_registry_lock"], layer="L10_verification",
        producer_pass_id="ba10.l11.emit_bundle", required=False,
        dependencies=(written["compile_state"].sha256,),
    )
    return artifacts, written


def _write_v3_compatibility(
    root: Path, archive: Path, records: list[ArtifactRecord]
) -> tuple[ArtifactRecord, str | None, dict[str, Any]]:
    v3_records = []
    legacy_markdown_sha256: str | None = None
    renderer_outputs: list[dict[str, Any]] = []
    with zipfile.ZipFile(archive) as source:
        names = source.namelist()
        manifest_member = _one_member(names, "/authority_bundle/authority_manifest.json")
        prefix = manifest_member.rsplit("authority_manifest.json", 1)[0]
        for member in sorted(name for name in names if name.startswith(prefix) and not name.endswith("/")):
            relative = member[len(prefix):]
            payload = source.read(member)
            target = f"compatibility/authority_v3/{_safe_relative(relative)}"
            path = root / target
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
            item = _record(
                artifact_id=f"compatibility.authority_v3.{sha256_bytes(relative.encode())[:24]}",
                artifact_kind="authority_v3_payload", relative_path=target, payload=payload,
                contract_id="room16.research_authority_bundle", contract_version=3,
                layer="L11_emit", producer_pass_id="ba10.l11.authority_v3_bridge",
                media_type="application/json" if relative.endswith(".json") else "application/octet-stream",
                required=False, authoritative=False, compatibility_only=True,
                compatibility_rule="byte_identical_compatibility_view",
                provenance=(f"archive:{archive.name}:{member}",),
            )
            records.append(item)
            v3_records.append({
                "source_member": member,
                "view_path": relative,
                "bundle_artifact_id": item.artifact_id,
                "sha256": item.sha256,
                "byte_length": item.byte_length,
            })

        markdown_member = _one_member(names, "/case/research/internal_best_report.md")
        markdown = source.read(markdown_member)
        legacy_markdown_sha256 = sha256_bytes(markdown)
        markdown_path = "presentation/legacy_canonical_report.md"
        (root / markdown_path).parent.mkdir(parents=True, exist_ok=True)
        (root / markdown_path).write_bytes(markdown)
        records.append(_record(
            artifact_id="presentation.legacy_canonical_report",
            artifact_kind="legacy_render_input", relative_path=markdown_path,
            payload=markdown, contract_id="room16.legacy_canonical_report", contract_version=1,
            layer="L11_emit", producer_pass_id="ba10.l11.render_projection",
            media_type="text/markdown", required=False, authoritative=False,
            compatibility_only=True, provenance=(f"archive:{archive.name}:{markdown_member}",),
        ))

        for suffix, fmt in (
            ("/case/documents/2026-", "document"),
            ("/case/documents/render_quality.json", "render_quality"),
        ):
            for member in sorted(name for name in names if suffix in name and not name.endswith("/")):
                if fmt == "document" and not member.lower().endswith((".pdf", ".docx", ".md")):
                    continue
                payload = source.read(member)
                renderer_outputs.append({
                    "archive_member": member,
                    "format": Path(member).suffix.lstrip(".") or fmt,
                    "sha256": sha256_bytes(payload),
                    "byte_length": len(payload),
                })

    bridge = {
        "contract_id": "room16.authority_v3_compatibility_view",
        "contract_version": 1,
        "bridge_mode": "authority_v3_compatibility_shadow",
        "source_archive_sha256": _sha256_file(archive),
        "target_contract_id": "room16.research_authority_bundle",
        "target_contract_version": 3,
        "semantic_authority": False,
        "files": v3_records,
        "file_set_sha256": sha256_json(v3_records),
        "byte_parity_required": True,
    }
    bridge_record = _add_json(
        root, records, artifact_id="compatibility.authority_v3_bridge",
        artifact_kind="authority_v3_bridge", relative_path=BRIDGE_PATH,
        value=bridge, layer="L11_emit", producer_pass_id="ba10.l11.authority_v3_bridge",
        authoritative=False, compatibility_only=True,
        compatibility_rule="byte_identical_compatibility_view",
        dependencies=(item["sha256"] for item in v3_records),
    )
    return bridge_record, legacy_markdown_sha256, {
        "legacy_renderer_outputs": renderer_outputs,
    }


def build_compiler_artifact_bundle(
    *, archive: Path, output_root: Path, replay: dict[str, Any] | None = None
) -> CompilerArtifactBundleManifest:
    """Build a deterministic bundle directory from one immutable input archive."""

    archive = archive.resolve()
    output_root = output_root.resolve()
    if not archive.is_file():
        raise ArtifactBundleError("ABI_COMPATIBILITY_SOURCE_INVALID", str(archive))
    before = _sha256_file(archive)
    result = replay or replay_rfc_0004_archive(archive=archive)
    if before != _sha256_file(archive) or result["archive_sha256_before"] != before:
        raise ArtifactBundleError("ABI_COMPATIBILITY_SOURCE_TAMPER", archive.name)
    if result.get("compiler_mode") != "compatibility_shadow":
        raise ArtifactBundleError("ABI_COMPATIBILITY_STATE_INVALID", "compiler_mode")
    freeze = json.loads(FREEZE_RECORD.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="room16-ba10-bundle-") as temporary:
        staging = Path(temporary) / "bundle"
        staging.mkdir()
        records: list[ArtifactRecord] = []
        artifacts, written = _write_semantic_artifacts(staging, result, records)
        bridge, legacy_markdown_sha256, renderer_compatibility = _write_v3_compatibility(
            staging, archive, records
        )
        renderer_projection = _semantic_ids(artifacts, legacy_markdown_sha256)
        renderer_projection["legacy_renderer_outputs"] = renderer_compatibility[
            "legacy_renderer_outputs"
        ]
        projection = _add_json(
            staging, records, artifact_id="presentation.renderer_projection",
            artifact_kind="renderer_projection", relative_path=RENDERER_PROJECTION_PATH,
            value=renderer_projection, layer="L11_emit",
            producer_pass_id="ba10.l11.render_projection",
            dependencies=(
                written["typed_facts"].sha256,
                written["claim_graph"].sha256,
                written["decision_graph"].sha256,
            ),
        )
        records = sorted(records, key=lambda item: item.artifact_id)
        verdict = result["verification_report"]["verdict"]
        compile_allowed = bool(verdict["compile_allowed"])
        compiler_identity = CompilerIdentity(
            pass_manifest_sha256=freeze["pass_manifest"]["effective_pass_manifest_sha256"],
            ir_schema_set_sha256=freeze["ir_schema"]["schema_set_sha256"],
            registry_authority_sha256=freeze["registry"]["authority_sha256"],
        ).model_dump(mode="json")
        compile_identity = CompileIdentity(
            ticker=result["ticker"], as_of_date=result["as_of_date"],
            source_archive_sha256=before,
            final_compile_state_sha256=result["compile_state"]["ir_sha256"],
            verification_report_sha256=result["verification_report"]["ir_sha256"],
            replay_sha256=result["replay_sha256"],
        ).model_dump(mode="json")
        compatibility = CompatibilityState(
            mode="authority_v3_compatibility_shadow"
        ).model_dump(mode="json")
        artifact_dump = [item.model_dump(mode="json") for item in records]
        artifact_index_sha256 = sha256_json(artifact_dump)
        artifact_by_kind: dict[str, list[ArtifactRecord]] = {}
        for item in records:
            artifact_by_kind.setdefault(item.artifact_kind, []).append(item)

        def section(
            section_id: str,
            value: Any,
            *,
            artifact_kinds: tuple[str, ...] = (),
            compatibility_rule: str = "exact_version",
        ) -> BundleSectionRecord:
            artifact_ids = tuple(
                sorted(
                    item.artifact_id
                    for kind in artifact_kinds
                    for item in artifact_by_kind.get(kind, [])
                )
            )
            return BundleSectionRecord(
                section_id=section_id,
                schema_version="1.0.0",
                sha256=sha256_json(value),
                compatibility_rule=compatibility_rule,
                required=True,
                artifact_ids=artifact_ids,
            )

        ir_references = {
            item.artifact_id: item.sha256
            for item in records
            if item.authoritative and item.layer.startswith("L")
        }
        sections = sorted(
            (
                section("compile_identity", compile_identity),
                section("compiler_version", compiler_identity["compiler_version"]),
                section(
                    "foundation_version",
                    compiler_identity["foundation_version"],
                    compatibility_rule="immutable_reference",
                ),
                section(
                    "registry_lock",
                    result["compile_state"]["semantic_registry_lock"],
                    artifact_kinds=("registry_lock",),
                    compatibility_rule="immutable_reference",
                ),
                section(
                    "pass_manifest",
                    compiler_identity["pass_manifest_sha256"],
                    compatibility_rule="immutable_reference",
                ),
                section("source_provenance", artifacts["source_inputs"], artifact_kinds=("source_provenance",)),
                section("ir_references", ir_references),
                section("typed_facts", artifacts["typed_facts"], artifact_kinds=("typed_facts",)),
                section("metrics", artifacts["metrics"], artifact_kinds=("metrics",)),
                section("formula_evaluations", artifacts["formula_evaluations"], artifact_kinds=("formula_evaluations",)),
                section("evidence_graph", artifacts["complete_evidence_graph"], artifact_kinds=("evidence_graph",)),
                section("claim_graph", artifacts["claim_graph"], artifact_kinds=("claim_graph",)),
                section("decision_graph", artifacts["semantic_decision_graph"], artifact_kinds=("decision_graph",)),
                section("diagnostics", result["verification_report"]["diagnostics"], artifact_kinds=("diagnostics",)),
                section("compile_verdict", verdict, artifact_kinds=("compile_verdict",)),
                section(
                    "compatibility_state",
                    compatibility,
                    artifact_kinds=("authority_v3_bridge",),
                    compatibility_rule="byte_identical_compatibility_view",
                ),
                section("artifact_hashes", artifact_dump),
            ),
            key=lambda item: item.section_id,
        )
        if tuple(item.section_id for item in sections) != REQUIRED_BUNDLE_SECTION_IDS:
            raise ArtifactBundleError("ABI_REQUIRED_SECTION_SET_INVALID", "section_index")
        manifest_body = {
            "contract_id": "room16.compiler_artifact_bundle",
            "contract_version": 1,
            "schema_version": "1.1.0",
            "canonicalization_profile": "room16.foundation.canonical_json@1",
            "hash_algorithm": "sha256",
            "compiler_identity": compiler_identity,
            "compile_identity": compile_identity,
            "registry_lock": result["compile_state"]["semantic_registry_lock"],
            "artifact_index_sha256": artifact_index_sha256,
            "artifacts": artifact_dump,
            "section_index_sha256": sha256_json(
                [item.model_dump(mode="json") for item in sections]
            ),
            "sections": [item.model_dump(mode="json") for item in sections],
            "compatibility": compatibility,
            "eligibility": EligibilityState(
                compile_allowed=compile_allowed, renderer_eligible=compile_allowed
            ).model_dump(mode="json"),
            "consumer_capabilities": ConsumerCapabilities().model_dump(mode="json"),
            "required_sections": list(REQUIRED_ARTIFACT_KINDS),
            "optional_sections": ["authority_v3_payload", "legacy_render_input", "registry_lock"],
            "extensions": {},
        }
        manifest_body["bundle_sha256"] = sha256_json(manifest_body)
        manifest = CompilerArtifactBundleManifest.model_validate(manifest_body)
        manifest.verify_bundle_hash()
        _write_json(staging / BUNDLE_MANIFEST, manifest.model_dump(mode="json"))
        if output_root.exists():
            shutil.rmtree(output_root)
        output_root.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(staging, output_root)
    verified = verify_compiler_artifact_bundle(output_root)
    if verified.bundle_sha256 != manifest.bundle_sha256:
        raise ArtifactBundleError("ABI_MANIFEST_HASH_MISMATCH", output_root.name)
    return verified


def verify_compiler_artifact_bundle(root: Path) -> CompilerArtifactBundleManifest:
    root = root.resolve()
    manifest_path = root / BUNDLE_MANIFEST
    if not manifest_path.is_file():
        raise ArtifactBundleError("ABI_BUNDLE_MISSING", str(root))
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        _nfc_required(payload)
        manifest = CompilerArtifactBundleManifest.model_validate(payload)
        manifest.verify_bundle_hash()
    except ArtifactBundleError:
        raise
    except Exception as exc:
        raise ArtifactBundleError("ABI_MANIFEST_INVALID", str(exc)) from exc
    for artifact in manifest.artifacts:
        path = (root / artifact.relative_path).resolve()
        if path != root and root not in path.parents:
            raise ArtifactBundleError("ABI_ARTIFACT_PATH_UNSAFE", artifact.relative_path)
        if not path.is_file():
            code = "ABI_ARTIFACT_MISSING" if artifact.required else "ABI_OPTIONAL_ARTIFACT_MISSING"
            raise ArtifactBundleError(code, artifact.artifact_id)
        if path.stat().st_size != artifact.byte_length or _sha256_file(path) != artifact.sha256:
            raise ArtifactBundleError("ABI_ARTIFACT_HASH_MISMATCH", artifact.artifact_id)
    if manifest.compatibility.compiler_mode != "compatibility_shadow":
        raise ArtifactBundleError("ABI_COMPATIBILITY_STATE_INVALID", "compiler_mode")
    if manifest.eligibility.release_ready or manifest.eligibility.publication_allowed:
        raise ArtifactBundleError("ABI_ELIGIBILITY_ESCALATION", manifest.bundle_sha256)
    return manifest


def materialize_authority_v3_view(*, bundle_root: Path, output_root: Path) -> dict[str, Any]:
    manifest = verify_compiler_artifact_bundle(bundle_root)
    bridge_record = next(
        (item for item in manifest.artifacts if item.artifact_kind == "authority_v3_bridge"),
        None,
    )
    if bridge_record is None:
        raise ArtifactBundleError("ABI_ARTIFACT_MISSING", "authority_v3_bridge")
    bridge = json.loads((bundle_root / bridge_record.relative_path).read_text(encoding="utf-8"))
    if bridge.get("target_contract_version") != 3 or bridge.get("semantic_authority") is not False:
        raise ArtifactBundleError("ABI_AUTHORITY_V3_BRIDGE_MISMATCH", "bridge_contract")
    artifact_by_id = {item.artifact_id: item for item in manifest.artifacts}
    with tempfile.TemporaryDirectory(prefix="room16-v3-view-") as temporary:
        staging = Path(temporary) / "authority_bundle"
        staging.mkdir()
        output_files = []
        for item in bridge["files"]:
            record = artifact_by_id.get(item["bundle_artifact_id"])
            if record is None or record.sha256 != item["sha256"]:
                raise ArtifactBundleError("ABI_AUTHORITY_V3_BRIDGE_MISMATCH", item["view_path"])
            source = bundle_root / record.relative_path
            target = staging / _safe_relative(item["view_path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            if _sha256_file(target) != item["sha256"]:
                raise ArtifactBundleError("ABI_AUTHORITY_V3_BRIDGE_MISMATCH", item["view_path"])
            output_files.append({"path": item["view_path"], "sha256": item["sha256"]})
        if output_root.exists():
            shutil.rmtree(output_root)
        output_root.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(staging, output_root)
    return {
        "contract_id": "room16.authority_v3_bridge_materialization_result",
        "contract_version": 1,
        "source_bundle_sha256": manifest.bundle_sha256,
        "file_count": len(output_files),
        "files": output_files,
        "byte_parity_verified": True,
    }


def build_current_output_archive(
    *, output_dir: Path, ticker: str, as_of_date: str, archive: Path
) -> Path:
    """Create the minimal deterministic compatibility input for live sidecar emission."""

    output_dir = output_dir.resolve()
    case = output_dir / ticker / as_of_date
    authority = case / "authority_bundle"
    claims = case / "analyst_claims.json"
    report = case / "internal_best_report.md"
    for required in (authority / "authority_manifest.json", claims, report):
        if not required.is_file():
            raise ArtifactBundleError("ABI_ARTIFACT_MISSING", str(required))
    root_name = f"ROOM16_CURRENT_{ticker}_{as_of_date}"
    inputs: list[tuple[Path, str]] = [(claims, f"{root_name}/case/research/analyst_claims.json"),
                                      (report, f"{root_name}/case/research/internal_best_report.md")]
    for path in sorted(item for item in authority.rglob("*") if item.is_file()):
        inputs.append((path, f"{root_name}/case/research/authority_bundle/{path.relative_to(authority).as_posix()}"))
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for source, member in sorted(inputs, key=lambda item: item[1]):
            info = zipfile.ZipInfo(member, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            bundle.writestr(info, source.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return archive
