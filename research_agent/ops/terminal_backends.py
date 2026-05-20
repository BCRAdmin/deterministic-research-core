"""Terminal backend contracts for future agent execution.

This module does not execute commands. It records the smallest useful local and
Docker backend contracts so future Vivi/Vega work can reason about execution
surfaces before any runtime authority is granted.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class TerminalBackendSpec:
    backend_id: str
    status: str
    isolation: str
    command_surface: tuple[str, ...]
    write_scope: str
    network: str
    secrets: str
    operator_gate_required: bool
    verification: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class BackendValidation:
    backend_id: str
    valid: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def default_backend_specs(root: Path) -> list[TerminalBackendSpec]:
    root = root.resolve()
    return [
        TerminalBackendSpec(
            backend_id="local_read_only",
            status="implemented_contract_only",
            isolation="host_user_no_extra_isolation",
            command_surface=("pwd", "ls", "find", "rg", "sed", "python3 -m pytest", "ruff check"),
            write_scope="none_by_default; artifact writes only through explicit scripts",
            network="disabled_by_policy_for_readiness_pack",
            secrets="not_read_not_printed",
            operator_gate_required=False,
            verification=(
                "commands_must_be_non_destructive",
                "dangerous_command_scan_before_execution",
                f"workdir_must_equal:{root}",
            ),
        ),
        TerminalBackendSpec(
            backend_id="docker_project_sandbox",
            status="planned_contract_ready_not_started",
            isolation="container_namespace_with_project_mount",
            command_surface=("python3 -m pytest", "ruff check", "python3 scripts/ops/agent_os_readiness.py"),
            write_scope="project_mount_only; no home_mount; no vault_mount_by_default",
            network="off_by_default",
            secrets="empty_env_except_explicit_allowlist",
            operator_gate_required=True,
            verification=(
                "image_digest_pinned_before_use",
                "workspace_mount_read_write_scope_confirmed",
                "no_home_or_secret_mounts",
                "post_run_artifact_diff_review",
            ),
        ),
    ]


def validate_backend_specs(specs: Sequence[TerminalBackendSpec], root: Path) -> list[BackendValidation]:
    validations: list[BackendValidation] = []
    root = root.resolve()
    for spec in specs:
        errors: list[str] = []
        warnings: list[str] = []
        if not spec.command_surface:
            errors.append("missing_command_surface")
        if spec.secrets != "not_read_not_printed" and "empty_env" not in spec.secrets:
            errors.append("secret_policy_not_explicit")
        if spec.network != "disabled_by_policy_for_readiness_pack" and "off_by_default" not in spec.network:
            warnings.append("network_not_disabled_by_default")
        if spec.backend_id == "local_read_only" and f"workdir_must_equal:{root}" not in spec.verification:
            errors.append("local_workdir_verification_missing")
        if spec.backend_id.startswith("docker") and not spec.operator_gate_required:
            errors.append("docker_backend_requires_operator_gate")
        validations.append(
            BackendValidation(
                backend_id=spec.backend_id,
                valid=not errors,
                errors=tuple(errors),
                warnings=tuple(warnings),
            )
        )
    return validations


def render_terminal_backends_markdown(
    specs: Sequence[TerminalBackendSpec],
    validations: Sequence[BackendValidation],
) -> str:
    validation_by_id = {item.backend_id: item for item in validations}
    lines = [
        "# Terminal Backend Contracts",
        "",
        "These are execution contracts only. No backend is started by the readiness runner.",
        "",
        "| Backend | Status | Isolation | Network | Secrets | Gate | Valid |",
        "| --- | --- | --- | --- | --- | ---: | ---: |",
    ]
    for spec in specs:
        validation = validation_by_id.get(spec.backend_id)
        lines.append(
            f"| `{spec.backend_id}` | `{spec.status}` | `{spec.isolation}` | `{spec.network}` | "
            f"`{spec.secrets}` | {str(spec.operator_gate_required).lower()} | "
            f"{str(validation.valid if validation else False).lower()} |"
        )
    lines.extend(["", "## Verification", ""])
    for spec in specs:
        lines.append(f"### {spec.backend_id}")
        for item in spec.verification:
            lines.append(f"- `{item}`")
        validation = validation_by_id.get(spec.backend_id)
        if validation:
            lines.append(f"- validation_errors: `{', '.join(validation.errors) if validation.errors else 'none'}`")
            lines.append(
                f"- validation_warnings: `{', '.join(validation.warnings) if validation.warnings else 'none'}`"
            )
        lines.append("")
    return "\n".join(lines)
