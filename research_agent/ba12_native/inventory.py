"""Fail-closed no-legacy-truth scanner for BA12 canonical paths."""

from __future__ import annotations

import json
from pathlib import Path

FORBIDDEN_RESEARCH_IMPORTS = (
    "semantic_wave.legacy_replay",
    "semantic_spine.rfc_0004",
    "productization.artifact_bundle",
    "run_research_pipeline",
    "run_current_research",
)
FORBIDDEN_PRODUCT_CANONICAL_CALLS = (
    "resolveCanonicalResearchAuthorityBundle(",
    "resolveCanonicalCompilerArtifactBundle(",
    "deterministicResearchReports()",
    "scanOperatorCompanies()",
    "findCompany(req.params.ticker)",
)


def scan_canonical_runtime(*, research_root: Path, product_root: Path) -> dict[str, object]:
    native_root = research_root / "research_agent/ba12_native"
    violations: list[str] = []
    for path in sorted(native_root.glob("*.py")):
        if path.name == "inventory.py":
            continue
        text = path.read_text(encoding="utf-8")
        for token in FORBIDDEN_RESEARCH_IMPORTS:
            if token in text:
                violations.append(f"{path.relative_to(research_root)}:{token}")
    server = (product_root / "room16-app/ba12-native-server.mjs").read_text(encoding="utf-8")
    routes = server
    for token in FORBIDDEN_PRODUCT_CANONICAL_CALLS:
        if token in routes:
            violations.append(f"room16-app/ba12-native-server.mjs:{token}")
    native_module = (product_root / "room16-app/server-modules/ba12-native-report.mjs").read_text(encoding="utf-8")
    for token in ("research-authority-bundle", "deterministic-research-report", "compiler-artifact-bundle.mjs\""):
        if token in native_module:
            violations.append(f"room16-app/server-modules/ba12-native-report.mjs:{token}")
    return {"contract_id": "room16.ba12.no_legacy_truth_scan", "contract_version": 1, "active_legacy_semantic_readers": len(violations), "violations": violations, "status": "PASS" if not violations else "BLOCK"}


def verify_inventory(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("contract_id") != "room16.ba12.legacy_path_inventory@1" or value.get("wave0_revalidation", {}).get("unknown_runtime_reachable_paths") != 0 or value.get("wave0_revalidation", {}).get("rfc_blockers_remaining") != 0:
        raise ValueError("BA12_LEGACY_INVENTORY_INCOMPLETE")
    return value
