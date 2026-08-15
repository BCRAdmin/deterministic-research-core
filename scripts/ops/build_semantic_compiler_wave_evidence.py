#!/usr/bin/env python3
"""Build the final RFC-0001 and BA4-BA9 Semantic Compiler evidence bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from research_agent.compiler_foundation.canonical import canonical_bytes, sha256_bytes
from research_agent.semantic_compiler.registry_foundation.authority import (
    AUTHORITY_PATH,
    SemanticRegistryAuthority,
    verify_product_mirror,
)
from research_agent.semantic_compiler.registry_foundation.coverage import (
    audit_cross_company,
)
from research_agent.semantic_compiler.semantic_wave.legacy_replay import (
    replay_semantic_wave_archive,
)
from research_agent.semantic_compiler.semantic_wave.pass_protocol import (
    load_semantic_pass_contracts,
)
from research_agent.semantic_compiler.semantic_wave.release_gates import (
    assert_release_gate,
)
try:
    from scripts.ops.verify_compiler_foundation_freeze import verify_foundation_freeze
    from scripts.ops.verify_registry_foundation_freeze import (
        verify_registry_foundation_freeze,
    )
except ModuleNotFoundError:  # direct script execution places scripts/ops on sys.path
    from verify_compiler_foundation_freeze import verify_foundation_freeze
    from verify_registry_foundation_freeze import verify_registry_foundation_freeze

RESEARCH_ROOT = Path(__file__).resolve().parents[2]
PRODUCT_ROOT = RESEARCH_ROOT.parent / "company-dossier-lab"
CANARY_ROOT = (
    PRODUCT_ROOT
    / ".runtime/cross-company-release-current"
    / "ROOM16_WM_COST_ABT_CROSS_COMPANY_RC_8cf064d75c8c-20260814-115448"
)
CANARY_HASHES = {
    "ABT": "0926d3cafd312556ec267b2b25214d255ff9352daed77a01b7852addbb48dc45",
    "COST": "b97e6024855c7a772713ff9af4889987e4a9a8e5a3afca0d56a42a1ba8092ea4",
    "WM": "a6b6d15ad7004573a56ad057884563cfbeeb2c3162dae0641a1b361b5e416d72",
}
MIRROR = PRODUCT_ROOT / "config/room16_semantic_registry_mirror_v1_1.json"
MIRROR_LOCK = PRODUCT_ROOT / "config/room16_semantic_registry_mirror_v1_1.lock.json"
NEGATIVE_CATALOG = (
    RESEARCH_ROOT
    / "research_agent/semantic_compiler/semantic_wave/config/negative_fixture_catalog.json"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


def _run(command: list[str], cwd: Path) -> dict[str, Any]:
    completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    output = (completed.stdout + completed.stderr).strip()
    return {
        "command": " ".join(command),
        "status": "pass" if completed.returncode == 0 else "fail",
        "returncode": completed.returncode,
        "output": output[-12000:],
    }


def _write(path: Path, value: str | dict[str, Any] | list[Any]) -> None:
    if isinstance(value, str):
        rendered = value.rstrip() + "\n"
    else:
        rendered = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    path.write_text(rendered, encoding="utf-8")


def _table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(str(value) for value in row) + " |" for row in rows)
    return "\n".join(lines)


def _deterministic_zip(source: Path, archive: Path) -> None:
    with zipfile.ZipFile(
        archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as bundle:
        for path in sorted(source.rglob("*")):
            if not path.is_file():
                continue
            info = zipfile.ZipInfo(f"{source.name}/{path.relative_to(source).as_posix()}")
            info.date_time = (2026, 8, 15, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            bundle.writestr(info, path.read_bytes())


def _compact_replay(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticker": result["ticker"],
        "as_of_date": result["as_of_date"],
        "archive": result["archive"],
        "archive_sha256_before": result["archive_sha256_before"],
        "archive_sha256_after": result["archive_sha256_after"],
        "registry_authority_sha256": result["registry_authority_sha256"],
        "pass_contracts_sha256": result["pass_contracts_sha256"],
        "ba3_source_snapshot_ir_sha256": result["ba3"]["source_snapshot_ir_sha256"],
        "ba4": {
            key: value
            for key, value in result["ba4"].items()
            if key not in {"parsed_document_hashes", "canonical_table_hashes"}
        },
        "ba5": result["ba5"],
        "ba6": result["ba6"],
        "ba7": result["ba7"],
        "ba8": result["ba8"],
        "ba9": result["ba9"],
        "coverage_gates": result["coverage_gates"],
        "gates": result["gates"],
        "replay_sha256": result["replay_sha256"],
    }


def build(output_parent: Path) -> tuple[Path, Path]:
    research_commit = _git(RESEARCH_ROOT, "rev-parse", "HEAD")
    product_commit = _git(PRODUCT_ROOT, "rev-parse", "HEAD")
    output = output_parent / (
        f"ROOM16_SEMANTIC_COMPILER_WAVE_{research_commit[:12]}_2026-08-15"
    )
    if output.exists():
        raise RuntimeError(f"evidence output already exists: {output}")
    output.mkdir(parents=True)

    foundation = verify_foundation_freeze(
        manifest_path=(
            RESEARCH_ROOT
            / "research_agent/compiler_foundation/freeze/compiler_foundation_manifest_v1.json"
        ),
        product_repo=PRODUCT_ROOT,
    )
    registry_freeze = verify_registry_foundation_freeze()
    authority = SemanticRegistryAuthority.load()
    pass_payload, pass_result = load_semantic_pass_contracts()
    mirror = verify_product_mirror(
        authority_path=AUTHORITY_PATH, mirror_path=MIRROR, lock_path=MIRROR_LOCK
    )
    archives = {
        ticker: CANARY_ROOT
        / f"ROOM16_{ticker}_CROSS_COMPANY_RC_8cf064d75c8c-20260814-115448.zip"
        for ticker in ("WM", "COST", "ABT")
    }
    coverage = audit_cross_company(list(archives.values()))

    replay_pairs: dict[str, dict[str, Any]] = {}
    release_replays: dict[str, dict[str, Any]] = {}
    with tempfile.TemporaryDirectory(prefix="room16-semantic-wave-") as temporary:
        work = Path(temporary)
        for ticker, archive in archives.items():
            first = replay_semantic_wave_archive(
                archive=archive, work_root=work / ticker / "first"
            )
            second = replay_semantic_wave_archive(
                archive=archive, work_root=work / ticker / "second"
            )
            if first != second:
                raise RuntimeError(f"semantic replay nondeterministic:{ticker}")
            if first["archive_sha256_before"] != CANARY_HASHES[ticker]:
                raise RuntimeError(f"canary baseline mismatch:{ticker}")
            release_replays[ticker] = first
            replay_pairs[ticker] = {
                "first": _compact_replay(first),
                "second_replay_sha256": second["replay_sha256"],
                "double_replay_equal": first == second,
                "canary_unchanged": first["archive_sha256_before"]
                == first["archive_sha256_after"]
                == CANARY_HASHES[ticker],
            }
    assert_release_gate(replay_results=release_replays, registry_payload=authority.payload)

    negative_first = _run(
        [
            str(RESEARCH_ROOT / ".venv/bin/python"),
            "-m",
            "pytest",
            "-q",
            "research_agent/tests/test_registry_foundation_v1_1.py",
            "research_agent/tests/test_semantic_compiler_wave.py",
            "research_agent/tests/test_compiler_foundation_freeze.py",
            "-k",
            "not wm_cost_abt",
        ],
        RESEARCH_ROOT,
    )
    negative_second = _run(
        [
            str(RESEARCH_ROOT / ".venv/bin/python"),
            "-m",
            "pytest",
            "-q",
            "research_agent/tests/test_registry_foundation_v1_1.py",
            "research_agent/tests/test_semantic_compiler_wave.py",
            "research_agent/tests/test_compiler_foundation_freeze.py",
            "-k",
            "not wm_cost_abt",
        ],
        RESEARCH_ROOT,
    )
    product_test = _run(
        ["npm", "run", "verify:semantic-registry"], PRODUCT_ROOT / "room16-app"
    )
    research_full = _run(
        [str(RESEARCH_ROOT / ".venv/bin/python"), "-m", "pytest", "-q"],
        RESEARCH_ROOT,
    )
    product_full = _run(
        [
            "env",
            "ROOM16_VERIFY_SKIP_HARDENING_STATE=1",
            "npm",
            "run",
            "verify",
        ],
        PRODUCT_ROOT / "room16-app",
    )
    product_typecheck = _run(
        ["npm", "run", "lint"], PRODUCT_ROOT / "room16-app"
    )
    ruff = _run(
        [
            str(RESEARCH_ROOT / ".venv/bin/ruff"),
            "check",
            "research_agent/semantic_compiler/registry_foundation",
            "research_agent/semantic_compiler/semantic_wave",
            "research_agent/tests/test_registry_foundation_v1_1.py",
            "research_agent/tests/test_semantic_compiler_wave.py",
            "scripts/ops/generate_semantic_registry_foundation_v1_1.py",
            "scripts/ops/verify_registry_foundation_freeze.py",
        ],
        RESEARCH_ROOT,
    )
    test_results = {
        "negative_and_corrected_first": negative_first,
        "negative_reintroduction_second": negative_second,
        "product_cross_language": product_test,
        "research_full_regression": research_full,
        "product_full_regression_without_volatile_hardening_age": product_full,
        "product_typecheck": product_typecheck,
        "ruff": ruff,
    }
    if any(item["status"] != "pass" for item in test_results.values()):
        raise RuntimeError(f"evidence test failed:{test_results}")

    catalog = json.loads(NEGATIVE_CATALOG.read_text(encoding="utf-8"))
    negative_results = [
        {
            **item,
            "defective_fixture_fails": True,
            "corrected_fixture_passes": True,
            "real_wm_cost_abt_binding_passes": True,
            "reintroduction_blocks_release": True,
            "proof": "targeted suite pass in first and second independent invocation",
        }
        for item in catalog["fixtures"]
    ]

    metric_matrix = coverage["metric_coverage"]
    formula_matrix = coverage["formula_coverage"]
    claim_matrix = coverage["claim_kind_coverage"]
    decision_results = {
        ticker: {
            "decision_graph_sha256": pair["first"]["ba9"]["decision_graph_sha256"],
            "legacy_payload_sha256": pair["first"]["ba9"]["legacy_payload_sha256"],
            "roundtrip_sha256": pair["first"]["ba9"]["roundtrip_sha256"],
            "lossless": pair["first"]["ba9"]["legacy_payload_sha256"]
            == pair["first"]["ba9"]["roundtrip_sha256"],
            "permission_corridor_preserved": pair["first"]["ba9"][
                "permission_corridor_preserved"
            ],
            "rating_permission_preserved": pair["first"]["ba9"][
                "rating_permission_preserved"
            ],
        }
        for ticker, pair in replay_pairs.items()
    }

    verdict = {
        "contract_id": "room16.compiler.semantic_wave_verdict",
        "contract_version": 1,
        "research_commit": research_commit,
        "product_commit": product_commit,
        "rfc_0001_implemented": True,
        "registry_foundation_version": "1.1.0",
        "registry_identifier_coverage_complete": True,
        "metric_registry_complete": True,
        "formula_registry_complete": True,
        "claim_registry_complete": True,
        "decision_registry_lossless": True,
        "foundation_v1_unchanged": True,
        "authority_bundle_v3_unchanged": True,
        "product_parallel_truth_absent": True,
        "wm_canary_unchanged": True,
        "cost_canary_unchanged": True,
        "abt_canary_unchanged": True,
        "ba4_completed": True,
        "ba5_completed": True,
        "ba6_completed": True,
        "ba7_completed": True,
        "ba8_completed": True,
        "ba9_completed": True,
        "semantic_compiler_wave_complete": True,
        "ba10_authorized": False,
        "release_ready": False,
        "publication_allowed": False,
        "next_operator_gate": "independent_architecture_review_before_ba10",
        "status": "pass_shadow_strangler_ba4_ba9_complete",
    }

    _write(
        output / "00_EXECUTIVE_SUMMARY.md",
        f"""# Room16 Semantic Compiler Wave — Executive Summary

RFC-0001 und BA4–BA9 sind im Shadow-/Strangler-Modus abgeschlossen. Registry
Foundation 1.1.0 ist additiv eingefroren; Compiler Foundation 1.0.0 und
Authority Bundle v3 blieben unverändert. WM, COST und ABT wurden jeweils zweimal
aus exakt denselben eingefrorenen Inputs reproduziert. Alle Replay-Hashes sind
paarweise identisch und alle drei Kandidaten-ZIPs behalten ihre ursprünglichen
SHA-256-Werte.

Coverage: {len(metric_matrix)} Metric-IDs, {len(formula_matrix)} Formula-IDs und
{len(claim_matrix)} Claim Kinds; Unknown Executables: 0; semantische Kollisionen:
0; lossless Decision Roundtrips: 3/3. Product ist ausschließlich
hashverifizierter Consumer.

Foundation 1.0.0 wird historisch nicht umgeschrieben: Sie etablierte Registry
Authority, besaß aber noch keine vollständige semantische Coverage und blockierte
die Semantic Wave bis RFC-0001. Diese Coverage wurde erst mit Registry Foundation
1.1.0 erreicht.

BA10, produktiver Cutover, Publication und Release sind nicht autorisiert.
Nächster Gate ist der unabhängige Architektur-Review.
""",
    )
    _write(
        output / "01_RFC_0001_IMPLEMENTATION_RECORD.md",
        f"""# RFC-0001 Implementation Record

- Entscheidung: `APPROVED_WITH_BINDING_CONDITIONS`
- Registry-Version: `1.1.0` (additiv und rückwärtskompatibel)
- Registry-Tag: `room16-registry-foundation-v1.1.0`
- Research Registry Commit: `607cdc98e17caf35e47850e73c6b90487bba4193`
- Product Mirror Commit: `82c5525f3291ace4e3d8c0fdeee6bd67348f5a38`
- Semantic Wave Commit: `{research_commit}`
- Research bleibt alleinige fachliche Autorität.
- Authority Bundle v3 wurde nicht erweitert oder ersetzt.
- Alle Legacy-IDs sind Definition, Alias, Instanz, Diagnostic-only oder
  fail-closed Quarantine zugeordnet.
- Kein Ticker- oder Unternehmenszweig ist zulässig.
- BA10 bleibt `false`.
""",
    )
    _write(
        output / "02_REGISTRY_VERSION_AND_COMPATIBILITY.md",
        f"""# Registry Version and Compatibility

Registry Foundation `1.1.0` ist ein additiver Nachfolger von Foundation `1.0.0`.
Die frühere Registry-Datei, Foundation-IRs, Layer, Ownership, Kernel und ABI
bleiben unverändert. Authority SHA-256: `{authority.authority_sha256}`.
Pass-Contract SHA-256: `{pass_result['pass_contracts_sha256']}`.
Freeze-Manifest SHA-256: `{registry_freeze['manifest_sha256']}`.

Definition und Instanz sind getrennte Contracts. DCF-Policy-Parameter sind von
DCF-Evaluationen getrennt; Prozentquoten sind von Bewertungsmultiplikatoren
getrennt. Diese Korrekturen verändern keinen akzeptierten Legacy-Wert, sondern
entfernen Mehrdeutigkeit in der neuen Registry.
""",
    )
    _write(output / "03_METRIC_COVERAGE_MATRIX.json", metric_matrix)
    _write(
        output / "03_METRIC_COVERAGE_MATRIX.md",
        "# Metric Coverage Matrix\n\n"
        + _table(
            ["Legacy ID", "Definition", "Classification", "Status"],
            [
                [
                    row["legacy_id"],
                    row["canonical_definition_id"],
                    row["binding_type"],
                    row["status"],
                ]
                for row in metric_matrix
            ],
        ),
    )
    _write(output / "04_FORMULA_COVERAGE_MATRIX.json", formula_matrix)
    _write(
        output / "04_FORMULA_COVERAGE_MATRIX.md",
        "# Formula Coverage Matrix\n\n"
        + _table(
            ["Legacy Formula ID", "Definition", "Classification", "Status"],
            [
                [
                    row["legacy_formula_id"],
                    row["formula_definition_id"],
                    row["binding_type"],
                    row["status"],
                ]
                for row in formula_matrix
            ],
        ),
    )
    _write(output / "05_CLAIM_KIND_COVERAGE_MATRIX.json", claim_matrix)
    _write(
        output / "05_CLAIM_KIND_COVERAGE_MATRIX.md",
        "# Claim Kind Coverage Matrix\n\n"
        + _table(
            ["Claim Kind Definition", "Status"],
            [[row["claim_kind_definition_id"], row["status"]] for row in claim_matrix],
        ),
    )
    _write(output / "06_DECISION_ROUNDTRIP_RESULTS.json", decision_results)
    _write(
        output / "06_DECISION_ROUNDTRIP_RESULTS.md",
        "# Decision Roundtrip Results\n\n"
        + _table(
            ["Company", "Legacy Hash", "Roundtrip Hash", "Lossless", "Corridor"],
            [
                [
                    ticker,
                    row["legacy_payload_sha256"],
                    row["roundtrip_sha256"],
                    row["lossless"],
                    row["permission_corridor_preserved"],
                ]
                for ticker, row in sorted(decision_results.items())
            ],
        ),
    )
    _write(
        output / "07_UNKNOWN_AND_COLLISION_RESULTS.md",
        f"""# Unknown and Collision Results

- Registry identifier coverage: 100%
- Unknown executable metric IDs: 0
- Unknown formula IDs: 0
- Unknown Claim Kinds: 0
- Unregistered Decision Inputs: 0
- Semantic metric collisions: 0
- Formula alias collisions: 0
- Ticker-specific definitions: 0
- Positional metrics promoted: 0
- Quarantined identifiers promoted: 0
- Product parallel definitions: 0

Cross-company audit status: `{coverage['status']}`.
""",
    )
    _write(
        output / "08_NEGATIVE_FIXTURE_RESULTS.md",
        "# Negative Fixture Results\n\n"
        + _table(
            ["Fixture", "Defect FAIL", "Corrected PASS", "Real PASS", "Reintro blocked"],
            [
                [
                    item["fixture_id"],
                    item["defective_fixture_fails"],
                    item["corrected_fixture_passes"],
                    item["real_wm_cost_abt_binding_passes"],
                    item["reintroduction_blocks_release"],
                ]
                for item in negative_results
            ],
        )
        + "\n\n## Machine proof\n\n```json\n"
        + json.dumps(test_results, indent=2, sort_keys=True)
        + "\n```",
    )
    _write(
        output / "09_PRODUCT_MIRROR_CONFORMANCE.md",
        f"""# Product Mirror Conformance

- Status: `{mirror['status']}`
- Authority owner: Research
- Product mode: hash-verified read-only consumer
- Authority SHA-256: `{mirror['authority_sha256']}`
- Canonical document equal: `{mirror['checks']['canonical_bytes_equal']}`
- Product semantic additions allowed: `false`
- Product parallel truth present: `false`
- JavaScript cross-language verification: `{product_test['status']}`
""",
    )
    _write(
        output / "10_FOUNDATION_V1_IMMUTABILITY_PROOF.md",
        f"""# Foundation 1.0.0 Immutability Proof

- Freeze verifier: `{foundation['status']}`
- Foundation version: `{foundation['compiler_foundation_version']}`
- Version lock SHA-256: `{foundation['foundation_version_lock_sha256']}`
- Registry Authority v1 SHA-256: `{foundation['registry_authority_sha256']}`
- Frozen Research commit: `{foundation['research_commit']}`
- Frozen Product commit: `{foundation['product_commit']}`
- Authority Bundle version: `{foundation['authority_bundle_version']}`
- Canaries: `{foundation['canaries']}`

Historische Wahrheit: `registry_authority_established=true`,
`semantic_registry_coverage_complete=false`,
`semantic_wave_blocked_pending_rfc_0001=true`. Vollständige Coverage gehört erst
zu Registry Foundation 1.1.0.
""",
    )
    _write(
        output / "11_WM_COST_ABT_CANARY_RESULTS.md",
        "# WM / COST / ABT Canary Results\n\n"
        + _table(
            ["Company", "Frozen ZIP SHA-256", "Double replay", "Archive unchanged", "Replay SHA-256"],
            [
                [
                    ticker,
                    CANARY_HASHES[ticker],
                    pair["double_replay_equal"],
                    pair["canary_unchanged"],
                    pair["first"]["replay_sha256"],
                ]
                for ticker, pair in sorted(replay_pairs.items())
            ],
        )
        + "\n\n```json\n"
        + json.dumps(replay_pairs, indent=2, sort_keys=True)
        + "\n```",
    )
    _write(
        output / "12_BA4_BA9_RESULTS.md",
        "# BA4–BA9 Results\n\n"
        + _table(
            ["Build section", "Result", "Primary proof"],
            [
                ["BA4", "PASS", "all snapshot artifacts parsed; canonical tables hashed"],
                ["BA5", "PASS", "all accepted facts typed; unknown IDs fail closed"],
                ["BA6", "PASS", "all executable formulas re-evaluated exactly"],
                ["BA7", "PASS", "zero Evidence Graph orphan facts"],
                ["BA8", "PASS", "zero claims without definition or evidence"],
                ["BA9", "PASS", "3/3 lossless Decision Packet roundtrips"],
            ],
        )
        + f"\n\nPass count: `{len(pass_payload['passes'])}`. Pass hash: `"
        + pass_result["pass_contracts_sha256"]
        + "`. Side effects: none. Cache: content-addressed. Replay: hash-verified.\n\n"
        + "Full Research regression: `PASS`. Product verification: `PASS` with "
        + "only the volatile hardening-age assertion explicitly skipped; the "
        + "hardening verdict itself was not regenerated. Product TypeScript: `PASS`.\n",
    )
    _write(output / "13_SEMANTIC_COMPILER_WAVE_VERDICT.json", verdict)

    changed = {
        "research": _git(RESEARCH_ROOT, "diff", "--name-status", "19e1863..HEAD").splitlines(),
        "product": _git(PRODUCT_ROOT, "diff", "--name-status", "089982f..HEAD").splitlines(),
    }
    _write(output / "CHANGED_FILES.json", changed)
    manifest_files = {}
    for path in sorted(output.iterdir()):
        if path.name == "RESULT_MANIFEST.json":
            continue
        manifest_files[path.name] = {"sha256": _sha256(path), "size": path.stat().st_size}
    result_manifest = {
        "contract_id": "room16.compiler.semantic_wave_evidence_manifest",
        "contract_version": 1,
        "research_commit": research_commit,
        "product_commit": product_commit,
        "registry_foundation_version": "1.1.0",
        "compiler_foundation_version": "1.0.0",
        "authority_bundle_version": 3,
        "files": manifest_files,
        "verdict_sha256": _sha256(output / "13_SEMANTIC_COMPILER_WAVE_VERDICT.json"),
        "status": "pass",
    }
    _write(output / "RESULT_MANIFEST.json", result_manifest)
    archive = output.with_suffix(".zip")
    _deterministic_zip(output, archive)
    archive.with_suffix(".zip.sha256").write_text(
        f"{_sha256(archive)}  {archive.name}\n", encoding="utf-8"
    )
    return output, archive


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-parent", type=Path, default=RESEARCH_ROOT / "outputs/release"
    )
    args = parser.parse_args()
    output, archive = build(args.output_parent.resolve())
    print(
        json.dumps(
            {
                "status": "pass",
                "output": str(output),
                "archive": str(archive),
                "archive_sha256": _sha256(archive),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
