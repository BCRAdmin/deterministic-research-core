import json
from pathlib import Path

from research_agent.compiler_foundation.kernel import load_pass_manifests
from research_agent.productization.contracts import REQUIRED_ARTIFACT_KINDS


ROOT = Path(__file__).parents[2]
CONFIG = ROOT / "research_agent/productization/config"
SEMANTIC_PASSES = ROOT / "research_agent/semantic_compiler/semantic_spine/config/rfc_0003_pass_manifests.json"
PRODUCT_CONFIG = ROOT.parent / "company-dossier-lab/room16-app/config"


def load(name: str):
    return json.loads((CONFIG / name).read_text(encoding="utf-8"))


def test_pass_execution_profile_is_exact_projection_of_frozen_semantic_manifest():
    profile = load("pass_execution_profile_v1.json")
    frozen = load_pass_manifests(SEMANTIC_PASSES)
    expected = [
        {"ordinal": item.ordinal, "pass_id": item.pass_id, "pass_version": item.pass_version, "status": "executed"}
        for item in frozen
    ]
    assert profile["contract_id"] == "room16.compiler.pass_execution_profile"
    assert profile["passes"] == expected
    assert len(expected) == 10


def test_required_artifact_profile_is_complete_and_product_mirrors_are_byte_identical():
    profile = load("required_artifact_profile_v1.json")
    assert [item["artifact_kind"] for item in profile["entries"]] == list(REQUIRED_ARTIFACT_KINDS)
    assert all(item["required_payload_keys"] for item in profile["entries"])
    for research_name, product_name in (
        ("pass_execution_profile_v1.json", "room16_pass_execution_profile_v1.json"),
        ("required_artifact_profile_v1.json", "room16_required_artifact_profile_v1.json"),
    ):
        assert (CONFIG / research_name).read_bytes() == (PRODUCT_CONFIG / product_name).read_bytes()
