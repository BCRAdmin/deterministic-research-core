"""Strict, content-addressed BA12 machine contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.compiler_foundation.contracts import StrictModel

SHA = r"^[0-9a-f]{64}$"
CANONICALIZATION = "room16.foundation.canonical_json@1"


def _hash(contract_id: str, body: dict[str, object]) -> str:
    return sha256_json({"domain": f"{contract_id}@1", "payload": body})


class _HashedContract(StrictModel):
    authority_owner: Literal["research_compiler"] = "research_compiler"
    canonicalization_profile: Literal["room16.foundation.canonical_json@1"] = CANONICALIZATION
    record_sha256: str = Field(pattern=SHA)

    @model_validator(mode="after")
    def valid_hash(self) -> "_HashedContract":
        body = self.model_dump(mode="json", exclude={"record_sha256"})
        if self.record_sha256 != _hash(str(body["contract_id"]), body):
            raise ValueError("BA12_RECORD_HASH_MISMATCH")
        return self


class NativeRunReceipt(_HashedContract):
    contract_id: Literal["room16.ba12.native_run_receipt"] = "room16.ba12.native_run_receipt"
    contract_version: Literal[1] = 1
    ticker: str = Field(pattern=r"^[A-Z0-9.^-]+$")
    as_of_date: str
    compile_request_sha256: str = Field(pattern=SHA)
    source_acquisition_sha256: str = Field(pattern=SHA)
    retrieval_receipt_set_sha256: str = Field(pattern=SHA)
    source_snapshot_sha256: str = Field(pattern=SHA)
    pass_execution_profile_sha256: str = Field(pattern=SHA)
    compiler_artifact_bundle_sha256: str = Field(pattern=SHA)
    ba11_governance_snapshot_sha256: str = Field(pattern=SHA)
    research_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    research_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    semantic_input: Literal["source_snapshot_ir_only"] = "source_snapshot_ir_only"
    legacy_semantic_input_allowed: Literal[False] = False
    status: Literal["PASS"] = "PASS"


class CutoverComparisonReceipt(_HashedContract):
    contract_id: Literal["room16.ba12.cutover_comparison_receipt"] = "room16.ba12.cutover_comparison_receipt"
    contract_version: Literal[1] = 1
    ticker: str
    native_bundle_sha256: str = Field(pattern=SHA)
    legacy_reference_sha256: str = Field(pattern=SHA)
    unexplained_semantic_differences: tuple[str, ...] = ()
    verdict: Literal["PASS", "BLOCK"]


class CutoverCandidate(_HashedContract):
    contract_id: Literal["room16.ba12.cutover_candidate"] = "room16.ba12.cutover_candidate"
    contract_version: Literal[1] = 1
    comparison_receipt_sha256s: tuple[str, ...]
    operator_execution_authority_sha256: str = Field(pattern=SHA)
    candidate_only: Literal[True] = True
    accepted: Literal[False] = False


class CutoverState(_HashedContract):
    contract_id: Literal["room16.ba12.cutover_state"] = "room16.ba12.cutover_state"
    contract_version: Literal[1] = 1
    state: Literal["shadow_native", "dual_run_compare", "cutover_candidate", "native_authoritative"]
    previous_state: Literal["shadow_native", "dual_run_compare", "cutover_candidate"] | None
    transition_receipt_sha256: str = Field(pattern=SHA)
    independent_acceptance_sha256: str | None = Field(default=None, pattern=SHA)
    frozen: bool = False


class RendererSurface(StrictModel):
    surface_id: str
    bundle_input: Literal["room16.compiler_artifact_bundle@2"] = "room16.compiler_artifact_bundle@2"
    consumer_trust_receipt_sha256: str = Field(pattern=SHA)
    renderer_implementation_sha256: str = Field(pattern=SHA)
    no_legacy_truth_scan_sha256: str = Field(pattern=SHA)
    failure_behavior: Literal["fail_closed_no_legacy_fallback"] = "fail_closed_no_legacy_fallback"


class RendererCutoverReceipt(_HashedContract):
    contract_id: Literal["room16.ba12.renderer_cutover_receipt"] = "room16.ba12.renderer_cutover_receipt"
    contract_version: Literal[1] = 1
    surfaces: tuple[RendererSurface, ...]
    legacy_truth_fallback_allowed: Literal[False] = False
    verdict: Literal["PASS"] = "PASS"


class RecoveryReceipt(_HashedContract):
    contract_id: Literal["room16.ba12.recovery_receipt"] = "room16.ba12.recovery_receipt"
    contract_version: Literal[1] = 1
    interrupted_state: str
    recovered_state: str
    source_snapshot_sha256: str = Field(pattern=SHA)
    recovered_bundle_sha256: str = Field(pattern=SHA)
    authority_mutated: Literal[False] = False
    verdict: Literal["PASS", "BLOCK"]


class ReleaseReadinessEnvelope(_HashedContract):
    contract_id: Literal["room16.ba12.release_readiness_envelope"] = "room16.ba12.release_readiness_envelope"
    contract_version: Literal[1] = 1
    evidence_sha256s: tuple[str, ...]
    ready_for_independent_rereview: Literal[True] = True
    release_ready_candidate: Literal[True] = True
    ba12_implementation_ready: Literal[False] = False
    ba12_frozen: Literal[False] = False
    release_ready: Literal[False] = False
    release_authorized: Literal[False] = False
    publication_authorized: Literal[False] = False
    deploy_authorized: Literal[False] = False


def create_record(model: type[_HashedContract], **values: object) -> _HashedContract:
    body = {**values}
    fields = model.model_fields
    body.setdefault("contract_id", fields["contract_id"].default)
    body.setdefault("contract_version", 1)
    body.setdefault("authority_owner", "research_compiler")
    body.setdefault("canonicalization_profile", CANONICALIZATION)
    body = model.model_construct(**body, record_sha256="0" * 64).model_dump(
        mode="json", exclude={"record_sha256"}
    )
    return model(**body, record_sha256=_hash(str(body["contract_id"]), body))
