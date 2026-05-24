from pathlib import Path

from research_agent.ops.past_blocks_closure import build_past_blocks_closure_report


def test_past_blocks_closure_accepts_closed_reviews(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    vault = tmp_path / "vault"
    lioncom = tmp_path / "lioncom"
    (root / "outputs/agent_os_readiness").mkdir(parents=True)
    (root / "outputs/vault_semantic_audit").mkdir(parents=True)
    vault.mkdir()
    (lioncom / "mission-control-board/lib/services").mkdir(parents=True)
    (lioncom / "mission-control-board/docs").mkdir(parents=True)
    (lioncom / "scripts").mkdir(parents=True)

    (vault / "Review Queue.md").write_text(
        "## Still Open\n\n"
        "- Status: `implemented_claim_start_snapshot`\n"
        "- Status: `implemented_report_only_guard`\n\n"
        "## No Remaining Past Blocks\n",
        encoding="utf-8",
    )
    (lioncom / "mission-control-board/lib/services/autonomyService.ts").write_text(
        "buildModelRouteSnapshotAtClaimStart modelRouteSnapshotAtClaimStart PATHS.VIVI_MODEL_ROUTE_STATUS",
        encoding="utf-8",
    )
    (lioncom / "scripts/run_local_duo_loop.sh").write_text(
        "CLAIM_MODEL_ROUTE_SNAPSHOT_JSON Claim-Start Model Route Snapshot claimModelRouteSnapshotAtClaimStart",
        encoding="utf-8",
    )
    (lioncom / "mission-control-board/docs/vivi-model-route-snapshot-closure-2026-05-21.md").write_text(
        "implemented_claim_start_snapshot Existing pre-change claims are not retroactively rewritten",
        encoding="utf-8",
    )
    (root / "outputs/agent_os_readiness/VAULT_SEMANTIC_OWNERSHIP_AUDIT.md").write_text(
        "report-only python3 scripts/ops/vault_semantic_audit.py",
        encoding="utf-8",
    )
    (root / "outputs/agent_os_readiness/AUTOMATION_JOB_CARDS.md").write_text(
        "Vault Semantic Ownership pruefen proposed_local_review_only",
        encoding="utf-8",
    )
    (root / "outputs/agent_os_readiness/OPERATOR_INBOX.md").write_text(
        "vault-semantic-ownership-review ready_for_review",
        encoding="utf-8",
    )
    (root / "outputs/vault_semantic_audit/VAULT_SEMANTIC_OWNERSHIP_AUDIT.md").write_text(
        "Workflow-Regel report-only",
        encoding="utf-8",
    )

    report = build_past_blocks_closure_report(root, vault, lioncom)

    assert report.valid is True
    assert report.remaining_past_blocks == ()


def test_past_blocks_closure_rejects_old_still_open_status(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    vault = tmp_path / "vault"
    lioncom = tmp_path / "lioncom"
    root.mkdir()
    vault.mkdir()
    lioncom.mkdir()
    (vault / "Review Queue.md").write_text("- Status: `still_open_low_noise`\n", encoding="utf-8")

    report = build_past_blocks_closure_report(root, vault, lioncom)

    assert report.valid is False
    assert "review_queue_still_open_status" in report.remaining_past_blocks
