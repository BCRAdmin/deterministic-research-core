from __future__ import annotations

import ast
import json
import subprocess
from pathlib import Path

import pytest

from research_agent.alpha_reit import FRESHNESS_POLICY, FORMULA_REGISTRY, MAPPING_REGISTRY, PRIMARY_TEXT_SOURCE_PROFILE, RANKING_PROFILE, UNSUPPORTED_TEXT_METRICS, build_alpha_reit_bundle, build_reit_semantic_artifacts
from research_agent.ba12_live_source import LiveCaptureExecutor, ProviderResponse, bridge_capture_set_to_ba3
from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.semantic_compiler.source_frontend.planner import build_compile_request, plan_source_acquisition

ROOT = Path(__file__).resolve().parents[2]
AS_OF = "2026-08-26"
AUTHORITY_TIME = "2026-08-26T12:00:00Z"
CASES = tuple(f"REIT-D-{index:03d}" for index in range(1, 24))


def _obs(value, *, end="2026-06-30", start=None, unit="USD"):
    row = {"end": end, "filed": "2026-07-31" if end > "2021" else end, "form": "10-Q", "val": value}
    if start:
        row["start"] = start
    return unit, row


def _companyfacts(*, incompatible_cash=False):
    current = {
        "Revenues": (2_000, "2026-04-01"), "NetIncomeLoss": (500, "2026-04-01"),
        "NetCashProvidedByUsedInOperatingActivities": (700, "2026-01-01"),
        "DebtInstrumentCarryingAmount": (10_000, None), "LongTermDebt": (9_900, None),
        "CashAndCashEquivalentsAtCarryingValue": (1_500, None),
        "EntityCommonStockSharesOutstanding": (100, None),
        "WeightedAverageNumberOfDilutedSharesOutstanding": (98, "2026-04-01"),
        "DepreciationAndAmortization": (300, "2026-04-01"),
        "RealEstateInvestmentPropertyAccumulatedDepreciation": (4_000, None),
        "PaymentsToAcquireRealEstate": (600, "2026-01-01"),
        "CommonStockDividendsPerShareCashPaid": (1.92, "2026-04-01"),
        "PaymentsOfDividends": (250, "2026-04-01"),
        "LongtermDebtWeightedAverageInterestRate": (0.031, None),
        "LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths": (300, None),
        "LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo": (400, None),
    }
    concepts = {}
    for concept, (value, start) in current.items():
        end = "2026-03-31" if incompatible_cash and concept == "CashAndCashEquivalentsAtCarryingValue" else "2026-06-30"
        unit = "shares" if "Shares" in concept and "Dividends" not in concept else ("USD/shares" if "PerShare" in concept else ("pure" if "InterestRate" in concept else "USD"))
        u, row = _obs(value, end=end, start=start, unit=unit)
        concepts[concept] = {"label": concept, "units": {u: [row]}}
    stale = {
        "RentalRevenue": "2021-06-30", "CapitalImprovements": "2019-06-30",
        "GainOnSaleOfRealEstate": "2019-06-30", "StraightLineRent": "2015-06-30",
        "RealEstateDevelopmentInProcess": "2013-06-30",
    }
    for concept, end in stale.items():
        u, row = _obs(999, end=end)
        concepts[concept] = {"label": concept, "units": {u: [row]}}
    ffd_u, ffd_row = _obs(777)
    return {"facts": {"us-gaap": concepts, "ffd": {"OfferingFee": {"label": "Offering Fee", "units": {ffd_u: [ffd_row]}}}}}


def _system(tmp_path: Path, *, incompatible_cash=False):
    resolution = {"status": "supported", "runtimeReady": True, "inputKind": "ticker", "input": "PLD", "ticker": "PLD", "companyName": "Fixture REIT", "exchange": "NYSE", "exchangeCode": "XNYS", "jurisdiction": "US", "isin": None, "source": "alpha_reit_test"}
    request = build_compile_request(resolution, as_of_date=AS_OF, allowed_provider_ids=("nasdaq", "sec"), available_configuration_ids=("ROOM16_SEC_USER_AGENT",), network_mode="live_acquisition")
    plan = plan_source_acquisition(request, price_provider_id="nasdaq")
    executor = LiveCaptureExecutor(tmp_path / "live")
    companyfacts = _companyfacts(incompatible_cash=incompatible_cash)
    market = [{"date": "2026-08-25", "open": 1, "high": 2, "low": 1, "close": 1.5}]
    bodies = {"sec": json.dumps(companyfacts).encode(), "nasdaq": json.dumps(market).encode()}
    records = tuple(executor.capture(request=request, plan=plan, acquisition_id=item.acquisition_id, attempt_id=f"reit.test.{item.provider_id}.1", adapter=lambda item=item: ProviderResponse(provider_id=item.provider_id, source_id=f"FIXTURE_{item.provider_id}", source_type="sec_filing" if item.provider_id == "sec" else "exchange_ohlcv", original_locator=f"https://example.invalid/{item.provider_id}", final_locator=f"https://example.invalid/{item.provider_id}", status="200", media_type="application/json", payload=bodies[item.provider_id], fetched_at_utc=AUTHORITY_TIME, available_at_utc=AUTHORITY_TIME)) for item in plan.acquisitions)
    snapshot_root = tmp_path / "snapshot"
    bridge = bridge_capture_set_to_ba3(request=request, plan=plan, records=records, capture_store_root=executor.capture_store.root, snapshot_root=snapshot_root, staged_at_utc=AUTHORITY_TIME)
    artifacts = build_reit_semantic_artifacts(snapshot=bridge.snapshot, payloads=[companyfacts, {"records": market}])
    return bridge, snapshot_root, artifacts


@pytest.fixture(scope="module")
def compiled(tmp_path_factory):
    root = tmp_path_factory.mktemp("alpha-reit")
    bridge, snapshot_root, artifacts = _system(root)
    bundle = build_alpha_reit_bundle(snapshot=bridge.snapshot, snapshot_root=snapshot_root, output_root=root / "bundle", research_commit="a" * 40, research_tree="b" * 40, monotonic_counter=501)
    return artifacts, bundle


@pytest.mark.parametrize("test_id", CASES, ids=CASES)
def test_alpha_reit_development_matrix(test_id, compiled, tmp_path):
    artifacts, bundle = compiled
    facts = artifacts["typed_facts"]["facts"]
    mapped = {x.get("semantic_metric_id"): x for x in facts if x.get("semantic_metric_id")}
    projection = artifacts["renderer_projection"]
    n = int(test_id[-3:])
    if n == 1:
        tree = ast.parse((ROOT / "research_agent/alpha_reit/projection.py").read_text())
        assert "alpha_saas" not in {x.module for x in ast.walk(tree) if isinstance(x, ast.ImportFrom)}
    elif n == 2: assert mapped["revenue"]["concept"] == "Revenues"
    elif n == 3: assert mapped["net_income"]["value"] == 500
    elif n == 4:
        assert mapped["total_debt"]["concept"] == "DebtInstrumentCarryingAmount"
        assert sum(x.get("semantic_metric_id") == "total_debt" for x in facts) == 1
    elif n == 5:
        assert {"depreciation_amortization", "real_estate_acquisitions", "dividend_per_share_paid", "debt_maturity_12m"} <= set(mapped)
        assert mapped["accumulated_real_estate_depreciation"]["semantic_metric_id"] != "depreciation_amortization"
    elif n == 6: assert all(x["freshness_status"] == "STALE" for x in facts if x["concept"] in {"RentalRevenue", "CapitalImprovements", "GainOnSaleOfRealEstate", "StraightLineRent", "RealEstateDevelopmentInProcess"})
    elif n == 7: assert all(x["freshness_status"] != "STALE" for x in projection["facts"])
    elif n == 8: assert all(x.get("namespace") != "ffd" for x in projection["facts"])
    elif n == 9:
        assert mapped["net_debt"]["value"] == 8_500
        assert mapped["net_debt"]["derivation"]["operand_fact_ids"] == [mapped["total_debt"]["fact_id"], mapped["cash"]["fact_id"]]
    elif n == 10: assert not ({"ffo", "affo", "noi", "payout_ratio"} & set(mapped))
    elif n == 11: assert PRIMARY_TEXT_SOURCE_PROFILE["status"] == "TEXT_SOURCE_PROFILE_UNAVAILABLE_WITHOUT_FROZEN_CHANGE"
    elif n == 12: assert {"reported_ffo", "reported_core_ffo"} <= set(UNSUPPORTED_TEXT_METRICS)
    elif n == 13: assert {"reported_noi", "reported_same_store_noi"} <= set(UNSUPPORTED_TEXT_METRICS)
    elif n == 14: assert "reported_occupancy" in UNSUPPORTED_TEXT_METRICS
    elif n == 15: assert "reported_rent_growth" in UNSUPPORTED_TEXT_METRICS
    elif n == 16: assert PRIMARY_TEXT_SOURCE_PROFILE["live_response_parsing_allowed"] is False
    elif n == 17:
        surfaced = {x["fact_id"] for x in projection["facts"]}
        linked = {x["fact_id"] for x in artifacts["evidence_graph"]["nodes"]}
        assert surfaced <= linked
    elif n == 18:
        assert projection["archetype"] == "REIT" and "REIT" in projection["title"]
        assert [x["semantic_metric_id"] for x in projection["facts"][:2]] == ["revenue", "net_income"]
    elif n == 19:
        emitted = {kind: json.loads((bundle.bundle_root / "artifacts" / f"{kind}.json").read_text()) for kind in artifacts}
        assert bundle.verification["status"] == "PASS" and sha256_json(emitted) == sha256_json(artifacts)
    elif n == 20:
        freeze = json.loads((ROOT.parent / "Alpha/RUNS/SAAS-WAVE1-2026-08-26-R1/SOFTWARE_SAAS_ALPHA_DEVELOPMENT_CONTRACT_V1.json").read_text())
        assert freeze["freeze_sha256"] == "063e322929c7a4586e21c8c97e0177516e8870e4f777181c9964042fe5242f0c"
        assert freeze["status"] == "FROZEN"
    elif n == 21:
        result = subprocess.run([str(ROOT / ".venv/bin/python"), "scripts/ops/verify_ba12_whole_system_freeze.py", "--json"], cwd=ROOT, capture_output=True)
        assert result.returncode == 0
    elif n == 22:
        assert bundle.verification["status"] == "PASS" and RANKING_PROFILE["ticker_specific_rules"] is False
    elif n == 23:
        source = "\n".join((ROOT / "research_agent/alpha_reit" / name).read_text() for name in ("projection.py", "primary_text.py"))
        assert "Realty Income" not in source and '"O"' not in source
        assert MAPPING_REGISTRY["selection"]["ticker_specific_rules"] is False


def test_net_debt_rejects_incompatible_period(tmp_path):
    _, _, artifacts = _system(tmp_path, incompatible_cash=True)
    assert "net_debt" not in {x.get("semantic_metric_id") for x in artifacts["typed_facts"]["facts"]}


def test_registry_contracts_are_hashable():
    assert all(len(sha256_json(x)) == 64 for x in (MAPPING_REGISTRY, FRESHNESS_POLICY, FORMULA_REGISTRY, RANKING_PROFILE, PRIMARY_TEXT_SOURCE_PROFILE))
