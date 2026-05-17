import json
from pathlib import Path

from research_agent.batch.batch_config import BatchConfig, BatchTickerConfig
from research_agent.batch.batch_runner import BatchRunner
from research_agent.batch.freshness import STALE_PRICE_BASIS_FOR_CURRENT_REPORT, evaluate_price_freshness
from research_agent.batch.source_coverage import evaluate_minimum_viable_data


class PriceDatedPipelineRunner:
    def __init__(self, price_basis_date: str):
        self.price_basis_date = price_basis_date

    def run(self, ticker, as_of_date, mode, output_dir):
        target = Path(output_dir)
        target.mkdir(parents=True, exist_ok=True)
        data_packet = target / "data_packet.json"
        data_packet.write_text(
            json.dumps({"price_basis": {"date": self.price_basis_date}}),
            encoding="utf-8",
        )
        quality = target / "quality_score.json"
        quality.write_text(
            json.dumps({"total_score": 95, "publishable": True}),
            encoding="utf-8",
        )
        return {
            "output_path": str(target),
            "artifacts": {
                "data_packet.json": str(data_packet),
                "quality_score.json": str(quality),
            },
            "quality_score": 95,
            "publishable": True,
            "final_rating": "Hold",
            "preferred_rating": "Hold",
        }


def test_old_price_basis_blocks_current_research():
    freshness = evaluate_price_freshness(
        "2026-05-05",
        batch_mode="current_research",
        reference_date="2026-05-17",
    )

    assert freshness.current_report_allowed is False
    assert freshness.historical_qa_only is True
    assert freshness.data_freshness_status == "stale_price_basis"
    assert freshness.issue_code == STALE_PRICE_BASIS_FOR_CURRENT_REPORT


def test_old_price_basis_allowed_only_as_historical_guardrail_test():
    freshness = evaluate_price_freshness(
        "2026-05-05",
        batch_mode="historical_guardrail_test",
        reference_date="2026-05-17",
    )

    assert freshness.current_report_allowed is False
    assert freshness.historical_qa_only is True
    assert freshness.data_freshness_status == "historical_qa_stale_price_basis"
    assert freshness.issue_code is None


def test_fresh_price_basis_allows_current_research():
    freshness = evaluate_price_freshness(
        "2026-05-15",
        batch_mode="current_research",
        reference_date="2026-05-17",
    )

    assert freshness.current_report_allowed is True
    assert freshness.historical_qa_only is False
    assert freshness.stale_price_basis is False


def test_batch_runner_routes_stale_current_research_to_manual_review(tmp_path):
    config = BatchConfig(
        batch_id="freshness_current",
        as_of_date="2026-05-17",
        batch_mode="current_research",
        freshness_reference_date="2026-05-17",
        pipeline_version="test",
        output_dir=str(tmp_path),
        tickers=[BatchTickerConfig(ticker="MSFT")],
    )

    manifest = BatchRunner(config, pipeline_runner=PriceDatedPipelineRunner("2026-05-05")).run()
    item = manifest.items[0]
    dashboard = json.loads((tmp_path / "freshness_current" / "dashboard_status.json").read_text(encoding="utf-8"))

    assert item.status == "manual_review"
    assert item.publishable is False
    assert item.current_report_allowed is False
    assert item.stale_price_basis is True
    assert dashboard["items"][0]["data_freshness_status"] == "stale_price_basis"
    assert dashboard["summary"]["current_report_allowed_count"] == 0


def test_batch_runner_marks_historical_guardrail_without_blocking_qa_status(tmp_path):
    config = BatchConfig(
        batch_id="freshness_historical",
        as_of_date="2026-05-17",
        batch_mode="historical_guardrail_test",
        freshness_reference_date="2026-05-17",
        pipeline_version="test",
        output_dir=str(tmp_path),
        tickers=[BatchTickerConfig(ticker="MSFT")],
    )

    manifest = BatchRunner(config, pipeline_runner=PriceDatedPipelineRunner("2026-05-05")).run()
    item = manifest.items[0]
    dashboard = json.loads((tmp_path / "freshness_historical" / "dashboard_status.json").read_text(encoding="utf-8"))

    assert item.status == "passed"
    assert item.current_report_allowed is False
    assert item.historical_qa_only is True
    assert item.counts["current_report_blocked_by_freshness_count"] == 0
    assert dashboard["items"][0]["data_freshness_status"] == "historical_qa_stale_price_basis"
    assert dashboard["summary"]["historical_qa_only_count"] == 1


def test_minimum_viable_data_gate_requires_price_and_financials():
    result = evaluate_minimum_viable_data(
        expected_bucket="EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH",
        price_source_present=False,
        cik_present=False,
        companyfacts_present=False,
        canonical_financials_present=False,
        current_period_evidence_present=False,
        news_fallback_present=False,
    )

    assert result["minimum_viable_report_possible"] is False
    assert "price" in result["missing_minimum_inputs"]
    assert "revenue / canonical financials" in result["missing_minimum_inputs"]
    assert "backlog/contracts/execution context" in result["missing_minimum_inputs"]

