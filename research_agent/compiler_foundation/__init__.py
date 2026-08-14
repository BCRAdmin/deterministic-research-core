"""Room16 BA0-BA2 compiler foundation.

This package is a shadow-only contract and replay layer.  It deliberately has
no import of, or call into, the legacy research or rendering orchestrators.
"""

from .contracts import (
    CompileVerdictIR,
    CompatibilityPolicy,
    DiagnosticIR,
    IREnvelope,
    PassManifest,
    ProvenanceRef,
    QuarantineState,
    RegistryEnvelope,
)

__all__ = [
    "CompileVerdictIR",
    "CompatibilityPolicy",
    "DiagnosticIR",
    "IREnvelope",
    "PassManifest",
    "ProvenanceRef",
    "QuarantineState",
    "RegistryEnvelope",
]
