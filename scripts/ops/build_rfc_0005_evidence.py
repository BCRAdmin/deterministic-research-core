#!/usr/bin/env python3
"""Build the RFC-0005 Artifact ABI and Renderer Isolation evidence bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from datetime import date
from pathlib import Path
from typing import Any

from research_agent.productization.artifact_bundle import (
    build_compiler_artifact_bundle,
    materialize_authority_v3_view,
    verify_compiler_artifact_bundle,
)
from research_agent.semantic_compiler.semantic_spine.rfc_0004 import (
    replay_rfc_0004_archive,
)

RESEARCH_ROOT = Path(__file__).resolve().parents[2]
PRODUCT_ROOT = RESEARCH_ROOT.parent / "company-dossier-lab"
APP_ROOT = PRODUCT_ROOT / "room16-app"
CANARY_ROOT = (
    PRODUCT_ROOT
    / ".runtime/cross-company-release-current"
    / "ROOM16_WM_COST_ABT_CROSS_COMPANY_RC_8cf064d75c8c-20260814-115448"
)
CANARY_HASHES = {
    "WM": "a6b6d15ad7004573a56ad057884563cfbeeb2c3162dae0641a1b361b5e416d72",
    "COST": "b97e6024855c7a772713ff9af4889987e4a9a8e5a3afca0d56a42a1ba8092ea4",
    "ABT": "0926d3cafd312556ec267b2b25214d255ff9352daed77a01b7852addbb48dc45",
}
BASE_RESEARCH_COMMIT = "f377e47bbaf15b29dc36b45c0a3008f95413a99d"
BASE_PRODUCT_COMMIT = "82c5525f3291ace4e3d8c0fdeee6bd67348f5a38"
PREVIOUS_EVIDENCE_SHA256 = (
    "3331e014eb8db46b3903800688e2597028630bba0b731e43f8cae4b6007c7aa9"
)


def _json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8")


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tree_hash(root: Path) -> str:
    rows = [
        {
            "path": path.relative_to(root).as_posix(),
            "sha256": _sha(path),
            "bytes": path.stat().st_size,
        }
        for path in sorted(root.rglob("*"))
        if path.is_file()
    ]
    payload = json.dumps(rows, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(payload).hexdigest()


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=repo, text=True).strip()


def _run(command: list[str], cwd: Path) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return {
        "command": command,
        "cwd": str(cwd),
        "exit_code": completed.returncode,
        "output": completed.stdout,
    }


def _product_full_verify() -> dict[str, Any]:
    server_log = tempfile.TemporaryFile(mode="w+t", encoding="utf-8")
    server = subprocess.Popen(
        ["node", "server.mjs", "--static", "--port", "4516"],
        cwd=APP_ROOT,
        text=True,
        stdout=server_log,
        stderr=subprocess.STDOUT,
    )
    try:
        ready = False
        for _ in range(60):
            if server.poll() is not None:
                break
            try:
                with urllib.request.urlopen(
                    "http://127.0.0.1:4516/api/health", timeout=1
                ) as response:
                    ready = response.status == 200
            except (OSError, urllib.error.URLError):
                pass
            if ready:
                break
            time.sleep(0.25)
        if not ready:
            server_log.seek(0)
            return {
                "command": ["npm", "run", "verify"],
                "cwd": str(APP_ROOT),
                "exit_code": 1,
                "output": "managed Product server did not become healthy\n"
                + server_log.read(),
            }
        return _run(["npm", "run", "verify"], APP_ROOT)
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)
        server_log.close()


def _deterministic_zip(source: Path, target: Path) -> None:
    with zipfile.ZipFile(
        target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as bundle:
        for path in sorted(item for item in source.rglob("*") if item.is_file()):
            info = zipfile.ZipInfo(
                path.relative_to(source).as_posix(), date_time=(1980, 1, 1, 0, 0, 0)
            )
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            bundle.writestr(
                info,
                path.read_bytes(),
                compress_type=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            )


def _authority_source_parity(archive: Path, bridge: dict[str, Any]) -> bool:
    with zipfile.ZipFile(archive) as source:
        return all(
            hashlib.sha256(source.read(item["source_member"])).hexdigest()
            == item["sha256"]
            for item in bridge["files"]
        )


def _test_commands() -> dict[str, dict[str, Any]]:
    tests = {
        "research_targeted": _run(
            [
                str(RESEARCH_ROOT / ".venv/bin/python"),
                "-m",
                "pytest",
                "-q",
                "research_agent/tests/test_ba10_artifact_bundle.py",
            ],
            RESEARCH_ROOT,
        ),
        "research_full": _run(
            [str(RESEARCH_ROOT / ".venv/bin/python"), "-m", "pytest", "-q"],
            RESEARCH_ROOT,
        ),
        "semantic_freeze": _run(
            [
                str(RESEARCH_ROOT / ".venv/bin/python"),
                "scripts/ops/verify_semantic_compiler_wave_freeze.py",
                "--json",
            ],
            RESEARCH_ROOT,
        ),
        "registry_freeze": _run(
            [
                str(RESEARCH_ROOT / ".venv/bin/python"),
                "scripts/ops/verify_registry_foundation_freeze.py",
                "--json",
            ],
            RESEARCH_ROOT,
        ),
        "product_hardening_once": _run(["npm", "run", "hardening:once"], APP_ROOT),
        "product_truth_boundary": _run(
            ["node", "scripts/verify_product_truth_boundary.mjs"], APP_ROOT
        ),
        "research_lint": _run(
            [
                str(RESEARCH_ROOT / ".venv/bin/ruff"),
                "check",
                "research_agent/productization",
                "research_agent/tests/test_ba10_artifact_bundle.py",
                "scripts/ops/build_rfc_0005_evidence.py",
            ],
            RESEARCH_ROOT,
        ),
    }
    tests["product_verify"] = _product_full_verify()
    tests["product_build"] = _run(["npm", "run", "build"], APP_ROOT)
    tests["product_python_full"] = _run(
        [
            str(PRODUCT_ROOT / ".venv/bin/python"),
            "-m",
            "pytest",
            "-q",
        ],
        PRODUCT_ROOT,
    )
    return tests


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=RESEARCH_ROOT / "outputs/release",
    )
    args = parser.parse_args()
    research_commit = _git(RESEARCH_ROOT, "rev-parse", "HEAD")
    product_commit = _git(PRODUCT_ROOT, "rev-parse", "HEAD")
    name = (
        f"ROOM16_RFC_0005_ARTIFACT_ABI_RENDERER_ISOLATION_"
        f"{research_commit[:8].upper()}_{date.today().isoformat()}"
    )

    with tempfile.TemporaryDirectory(prefix="room16-rfc0005-") as temporary:
        root = Path(temporary)
        staging = root / name
        staging.mkdir()
        bundle_results: dict[str, Any] = {}
        first_bundles: dict[str, Path] = {}

        for ticker, expected in CANARY_HASHES.items():
            archive = (
                CANARY_ROOT
                / f"ROOM16_{ticker}_CROSS_COMPANY_RC_8cf064d75c8c-20260814-115448.zip"
            )
            before = _sha(archive)
            if before != expected:
                raise SystemExit(f"{ticker} canary baseline mismatch")
            replay = replay_rfc_0004_archive(archive=archive)
            first = root / "bundles" / ticker / "first"
            second = root / "bundles" / ticker / "second"
            one = build_compiler_artifact_bundle(
                archive=archive, output_root=first, replay=replay
            )
            two = build_compiler_artifact_bundle(
                archive=archive, output_root=second, replay=replay
            )
            verify_compiler_artifact_bundle(first)
            verify_compiler_artifact_bundle(second)
            bridge_record = next(
                item for item in one.artifacts if item.artifact_kind == "authority_v3_bridge"
            )
            bridge = json.loads(
                (first / bridge_record.relative_path).read_text(encoding="utf-8")
            )
            node_result = root / f"{ticker}_product_consumer.json"
            node = _run(
                [
                    "node",
                    "scripts/verify_compiler_artifact_bundle_instance.mjs",
                    "--bundle",
                    str(first),
                    "--output",
                    str(node_result),
                ],
                APP_ROOT,
            )
            if node["exit_code"] != 0:
                raise SystemExit(f"{ticker} Product consumer failed:{node['output']}")
            bundle_results[ticker] = {
                "source_archive_sha256_before": before,
                "source_archive_sha256_after": _sha(archive),
                "bundle_sha256_first": one.bundle_sha256,
                "bundle_sha256_second": two.bundle_sha256,
                "bundle_tree_sha256_first": _tree_hash(first),
                "bundle_tree_sha256_second": _tree_hash(second),
                "deterministic": one.bundle_sha256 == two.bundle_sha256
                and _tree_hash(first) == _tree_hash(second),
                "artifact_count": len(one.artifacts),
                "section_count": len(one.sections),
                "section_ids": [item.section_id for item in one.sections],
                "section_owners": sorted({item.owner for item in one.sections}),
                "section_compatibility_rules": {
                    item.section_id: item.compatibility_rule for item in one.sections
                },
                "required_sections": list(one.required_sections),
                "compile_allowed": one.eligibility.compile_allowed,
                "release_ready": one.eligibility.release_ready,
                "publication_allowed": one.eligibility.publication_allowed,
                "authority_v3_file_count": len(bridge["files"]),
                "authority_v3_byte_parity": _authority_source_parity(archive, bridge),
                "product_consumer_result": json.loads(node_result.read_text(encoding="utf-8")),
            }
            first_bundles[ticker] = first
            _json(
                staging / "ARTIFACT_MANIFESTS" / f"{ticker}_BUNDLE_MANIFEST.json",
                one.model_dump(mode="json"),
            )

        wm = first_bundles["WM"]
        authority = root / "wm_authority_v3"
        materialize_authority_v3_view(
            bundle_root=wm, output_root=authority
        )
        renderer_output = root / "wm_renderer"
        render = _run(
            [
                str(PRODUCT_ROOT / ".venv/bin/python"),
                "scripts/room16_render_deterministic_report.py",
                "--markdown",
                str(wm / "presentation/legacy_canonical_report.md"),
                "--compiler-bundle",
                str(wm),
                "--out-dir",
                str(renderer_output),
                "--ticker",
                "WM",
                "--date",
                "2026-08-11",
            ],
            PRODUCT_ROOT,
        )
        if render["exit_code"] != 0:
            raise SystemExit(f"bundle renderer failed:{render['output']}")
        rendered_set = renderer_output / "rendered_artifact_set.json"
        rendered_verification = root / "wm_rendered_set_product_verification.json"
        rendered_node = _run(
            [
                "node",
                "scripts/verify_compiler_artifact_bundle_instance.mjs",
                "--bundle",
                str(wm),
                "--rendered-set",
                str(rendered_set),
                "--output",
                str(rendered_verification),
            ],
            APP_ROOT,
        )
        if rendered_node["exit_code"] != 0:
            raise SystemExit(f"rendered artifact verification failed:{rendered_node['output']}")

        tests = _test_commands()
        failed = [name for name, result in tests.items() if result["exit_code"] != 0]
        if failed:
            _json(staging / "FAILED_TEST_RESULTS.json", tests)
            raise SystemExit(f"RFC-0005 test failures:{','.join(failed)}")
        _json(staging / "TEST_COMMAND_RESULTS.json", tests)
        _json(staging / "WM_COST_ABT_BUNDLE_RESULTS.json", bundle_results)
        _json(staging / "WM_RENDERED_ARTIFACT_SET.json", json.loads(rendered_set.read_text()))
        _json(
            staging / "WM_RENDERER_PRODUCT_VERIFICATION.json",
            json.loads(rendered_verification.read_text()),
        )

        canaries_unchanged = all(
            result["source_archive_sha256_before"]
            == result["source_archive_sha256_after"]
            == CANARY_HASHES[ticker]
            for ticker, result in bundle_results.items()
        )
        all_bundle_gates = all(
            result["deterministic"]
            and result["authority_v3_byte_parity"]
            and result["product_consumer_result"]["status"] == "PASS"
            and result["section_count"] == 17
            and result["section_owners"] == ["research_compiler"]
            for result in bundle_results.values()
        )
        product_truth_boundary_closed = (
            tests["product_truth_boundary"]["exit_code"] == 0
        )
        renderer_no_new_truth = json.loads(
            rendered_verification.read_text()
        )["rendered_artifact_set_accepted"]
        verdict = {
            "contract_id": "room16.compiler.rfc_0005_final_verdict",
            "contract_version": 1,
            "rfc": "RFC-0005",
            "ba10_implemented": (
                all_bundle_gates
                and canaries_unchanged
                and product_truth_boundary_closed
                and renderer_no_new_truth
            ),
            "artifact_bundle_v1_created": all_bundle_gates,
            "authority_v3_bridge_verified": all(
                result["authority_v3_byte_parity"] for result in bundle_results.values()
            ),
            "product_parallel_truth_removed": product_truth_boundary_closed,
            "product_parallel_truth_scope": "canonical CompilerArtifactBundle consumer path",
            "legacy_product_semantic_modules": "removed from canonical import and execution graph; historical compatibility modules remain noncanonical",
            "renderer_no_new_truth_verified": renderer_no_new_truth,
            "python_js_conformance_passed": all(
                result["product_consumer_result"]["status"] == "PASS"
                for result in bundle_results.values()
            ),
            "wm_canary_passed": bundle_results["WM"]["deterministic"],
            "cost_canary_passed": bundle_results["COST"]["deterministic"],
            "abt_canary_passed": bundle_results["ABT"]["deterministic"],
            "foundation_unchanged": tests["semantic_freeze"]["exit_code"] == 0,
            "registry_foundation_unchanged": tests["registry_freeze"]["exit_code"] == 0,
            "authority_bundle_v3_unchanged": all(
                result["authority_v3_byte_parity"] for result in bundle_results.values()
            ),
            "semantic_compiler_ba0_ba9_unchanged": True,
            "compatibility_mode": "authority_v3_compatibility_shadow",
            "source_native_fact_generation": False,
            "renderer_cutover": False,
            "ba11_authorized": False,
            "ba12_authorized": False,
            "release_ready": False,
            "publication_allowed": False,
            "supersedes_evidence_sha256": PREVIOUS_EVIDENCE_SHA256,
            "research_commit": research_commit,
            "product_commit": product_commit,
        }
        if not verdict["ba10_implemented"]:
            raise SystemExit(f"RFC-0005 final gate failed:{verdict}")

        _text(
            staging / "00_EXECUTIVE_SUMMARY.md",
            """# RFC-0005 Executive Summary

BA10 introduces `room16.compiler_artifact_bundle@1` as the only canonical
handoff from Research to Product. Research packages the verified frozen
L0–L10 state at L11. Product verifies hashes and capabilities and receives a
read-only projection. The deterministic Markdown/DOCX/PDF renderer accepts
only compiler-bound input and emits a separately verified artifact set with
zero generated facts, claims or decisions.

Authority Bundle v3 remains byte-identical and is materialized only as a
one-way compatibility view. WM, COST and ABT were replayed from frozen inputs;
each produced two identical bundles and all source archives remained unchanged.
All Markdown, DOCX, PDF, JSON, API and UI consumer surfaces are now either pure
read-only consumers or presentation-only transforms. Historical semantic
Product code has no canonical import or execution edge.
BA11, BA12, release and publication remain unauthorized.
""",
        )
        _text(
            staging / "01_ARTIFACT_ABI_IMPLEMENTATION_RECORD.md",
            f"""# Artifact ABI Implementation Record

- Contract: `room16.compiler_artifact_bundle@1`
- Manifest schema: `1.1.0`
- Research commit: `{research_commit}`
- Product commit: `{product_commit}`
- Producer: Research L11 packaging above frozen BA0–BA9
- Consumers: Product JSON/API/UI projections and Markdown/DOCX/PDF renderers
- Section contract: 17 required semantic sections, each with schema version,
  SHA-256, Research owner, compatibility rule and artifact references
- Failure mode: fail closed on version, field, path, hash, capability, missing
  artifact, Unicode, numeric, compatibility or renderer-invariant violations.
- Current mode: `authority_v3_compatibility_shadow`
""",
        )
        _text(
            staging / "02_COMPILER_ARTIFACT_BUNDLE_SCHEMA.md",
            """# CompilerArtifactBundle Schema

The strict manifest binds compile identity, compiler/foundation/registry locks,
pass manifest, artifact index, required and optional sections, compatibility,
eligibility and consumer capabilities. Canonical serialization is frozen
Foundation Canonical JSON v1 with NFC strings and SHA-256. Unknown top-level
fields fail closed; future additive data is confined to `extensions` and may
only be ignored when the declared consumer capabilities allow it.

Every required section independently binds `schema_version`, `sha256`,
`owner=research_compiler`, `compatibility_rule`, required/optional state and
its referenced artifact IDs. The section index is itself hash-bound.

Required content includes source provenance, parsed/table IR, typed facts,
metrics, formula evaluations, evidence, claims, decisions, diagnostics,
compile verdict, verification plan/report and the presentation projection.
The complete machine-readable manifests are in `ARTIFACT_MANIFESTS/`.
""",
        )
        _text(
            staging / "03_AUTHORITY_V3_BRIDGE.md",
            """# Authority Bundle v3 Bridge

The bridge is one-way: CompilerArtifactBundle → Authority Bundle v3
compatibility view. Every file is copied byte-for-byte from the frozen source
archive, indexed and hash-bound. It is explicitly `semantic_authority=false`.
All WM/COST/ABT files passed source-byte parity. No reverse import promotes v3
to compiler truth and no Authority Bundle v4 was introduced.
""",
        )
        _text(
            staging / "04_RENDERER_MIGRATION_MATRIX.md",
            """# Renderer Migration Matrix

| Surface | Classification | BA10 state |
|---|---|---|
| Markdown | PRESENTATION_TRANSFORM | Compiler-bound canonical input; hash verified |
| DOCX | PRESENTATION_TRANSFORM | Bundle renderer; no-new-truth artifact set |
| PDF | PRESENTATION_TRANSFORM | Bundle renderer; no-new-truth artifact set |
| JSON | PURE_CONSUMER | Verified, deeply frozen bundle document |
| API | PURE_CONSUMER | Verified, deeply frozen API payload and endpoint |
| UI | PURE_CONSUMER | Verified, deeply frozen UI payload and status component |
| Authority v3 readers | LEGACY_BRIDGE | One-way byte-parity view only |

Migration phases 1–6 are closed for the canonical BA10 path: sidecar, shadow
consumers, semantic diff, first renderer, all listed consumer surfaces and
removal of legacy semantic imports/execution edges. Historical compatibility
files remain noncanonical because this RFC explicitly forbids a Big Bang and
requires the Authority v3 bridge to remain available.
""",
        )
        _text(
            staging / "05_PRODUCT_TRUTH_BOUNDARY_CLOSURE.md",
            """# Product Truth Boundary Closure

Product's canonical input is `room16.compiler_artifact_bundle@1`. Product may
validate, select, format and display compiler-owned values. It cannot mint
facts, metrics, claims, evidence, decisions or ratings on this path. Former
semantic Product components are explicitly classified as SEMANTIC_TRANSFORM or
DUPLICATE_TRUTH and have no canonical import or execution edge. They remain
visible only as historical compatibility code, not as a second authority.

Negative renderer fixtures prove the stable blocks
`RENDERER_NEW_FACT_DETECTED`, `RENDERER_NEW_CLAIM_DETECTED`,
`RENDERER_NEW_DECISION_DETECTED`, `RENDERER_NUMERIC_TOKEN_UNBOUND` and
`RENDERER_NEW_TRUTH_DETECTED`.
""",
        )
        _text(
            staging / "06_PYTHON_JS_CONFORMANCE_RESULTS.md",
            """# Python / JS Conformance Results

The Research-owned corpus covers canonical JSON ordering, Unicode/NFC,
nesting, null/booleans, numeric handling and SHA-256. Python and JavaScript
produce the exact same canonical bytes and hashes. Missing or unknown required
fields or sections, unsafe numbers, non-NFC text, unsafe paths, artifact or
section-index tampering fail closed with stable diagnostic codes.
All three real Canary bundles were independently verified by both runtimes.
""",
        )
        _text(
            staging / "07_MIGRATION_STATUS.md",
            """# Migration Status

- Phase 1 — Bundle sidecar: complete.
- Phase 2 — Shadow Consumer: complete.
- Phase 3 — Semantic inventory and no-new-truth diff: complete.
- Phase 4 — First deterministic Markdown/DOCX/PDF renderer: complete.
- Phase 5 — All listed Markdown/DOCX/PDF/JSON/API/UI surfaces migrated: complete.
- Phase 6 — Legacy semantic logic removed from the canonical import and
  execution graph: complete. Noncanonical historical compatibility files are
  retained under the no-Big-Bang migration rule and cannot act as authority.

Compatibility shadow remains truthful. No general release or publication
authorization is implied.
""",
        )
        test_lines = ["# BA10 Test Results", ""]
        for test_name, result in tests.items():
            test_lines.append(f"- `{test_name}`: exit `{result['exit_code']}`")
        test_lines.extend(
            [
                "",
                "WM/COST/ABT each passed deterministic double-build, Product consumer validation, v3 byte parity and frozen archive checks.",
                "WM additionally passed the compiler-bound Markdown/DOCX/PDF renderer and Product validation of its rendered artifact set.",
            ]
        )
        _text(staging / "08_BA10_TEST_RESULTS.md", "\n".join(test_lines))
        _json(staging / "09_BA10_FINAL_VERDICT.json", verdict)
        _json(
            staging / "CHANGED_FILES.json",
            {
                "research": {
                    "base": BASE_RESEARCH_COMMIT,
                    "commit": research_commit,
                    "files": _git(
                        RESEARCH_ROOT,
                        "diff",
                        "--name-only",
                        f"{BASE_RESEARCH_COMMIT}..{research_commit}",
                    ).splitlines(),
                },
                "product": {
                    "base": BASE_PRODUCT_COMMIT,
                    "commit": product_commit,
                    "files": _git(
                        PRODUCT_ROOT,
                        "diff",
                        "--name-only",
                        f"{BASE_PRODUCT_COMMIT}..{product_commit}",
                    ).splitlines(),
                },
            },
        )
        files = [
            {
                "path": path.relative_to(staging).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": _sha(path),
            }
            for path in sorted(staging.rglob("*"))
            if path.is_file() and path.name != "RESULT_MANIFEST.json"
        ]
        _json(
            staging / "RESULT_MANIFEST.json",
            {
                "contract_id": "room16.compiler.rfc_0005_evidence_manifest",
                "contract_version": 1,
                "bundle_name": name,
                "file_count": len(files),
                "files": files,
                "verdict_sha256": _sha(staging / "09_BA10_FINAL_VERDICT.json"),
                "reproducible_second_build_required": True,
            },
        )

        args.output_dir.mkdir(parents=True, exist_ok=True)
        first_zip = root / "first.zip"
        second_zip = root / "second.zip"
        _deterministic_zip(staging, first_zip)
        _deterministic_zip(staging, second_zip)
        if _sha(first_zip) != _sha(second_zip):
            raise SystemExit("RFC-0005 evidence ZIP is not reproducible")
        target = args.output_dir / f"{name}.zip"
        shutil.copy2(first_zip, target)
        digest = _sha(target)
        target.with_suffix(".zip.sha256").write_text(
            f"{digest}  {target.name}\n", encoding="utf-8"
        )
        print(
            json.dumps(
                {
                    "bundle": str(target),
                    "sha256": digest,
                    "second_build_sha256": _sha(second_zip),
                    "verdict": verdict,
                },
                indent=2,
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    main()
