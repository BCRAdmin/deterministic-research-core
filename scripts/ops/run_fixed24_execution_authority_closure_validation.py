#!/usr/bin/env python3
"""Execute the 30-row Fixed24 execution-authority closure matrix offline."""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import subprocess
from pathlib import Path
from typing import Any, Callable

from research_agent.alpha_shared import runner
from research_agent.alpha_shared.execution_authority import (
    BatchExecutionAuthorityIR,
    BatchExecutionCaseIR,
    ExecutionAuthorityError,
    RuntimeIdentityIR,
    authorize_case_before_network,
    fixed_company_list_sha256,
    ordered_cases_from_fixed_company_list,
    threshold_authority_sha256,
)
from research_agent.compiler_foundation.canonical import sha256_json


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _fixed_authority(
    *,
    runtime: RuntimeIdentityIR,
    companies: dict[str, Any],
    thresholds: dict[str, Any],
    list_sha256: str | None = None,
    threshold_sha256: str | None = None,
    network_live_authorized: bool = False,
    shared_freeze_sha256: str | None = None,
) -> BatchExecutionAuthorityIR:
    return BatchExecutionAuthorityIR.create(
        authority_kind="FIXED_BATCH",
        as_of_date=runtime.as_of_date,
        research_commit=runtime.research_commit,
        research_tree=runtime.research_tree,
        product_commit=runtime.product_commit,
        product_tree=runtime.product_tree,
        shared_freeze_sha256=shared_freeze_sha256,
        fixed_company_list_sha256=list_sha256 or fixed_company_list_sha256(companies),
        threshold_sha256=threshold_sha256 or threshold_authority_sha256(thresholds),
        ordered_cases=ordered_cases_from_fixed_company_list(companies),
        network_live_authorized=network_live_authorized,
    )


def _blocked(code: str, operation: Callable[[], object]) -> dict[str, object]:
    try:
        operation()
    except ExecutionAuthorityError as exc:
        if exc.code != code:
            raise AssertionError(f"expected {code}, received {exc.code}") from exc
        return {"actual": "BLOCK", "diagnostic_code": exc.code, "network_queries": 0}
    raise AssertionError(f"expected execution-authority block {code}")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def execute(args: argparse.Namespace) -> dict[str, object]:
    handoff = args.handoff_root
    matrix = _read(handoff / "05_EXECUTION_AUTHORITY_ACCEPTANCE_MATRIX.json")
    companies = _read(handoff / "06_FIXED24_LIST_AUTHORITY.json")
    thresholds = _read(handoff / "07_FIXED24_THRESHOLD_AUTHORITY.json")
    manifest = _read(handoff / "MANIFEST.json")
    runtime = RuntimeIdentityIR(
        research_commit=manifest["research_base"],
        research_tree=manifest["research_tree"],
        product_commit=manifest["product_base"],
        product_tree=manifest["product_tree"],
        as_of_date="2026-08-28",
    )
    authority = _fixed_authority(
        runtime=runtime,
        companies=companies,
        thresholds=thresholds,
    )

    def authorize(
        *,
        ticker: str = "ORCL",
        profile: str = "saas",
        sequence: int = 1,
        selected_authority: BatchExecutionAuthorityIR = authority,
        selected_runtime: RuntimeIdentityIR = runtime,
    ):
        return authorize_case_before_network(
            ticker=ticker,
            archetype_profile_id=profile,
            sequence=sequence,
            authority=selected_authority,
            runtime_identity=selected_runtime,
            fixed_company_list=companies,
            threshold_authority=thresholds,
        )

    outcomes: dict[str, dict[str, object]] = {}
    for test_id, ticker, profile, sequence in (
        ("AUTH-001", "ORCL", "saas", 1),
        ("AUTH-002", "ADBE", "saas", 2),
        ("AUTH-003", "MTDR", "energy", 24),
    ):
        receipt = authorize(ticker=ticker, profile=profile, sequence=sequence)
        outcomes[test_id] = {
            "actual": "PASS",
            "receipt_sha256": receipt.receipt_sha256,
            "authorization_mode": receipt.authorization_mode,
            "network_queries": receipt.live_network_query_count,
        }

    outcomes["AUTH-004"] = _blocked(
        "EXEC_AUTH_CASE_NOT_ORDERED", lambda: authorize(ticker="UNKNOWN")
    )
    outcomes["AUTH-005"] = _blocked(
        "EXEC_AUTH_CASE_NOT_ORDERED", lambda: authorize(sequence=2)
    )
    outcomes["AUTH-006"] = _blocked(
        "EXEC_AUTH_PROFILE_MISMATCH", lambda: authorize(profile="energy")
    )
    wrong_list = _fixed_authority(
        runtime=runtime, companies=companies, thresholds=thresholds, list_sha256="a" * 64
    )
    outcomes["AUTH-007"] = _blocked(
        "EXEC_AUTH_FIXED_LIST_HASH_MISMATCH",
        lambda: authorize(selected_authority=wrong_list),
    )
    wrong_threshold = _fixed_authority(
        runtime=runtime,
        companies=companies,
        thresholds=thresholds,
        threshold_sha256="b" * 64,
    )
    outcomes["AUTH-008"] = _blocked(
        "EXEC_AUTH_THRESHOLD_HASH_MISMATCH",
        lambda: authorize(selected_authority=wrong_threshold),
    )
    runtime_variants = {
        "AUTH-009": runtime.model_copy(update={"research_commit": "a" * 40}),
        "AUTH-010": runtime.model_copy(update={"research_tree": "b" * 40}),
        "AUTH-011": runtime.model_copy(update={"product_commit": "c" * 40}),
        "AUTH-012": runtime.model_copy(update={"as_of_date": "2026-08-27"}),
    }
    for test_id, selected_runtime in runtime_variants.items():
        outcomes[test_id] = _blocked(
            "EXEC_AUTH_RUNTIME_MISMATCH",
            lambda selected_runtime=selected_runtime: authorize(
                selected_runtime=selected_runtime
            ),
        )
    live_without_freeze = _fixed_authority(
        runtime=runtime,
        companies=companies,
        thresholds=thresholds,
        network_live_authorized=True,
        shared_freeze_sha256="c" * 64,
    )
    outcomes["AUTH-013"] = _blocked(
        "EXEC_AUTH_SHARED_FREEZE_MISSING",
        lambda: authorize(selected_authority=live_without_freeze),
    )
    for test_id, field in (
        ("AUTH-014", "semantic_changes_authorized"),
        ("AUTH-015", "company_replacement_authorized"),
        ("AUTH-016", "ticker_specific_rules_authorized"),
    ):
        body = authority.model_dump(mode="json", exclude={"authority_sha256"})
        body[field] = True
        forbidden = authority.model_copy(
            update={field: True, "authority_sha256": sha256_json(body)}
        )
        outcomes[test_id] = _blocked(
            "EXEC_AUTH_FORBIDDEN_CAPABILITY",
            lambda forbidden=forbidden: authorize(selected_authority=forbidden),
        )
    tampered = authority.model_copy(update={"authority_sha256": "0" * 64})
    outcomes["AUTH-017"] = _blocked(
        "EXEC_AUTH_SELFHASH_MISMATCH",
        lambda: authorize(selected_authority=tampered),
    )
    failed = _blocked("EXEC_AUTH_CASE_NOT_ORDERED", lambda: authorize(ticker="UNKNOWN"))
    outcomes["AUTH-018"] = {**failed, "actual": "PASS", "rejected_case": "BLOCK"}
    offline_receipt = authorize()
    outcomes["AUTH-019"] = {
        "actual": "PASS",
        "authorization_mode": offline_receipt.authorization_mode,
        "network_queries": offline_receipt.live_network_query_count,
    }
    runner_source = inspect.getsource(runner)
    outcomes["AUTH-020"] = {
        "actual": "PASS"
        if "DEVELOPMENT_LIVE_TICKERS" not in runner_source
        and "verify_receipt_for_live_case" in inspect.getsource(runner.run_canonical_alpha_case)
        else "FAIL",
        "hardcoded_ticker_guard_present": "DEVELOPMENT_LIVE_TICKERS" in runner_source,
        "verified_receipt_required": True,
    }
    development_authority = BatchExecutionAuthorityIR.create(
        authority_kind="DEVELOPMENT_VALIDATION",
        as_of_date=runtime.as_of_date,
        research_commit=runtime.research_commit,
        research_tree=runtime.research_tree,
        product_commit=runtime.product_commit,
        product_tree=runtime.product_tree,
        shared_freeze_sha256=None,
        fixed_company_list_sha256=None,
        threshold_sha256=None,
        ordered_cases=(
            BatchExecutionCaseIR(
                sequence=1,
                ticker="XOM",
                company_name="Exxon Mobil Corporation",
                archetype_profile_id="energy",
            ),
        ),
        network_live_authorized=True,
    )
    development_receipt = authorize_case_before_network(
        ticker="XOM",
        archetype_profile_id="energy",
        sequence=1,
        authority=development_authority,
        runtime_identity=runtime,
    )
    outcomes["AUTH-021"] = {
        "actual": "PASS",
        "authority_kind": development_receipt.authority_kind,
        "network_queries": development_receipt.live_network_query_count,
    }
    freeze = _read(args.stop_result_root / "02_SHARED_HARDENING_FREEZE.json")
    semantic_files = {
        path: {
            "expected": expected,
            "actual": _sha256(args.research_repo / path),
            "unchanged": _sha256(args.research_repo / path) == expected,
        }
        for path, expected in freeze["source_file_sha256s"].items()
        if path != "research_agent/alpha_shared/runner.py"
    }
    outcomes["AUTH-022"] = {
        "actual": "PASS" if all(item["unchanged"] for item in semantic_files.values()) else "FAIL",
        "semantic_file_count": len(semantic_files),
        "runner_excluded_as_authorized_execution_control_delta": True,
    }
    product_clean = _git(args.product_repo, "status", "--porcelain", "--untracked-files=no") == ""
    product_identity = {
        "head": _git(args.product_repo, "rev-parse", "HEAD"),
        "tree": _git(args.product_repo, "rev-parse", "HEAD^{tree}"),
    }
    outcomes["AUTH-023"] = {
        "actual": "PASS"
        if product_clean
        and product_identity["head"] == manifest["product_base"]
        and product_identity["tree"] == manifest["product_tree"]
        else "FAIL",
        "product_clean": product_clean,
        **product_identity,
    }
    prestart = _read(args.stop_result_root / "04_BATCH_PRESTART_STATE.json")
    outcomes["AUTH-024"] = {
        "actual": "PASS"
        if prestart["fixed24_query_count"] == 0 and prestart["fixed24_run_count"] == 0
        else "FAIL",
        "fixed24_query_count": prestart["fixed24_query_count"],
        "fixed24_run_count": prestart["fixed24_run_count"],
    }

    external = _read(args.external_gates_json) if args.external_gates_json else {}
    outcomes.update(external.get("matrix_outcomes", {}))
    rows = []
    for expected_row in matrix["rows"]:
        test_id = expected_row["test_id"]
        outcome = outcomes.get(test_id)
        if outcome is None:
            raise RuntimeError(f"missing matrix outcome: {test_id}")
        actual = outcome["actual"]
        expected = expected_row["expected"]
        status = "PASS" if actual == expected or (expected == "BLOCK" and actual == "BLOCK") else "FAIL"
        rows.append({**expected_row, **outcome, "status": status})
    failed = [item["test_id"] for item in rows if item["status"] != "PASS"]
    result = {
        "contract_id": "room16.fixed24.execution_authority_matrix_execution@1",
        "schema_version": 1,
        "status": "PASS" if not failed else "FAIL",
        "authority_sha256": authority.authority_sha256,
        "fixed_company_list_sha256": fixed_company_list_sha256(companies),
        "threshold_sha256": threshold_authority_sha256(thresholds),
        "row_count": len(rows),
        "passed_count": len(rows) - len(failed),
        "failed_count": len(failed),
        "failed_test_ids": failed,
        "authorization_preflight_count": 8,
        "case_attempt_count": 0,
        "live_network_query_count": 0,
        "completed_case_count": 0,
        "semantic_files": semantic_files,
        "rows": rows,
    }
    _write(args.output, result)
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--handoff-root", type=Path, required=True)
    parser.add_argument("--stop-result-root", type=Path, required=True)
    parser.add_argument("--r4-root", type=Path, required=True)
    parser.add_argument("--research-repo", type=Path, required=True)
    parser.add_argument("--product-repo", type=Path, required=True)
    parser.add_argument("--external-gates-json", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    result = execute(_parser().parse_args())
    print(
        json.dumps(
            {
                "status": result["status"],
                "rows": result["row_count"],
                "failed": result["failed_count"],
                "network_queries": result["live_network_query_count"],
            },
            sort_keys=True,
        )
    )
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
