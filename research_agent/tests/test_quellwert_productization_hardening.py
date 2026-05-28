from pathlib import Path

from research_agent.ops.quellwert_productization_hardening import (
    ProductizationAuditPaths,
    build_productization_audit,
)


def test_quellwert_productization_audit_reports_external_blocked_state():
    audit = build_productization_audit(
        ProductizationAuditPaths(
            closure_root=Path("outputs/quellwert_room16_operating/closure_sprint_2026-05-28"),
            launch_pack_root=Path("outputs/quellwert_room16_operating/launch_pack_2026-05-27"),
            output_root=Path("/tmp/unused_quellwert_audit"),
        )
    )

    assert audit["status"] == "local_hardening_pass_external_blocked"
    assert audit["external_launch_go"] is False
    assert audit["outcome_readiness_result"]["status"] == "pass"
    assert audit["p0_open_gated"]
    assert audit["p1_open_gated"]
