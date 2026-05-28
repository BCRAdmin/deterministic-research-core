"""OpenJarvis component adapter.

This module turns OpenJarvis from a system-adoption question into a component
harvest pipeline: which ideas should be copied, rebuilt, gated, or rejected
inside the existing Vega/PIG/LIONCOM stack.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from research_agent.ops.openjarvis_capability_lab import load_json, utc_now, write_json, write_text


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = REPO_ROOT / "configs/openjarvis/openjarvis_component_adapter.json"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "outputs/openjarvis_capability_lab/component_adapter"
DEFAULT_TRIAL_ROOT = REPO_ROOT / "outputs/openjarvis_capability_lab/operator_trials"


def latest_trial_report(trial_root: Path = DEFAULT_TRIAL_ROOT) -> dict[str, Any]:
    reports = sorted(trial_root.glob("*/reports/OPENJARVIS_OPERATOR_TRIALS_REPORT.json"))
    if not reports:
        return {
            "status": "MISSING",
            "trial_root": str(trial_root),
            "overall_decision": "operator_trials_missing",
        }
    path = reports[-1]
    payload = load_json(path)
    return {**payload, "path": str(path)}


def compact_runtime_warnings(trial: dict[str, Any]) -> list[str]:
    warnings = trial.get("runtime_sandbox", {}).get("warnings", [])
    return [str(item) for item in warnings]


def resolve_evidence_key(trial: dict[str, Any], key: str) -> Any:
    current: Any = trial
    for part in key.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def component_status(component: dict[str, Any], trial: dict[str, Any]) -> str:
    mode = component.get("adoption_mode")
    if mode == "reject_currently":
        return "REJECT_CURRENT"
    if mode == "keep_operator_gated":
        return "GATED_READY"
    if mode in {"rebuild_locally", "copy_pattern_then_harden", "mine_read_only_then_rebuild"}:
        return "ADAPT_READY"
    if mode == "keep_benchmark_and_copy_winning_queries":
        arena = trial.get("arena") or {}
        if arena.get("shadow_fail_count", 0):
            return "NEEDS_REVIEW"
        return "ADAPT_READY"
    return "REVIEW"


def build_component_matrix(config: dict[str, Any], trial: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for component in config.get("components", []):
        evidence = {
            key: resolve_evidence_key(trial, key)
            for key in component.get("evidence_keys", [])
        }
        rows.append(
            {
                "id": component.get("id"),
                "title": component.get("title"),
                "source_pattern": component.get("source_pattern"),
                "local_target": component.get("local_target"),
                "adoption_mode": component.get("adoption_mode"),
                "status": component_status(component, trial),
                "value": component.get("value"),
                "risk": component.get("risk"),
                "reason": component.get("reason"),
                "required_controls": component.get("required_controls", []),
                "evidence": evidence,
            }
        )
    return rows


def run_github_digest_read_only(account: str = "BCRAdmin", limit: int = 100) -> dict[str, Any]:
    """Build a read-only GitHub PR digest via gh.

    This function intentionally uses only `gh repo list` and `gh pr list`.
    It never writes comments, labels, branches, commits, merges or pushes.
    """

    def run(args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(args, text=True, capture_output=True, check=False)

    auth = run(["gh", "auth", "status"])
    repos_cp = run(
        [
            "gh",
            "repo",
            "list",
            account,
            "--limit",
            str(limit),
            "--json",
            "nameWithOwner,isPrivate,updatedAt,url,primaryLanguage,defaultBranchRef",
        ]
    )
    repos = json.loads(repos_cp.stdout or "[]") if repos_cp.returncode == 0 else []
    all_prs: list[dict[str, Any]] = []
    repo_summaries: list[dict[str, Any]] = []
    for repo in repos:
        name = repo["nameWithOwner"]
        pr_cp = run(
            [
                "gh",
                "pr",
                "list",
                "--repo",
                name,
                "--state",
                "open",
                "--limit",
                "100",
                "--json",
                "number,title,author,updatedAt,url,isDraft,baseRefName,headRefName,mergeStateStatus,statusCheckRollup,labels",
            ]
        )
        prs = json.loads(pr_cp.stdout or "[]") if pr_cp.returncode == 0 else []
        dependabot = [pr for pr in prs if is_dependabot_pr(pr)]
        repo_summaries.append(
            {
                "repo": name,
                "is_private": repo.get("isPrivate"),
                "updated_at": repo.get("updatedAt"),
                "url": repo.get("url"),
                "primary_language": (repo.get("primaryLanguage") or {}).get("name"),
                "default_branch": (repo.get("defaultBranchRef") or {}).get("name"),
                "open_pr_count": len(prs),
                "dependabot_open_pr_count": len(dependabot),
            }
        )
        for pr in prs:
            all_prs.append({"repo": name, **pr})
    open_dependabot = [pr for pr in all_prs if is_dependabot_pr(pr)]
    return {
        "schema_version": 1,
        "generated_at": utc_now(),
        "status": "PASS" if auth.returncode == 0 and repos_cp.returncode == 0 else "FAIL",
        "account": account,
        "read_only": True,
        "mutations_attempted": False,
        "repo_count": len(repos),
        "open_pr_count": len(all_prs),
        "open_dependabot_pr_count": len(open_dependabot),
        "repos": repo_summaries,
        "open_dependabot_prs": open_dependabot,
        "all_open_prs": all_prs,
        "commands_used": [
            "gh auth status",
            "gh repo list <account> --json ...",
            "gh pr list --repo <repo> --state open --json ...",
        ],
    }


def is_dependabot_pr(pr: dict[str, Any]) -> bool:
    author = ((pr.get("author") or {}).get("login") or "").lower()
    title = (pr.get("title") or "").lower()
    return author in {"dependabot[bot]", "app/dependabot"} or "dependabot" in title


def build_component_adapter(
    config_path: Path = DEFAULT_CONFIG_PATH,
    *,
    trial_root: Path = DEFAULT_TRIAL_ROOT,
    github_digest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = load_json(config_path)
    trial = latest_trial_report(trial_root)
    if github_digest is None and trial.get("github_dependabot_digest"):
        github_digest = trial.get("github_dependabot_digest")
    component_matrix = build_component_matrix(config, trial)
    adopt_ready = [item for item in component_matrix if item["status"] == "ADAPT_READY"]
    gated = [item for item in component_matrix if item["status"] == "GATED_READY"]
    rejected = [item for item in component_matrix if item["status"] == "REJECT_CURRENT"]
    automation = config.get("automation_candidate", {})
    local_skill = config.get("local_skill", {})
    return {
        "schema_version": 1,
        "generated_at": utc_now(),
        "adapter_id": config.get("adapter_id"),
        "status": "PASS" if component_matrix else "FAIL",
        "decision_frame": config.get("decision_frame"),
        "overall_decision": "harvest_and_rebuild_selected_patterns",
        "trial_report_path": trial.get("path", ""),
        "runtime_warnings": compact_runtime_warnings(trial),
        "component_count": len(component_matrix),
        "adapt_ready_count": len(adopt_ready),
        "gated_ready_count": len(gated),
        "rejected_current_count": len(rejected),
        "component_matrix": component_matrix,
        "github_digest": github_digest or {
            "status": "NOT_RUN",
            "read_only": True,
            "mutations_attempted": False,
        },
        "automation_candidate": automation,
        "local_skill": local_skill,
        "hard_rules": [
            "openjarvis_patterns_are_inspiration_not_authority",
            "copy_good_patterns_into_vega_pig_lioncom_before_runtime_adoption",
            "real_repo_writes_require_a_disposable_workspace_wrapper_first",
            "github_digest_is_read_only_until_separate_operator_go",
            "external_skills_are_mined_read_only_before_becoming_local_skills",
        ],
        "next_build_targets": [
            "wire_component_adapter_into_agent_os_readiness",
            "surface_adapter_summary_in_pig_and_lioncom",
            "keep_weekly_digest_as_local_review_job_card",
            "iterate_skill_mining_against Hermes/OpenClaw sources only through guardrails",
        ],
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# OpenJarvis Component Adapter",
        "",
        f"- Status: `{report.get('status')}`",
        f"- Entscheidung: `{report.get('overall_decision')}`",
        f"- Komponenten: `{report.get('component_count')}`",
        f"- Adapt-ready: `{report.get('adapt_ready_count')}`",
        f"- Gated-ready: `{report.get('gated_ready_count')}`",
        f"- Derzeit abgelehnt: `{report.get('rejected_current_count')}`",
        f"- Trial-Report: `{report.get('trial_report_path') or 'missing'}`",
        "",
        "## Komponenten",
        "",
        "| Komponente | Status | Modus | Wert | Risiko | Ziel |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for item in report.get("component_matrix", []):
        lines.append(
            f"| `{item.get('id')}` | `{item.get('status')}` | `{item.get('adoption_mode')}` | "
            f"`{item.get('value')}` | `{item.get('risk')}` | {item.get('local_target')} |"
        )
    lines.extend(["", "## Read-only Digest", ""])
    digest = report.get("github_digest", {})
    lines.extend(
        [
            f"- Status: `{digest.get('status')}`",
            f"- Repos: `{digest.get('repo_count', 0)}`",
            f"- Offene PRs: `{digest.get('open_pr_count', 0)}`",
            f"- Dependabot-PRs: `{digest.get('open_dependabot_pr_count', 0)}`",
            f"- Mutationen: `{digest.get('mutations_attempted')}`",
            "",
            "## Skill / Automation",
            "",
            f"- Skill: `{report.get('local_skill', {}).get('name')}`",
            f"- Skill-Pfad: `{report.get('local_skill', {}).get('path')}`",
            f"- Automation-Kandidat: `{report.get('automation_candidate', {}).get('id')}`",
            f"- Automation-Status: `{report.get('automation_candidate', {}).get('status')}`",
            "",
            "## Harte Regeln",
            "",
        ]
    )
    for rule in report.get("hard_rules", []):
        lines.append(f"- `{rule}`")
    lines.extend(["", "## Nächste Build-Ziele", ""])
    for target in report.get("next_build_targets", []):
        lines.append(f"- `{target}`")
    return "\n".join(lines) + "\n"


def write_component_adapter(report: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    report = {**report, "path": str((output_dir / "OPENJARVIS_COMPONENT_ADAPTER.json").resolve())}
    write_json(output_dir / "OPENJARVIS_COMPONENT_ADAPTER.json", report)
    write_text(output_dir / "OPENJARVIS_COMPONENT_ADAPTER.md", render_markdown(report))
    write_json(
        output_dir / "OPENJARVIS_COMPONENT_MATRIX.json",
        {"components": report.get("component_matrix", [])},
    )
    write_text(
        output_dir / "OPENJARVIS_COMPONENT_ADAPTER_VALIDATION.txt",
        "\n".join(
            [
                "OpenJarvis Component Adapter Validation",
                f"status={report.get('status')}",
                f"component_count={report.get('component_count')}",
                f"adapt_ready_count={report.get('adapt_ready_count')}",
                f"gated_ready_count={report.get('gated_ready_count')}",
                f"rejected_current_count={report.get('rejected_current_count')}",
                f"github_digest_status={report.get('github_digest', {}).get('status')}",
                "mutations_attempted=false",
            ]
        )
        + "\n",
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the OpenJarvis component adapter.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Component adapter config.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Output directory.")
    parser.add_argument("--trial-root", default=str(DEFAULT_TRIAL_ROOT), help="Operator trials root.")
    parser.add_argument("--run-github-digest", action="store_true", help="Run read-only gh digest.")
    parser.add_argument("--github-account", default="BCRAdmin", help="GitHub account for read-only digest.")
    parser.add_argument("--json", action="store_true", help="Print JSON report.")
    args = parser.parse_args(argv)
    digest = run_github_digest_read_only(args.github_account) if args.run_github_digest else None
    report = build_component_adapter(
        Path(args.config).expanduser().resolve(),
        trial_root=Path(args.trial_root).expanduser().resolve(),
        github_digest=digest,
    )
    written = write_component_adapter(report, Path(args.output_dir).expanduser().resolve())
    if args.json:
        print(json.dumps(written, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(f"{written['status']} {written['path']}")
    return 0 if written["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
