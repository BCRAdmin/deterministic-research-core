from research_agent.e2e.fixture_loader import load_cases_from_path


def test_e2e_cases_directory_loads_smoke_cases():
    cases = load_cases_from_path("research_agent/tests/fixtures/e2e_cases")

    assert {case.ticker for case in cases} == {"AMZN", "NVDA", "DDOG", "MDB"}
    assert all(case.original_report_path.endswith("bad_report.md") for case in cases)
