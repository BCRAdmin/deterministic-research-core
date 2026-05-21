from pathlib import Path

from research_agent.ops.vault_semantic_audit import (
    audit_vault_semantic_ownership,
    default_viewpoints,
    render_vault_semantic_audit_markdown,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _project(name: str, status: str, body: str) -> str:
    return "\n".join(
        [
            "---",
            "type: project",
            f"status: {status}",
            "updated: 2026-05-21",
            "---",
            "",
            f"# {name}",
            "",
            body,
            "",
        ]
    )


def _write_clean_vault(vault: Path) -> None:
    _write(
        vault / "Project - Utility Websites Portfolio.md",
        _project(
            "Project - Utility Websites Portfolio",
            "active",
            "Materialbedarf, Elterngeld und Microtool sind aktive Lanes.",
        ),
    )
    _write(
        vault / "Project - Utility Wortcluster.md",
        _project(
            "Project - Utility Wortcluster",
            "waiting",
            "\n".join(
                [
                    "Wortquelle, Regelset und Solver.",
                    "## Historische Utility-Websites-Migrationsspur",
                    "Materialbedarf, Elterngeld und Microtool gehoeren zu "
                    "[[Project - Utility Websites Portfolio]].",
                ]
            ),
        ),
    )
    for relative in [
        "00 DreamFactory Home.md",
        "01 Projects.md",
        "02 Plans and Status.md",
        "03 Features.md",
        "04 Agent Start Here.md",
        "DreamFactory – Projektübersicht.md",
        "DreamFactory – Systemhandbuch.md",
        "Canonical/Canonical Index.md",
    ]:
        _write(
            vault / relative,
            (
                "[[Project - LIONCOM Dashboard]], [[Project - Membership Finanzplattform]], "
                "[[Project - Utility Wortcluster]], [[Project - Utility Websites Portfolio]], "
                "[[Project - Quellwert]]"
            ),
        )
    _write(vault / "Review Queue.md", "## 2026-05-21 - Review Queue Aging Audit\n")


def test_default_viewpoints_cover_operator_relief_angles() -> None:
    ids = {viewpoint.viewpoint_id for viewpoint in default_viewpoints()}

    assert "ownership" in ids
    assert "start_surface_alignment" in ids
    assert "status_aging" in ids


def test_vault_semantic_audit_passes_clean_split(tmp_path: Path) -> None:
    _write_clean_vault(tmp_path)

    audit = audit_vault_semantic_ownership(tmp_path)

    assert audit.valid is True
    assert not audit.findings


def test_vault_semantic_audit_flags_old_active_route_phrase(tmp_path: Path) -> None:
    _write_clean_vault(tmp_path)
    _write(
        tmp_path / "Materialbedarf-Rechner.md",
        "Fuehrendes Projektumfeld: [[Project - Utility Wortcluster]]\n",
    )

    audit = audit_vault_semantic_ownership(tmp_path)

    assert audit.valid is False
    assert any(finding.check_id == "old_active_route_phrase" for finding in audit.findings)


def test_vault_semantic_audit_flags_start_surface_without_portfolio(tmp_path: Path) -> None:
    _write_clean_vault(tmp_path)
    _write(tmp_path / "00 DreamFactory Home.md", "[[Project - Utility Wortcluster]]\n")

    audit = audit_vault_semantic_ownership(tmp_path)

    assert audit.valid is False
    assert any(
        finding.check_id == "start_surface_missing_utility_portfolio"
        for finding in audit.findings
    )


def test_vault_semantic_audit_markdown_lists_viewpoints(tmp_path: Path) -> None:
    _write_clean_vault(tmp_path)
    audit = audit_vault_semantic_ownership(tmp_path)

    markdown = render_vault_semantic_audit_markdown(audit)

    assert "## Blickwinkel" in markdown
    assert "Ownership statt Linkstatus" in markdown
