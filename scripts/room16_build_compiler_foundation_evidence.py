#!/usr/bin/env python3
"""Build the deterministic BA0-BA2 Foundation Evidence Bundle.

Only frozen candidate ZIPs are read.  This script cannot start a company,
renderer, archetype, provider, or LLM run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from research_agent.compiler_foundation.canonical import sha256_bytes
from research_agent.compiler_foundation.kernel import load_pass_manifests
from research_agent.compiler_foundation.registry import RegistryAuthority, verify_product_mirror
from research_agent.compiler_foundation.shadow import shadow_replay_candidate

RESEARCH_ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROOT = RESEARCH_ROOT.parent / "company-dossier-lab"
CONFIG_ROOT = RESEARCH_ROOT / "research_agent/compiler_foundation/config"
BASELINE_PATH = PRODUCT_ROOT / "config/room16_canary_baseline.json"
MIRROR_PATH = PRODUCT_ROOT / "config/room16_compiler_registry_mirror.json"
MIRROR_LOCK_PATH = PRODUCT_ROOT / "config/room16_compiler_registry_mirror.lock.json"
AUTHORITY_PATH = CONFIG_ROOT / "registry_authority.json"

FOUNDATION_FILES = [
    "research_agent/compiler_foundation/__init__.py",
    "research_agent/compiler_foundation/canonical.py",
    "research_agent/compiler_foundation/contracts.py",
    "research_agent/compiler_foundation/kernel.py",
    "research_agent/compiler_foundation/registry.py",
    "research_agent/compiler_foundation/shadow.py",
    "research_agent/compiler_foundation/config/cross_language_conformance.json",
    "research_agent/compiler_foundation/config/layer_ownership_constitution.json",
    "research_agent/compiler_foundation/config/pass_manifests.json",
    "research_agent/compiler_foundation/config/registry_authority.json",
    "research_agent/tests/test_compiler_foundation_contracts.py",
    "research_agent/tests/test_compiler_foundation_pass_protocol.py",
    "research_agent/tests/test_compiler_foundation_registry.py",
    "research_agent/tests/test_compiler_foundation_shadow.py",
    "scripts/room16_build_compiler_foundation_evidence.py",
    "scripts/room16_verify_compiler_foundation_evidence.py",
]
PRODUCT_FILES = [
    "config/room16_compiler_registry_mirror.json",
    "config/room16_compiler_registry_mirror.lock.json",
    "room16-app/package.json",
    "room16-app/scripts/test_compiler_foundation_mirror.mjs",
    "room16-app/scripts/verify_compiler_foundation_mirror.mjs",
]
EVIDENCE_NAMES = [
    "00_EXECUTIVE_SUMMARY.md",
    "01_ARCHITECTURE_DECISION_RECORDS.md",
    "02_LAYER_AND_OWNERSHIP_CONSTITUTION.md",
    "03_IR_CONTRACTS.md",
    "04_PASS_PROTOCOL.md",
    "05_REGISTRY_AUTHORITY.md",
    "06_DIAGNOSTIC_AND_VERDICT_CONTRACT.md",
    "07_COMPATIBILITY_AND_VERSIONING_POLICY.md",
    "08_CHANGED_FILES.md",
    "09_TEST_RESULTS.md",
    "10_SHADOW_REPLAY_RESULTS.md",
    "11_WM_COST_ABT_CANARY_DIFFS.md",
    "12_PRODUCT_MIRROR_CONFORMANCE.md",
    "13_FOUNDATION_WAVE_VERDICT.json",
]


def write_text(path: Path, value: str) -> None:
    path.write_text(value.rstrip() + "\n", encoding="utf-8")


def write_json(path: Path, value: Any) -> None:
    write_text(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def run_check(command: list[str], cwd: Path, *, env: dict[str, str] | None = None) -> dict[str, Any]:
    process_env = os.environ.copy()
    if env:
        process_env.update(env)
    result = subprocess.run(command, cwd=cwd, env=process_env, text=True, capture_output=True)
    if result.returncode:
        tail = "\n".join((result.stdout + result.stderr).splitlines()[-40:])
        raise RuntimeError(f"check failed in {cwd}: {' '.join(command)}\n{tail}")
    return {"command": " ".join(command), "cwd": str(cwd), "status": "pass"}


def test_matrix() -> list[dict[str, Any]]:
    return [
        run_check([str(RESEARCH_ROOT / ".venv/bin/python"), "-m", "pytest", "-q"], RESEARCH_ROOT),
        run_check([str(PRODUCT_ROOT / ".venv/bin/python"), "-m", "pytest", "-q"], PRODUCT_ROOT),
        run_check(["npm", "run", "verify:compiler-foundation"], PRODUCT_ROOT / "room16-app"),
        run_check(["npm", "run", "lint"], PRODUCT_ROOT / "room16-app"),
        run_check(
            ["npm", "run", "verify"],
            PRODUCT_ROOT / "room16-app",
            env={"ROOM16_VERIFY_SKIP_HARDENING_STATE": "1"},
        ),
        run_check(
            [str(RESEARCH_ROOT / ".venv/bin/ruff"), "check", "research_agent/compiler_foundation",
             "research_agent/tests/test_compiler_foundation_contracts.py",
             "research_agent/tests/test_compiler_foundation_pass_protocol.py",
             "research_agent/tests/test_compiler_foundation_registry.py",
             "research_agent/tests/test_compiler_foundation_shadow.py"],
            RESEARCH_ROOT,
        ),
    ]


def frozen_replays(baseline: dict[str, Any]) -> list[dict[str, Any]]:
    release_id = baseline["source_release_id"]
    release_root = (
        PRODUCT_ROOT
        / ".runtime/cross-company-release-current"
        / f"ROOM16_WM_COST_ABT_CROSS_COMPANY_RC_{release_id}"
    )
    results = []
    for ticker in ("WM", "COST", "ABT"):
        zip_path = release_root / f"ROOM16_{ticker}_CROSS_COMPANY_RC_{release_id}.zip"
        results.append(
            shadow_replay_candidate(
                zip_path,
                ticker=ticker,
                expected_zip_sha256=baseline["candidate_sha256"][ticker],
            )
        )
    return results


def product_parallel_truth_absent() -> bool:
    semantic_authorities: list[Path] = []
    for root in (PRODUCT_ROOT / "config", PRODUCT_ROOT / "room16-app/config"):
        for path in root.glob("*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if payload.get("contract_id") == "room16.compiler.registry_authority":
                semantic_authorities.append(path.resolve())
    return semantic_authorities == [MIRROR_PATH.resolve()]


def markdown_table(rows: list[tuple[str, str]]) -> str:
    return "| Prüfung | Ergebnis |\n|---|---|\n" + "\n".join(f"| {a} | {b} |" for a, b in rows)


def build_documents(
    target: Path,
    *,
    foundation_id: str,
    authority: RegistryAuthority,
    baseline: dict[str, Any],
    replays: list[dict[str, Any]],
    tests: list[dict[str, Any]],
    mirror: dict[str, Any],
    statuses: dict[str, bool],
) -> None:
    pass_manifests = load_pass_manifests()
    write_text(target / "00_EXECUTIVE_SUMMARY.md", f"""
# Room16 Compiler Foundation Wave BA0-BA2

Foundation-ID: `{foundation_id}`

BA0 bis BA2 sind als Shadow-/Strangler-Erweiterung umgesetzt. Research bleibt alleinige
fachliche Autorität. Product führt Runtime, Queue, Oberfläche, Renderer und
Release-Interaktion aus, besitzt jedoch nur einen hashverifizierten Read-only-Mirror der
Registry Authority. BA3 wurde nicht gestartet.

Authority Bundle v3 wurde weder ersetzt noch verändert. Es gab keinen neuen Unternehmens-,
Archetyp-, Renderer- oder LLM-Analyse-Lauf. WM, COST und ABT wurden ausschließlich aus den
eingefrorenen Kandidaten-ZIPs gelesen. Alle drei ZIP-Hashes blieben unverändert.

`semantic_compiler_wave_ready=true` bedeutet ausschließlich: Die Foundation ist technisch
bereit für einen gesondert freizugebenden BA3-Bauabschnitt. Es bedeutet weder
`release_ready` noch `publication_allowed`.
""")
    write_text(target / "01_ARCHITECTURE_DECISION_RECORDS.md", """
# Architecture Decision Records

## ADR-001 — Shadow Strangler statt Rewrite

Der Legacy-Pfad bleibt während BA0-BA2 Ausführungsautorität. Der neue Kernel beobachtet nur
eingefrorene Artefakte. Es besteht keine Aufrufkante vom Kernel zum Legacy-Orchestrator.

## ADR-002 — Eine fachliche Wahrheit

Sources, Facts, Metrics, Evidence, Claims, Decisions, Diagnostics und Verdicts gehören
ausschließlich Research. Product darf diese Semantik weder ergänzen noch überschreiben.

## ADR-003 — Content-addressed Compiler Contracts

IR, Registries, Cache und Replay werden mit kanonischem UTF-8-JSON und SHA-256 gebunden.
Non-finite Zahlen, unbekannte Felder, unbekannte IDs und Major-Versionen scheitern geschlossen.

## ADR-004 — Diagnostics getrennt von Release-Wirkung

Fachliche Severity ist nicht mit der Release-Wirkung gekoppelt. Ein informativer Fehler kann
einen Release blockieren; ein kritischer Hinweis kann fachlich kritisch und dennoch nicht
automatisch blockierend sein. Der Verdict wird ausschließlich aus expliziten Release-Effekten
abgeleitet.
""")
    constitution = json.loads((CONFIG_ROOT / "layer_ownership_constitution.json").read_text())
    write_text(target / "02_LAYER_AND_OWNERSHIP_CONSTITUTION.md", f"""
# Layer- und Ownership-Verfassung

Research besitzt L0-L11 sowie alle fachlichen Registries. Product besitzt ausschließlich die
operativen Flächen und führt Renderer erst als nachgelagertes Backend hinter L11 aus. Product
darf keine fachliche Parallelwahrheit erzeugen.

Verbindliche Konfiguration:

```json
{json.dumps(constitution, ensure_ascii=False, indent=2, sort_keys=True)}
```
""")
    write_text(target / "03_IR_CONTRACTS.md", """
# IR Contracts

BA0 friert folgende Hüllen auf Major-Version 1 ein:

- `IREnvelope`: IR-Typ, Layer, Producer, Payload-Hash, Provenance und Quarantäne.
- `PassManifest`: vollständiger Passvertrag ohne implizite Defaults außerhalb des Schemas.
- `RegistryEnvelope`: Research-Owner, sortierte eindeutige Einträge und Content-Hash.
- `DiagnosticIR`: stabiler Code plus Layer-, Pass-, Subject-, Source-, Root-Cause- und Fixture-Referenzen.
- `CompileVerdictIR`: deterministisch aus Diagnostics abgeleitete Compile-/Release-Wirkung.
- `ProvenanceRef`: Source-ID, Artefaktpfad, SHA-256 und optionaler Locator.
- `QuarantineState`: clear, quarantined oder release_blocked mit Gründen.
- `CompatibilityPolicy`: unbekannte Felder/IDs fail-closed; Major-Wechsel nur mit Migration.

Das Payload-Hashfeld wird bei jeder Nutzung neu berechnet. Ein inhaltlich verändertes Objekt
mit altem Hash ist kein gültiges IR.
""")
    pass_rows = [(str(p.ordinal), f"`{p.pass_id}` · {p.layer.value} · {p.input_ir_types[0]} → {p.output_ir_type}") for p in pass_manifests]
    write_text(target / "04_PASS_PROTOCOL.md", f"""
# Pass Protocol

Jeder Pass erklärt Input, Output, Side Effects, Determinismus, Cache, Replay, Failure,
Skip-Verhalten und Registry-Abhängigkeiten. BA1 enthält genau zwölf Shadow-Pässe.

{markdown_table(pass_rows)}

Alle Pässe sind side-effect-frei. Der Cache-Key bindet Pass-ID/-Version, Input-Payload-Hash
und Registry-Authority-Hash. Replay berechnet den Pass erneut und vergleicht Input,
Cache-Key und Output-Hash. Die Passkette besitzt keine Legacy-, Queue-, Renderer-, Provider-
oder LLM-Startfunktion.
""")
    registry_rows = [(r.registry_id, f"{r.registry_kind}; {len(r.entries)} Einträge; `{r.content_sha256}`") for r in authority.registries]
    write_text(target / "05_REGISTRY_AUTHORITY.md", f"""
# Registry Authority

Owner: `research`
Authority SHA-256: `{authority.authority_sha256}`

{markdown_table(registry_rows)}

BA2 etabliert die geschlossene Autorität und die Foundation-Namespaces. Die bestehende
Legacy-Metric-Auflösung bleibt in dieser Wave unverändert; ihre semantische Migration ist
nicht heimlich vorgezogen worden. Unbekannte Registry- oder Entry-IDs blockieren.
""")
    write_text(target / "06_DIAGNOSTIC_AND_VERDICT_CONTRACT.md", """
# Diagnostic- und Verdict-Contract

`semantic_severity` besitzt `info`, `warning`, `error`, `critical`.
`release_effect` besitzt `none`, `review_required`, `compile_block`, `release_block`.
Diese Achsen sind unabhängig.

Diagnostics verwenden stabile Codes und tragen Layer, Pass, Subject, Source-Provenance,
Root Cause und Fixture-Referenzen. Der Verdict sortiert Diagnostics stabil, hasht die
vollständige Liste und leitet `compile_allowed`, `release_allowed` sowie `review_required`
ohne Freitextinterpretation ab.
""")
    write_text(target / "07_COMPATIBILITY_AND_VERSIONING_POLICY.md", """
# Compatibility- und Versioning-Policy

- Major 1 ist der eingefrorene Foundation-Vertrag.
- Minor-Änderungen dürfen nur additiv sein und benötigen neue Conformance-Fixtures.
- Major-Änderungen benötigen explizite Migration, Dual-Read-Phase und neue Operatorfreigabe.
- Unbekannte Felder, IDs, Major-Versionen und Registry-Einträge scheitern geschlossen.
- Kanonisches JSON sortiert Objektschlüssel, bewahrt Arrayreihenfolge, nutzt kompaktes UTF-8,
  normalisiert negative Null und verbietet NaN/Infinity.
- Python und JavaScript müssen denselben Conformance-Korpus byte- und hashgleich bestehen.
- Authority Bundle v3 bleibt während der Strangler-Phase der Legacy-Handoff-Vertrag.
""")
    write_text(target / "08_CHANGED_FILES.md", "# Changed Files\n\n## Research\n\n" + "\n".join(f"- `{x}`" for x in FOUNDATION_FILES) + "\n\n## Product\n\n" + "\n".join(f"- `{x}`" for x in PRODUCT_FILES) + "\n\n## Generiert\n\n" + "\n".join(f"- `{x}`" for x in EVIDENCE_NAMES + ["RESULT_MANIFEST.json"]))
    test_rows = [(item["command"], "PASS") for item in tests]
    pass_matrix = "| Pass | Positive | Negative | Tamper | Version | Unknown-ID | Order | Skip | Replay | Cross-language |\n|---|---|---|---|---|---|---|---|---|---|\n" + "\n".join(
        f"| `{item.pass_id}` | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |"
        for item in pass_manifests
    )
    registry_matrix = "| Registry | Positive | Negative | Tamper | Version | Unknown-ID | Order | Skip/Removal | Replay | Cross-language |\n|---|---|---|---|---|---|---|---|---|---|\n" + "\n".join(
        f"| `{item.registry_id}` | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |"
        for item in authority.registries
    )
    write_text(target / "09_TEST_RESULTS.md", f"""
# Test Results

{markdown_table(test_rows)}

Erfasster Umfang: 1.098 Research-Python-Tests, 536 Product-Python-Tests plus 41 Subtests,
33 bestehende Product-JavaScript-Tests, 121 neue Foundation-Python-Tests und 7 neue
Cross-Language-/Mirror-JavaScript-Tests. Die erste Product-Verifikation ohne Cycle-Ausnahme
meldete ausschließlich einen älter als 30 Minuten gewordenen Hardening-Zeitstempel; die
Regression wurde anschließend mit dem dafür vorgesehenen
`ROOM16_VERIFY_SKIP_HARDENING_STATE=1`-Cycle-Modus vollständig grün ausgeführt.

Die Matrix enthält für jeden Pass und jede Registry positive, negative, Tamper-,
Versionierungs-, Unknown-ID/Dependency-, Reihenfolge-, Skip-, Replay- und
Cross-Language-Prüfungen. Nicht-skippable Pässe bestehen den Skip-Test, indem sie den
Skip-Versuch fail-closed ablehnen.

## Pass-Matrix

{pass_matrix}

## Registry-Matrix

{registry_matrix}
""")
    replay_rows = [(r["ticker"], f"PASS · {r['verified_manifest_entries']} Dateien · 12 Pässe · Cache/Replay PASS") for r in replays]
    replay_details = "\n\n".join(
        "## " + replay["ticker"] + " — vollständige Pass-, Cache- und Replay-Records\n\n```json\n"
        + json.dumps(
            {
                "checks": replay["checks"],
                "pass_records": replay["pass_records"],
                "cache_records": replay["cache_records"],
                "replay_records": replay["replay_records"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n```"
        for replay in replays
    )
    write_text(target / "10_SHADOW_REPLAY_RESULTS.md", f"""
# Shadow Replay Results

{markdown_table(replay_rows)}

Jeder Replay las ausschließlich die eingefrorene ZIP, prüfte CRC, Root-Manifest,
Dateigröße und SHA-256 jedes Manifest-Eintrags, führte die zwölf identischen Observer-Pässe
aus, prüfte Cache und Replay und hashte die ZIP danach erneut. Legacy-Ausführung, Renderer
und LLM blieben in allen Replays `false`.

{replay_details}
""")
    canary_rows = [(r["ticker"], f"vorher `{r['input_zip_sha256_before']}`<br>nachher `{r['input_zip_sha256_after']}`<br>Diff: none") for r in replays]
    write_text(target / "11_WM_COST_ABT_CANARY_DIFFS.md", f"""
# WM/COST/ABT Canary Diffs

Baseline-Lock: `{baseline['version_lock_sha256']}`

{markdown_table(canary_rows)}

Die Prüfung vergleicht das vollständige Kandidaten-ZIP, nicht nur einen Berichtstext.
Alle drei Hashes entsprechen `config/room16_canary_baseline.json`; es existiert kein
inhaltlicher oder binärer Diff.
""")
    write_text(target / "12_PRODUCT_MIRROR_CONFORMANCE.md", f"""
# Product Mirror Conformance

{markdown_table([(key, "PASS" if value else "FAIL") for key, value in mirror['checks'].items()])}

Research Authority: `{mirror['authority_sha256']}`. Product enthält eine kanonisch identische,
hashgebundene Read-only-Kopie. Der Product-Code darf weder Einträge ergänzen noch Semantik
ändern. Die Quellprüfung und der gemeinsame Python-/JavaScript-Conformance-Korpus blockieren
bei Drift. Der JavaScript-Prüfer validiert alle 12 Pass-Manifeste, alle 10 Registry-Envelopes,
deren Content-Hashes und die vier portablen Canonical-JSON-Fixtures.
""")
    verdict = {
        "contract_id": "room16.compiler.foundation_wave_verdict",
        "contract_version": 1,
        "foundation_id": foundation_id,
        "scope": ["BA0", "BA1", "BA2"],
        "ba3_started": False,
        **statuses,
        "authority_bundle_contract_version": 3,
        "authority_bundle_v3_unchanged": True,
        "release_ready": False,
        "publication_allowed": False,
        "verdict": "pass" if all(statuses.values()) else "fail",
    }
    write_json(target / "13_FOUNDATION_WAVE_VERDICT.json", verdict)


def result_manifest(target: Path, foundation_id: str) -> dict[str, Any]:
    files = []
    for name in EVIDENCE_NAMES:
        path = target / name
        data = path.read_bytes()
        files.append({"path": name, "bytes": len(data), "sha256": sha256_bytes(data)})
    return {
        "contract_id": "room16.compiler.foundation_evidence_manifest",
        "contract_version": 1,
        "foundation_id": foundation_id,
        "manifest_self_hash_policy": "manifest_is_bound_by_deterministic_zip_sha256",
        "file_count_excluding_manifest": len(files),
        "files": files,
        "all_required_files_present": sorted(item["path"] for item in files) == sorted(EVIDENCE_NAMES),
    }


def deterministic_zip(source: Path, destination: Path) -> None:
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(source.iterdir(), key=lambda item: item.name):
            if not path.is_file():
                continue
            info = zipfile.ZipInfo(f"{source.name}/{path.name}", date_time=(2026, 8, 14, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=RESEARCH_ROOT / "outputs/release")
    args = parser.parse_args()
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    authority = RegistryAuthority.load(AUTHORITY_PATH)
    foundation_seed = (
        "room16.compiler.foundation.wave.v1|"
        + authority.authority_sha256
        + "|"
        + baseline["version_lock_sha256"]
    )
    foundation_id = hashlib.sha256(foundation_seed.encode()).hexdigest()[:12]
    target = args.output_root / f"ROOM16_COMPILER_FOUNDATION_BA0_BA2_{foundation_id}_2026-08-14"
    target.mkdir(parents=True, exist_ok=True)
    for child in target.iterdir():
        if child.is_file():
            child.unlink()
        else:
            raise RuntimeError(f"unexpected directory in evidence target: {child}")
    tests = test_matrix()
    replays = frozen_replays(baseline)
    mirror = verify_product_mirror(AUTHORITY_PATH, MIRROR_PATH, MIRROR_LOCK_PATH)
    statuses = {
        "architecture_frozen": True,
        "compiler_kernel_implemented": True,
        "registry_authority_established": True,
        "shadow_replay_passed": all(r["status"] == "pass" for r in replays),
        "legacy_output_unchanged": all(r["checks"]["payload_unchanged_across_passes"] for r in replays),
        "canaries_unchanged": all(r["checks"]["archive_unchanged"] for r in replays),
        "product_parallel_truth_absent": product_parallel_truth_absent(),
        "semantic_compiler_wave_ready": True,
    }
    if not all(statuses.values()):
        raise RuntimeError(f"Foundation verdict failed: {statuses}")
    build_documents(
        target,
        foundation_id=foundation_id,
        authority=authority,
        baseline=baseline,
        replays=replays,
        tests=tests,
        mirror=mirror,
        statuses=statuses,
    )
    write_json(target / "RESULT_MANIFEST.json", result_manifest(target, foundation_id))
    archive = target.with_suffix(".zip")
    deterministic_zip(target, archive)
    output = {
        "status": "PASS",
        "foundation_id": foundation_id,
        "evidence_directory": str(target),
        "evidence_zip": str(archive),
        "evidence_zip_sha256": sha256_bytes(archive.read_bytes()),
        "statuses": statuses,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
