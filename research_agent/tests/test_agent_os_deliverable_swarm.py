from dataclasses import replace
from pathlib import Path

from research_agent.ops.deliverable_swarm import (
    REQUIRED_CONTRACT_METADATA,
    REQUIRED_LANES,
    default_deliverable_lanes,
    default_delivery_contracts,
    render_deliverable_swarm_markdown,
    validate_deliverable_swarm,
)


def test_default_deliverable_swarm_contract_is_valid(tmp_path: Path) -> None:
    lanes = default_deliverable_lanes(tmp_path)
    contracts = default_delivery_contracts(tmp_path)
    validation = validate_deliverable_swarm(lanes, contracts, tmp_path)

    assert validation.valid is True
    assert not validation.errors
    assert tuple(lane.lane_id for lane in lanes) == REQUIRED_LANES
    assert len(contracts) >= len(lanes)


def test_orchestrator_routes_to_every_specialist_without_full_mesh(tmp_path: Path) -> None:
    lanes = default_deliverable_lanes(tmp_path)
    by_id = {lane.lane_id: lane for lane in lanes}

    assert set(by_id["orchestrator"].handoff_targets) == set(REQUIRED_LANES) - {"orchestrator"}
    for lane_id, lane in by_id.items():
        if lane_id == "orchestrator":
            continue
        assert "orchestrator" in lane.handoff_targets
        assert len(lane.handoff_targets) < len(REQUIRED_LANES) - 1


def test_external_media_lanes_require_operator_gate(tmp_path: Path) -> None:
    lanes = default_deliverable_lanes(tmp_path)
    by_id = {lane.lane_id: lane for lane in lanes}

    assert by_id["images"].operator_gate_required is True
    assert by_id["video"].operator_gate_required is True

    broken = [
        replace(lane, operator_gate_required=False)
        if lane.lane_id == "images"
        else lane
        for lane in lanes
    ]
    validation = validate_deliverable_swarm(broken, default_delivery_contracts(tmp_path), tmp_path)

    assert validation.valid is False
    assert "external_provider_lane_without_gate:images" in validation.errors


def test_every_lane_artifact_has_output_contract_and_metadata(tmp_path: Path) -> None:
    lanes = default_deliverable_lanes(tmp_path)
    contracts = default_delivery_contracts(tmp_path)
    contract_types = {(contract.lane_id, contract.artifact_type) for contract in contracts}

    for lane in lanes:
        for artifact_type in lane.artifact_types:
            assert (lane.lane_id, artifact_type) in contract_types

    required = set(REQUIRED_CONTRACT_METADATA)
    for contract in contracts:
        assert required.issubset(set(contract.required_metadata))
        assert contract.default_path_template.startswith("outputs/")
        assert "verified" in contract.final_status_values
        assert "blocked" in contract.final_status_values


def test_deliverable_swarm_markdown_renders_validation_and_boundaries(tmp_path: Path) -> None:
    lanes = default_deliverable_lanes(tmp_path)
    contracts = default_delivery_contracts(tmp_path)
    validation = validate_deliverable_swarm(lanes, contracts, tmp_path)
    markdown = render_deliverable_swarm_markdown(lanes, contracts, validation)

    assert "Valid: `true`" in markdown
    assert "`orchestrator`" in markdown
    assert "`research_brief`" in markdown
    assert "`auto_install_external_runtime`" in markdown
