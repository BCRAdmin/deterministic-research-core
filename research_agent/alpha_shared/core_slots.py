"""Generic, hash-bound core coverage slots for archetype reports."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

from pydantic import Field, model_validator

from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.compiler_foundation.contracts import StrictModel

SHA256 = r"^[0-9a-f]{64}$"


class CoreCoverageSlotIR(StrictModel):
    contract_id: Literal["room16.core_coverage_slot_ir"] = "room16.core_coverage_slot_ir"
    contract_version: Literal[1] = 1
    slot_id: str
    label: str
    eligible_metric_ids: tuple[str, ...]
    minimum_resolved_count: int
    maximum_counted: int
    selection_priority: tuple[str, ...]
    preserve_selected_metric_identity: Literal[True] = True
    slot_sha256: str = Field(pattern=SHA256)

    @classmethod
    def create(cls, **values: object) -> "CoreCoverageSlotIR":
        body = {
            "contract_id": "room16.core_coverage_slot_ir",
            "contract_version": 1,
            "preserve_selected_metric_identity": True,
            **values,
        }
        return cls(**body, slot_sha256=sha256_json(body))

    @model_validator(mode="after")
    def verify_slot(self) -> "CoreCoverageSlotIR":
        body = self.model_dump(mode="json", exclude={"slot_sha256"})
        if sha256_json(body) != self.slot_sha256:
            raise ValueError("core coverage slot self-hash mismatch")
        if not self.eligible_metric_ids or self.minimum_resolved_count != 1:
            raise ValueError("core coverage slot must require exactly one resolved choice")
        if self.maximum_counted != 1:
            raise ValueError("core coverage slot may count at most once")
        if set(self.selection_priority) != set(self.eligible_metric_ids):
            raise ValueError("slot selection priority must cover eligible metrics exactly")
        return self


class CoreCoverageSlotResolutionIR(StrictModel):
    contract_id: Literal["room16.core_coverage_slot_resolution_ir"] = (
        "room16.core_coverage_slot_resolution_ir"
    )
    contract_version: Literal[1] = 1
    slot_id: str
    slot_sha256: str = Field(pattern=SHA256)
    status: Literal["RESOLVED", "UNSUPPORTED"]
    selected_metric_id_or_null: str | None
    eligible_resolved_metric_ids: tuple[str, ...]
    counted: int
    selected_metric_identity_preserved: Literal[True] = True
    comparability_grade_or_null: str | None
    cross_issuer_definition_standardized_or_null: bool | None
    resolution_sha256: str = Field(pattern=SHA256)

    @classmethod
    def create(cls, **values: object) -> "CoreCoverageSlotResolutionIR":
        body = {
            "contract_id": "room16.core_coverage_slot_resolution_ir",
            "contract_version": 1,
            "selected_metric_identity_preserved": True,
            **values,
        }
        return cls(**body, resolution_sha256=sha256_json(body))

    @model_validator(mode="after")
    def verify_resolution(self) -> "CoreCoverageSlotResolutionIR":
        body = self.model_dump(mode="json", exclude={"resolution_sha256"})
        if sha256_json(body) != self.resolution_sha256:
            raise ValueError("core slot resolution self-hash mismatch")
        if self.status == "RESOLVED" and (
            self.selected_metric_id_or_null is None or self.counted != 1
        ):
            raise ValueError("resolved core slot must preserve one selected metric")
        if self.status == "UNSUPPORTED" and (
            self.selected_metric_id_or_null is not None or self.counted != 0
        ):
            raise ValueError("unsupported core slot cannot count a metric")
        return self


REIT_OPERATING_PERFORMANCE_GRADES: dict[str, tuple[str, bool]] = {
    "reported_ffo": ("NAREIT_OR_EXPLICIT_FFO", True),
    "reported_core_ffo": ("ISSUER_ADJUSTED_FFO", False),
    "reported_affo": ("ISSUER_DEFINED_NONSTANDARD", False),
}


def _single_metric_slot(metric_id: str) -> CoreCoverageSlotIR:
    return CoreCoverageSlotIR.create(
        slot_id=metric_id,
        label=metric_id,
        eligible_metric_ids=(metric_id,),
        minimum_resolved_count=1,
        maximum_counted=1,
        selection_priority=(metric_id,),
    )


def required_core_slots(
    profile_id: str, legacy_required_metrics: tuple[str, ...]
) -> tuple[CoreCoverageSlotIR, ...]:
    """Return generic singleton slots, except for the additive REIT v2 policy."""

    if profile_id != "reit":
        return tuple(_single_metric_slot(metric_id) for metric_id in legacy_required_metrics)
    return (
        _single_metric_slot("revenue"),
        _single_metric_slot("net_income"),
        CoreCoverageSlotIR.create(
            slot_id="reit_operating_performance_measure",
            label="REIT operating performance measure",
            eligible_metric_ids=("reported_ffo", "reported_core_ffo", "reported_affo"),
            minimum_resolved_count=1,
            maximum_counted=1,
            selection_priority=("reported_ffo", "reported_core_ffo", "reported_affo"),
        ),
        _single_metric_slot("operating_cash_flow"),
        _single_metric_slot("total_debt"),
    )


def resolve_core_slots(
    slots: tuple[CoreCoverageSlotIR, ...], metrics_by_id: Mapping[str, Any]
) -> tuple[CoreCoverageSlotResolutionIR, ...]:
    resolutions = []
    for slot in slots:
        available = tuple(
            metric_id for metric_id in slot.selection_priority if metric_id in metrics_by_id
        )
        selected = available[0] if available else None
        grade: str | None = None
        standardized: bool | None = None
        if slot.slot_id == "reit_operating_performance_measure" and selected is not None:
            grade, standardized = REIT_OPERATING_PERFORMANCE_GRADES[selected]
        resolutions.append(
            CoreCoverageSlotResolutionIR.create(
                slot_id=slot.slot_id,
                slot_sha256=slot.slot_sha256,
                status="RESOLVED" if selected is not None else "UNSUPPORTED",
                selected_metric_id_or_null=selected,
                eligible_resolved_metric_ids=available,
                counted=1 if selected is not None else 0,
                comparability_grade_or_null=grade,
                cross_issuer_definition_standardized_or_null=standardized,
            )
        )
    return tuple(resolutions)


def core_slot_registry(profiles: Mapping[str, tuple[str, ...]]) -> dict[str, object]:
    body = {
        "contract_id": "room16.core_coverage_slot_registry",
        "contract_version": 1,
        "profiles": {
            profile_id: [
                item.model_dump(mode="json")
                for item in required_core_slots(profile_id, required_metrics)
            ]
            for profile_id, required_metrics in sorted(profiles.items())
        },
        "ticker_specific_rules": False,
    }
    return {**body, "registry_sha256": sha256_json(body)}
