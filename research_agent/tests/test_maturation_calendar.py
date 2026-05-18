from research_agent.outcomes.maturation_calendar import (
    CALIBRATION_MIN_HORIZON,
    MATURATION_CALENDAR_MODE,
    can_enter_shadow_calibration,
    expected_maturity_date,
    maturation_status,
    maturation_window,
    packet_maturation_status,
)
from research_agent.outcomes.outcome_packet import (
    calculate_outcome_packets,
    load_outcome_fixtures,
    packet_by_horizon,
)
from research_agent.outcomes.verify_outcome_schema import DEFAULT_FIXTURE_DIR


def _fixture(scenario_id):
    fixtures = {fixture.scenario_id: fixture for fixture in load_outcome_fixtures(DEFAULT_FIXTURE_DIR)}
    return fixtures[scenario_id]


def test_naive_calendar_maturity_dates_for_all_horizons():
    assert expected_maturity_date("2026-05-01", "5D").isoformat() == "2026-05-06"
    assert expected_maturity_date("2026-05-01", "10D").isoformat() == "2026-05-11"
    assert expected_maturity_date("2026-05-01", "20D").isoformat() == "2026-05-21"
    assert expected_maturity_date("2026-05-01", "60D").isoformat() == "2026-06-30"


def test_pending_before_expected_maturity_date():
    assert maturation_status("2026-05-01", "5D", "2026-05-05") == "pending"


def test_matured_on_expected_maturity_date():
    window = maturation_window("2026-05-01", "5D", "2026-05-06")

    assert window.status == "matured"
    assert window.expected_maturity_date == "2026-05-06"
    assert window.mode == MATURATION_CALENDAR_MODE


def test_20d_and_60d_remain_pending_until_their_own_window():
    assert maturation_status("2026-05-01", "20D", "2026-05-20") == "pending"
    assert maturation_status("2026-05-01", "20D", "2026-05-21") == "matured"
    assert maturation_status("2026-05-01", "60D", "2026-06-29") == "pending"
    assert maturation_status("2026-05-01", "60D", "2026-06-30") == "matured"


def test_matured_packet_does_not_become_public_ready():
    packets = packet_by_horizon(calculate_outcome_packets(_fixture("matured_5d")))

    assert packets["5D"].status == "matured"
    assert packet_maturation_status(packets["5D"], "2026-05-06") == "matured"
    assert not packets["5D"].public_ready


def test_manual_review_remains_manual_review_after_maturity():
    packets = packet_by_horizon(calculate_outcome_packets(_fixture("manual_review_no_auto_publish")))

    assert packets["5D"].status == "matured"
    assert packets["5D"].decision_type == "manual_review"
    assert packet_maturation_status(packets["5D"], "2026-05-06") == "matured"
    assert not can_enter_shadow_calibration(packets["5D"], "2026-05-06", sample_count=100)


def test_shadow_calibration_requires_matured_60d_and_minimum_samples():
    packets = packet_by_horizon(calculate_outcome_packets(_fixture("matured_5d")))

    assert CALIBRATION_MIN_HORIZON == "60D"
    assert not can_enter_shadow_calibration(packets["5D"], "2026-05-06", sample_count=100)
