import json
from pathlib import Path

from research_agent.ops.portfolio_surface_audit import (
    audit_portfolio_surfaces,
    default_project_surface_specs,
    render_portfolio_surface_canvas,
    render_portfolio_surface_markdown,
)


def _write_project_note(vault: Path, name: str, status: str, body: str) -> None:
    (vault / name).write_text(
        "\n".join(
            [
                "---",
                "type: project",
                f"status: {status}",
                "updated: 2026-05-21",
                "---",
                "",
                f"# {name.removesuffix('.md')}",
                "",
                "## Kurzbild",
                "",
                body,
                "",
                "## Aktueller Stand",
                "",
                body,
                "",
                "## Produktoberflaechen-Check",
                "",
                body,
                "",
                "## Naechster sinnvoller Schnitt",
                "",
                body,
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_valid_vault(vault: Path) -> None:
    _write_project_note(
        vault,
        "Project - LIONCOM Dashboard.md",
        "active",
        "Operator Control mit Vivi, Vega, Gate, Verifier und Operator-Go.",
    )
    _write_project_note(
        vault,
        "Project - Membership Finanzplattform.md",
        "active",
        "Proof, Waitlist, Provider, Launch, Operator-Go, Checkout und Mail bleiben gegated.",
    )
    _write_project_note(
        vault,
        "Project - Utility Websites Portfolio.md",
        "active",
        "Materialbedarf, Elterngeld, Microtool, GSC, Messvertrag und Trust sind aktive Lanes.",
    )
    _write_project_note(
        vault,
        "Project - Utility Wortcluster.md",
        "waiting",
        (
            "Wortquelle, Regelset, Solver, waiting, Datenquellen-Hold und Methodik. "
            "Historische Materialbedarf-/Elterngeld-/Microtool-Belege verweisen auf "
            "[[Project - Utility Websites Portfolio]]. Utility-Websites-Portfolio ist eine "
            "eigene aktive Projektkarte."
        ),
    )
    _write_project_note(
        vault,
        "Project - Quellwert.md",
        "local_preview",
        "Research, Archiv, Methodik, Room16, Promotion, public_ready, Operator-Go und Non-Advice.",
    )


def test_default_portfolio_surface_specs_cover_canonical_projects() -> None:
    specs = default_project_surface_specs()

    assert [spec.project_id for spec in specs] == [
        "lioncom_dashboard",
        "membership_finanzplattform",
        "utility_wortcluster",
        "utility_websites_portfolio",
        "quellwert",
    ]


def test_portfolio_surface_audit_passes_for_split_and_marked_project_cards(tmp_path: Path) -> None:
    _write_valid_vault(tmp_path)

    audit = audit_portfolio_surfaces(tmp_path)

    assert audit.valid is True
    assert not audit.findings
    assert {result.audit_status for result in audit.results} == {"verified_local_surface"}


def test_portfolio_surface_audit_flags_utility_mix_without_split(tmp_path: Path) -> None:
    _write_valid_vault(tmp_path)
    (tmp_path / "Project - Utility Websites Portfolio.md").unlink()
    _write_project_note(
        tmp_path,
        "Project - Utility Wortcluster.md",
        "waiting",
        "Wortquelle, Regelset, Solver, waiting, Datenquellen-Hold, Methodik und Materialbedarf.",
    )

    audit = audit_portfolio_surfaces(tmp_path)

    assert audit.valid is False
    check_ids = {finding.check_id for finding in audit.findings}
    assert "project_note_missing" in check_ids
    assert "utility_active_lanes_mixed_into_waiting_project" in check_ids


def test_portfolio_surface_renderers_emit_markdown_and_canvas(tmp_path: Path) -> None:
    _write_valid_vault(tmp_path)
    audit = audit_portfolio_surfaces(tmp_path)

    markdown = render_portfolio_surface_markdown(audit)
    canvas = json.loads(render_portfolio_surface_canvas(audit))

    assert "Portfolio-Produktoberflaechen-Audit" in markdown
    assert "Keine Blocker oder High-Findings" in markdown
    assert any(node["id"] == "portfolio-audit" for node in canvas["nodes"])
    assert len(canvas["edges"]) >= len(audit.results)
