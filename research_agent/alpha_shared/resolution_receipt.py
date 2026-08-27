"""Hash-bound shared metric-resolution receipts."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.compiler_foundation.contracts import StrictModel


class RejectedCandidate(StrictModel):
    candidate_id: str
    reason_codes: tuple[str, ...]


class MetricResolutionReceipt(StrictModel):
    contract_id: str = "room16.alpha.metric_resolution_receipt"
    contract_version: int = 1
    metric_id: str
    status: Literal["RESOLVED", "UNSUPPORTED", "AMBIGUOUS", "STALE_ONLY"]
    selected_candidate_id_or_null: str | None
    selected_concept_or_label: str | None
    source_kind: str | None
    period_role: str | None
    freshness_status: str | None
    unit: str | None
    score_components: dict[str, int]
    rejected_candidates: tuple[RejectedCandidate, ...]
    evidence_ids: tuple[str, ...]
    resolver_profile_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @classmethod
    def create(cls, **values: object) -> "MetricResolutionReceipt":
        body = {
            "contract_id": "room16.alpha.metric_resolution_receipt",
            "contract_version": 1,
            **values,
        }
        return cls(**body, receipt_sha256=sha256_json(body))

    @model_validator(mode="after")
    def validate_hash(self) -> "MetricResolutionReceipt":
        body = self.model_dump(mode="json")
        body.pop("receipt_sha256")
        if sha256_json(body) != self.receipt_sha256:
            raise ValueError("metric resolution receipt self-hash mismatch")
        return self
