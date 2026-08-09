import json
from pathlib import Path

from research_agent.decision.rating_engine import build_decision_packet
from research_agent.research_core.models.metrics_packet import MetricsPacket
from research_agent.research_core.models.validation_report import ValidationReport


FIXTURES = Path(__file__).parent / "fixtures"


def _load_json(fixture_name, filename):
    return json.loads((FIXTURES / fixture_name / filename).read_text(encoding="utf-8"))


def test_decision_packet_records_triggered_rules():
    packet = build_decision_packet(
        metrics_packet=MetricsPacket(**_load_json("mdb_2026_05_01", "metrics_packet.json")),
        validation_report=ValidationReport(**_load_json("mdb_2026_05_01", "validation_report.json")),
    )

    assert "SBC_TO_REVENUE_GT_20" not in packet.triggered_rules
    assert "REVENUE_GROWTH_GT_30" not in packet.triggered_rules
    assert "REVENUE_GROWTH_GT_15" not in packet.triggered_rules
    assert "REVENUE_GROWTH_LT_5" not in packet.triggered_rules
    assert "FCF_MARGIN_GT_25" not in packet.triggered_rules
    assert "OPERATING_MARGIN_GT_10" not in packet.triggered_rules
    assert "NET_CASH_POSITIVE" not in packet.triggered_rules
    assert "TREND_STATE_BEARISH" not in packet.triggered_rules
    assert packet.signal_scores.technical_score == 0
    assert packet.signal_scores.technical_status == "partial"
    assert "PRICE_BELOW_200SMA" not in packet.triggered_rules
    assert "BEARISH_MA_ALIGNMENT" not in packet.triggered_rules
    assert "DEATH_CROSS" not in packet.triggered_rules
    assert "FORWARD_EPS_GUIDANCE_MISMATCH" not in packet.triggered_rules
    assert packet.signal_scores.risk_score == 0
    assert packet.signal_scores.risk_status == "not_measured"
    assert packet.key_risks == [
        "Company risk score: not measured by the current decision model."
    ]
    assert packet.signal_scores.valuation_score == 0
    assert packet.signal_scores.valuation_status == "unbenchmarked"
    assert packet.score_version == "v1"
    assert packet.calibration_mode == "live"
