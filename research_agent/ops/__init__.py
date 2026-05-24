"""Local Agent OS readiness helpers.

These modules translate useful Hermes-style operating patterns into bounded,
read-only or artifact-writing workflows for this repository. They do not install
external skills, open network connections, mutate secrets, or update runtime
configuration.
"""

from __future__ import annotations

__all__ = [
    "automation_cards",
    "coding_guardrails",
    "deliverable_swarm",
    "guardrails",
    "memory_inbox",
    "operator_inbox",
    "readiness",
    "skill_registry",
    "terminal_backends",
]
