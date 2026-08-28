"""Generic supplemental reported-label profiles."""

from __future__ import annotations

from research_agent.compiler_foundation.canonical import sha256_json

OBSERVATION_REGISTRY = {
    "contract_id": "room16.alpha.shared_observation_registry",
    "contract_version": 1,
    "labels": {
        "reported_affo": ["adjusted funds from operations (affo)", "affo"],
        "reported_core_ffo": ["core ffo"],
        "reported_ffo": [
            "ffo attributable to common stockholders",
            "funds from operations",
        ],
        "rpo": ["remaining performance obligation", "total rpo"],
        "crpo": ["current remaining performance obligation", "current rpo", "crpo"],
        "efficiency_ratio": ["efficiency ratio"],
        "guidance": ["guidance", "outlook"],
        "net_interest_margin": ["net interest margin", "nim"],
        "occupancy": ["occupancy", "leased percentage"],
        "production_volume": ["production volume", "oil-equivalent production", "net production"],
        "rotce": ["return on tangible common equity", "rotce"],
        "same_store_noi": ["same store noi", "same-store noi", "net operating income"],
        "segment_operating_results": ["segment earnings", "segment operating"],
    },
}
OBSERVATION_REGISTRY_SHA256 = sha256_json(OBSERVATION_REGISTRY)


def label_profiles() -> dict[str, tuple[str, ...]]:
    labels = OBSERVATION_REGISTRY["labels"]
    return {key: tuple(value) for key, value in labels.items()}
