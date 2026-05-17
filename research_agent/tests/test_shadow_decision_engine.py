import json
from pathlib import Path

from research_agent.calibration.rule_weight_config import DEFAULT_RULE_WEIGHTS
from research_agent.calibration.rule_weight_engine import RuleCalibrationStats, build_shadow_weight_config
from research_agent.calibration.shadow_decision_engine import compare_live_vs_shadow_decision
from research_agent.outcomes.price_outcome import WindowOutcome
from research_agent.research_core.models.metrics_packet import MetricsPacket
from research_agent.research_core.models.validation_report import ValidationReport


FIXTURES = Path(__file__).parent / "fixtures"


def _load_json(fixture_name, filename):
    return json.loads((FIXTURES / fixture_name / filename).read_text(encoding="utf-8"))


def test_shadow_decision_comparison_outputs_both_ratings():
    metrics = MetricsPacket(**_load_json("mdb_2026_05_01", "metrics_packet.json"))
    validation = ValidationReport(**_load_json("mdb_2026_05_01", "validation_report.json"))
    shadow_weights = build_shadow_weight_config(
        DEFAULT_RULE_WEIGHTS,
        [
            RuleCalibrationStats(
                rule_id="DEATH_CROSS",
                sample_size=100,
                avg_60d_excess_return=-0.08,
                suggested_weight_delta=-0.25,
                confidence="high",
                recommendation="decrease",
            )
        ],
        version="v2_shadow",
    )
    outcome_60d = WindowOutcome(
        window="60d",
        start_price=250.83,
        start_date="2026-05-01",
        end_date="2026-07-30",
        end_price=220.0,
        return_pct=-0.123,
        max_drawdown_pct=-0.18,
    )

    comparison = compare_live_vs_shadow_decision(
        report_id="MDB_2026-05-01",
        metrics_packet=metrics,
        validation_report=validation,
        outcome_20d=None,
        outcome_60d=outcome_60d,
        shadow_rule_weights=shadow_weights,
    )

    assert comparison.live_preferred_rating is not None
    assert comparison.shadow_preferred_rating is not None
    assert comparison.live_success_60d is not None
    assert comparison.shadow_success_60d is not None
