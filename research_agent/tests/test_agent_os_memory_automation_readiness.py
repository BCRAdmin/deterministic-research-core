from pathlib import Path

from research_agent.ops.automation_cards import default_job_cards, validate_job_card
from research_agent.ops.memory_inbox import build_search_index, collect_memory_candidates, search_index
from research_agent.ops.readiness import build_openclaw_migration_dry_run


def test_memory_inbox_collects_promotion_candidate(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "note.md").write_text(
        "# Note\n\n- Learning: Hermes-style setup should become a local readiness pack.\n",
        encoding="utf-8",
    )

    candidates = collect_memory_candidates(tmp_path, targets=("docs",))

    assert len(candidates) == 1
    assert candidates[0].route == "DreamFactory System/Agent Stack"


def test_session_search_index_returns_hits(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "note.md").write_text("Hermes OpenClaw readiness pack\n", encoding="utf-8")
    db_path = tmp_path / "out" / "search.sqlite"

    row_count = build_search_index(tmp_path, db_path, targets=("docs",))
    hits = search_index(db_path, "Hermes", limit=5)

    assert row_count == 1
    assert hits
    assert hits[0].path == "docs/note.md"


def test_default_automation_cards_are_valid(tmp_path: Path) -> None:
    (tmp_path / "docs" / "agent_os").mkdir(parents=True)
    (tmp_path / "docs" / "agent_os" / "AGENT_OS_READINESS_PACK.md").write_text("pack", encoding="utf-8")
    (tmp_path / "docs" / "agent_os" / "DELIVERABLE_SWARM_CONTRACT.md").write_text(
        "contract",
        encoding="utf-8",
    )
    (tmp_path / "outputs" / "agent_os_readiness").mkdir(parents=True)
    for name in (
        "AGENT_OS_READINESS_REPORT.md",
        "MEMORY_INBOX_CANDIDATES.md",
        "SKILL_REGISTRY.md",
        "GUARDRAIL_SCAN.md",
        "DELIVERABLE_SWARM_CONTRACT.md",
    ):
        (tmp_path / "outputs" / "agent_os_readiness" / name).write_text("output", encoding="utf-8")

    cards = default_job_cards(tmp_path)
    validations = [validate_job_card(card, tmp_path) for card in cards]

    assert all(validation.valid for validation in validations)


def test_openclaw_migration_dry_run_never_requires_secret_import(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("TOKEN=secret", encoding="utf-8")

    items = build_openclaw_migration_dry_run(tmp_path)
    env_item = next(item for item in items if item.source.endswith(".env"))

    assert env_item.secret_sensitive is True
    assert env_item.action == "manifest_only_requires_explicit_secret_gate"
