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
