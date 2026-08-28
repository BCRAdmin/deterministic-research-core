"""Lossless, deterministic SourceSnapshot fact candidate inventory for RFC-0011 R4."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, model_validator

from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.compiler_foundation.contracts import StrictModel

from .contracts import SharedBaseInputIR

SHA256 = r"^[0-9a-f]{64}$"
DurationRole = Literal[
    "INSTANT", "STANDALONE_QUARTER", "YEAR_TO_DATE", "ANNUAL", "OTHER_DURATION"
]


def _body(model: StrictModel, hash_field: str) -> dict[str, object]:
    value = model.model_dump(mode="json")
    value.pop(hash_field)
    return value


def _duration_role(start: str | None, end: str) -> DurationRole:
    if start is None:
        return "INSTANT"
    duration = (date.fromisoformat(end) - date.fromisoformat(start)).days + 1
    if 70 <= duration <= 111:
        return "STANDALONE_QUARTER"
    if 150 <= duration <= 285:
        return "YEAR_TO_DATE"
    if 330 <= duration <= 391:
        return "ANNUAL"
    return "OTHER_DURATION"


def _value_text(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


class RawFactCandidateIR(StrictModel):
    contract_id: Literal["room16.rfc0011.raw_fact_candidate_ir"] = (
        "room16.rfc0011.raw_fact_candidate_ir"
    )
    contract_version: Literal[1] = 1
    candidate_id: str
    source_snapshot_sha256: str = Field(pattern=SHA256)
    source_artifact_sha256: str = Field(pattern=SHA256)
    namespace: str
    concept: str
    label: str
    value: str
    unit: str
    start_or_null: str | None
    end: str
    filed: str
    form: str
    frame_or_null: str | None
    accession_or_null: str | None
    fy_or_null: int | str | None
    fp_or_null: str | None
    source_id: str
    provider_id: str
    source_kind: Literal["companyfacts", "market_price"]
    dimensions_present: Literal[False] = False
    dimension_key: Literal["NO_DIMENSIONS"] = "NO_DIMENSIONS"
    preliminary_duration_role: DurationRole
    candidate_sha256: str = Field(pattern=SHA256)

    @classmethod
    def create(cls, **values: object) -> "RawFactCandidateIR":
        identity = {
            key: values.get(key)
            for key in (
                "source_snapshot_sha256",
                "source_artifact_sha256",
                "namespace",
                "concept",
                "unit",
                "start_or_null",
                "end",
                "filed",
                "form",
                "accession_or_null",
                "frame_or_null",
                "value",
            )
        }
        body = {
            "contract_id": "room16.rfc0011.raw_fact_candidate_ir",
            "contract_version": 1,
            "candidate_id": f"raw.{sha256_json(identity)}",
            "dimensions_present": False,
            "dimension_key": "NO_DIMENSIONS",
            **values,
        }
        return cls(**body, candidate_sha256=sha256_json(body))

    @model_validator(mode="after")
    def verify_candidate(self) -> "RawFactCandidateIR":
        date.fromisoformat(self.end)
        date.fromisoformat(self.filed)
        if self.start_or_null is not None:
            date.fromisoformat(self.start_or_null)
        if _duration_role(self.start_or_null, self.end) != self.preliminary_duration_role:
            raise ValueError("raw fact duration role mismatch")
        if sha256_json(_body(self, "candidate_sha256")) != self.candidate_sha256:
            raise ValueError("raw fact candidate self-hash mismatch")
        return self


class ExcludedRawFactCandidateIR(StrictModel):
    source_artifact_sha256: str = Field(pattern=SHA256)
    namespace: str
    concept: str
    unit: str
    end_or_null: str | None
    filed_or_null: str | None
    reason_codes: tuple[str, ...]
    exclusion_sha256: str = Field(pattern=SHA256)

    @classmethod
    def create(cls, **values: object) -> "ExcludedRawFactCandidateIR":
        return cls(**values, exclusion_sha256=sha256_json(values))

    @model_validator(mode="after")
    def verify_exclusion(self) -> "ExcludedRawFactCandidateIR":
        if sha256_json(_body(self, "exclusion_sha256")) != self.exclusion_sha256:
            raise ValueError("raw fact exclusion self-hash mismatch")
        return self


class RawFactDedupeReceiptIR(StrictModel):
    input_candidate_count: int = Field(ge=0)
    output_candidate_count: int = Field(ge=0)
    duplicate_count: int = Field(ge=0)
    duplicate_candidate_ids: tuple[str, ...]
    receipt_sha256: str = Field(pattern=SHA256)

    @classmethod
    def create(cls, **values: object) -> "RawFactDedupeReceiptIR":
        return cls(**values, receipt_sha256=sha256_json(values))

    @model_validator(mode="after")
    def verify_receipt(self) -> "RawFactDedupeReceiptIR":
        if self.input_candidate_count != self.output_candidate_count + self.duplicate_count:
            raise ValueError("raw fact dedupe counts do not reconcile")
        if sha256_json(_body(self, "receipt_sha256")) != self.receipt_sha256:
            raise ValueError("raw fact dedupe receipt self-hash mismatch")
        return self


class SourceSnapshotFactInventoryIR(StrictModel):
    contract_id: Literal["room16.rfc0011.source_snapshot_fact_inventory_ir"] = (
        "room16.rfc0011.source_snapshot_fact_inventory_ir"
    )
    contract_version: Literal[1] = 1
    ticker: str
    as_of_date: str
    source_snapshot_sha256: str = Field(pattern=SHA256)
    candidates: tuple[RawFactCandidateIR, ...]
    exclusions: tuple[ExcludedRawFactCandidateIR, ...]
    dedupe_receipt: RawFactDedupeReceiptIR
    inventory_sha256: str = Field(pattern=SHA256)

    @classmethod
    def create(cls, **values: object) -> "SourceSnapshotFactInventoryIR":
        candidates = tuple(sorted(values.pop("candidates"), key=lambda item: item.candidate_id))
        exclusions = tuple(
            sorted(values.pop("exclusions"), key=lambda item: item.exclusion_sha256)
        )
        body = {
            "contract_id": "room16.rfc0011.source_snapshot_fact_inventory_ir",
            "contract_version": 1,
            **values,
            "candidates": [item.model_dump(mode="json") for item in candidates],
            "exclusions": [item.model_dump(mode="json") for item in exclusions],
        }
        return cls(**body, inventory_sha256=sha256_json(body))

    @model_validator(mode="after")
    def verify_inventory(self) -> "SourceSnapshotFactInventoryIR":
        ids = tuple(item.candidate_id for item in self.candidates)
        if ids != tuple(sorted(ids)) or len(ids) != len(set(ids)):
            raise ValueError("raw fact candidates must be unique and sorted")
        if sha256_json(_body(self, "inventory_sha256")) != self.inventory_sha256:
            raise ValueError("raw fact inventory self-hash mismatch")
        return self


def _artifact_payload(base: SharedBaseInputIR, relative_path: str, expected_sha: str) -> Any:
    root = Path(base.snapshot_root).resolve()
    target = (root / relative_path).resolve()
    if root not in target.parents or not target.is_file():
        raise ValueError("R4_RAW_INVENTORY_ARTIFACT_MISSING")
    payload = target.read_bytes()
    if hashlib.sha256(payload).hexdigest() != expected_sha:
        raise ValueError("R4_RAW_INVENTORY_ARTIFACT_HASH_MISMATCH")
    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError("R4_RAW_INVENTORY_JSON_INVALID") from exc


def build_source_snapshot_fact_inventory(
    base: SharedBaseInputIR,
) -> SourceSnapshotFactInventoryIR:
    """Parse all eligible raw CompanyFacts/market observations without latest collapse."""

    snapshot = base.snapshot_ir
    artifacts = {item.snapshot_id: item for item in snapshot.artifacts}
    receipts = {item.receipt_id: item for item in snapshot.retrieval_receipts}
    candidates: list[RawFactCandidateIR] = []
    exclusions: list[ExcludedRawFactCandidateIR] = []
    for disposition in snapshot.source_dispositions:
        receipt = receipts[disposition.receipt_id]
        for snapshot_id in disposition.snapshot_ids:
            artifact = artifacts[snapshot_id]
            payload = _artifact_payload(base, artifact.path, artifact.sha256)
            facts = payload.get("facts") if isinstance(payload, dict) else None
            if isinstance(facts, dict):
                for namespace, concepts in sorted(facts.items()):
                    if not isinstance(concepts, dict):
                        continue
                    for concept, definition in sorted(concepts.items()):
                        if not isinstance(definition, dict):
                            continue
                        units = definition.get("units")
                        if not isinstance(units, dict):
                            continue
                        label = str(definition.get("label") or concept)
                        for unit, observations in sorted(units.items()):
                            if not isinstance(observations, list):
                                continue
                            for observation in observations:
                                if not isinstance(observation, dict) or "val" not in observation:
                                    continue
                                end = str(observation.get("end") or "")
                                filed = str(observation.get("filed") or "")
                                reasons = []
                                if not end:
                                    reasons.append("PERIOD_END_MISSING")
                                if not filed:
                                    reasons.append("FILED_DATE_MISSING")
                                if filed and filed > base.as_of_date:
                                    reasons.append("FILED_AFTER_AS_OF")
                                if end and end > base.as_of_date:
                                    reasons.append("PERIOD_END_AFTER_AS_OF")
                                if reasons:
                                    exclusions.append(
                                        ExcludedRawFactCandidateIR.create(
                                            source_artifact_sha256=artifact.sha256,
                                            namespace=str(namespace),
                                            concept=str(concept),
                                            unit=str(unit),
                                            end_or_null=end or None,
                                            filed_or_null=filed or None,
                                            reason_codes=tuple(reasons),
                                        )
                                    )
                                    continue
                                start = str(observation.get("start") or "") or None
                                candidates.append(
                                    RawFactCandidateIR.create(
                                        source_snapshot_sha256=base.source_snapshot_sha256,
                                        source_artifact_sha256=artifact.sha256,
                                        namespace=str(namespace),
                                        concept=str(concept),
                                        label=label,
                                        value=_value_text(observation["val"]),
                                        unit=str(unit),
                                        start_or_null=start,
                                        end=end,
                                        filed=filed,
                                        form=str(observation.get("form") or ""),
                                        frame_or_null=str(observation.get("frame") or "") or None,
                                        accession_or_null=(
                                            str(observation.get("accn") or "") or None
                                        ),
                                        fy_or_null=observation.get("fy"),
                                        fp_or_null=str(observation.get("fp") or "") or None,
                                        source_id=receipt.source_id,
                                        provider_id=receipt.provider_id,
                                        source_kind="companyfacts",
                                        preliminary_duration_role=_duration_role(start, end),
                                    )
                                )
            records = payload if isinstance(payload, list) else None
            if isinstance(payload, dict):
                records = payload.get("records")
            if isinstance(records, list):
                for row in records:
                    if not isinstance(row, dict) or "date" not in row or "close" not in row:
                        continue
                    end = str(row["date"])
                    if end > base.as_of_date:
                        exclusions.append(
                            ExcludedRawFactCandidateIR.create(
                                source_artifact_sha256=artifact.sha256,
                                namespace="market",
                                concept="LatestMarketClose",
                                unit="USD",
                                end_or_null=end,
                                filed_or_null=end,
                                reason_codes=("PERIOD_END_AFTER_AS_OF",),
                            )
                        )
                        continue
                    candidates.append(
                        RawFactCandidateIR.create(
                            source_snapshot_sha256=base.source_snapshot_sha256,
                            source_artifact_sha256=artifact.sha256,
                            namespace="market",
                            concept="LatestMarketClose",
                            label="Latest market close",
                            value=_value_text(row["close"]),
                            unit="USD",
                            start_or_null=None,
                            end=end,
                            filed=end,
                            form="market",
                            frame_or_null=None,
                            accession_or_null=None,
                            fy_or_null=None,
                            fp_or_null=None,
                            source_id=receipt.source_id,
                            provider_id=receipt.provider_id,
                            source_kind="market_price",
                            preliminary_duration_role="INSTANT",
                        )
                    )
    unique: dict[str, RawFactCandidateIR] = {}
    duplicates: list[str] = []
    for candidate in candidates:
        if candidate.candidate_id in unique:
            duplicates.append(candidate.candidate_id)
        else:
            unique[candidate.candidate_id] = candidate
    dedupe = RawFactDedupeReceiptIR.create(
        input_candidate_count=len(candidates),
        output_candidate_count=len(unique),
        duplicate_count=len(duplicates),
        duplicate_candidate_ids=tuple(sorted(duplicates)),
    )
    return SourceSnapshotFactInventoryIR.create(
        ticker=base.ticker,
        as_of_date=base.as_of_date,
        source_snapshot_sha256=base.source_snapshot_sha256,
        candidates=tuple(unique.values()),
        exclusions=tuple(exclusions),
        dedupe_receipt=dedupe,
    )
