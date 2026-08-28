"""Hash-bound adapters over the four frozen Alpha Development profiles."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from research_agent.alpha_bank.projection import (
    CORE_ORDER as BANK_CORE_ORDER,
    FORMULA_REGISTRY as BANK_FORMULAS,
    MAPPING_REGISTRY as BANK_MAPPING,
    RANKING_PROFILE as BANK_RANKING,
    UNSUPPORTED_METRICS as BANK_UNSUPPORTED,
)
from research_agent.alpha_energy.projection import (
    CORE_ORDER as ENERGY_CORE_ORDER,
    FORMULA_REGISTRY as ENERGY_FORMULAS,
    MAPPING_REGISTRY as ENERGY_MAPPING,
    OPERATING_METRICS_REQUIRING_PRIMARY_TEXT as ENERGY_UNSUPPORTED,
    RANKING_PROFILE as ENERGY_RANKING,
)
from research_agent.alpha_reit.primary_text import UNSUPPORTED_TEXT_METRICS as REIT_UNSUPPORTED
from research_agent.alpha_reit.projection import (
    CORE_ORDER as REIT_CORE_ORDER,
    FORMULA_REGISTRY as REIT_FORMULAS,
    MAPPING_REGISTRY as REIT_MAPPING,
    RANKING_PROFILE as REIT_RANKING,
)
from research_agent.alpha_saas.projection import (
    CORE_ORDER as SAAS_CORE_ORDER,
    FORMULA_REGISTRY as SAAS_FORMULAS,
    MAPPING_REGISTRY as SAAS_MAPPING,
    RANKING_PROFILE as SAAS_RANKING,
    SOURCE_PROFILE as SAAS_SOURCE,
)
from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.compiler_foundation.contracts import StrictModel

from .metric_semantics import METRIC_SEMANTICS_REGISTRY_SHA256, metric_semantics

SHA256 = r"^[0-9a-f]{64}$"
ProfileId = Literal["saas", "reit", "bank", "energy"]
REQUIRED_REPORT_SECTIONS = (
    "identity",
    "as_of",
    "archetype",
    "core_metrics",
    "derived_metrics",
    "important_unsupported_metrics",
    "stale_or_comparative_diagnostics",
    "source_coverage",
    "report_completeness",
    "evidence_lineage",
)

FREEZE_SHA256S: dict[ProfileId, str] = {
    "saas": "063e322929c7a4586e21c8c97e0177516e8870e4f777181c9964042fe5242f0c",
    "reit": "7085404f501c41c103c8057170a15ff2ebda2a1d6e4b9bed2bd0a14e3d83bdd2",
    "bank": "6c1049d53590127bfac582b143df09ca8a885f5c4f87f031b58b1141548df435",
    "energy": "ec8e2b49f19610635034b5d9791f957a95193f7715b2b00bca10c860e2ea4857",
}

_PROFILE_SOURCE: dict[ProfileId, dict[str, Any]] = {
    "saas": {
        "archetype": "Software/SaaS",
        "mapping": SAAS_MAPPING,
        "formulas": SAAS_FORMULAS,
        "ranking": SAAS_RANKING,
        "core_order": SAAS_CORE_ORDER,
        "unsupported": ("crpo", "guidance"),
        "supplemental": SAAS_SOURCE,
    },
    "reit": {
        "archetype": "REIT",
        "mapping": REIT_MAPPING,
        "formulas": REIT_FORMULAS,
        "ranking": REIT_RANKING,
        "core_order": REIT_CORE_ORDER,
        "unsupported": REIT_UNSUPPORTED,
        "supplemental": {},
    },
    "bank": {
        "archetype": "Bank",
        "mapping": BANK_MAPPING,
        "formulas": BANK_FORMULAS,
        "ranking": BANK_RANKING,
        "core_order": BANK_CORE_ORDER,
        "unsupported": BANK_UNSUPPORTED,
        "supplemental": {},
    },
    "energy": {
        "archetype": "Integrated Energy",
        "mapping": ENERGY_MAPPING,
        "formulas": ENERGY_FORMULAS,
        "ranking": ENERGY_RANKING,
        "core_order": ENERGY_CORE_ORDER,
        "unsupported": ENERGY_UNSUPPORTED,
        "supplemental": {},
    },
}

_EXPECTED_REGISTRY_HASHES: dict[ProfileId, dict[str, str]] = {
    "saas": {
        "mapping": "a15023c8953e92b6ecf866469fb4e69507370df0617481a4aeaa225443a0e23b",
        "formula": "a3152b2d04609fb690e6109636a1aa6243ee599dbb8d7503f2637c4f711ff482",
        "ranking": "597e385c734d7dac849a43816f964172eb358d5930c9a7e0dcbc08cf8b5d123b",
    },
    "reit": {
        "mapping": "136e91a1ea6cd439a759812d1273aeb7647c3a477b0b2274e7f704d8cd70fd21",
        "formula": "a389f72644870c716829592e02d43f159cb181df99f7f44899de33589af081c3",
        "ranking": "2574c3635362e302cf04b4ced16aa067063f3ffd7675fa42d763772f0c8cd51f",
    },
    "bank": {
        "mapping": "926f2186f138d9e474fff7ef255e7b3d287e8eece4a95131172500a70c73eb8a",
        "formula": "952bff4a25bf31953536ab958677d416c6638dc28acc58514cdd9fc0e0bf0e48",
        "ranking": "f2247dba60f8cd47ec9754caae27f3cfbf61a995db1965593e4fc3d87440d980",
    },
    "energy": {
        "mapping": "af0ea1389138b46d56548fc792b9b328cfc3799dddbae0d32b09d85cc520c5df",
        "formula": "53f717d81565949bfc5c61f8d714554b01158d5b106d7b8e14e63a3367ef5114",
        "ranking": "81d35ae945d2223de4f3f31884a5d714767347d292cd9b3990fc49ae42d3010e",
    },
}

class ArchetypeMetricDefinitionIR(StrictModel):
    metric_id: str
    approved_concepts: tuple[str, ...]
    period_type: Literal["INSTANT", "DURATION"]
    allowed_units: tuple[str, ...]
    required_core: bool
    derived_only: bool = False


class ArchetypeProfileAdapterIR(StrictModel):
    contract_id: Literal["room16.rfc0011.archetype_profile_adapter_ir"] = (
        "room16.rfc0011.archetype_profile_adapter_ir"
    )
    contract_version: Literal[1] = 1
    archetype_profile_id: ProfileId
    archetype: str
    profile_freeze_sha256: str = Field(pattern=SHA256)
    mapping_registry_sha256: str = Field(pattern=SHA256)
    formula_registry_sha256: str = Field(pattern=SHA256)
    ranking_profile_sha256: str = Field(pattern=SHA256)
    metric_semantics_registry_sha256: str = Field(pattern=SHA256)
    required_core_metrics: tuple[str, ...]
    optional_metrics: tuple[str, ...]
    metric_definitions: tuple[ArchetypeMetricDefinitionIR, ...]
    allowed_safe_formulas: dict[str, Any]
    ranking_order: tuple[str, ...]
    unsupported_metric_definitions: tuple[str, ...]
    required_report_sections: tuple[str, ...]
    ticker_specific_rules: Literal[False] = False
    adapter_sha256: str = Field(pattern=SHA256)

    @classmethod
    def create(cls, **values: object) -> "ArchetypeProfileAdapterIR":
        body = {
            "contract_id": "room16.rfc0011.archetype_profile_adapter_ir",
            "contract_version": 1,
            "ticker_specific_rules": False,
            **values,
        }
        return cls(**body, adapter_sha256=sha256_json(body))

    @model_validator(mode="after")
    def verify_adapter(self) -> "ArchetypeProfileAdapterIR":
        body = self.model_dump(mode="json", exclude={"adapter_sha256"})
        if sha256_json(body) != self.adapter_sha256:
            raise ValueError("archetype profile adapter self-hash mismatch")
        if self.profile_freeze_sha256 != FREEZE_SHA256S[self.archetype_profile_id]:
            raise ValueError("archetype Development freeze binding mismatch")
        return self


def load_archetype_profile(profile_id: ProfileId | str) -> ArchetypeProfileAdapterIR:
    if profile_id not in _PROFILE_SOURCE:
        raise ValueError(f"R4_ARCHETYPE_PROFILE_UNSUPPORTED:{profile_id}")
    typed_id: ProfileId = profile_id  # type: ignore[assignment]
    source = _PROFILE_SOURCE[typed_id]
    observed = {
        "mapping": sha256_json(source["mapping"]),
        "formula": sha256_json(source["formulas"]),
        "ranking": sha256_json(source["ranking"]),
    }
    if observed != _EXPECTED_REGISTRY_HASHES[typed_id]:
        raise ValueError(f"R4_ARCHETYPE_FROZEN_REGISTRY_DRIFT:{profile_id}")
    order = tuple(str(item) for item in source["core_order"])
    required = order[:5]
    mappings = source["mapping"]["metrics"]
    formula_outputs = {
        str(value["output_metric"])
        for value in source["formulas"].get("formulas", {}).values()
    }
    definitions = []
    for metric_id in order:
        semantics = metric_semantics(metric_id)
        if semantics is None:
            raise ValueError(f"R4_METRIC_SEMANTICS_UNSUPPORTED:{profile_id}:{metric_id}")
        concepts = tuple(str(item) for item in mappings.get(metric_id, ()))
        definitions.append(
            ArchetypeMetricDefinitionIR(
                metric_id=metric_id,
                approved_concepts=concepts,
                period_type=semantics.period_type,
                allowed_units=semantics.allowed_units,
                required_core=metric_id in required,
                derived_only=metric_id in formula_outputs,
            )
        )
    return ArchetypeProfileAdapterIR.create(
        archetype_profile_id=typed_id,
        archetype=str(source["archetype"]),
        profile_freeze_sha256=FREEZE_SHA256S[typed_id],
        mapping_registry_sha256=observed["mapping"],
        formula_registry_sha256=observed["formula"],
        ranking_profile_sha256=observed["ranking"],
        metric_semantics_registry_sha256=METRIC_SEMANTICS_REGISTRY_SHA256,
        required_core_metrics=required,
        optional_metrics=order[5:],
        metric_definitions=tuple(definitions),
        allowed_safe_formulas=source["formulas"],
        ranking_order=order,
        unsupported_metric_definitions=tuple(str(item) for item in source["unsupported"]),
        required_report_sections=REQUIRED_REPORT_SECTIONS,
    )


def archetype_profile_registry() -> dict[str, object]:
    profiles = [load_archetype_profile(item).model_dump(mode="json") for item in _PROFILE_SOURCE]
    body = {
        "contract_id": "room16.rfc0011.archetype_profile_adapter_registry",
        "contract_version": 1,
        "profiles": profiles,
        "ticker_specific_rules": False,
    }
    return {**body, "registry_sha256": sha256_json(body)}
