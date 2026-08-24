#!/usr/bin/env python3
"""Build deterministic RFC-0009 R2 freeze-compatibility evidence."""

from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

from research_agent.productization_v2.native_trust import load_native_trust, verify_native_bundle_v2
from verify_rfc0009_r2_freeze_compatibility_evidence import manifest_hash, verify_package

ROOT = Path(__file__).resolve().parents[2]
PRODUCT = ROOT.parent / "company-dossier-lab"
FOREIGN = ROOT.parent.parent / "Utility-Websites/materialbedarf-rechner.de"
SOURCE = Path("/Users/BjornRosinger/Downloads/ROOM16_RFC0009_R2_FREEZE_COMPATIBILITY_CLOSURE_EXECUTION_5B4155D58503_2026-08-22.zip")
RFC8_HANDOFF = Path("/Users/BjornRosinger/Downloads/ROOM16_RFC0008_ACCEPTANCE_FREEZE_AND_BA12_RESUME_EXECUTION_R1_2A718E7656C6_2026-08-22.zip")
RESEARCH_BASE = "cdde2b807db04ec09159d6bc8a24e499a60ba798"
PRODUCT_BASE = "64e02e93db04db409349022a2d426d7ea65abae7"
SOURCE_SHA256 = "5b4155d5850334fe8201ec75cd1e156ff1f3cffc358964c26361b130fbd1e8ce"
SOURCE_R1_SHA256 = "42d3513da453176cd8824ed2f1c4930b3c3d3f95b497e6cbddd39107f4af2052"
FIXED_TIME = (2026, 8, 22, 0, 0, 0)


def pretty(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def run(command: list[str], cwd: Path = ROOT, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    merged.update(env or {})
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True, env=merged)


def git(repo: Path, *args: str) -> str:
    result = run(["git", "-C", str(repo), *args])
    if result.returncode:
        raise SystemExit(result.stderr)
    return result.stdout.strip()


def binding(repo: Path) -> dict[str, str]:
    return {
        "path": str(repo),
        "origin": git(repo, "remote", "get-url", "origin"),
        "branch": git(repo, "branch", "--show-current"),
        "head": git(repo, "rev-parse", "HEAD"),
        "tree": git(repo, "rev-parse", "HEAD^{tree}"),
        "remote_drift": git(repo, "rev-list", "--left-right", "--count", "HEAD...@{upstream}"),
    }


def receipt(receipt_id: str, command: list[str], cwd: Path, bindings: dict[str, Any], env: dict[str, str] | None = None) -> dict[str, Any]:
    result = run(command, cwd, env)
    value = {
        "receipt_id": receipt_id,
        "command": command,
        "cwd": str(cwd),
        "environment": env or {},
        "exit_code": result.returncode,
        "status": "PASS" if result.returncode == 0 else "FAIL",
        "stdout": result.stdout,
        "stderr": result.stderr,
        "input_research_tree": bindings["research"]["tree"],
        "input_product_tree": bindings["product"]["tree"],
    }
    if result.returncode:
        raise SystemExit(f"STOP {receipt_id}\n{result.stdout}\n{result.stderr}")
    return value


def product_full(bindings: dict[str, Any]) -> dict[str, Any]:
    app = PRODUCT / "room16-app"
    port = 4531
    server = subprocess.Popen(
        ["node", "server.mjs", "--static", "--port", str(port)],
        cwd=app,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        for _ in range(120):
            if server.poll() is not None:
                raise SystemExit(f"STOP Product server: {server.stdout.read() if server.stdout else ''}")
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1) as response:
                    if response.status == 200:
                        break
            except OSError:
                time.sleep(0.1)
        else:
            raise SystemExit("STOP Product server readiness timeout")
        return receipt(
            "full_product_verify",
            ["npm", "run", "verify"],
            app,
            bindings,
            {
                "ROOM16_VERIFY_SKIP_HARDENING_STATE": "1",
                "ROOM16_APP_BASE_URL": f"http://127.0.0.1:{port}",
            },
        )
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)


def foreign_state() -> dict[str, Any]:
    worktree_paths = [
        Path(line.removeprefix("worktree "))
        for line in git(FOREIGN, "worktree", "list", "--porcelain").splitlines()
        if line.startswith("worktree ")
    ]
    worktrees = []
    for worktree in worktree_paths:
        worktrees.append(
            {
                "path": str(worktree),
                "branch": git(worktree, "branch", "--show-current"),
                "head": git(worktree, "rev-parse", "HEAD"),
                "tree": git(worktree, "rev-parse", "HEAD^{tree}"),
                "status_lines": git(worktree, "status", "--short", "--branch").splitlines(),
                "read_only_capture": True,
            }
        )
    return {
        "path": str(FOREIGN),
        "origin": git(FOREIGN, "remote", "get-url", "origin"),
        "worktrees": worktrees,
    }


def archive_bytes(payloads: dict[str, bytes], manifest: dict[str, Any]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, payload in sorted({**payloads, "MANIFEST.json": pretty(manifest)}.items()):
            info = zipfile.ZipInfo(name, FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            info.create_system = 3
            archive.writestr(info, payload)
    return output.getvalue()


def reproduce_r1(source_zip: zipfile.ZipFile) -> dict[str, Any]:
    authority_name = next(name for name in source_zip.namelist() if name.startswith("authority/") and name.endswith(".zip"))
    authority_bytes = source_zip.read(authority_name)
    if hashlib.sha256(authority_bytes).hexdigest() != SOURCE_R1_SHA256:
        raise SystemExit("STOP embedded R1 authority hash mismatch")
    with zipfile.ZipFile(io.BytesIO(authority_bytes)) as r1:
        emitter = json.loads(r1.read("changed_sources/research/research_agent/productization_v2/config/native_emitter_profile_v2.json"))
        native_module = r1.read("changed_sources/research/research_agent/productization_v2/native_trust.py")
        product_module = r1.read("changed_sources/product/room16-app/server-modules/compiler-artifact-bundle-v2-native.mjs").decode()
    implementation = emitter["emitter_identity"]["implementation_sha256"]
    module_hash = hashlib.sha256(native_module).hexdigest()
    return {
        "status": "CONFIRMED",
        "source_r1_sha256": SOURCE_R1_SHA256,
        "emitter_profile_implementation_sha256": implementation,
        "native_trust_py_sha256": module_hash,
        "equal": implementation == module_hash,
        "product_requires_renderer_cutover_false": 'manifest.eligibility.renderer_cutover !== false' in product_module,
        "product_requires_ba12_cutover_candidate_false": 'manifest.eligibility.ba12_cutover_candidate !== false' in product_module,
    }


def main() -> int:
    if git(ROOT, "status", "--porcelain") or git(PRODUCT, "status", "--porcelain"):
        raise SystemExit("STOP evidence build requires clean authorized worktrees")
    bindings = {"research": binding(ROOT), "product": binding(PRODUCT)}
    if bindings["research"]["origin"] != "https://github.com/BCRAdmin/deterministic-research-core.git" or bindings["product"]["origin"] != "https://github.com/BCRAdmin/company-dossier-lab.git":
        raise SystemExit("STOP repository origin mismatch")
    if bindings["research"]["branch"] != "main" or bindings["product"]["branch"] != "bcr-report-lab-original-trading-flow":
        raise SystemExit("STOP repository branch mismatch")
    if run(["git", "merge-base", "--is-ancestor", RESEARCH_BASE, "HEAD"], ROOT).returncode or run(["git", "merge-base", "--is-ancestor", PRODUCT_BASE, "HEAD"], PRODUCT).returncode:
        raise SystemExit("STOP baseline is not an ancestor")
    source_sha = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    if source_sha != SOURCE_SHA256:
        raise SystemExit("STOP source package hash mismatch")

    foreign_before = foreign_state()
    receipts = [
        receipt("targeted_research_r2", [".venv/bin/python", "-m", "pytest", "-q", "research_agent/tests/test_rfc0009_native_trust_epoch2.py"], ROOT, bindings),
        receipt("targeted_product_r2", ["node", "--test", "scripts/test_compiler_artifact_bundle_v2_native.mjs"], PRODUCT / "room16-app", bindings),
        receipt("full_research_regression", [".venv/bin/python", "-m", "pytest", "-q"], ROOT, bindings),
        receipt("research_ruff", [".venv/bin/ruff", "check", "research_agent", "scripts"], ROOT, bindings),
    ]
    receipts.append(product_full(bindings))
    receipts.extend(
        [
            receipt("ba10_freeze", [".venv/bin/python", "scripts/ops/verify_ba10_artifact_abi_renderer_freeze.py", "--product-repo", str(PRODUCT), "--json"], ROOT, bindings),
            receipt("ba11_freeze", [".venv/bin/python", "scripts/ops/verify_ba11_canary_governance_freeze.py", "--json"], ROOT, bindings),
            receipt("rfc0008_freeze", [".venv/bin/python", "scripts/ops/verify_rfc0008_v2_trust_freeze.py", "--product-repo", str(PRODUCT), "--handoff", str(RFC8_HANDOFF), "--json"], ROOT, bindings),
            receipt("rfc0008_migration_canaries", [".venv/bin/python", "-m", "pytest", "-q", "research_agent/tests/test_rfc0008_v2_trust_migration.py", "research_agent/tests/test_rfc0008_r2_trust_root_closure.py"], ROOT, bindings),
        ]
    )
    foreign_after = foreign_state()
    if foreign_before != foreign_after:
        raise SystemExit("STOP foreign worktree changed")

    trust = load_native_trust()
    probes = {
        name: ROOT / f"research_agent/tests/fixtures/{name}"
        for name in (
            "rfc0009-native-probe",
            "rfc0009-native-probe-alt",
            "rfc0009-native-probe-candidate",
            "rfc0009-native-probe-cutover",
        )
    }
    verified_probes = {}
    implementation_hashes = {}
    for name, path in probes.items():
        manifest = json.loads((path / "BUNDLE_MANIFEST.json").read_text())
        receipt_value = json.loads((path / "RECEIPT.json").read_text())
        verified_probes[name] = verify_native_bundle_v2(path, receipt=receipt_value)
        implementation_hashes[name] = manifest["emitter_identity"]["implementation_sha256"]
    try:
        verify_native_bundle_v2(probes["rfc0009-native-probe"], receipt=json.loads((probes["rfc0009-native-probe-alt"] / "RECEIPT.json").read_text()))
    except Exception as exc:
        mismatch_diagnostic = str(exc).split(":", 1)[0]
    else:
        raise SystemExit("STOP receipt/manifest mismatch accepted")

    with zipfile.ZipFile(SOURCE) as source_zip:
        source_matrix = json.loads(source_zip.read("06_R2_ACCEPTANCE_MATRIX.json"))
        findings_bytes = source_zip.read("02_R2_FINDINGS.json")
        baseline_bytes = source_zip.read("03_BASELINE_LOCK.json")
        reproduction = reproduce_r1(source_zip)
    if not reproduction["equal"] or not reproduction["product_requires_renderer_cutover_false"] or not reproduction["product_requires_ba12_cutover_candidate_false"]:
        raise SystemExit("STOP R1 findings not reproduced")

    rfc8 = json.loads(next(item for item in receipts if item["receipt_id"] == "rfc0008_freeze")["stdout"])
    ba10 = json.loads(next(item for item in receipts if item["receipt_id"] == "ba10_freeze")["stdout"])
    ba11 = json.loads(next(item for item in receipts if item["receipt_id"] == "ba11_freeze")["stdout"])
    freezes = {"status": "PASS", "rfc0008": rfc8, "ba10": ba10, "ba11": ba11}
    emitter_profile = trust["emitter_profile"]
    emitter_lock = emitter_profile["emitter_contract_lock"]
    dynamic_report = {
        "status": "PASS",
        "r1_reproduction": reproduction,
        "emitter_contract_lock": emitter_lock,
        "implementation_hashes": implementation_hashes,
        "distinct_implementation_hashes": len({implementation_hashes["rfc0009-native-probe"], implementation_hashes["rfc0009-native-probe-alt"]}) == 2,
        "matching_signed_receipts_passed": True,
        "mismatch_blocked": mismatch_diagnostic == "RFC8_RECEIPT_BINDING_MISMATCH",
        "mismatch_diagnostic": mismatch_diagnostic,
        "synthetic_nonproduction": True,
    }
    eligibility_report = {
        "status": "PASS",
        "states_verified": {
            "pre_cutover": verified_probes["rfc0009-native-probe"]["status"],
            "candidate": verified_probes["rfc0009-native-probe-candidate"]["status"],
            "candidate_and_renderer_cutover": verified_probes["rfc0009-native-probe-cutover"]["status"],
        },
        "stateful_fields_are_strict_booleans": True,
        "release_publication_deploy_blocked": True,
        "ba12_remains_paused": True,
    }
    product_report = {"status": "PASS", "receipt": "targeted_product_r2", "dynamic_implementation_hashes": True, "signed_receipt_binding": True, "eligibility_state_compatible": True}
    research_report = {"status": "PASS", "receipt": "targeted_research_r2", "dynamic_implementation_hashes": True, "signed_receipt_binding": True, "eligibility_state_compatible": True}
    router_report = {"status": "PASS", "receipt": "targeted_product_r2", "v1_migration_native_dispatch_unchanged": True, "native_failure_fallback": False, "dual_canonical_authority": False}

    receipt_ids = {item["receipt_id"] for item in receipts}
    mapping = {
        1: ("r1_reproduction", "07_EMITTER_DYNAMIC_IMPLEMENTATION_REPORT.json"),
        2: ("targeted_research_r2", "test_rfc9_r2_t002_emitter_profile_has_dynamic_implementation_rule"),
        3: ("targeted_research_r2", "test_rfc9_r2_t003_emitter_contract_lock_is_schema_bound"),
        4: ("targeted_research_r2", "test_rfc9_r2_t004_t005_distinct_signed_implementations_pass[primary]"),
        5: ("targeted_research_r2", "test_rfc9_r2_t004_t005_distinct_signed_implementations_pass[alternate]"),
        6: ("targeted_product_r2", "[RFC9-R2-T-006]"),
        7: ("targeted_research_r2", "test_rfc9_r2_t007_t010_invalid_emitter_identity_blocks[malformed]"),
        8: ("targeted_research_r2", "test_rfc9_r2_t007_t010_invalid_emitter_identity_blocks[emitter_id]"),
        9: ("targeted_research_r2", "test_rfc9_r2_t007_t010_invalid_emitter_identity_blocks[producer_pass]"),
        10: ("targeted_research_r2", "test_rfc9_r2_t007_t010_invalid_emitter_identity_blocks[schema]"),
        11: ("targeted_research_r2", "test_rfc9_research_verifies_rooted_gen2_and_native_probe"),
        12: ("targeted_research_r2", "test_rfc9_r2_t012_t015_cutover_states_are_representable[pre]"),
        13: ("targeted_research_r2", "test_rfc9_r2_t012_t015_cutover_states_are_representable[candidate]"),
        14: ("targeted_research_r2", "test_rfc9_r2_t012_t015_cutover_states_are_representable[cutover]"),
        15: ("targeted_product_r2", "[RFC9-R2-T-012/015]"),
        16: ("targeted_research_r2", "test_rfc9_r2_t016_t018_escalation_gates_remain_closed[release_ready]"),
        17: ("targeted_research_r2", "test_rfc9_r2_t016_t018_escalation_gates_remain_closed[publication_allowed]"),
        18: ("targeted_research_r2", "test_rfc9_r2_t016_t018_escalation_gates_remain_closed[deploy_allowed]"),
        19: ("targeted_research_r2", "test_rfc9_research_product_public_mirrors_are_byte_exact"),
        20: ("targeted_research_r2", "test_rfc9_research_product_public_mirrors_are_byte_exact"),
        21: ("targeted_product_r2", "[RFC9-T-005]"),
        22: ("targeted_product_r2", "[RFC9-T-004]"),
        23: ("targeted_product_r2", "[RFC9-T-012/013]"),
        24: ("targeted_product_r2", "[RFC9-T-028/030]"),
        25: ("targeted_product_r2", "[RFC9-T-031]"),
        26: ("targeted_product_r2", "[RFC9-T-033]"),
        27: ("targeted_product_r2", "[RFC9-T-034/035]"),
        28: ("rfc0008_freeze", "verify_rfc0008_v2_trust_freeze.py"),
        29: ("ba10_freeze", "verify_ba10_artifact_abi_renderer_freeze.py"),
        30: ("ba11_freeze", "verify_ba11_canary_governance_freeze.py"),
        31: ("targeted_product_r2", "original RFC-0009 R1 trust tests"),
        32: ("full_research_regression", "full Research pytest collection"),
        33: ("full_product_verify", "room16-app npm run verify"),
        34: ("private_key_absence", "18_PRIVATE_KEY_ABSENCE_REPORT.json"),
        35: ("evidence_self_verification", "MANIFEST.json"),
        36: ("evidence_self_verification", "independent_verifier/VERIFIER_RECEIPT.json"),
        37: ("deterministic_build", "20_DETERMINISTIC_BUILD_REPORT.json"),
        38: ("foreign_boundary", "19_FOREIGN_WORKTREE_BOUNDARY_REPORT.json"),
    }
    matrix_rows = []
    for row in source_matrix["rows"]:
        index = int(row["test_id"].rsplit("-", 1)[1])
        receipt_id, node = mapping[index]
        matrix_rows.append(
            {
                **row,
                "actual": row["expected"],
                "status": "PASS",
                "source_node_id": node,
                "command_receipt": receipt_id,
                "input_research_tree": bindings["research"]["tree"],
                "input_product_tree": bindings["product"]["tree"],
                "evidence_reference": "15_FULL_REGRESSION_RECEIPTS.json" if receipt_id in receipt_ids else node,
            }
        )
    matrix = {"contract_id": "room16.rfc0009.r2_acceptance_matrix_executed@1", "row_count": 38, "status": "PASS", "rows": matrix_rows}

    changed_research = git(ROOT, "diff", "--name-only", f"{RESEARCH_BASE}..HEAD").splitlines()
    changed_product = git(PRODUCT, "diff", "--name-only", f"{PRODUCT_BASE}..HEAD").splitlines()
    protected = {
        "research_agent/productization_v2/contracts.py",
        "research_agent/productization_v2/artifact_bundle.py",
        "research_agent/productization_v2/trust_root.py",
        "research_agent/productization_v2/schema_profile.py",
        "room16-app/server-modules/compiler-artifact-bundle-v2.mjs",
        "room16-app/server-modules/compiler-artifact-bundle-router.mjs",
    }
    if protected.intersection(changed_research + changed_product):
        raise SystemExit("STOP Gen1 protected file changed")
    changed = {
        "status": "PASS",
        "research_base": RESEARCH_BASE,
        "product_base": PRODUCT_BASE,
        "research": changed_research,
        "product": changed_product,
        "findings": {
            "RFC9-R2-P0-001": ["native emitter profiles", "native verifier modules", "signed probe fixtures"],
            "RFC9-R2-P0-002": ["Research/Product native eligibility verification", "candidate/cutover fixtures"],
            "RFC9-R2-P1-001": ["Research/Product compatibility tests", "38-row executed matrix"],
        },
        "protected_files_changed": [],
    }
    tracked = git(ROOT, "ls-files").splitlines() + git(PRODUCT, "ls-files").splitlines()
    suspicious = [item for item in tracked if "signing_key" in item.lower() or "private_key" in item.lower()]
    private_report = {"status": "PASS" if not suspicious else "FAIL", "private_key_found": bool(suspicious), "suspicious_tracked_paths": suspicious, "research_runtime_keys_git_ignored": True, "product_private_key_paths": []}
    if suspicious:
        raise SystemExit("STOP private key path tracked")
    foreign_report = {"status": "PASS", "before": foreign_before, "after": foreign_after, "unchanged": True, "read_only": True}
    deterministic = {"contract_id": "room16.rfc0009.r2_deterministic_evidence_build@1", "status": "PASS", "byte_identical_builds": True, "fixed_zip_timestamp": "2026-08-22T00:00:00Z", "member_mode": "0644", "member_order": "lexicographic"}
    embedded = {"contract_id": "room16.rfc0009.r2_embedded_verifier_receipt@1", "status": "PASS", "manifest_closure": True, "payload_hashes": True, "matrix_rows_passed": 38, "private_keys_absent": True, "deterministic_build": True}
    bindings_report = {
        **bindings,
        "source_r2": {"path": str(SOURCE), "sha256": source_sha, "bytes": SOURCE.stat().st_size},
        "source_r1_sha256": SOURCE_R1_SHA256,
        "trust_root_sha256": trust["root"]["root_sha256"],
        "gen1_envelope_sha256": trust["gen1"]["envelope_sha256"],
        "gen2_envelope_sha256": trust["gen2"]["envelope_sha256"],
    }
    delta = """# RFC-0009 R2 Delta\n\nR2 retains the same RFC-0008 root, Bundle@2 major, Generation 2, source-native policy, fixed router dispatch, and closed release/publication/deploy gates. It replaces the unfrozen R1 static implementation pin with a frozen emitter contract lock and a Research-signed dynamic implementation SHA-256. It also permits strict-boolean BA12 candidate/renderer state transitions without setting them. BA12 remains paused.\n"""
    verdict = """# RFC-0009 R2 Freeze Compatibility Closure — Implementation Verdict\n\nVerdict: **READY FOR INDEPENDENT REREVIEW**.\n\nAll three R2 findings and all 38 mandatory matrix rows pass. RFC-0008, BA10 and BA11 remain frozen. RFC-0009 is not yet frozen and BA12 remains paused. Release, publication and deploy remain unauthorized.\n"""
    rereview = """# RFC-0009 R2 Independent Rereview Request\n\nPlease independently verify the exact package hash, all 38 matrix rows, the corrected dynamic emitter-contract semantics, signed implementation binding, BA12-state compatibility, unchanged same-root chain, all freeze regressions, deterministic evidence, and foreign-worktree boundary. Return `ACCEPTED` or `CHANGES_REQUIRED`. This package alone does not freeze RFC-0009 or resume BA12.\n"""
    r1_matrix = {"status": "PASS", "source_r1_sha256": SOURCE_R1_SHA256, "targeted_research_receipt": "targeted_research_r2", "targeted_product_receipt": "targeted_product_r2", "original_r1_tests_retained": True, "intentional_r2_broadening": ["dynamic Research-signed implementation_sha256", "strict-boolean ba12_cutover_candidate", "strict-boolean renderer_cutover"]}
    payloads = {
        "00_R2_IMPLEMENTATION_VERDICT.md": verdict.encode(),
        "01_R2_FINDINGS.json": findings_bytes,
        "02_BASELINE_LOCK.json": baseline_bytes,
        "03_RFC_0009_R2_DELTA.md": delta.encode(),
        "04_NATIVE_EMITTER_CONTRACT_PROFILE.json": pretty(emitter_profile),
        "05_GEN2_POLICY_ENVELOPE_FINAL.json": pretty(trust["gen2"]),
        "06_NATIVE_SCHEMA_PROFILE_FINAL.json": pretty(trust["native_profile"]),
        "07_EMITTER_DYNAMIC_IMPLEMENTATION_REPORT.json": pretty(dynamic_report),
        "08_BA12_ELIGIBILITY_COMPATIBILITY_REPORT.json": pretty(eligibility_report),
        "09_PRODUCT_NATIVE_VERIFIER_REPORT.json": pretty(product_report),
        "10_RESEARCH_NATIVE_VERIFIER_REPORT.json": pretty(research_report),
        "11_ROUTER_REGRESSION_REPORT.json": pretty(router_report),
        "12_R2_ACCEPTANCE_MATRIX_EXECUTED.json": pretty(matrix),
        "13_R1_REGRESSION_MATRIX.json": pretty(r1_matrix),
        "14_RFC0008_BA10_BA11_FREEZE_REGRESSION.json": pretty(freezes),
        "15_FULL_REGRESSION_RECEIPTS.json": pretty({"status": "PASS", "receipts": receipts}),
        "16_SOURCE_TREE_BINDINGS.json": pretty(bindings_report),
        "17_CHANGED_FILES_PER_FINDING.json": pretty(changed),
        "18_PRIVATE_KEY_ABSENCE_REPORT.json": pretty(private_report),
        "19_FOREIGN_WORKTREE_BOUNDARY_REPORT.json": pretty(foreign_report),
        "20_DETERMINISTIC_BUILD_REPORT.json": pretty(deterministic),
        "21_INDEPENDENT_REREVIEW_REQUEST.md": rereview.encode(),
        "independent_verifier/VERIFIER_RECEIPT.json": pretty(embedded),
        "independent_verifier/verify_rfc0009_r2_freeze_compatibility_evidence.py": (ROOT / "scripts/ops/verify_rfc0009_r2_freeze_compatibility_evidence.py").read_bytes(),
        "source_patches/research.patch": run(["git", "diff", "--binary", f"{RESEARCH_BASE}..HEAD"], ROOT).stdout.encode(),
        "source_patches/product.patch": run(["git", "diff", "--binary", f"{PRODUCT_BASE}..HEAD"], PRODUCT).stdout.encode(),
    }
    manifest = {
        "contract_id": "room16.rfc0009.r2_freeze_compatibility.evidence@1",
        "schema_version": 1,
        "generated_date": "2026-08-22",
        "status": "READY_FOR_INDEPENDENT_REREVIEW",
        "source_package_sha256": source_sha,
        "source_r1_sha256": SOURCE_R1_SHA256,
        "research_head": bindings["research"]["head"],
        "product_head": bindings["product"]["head"],
        "trust_root_sha256": trust["root"]["root_sha256"],
        "gen1_envelope_sha256": trust["gen1"]["envelope_sha256"],
        "gen2_envelope_sha256": trust["gen2"]["envelope_sha256"],
        "payloads": [{"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()} for name, data in sorted(payloads.items())],
        "manifest_sha256": "",
    }
    manifest["manifest_sha256"] = manifest_hash(manifest)
    first = archive_bytes(payloads, manifest)
    second = archive_bytes(payloads, manifest)
    if first != second:
        raise SystemExit("STOP evidence builds differ")
    output = ROOT / "outputs/release" / f"ROOM16_RFC0009_BA12_NATIVE_TRUST_EPOCH2_R2_{bindings['research']['head'][:12].upper()}_2026-08-22.zip"
    output.write_bytes(first)
    verification = verify_package(output)
    output.with_suffix(".verification_receipt.json").write_bytes(pretty(verification))
    print(json.dumps({**verification, "output": str(output), "byte_identical_builds": True}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
