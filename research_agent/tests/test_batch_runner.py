import json
from pathlib import Path

from research_agent.batch.batch_config import BatchConfig, BatchTickerConfig
from research_agent.batch.batch_runner import BatchRunner, _counts_from_artifacts


class FakePipelineRunner:
    def run(self, ticker, as_of_date, mode, output_dir):
        if ticker == "FAIL":
            raise RuntimeError("validation failed: missing primary source")
        target = Path(output_dir)
        target.mkdir(parents=True, exist_ok=True)
        (target / "final_report.md").write_text(f"# {ticker} report", encoding="utf-8")
        (target / "quality_score.json").write_text(
            json.dumps({"total_score": 90, "publishable": True}),
            encoding="utf-8",
        )
        return {
            "output_path": str(target),
            "quality_score": 90,
            "publishable": True,
            "final_rating": "Hold",
            "preferred_rating": "Hold",
        }


class MissingDataPipelineRunner:
    def run(self, ticker, as_of_date, mode, output_dir):
        if ticker == "NODATA":
            raise FileNotFoundError("missing price data for NODATA")
        return {
            "output_path": output_dir,
            "quality_score": 90,
            "publishable": True,
            "final_rating": "Hold",
            "preferred_rating": "Hold",
        }


def test_batch_runner_continues_after_one_failure(tmp_path):
    config = BatchConfig(
        batch_id="batch_test",
        as_of_date="2026-05-06",
        pipeline_version="test",
        output_dir=str(tmp_path),
        tickers=[
            BatchTickerConfig(ticker="AMZN"),
            BatchTickerConfig(ticker="FAIL"),
            BatchTickerConfig(ticker="NVDA"),
        ],
    )

    manifest = BatchRunner(config, pipeline_runner=FakePipelineRunner()).run()

    assert len(manifest.items) == 3
    assert any(item.status == "failed" for item in manifest.items)
    assert sum(1 for item in manifest.items if item.status == "passed") == 2
    assert (tmp_path / "batch_test" / "batch_manifest.json").exists()
    assert (tmp_path / "batch_test" / "dashboard_status.json").exists()
    assert (tmp_path / "batch_test" / "pilot_review.md").exists()

    failed = next(item for item in manifest.items if item.ticker == "FAIL")
    assert failed.failure_type == "validation_error"


def test_batch_runner_routes_missing_source_inputs_to_data_unavailable(tmp_path):
    config = BatchConfig(
        batch_id="batch_data_unavailable",
        as_of_date="2026-05-06",
        pipeline_version="test",
        output_dir=str(tmp_path),
        tickers=[
            BatchTickerConfig(ticker="OK"),
            BatchTickerConfig(ticker="NODATA"),
        ],
    )

    manifest = BatchRunner(config, pipeline_runner=MissingDataPipelineRunner()).run()
    data_unavailable = next(item for item in manifest.items if item.ticker == "NODATA")
    dashboard = json.loads((tmp_path / "batch_data_unavailable" / "dashboard_status.json").read_text(encoding="utf-8"))

    assert data_unavailable.status == "data_unavailable"
    assert data_unavailable.failure_type == "data_error"
    assert data_unavailable.publishable is None
    assert dashboard["summary"]["data_unavailable"] == 1
    assert dashboard["items"][1]["display_status"] == "Data unavailable"


def test_batch_runner_writes_dashboard_status(tmp_path):
    config = BatchConfig(
        batch_id="batch_dashboard",
        as_of_date="2026-05-06",
        pipeline_version="test",
        output_dir=str(tmp_path),
        tickers=[BatchTickerConfig(ticker="AMZN")],
    )

    BatchRunner(config, pipeline_runner=FakePipelineRunner()).run()
    dashboard = json.loads((tmp_path / "batch_dashboard" / "dashboard_status.json").read_text(encoding="utf-8"))

    assert dashboard["summary"]["total"] == 1
    assert dashboard["summary"]["passed"] == 1
    assert dashboard["items"][0]["artifacts"]["final_report.md"].endswith("final_report.md")


def test_batch_runner_counts_deeptech_audit_codes_without_aborting(tmp_path):
    audit_path = tmp_path / "audit_report.json"
    audit_path.write_text(
        json.dumps(
            {
                "issues": [
                    {
                        "severity": "warning",
                        "code": "SPECULATIVE_DEEP_TECH_MANUAL_REVIEW_PROFILE",
                        "message": "Manual review profile active.",
                    },
                    {
                        "severity": "warning",
                        "code": "ORDER_MATERIALITY_MISSING",
                        "message": "Backlog materiality needs review.",
                    },
                    {
                        "severity": "warning",
                        "code": "EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH_MANUAL_REVIEW_PROFILE",
                        "message": "Early-commercial capital-intensive tech needs review.",
                    },
                    {
                        "severity": "error",
                        "code": "EXTREME_VALUATION_REQUIRES_REVIEW",
                        "message": "Extreme valuation needs review.",
                    },
                    {
                        "severity": "error",
                        "code": "TRUE_VALUATION_ANOMALY",
                        "message": "True valuation anomaly needs review.",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    counts = _counts_from_artifacts({"audit_report.json": str(audit_path)})

    assert counts["speculative_deep_tech_profile_count"] == 1
    assert counts["order_materiality_missing_count"] == 1
    assert counts["early_commercial_capital_intensive_tech_count"] == 1
    assert counts["extreme_valuation_review"] == 1
    assert counts["true_valuation_anomaly"] == 1
    assert counts["true_anomaly"] == 2


def test_batch_runner_indexes_report_manifest_metadata_artifacts(tmp_path):
    class ManifestPipelineRunner:
        def run(self, ticker, as_of_date, output_dir):
            target = Path(output_dir)
            packet_dir = target / "packets"
            report_dir = target / "reports" / ticker / as_of_date
            packet_dir.mkdir(parents=True, exist_ok=True)
            report_dir.mkdir(parents=True, exist_ok=True)
            for name in [
                "data_packet.json",
                "metrics_packet.json",
                "validation_report.json",
                "decision_packet.json",
                "evidence_ledger.json",
                "canonical_financials.json",
            ]:
                (packet_dir / name).write_text("{}", encoding="utf-8")
            (packet_dir / "canonical_financials.json").write_text(
                "{\"metrics\": [{\"metric_name\": \"revenue\"}]}",
                encoding="utf-8",
            )
            (packet_dir / "reconciliation_report.md").write_text("# reconciliation", encoding="utf-8")
            (report_dir / "quality_score.json").write_text("{\"total_score\": 90, \"publishable\": true}", encoding="utf-8")
            (target / "final_report.md").write_text("# report", encoding="utf-8")
            manifest = {
                "quality_score": 90,
                "publishable": True,
                "final_rating": "Hold",
                "preferred_rating": "Hold",
                "final_report_path": str(target / "final_report.md"),
                "metrics_packet_path": str(packet_dir / "metrics_packet.json"),
                "validation_report_path": str(packet_dir / "validation_report.json"),
                "decision_packet_path": str(packet_dir / "decision_packet.json"),
                "metadata": {
                    "data_packet_path": str(packet_dir / "data_packet.json"),
                    "quality_score_path": str(report_dir / "quality_score.json"),
                    "evidence_ledger_path": str(packet_dir / "evidence_ledger.json"),
                    "canonical_financials_path": str(packet_dir / "canonical_financials.json"),
                    "reconciliation_report_path": str(packet_dir / "reconciliation_report.md"),
                },
            }
            manifest_path = report_dir / "report_manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            return {
                "output_path": str(report_dir),
                "artifacts": {"report_manifest.json": str(manifest_path)},
            }

    config = BatchConfig(
        batch_id="batch_manifest_artifacts",
        as_of_date="2026-05-06",
        pipeline_version="test",
        output_dir=str(tmp_path),
        tickers=[BatchTickerConfig(ticker="AMZN")],
    )

    manifest = BatchRunner(config, pipeline_runner=ManifestPipelineRunner()).run()
    artifacts = manifest.items[0].artifacts

    assert "evidence_ledger.json" in artifacts
    assert "reconciliation_report.md" in artifacts
    assert "final_report.md" in artifacts
    assert manifest.items[0].counts["canonical_metrics_created"] == 1


def test_default_batch_runner_uses_manual_packet_fixture_fallback(tmp_path):
    config = BatchConfig(
        batch_id="batch_fixture_fallback",
        as_of_date="2026-05-01",
        pipeline_version="test",
        output_dir=str(tmp_path),
        tickers=[BatchTickerConfig(ticker="NVDA")],
    )

    manifest = BatchRunner(config).run()

    assert manifest.items[0].status == "repaired"
    assert manifest.items[0].quality_score >= 85
    assert manifest.items[0].preferred_rating == "Accumulate"
    assert "final_repaired_report.md" in manifest.items[0].artifacts
