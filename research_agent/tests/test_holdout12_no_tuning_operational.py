from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from research_agent.alpha_shared.execution_authority import (
    RuntimeIdentityIR,
    authorize_case_before_network,
)
from research_agent.compiler_foundation.canonical import sha256_json


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/ops/run_holdout12_no_tuning.py"
SPEC = importlib.util.spec_from_file_location("holdout12_runner_test", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


def _runtime() -> RuntimeIdentityIR:
    return RuntimeIdentityIR(
        research_commit="1" * 40,
        research_tree="2" * 40,
        product_commit=RUNNER.PRODUCT_COMMIT,
        product_tree=RUNNER.PRODUCT_TREE,
        as_of_date=RUNNER.AS_OF,
    )


def _plan() -> dict[str, object]:
    rows = [
        (1, "SNOW", "Snowflake Inc.", "Software/SaaS", "saas"),
        (2, "DDOG", "Datadog, Inc.", "Software/SaaS", "saas"),
        (3, "ZS", "Zscaler, Inc.", "Software/SaaS", "saas"),
        (4, "VICI", "VICI Properties Inc.", "REIT", "reit"),
        (5, "WELL", "Welltower Inc.", "REIT", "reit"),
        (6, "SPG", "Simon Property Group, Inc.", "REIT", "reit"),
        (7, "TFC", "Truist Financial Corporation", "Bank", "bank"),
        (8, "BK", "The Bank of New York Mellon Corporation", "Bank", "bank"),
        (9, "STT", "State Street Corporation", "Bank", "bank"),
        (10, "VLO", "Valero Energy Corporation", "Integrated Energy", "energy"),
        (11, "PSX", "Phillips 66", "Integrated Energy", "energy"),
        (12, "DVN", "Devon Energy Corporation", "Integrated Energy", "energy"),
    ]
    companies = [
        {
            "sequence": sequence,
            "ticker": ticker,
            "company_name": company,
            "archetype": archetype,
            "archetype_profile_id": profile,
        }
        for sequence, ticker, company, archetype, profile in rows
    ]
    return {"companies": companies}


def test_exact_external_order_creates_twelve_zero_call_receipts():
    runtime = _runtime()
    authority = RUNNER._authority(runtime, _plan())
    receipts = [
        authorize_case_before_network(
            ticker=case.ticker,
            archetype_profile_id=case.archetype_profile_id,
            sequence=case.sequence,
            authority=authority,
            runtime_identity=runtime,
        )
        for case in authority.ordered_cases
    ]
    assert [item.ticker for item in receipts] == [
        "SNOW", "DDOG", "ZS", "VICI", "WELL", "SPG",
        "TFC", "BK", "STT", "VLO", "PSX", "DVN",
    ]
    assert all(item.live_network_query_count == 0 for item in receipts)
    assert all(item.authorization_mode == "LIVE_AUTHORIZED" for item in receipts)
    assert authority.authority_kind == "DEVELOPMENT_VALIDATION"
    assert authority.fixed_company_list_sha256 is None
    assert authority.threshold_sha256 is None


@pytest.mark.parametrize(
    ("ticker", "sequence", "profile"),
    (("WRONG", 1, "saas"), ("SNOW", 2, "saas"), ("SNOW", 1, "reit")),
)
def test_wrong_case_binding_blocks_before_network(ticker: str, sequence: int, profile: str):
    runtime = _runtime()
    authority = RUNNER._authority(runtime, _plan())
    with pytest.raises(Exception):
        authorize_case_before_network(
            ticker=ticker,
            archetype_profile_id=profile,
            sequence=sequence,
            authority=authority,
            runtime_identity=runtime,
        )


def test_plan_company_hash_is_exact_and_tamper_changes_it():
    plan = _plan()
    assert sha256_json(plan["companies"]) == RUNNER.COMPANIES_SHA
    plan["companies"][0]["ticker"] = "WRONG"  # type: ignore[index]
    assert sha256_json(plan["companies"]) != RUNNER.COMPANIES_SHA


def test_holdout_tickers_do_not_appear_in_semantic_modules():
    semantic_files = (
        "research_agent/alpha_shared/document_normalizer.py",
        "research_agent/alpha_shared/metric_semantics.py",
        "research_agent/alpha_shared/supplemental_semantics.py",
        "research_agent/alpha_shared/reit_total_row_grammar.py",
        "research_agent/alpha_shared/concept_registry.py",
        "research_agent/alpha_shared/period_freshness.py",
    )
    tickers = {item["ticker"] for item in _plan()["companies"]}  # type: ignore[index]
    for relative in semantic_files:
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert not any(ticker in text for ticker in tickers)


def test_ba12_package_file_set_is_complete_sorted_and_frozen():
    package_files = RUNNER._ba12_package_files()
    assert package_files
    assert list(package_files) == sorted(set(package_files))
    assert "research_agent/ba12_live_source.py" not in package_files
    assert all((ROOT / path).is_file() for path in package_files)
    freeze = RUNNER._freeze(_runtime())
    assert freeze["ba12_live_source_package_files"] == list(package_files)
    assert freeze["ba12_live_source_file_set_sha256"] == sha256_json(
        list(package_files)
    )
    assert all(path in freeze["frozen_source_hashes"] for path in package_files)
    assert all(RUNNER._freeze_source_checks(freeze).values())


def test_ba12_package_member_removal_blocks_freeze_verification():
    freeze = RUNNER._freeze(_runtime())
    current = RUNNER._ba12_package_files()[1:]
    checks = RUNNER._freeze_source_checks(freeze, current_package_files=current)
    assert checks["package_list_exact"] is False
    assert checks["package_file_set_selfhash"] is False


def test_unexpected_ba12_package_member_blocks_freeze_verification():
    freeze = RUNNER._freeze(_runtime())
    current = (*RUNNER._ba12_package_files(), "research_agent/ba12_live_source/unexpected.py")
    checks = RUNNER._freeze_source_checks(freeze, current_package_files=current)
    assert checks["package_list_exact"] is False
    assert checks["package_file_set_selfhash"] is False


def test_ba12_package_member_hash_tamper_blocks_freeze_verification():
    freeze = RUNNER._freeze(_runtime())
    hashes = dict(freeze["frozen_source_hashes"])
    hashes[RUNNER._ba12_package_files()[0]] = "0" * 64
    checks = RUNNER._freeze_source_checks(freeze, current_source_hashes=hashes)
    assert checks["all_frozen_source_hashes_match"] is False


def test_wrong_execution_authority_source_hash_blocks_freeze_verification():
    freeze = RUNNER._freeze(_runtime())
    assert freeze["execution_authority_source_sha256"] == RUNNER._sha(
        ROOT / RUNNER.EXECUTION_AUTHORITY_SOURCE
    )
    freeze["execution_authority_source_sha256"] = "0" * 64
    checks = RUNNER._freeze_source_checks(freeze)
    assert checks["execution_authority_source_binding"] is False
