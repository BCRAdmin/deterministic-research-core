import json
from pathlib import Path

from research_agent.ops.vega_maturity_sprint import (
    VegaMaturitySprintPaths,
    build_vega_maturity_sprint,
    write_vega_maturity_sprint,
)


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_vega_maturity_sprint_keeps_external_and_production_closed(tmp_path):
    productization_path = _write_json(
        tmp_path / "productization.json",
        {
            "status": "local_hardening_pass_external_blocked",
            "external_launch_go": False,
            "p0_open_gated": ["10D outcome remains pending_price_data."],
            "p1_open_gated": ["Production controls still need evidence."],
        },
    )
    report_machine_path = _write_json(
        tmp_path / "report-machine.json",
        {
            "verdict": "pass",
            "checks": [
                {
                    "name": "public_library_ok",
                    "status": "pass",
                    "details": {
                        "summary": {
                            "totalReports": 14,
                            "hiddenByGate": 14,
                            "effectivePublic": 0,
                            "effectiveMember": 0,
                        }
                    },
                }
            ],
        },
    )

    payload = build_vega_maturity_sprint(
        VegaMaturitySprintPaths(
            productization_audit_json=productization_path,
            report_machine_verification_json=report_machine_path,
            output_root=tmp_path / "out",
        )
    )

    assert payload["status"] == "local_maturity_run_pass_operator_gated"
    assert payload["external_ready"] is False
    assert payload["production_ready"] is False
    assert payload["no_external_actions"] is True
    assert payload["summary"]["visibility_effective_public"] == 0
    assert payload["summary"]["visibility_effective_member"] == 0
    assert {item["id"] for item in payload["deliverables"]} == {
        "publishability_contract",
        "observability_baseline",
        "rollback_kill_switch",
        "supply_chain_compliance_minimum",
    }


def test_vega_maturity_sprint_writes_json_and_markdown(tmp_path):
    productization_path = _write_json(
        tmp_path / "productization.json",
        {"status": "local_hardening_pass_external_blocked", "external_launch_go": False},
    )
    report_machine_path = _write_json(
        tmp_path / "report-machine.json",
        {
            "checks": [
                {
                    "name": "public_library_ok",
                    "status": "pass",
                    "details": {"summary": {"effectivePublic": 0, "effectiveMember": 0}},
                }
            ]
        },
    )
    payload = build_vega_maturity_sprint(
        VegaMaturitySprintPaths(
            productization_audit_json=productization_path,
            report_machine_verification_json=report_machine_path,
            output_root=tmp_path / "out",
        )
    )

    json_path, md_path = write_vega_maturity_sprint(payload, output_root=tmp_path / "out")

    assert json_path.exists()
    assert md_path.exists()
    assert json.loads(json_path.read_text(encoding="utf-8"))["status"] == payload["status"]
    assert "Vega Maturity Sprint" in md_path.read_text(encoding="utf-8")
