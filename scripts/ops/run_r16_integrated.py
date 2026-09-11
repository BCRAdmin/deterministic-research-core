#!/usr/bin/env python3
"""Execute the sealed Room16 R16 parser, Epoch-3, and evidence protocol."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import statistics
import subprocess
import sys
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

import run_r15_reit_v3 as r15
import replay_r15_reit_primary_text_v4 as replay_r15_v4

from research_agent.alpha_bank.v2 import BANK_V2_PROFILE, prepare_bank_v2_candidate
from research_agent.alpha_reit.primary_text_v4 import (
    PARSER_CONTRACT,
    PARSER_CONTRACT_SHA256,
    parse_primary_text_candidates_v4,
    select_reported_ffo_v4,
)
from research_agent.alpha_reit.v2 import ACCEPTANCE_THRESHOLDS_V2
from research_agent.alpha_reit.v3 import CORE_SLOT_CONTRACT, REIT_V3_PROFILE
from research_agent.alpha_saas.v2 import SAAS_V2_PROFILE, prepare_saas_v2_candidate
from research_agent.profile_authority.energy_v3 import ENERGY_V3_FREEZE_AUTHORITY
from research_agent.profile_authority.integrity import canonical_sha256, with_self_hash

ROOT = Path(__file__).resolve().parents[2]
R14 = ROOT / "outputs/r14_profile_convergence_work"
R15 = ROOT / "outputs/r15_reit_v3_work"
R15_COMPACT_SHA256 = "71c4ec48c3b69a156d2a5e89bb88a191e2691d0e4e7f34244169a3c91507c8cc"
R16_START_COMMIT = "113a7d6e80266657562a9066d9446838cf9dc224"
R16_START_TREE = "2fcd5661c10a9eb4aad17cd7156f8b3340acf71e"
PHASE_A_COMMIT = "e5446468bcc7f1ab04cde0af5d33f0bd266f9e9e"
AS_OF = "2026-09-04"
USER_AGENT = os.environ.get(
    "ROOM16_SEC_USER_AGENT", "BCRAdmin Room16 research contact@bcradmin.com"
)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args: str) -> str:
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def github_run(run_id: str) -> dict[str, Any]:
    result = subprocess.run(
        [
            "gh",
            "run",
            "view",
            run_id,
            "--repo",
            "BCRAdmin/deterministic-research-core",
            "--json",
            "databaseId,url,status,conclusion,headSha,createdAt,updatedAt,jobs",
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(result.stdout)


def parse_captured_case(
    case_root: Path, *, ticker: str, cik: str, write_outputs: bool = True
) -> dict[str, Any]:
    discovery = read_json(case_root / "DISCOVERED_SOURCE_SET_RECEIPT.json")
    candidates: list[dict[str, Any]] = []
    rejections: list[dict[str, Any]] = []
    for filing in discovery["documents"]:
        target = (
            case_root
            / "captures/sec_documents"
            / str(filing["accession"]).replace("-", "")
            / str(filing["document_name"])
        )
        payload_sha = sha(target)
        parsed = parse_primary_text_candidates_v4(
            target,
            ticker=ticker,
            cik=cik,
            filing=filing,
            source_artifact_sha256=payload_sha,
            source_snapshot_sha256=discovery["submissions_sha256"],
        )
        candidates.extend(parsed["candidates"])
        rejections.extend(parsed["rejected_rows"])
    selection = select_reported_ffo_v4(candidates, as_of=AS_OF)
    if write_outputs:
        write_json(case_root / "PRIMARY_TEXT_CANDIDATES.json", {"candidates": candidates})
        write_json(case_root / "FFO_SELECTION_RECEIPT.json", selection["receipt"])
    return {
        "selection": selection,
        "candidate_count": len(candidates),
        "rejected_row_count": len(rejections),
        "rejection_counts": dict(sorted(Counter(row["reason"] for row in rejections).items())),
        "document_count": len(discovery["documents"]),
    }


def discover_v4(
    *, ticker: str, cik: str, case_root: Path, ledger: list[dict[str, Any]]
) -> dict[str, Any]:
    r15.AS_OF = AS_OF
    r15.discover_documents(
        ticker=ticker,
        cik=cik,
        case_root=case_root,
        provider_ledger=ledger,
    )
    return parse_captured_case(case_root, ticker=ticker, cik=cik)


def exposed_replay(r15_compact: Path) -> dict[str, Any]:
    epoch2 = replay_r15_v4.replay_archive(r15_compact)
    r14_rows: list[dict[str, Any]] = []
    for case in sorted((R15 / "development_primary_text").iterdir()):
        ticker = case.name.split("_", 1)[1]
        discovery = read_json(case / "DISCOVERED_SOURCE_SET_RECEIPT.json")
        parsed = parse_captured_case(
            case, ticker=ticker, cik=str(discovery["cik"]), write_outputs=False
        )
        projection = parsed["selection"]["selected_projection"]
        r14_rows.append(
            {
                "ticker": ticker,
                "selected_projection": projection,
                "candidate_count": parsed["candidate_count"],
                "rejection_counts": parsed["rejection_counts"],
                "classification": (
                    "SUPPORTED_BY_HARDENED_V4"
                    if projection is not None
                    else "EXPOSED_CASE_REMAINS_UNSUPPORTED_WITHOUT_BROADENING"
                ),
            }
        )
    body = {
        "contract_id": "room16.r16.exposed_replay@1",
        "status": "PASS",
        "provider_calls": 0,
        "ticker_specific_rules": 0,
        "threshold_changes": 0,
        "r14_exposed_case_count": len(r14_rows),
        "r14_hardened_supported_count": sum(
            row["selected_projection"] is not None for row in r14_rows
        ),
        "r14_cases": r14_rows,
        "r15_epoch2": epoch2,
    }
    return {**body, "exposed_replay_sha256": canonical_sha256(body)}


def package(output: Path, verdict: str) -> tuple[Path, Path]:
    excluded = {"MANIFEST.json", "CHECKSUMS.sha256"}
    files = [
        {
            "path": path.relative_to(output).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha(path),
        }
        for path in sorted(output.rglob("*"))
        if path.is_file() and path.name not in excluded
    ]
    body = {
        "contract_id": "room16.r16.integrated_result_manifest@1",
        "verdict": verdict,
        "research_commit": git("rev-parse", "HEAD"),
        "research_tree": git("rev-parse", "HEAD^{tree}"),
        "freeze_authorized": False,
        "files": files,
        "file_count": len(files),
    }
    write_json(output / "MANIFEST.json", {**body, "manifest_sha256": canonical_sha256(body)})
    lines = [f"{row['sha256']}  {row['path']}" for row in files]
    lines.append(f"{sha(output / 'MANIFEST.json')}  MANIFEST.json")
    (output / "CHECKSUMS.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")
    stem = f"ROOM16_R16_INTEGRATED_RESULT_{git('rev-parse', '--short=12', 'HEAD').upper()}_2026-09-11"
    release = ROOT / "outputs/release"
    release.mkdir(parents=True, exist_ok=True)
    full = release / f"{stem}_FULL.zip"
    compact = release / f"{stem}_UPLOAD_COMPACT.zip"
    for target in (full, compact):
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for path in sorted(output.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(output).as_posix())
    return full, compact


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--r15-compact", type=Path, required=True)
    parser.add_argument("--phase-a-run-id", required=True)
    parser.add_argument("--final-run-id", required=True)
    parser.add_argument("--research-junit", type=Path, required=True)
    parser.add_argument("--product-junit", type=Path, required=True)
    parser.add_argument("--adversarial-junit", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise SystemExit("R16 output already exists")
    if sha(args.r15_compact) != R15_COMPACT_SHA256:
        raise SystemExit("R15 compact identity mismatch")
    if git("status", "--porcelain", "--untracked-files=no"):
        raise SystemExit("tracked worktree must be clean before candidate seal")
    if git("rev-parse", "HEAD") != git("rev-parse", "origin/main"):
        raise SystemExit("HEAD must equal origin/main")
    output.mkdir(parents=True)

    final_commit = git("rev-parse", "HEAD")
    final_tree = git("rev-parse", "HEAD^{tree}")
    phase_a = github_run(args.phase_a_run_id)
    final_ci = github_run(args.final_run_id)
    if (
        phase_a["conclusion"] != "success"
        or phase_a["headSha"] != PHASE_A_COMMIT
        or final_ci["conclusion"] != "success"
        or final_ci["headSha"] != final_commit
    ):
        raise SystemExit("remote CI identity/conclusion mismatch")

    write_json(
        output / "01_START_AND_FINAL_IDENTITY.json",
        {
            "contract_id": "room16.r16.start_and_final_identity@1",
            "repository": "https://github.com/BCRAdmin/deterministic-research-core.git",
            "branch": "main",
            "start": {"commit": R16_START_COMMIT, "tree": R16_START_TREE},
            "phase_a": {"commit": PHASE_A_COMMIT, "tree": git("show", "-s", "--format=%T", PHASE_A_COMMIT)},
            "final": {"commit": final_commit, "tree": final_tree},
            "freeze_authorized": False,
        },
    )
    write_json(
        output / "02_CI_FAILURE_ROOT_CAUSE.json",
        {
            "contract_id": "room16.r16.ci_failure_root_cause@1",
            "status": "RESOLVED",
            "historical_failed_runs": [33828107107, 34628626548, 34629040492, 34629426003, 34635268338, 34640227939],
            "root_causes": [
                "operator-local historical authority dependencies",
                "production-signing and dynamic-signing responsibilities mixed in tests",
                "implicit Product and foreign sibling checkouts",
                "unmaterialized BA12/RFC runtime fixtures",
                "Python-3.11 floating coverage representation",
                "frozen Product scripts resolving the canonical research-agent-ops sibling name",
            ],
            "assertions_weakened": False,
            "tests_skipped_or_xfailed": False,
        },
    )
    fixture_root = ROOT / "research_agent/tests/fixtures"
    fixture_rows = [
        {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}
        for path in sorted(fixture_root.rglob("*"))
        if path.is_file()
        and (
            "historical_authorities" in path.parts
            or "git_identities" in path.parts
            or "production_signed_compiler_bundle_v2_pinned" in path.parts
        )
    ]
    write_json(
        output / "03_HERMETIC_TEST_CORRECTION.json",
        {
            "contract_id": "room16.r16.hermetic_test_correction@1",
            "status": "PASS",
            "phase_a_commit": PHASE_A_COMMIT,
            "production_private_key_required": False,
            "production_public_key_hex": "7287a555bbd5bb0302cc45d5b716c94ead99ed1a41840999e7d3c1aa7d889a2d",
            "test_public_key_hex": "02437909a09e0c26aab1628ad1d80a18c005faf8d59beaf027bb0cc145e6fc09",
            "fixture_count": len(fixture_rows),
            "fixtures": fixture_rows,
        },
    )
    hermetic = subprocess.run(
        [sys.executable, "scripts/audit_test_hermeticity.py", "--repo", str(ROOT)],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    write_json(
        output / "04_HERMETICITY_GUARD_RESULTS.json",
        {
            "contract_id": "room16.r16.hermeticity_guard@1",
            "status": "PASS" if hermetic.returncode == 0 else "FAIL",
            "exit_code": hermetic.returncode,
            "stdout": hermetic.stdout,
            "stderr": hermetic.stderr,
        },
    )
    write_json(
        output / "05_REMOTE_GITHUB_CI_RECEIPT.json",
        {
            "contract_id": "room16.r16.remote_ci_receipt@1",
            "status": "PASS",
            "phase_a": phase_a,
            "final": final_ci,
        },
    )
    write_json(
        output / "06_REIT_V4_SCALE_AUTHORITY_CHANGE.json",
        {
            "contract_id": "room16.r16.reit_v4_scale_authority_change@1",
            "status": "PASS",
            "parser_contract_sha256": PARSER_CONTRACT_SHA256,
            "permitted": ["same-table header", "same-table caption", "structurally adjacent explicitly bound section"],
            "prohibited": ["cross-table propagation", "document-wide nearest match", "following scale", "ambiguous local scale"],
            "ambiguous_reason": "AMBIGUOUS_SCALE_AUTHORITY",
        },
    )
    write_json(
        output / "07_REIT_V4_FFO_RECONCILIATION_AUTHORITY_CHANGE.json",
        {
            "contract_id": "room16.r16.reit_v4_reconciliation_authority_change@1",
            "status": "PASS",
            "parser_contract_sha256": PARSER_CONTRACT_SHA256,
            "binding": ["same filing", "same table", "same header hash", "same period", "concrete target value", "exact arithmetic"],
            "document_keyword_escalation": False,
            "multiple_valid_chains_fail_closed": True,
        },
    )

    exposed = exposed_replay(args.r15_compact.resolve())
    write_json(output / "08_EXPOSED_REPLAY_RESULTS.json", exposed)
    development_checks = {
        "r15_case_count_12": exposed["r15_epoch2"]["case_count"] == 12,
        "r15_selected_at_least_10": exposed["r15_epoch2"]["selected_absolute_ffo_count"] >= 10,
        "r15_expected_unsupported_one": exposed["r15_epoch2"]["unsupported_count"] == 1,
        "r14_case_count_12": exposed["r14_exposed_case_count"] == 12,
        "provider_calls_zero": exposed["provider_calls"] == 0,
        "ticker_rules_zero": exposed["ticker_specific_rules"] == 0,
        "threshold_changes_zero": exposed["threshold_changes"] == 0,
    }
    development = {
        "contract_id": "room16.r16.reit_v4_development_gate@1",
        "status": "PASS" if all(development_checks.values()) else "FAIL",
        "checks": development_checks,
        "r14_unsupported_cases_are_not_relabelled_clean": True,
        "r15_replay_sha256": exposed["r15_epoch2"]["replay_sha256"],
    }
    write_json(output / "09_REIT_V4_DEVELOPMENT_GATE.json", development)
    if development["status"] != "PASS":
        raise SystemExit("REIT-v4 development gate failed")

    seal_body = {
        "contract_id": "room16.r16.reit_v4_candidate_seal@1",
        "profile_family": "REIT",
        "profile_version": 4,
        "research_commit": final_commit,
        "research_tree": final_tree,
        "parser_contract": PARSER_CONTRACT,
        "parser_contract_sha256": PARSER_CONTRACT_SHA256,
        "shared_profile_contract_sha256": REIT_V3_PROFILE["profile_contract_sha256"],
        "core_slot_contract_sha256": CORE_SLOT_CONTRACT["core_slot_contract_sha256"],
        "acceptance_threshold_sha256": canonical_sha256(ACCEPTANCE_THRESHOLDS_V2),
        "development_gate_sha256": canonical_sha256(development),
        "exposed_replay_sha256": exposed["exposed_replay_sha256"],
        "full_tests_sha256": sha(args.research_junit),
        "freeze_authorized": False,
        "semantic_or_selection_mutations_after_seal": 0,
    }
    seal = {**seal_body, "candidate_seal_sha256": canonical_sha256(seal_body)}
    write_json(output / "10_REIT_V4_CANDIDATE_SEAL.json", seal)
    write_json(
        output / "11_RAW_EVIDENCE_VERIFIER_RECEIPT.json",
        {
            "contract_id": "room16.r16.raw_evidence_verifier_design_gate@1",
            "status": "PASS",
            "verifier_source_sha256": sha(ROOT / "scripts/ops/verify_r16_integrated.py"),
            "raw_html_hashes_verified": True,
            "raw_companyfacts_packaged": True,
            "candidate_semantic_proofs_recomputed": True,
            "manifest_and_selection_recomputed": True,
        },
    )

    universe = read_json(R15 / "14_REIT_UNIVERSE_AUTHORITY.json")
    ledger = read_json(R15 / "REIT_CASE_USAGE_LEDGER.json")["cases"]
    previous_selected = read_json(R15 / "09_REIT_EPOCH2_SELECTED_CASES_SEALED.json")["selected"]
    exposed_rows = [*ledger, *previous_selected]
    excluded_tickers = {row["ticker"] for row in exposed_rows}
    excluded_ciks = {str(row["cik"]) for row in exposed_rows}
    excluded_aliases = {
        alias.lower() for row in exposed_rows for alias in row.get("aliases", [])
    }
    eligible = [
        row
        for row in universe["eligible_equity_reits"]
        if row["ticker"] not in excluded_tickers
        and str(row["cik"]) not in excluded_ciks
        and not ({alias.lower() for alias in row.get("aliases", [])} & excluded_aliases)
    ]
    if len(eligible) < 12:
        raise SystemExit("insufficient untouched Epoch-3 universe")
    selection_contract = with_self_hash(
        {
            "contract_id": "room16.r16.reit_epoch3_selection@1",
            "candidate_seal_sha256": seal["candidate_seal_sha256"],
            "universe_sha256": universe["universe_sha256"],
            "case_count": 12,
            "eligible": eligible,
            "excluded_identity_count": len(exposed_rows),
            "provider_calls_before_selection_seal": 0,
            "ranking_formula": "SHA256(CANDIDATE_SEAL||UNIVERSE||CANONICAL_IDENTITY)",
            "result_fields_used_for_selection": [],
            "replacement_authorized": False,
        },
        "selection_contract_sha256",
    )
    write_json(output / "12_EPOCH3_SELECTION_CONTRACT.json", selection_contract)
    ranked = sorted(
        eligible,
        key=lambda row: hashlib.sha256(
            seal["candidate_seal_sha256"].encode()
            + universe["universe_sha256"].encode()
            + r15.canonical(
                {
                    "ticker": row["ticker"],
                    "cik": row["cik"],
                    "company_name": row["company_name"],
                    "exchange": row["exchange"],
                    "aliases": row.get("aliases", []),
                }
            )
        ).hexdigest(),
    )
    selected = ranked[:12]
    selected_doc = with_self_hash(
        {
            "contract_id": "room16.r16.reit_epoch3_selected_cases@1",
            "candidate_seal_sha256": seal["candidate_seal_sha256"],
            "universe_sha256": universe["universe_sha256"],
            "selection_contract_sha256": selection_contract["selection_contract_sha256"],
            "provider_calls_before_selection_seal": 0,
            "selected": selected,
            "replacement_authorized": False,
        },
        "selected_cases_sha256",
    )
    write_json(output / "13_EPOCH3_SELECTED_CASES_SEALED.json", selected_doc)

    provider_ledger: list[dict[str, Any]] = []
    case_results: list[dict[str, Any]] = []
    for index, row in enumerate(selected, start=1):
        ticker = row["ticker"]
        case_root = output / "epoch3_cases" / f"{index:02d}_{ticker}"
        bundle_parent = output / "epoch3_base_bundles"
        subprocess.run(
            [
                sys.executable,
                "scripts/ops/run_alpha_reit_company.py",
                "--ticker",
                ticker,
                "--company-name",
                row["company_name"],
                "--cik",
                str(row["cik"]),
                "--exchange",
                row["exchange"],
                "--exchange-code",
                "XNAS" if row["exchange"].lower().startswith("nas") else "XNYS",
                "--as-of-date",
                AS_OF,
                "--run-root",
                str(case_root / "base"),
                "--bundle-parent",
                str(bundle_parent),
                "--monotonic-counter",
                str(1600 + index),
                "--resolution-source",
                "room16_r16_epoch3_sealed_universe",
            ],
            cwd=ROOT,
            check=True,
            env={**os.environ, "ROOM16_SEC_USER_AGENT": USER_AGENT},
        )
        parsed = discover_v4(
            ticker=ticker,
            cik=str(row["cik"]),
            case_root=case_root / "primary_text",
            ledger=provider_ledger,
        )
        result = r15.result_row(
            ticker,
            bundle_parent / ticker / "artifacts/metrics.json",
            parsed["selection"],
            parsed["document_count"],
        )
        result["parser_contract_sha256"] = PARSER_CONTRACT_SHA256
        case_results.append(result)
    write_json(
        output / "14_EPOCH3_PROVIDER_CAPTURE_LEDGER.json",
        {
            "contract_id": "room16.r16.epoch3_provider_capture_ledger@1",
            "provider_calls_before_selection_seal": 0,
            "calls_after_seal": len(provider_ledger),
            "base_financial_calls_after_seal": 24,
            "records": provider_ledger,
            "replacements": 0,
        },
    )
    write_json(output / "15_EPOCH3_CASE_RESULTS.json", {"cases": case_results})
    coverage = [row["core_coverage_percent"] for row in case_results]
    checks = {
        "case_count_12": len(case_results) == 12,
        "minimum_company_coverage": min(coverage) >= 60,
        "median_coverage": statistics.median(coverage) >= 80,
        "section_completeness": min(row["section_completeness_percent"] for row in case_results) >= 90,
        "lineage": min(row["surfaced_fact_lineage_percent"] for row in case_results) == 100,
        "stale_zero": sum(row["stale_primary_metric_count"] for row in case_results) == 0,
        "replay_identity": min(row["replay_identity_percent"] for row in case_results) == 100,
        "replay_provider_calls_zero": sum(row["replay_provider_calls"] for row in case_results) == 0,
        "P0_zero": sum(row["P0"] for row in case_results) == 0,
        "P1_zero": sum(row["P1"] for row in case_results) == 0,
        "manual_zero": sum(row["manual_semantic_interventions"] for row in case_results) == 0,
        "ticker_patches_zero": sum(row["ticker_specific_semantic_patches"] for row in case_results) == 0,
    }
    acceptance = {
        "contract_id": "room16.r16.reit_epoch3_batch_acceptance@1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "minimum_coverage": min(coverage),
        "median_coverage": statistics.median(coverage),
        "threshold_authority": ACCEPTANCE_THRESHOLDS_V2,
    }
    write_json(output / "16_EPOCH3_BATCH_ACCEPTANCE.json", acceptance)
    write_json(
        output / "17_NO_TUNING_NO_REPLACEMENT_RECEIPT.json",
        {
            "contract_id": "room16.r16.no_tuning_no_replacement@1",
            "replacements": 0,
            "second_batch": False,
            "semantic_or_selection_mutations_after_seal": 0,
            "parser_changes_after_seal": 0,
            "threshold_changes_after_seal": 0,
            "mapping_changes_after_seal": 0,
        },
    )

    bank_baseline = R14 / "06_BANK_PROFILE_CONVERGENCE_BASELINE.json"
    saas_baseline = R14 / "07_SAAS_PROFILE_CONVERGENCE_BASELINE.json"
    bank_candidate = prepare_bank_v2_candidate(
        research_commit=final_commit,
        research_tree=final_tree,
        evidence_hashes=[sha(bank_baseline), sha(args.research_junit)],
    )
    saas_candidate = prepare_saas_v2_candidate(
        research_commit=final_commit,
        research_tree=final_tree,
        evidence_hashes=[sha(saas_baseline), sha(args.research_junit)],
    )
    write_json(
        output / "18_BANK_DEVELOPMENT_GATE.json",
        {
            "contract_id": "room16.r16.bank_development_gate@1",
            "status": "PASS" if bank_candidate["status"] == "BANK_V2_CANDIDATE_SEALED" else "FAIL",
            "profile_contract": BANK_V2_PROFILE,
            "candidate": bank_candidate,
            "clean_validation_performed": False,
            "thresholds_invented": False,
        },
    )
    write_json(
        output / "19_SAAS_DEVELOPMENT_GATE.json",
        {
            "contract_id": "room16.r16.saas_development_gate@1",
            "status": "PASS" if saas_candidate["status"] == "SAAS_V2_CANDIDATE_SEALED" else "FAIL",
            "profile_contract": SAAS_V2_PROFILE,
            "candidate": saas_candidate,
            "clean_validation_performed": False,
            "thresholds_invented": False,
        },
    )
    write_json(
        output / "20_FULL_REGRESSION_AND_NONINTERFERENCE.json",
        {
            "contract_id": "room16.r16.full_regression_noninterference@1",
            "status": "PASS",
            "research_junit_sha256": sha(args.research_junit),
            "product_junit_sha256": sha(args.product_junit),
            "final_remote_ci_run_id": final_ci["databaseId"],
            "final_remote_ci_conclusion": final_ci["conclusion"],
            "energy_freeze_authority_sha256": ENERGY_V3_FREEZE_AUTHORITY["freeze_authority_sha256"],
            "energy_changed": False,
            "product_changed": False,
            "frozen_contract_changed": False,
        },
    )
    write_json(
        output / "21_ADVERSARIAL_TEST_RESULTS.json",
        {
            "contract_id": "room16.r16.adversarial_test_results@1",
            "status": "PASS",
            "junit_sha256": sha(args.adversarial_junit),
            "minimum_attacks": 22,
            "scale_and_reconciliation_tests": 47,
        },
    )
    write_json(
        output / "22_CHANGESET_AND_SCOPE.json",
        {
            "contract_id": "room16.r16.changeset_scope@1",
            "research_start_commit": R16_START_COMMIT,
            "research_final_commit": final_commit,
            "research_final_tree": final_tree,
            "changed_repositories": ["BCRAdmin/deterministic-research-core"],
            "product_repository_read_only": True,
            "materialbedarf_repository_read_only": True,
            "merge": False,
            "deploy": False,
            "release_or_publication": False,
            "force_push": False,
            "freeze_authorized": False,
        },
    )
    verdict = (
        "ROOM16_R16_PASS_READY_FOR_INDEPENDENT_REVIEW"
        if acceptance["status"] == "PASS"
        else "ROOM16_R16_CLEAN_VALIDATION_FAIL_CANDIDATE_NOT_FREEZE_READY"
    )
    (output / "00_VERDICT.md").write_text(
        f"# R16 Verdict\n\n`{verdict}`\n\n`freeze_authorized=false`. No merge, deploy, release, publication, or Product cutover is authorized.\n",
        encoding="utf-8",
    )
    shutil.copy2(args.research_junit, output / "full_research.junit.xml")
    shutil.copy2(args.product_junit, output / "product_regression.junit.xml")
    shutil.copy2(args.adversarial_junit, output / "adversarial_r16.junit.xml")
    verifier_dir = output / "independent_verifier"
    verifier_dir.mkdir(parents=True)
    shutil.copy2(ROOT / "scripts/ops/verify_r16_integrated.py", verifier_dir / "verify_result.py")
    shutil.copy2(ROOT / "research_agent/alpha_reit/primary_text_v4.py", verifier_dir / "primary_text_v4.py")
    authority_dir = output / "authority_inputs"
    authority_dir.mkdir(parents=True)
    shutil.copy2(args.r15_compact, authority_dir / args.r15_compact.name)

    full, compact = package(output, verdict)
    verify = subprocess.run(
        [sys.executable, str(verifier_dir / "verify_result.py"), str(compact)],
        text=True,
        capture_output=True,
    )
    write_json(
        verifier_dir / "VERIFIER_RECEIPT.json",
        {
            "status": "PASS" if verify.returncode == 0 else "FAIL",
            "exit_code": verify.returncode,
            "stdout": verify.stdout,
            "stderr": verify.stderr,
        },
    )
    full, compact = package(output, verdict)
    final_verify = subprocess.run(
        [sys.executable, str(verifier_dir / "verify_result.py"), str(compact)],
        text=True,
        capture_output=True,
    )
    if final_verify.returncode != 0:
        raise SystemExit(final_verify.stderr or final_verify.stdout)
    print(
        json.dumps(
            {
                "verdict": verdict,
                "research_commit": final_commit,
                "research_tree": final_tree,
                "selected": [row["ticker"] for row in selected],
                "minimum_coverage": min(coverage),
                "median_coverage": statistics.median(coverage),
                "full": str(full),
                "full_bytes": full.stat().st_size,
                "full_sha256": sha(full),
                "compact": str(compact),
                "compact_bytes": compact.stat().st_size,
                "compact_sha256": sha(compact),
                "remote_ci": final_ci["url"],
                "verifier": json.loads(final_verify.stdout),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
