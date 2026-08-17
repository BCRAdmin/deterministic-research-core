#!/usr/bin/env python3
"""Verify the accepted BA3-BA9 Semantic Compiler Wave freeze."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import inspect
import json
import subprocess
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.compiler_foundation.kernel import load_pass_manifests


RESEARCH_ROOT = Path(__file__).resolve().parents[2]
FREEZE_RECORD = (
    RESEARCH_ROOT
    / "research_agent/semantic_compiler/freeze/semantic_compiler_wave_freeze_v1.json"
)
SCHEMA_MODULES = (
    "research_agent.compiler_foundation.contracts",
    "research_agent.semantic_compiler.source_frontend.contracts",
    "research_agent.semantic_compiler.registry_foundation.contracts",
    "research_agent.semantic_compiler.semantic_wave.contracts",
    "research_agent.semantic_compiler.semantic_spine.contracts",
    "research_agent.semantic_compiler.semantic_spine.rfc_0003_contracts",
    "research_agent.semantic_compiler.semantic_spine.rfc_0004_contracts",
)


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _schema_catalog() -> dict[str, Any]:
    catalog: dict[str, Any] = {}
    for module_name in SCHEMA_MODULES:
        module = importlib.import_module(module_name)
        for name, model in inspect.getmembers(module, inspect.isclass):
            if (
                model.__module__ == module_name
                and issubclass(model, BaseModel)
            ):
                catalog[f"{module_name}.{name}"] = model.model_json_schema(
                    mode="validation"
                )
    return catalog


def _semantic_source_hashes() -> dict[str, str]:
    source_root = RESEARCH_ROOT / "research_agent/semantic_compiler"
    result: dict[str, str] = {}
    for path in sorted(source_root.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        relative = path.relative_to(RESEARCH_ROOT).as_posix()
        if relative.startswith("research_agent/semantic_compiler/freeze/"):
            continue
        if path.suffix not in {".py", ".json"}:
            continue
        result[relative] = _file_sha256(path)
    return result


def verify(product_repo: Path) -> dict[str, Any]:
    record = json.loads(FREEZE_RECORD.read_text(encoding="utf-8"))
    checks: dict[str, bool] = {}

    tag = record["git"]["tag"]
    checks["semantic_tag_object"] = (
        _git(RESEARCH_ROOT, "rev-parse", tag) == record["git"]["tag_object"]
    )
    checks["semantic_tag_target"] = (
        _git(RESEARCH_ROOT, "rev-parse", f"{tag}^{{}}")
        == record["git"]["research_commit"]
    )

    foundation = json.loads(
        (
            RESEARCH_ROOT
            / "research_agent/compiler_foundation/freeze/compiler_foundation_manifest_v1.json"
        ).read_text(encoding="utf-8")
    )
    checks["foundation_version"] = (
        foundation["compiler_foundation_version"]
        == record["versions"]["compiler_foundation"]
    )
    checks["foundation_version_lock"] = (
        foundation["version_lock_sha256"]
        == record["foundation"]["version_lock_sha256"]
    )

    registry = json.loads(
        (
            RESEARCH_ROOT
            / "research_agent/semantic_compiler/registry_foundation/freeze/registry_foundation_manifest_v1_1.json"
        ).read_text(encoding="utf-8")
    )
    checks["registry_version"] = (
        registry["registry_foundation_version"]
        == record["versions"]["registry_foundation"]
    )
    checks["registry_authority"] = (
        registry["authority"]["authority_sha256"]
        == record["registry"]["authority_sha256"]
    )

    pass_path = RESEARCH_ROOT / record["pass_manifest"]["path"]
    pass_document = json.loads(pass_path.read_text(encoding="utf-8"))
    effective_passes = [
        item.model_dump(mode="json") for item in load_pass_manifests(pass_path)
    ]
    checks["pass_manifest_file"] = (
        _file_sha256(pass_path) == record["pass_manifest"]["file_sha256"]
    )
    checks["pass_manifest_document"] = (
        sha256_json(pass_document)
        == record["pass_manifest"]["canonical_document_sha256"]
    )
    checks["effective_pass_manifest"] = (
        sha256_json(effective_passes)
        == record["pass_manifest"]["effective_pass_manifest_sha256"]
    )
    checks["pass_ids_and_order"] = (
        [item["pass_id"] for item in effective_passes]
        == record["pass_manifest"]["pass_ids"]
    )

    schemas = _schema_catalog()
    checks["ir_schema_count"] = len(schemas) == record["ir_schema"]["schema_count"]
    checks["ir_schema_set"] = (
        sha256_json(schemas) == record["ir_schema"]["schema_set_sha256"]
    )

    semantic_sources = _semantic_source_hashes()
    checks["semantic_source_count"] = (
        len(semantic_sources) == record["semantic_source_set"]["file_count"]
    )
    checks["semantic_source_set"] = (
        sha256_json(semantic_sources)
        == record["semantic_source_set"]["source_set_sha256"]
    )

    evidence = RESEARCH_ROOT / record["accepted_evidence"]["archive"]
    checks["accepted_evidence_archive"] = (
        evidence.is_file()
        and _file_sha256(evidence)
        == record["accepted_evidence"]["archive_sha256"]
    )

    product_commit = record["git"]["product_commit"]
    checks["product_commit_exists"] = (
        _git(product_repo, "cat-file", "-t", product_commit) == "commit"
    )
    canary_path = product_repo / record["canary_baseline"]["product_path"]
    canary = json.loads(canary_path.read_text(encoding="utf-8"))
    checks["canary_baseline_file"] = (
        _file_sha256(canary_path)
        == record["canary_baseline"]["baseline_file_sha256"]
    )
    checks["canary_version_lock"] = (
        canary["version_lock_sha256"]
        == record["canary_baseline"]["version_lock_sha256"]
    )
    checks["canary_candidates"] = (
        canary["candidate_sha256"] == record["canary_baseline"]["candidate_sha256"]
    )

    checks["version_lock"] = (
        sha256_json(record["version_lock_inputs"])
        == record["version_lock_sha256"]
    )
    checks["semantic_wave_complete"] = bool(
        record["status_flags"]["semantic_compiler_wave_complete"]
    )
    checks["ba10_not_started"] = not any(
        (
            record["status_flags"]["ba10_authorized"],
            record["status_flags"]["ba10_started"],
        )
    )

    failed = sorted(name for name, passed in checks.items() if not passed)
    return {
        "contract_id": "room16.compiler.semantic_wave_freeze_verification",
        "contract_version": 1,
        "status": "PASS" if not failed else "FAIL",
        "freeze_version": record["versions"]["semantic_compiler_wave"],
        "version_lock_sha256": record["version_lock_sha256"],
        "checks": checks,
        "failed_checks": failed,
        "ba10_authorized": False,
        "ba10_started": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--product-repo",
        type=Path,
        default=RESEARCH_ROOT.parent / "company-dossier-lab",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = verify(args.product_repo.resolve())
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(result["status"])
        for name, passed in result["checks"].items():
            print(f"{'PASS' if passed else 'FAIL'} {name}")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
