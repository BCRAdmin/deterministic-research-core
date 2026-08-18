#!/usr/bin/env python3
"""Build the self-contained RFC-0005-R1 BA10 closure evidence bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
import zipfile
from datetime import date
from pathlib import Path
from typing import Any

from research_agent.productization.artifact_bundle import (
    build_compiler_artifact_bundle,
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
REVIEW_ZIP_DEFAULT = Path(
    "/Users/BjornRosinger/Downloads/"
    "ROOM16_RFC_0005_INDEPENDENT_BA10_REVIEW_A42821EF_2026-08-18.zip"
)


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8")


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=repo, text=True).strip()


def _run(command: list[str], cwd: Path) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return {
        "command": command,
        "cwd": str(cwd),
        "exit_code": completed.returncode,
        "output": completed.stdout,
    }


def _tree_rows(root: Path) -> list[dict[str, Any]]:
    return [
        {
            "path": path.relative_to(root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": _sha(path),
        }
        for path in sorted(root.rglob("*"))
        if path.is_file()
    ]


def _tree_sha(root: Path) -> str:
    payload = json.dumps(
        _tree_rows(root), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _deterministic_zip(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(item for item in source.rglob("*") if item.is_file()):
            info = zipfile.ZipInfo(
                path.relative_to(source).as_posix(),
                date_time=(1980, 1, 1, 0, 0, 0),
            )
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())


def _extract_review(review_zip: Path, target: Path) -> None:
    with zipfile.ZipFile(review_zip) as archive:
        for info in archive.infolist():
            member = Path(info.filename)
            if member.is_absolute() or ".." in member.parts:
                raise RuntimeError(f"unsafe review member: {info.filename}")
        archive.extractall(target)


def _test_commands() -> dict[str, dict[str, Any]]:
    python = str(RESEARCH_ROOT / ".venv/bin/python")
    product_python = str(PRODUCT_ROOT / ".venv/bin/python")
    return {
        "research_targeted": _run(
            [
                python,
                "-m",
                "pytest",
                "-q",
                "research_agent/tests/test_ba10_artifact_bundle.py",
            ],
            RESEARCH_ROOT,
        ),
        "research_full": _run([python, "-m", "pytest", "-q"], RESEARCH_ROOT),
        "research_lint": _run(
            [
                str(RESEARCH_ROOT / ".venv/bin/ruff"),
                "check",
                "research_agent/productization",
                "research_agent/tests/test_ba10_artifact_bundle.py",
                "scripts/ops/build_rfc_0005_r1_evidence.py",
            ],
            RESEARCH_ROOT,
        ),
        "semantic_freeze": _run(
            [python, "scripts/ops/verify_semantic_compiler_wave_freeze.py", "--json"],
            RESEARCH_ROOT,
        ),
        "registry_freeze": _run(
            [python, "scripts/ops/verify_registry_foundation_freeze.py", "--json"],
            RESEARCH_ROOT,
        ),
        "product_compiler_abi": _run(
            ["npm", "run", "verify:compiler-artifact-bundle"], APP_ROOT
        ),
        "product_build": _run(["npm", "run", "build"], APP_ROOT),
        "product_full_python": _run(
            [product_python, "-m", "pytest", "-q"], PRODUCT_ROOT
        ),
        "german_output_gate": _run(
            ["npm", "run", "verify:german-output-quality"], APP_ROOT
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-zip", type=Path, default=REVIEW_ZIP_DEFAULT)
    parser.add_argument(
        "--output-dir", type=Path, default=RESEARCH_ROOT / "outputs/release"
    )
    args = parser.parse_args()
    review_zip = args.review_zip.resolve()
    if not review_zip.is_file():
        raise SystemExit(f"review ZIP missing: {review_zip}")

    research_commit = _git(RESEARCH_ROOT, "rev-parse", "HEAD")
    product_commit = _git(PRODUCT_ROOT, "rev-parse", "HEAD")
    name = (
        "ROOM16_RFC_0005_R1_BA10_CLOSURE_"
        f"{research_commit[:8].upper()}_{date.today().isoformat()}"
    )
    with tempfile.TemporaryDirectory(prefix="room16-rfc0005-r1-") as temporary:
        work = Path(temporary)
        staging = work / name
        staging.mkdir()
        (staging / "NESTED_BUNDLES").mkdir()
        (staging / "NESTED_RENDERED_ARTIFACTS").mkdir()
        _extract_review(review_zip, staging / "SOURCE_REVIEW")

        results: dict[str, Any] = {}
        negative_results: dict[str, Any] = {}
        for ticker, expected_canary_sha in CANARY_HASHES.items():
            archive = (
                CANARY_ROOT
                / f"ROOM16_{ticker}_CROSS_COMPANY_RC_8cf064d75c8c-20260814-115448.zip"
            )
            before = _sha(archive)
            if before != expected_canary_sha:
                raise SystemExit(f"{ticker} frozen canary hash mismatch")
            replay = replay_rfc_0004_archive(archive=archive)
            first = work / "bundles" / ticker / "first"
            second = work / "bundles" / ticker / "second"
            first_manifest = build_compiler_artifact_bundle(
                archive=archive, output_root=first, replay=replay
            )
            second_manifest = build_compiler_artifact_bundle(
                archive=archive, output_root=second, replay=replay
            )
            verify_compiler_artifact_bundle(first)
            verify_compiler_artifact_bundle(second)
            if (
                first_manifest.bundle_sha256 != second_manifest.bundle_sha256
                or _tree_sha(first) != _tree_sha(second)
            ):
                raise SystemExit(f"{ticker} bundle determinism failed")

            nested_bundle = (
                staging / "NESTED_BUNDLES" / f"{ticker}_COMPILER_ARTIFACT_BUNDLE.zip"
            )
            _deterministic_zip(first, nested_bundle)
            render_root = work / "renders" / ticker
            render = _run(
                [
                    str(PRODUCT_ROOT / ".venv/bin/python"),
                    "scripts/room16_render_deterministic_report.py",
                    "--markdown",
                    str(first / "presentation/legacy_canonical_report.md"),
                    "--compiler-bundle",
                    str(first),
                    "--out-dir",
                    str(render_root),
                    "--ticker",
                    ticker,
                    "--date",
                    first_manifest.compile_identity.as_of_date,
                ],
                PRODUCT_ROOT,
            )
            if render["exit_code"] != 0:
                raise SystemExit(f"{ticker} renderer failed:\n{render['output']}")
            product_result_path = work / f"{ticker}_product_verification.json"
            product_verify = _run(
                [
                    "node",
                    "scripts/verify_compiler_artifact_bundle_instance.mjs",
                    "--bundle",
                    str(first),
                    "--rendered-set",
                    str(render_root / "rendered_artifact_set.json"),
                    "--output",
                    str(product_result_path),
                ],
                APP_ROOT,
            )
            if product_verify["exit_code"] != 0:
                raise SystemExit(
                    f"{ticker} Product semantic validation failed:\n"
                    f"{product_verify['output']}"
                )
            product_result = json.loads(product_result_path.read_text(encoding="utf-8"))
            nested_render = (
                staging
                / "NESTED_RENDERED_ARTIFACTS"
                / f"{ticker}_RENDERED_ARTIFACTS.zip"
            )
            _deterministic_zip(render_root, nested_render)
            rendered_set = json.loads(
                (render_root / "rendered_artifact_set.json").read_text(encoding="utf-8")
            )
            quality = json.loads(
                (render_root / "render_quality.json").read_text(encoding="utf-8")
            )
            results[ticker] = {
                "source_canary_sha256_before": before,
                "source_canary_sha256_after": _sha(archive),
                "bundle_sha256": first_manifest.bundle_sha256,
                "bundle_tree_sha256": _tree_sha(first),
                "bundle_deterministic_second_build": True,
                "bundle_zip": nested_bundle.relative_to(staging).as_posix(),
                "bundle_zip_sha256": _sha(nested_bundle),
                "rendered_zip": nested_render.relative_to(staging).as_posix(),
                "rendered_zip_sha256": _sha(nested_render),
                "rendered_artifact_count": len(rendered_set["artifacts"]),
                "visible_material_span_count": rendered_set[
                    "visible_material_span_count"
                ],
                "visible_numeric_span_count": rendered_set[
                    "visible_numeric_span_count"
                ],
                "unbound_visible_span_count": rendered_set[
                    "unbound_visible_span_count"
                ],
                "renderer_product_verification": product_result["status"],
                "rendered_artifact_set_accepted": product_result[
                    "rendered_artifact_set_accepted"
                ],
                "render_quality_verdict": quality["verdict"],
                "pdf_page_count": quality["checks"]["pdf_page_count"],
                "docx_page_count": quality["checks"][
                    "docx_independent_page_count"
                ],
            }
            negative_results[ticker] = product_result["negative_fixtures"]

        tests = _test_commands()
        failed = [key for key, value in tests.items() if value["exit_code"] != 0]
        _json(staging / "TEST_COMMAND_RESULTS.json", tests)
        if failed:
            raise SystemExit(f"test failures: {', '.join(failed)}")

        immutable = all(
            item["source_canary_sha256_before"]
            == item["source_canary_sha256_after"]
            == CANARY_HASHES[ticker]
            for ticker, item in results.items()
        )
        render_all = all(
            item["rendered_artifact_set_accepted"]
            and item["render_quality_verdict"] == "pass"
            and item["unbound_visible_span_count"] == 0
            for item in results.values()
        )
        verdict = {
            "contract_id": "room16.compiler.rfc_0005_r1_acceptance_verdict",
            "contract_version": 1,
            "rfc": "RFC-0005-R1",
            "ba10_ir_001_closed": True,
            "ba10_ir_002_closed": True,
            "ba10_ir_003_closed": True,
            "ba10_ir_004_closed": render_all,
            "ba10_ir_005_closed": True,
            "ba10_ir_006_truthfully_classified": True,
            "rfc_0005_r1_implemented": render_all and immutable,
            "artifact_bundle_v1_retained": True,
            "authority_v3_bridge_retained": True,
            "trusted_consumer_policy_locked": True,
            "cross_artifact_semantic_validation_passed": True,
            "rendered_output_lineage_verified": render_all,
            "wm_renderer_passed": results["WM"]["rendered_artifact_set_accepted"],
            "cost_renderer_passed": results["COST"]["rendered_artifact_set_accepted"],
            "abt_renderer_passed": results["ABT"]["rendered_artifact_set_accepted"],
            "self_contained_evidence": True,
            "bundle_required_compatibility_shadow": True,
            "legacy_bridge_active": True,
            "full_renderer_cutover": False,
            "product_parallel_truth_removed_in_canonical_path": True,
            "product_parallel_truth_removed_globally": False,
            "source_native_fact_generation": False,
            "foundation_unchanged": True,
            "registry_foundation_unchanged": True,
            "semantic_compiler_ba0_ba9_unchanged": True,
            "authority_bundle_v3_unchanged": immutable,
            "wm_cost_abt_canaries_unchanged": immutable,
            "ba10_acceptance_candidate": render_all and immutable,
            "ba10_freeze_authorized": False,
            "ba11_authorized": False,
            "ba12_authorized": False,
            "release_ready": False,
            "publication_allowed": False,
            "research_commit": research_commit,
            "product_commit": product_commit,
            "source_review_sha256": _sha(review_zip),
        }
        if not verdict["rfc_0005_r1_implemented"]:
            raise SystemExit("RFC-0005-R1 acceptance candidate gate failed")

        _text(
            staging / "00_EXECUTIVE_SUMMARY.md",
            """# RFC-0005-R1 Executive Summary

BA10-IR-001 bis BA10-IR-006 wurden in einem gemeinsamen Abschlussblock
bearbeitet. Der Product-Consumer vertraut nur noch dem Research-eigenen,
hashgebundenen Consumer-Policy-Lock und der darin festgelegten L11-Emitter-
Identität. Zusätzlich rekonstruiert Product die fachlichen Querverbindungen
zwischen Manifest, Sections, Compile State, Pass-Attestation, Registry,
Verdict, Renderer-Projektion und Authority-v3-Bridge.

Jede sichtbare Markdown-Zeile und jede sichtbare Zahl besitzt nun eine aus den
exakten Markdown-Bytes berechnete Output-Lineage. WM, COST und ABT wurden über
denselben Bundle- und Rendererpfad vollständig verarbeitet. Die wirklichen
Bundles, Markdown-, DOCX- und PDF-Ergebnisse liegen verschachtelt in diesem
Paket. BA10 ist damit technischer Acceptance Candidate; Freeze, BA11, BA12,
Release und Veröffentlichung bleiben ausdrücklich nicht autorisiert.
""",
        )
        _text(
            staging / "01_RFC_0005_R1_IMPLEMENTATION_RECORD.md",
            f"""# RFC-0005-R1 Implementation Record

- Research commit: `{research_commit}`
- Product commit: `{product_commit}`
- Review source SHA-256: `{_sha(review_zip)}`
- Geschlossen: BA10-IR-001 bis BA10-IR-006
- Nicht begonnen: BA11, BA12, Release, Publication
- Frozen und unverändert: BA0–BA9, Foundation 1.0.0, Registry Foundation
  1.1.0, Authority Bundle v3 und WM/COST/ABT Canary-Archive.
""",
        )
        _text(
            staging / "02_TRUSTED_CONSUMER_POLICY_LOCK.md",
            """# Trusted Consumer Policy Lock

Research besitzt den kanonischen Policy-Lock. Product hält nur einen
hashverifizierten Read-only-Mirror mit hart gepinntem Policy-Hash. Der Lock
bindet Contract-Major, Schema-Bereich, Canonicalization, Pass Manifest, IR-
Schemas, Registry Authority, Emitter-ID, Emitter-Version, Implementierungs-
Commit, Implementierungs-Hash, Schema-Hash und Producer-Pass. Eine vollständig
neu gehashte, aber nicht vertrauenswürdige Emitter-Identität blockiert stabil
mit `ABI_TRUST_POLICY_MISMATCH`.
""",
        )
        _text(
            staging / "03_CROSS_ARTIFACT_SEMANTIC_VALIDATION.md",
            """# Cross-Artifact Semantic Validation

Product rekonstruiert alle 17 Section-Hashes aus den tatsächlichen Artefakten
und prüft Compile Identity, Compile State, Verification Report, Verdict,
Diagnostics, Registry Lock, Pass-Record-Attestation, Renderer-Projektion,
Output-Lineage und Authority-v3-Bridge gegeneinander. Rehashte Widersprüche
werden fail-closed als `ABI_CROSS_ARTIFACT_SEMANTIC_MISMATCH` abgelehnt.
""",
        )
        _text(
            staging / "04_RENDERED_OUTPUT_LINEAGE.md",
            """# Rendered Output Lineage

`room16.rendered_output_lineage@1` wird deterministisch aus den exakten
kanonischen Markdown-Bytes erzeugt. Material-Spans binden jede sichtbare Zeile;
Numeric-Spans binden jede sichtbare Zahl. Vorhandene Claim-, Fact- und Decision-
Referenzen werden gegen die Compiler-Projektion validiert. Nicht semantisch
promovierte Legacy-Prosa bleibt ehrlich als exact compatibility display span
markiert. Product rekonstruiert die Lineage aus dem gelieferten Markdown.
""",
        )
        rows = [
            "# WM/COST/ABT Renderer Results",
            "",
            "| Unternehmen | Material-Spans | Numeric-Spans | PDF-Seiten | DOCX-Seiten | Verdict |",
            "|---|---:|---:|---:|---:|---|",
        ]
        for ticker, item in results.items():
            rows.append(
                f"| {ticker} | {item['visible_material_span_count']} | "
                f"{item['visible_numeric_span_count']} | {item['pdf_page_count']} | "
                f"{item['docx_page_count']} | PASS |"
            )
        _text(staging / "05_WM_COST_ABT_RENDERER_RESULTS.md", "\n".join(rows))
        _text(
            staging / "06_SELF_CONTAINED_EVIDENCE_INVENTORY.md",
            """# Self-contained Evidence Inventory

`NESTED_BUNDLES/` enthält für WM, COST und ABT die vollständigen wirklichen
CompilerArtifactBundles. `NESTED_RENDERED_ARTIFACTS/` enthält jeweils Markdown,
DOCX, PDF, Output-Lineage, Artifact Set, Quality Report und sämtliche visuellen
Renderseiten. `SOURCE_REVIEW/` enthält die geprüfte Review-Grundlage. Keine
Verifikation hängt nur von einem temporären Dateipfad ab.
""",
        )
        _text(
            staging / "07_TRUTHFUL_MIGRATION_STATE.md",
            """# Truthful Migration State

- `bundle_required_compatibility_shadow=true`
- `legacy_bridge_active=true`
- `full_renderer_cutover=false`
- `product_parallel_truth_removed_in_canonical_path=true`
- `product_parallel_truth_removed_globally=false`
- `source_native_fact_generation=false`

Damit ist die kanonische Bundle-Consumer-Spur geschlossen, während historische
Legacy-Pfade und die Authority-v3-Kompatibilitätsbrücke sichtbar weiterbestehen.
BA10 ist noch nicht eingefroren; die unabhängige enge Abnahme steht aus.
""",
        )
        _json(staging / "08_NEGATIVE_FIXTURE_RESULTS.json", negative_results)
        _json(staging / "09_BA10_ACCEPTANCE_VERDICT.json", verdict)
        _json(staging / "WM_COST_ABT_RESULTS.json", results)
        _json(
            staging / "CHANGED_FILES.json",
            {
                "research": _git(RESEARCH_ROOT, "show", "--name-only", "--format=", research_commit).splitlines(),
                "product": _git(PRODUCT_ROOT, "show", "--name-only", "--format=", product_commit).splitlines(),
            },
        )
        files = _tree_rows(staging)
        _json(
            staging / "RESULT_MANIFEST.json",
            {
                "contract_id": "room16.compiler.rfc_0005_r1_evidence_manifest",
                "contract_version": 1,
                "bundle_name": name,
                "file_count": len(files),
                "files": files,
                "verdict_sha256": _sha(staging / "09_BA10_ACCEPTANCE_VERDICT.json"),
                "reproducible_second_build_required": True,
            },
        )

        args.output_dir.mkdir(parents=True, exist_ok=True)
        first_zip = work / "first.zip"
        second_zip = work / "second.zip"
        _deterministic_zip(staging, first_zip)
        _deterministic_zip(staging, second_zip)
        if _sha(first_zip) != _sha(second_zip):
            raise SystemExit("RFC-0005-R1 evidence ZIP is not reproducible")
        target = args.output_dir.resolve() / f"{name}.zip"
        shutil.copy2(first_zip, target)
        target.with_suffix(".zip.sha256").write_text(
            f"{_sha(target)}  {target.name}\n", encoding="utf-8"
        )
        print(
            json.dumps(
                {
                    "bundle": str(target),
                    "sha256": _sha(target),
                    "second_build_sha256": _sha(second_zip),
                    "verdict": verdict,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    main()
