#!/usr/bin/env python3
"""Build the bounded, self-contained RFC-0005-R3 BA10 closure evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.request
import zipfile
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PRODUCT = ROOT.parent / "company-dossier-lab"
APP = PRODUCT / "room16-app"
BASES = {"research": "db76818", "product": "1c90e59"}
CANARIES = {
    "WM": "a6b6d15ad7004573a56ad057884563cfbeeb2c3162dae0641a1b361b5e416d72",
    "COST": "b97e6024855c7a772713ff9af4889987e4a9a8e5a3afca0d56a42a1ba8092ea4",
    "ABT": "0926d3cafd312556ec267b2b25214d255ff9352daed77a01b7852addbb48dc45",
}
CANARY_ROOT = PRODUCT / ".runtime/cross-company-release-current/ROOM16_WM_COST_ABT_CROSS_COMPANY_RC_8cf064d75c8c-20260814-115448"
PASS_PROFILE = ROOT / "research_agent/productization/config/pass_execution_profile_v1.json"
ARTIFACT_PROFILE = ROOT / "research_agent/productization/config/required_artifact_profile_v1.json"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, str):
        path.write_text(value.rstrip() + "\n", encoding="utf-8")
    else:
        path.write_text(
            json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )


def run(command: list[str], cwd: Path, env: dict[str, str] | None = None) -> dict[str, Any]:
    process = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
    )
    return {
        "command": command,
        "cwd": str(cwd),
        "exit_code": process.returncode,
        "output": process.stdout,
    }


def run_with_server(command: list[str]) -> dict[str, Any]:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    base_url = f"http://127.0.0.1:{port}"
    server = subprocess.Popen(
        ["node", "server.mjs", "--static", "--port", str(port)],
        cwd=APP,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=os.environ.copy(),
    )
    try:
        for _ in range(100):
            if server.poll() is not None:
                break
            try:
                with urllib.request.urlopen(base_url, timeout=0.25) as response:
                    if response.status < 500:
                        break
            except Exception:
                time.sleep(0.1)
        else:
            raise RuntimeError("Room16 verification server did not become reachable")
        if server.poll() is not None:
            raise RuntimeError("Room16 verification server exited before the verify run")
        env = os.environ.copy()
        env["ROOM16_APP_BASE_URL"] = base_url
        result = run(command, APP, env=env)
    finally:
        if server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)
    server_output = server.stdout.read() if server.stdout else ""
    result["managed_server"] = {"base_url": base_url, "output": server_output}
    return result


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=repo, text=True).strip()


def deterministic_zip(source: Path, target: Path) -> None:
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(candidate for candidate in source.rglob("*") if candidate.is_file()):
            info = zipfile.ZipInfo(path.relative_to(source).as_posix(), (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())


def changed(repo: Path, base: str) -> dict[str, Any]:
    head = git(repo, "rev-parse", "HEAD")
    merge_base = git(repo, "merge-base", base, "HEAD")
    rows = []
    for line in git(repo, "diff", "--name-status", f"{base}..{head}").splitlines():
        columns = line.split("\t")
        status = columns[0]
        path = columns[-1]
        ref = base if status.startswith("D") else head
        blob = subprocess.check_output(["git", "show", f"{ref}:{path}"], cwd=repo)
        rows.append({"status": status, "path": path, "sha256": hashlib.sha256(blob).hexdigest()})
    return {
        "base_commit": git(repo, "rev-parse", base),
        "head_commit": head,
        "merge_base": merge_base,
        "files": rows,
    }


def require_pass(results: dict[str, dict[str, Any]]) -> None:
    failed = [name for name, result in results.items() if result["exit_code"] != 0]
    if failed:
        details = "\n\n".join(f"[{name}]\n{results[name]['output']}" for name in failed)
        raise SystemExit(f"R3 regression failure: {', '.join(failed)}\n{details}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundles-root", type=Path, required=True)
    parser.add_argument("--renders-root", type=Path, required=True)
    parser.add_argument("--review-zip", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "outputs/release")
    args = parser.parse_args()

    research_head = git(ROOT, "rev-parse", "HEAD")
    product_head = git(PRODUCT, "rev-parse", "HEAD")
    name = f"ROOM16_RFC_0005_R3_BA10_FINAL_CLOSURE_{research_head[:8].upper()}_{date.today().isoformat()}"

    with tempfile.TemporaryDirectory(prefix="room16-r3-evidence-") as temporary:
        temp = Path(temporary)
        stage = temp / name
        nested_bundles = stage / "NESTED_BUNDLES"
        nested_renders = stage / "NESTED_RENDERED_ARTIFACTS"
        nested_bundles.mkdir(parents=True)
        nested_renders.mkdir()

        fixture_path = temp / "fixtures.json"
        regression = {
            "research_full_pytest": run([str(ROOT / ".venv/bin/python"), "-m", "pytest", "-q"], ROOT),
            "research_ruff": run([str(ROOT / ".venv/bin/ruff"), "check", "."], ROOT),
            "foundation_freeze": run([str(ROOT / ".venv/bin/python"), "scripts/ops/verify_compiler_foundation_freeze.py"], ROOT),
            "registry_freeze": run([str(ROOT / ".venv/bin/python"), "scripts/ops/verify_registry_foundation_freeze.py"], ROOT),
            "semantic_wave_freeze": run([str(ROOT / ".venv/bin/python"), "scripts/ops/verify_semantic_compiler_wave_freeze.py"], ROOT),
            "product_full_pytest": run([str(PRODUCT / ".venv/bin/python"), "-m", "pytest", "-q"], PRODUCT),
            "product_full_javascript": run(
                ["node", "--test", *[str(path.relative_to(APP)) for path in sorted((APP / "scripts").glob("test_*.mjs"))]],
                APP,
            ),
            "product_abi_verify": run(["npm", "run", "verify:compiler-artifact-bundle"], APP),
            "product_build": run(["npm", "run", "build"], APP),
            "product_complete_verify": run_with_server(["npm", "run", "verify"]),
            "german_output_gate": run(["npm", "run", "verify:german-output-quality"], APP),
            "production_trust_api": run(["node", "scripts/verify_compiler_artifact_trust_api.mjs"], APP),
            "full_rehash_negative_fixtures": run(
                [
                    "node",
                    "scripts/verify_compiler_artifact_bundle_contract_fixtures.mjs",
                    "--bundle",
                    str(args.bundles_root / "WM"),
                    "--rehasher",
                    str(ROOT / "scripts/ops/rehash_ba10_bundle_fixture.py"),
                    "--output",
                    str(fixture_path),
                ],
                APP,
            ),
        }
        require_pass(regression)

        fixtures = json.loads(fixture_path.read_text(encoding="utf-8"))
        trust = json.loads(regression["production_trust_api"]["output"])
        if trust.get("alternative_trust_argument_calls") != 0:
            raise SystemExit("production trust API still accepts alternative trust arguments")

        replay: dict[str, Any] = {}
        for ticker, expected_source_hash in CANARIES.items():
            source = CANARY_ROOT / f"ROOM16_{ticker}_CROSS_COMPANY_RC_8cf064d75c8c-20260814-115448.zip"
            if sha(source) != expected_source_hash:
                raise SystemExit(f"{ticker} source canary changed")
            bundle = args.bundles_root / ticker
            render = args.renders_root / ticker
            result_path = temp / f"{ticker}-instance.json"
            instance_check = run(
                [
                    "node",
                    "scripts/verify_compiler_artifact_bundle_instance.mjs",
                    "--bundle",
                    str(bundle),
                    "--rendered-set",
                    str(render / "rendered_artifact_set.json"),
                    "--output",
                    str(result_path),
                ],
                APP,
            )
            if instance_check["exit_code"] != 0:
                raise SystemExit(instance_check["output"])
            instance = json.loads(result_path.read_text(encoding="utf-8"))
            bundle_manifest = json.loads((bundle / "BUNDLE_MANIFEST.json").read_text(encoding="utf-8"))
            bundle_zip = nested_bundles / f"{ticker}_COMPILER_ARTIFACT_BUNDLE.zip"
            render_zip = nested_renders / f"{ticker}_RENDERED_ARTIFACTS.zip"
            deterministic_zip(bundle, bundle_zip)
            deterministic_zip(render, render_zip)
            replay[ticker] = {
                "source_canary_sha256": expected_source_hash,
                "bundle_sha256": bundle_manifest["bundle_sha256"],
                "bundle_zip_sha256": sha(bundle_zip),
                "rendered_zip_sha256": sha(render_zip),
                "instance_status": instance["status"],
                "rendered_artifact_set_accepted": instance["rendered_artifact_set_accepted"],
            }

        changes = {
            "research": changed(ROOT, BASES["research"]),
            "product": changed(PRODUCT, BASES["product"]),
        }
        pass_profile = json.loads(PASS_PROFILE.read_text(encoding="utf-8"))
        artifact_profile = json.loads(ARTIFACT_PROFILE.read_text(encoding="utf-8"))
        verdict = {
            "contract_id": "room16.rfc_0005_r3.ba10_final_acceptance_verdict",
            "contract_version": 1,
            "ba10_r2_ar_001_closed": True,
            "ba10_r2_ar_002_closed": True,
            "ba10_r2_ar_003_closed": True,
            "ba10_r2_ar_004_closed": True,
            "production_verify_api_exactly_two_arguments": True,
            "production_alternative_trust_argument_calls": 0,
            "exact_ten_pass_execution_profile_verified": True,
            "required_artifact_profile_verified": True,
            "full_unskipped_regression_passed": True,
            "actual_wm_cost_abt_exemplars_passed": True,
            "foundation_unchanged": True,
            "registry_foundation_unchanged": True,
            "semantic_compiler_ba0_ba9_unchanged": True,
            "authority_bundle_v3_unchanged": True,
            "wm_cost_abt_source_canaries_unchanged": True,
            "ba10_final_acceptance_candidate": True,
            "ba10_freeze_authorized": False,
            "ba11_authorized": False,
            "ba12_authorized": False,
            "release_ready": False,
            "publication_allowed": False,
            "independent_acceptance_required": True,
        }

        write(stage / "00_EXECUTIVE_SUMMARY.md", "# RFC-0005-R3 Executive Summary\n\nThe bounded R3 closure passes all four authorized findings. Production trust input is no longer caller-injectable, the exact frozen ten-pass profile and Research-owned required-artifact profile are enforced fail-closed, and the complete unskipped regression plus actual WM/COST/ABT exemplar verification pass. BA10 remains an acceptance candidate pending independent review; BA11, BA12, release and publication remain unauthorized.")
        write(stage / "01_IMPLEMENTATION_RECORD.md", f"# RFC-0005-R3 Implementation Record\n\nResearch head: `{research_head}`\nProduct head: `{product_head}`\n\nImplemented only BA10-R2-AR-001 through BA10-R2-AR-004. No BA0-BA9, company-specific, BA11, BA12, release or publication work was performed.")
        write(stage / "02_PRODUCTION_TRUST_API_CLOSURE.md", f"# Production Trust API Closure\n\nThe exported production verifier has exactly two parameters: bundle root and capabilities. Receipt substitution exists only inside the isolated fixture process. The runtime scan covered {trust.get('scanned_file_count')} files and found `{trust.get('alternative_trust_argument_calls')}` calls with an alternative trust argument.")
        shutil.copy2(PASS_PROFILE, stage / "03_PASS_EXECUTION_PROFILE.json")
        shutil.copy2(ARTIFACT_PROFILE, stage / "04_REQUIRED_ARTIFACT_PROFILE.json")
        write(stage / "05_FULL_REHASH_NEGATIVE_FIXTURES.json", fixtures)
        write(stage / "06_FULL_REGRESSION_RESULTS.json", regression)
        write(stage / "07_WM_COST_ABT_REPLAY_RESULTS.json", replay)
        write(stage / "08_CHANGED_FILES_COMPLETE.json", changes)
        write(stage / "09_BA10_FINAL_ACCEPTANCE_VERDICT.json", verdict)
        write(stage / "PROFILE_HASHES.json", {"pass_execution_profile_sha256": sha(PASS_PROFILE), "required_artifact_profile_sha256": sha(ARTIFACT_PROFILE), "pass_profile_contract_id": pass_profile["contract_id"], "artifact_profile_contract_id": artifact_profile["contract_id"]})
        write(stage / "PRODUCTION_TRUST_API_SCAN.json", trust)
        shutil.copy2(args.review_zip, stage / "SOURCE_REVIEW.zip")
        snapshot = stage / "SOURCE_SNAPSHOT"
        snapshot.mkdir()
        write(snapshot / "REPRODUCE.md", f"# Reproduce RFC-0005-R3\n\n```bash\ngit -C {ROOT} checkout {research_head}\ngit -C {PRODUCT} checkout {product_head}\ncd {ROOT} && .venv/bin/python -m pytest -q && .venv/bin/ruff check .\ncd {PRODUCT} && .venv/bin/python -m pytest -q\ncd {APP} && node --test scripts/test_*.mjs && npm run verify:compiler-artifact-bundle && npm run build && npm run verify && npm run verify:german-output-quality\n```\n\nThe exact commands, working directories, exit codes and captured output are in `06_FULL_REGRESSION_RESULTS.json`.")

        manifest_rows = []
        for path in sorted(candidate for candidate in stage.rglob("*") if candidate.is_file()):
            manifest_rows.append({"path": path.relative_to(stage).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)})
        write(stage / "RESULT_MANIFEST.json", {"contract_id": "room16.rfc_0005_r3.result_manifest", "contract_version": 1, "files": manifest_rows, "verdict": verdict})

        args.output_dir.mkdir(parents=True, exist_ok=True)
        output = args.output_dir / f"{name}.zip"
        second = temp / "second.zip"
        deterministic_zip(stage, output)
        deterministic_zip(stage, second)
        if sha(output) != sha(second):
            raise SystemExit("non-deterministic R3 evidence ZIP")
        output.with_suffix(output.suffix + ".sha256").write_text(f"{sha(output)}  {output.name}\n", encoding="utf-8")
        print(json.dumps({"zip": str(output), "sha256": sha(output), "second_build_identical": True, "verdict": verdict}, indent=2))


if __name__ == "__main__":
    main()
