from research_agent.e2e.e2e_runner import E2ERunner
from research_agent.e2e.golden_expectations import build_golden_case


def test_e2e_mdb_causality_softened_and_sell_blocked(tmp_path):
    result = E2ERunner(tmp_path).run_case(build_golden_case("mdb_2026_05_01"))

    assert result.passed
    assert result.initial_audit.has_issue("OVERSTATED_CAUSALITY")
    assert not result.final_audit.has_issue("OVERSTATED_CAUSALITY")
    assert "Sell" in {rating.value for rating in result.decision_packet.rating_permission.blocked_ratings}
    assert result.decision_packet.rating_permission.preferred_rating.value in {
        "Tactical Underweight",
        "Tactical Trim",
        "Hold",
    }
