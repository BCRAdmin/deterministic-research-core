import pytest

from research_agent.outcomes.outcome_packet import (
    calculate_outcome_packets,
    load_outcome_fixtures,
    packet_by_horizon,
)
from research_agent.outcomes.verify_outcome_schema import (
    DEFAULT_FIXTURE_DIR,
    verify_outcome_schema_fixture_dir,
)


def _fixture(scenario_id):
    fixtures = {fixture.scenario_id: fixture for fixture in load_outcome_fixtures(DEFAULT_FIXTURE_DIR)}
    return fixtures[scenario_id]


def test_outcome_schema_verifier_accepts_golden_fixtures():
    assert verify_outcome_schema_fixture_dir(DEFAULT_FIXTURE_DIR) == []


def test_pending_5d_status_uses_fixture_observation_count():
    packets = packet_by_horizon(calculate_outcome_packets(_fixture("pending_5d")))

    assert packets["5D"].status == "pending"
    assert packets["5D"].observed_return is None
    assert "needs_5_future_trading_observations" in packets["5D"].notes


def test_matured_5d_calculates_benchmark_delta():
    packets = packet_by_horizon(calculate_outcome_packets(_fixture("matured_5d")))

    assert packets["5D"].status == "matured"
    assert packets["5D"].observed_return == pytest.approx(0.1)
    assert packets["5D"].benchmark_return == pytest.approx(0.05)
    assert packets["5D"].delta_to_benchmark == pytest.approx(0.05)
    assert packets["10D"].status == "pending"


def test_missing_benchmark_blocks_delta_as_data_unavailable():
    packets = packet_by_horizon(calculate_outcome_packets(_fixture("missing_benchmark")))

    assert packets["5D"].status == "data_unavailable"
    assert packets["5D"].benchmark_return is None
    assert "benchmark_basis_price_unavailable" in packets["5D"].notes


def test_missing_instrument_data_is_unavailable():
    packets = packet_by_horizon(calculate_outcome_packets(_fixture("data_unavailable")))

    assert packets["5D"].status == "data_unavailable"
    assert packets["5D"].observed_return is None
    assert "instrument_price_history_unavailable" in packets["5D"].notes


def test_invalidated_source_blocks_all_horizons():
    packets = calculate_outcome_packets(_fixture("invalidated_source"))

    assert {packet.status for packet in packets} == {"invalidated"}
    assert all("fixture_source_hash_mismatch" in packet.notes for packet in packets)


def test_manual_review_never_becomes_public_ready():
    packets = packet_by_horizon(calculate_outcome_packets(_fixture("manual_review_no_auto_publish")))

    assert packets["5D"].status == "matured"
    assert packets["5D"].decision_type == "manual_review"
    assert packets["5D"].manual_review_reason == "MISSING_FCF_SUPPORT_FOR_ACCUMULATE"
    assert not packets["5D"].public_ready
    assert "manual_review_remains_binding" in packets["5D"].notes


def test_no_live_fetch_mode_is_enforced():
    with pytest.raises(RuntimeError, match="live fetch is disabled"):
        calculate_outcome_packets(_fixture("matured_5d"), no_live_fetch=False)
