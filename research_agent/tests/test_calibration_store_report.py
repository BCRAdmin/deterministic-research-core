from research_agent.calibration.calibration_report import render_calibration_report, save_calibration_report
from research_agent.calibration.calibration_store import (
    generate_default_rule_weights,
    load_calibration_config,
)
from research_agent.calibration.rule_weight_engine import RuleCalibrationStats


def test_rule_weights_v1_json_can_be_generated(tmp_path):
    path = generate_default_rule_weights(tmp_path)
    record = load_calibration_config(path)

    assert path.name == "rule_weights_v1.json"
    assert record.version == "v1"
    assert "DEATH_CROSS" in record.rules
    assert record.mode == "shadow"


def test_calibration_report_markdown_can_be_generated(tmp_path):
    markdown = render_calibration_report(
        [
            RuleCalibrationStats(
                rule_id="DEATH_CROSS",
                sample_size=41,
                avg_60d_excess_return=-0.062,
                hit_rate_positive_excess_60d=0.32,
                suggested_weight_delta=-0.25,
                confidence="medium",
                recommendation="decrease",
            ),
            RuleCalibrationStats(
                rule_id="RSI_GT_75",
                sample_size=12,
                avg_60d_excess_return=-0.01,
                suggested_weight_delta=0.0,
                confidence="low",
                recommendation="shadow_only",
            ),
        ],
        report_date="2026-06-01",
        live_engine_version="v1",
        shadow_engine_version="v2_shadow",
    )
    path = save_calibration_report(markdown, tmp_path / "reports" / "calibration_report_2026-06-01.md")

    assert path.exists()
    assert "# Calibration Report - 2026-06-01" in markdown
    assert "DEATH_CROSS" in markdown
    assert "Keep calibrated weights in shadow mode" in markdown
