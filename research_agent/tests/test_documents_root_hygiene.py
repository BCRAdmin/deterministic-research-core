from pathlib import Path

from research_agent.ops.documents_root_hygiene import scan_documents_root


def test_documents_root_hygiene_allows_legacy_workspace_and_migrated_symlink(tmp_path: Path) -> None:
    (tmp_path / "New project").mkdir()
    reports = tmp_path / "DreamFactory" / "Room16" / "Reports"
    reports.mkdir(parents=True)
    research_agent_ops = tmp_path / "DreamFactory" / "Room16" / "research-agent-ops"
    research_agent_ops.mkdir(parents=True)
    (tmp_path / "BCR Ventures" / "client-prototypes" / "wp-stb-roesinger-redesign").mkdir(
        parents=True
    )
    (tmp_path / "Room 16 Reports").symlink_to(reports)
    (tmp_path / "New project 2").symlink_to(research_agent_ops)

    payload = scan_documents_root(tmp_path)

    assert payload["ok"] is True
    assert payload["error_count"] == 0
    assert payload["warning_count"] == 3


def test_documents_root_hygiene_blocks_generic_and_root_leak_dirs(tmp_path: Path) -> None:
    (tmp_path / "DreamFactory" / "Room16" / "Reports").mkdir(parents=True)
    (tmp_path / "DreamFactory" / "Room16" / "research-agent-ops").mkdir(parents=True)
    (tmp_path / "BCR Ventures" / "client-prototypes" / "wp-stb-roesinger-redesign").mkdir(
        parents=True
    )
    (tmp_path / "New project 3").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "wp-stb-roesinger-redesign").mkdir()

    payload = scan_documents_root(tmp_path)

    assert payload["ok"] is False
    assert payload["error_count"] == 3
    assert {finding["code"] for finding in payload["findings"] if finding["severity"] == "error"} == {
        "generic_project_folder_name",
        "root_runtime_leak",
        "client_prototype_must_live_under_bcr_ventures",
    }


def test_documents_root_hygiene_blocks_real_room16_root_folder(tmp_path: Path) -> None:
    (tmp_path / "DreamFactory" / "Room16" / "Reports").mkdir(parents=True)
    (tmp_path / "DreamFactory" / "Room16" / "research-agent-ops").mkdir(parents=True)
    (tmp_path / "BCR Ventures" / "client-prototypes" / "wp-stb-roesinger-redesign").mkdir(
        parents=True
    )
    (tmp_path / "Room 16 Reports").mkdir()

    payload = scan_documents_root(tmp_path)

    assert payload["ok"] is False
    assert any(
        finding["code"] == "room16_reports_root_folder"
        for finding in payload["findings"]
        if finding["severity"] == "error"
    )


def test_documents_root_hygiene_blocks_real_new_project_2_after_migration(tmp_path: Path) -> None:
    (tmp_path / "DreamFactory" / "Room16" / "Reports").mkdir(parents=True)
    (tmp_path / "DreamFactory" / "Room16" / "research-agent-ops").mkdir(parents=True)
    (tmp_path / "BCR Ventures" / "client-prototypes" / "wp-stb-roesinger-redesign").mkdir(
        parents=True
    )
    (tmp_path / "New project 2").mkdir()

    payload = scan_documents_root(tmp_path)

    assert payload["ok"] is False
    assert any(
        finding["code"] == "migrated_workspace_must_be_symlink"
        for finding in payload["findings"]
        if finding["severity"] == "error"
    )
