"""BA3 Source Front-End contracts and offline execution."""

from .contracts import (
    CompilePolicyIR,
    CompileRequestIR,
    ResolvedInstrumentIR,
    RetrievalReceiptIR,
    SourceAcquisitionIR,
    SourceArtifactIR,
    SourceDispositionIR,
    SourceSnapshotIR,
)
from .offline import OfflineSourceInput, freeze_offline_sources, verify_source_snapshot
from .planner import build_compile_request, plan_source_acquisition

__all__ = [
    "CompilePolicyIR",
    "CompileRequestIR",
    "OfflineSourceInput",
    "ResolvedInstrumentIR",
    "RetrievalReceiptIR",
    "SourceAcquisitionIR",
    "SourceArtifactIR",
    "SourceDispositionIR",
    "SourceSnapshotIR",
    "build_compile_request",
    "freeze_offline_sources",
    "plan_source_acquisition",
    "verify_source_snapshot",
]

