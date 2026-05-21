from pathlib import Path


def test_multi_agent_repo_entrypoints_are_documented_wrappers() -> None:
    root = Path(__file__).resolve().parents[2]
    wrappers = [
        root / "scripts/ops/context_pack_builder.py",
        root / "scripts/ops/multi_agent_panel.py",
    ]

    for wrapper in wrappers:
        text = wrapper.read_text(encoding="utf-8")
        assert "vega-multi-agent-research" in text
        assert "SKILL_SCRIPT" in text
        assert "runpy.run_path" in text
