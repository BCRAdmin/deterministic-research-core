from pathlib import Path

from research_agent.ops.documents_root_hygiene import scan_documents_root


def test_documents_root_hygiene_allows_canonical_namespaces_and_operator_app(tmp_path: Path) -> None:
    (tmp_path / "DreamFactory" / "Project-Intelligence-Graph").mkdir(parents=True)
    reports = tmp_path / "DreamFactory" / "Room16" / "Reports"
    reports.mkdir(parents=True)
    research_agent_ops = tmp_path / "DreamFactory" / "Room16" / "research-agent-ops"
    research_agent_ops.mkdir(parents=True)
    (tmp_path / "BCR Ventures" / "client-prototypes" / "wp-stb-roesinger-redesign").mkdir(
        parents=True
    )
    (tmp_path / "Midjurney").mkdir()

    payload = scan_documents_root(tmp_path)

    assert payload["ok"] is True
    assert payload["error_count"] == 0
    assert payload["warning_count"] == 0


def test_documents_root_hygiene_blocks_generic_and_root_leak_dirs(tmp_path: Path) -> None:
    (tmp_path / "DreamFactory" / "Project-Intelligence-Graph").mkdir(parents=True)
    (tmp_path / "DreamFactory" / "Room16" / "Reports").mkdir(parents=True)
    (tmp_path / "DreamFactory" / "Room16" / "research-agent-ops").mkdir(parents=True)
    (tmp_path / "BCR Ventures" / "client-prototypes" / "wp-stb-roesinger-redesign").mkdir(
        parents=True
    )
    (tmp_path / "New project 3").mkdir()
    (tmp_path / "docs").mkdir()

    payload = scan_documents_root(tmp_path)

    assert payload["ok"] is False
    assert payload["error_count"] == 2
    assert {finding["code"] for finding in payload["findings"] if finding["severity"] == "error"} == {
        "generic_project_folder_name",
        "root_runtime_leak",
    }


def test_documents_root_hygiene_blocks_retired_root_names(tmp_path: Path) -> None:
    (tmp_path / "DreamFactory" / "Project-Intelligence-Graph").mkdir(parents=True)
    (tmp_path / "DreamFactory" / "Room16" / "Reports").mkdir(parents=True)
    (tmp_path / "DreamFactory" / "Room16" / "research-agent-ops").mkdir(parents=True)
    (tmp_path / "BCR Ventures" / "client-prototypes" / "wp-stb-roesinger-redesign").mkdir(
        parents=True
    )
    (tmp_path / "New project").mkdir()
    (tmp_path / "New project 2").mkdir()
    (tmp_path / "Room 16 Reports").mkdir()
    (tmp_path / "wp-stb-roesinger-redesign").mkdir()

    payload = scan_documents_root(tmp_path)

    assert payload["ok"] is False
    assert {
        finding["code"]
        for finding in payload["findings"]
        if finding["severity"] == "error"
    } == {
        "retired_new_project_root_present",
        "retired_new_project_2_root_present",
        "retired_room16_reports_root_present",
        "retired_wp_stb_root_present",
    }


def test_documents_root_hygiene_blocks_desktop_markdown(tmp_path: Path) -> None:
    (tmp_path / "DreamFactory" / "Project-Intelligence-Graph").mkdir(parents=True)
    (tmp_path / "DreamFactory" / "Room16" / "Reports").mkdir(parents=True)
    (tmp_path / "DreamFactory" / "Room16" / "research-agent-ops").mkdir(parents=True)
    (tmp_path / "BCR Ventures" / "client-prototypes" / "wp-stb-roesinger-redesign").mkdir(
        parents=True
    )
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    (desktop / "loose-note.md").write_text("# loose\n", encoding="utf-8")

    payload = scan_documents_root(tmp_path, desktop_root=desktop)

    assert payload["ok"] is False
    assert payload["error_count"] == 1
    assert payload["findings"][0]["code"] == "desktop_markdown_output_present"
