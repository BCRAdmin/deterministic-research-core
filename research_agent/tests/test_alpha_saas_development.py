from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.alpha_saas import (
    FORMULA_REGISTRY,
    MAPPING_REGISTRY,
    RANKING_PROFILE,
    SOURCE_PROFILE,
    build_alpha_saas_bundle,
    build_saas_semantic_artifacts,
)
from research_agent.ba12_live_source import (
    LiveCaptureExecutor,
    ProviderResponse,
    bridge_capture_set_to_ba3,
)
from research_agent.semantic_compiler.source_frontend.planner import (
    build_compile_request,
    plan_source_acquisition,
)


ROOT = Path(__file__).resolve().parents[2]
PRODUCT = ROOT.parent / "company-dossier-lab"
AS_OF = "2026-08-26"
AUTHORITY_TIME = "2026-08-26T12:00:00Z"
CASES = tuple(f"SAAS-D-{index:03d}" for index in range(1, 20))


def _observation(value, *, start="2026-02-01", end="2026-04-30", unit="USD"):
    return unit, {
        "start": start,
        "end": end,
        "filed": "2026-05-28",
        "form": "10-Q",
        "val": value,
    }


def _companyfacts(*, incompatible_capex: bool = False):
    concepts = {}
    values = {
        "RevenueFromContractWithCustomerExcludingAssessedTax": 11_133_000_000,
        "RevenueRemainingPerformanceObligation": 67_900_000_000,
        "ContractWithCustomerLiabilityCurrent": 20_363_000_000,
        "ShareBasedCompensation": 857_000_000,
        "OperatingIncomeLoss": 2_347_000_000,
        "NetCashProvidedByUsedInOperatingActivities": 6_701_000_000,
        "PaymentsToAcquirePropertyPlantAndEquipment": 145_000_000,
    }
    instant = {
        "RevenueRemainingPerformanceObligation",
        "ContractWithCustomerLiabilityCurrent",
    }
    for concept, value in values.items():
        start = None if concept in instant else "2026-02-01"
        if incompatible_capex and concept == "PaymentsToAcquirePropertyPlantAndEquipment":
            start = "2025-02-01"
        unit, observation = _observation(value, start=start)
        if start is None:
            observation.pop("start")
        concepts[concept] = {"label": concept, "units": {unit: [observation]}}
    concepts["AdditionalPaidInCapitalIncreaseFromShareBasedCompensation"] = {
        "label": "APIC increase from share based compensation",
        "units": {"USD": [_observation(999_000_000)[1]]},
    }
    concepts["AccountsPayable"] = {
        "label": "Accounts Payable (Deprecated 2009-01-31)",
        "units": {
            "USD": [
                {
                    "end": "2009-07-31",
                    "filed": "2009-08-25",
                    "form": "10-Q",
                    "val": 13_389_000,
                }
            ]
        },
    }
    return {"cik": 1, "entityName": "Fixture", "facts": {"us-gaap": concepts}}


def _system(tmp_path: Path, *, incompatible_capex: bool = False):
    resolution = {
        "status": "supported",
        "runtimeReady": True,
        "inputKind": "ticker",
        "input": "CRM",
        "ticker": "CRM",
        "companyName": "Fixture",
        "exchange": "NYSE",
        "exchangeCode": "XNYS",
        "jurisdiction": "US",
        "isin": None,
        "source": "alpha_saas_test",
    }
    request = build_compile_request(
        resolution,
        as_of_date=AS_OF,
        allowed_provider_ids=("nasdaq", "sec"),
        available_configuration_ids=("ROOM16_SEC_USER_AGENT",),
        network_mode="live_acquisition",
    )
    plan = plan_source_acquisition(request, price_provider_id="nasdaq")
    executor = LiveCaptureExecutor(tmp_path / "live")
    bodies = {
        "sec": json.dumps(_companyfacts(incompatible_capex=incompatible_capex)).encode(),
        "nasdaq": json.dumps(
            [{"date": "2026-08-25", "open": 1, "high": 2, "low": 1, "close": 1.5}]
        ).encode(),
    }
    records = tuple(
        executor.capture(
            request=request,
            plan=plan,
            acquisition_id=item.acquisition_id,
            attempt_id=f"alpha.test.{item.provider_id}.1",
            adapter=lambda item=item: ProviderResponse(
                provider_id=item.provider_id,
                source_id=f"FIXTURE_{item.provider_id}",
                source_type="sec_filing" if item.provider_id == "sec" else "exchange_ohlcv",
                original_locator=f"https://example.invalid/{item.provider_id}",
                final_locator=f"https://example.invalid/{item.provider_id}",
                status="200",
                media_type="application/json",
                payload=bodies[item.provider_id],
                fetched_at_utc=AUTHORITY_TIME,
                available_at_utc=AUTHORITY_TIME,
            ),
        )
        for item in plan.acquisitions
    )
    snapshot_root = tmp_path / "snapshot"
    bridge = bridge_capture_set_to_ba3(
        request=request,
        plan=plan,
        records=records,
        capture_store_root=executor.capture_store.root,
        snapshot_root=snapshot_root,
        staged_at_utc=AUTHORITY_TIME,
    )
    payloads = [_companyfacts(incompatible_capex=incompatible_capex), {"records": json.loads(bodies["nasdaq"])}]
    artifacts = build_saas_semantic_artifacts(snapshot=bridge.snapshot, payloads=payloads)
    return bridge, snapshot_root, artifacts


@pytest.fixture(scope="module")
def compiled(tmp_path_factory):
    root = tmp_path_factory.mktemp("alpha-saas")
    bridge, snapshot_root, artifacts = _system(root)
    bundle = build_alpha_saas_bundle(
        snapshot=bridge.snapshot,
        snapshot_root=snapshot_root,
        output_root=root / "bundle",
        research_commit="a" * 40,
        research_tree="b" * 40,
        monotonic_counter=401,
    )
    return artifacts, bundle


@pytest.mark.parametrize("test_id", CASES, ids=CASES)
def test_alpha_saas_development_matrix(test_id: str, compiled, tmp_path: Path):
    artifacts, bundle = compiled
    facts = artifacts["typed_facts"]["facts"]
    projection = artifacts["renderer_projection"]
    mapped = {item.get("semantic_metric_id"): item for item in facts}
    n = int(test_id[-3:])
    if n == 1:
        assert mapped["revenue"]["value"] == 11_133_000_000
    elif n == 2:
        assert mapped["rpo"]["value"] == 67_900_000_000
    elif n == 3:
        assert mapped["current_contract_liability"]["value"] == 20_363_000_000
    elif n == 4:
        assert mapped["direct_sbc_expense"]["concept"] == "ShareBasedCompensation"
    elif n == 5:
        assert mapped["direct_sbc_expense"]["value"] != 999_000_000
    elif n == 6:
        assert mapped["operating_margin"]["value"] == round(2_347 / 11_133, 12)
    elif n == 7:
        assert mapped["free_cash_flow"]["value"] == 6_556_000_000
    elif n == 8:
        _, _, incompatible = _system(tmp_path / "incompatible", incompatible_capex=True)
        assert "free_cash_flow" not in {
            item.get("semantic_metric_id") for item in incompatible["typed_facts"]["facts"]
        }
    elif n == 9:
        assert projection["facts"][0]["semantic_metric_id"] == "revenue"
        assert projection["facts"][-1]["concept"] == "AccountsPayable"
    elif n == 10:
        assert RANKING_PROFILE["ticker_specific_rules"] is False
    elif n == 11:
        required = {"revenue", "rpo", "current_contract_liability", "direct_sbc_expense", "operating_cash_flow", "capex", "free_cash_flow", "operating_margin"}
        assert required <= {item.get("semantic_metric_id") for item in projection["facts"]}
    elif n == 12:
        assert SOURCE_PROFILE["crpo"].startswith("explicitly_unsupported")
    elif n == 13:
        assert SOURCE_PROFILE["guidance"].startswith("explicitly_unsupported")
    elif n == 14:
        assert {item["fact_id"] for item in projection["facts"]} <= set(projection["lineage"]["fact_ids"])
    elif n == 15:
        source = (ROOT / "scripts/ops/run_alpha_saas_company.py").read_text()
        assert "http_status_or_provider_status" in source
        assert "normal_evidence_export_seconds" in source
        assert '"manual_intervention_count": 0' in source
    elif n == 16:
        assert bundle.verification["status"] == "PASS"
        emitted = {
            kind: json.loads(
                (bundle.bundle_root / "artifacts" / f"{kind}.json").read_text()
            )
            for kind in artifacts
        }
        assert sha256_json(emitted) == sha256_json(artifacts)
    elif n == 17:
        result = subprocess.run(
            [str(ROOT / ".venv/bin/python"), "scripts/ops/verify_ba12_whole_system_freeze.py", "--json"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
    elif n == 18:
        result = subprocess.run(
            [
                "node",
                "--input-type=module",
                "-e",
                "import {resolveBa12NativeReport} from './room16-app/server-modules/ba12-native-report.mjs'; console.log(resolveBa12NativeReport(process.argv[1]).projection.facts[0].semantic_metric_id)",
                str(bundle.bundle_root),
            ],
            cwd=PRODUCT,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0 and result.stdout.strip() == "revenue"
    elif n == 19:
        assert MAPPING_REGISTRY["selection"]["ticker_specific_rules"] is False
        assert FORMULA_REGISTRY["period_compatibility"] == "exact_period_start_and_end"
