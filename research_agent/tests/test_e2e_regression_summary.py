import json

from research_agent.e2e.e2e_runner import E2ERunner
from research_agent.e2e.golden_expectations import build_all_golden_cases
from research_agent.e2e.regression_summary import build_regression_summary


def test_e2e_regression_summary_outputs_json_and_markdown(tmp_path):
    runner = E2ERunner(tmp_path)
    results = runner.run_cases(build_all_golden_cases(), run_id="e2e_test_run")
    summary = build_regression_summary(results, run_id="e2e_test_run")

    assert summary.cases_total == 4
    assert summary.cases_passed == 4
    assert summary.cases_failed == 0
    assert summary.repair_rate == 1.0
    assert (tmp_path / "e2e_summary.json").exists()
    assert (tmp_path / "e2e_summary.md").exists()

    payload = json.loads((tmp_path / "e2e_summary.json").read_text(encoding="utf-8"))
    assert payload["run_id"] == "e2e_test_run"
    assert "E2E Regression Summary" in (tmp_path / "e2e_summary.md").read_text(encoding="utf-8")


def test_e2e_case_artifacts_are_written(tmp_path):
    runner = E2ERunner(tmp_path)
    result = runner.run_case(build_all_golden_cases()[0])
    case_dir = tmp_path / result.case_id

    assert (case_dir / "final_repaired_report.md").exists()
    assert (case_dir / "audit_report.json").exists()
    assert (case_dir / "quality_score.json").exists()
    assert (case_dir / "decision_packet.json").exists()
    assert (case_dir / "evidence_report.md").exists()
    assert (case_dir / "acceptance_report.md").exists()
