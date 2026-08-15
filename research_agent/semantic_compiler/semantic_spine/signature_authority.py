"""Research-owned narrow semantic Metric Signature Authority for RFC-0002."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from research_agent.compiler_foundation.canonical import sha256_json

from .contracts import MetricSignatureIR, TypedFactSpineIR
from .semantics import signature_for_fact

AUTHORITY_PATH = Path(__file__).with_name("config") / "semantic_metric_signatures_v2.json"


class MetricSignatureAuthorityError(ValueError):
    pass


class MetricSignatureAuthority:
    def __init__(self, payload: dict[str, Any]) -> None:
        if payload.get("contract_id") != "room16.compiler.metric_signature_authority" or payload.get("contract_version") != 1:
            raise MetricSignatureAuthorityError("metric_signature_authority_contract_invalid")
        if payload.get("version") != "2.0.0-rfc0002" or payload.get("owner") != "research":
            raise MetricSignatureAuthorityError("metric_signature_authority_version_or_owner_invalid")
        declared = payload.get("authority_sha256")
        body = {key: value for key, value in payload.items() if key != "authority_sha256"}
        if declared != sha256_json(body):
            raise MetricSignatureAuthorityError("metric_signature_authority_hash_mismatch")
        signatures = tuple(MetricSignatureIR.model_validate(item) for item in payload.get("signatures") or [])
        ids = [item.signature_id for item in signatures]
        if ids != sorted(ids) or len(ids) != len(set(ids)):
            raise MetricSignatureAuthorityError("metric_signatures_not_unique_and_sorted")
        self.payload = payload
        self.authority_sha256 = str(declared)
        self.signatures = {item.signature_id: item for item in signatures}
        self.by_metric: dict[str, tuple[str, ...]] = {}
        for signature in signatures:
            self.by_metric.setdefault(signature.legacy_metric_id, ())
            self.by_metric[signature.legacy_metric_id] = tuple(sorted((*self.by_metric[signature.legacy_metric_id], signature.signature_id)))

    @classmethod
    def load(cls, path: Path = AUTHORITY_PATH) -> "MetricSignatureAuthority":
        return cls(json.loads(path.read_text(encoding="utf-8")))

    def require_fact_signature(self, fact: TypedFactSpineIR) -> MetricSignatureIR:
        candidate = signature_for_fact(fact)
        expected = self.signatures.get(candidate.signature_id)
        if expected is None:
            if fact.metric_id not in self.by_metric:
                raise MetricSignatureAuthorityError(f"unknown_metric_signature:{fact.metric_id}")
            raise MetricSignatureAuthorityError(f"metric_signature_contract_mismatch:{fact.metric_id}")
        if expected.expected_contract_sha256 != candidate.expected_contract_sha256 or expected.ir_sha256 != candidate.ir_sha256:
            raise MetricSignatureAuthorityError(f"metric_signature_tamper:{fact.metric_id}")
        return expected
