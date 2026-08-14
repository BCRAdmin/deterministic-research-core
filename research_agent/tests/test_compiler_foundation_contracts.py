from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from research_agent.compiler_foundation.canonical import (
    CanonicalizationError,
    canonical_json,
    sha256_json,
)
from research_agent.compiler_foundation.contracts import (
    CompileVerdictIR,
    CompatibilityPolicy,
    CompilerLayer,
    ContractError,
    DiagnosticIR,
    IREnvelope,
    ProvenanceRef,
    QuarantineState,
    ReleaseEffect,
    SemanticSeverity,
)

CONFIG = Path(__file__).parents[1] / "compiler_foundation" / "config"


def diagnostic(code: str, effect: ReleaseEffect, severity: SemanticSeverity) -> DiagnosticIR:
    return DiagnosticIR(
        code=code,
        semantic_severity=severity,
        release_effect=effect,
        layer=CompilerLayer.L10_VERIFICATION,
        pass_id="foundation.l10_verification_observe",
        subject_ref="fixture:subject",
        root_cause_ref="fixture:root",
        fixture_refs=("fixture:negative",),
        message="fixture diagnostic",
    )


def test_all_ba0_envelopes_are_versioned_and_fail_closed() -> None:
    provenance = ProvenanceRef(source_id="fixture:source", artifact_path="fixture.json", sha256="a" * 64)
    ir = IREnvelope.create(
        ir_type="fixture.ir",
        layer=CompilerLayer.L0_COMPILE_INTAKE,
        producer_pass_id="fixture.pass",
        payload={"answer": 42},
        provenance_refs=(provenance,),
    )
    ir.verify_hash()
    assert ir.contract_version == 1
    assert ir.quarantine == QuarantineState()
    assert ir.compatibility.unknown_id_policy == "fail_closed"

    tampered = ir.model_copy(update={"payload": {"answer": 43}})
    with pytest.raises(ContractError, match="hash mismatch"):
        tampered.verify_hash()
    with pytest.raises(ValidationError):
        IREnvelope.model_validate({**ir.model_dump(mode="json"), "contract_version": 2})
    with pytest.raises(ValidationError):
        IREnvelope.model_validate({**ir.model_dump(mode="json"), "unknown": True})


def test_diagnostic_severity_and_release_effect_are_independent() -> None:
    severe_nonblocking = diagnostic("HIGH_SEVERITY_NO_BLOCK", ReleaseEffect.NONE, SemanticSeverity.CRITICAL)
    low_severity_block = diagnostic("LOW_SEVERITY_RELEASE_BLOCK", ReleaseEffect.RELEASE_BLOCK, SemanticSeverity.INFO)
    verdict = CompileVerdictIR.derive([severe_nonblocking, low_severity_block])
    assert verdict.compile_allowed is True
    assert verdict.release_allowed is False
    assert verdict.review_required is True
    assert verdict.blocking_codes == ("LOW_SEVERITY_RELEASE_BLOCK",)


@pytest.mark.parametrize(
    ("effect", "compile_allowed", "release_allowed"),
    [
        (ReleaseEffect.NONE, True, True),
        (ReleaseEffect.REVIEW_REQUIRED, True, True),
        (ReleaseEffect.RELEASE_BLOCK, True, False),
        (ReleaseEffect.COMPILE_BLOCK, False, False),
    ],
)
def test_verdict_derivation(effect: ReleaseEffect, compile_allowed: bool, release_allowed: bool) -> None:
    verdict = CompileVerdictIR.derive([diagnostic("FIXTURE_CODE", effect, SemanticSeverity.ERROR)])
    assert verdict.compile_allowed is compile_allowed
    assert verdict.release_allowed is release_allowed


def test_compatibility_and_quarantine_invariants() -> None:
    with pytest.raises(ValidationError):
        CompatibilityPolicy(
            current_major=2,
            current_minor=0,
            minimum_reader_major=1,
            maximum_reader_major=1,
        )
    with pytest.raises(ValidationError):
        QuarantineState(status="quarantined")
    with pytest.raises(ValidationError):
        QuarantineState(status="clear", review_required=True)


def test_python_cross_language_conformance_corpus() -> None:
    corpus = json.loads((CONFIG / "cross_language_conformance.json").read_text(encoding="utf-8"))
    for fixture in corpus["fixtures"]:
        assert canonical_json(fixture["value"]) == fixture["canonical_json"]
        assert sha256_json(fixture["value"]) == fixture["sha256"]
    for name, expected in corpus["document_fixtures"].items():
        assert sha256_json(json.loads((CONFIG / name).read_text(encoding="utf-8"))) == expected
    with pytest.raises(CanonicalizationError):
        canonical_json({"bad": float("nan")})
    with pytest.raises(CanonicalizationError):
        canonical_json({"bad": 9_007_199_254_740_992})
    with pytest.raises(CanonicalizationError):
        canonical_json({"bad": "\ud800"})
