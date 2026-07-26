"""Versioned integration contracts exported by the deterministic research core."""

from research_agent.integration.authority_bundle import (
    AUTHORITY_CONTRACT_ID,
    AUTHORITY_CONTRACT_VERSION,
    build_authority_bundle,
    verify_authority_bundle,
)

__all__ = [
    "AUTHORITY_CONTRACT_ID",
    "AUTHORITY_CONTRACT_VERSION",
    "build_authority_bundle",
    "verify_authority_bundle",
]
