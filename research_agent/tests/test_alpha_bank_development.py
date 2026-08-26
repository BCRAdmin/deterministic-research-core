from __future__ import annotations

import ast
import json
import subprocess
from pathlib import Path

import pytest

from research_agent.alpha_bank import (
    FRESHNESS_POLICY, FORMULA_REGISTRY, MAPPING_REGISTRY, PERIOD_BASIS_POLICY,
    RANKING_PROFILE, REGULATORY_MAPPING_REGISTRY, REGULATORY_SOURCE_PROFILE,
    REGULATORY_TARGETS, UNSUPPORTED_METRICS, build_alpha_bank_bundle,
    build_bank_semantic_artifacts, normalize_legal_name,
    resolve_unique_top_tier_entity,
)
from research_agent.ba12_live_source import LiveCaptureExecutor, ProviderResponse, bridge_capture_set_to_ba3
from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.semantic_compiler.source_frontend.planner import build_compile_request, plan_source_acquisition

ROOT = Path(__file__).resolve().parents[2]
AS_OF = "2026-08-26"
AUTHORITY_TIME = "2026-08-26T12:00:00Z"
CASES = tuple(f"BANK-D-{index:03d}" for index in range(1, 25))


def _observation(value, *, start=None, end="2026-06-30", unit="USD", filed="2026-08-01"):
    row = {"end": end, "filed": filed if end > "2020" else end, "form": "10-Q", "val": value, "accn": f"000-{end}"}
    if start:
        row["start"] = start
    return unit, row


def _companyfacts(*, incompatible_allowance=False):
    flows = {
        "NetIncomeLoss": (14_000, 27_000),
        "EarningsPerShareDiluted": (4.5, 8.6),
        "RevenuesNetOfInterestExpense": (44_000, 88_000),
        "InterestIncomeExpenseNet": (23_000, 46_000),
        "NoninterestIncome": (21_000, 42_000),
        "NoninterestExpense": (20_000, 40_000),
        "FinancingReceivableExcludingAccruedInterestCreditLossExpenseReversal": (2_500, 4_900),
        "FinancingReceivableExcludingAccruedInterestAllowanceForCreditLossWriteoffAfterRecovery": (2_000, 3_900),
        "CommonStockDividendsPerShareDeclared": (1.4, 2.8),
        "PaymentsForRepurchaseOfCommonStock": (5_000, 9_000),
        "WeightedAverageNumberOfDilutedSharesOutstanding": (3_100, 3_105),
    }
    instants = {
        "Assets": 4_000_000,
        "FinancingReceivableExcludingAccruedInterestBeforeAllowanceForCreditLoss": 1_400_000,
        "Deposits": 2_500_000,
        "DebtSecuritiesAvailableForSaleAndHeldToMaturityAmortizedCostAfterAllowanceForCreditLoss": 700_000,
        "CashAndDueFromBanks": 500_000,
        "LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities": 300_000,
        "FinancingReceivableAllowanceForCreditLossExcludingAccruedInterest": 20_000,
        "NumberOfReportableSegments": 4,
        "EntityCommonStockSharesOutstanding": 3_000,
    }
    concepts = {}
    for concept, (quarter, ytd) in flows.items():
        unit = "USD/shares" if "PerShare" in concept or "EarningsPerShare" in concept else ("shares" if "Shares" in concept else "USD")
        _, q = _observation(quarter, start="2026-04-01", unit=unit)
        _, h1 = _observation(ytd, start="2026-01-01", unit=unit)
        concepts[concept] = {"label": concept, "units": {unit: [q, h1]}}
    for concept, value in instants.items():
        end = "2026-03-31" if incompatible_allowance and concept == "FinancingReceivableAllowanceForCreditLossExcludingAccruedInterest" else "2026-06-30"
        unit = "shares" if "Shares" in concept else ("pure" if "NumberOf" in concept else "USD")
        _, row = _observation(value, end=end, unit=unit)
        concepts[concept] = {"label": concept, "units": {unit: [row]}}
    _, old = _observation(0.12, start=None, end="2012-06-30", unit="ratio")
    concepts["TierOneRiskBasedCapitalRatio"] = {"label": "Tier One Risk Based Capital Ratio", "units": {"ratio": [old]}}
    _, fee = _observation(99)
    return {"facts": {"us-gaap": concepts, "dei": {"RegistrationFee": {"label": "Registration Fee", "units": {"USD": [fee]}}}}}


def _system(tmp_path: Path, *, incompatible_allowance=False):
    resolution = {"status": "supported", "runtimeReady": True, "inputKind": "ticker", "input": "JPM", "ticker": "JPM", "companyName": "JPMorgan Chase & Co.", "exchange": "NYSE", "exchangeCode": "XNYS", "jurisdiction": "US", "isin": None, "source": "alpha_bank_test"}
    request = build_compile_request(resolution, as_of_date=AS_OF, allowed_provider_ids=("nasdaq", "sec"), available_configuration_ids=("ROOM16_SEC_USER_AGENT",), network_mode="live_acquisition")
    plan = plan_source_acquisition(request, price_provider_id="nasdaq")
    executor = LiveCaptureExecutor(tmp_path / "live")
    companyfacts = _companyfacts(incompatible_allowance=incompatible_allowance)
    market = [{"date": "2026-08-25", "open": 1, "high": 2, "low": 1, "close": 1.5}]
    bodies = {"sec": json.dumps(companyfacts).encode(), "nasdaq": json.dumps(market).encode()}
    records = tuple(executor.capture(request=request, plan=plan, acquisition_id=item.acquisition_id, attempt_id=f"bank.test.{item.provider_id}.1", adapter=lambda item=item: ProviderResponse(provider_id=item.provider_id, source_id=f"FIXTURE_{item.provider_id}", source_type="sec_filing" if item.provider_id == "sec" else "exchange_ohlcv", original_locator=f"https://example.invalid/{item.provider_id}", final_locator=f"https://example.invalid/{item.provider_id}", status="200", media_type="application/json", payload=bodies[item.provider_id], fetched_at_utc=AUTHORITY_TIME, available_at_utc=AUTHORITY_TIME)) for item in plan.acquisitions)
    snapshot_root = tmp_path / "snapshot"
    bridge = bridge_capture_set_to_ba3(request=request, plan=plan, records=records, capture_store_root=executor.capture_store.root, snapshot_root=snapshot_root, staged_at_utc=AUTHORITY_TIME)
    artifacts = build_bank_semantic_artifacts(snapshot=bridge.snapshot, payloads=[companyfacts, {"records": market}])
    return bridge, snapshot_root, artifacts


@pytest.fixture(scope="module")
def compiled(tmp_path_factory):
    root = tmp_path_factory.mktemp("alpha-bank")
    bridge, snapshot_root, artifacts = _system(root)
    bundle = build_alpha_bank_bundle(snapshot=bridge.snapshot, snapshot_root=snapshot_root, output_root=root / "bundle", research_commit="a" * 40, research_tree="b" * 40, monotonic_counter=601)
    return artifacts, bundle


@pytest.mark.parametrize("test_id", CASES, ids=CASES)
def test_alpha_bank_development_matrix(test_id, compiled):
    artifacts, bundle = compiled
    facts = artifacts["typed_facts"]["facts"]
    grouped = {}
    for item in facts:
        if item.get("semantic_metric_id"):
            grouped.setdefault(item["semantic_metric_id"], []).append(item)
    projection = artifacts["renderer_projection"]
    n = int(test_id[-3:])
    if n == 1:
        modules = []
        for file in (ROOT / "research_agent/alpha_bank").glob("*.py"):
            tree = ast.parse(file.read_text())
            modules.extend(x.module for x in ast.walk(tree) if isinstance(x, ast.ImportFrom) and x.module)
        assert all("alpha_saas" not in x and "alpha_reit" not in x for x in modules)
    elif n == 2:
        rows = grouped["net_income"]
        assert {x["period_basis"] for x in rows} == {"STANDALONE_QUARTER", "YEAR_TO_DATE"}
        assert {x["period_end"] for x in rows} == {"2026-06-30"}
    elif n == 3:
        rows = grouped["net_income"]
        assert {x["period_start"] for x in rows} == {"2026-01-01", "2026-04-01"}
        assert next(x for x in rows if x["period_start"] == "2026-01-01")["period_basis"] != "STANDALONE_QUARTER"
    elif n == 4:
        assert {"net_income", "diluted_eps", "net_revenue", "net_interest_income"} <= set(grouped)
    elif n == 5:
        assert {"gross_loans_or_financing_receivables", "deposits", "total_assets", "investment_securities", "cash_and_due_from_banks", "long_term_debt"} <= set(grouped)
    elif n == 6:
        assert {"provision_for_credit_losses", "allowance_for_credit_losses", "net_charge_offs"} <= set(grouped)
        assert len({grouped[x][0]["concept"] for x in ("provision_for_credit_losses", "allowance_for_credit_losses", "net_charge_offs")}) == 3
    elif n == 7:
        assert {"common_dividend_per_share", "common_stock_repurchases", "common_shares", "diluted_weighted_average_shares"} <= set(grouped)
    elif n == 8:
        old = next(x for x in facts if x["concept"] == "TierOneRiskBasedCapitalRatio")
        assert old["freshness_status"] == "STALE" and old not in projection["facts"]
    elif n == 9:
        assert [x["semantic_metric_id"] for x in projection["facts"][:4]] == ["net_income", "net_income", "diluted_eps", "diluted_eps"]
        assert all(x["freshness_status"] != "STALE" for x in projection["facts"])
    elif n == 10:
        row = grouped["allowance_to_loans"][0]
        assert row["value"] == pytest.approx(20_000 / 1_400_000) and "Derived period-end" in row["label"]
    elif n == 11:
        row = grouped["period_end_loans_to_deposits"][0]
        assert row["value"] == pytest.approx(1_400_000 / 2_500_000) and "Derived period-end" in row["label"]
    elif n == 12:
        assert not ({"net_interest_margin", "efficiency_ratio", "rotce", "charge_off_rate", "cet1_ratio"} & set(grouped))
    elif n == 13:
        assert REGULATORY_SOURCE_PROFILE["status"] == "REGULATORY_SOURCE_UNAVAILABLE_WITHOUT_FROZEN_CHANGE"
        assert REGULATORY_SOURCE_PROFILE["capture_before_parse_required"] is True
    elif n == 14:
        rows = [{"legal_name": "Other Bank", "is_top_tier": True, "rssd": "1"}, {"legal_name": "JPMorgan Chase & Co.", "is_top_tier": True, "rssd": "2"}]
        assert normalize_legal_name("JPMorgan Chase & Co.") == "JPMORGAN CHASE CO"
        assert resolve_unique_top_tier_entity(rows, "JPMORGAN CHASE CO")["rssd"] == "2"
        assert resolve_unique_top_tier_entity(rows + [rows[1]], "JPMORGAN CHASE CO") is None
    elif n == 15:
        assert REGULATORY_MAPPING_REGISTRY["active"] is False
        assert {"mdrm_code", "official_label", "regulatory_basis", "source_file_sha256"} <= set(REGULATORY_MAPPING_REGISTRY["required_lineage"])
    elif n == 16:
        diagnostics = artifacts["diagnostics"]["regulatory"]
        assert {x["metric_id"] for x in diagnostics} == set(REGULATORY_TARGETS)
        assert all(x["status"] == "UNSUPPORTED" for x in diagnostics)
    elif n == 17:
        assert REGULATORY_MAPPING_REGISTRY["standardized_advanced_conflation_allowed"] is False
        assert "cet1_ratio_standardized" in REGULATORY_TARGETS and "cet1_ratio_advanced" in REGULATORY_TARGETS
    elif n == 18:
        assert {"net_interest_margin", "rotce", "efficiency_ratio", "average_loans", "average_deposits", "named_segment_economics"} <= set(UNSUPPORTED_METRICS)
    elif n == 19:
        assert projection["archetype"] == "BANK" and "Bank" in projection["title"]
        assert all("[STANDALONE_QUARTER]" in x["statement"] or "[YEAR_TO_DATE]" in x["statement"] or "[INSTANT]" in x["statement"] for x in projection["claims"])
    elif n == 20:
        surfaced = {x["fact_id"] for x in projection["facts"]}
        linked = {x["fact_id"] for x in artifacts["evidence_graph"]["nodes"]}
        assert surfaced <= linked
        assert all(set(x["derivation"]["operand_fact_ids"]) <= linked for x in facts if x.get("derivation"))
    elif n == 21:
        emitted = {kind: json.loads((bundle.bundle_root / "artifacts" / f"{kind}.json").read_text()) for kind in artifacts}
        assert bundle.verification["status"] == "PASS" and sha256_json(emitted) == sha256_json(artifacts)
    elif n == 22:
        saas = json.loads((ROOT.parent / "Alpha/RUNS/SAAS-WAVE1-2026-08-26-R1/SOFTWARE_SAAS_ALPHA_DEVELOPMENT_CONTRACT_V1.json").read_text())
        reit = json.loads((ROOT.parent / "Alpha/RUNS/REIT-WAVE2-CLOSURE-2026-08-26-R1/REIT_ALPHA_DEVELOPMENT_CONTRACT_V1.json").read_text())
        assert saas["freeze_sha256"] == "063e322929c7a4586e21c8c97e0177516e8870e4f777181c9964042fe5242f0c"
        assert reit["freeze_sha256"] == "7085404f501c41c103c8057170a15ff2ebda2a1d6e4b9bed2bd0a14e3d83bdd2"
    elif n == 23:
        result = subprocess.run([str(ROOT / ".venv/bin/python"), "scripts/ops/verify_ba12_whole_system_freeze.py", "--json"], cwd=ROOT, capture_output=True)
        assert result.returncode == 0
        assert bundle.verification["status"] == "PASS"
    elif n == 24:
        source = "\n".join(file.read_text() for file in (ROOT / "research_agent/alpha_bank").glob("*.py"))
        assert "Bank of America" not in source and '"BAC"' not in source
        assert MAPPING_REGISTRY["selection"]["ticker_specific_rules"] is False


def test_derived_ratios_reject_incompatible_period(tmp_path):
    _, _, artifacts = _system(tmp_path, incompatible_allowance=True)
    assert "allowance_to_loans" not in {x.get("semantic_metric_id") for x in artifacts["typed_facts"]["facts"]}


def test_regulatory_entity_resolution_rejects_zero_duplicate_and_subsidiary():
    rows = [
        {"legal_name": "Example Bancorp", "is_top_tier": False},
        {"legal_name": "Example Bancorp", "is_top_tier": True},
    ]
    assert resolve_unique_top_tier_entity(rows, "Example Bancorp") == rows[1]
    assert resolve_unique_top_tier_entity(rows, "Missing Bancorp") is None
    assert resolve_unique_top_tier_entity(rows + [dict(rows[1])], "Example Bancorp") is None


def test_registry_contracts_are_hashable():
    registries = (MAPPING_REGISTRY, PERIOD_BASIS_POLICY, FRESHNESS_POLICY, FORMULA_REGISTRY, RANKING_PROFILE, REGULATORY_SOURCE_PROFILE, REGULATORY_MAPPING_REGISTRY)
    assert all(len(sha256_json(item)) == 64 for item in registries)
