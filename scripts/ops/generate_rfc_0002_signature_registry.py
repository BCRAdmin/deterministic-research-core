#!/usr/bin/env python3
"""Generate the RFC-0002 semantic Metric Signature Authority from frozen canaries."""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path
from typing import Any

from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.semantic_compiler.registry_foundation.authority import SemanticRegistryAuthority
from research_agent.semantic_compiler.semantic_spine.contracts import TypedFactSpineIR, create_hashed
from research_agent.semantic_compiler.semantic_spine.semantics import _fact_kind, signature_for_fact

RESEARCH_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CANARY_ROOT = RESEARCH_ROOT.parent / "company-dossier-lab/.runtime/cross-company-release-current/ROOM16_WM_COST_ABT_CROSS_COMPANY_RC_8cf064d75c8c-20260814-115448"
DEFAULT_OUTPUT = RESEARCH_ROOT / "research_agent/semantic_compiler/semantic_spine/config/semantic_metric_signatures_v2.json"


def _one(names: list[str], suffix: str) -> str:
    matches = [name for name in names if name.endswith(suffix)]
    if len(matches) != 1:
        raise ValueError(f"archive member count invalid: {suffix}")
    return matches[0]


def _typed(fact: dict[str, Any], authority: SemanticRegistryAuthority) -> TypedFactSpineIR:
    definition, binding = authority.bind_metric(str(fact["metric"]))
    if binding in {"quarantined_unknown", "semantic_collision"}:
        raise ValueError(f"unexecutable metric: {fact['metric']}")
    dimension = str(fact.get("dimension") or "text")
    fact_type = str(fact.get("fact_type") or "unknown")
    period_kind = str(fact.get("period_kind") or "unknown")
    return create_hashed(
        TypedFactSpineIR,
        fact_id=str(fact["fact_id"]),
        metric_id=str(fact["metric"]),
        metric_definition_id=definition,
        fact_kind=_fact_kind(dimension=dimension, fact_type=fact_type, period_kind=period_kind),
        fact_type=fact_type,
        value_state="missing" if fact.get("is_missing") else "not_applicable" if fact.get("is_not_applicable") else "zero" if fact.get("is_zero") else "value",
        value=fact.get("value"),
        dimension=dimension,
        unit=str(fact.get("display_unit") or fact.get("unit") or "text"),
        currency=str(fact.get("currency") or "none"),
        scale=str(fact.get("source_scale") or "none"),
        period_kind=period_kind,
        period_start=fact.get("period_start"),
        period_end=fact.get("period_end"),
        source_ids=tuple(sorted({str(item) for item in (fact.get("source_ids") or [fact.get("source_id")]) if item})),
        evidence_ids=tuple(sorted({str(item) for item in fact.get("evidence_ids") or [] if item})),
        source_locator=fact.get("source_locator"),
        table_id=fact.get("table_id"),
        cell_id=fact.get("cell_id"),
        normalized_record_sha256="0" * 64,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--canary-root", type=Path, default=DEFAULT_CANARY_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    authority = SemanticRegistryAuthority.load()
    signatures = {}
    canary_hashes = {}
    import hashlib
    for archive in sorted(args.canary_root.glob("*.zip")):
        canary_hashes[archive.name] = hashlib.sha256(archive.read_bytes()).hexdigest()
        with zipfile.ZipFile(archive) as bundle:
            facts = json.loads(bundle.read(_one(bundle.namelist(), "/authority_bundle/fact_ledger.json")))["claims"]
        for fact in facts:
            signature = signature_for_fact(_typed(fact, authority))
            previous = signatures.get(signature.signature_id)
            if previous is not None and previous != signature:
                raise ValueError(f"signature collision: {signature.signature_id}")
            signatures[signature.signature_id] = signature
    body = {
        "contract_id": "room16.compiler.metric_signature_authority",
        "contract_version": 1,
        "version": "2.0.0-rfc0002",
        "rfc_id": "RFC-0002",
        "owner": "research",
        "parent_registry_foundation_version": "1.1.0",
        "parent_registry_authority_sha256": authority.authority_sha256,
        "source_canary_hashes": {key: canary_hashes[key] for key in sorted(canary_hashes)},
        "signatures": [signatures[key].model_dump(mode="json") for key in sorted(signatures)],
    }
    payload = {**body, "authority_sha256": sha256_json(body)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "signature_count": len(signatures), "authority_sha256": payload["authority_sha256"]}, indent=2))


if __name__ == "__main__":
    main()
