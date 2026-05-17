from research_agent.e2e.e2e_runner import E2ERunner
from research_agent.e2e.golden_expectations import build_golden_case


def test_e2e_amzn_expected_rating_corridor(tmp_path):
    result = E2ERunner(tmp_path).run_case(build_golden_case("amzn_2026_05_01"))

    assert result.passed
    assert result.decision_packet.rating_permission.preferred_rating.value == "Hold"
    assert "Sell" in {rating.value for rating in result.decision_packet.rating_permission.blocked_ratings}
    assert "Strong Buy" in {rating.value for rating in result.decision_packet.rating_permission.blocked_ratings}
    assert result.initial_audit.has_issue("NO_NEWS_WITH_AVAILABLE_SOURCES")
    assert not result.final_audit.has_blocking_errors
