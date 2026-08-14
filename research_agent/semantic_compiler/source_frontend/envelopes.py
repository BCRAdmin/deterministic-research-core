"""Foundation IREnvelope bindings for BA3 outputs."""

from __future__ import annotations

from research_agent.compiler_foundation.contracts import CompilerLayer, IREnvelope

from .contracts import CompileRequestIR, SourceAcquisitionIR, SourceSnapshotIR


def compile_request_envelope(value: CompileRequestIR) -> IREnvelope:
    return IREnvelope.create(
        ir_type="compile_request_ir",
        layer=CompilerLayer.L0_COMPILE_INTAKE,
        producer_pass_id="ba3.l0.freeze_compile_request",
        payload=value.model_dump(mode="json"),
    )


def source_acquisition_envelope(value: SourceAcquisitionIR) -> IREnvelope:
    return IREnvelope.create(
        ir_type="source_acquisition_ir",
        layer=CompilerLayer.L1_SOURCE_ACQUISITION,
        producer_pass_id="ba3.l1.plan_source_acquisition",
        payload=value.model_dump(mode="json"),
    )


def source_snapshot_envelope(value: SourceSnapshotIR) -> IREnvelope:
    return IREnvelope.create(
        ir_type="source_snapshot_ir",
        layer=CompilerLayer.L2_SOURCE_SNAPSHOT,
        producer_pass_id="ba3.l2.freeze_source_snapshot",
        payload=value.model_dump(mode="json"),
    )
