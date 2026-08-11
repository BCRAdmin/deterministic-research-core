from research_agent.e2e.e2e_runner import E2ERunner
from research_agent.e2e.golden_expectations import build_golden_case


def test_e2e_nvda_repairs_fcf_and_stays_hold_without_benchmark(tmp_path):
    result = E2ERunner(tmp_path).run_case(build_golden_case("nvda_2026_05_01"))

    assert result.passed
    assert result.initial_audit.has_issue("NUMERIC_MISMATCH", metric="free_cash_flow_ttm")
    assert result.initial_audit.has_issue("PERIOD_MISMATCH", metric="operating_margin")
    assert not result.final_audit.has_issue("NUMERIC_MISMATCH")
    assert result.decision_packet.rating_permission.preferred_rating.value == "Hold"
    assert result.quality_score.total_score >= 80
    assert result.final_status == "manual_review"
