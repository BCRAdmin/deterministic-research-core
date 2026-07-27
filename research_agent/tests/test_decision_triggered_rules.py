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

    assert "SBC_TO_REVENUE_GT_20" in packet.triggered_rules
    assert "PRICE_BELOW_200SMA" in packet.triggered_rules
    assert "BEARISH_MA_ALIGNMENT" in packet.triggered_rules
    assert "DEATH_CROSS" not in packet.triggered_rules
    assert "FORWARD_EPS_GUIDANCE_MISMATCH" in packet.triggered_rules
    assert packet.score_version == "v1"
    assert packet.calibration_mode == "live"
