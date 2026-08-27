from __future__ import annotations

import ast
import json
import subprocess
from pathlib import Path

import pytest

from research_agent.alpha_energy import (
    FRESHNESS_POLICY,
    FORMULA_REGISTRY,
    MAPPING_REGISTRY,
    OPERATING_METRICS_REQUIRING_PRIMARY_TEXT,
    PERIOD_BASIS_POLICY,
    RANKING_PROFILE,
    build_alpha_energy_bundle,
    build_energy_semantic_artifacts,
)
from research_agent.ba12_live_source import (
    LiveCaptureExecutor,
    ProviderResponse,
    bridge_capture_set_to_ba3,
)
from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.semantic_compiler.source_frontend.planner import (
    build_compile_request,
    plan_source_acquisition,
)

ROOT = Path(__file__).resolve().parents[2]
AS_OF = "2026-08-27"
AUTHORITY_TIME = "2026-08-27T12:00:00Z"
CASES = tuple(f"ENERGY-D-{index:03d}" for index in range(1, 22))


def _row(
    value: int | float,
    *,
    start: str | None = None,
    end: str = "2026-06-30",
    filed: str = "2026-08-01",
) -> dict[str, object]:
    result: dict[str, object] = {
        "end": end,
        "filed": filed,
        "form": "10-Q",
        "val": value,
        "accn": f"000-{end}-{filed}",
        "frame": None,
    }
    if start:
        result["start"] = start
    return result


def _companyfacts(*, incompatible_capex: bool = False) -> dict[str, object]:
    quarter_ytd = {
        "Revenues": (81_000, 162_000, "USD"),
        "NetIncomeLoss": (7_000, 14_000, "USD"),
        "EarningsPerShareDiluted": (2.1, 4.2, "USD/shares"),
    }
    ytd = {
        "NetCashProvidedByUsedInOperatingActivities": (31_000, "USD"),
        "PaymentsToAcquirePropertyPlantAndEquipment": (
            12_000,
            "EUR" if incompatible_capex else "USD",
        ),
        "PaymentsOfDividendsCommonStock": (8_000, "USD"),
        "PaymentsForRepurchaseOfCommonStock": (5_000, "USD"),
    }
    instants = {
        "CashAndCashEquivalentsAtCarryingValue": (25_000, "USD"),
        "DebtCurrent": (4_000, "USD"),
        "LongTermDebtAndCapitalLeaseObligations": (39_000, "USD"),
        "EntityCommonStockSharesOutstanding": (4_100, "shares"),
    }
    concepts: dict[str, object] = {}
    for concept, (quarter, half, unit) in quarter_ytd.items():
        concepts[concept] = {
            "label": concept,
            "units": {
                unit: [
                    _row(quarter, start="2026-04-01"),
                    _row(half, start="2026-01-01"),
                ]
            },
        }
    for concept, (value, unit) in ytd.items():
        concepts[concept] = {
            "label": concept,
            "units": {unit: [_row(value, start="2026-01-01")]},
        }
    for concept, (value, unit) in instants.items():
        concepts[concept] = {
            "label": concept,
            "units": {unit: [_row(value)]},
        }
    concepts["ExplorationExpense"] = {
        "label": "Exploration expense",
        "units": {
            "USD": [
                _row(500, start="2026-01-01"),
                _row(
                    450,
                    start="2025-01-01",
                    end="2025-06-30",
                    filed="2026-08-01",
                ),
            ]
        },
    }
    return {"facts": {"us-gaap": concepts}}


def _system(tmp_path: Path, *, incompatible_capex: bool = False):
    resolution = {
        "status": "supported",
        "runtimeReady": True,
        "inputKind": "ticker",
        "input": "ENE",
        "ticker": "ENE",
        "companyName": "Generic Energy Corporation",
        "exchange": "NYSE",
        "exchangeCode": "XNYS",
        "jurisdiction": "US",
        "isin": None,
        "source": "alpha_energy_test",
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
    companyfacts = _companyfacts(incompatible_capex=incompatible_capex)
    market = [
        {
            "date": "2026-08-26",
            "open": 100,
            "high": 102,
            "low": 99,
            "close": 101.5,
        }
    ]
    bodies = {
        "sec": json.dumps(companyfacts).encode(),
        "nasdaq": json.dumps(market).encode(),
    }
    records = tuple(
        executor.capture(
            request=request,
            plan=plan,
            acquisition_id=item.acquisition_id,
            attempt_id=f"alpha.energy.test.{item.provider_id}.1",
            adapter=lambda item=item: ProviderResponse(
                provider_id=item.provider_id,
                source_id=f"FIXTURE_{item.provider_id}",
                source_type=(
                    "sec_filing" if item.provider_id == "sec" else "exchange_ohlcv"
                ),
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
    artifacts = build_energy_semantic_artifacts(
        snapshot=bridge.snapshot,
        payloads=[companyfacts, {"records": market}],
    )
    return bridge, snapshot_root, artifacts


@pytest.fixture(scope="module")
def compiled(tmp_path_factory):
    root = tmp_path_factory.mktemp("alpha-energy")
    bridge, snapshot_root, artifacts = _system(root)
    bundle = build_alpha_energy_bundle(
        snapshot=bridge.snapshot,
        snapshot_root=snapshot_root,
        output_root=root / "bundle",
        research_commit="a" * 40,
        research_tree="b" * 40,
        monotonic_counter=701,
    )
    return artifacts, bundle


@pytest.mark.parametrize("test_id", CASES, ids=CASES)
def test_alpha_energy_development_matrix(test_id, compiled, tmp_path):
    artifacts, bundle = compiled
    facts = artifacts["typed_facts"]["facts"]
    grouped: dict[str, list[dict[str, object]]] = {}
    for item in facts:
        if item.get("semantic_metric_id"):
            grouped.setdefault(str(item["semantic_metric_id"]), []).append(item)
    projection = artifacts["renderer_projection"]
    n = int(test_id[-3:])
    if n == 1:
        modules: list[str] = []
        for file in (ROOT / "research_agent/alpha_energy").glob("*.py"):
            tree = ast.parse(file.read_text())
            modules.extend(
                item.module
                for item in ast.walk(tree)
                if isinstance(item, ast.ImportFrom) and item.module
            )
        assert all(
            name not in module
            for module in modules
            for name in ("alpha_saas", "alpha_reit", "alpha_bank")
        )
    elif n == 2:
        for metric in ("revenue", "net_income", "diluted_eps"):
            assert {item["period_basis"] for item in grouped[metric]} == {
                "STANDALONE_QUARTER",
                "YEAR_TO_DATE",
            }
    elif n == 3:
        half = next(
            item for item in grouped["revenue"] if item["start"] == "2026-01-01"
        )
        assert half["period_basis"] == "YEAR_TO_DATE"
        assert half["period_basis"] != "STANDALONE_QUARTER"
    elif n == 4:
        assert {"revenue", "net_income", "diluted_eps"} <= set(grouped)
    elif n == 5:
        assert {
            "operating_cash_flow",
            "capital_expenditure",
            "cash",
            "current_debt",
            "long_term_debt_and_leases",
            "shares_outstanding",
            "dividends_paid",
            "share_repurchases",
            "exploration_expense",
        } <= set(grouped)
    elif n == 6:
        old = next(
            item
            for item in grouped["exploration_expense"]
            if item["end"] == "2025-06-30"
        )
        assert old["period_role"] == "COMPARATIVE"
        assert old["newer_same_concept_same_basis_exists"] is True
        assert old not in projection["facts"]
    elif n == 7:
        projected = [item["semantic_metric_id"] for item in projection["facts"]]
        assert projected[:3] == ["revenue", "net_income", "diluted_eps"]
        assert all(item["freshness_status"] != "STALE" for item in projection["facts"])
    elif n == 8:
        row = grouped["free_cash_flow"][0]
        assert row["value"] == 19_000
        assert row["start"] == "2026-01-01" and row["end"] == "2026-06-30"
        assert row["label"] == "Free cash flow (analytical: OCF - PP&E CapEx)"
    elif n == 9:
        _, _, incompatible = _system(tmp_path, incompatible_capex=True)
        assert "free_cash_flow" not in {
            item.get("semantic_metric_id")
            for item in incompatible["typed_facts"]["facts"]
        }
        assert FORMULA_REGISTRY["formulas"]["energy.free_cash_flow@1"]["label"] != "Free cash flow"
    elif n == 10:
        unsupported = artifacts["diagnostics"]["unsupported"]
        assert {item["metric_id"] for item in unsupported} == set(
            OPERATING_METRICS_REQUIRING_PRIMARY_TEXT
        )
        assert all(
            item["status"] == "SUPPLEMENTAL_PRIMARY_TEXT_REQUIRED"
            for item in unsupported
        )
    elif n == 11:
        assert all(item["proxy_used"] is False for item in artifacts["diagnostics"]["unsupported"])
    elif n == 12:
        assert artifacts["execution_attestation"]["unit_conversion_used"] is False
        assert all(
            item.get("derivation", {}).get("unit_conversion_used") is False
            for item in facts
            if item.get("derivation")
        )
    elif n == 13:
        assert all("dimensions" not in item for item in projection["facts"])
        assert not any("segment" in item["statement"].lower() for item in projection["claims"])
    elif n == 14:
        assert projection["archetype"] == "ENERGY"
        assert "Energy" in projection["title"]
        assert not any(
            word in projection["title"] for word in ("SaaS", "REIT", "Bank")
        )
    elif n == 15:
        linked = {item["fact_id"] for item in artifacts["evidence_graph"]["nodes"]}
        assert {item["fact_id"] for item in projection["facts"]} <= linked
        assert all(
            set(item["derivation"]["operand_fact_ids"]) <= linked
            for item in facts
            if item.get("derivation")
        )
        assert all(
            {
                "start",
                "end",
                "filed",
                "form",
                "frame",
                "unit",
                "value",
                "concept",
                "namespace",
                "accession",
            }
            <= set(item)
            for item in facts
        )
    elif n == 16:
        copied = tmp_path / "run_alpha_energy_company.py"
        copied.write_bytes((ROOT / "scripts/ops/run_alpha_energy_company.py").read_bytes())
        result = subprocess.run(
            [
                str(ROOT / ".venv/bin/python"),
                str(copied),
                "--research-root",
                str(ROOT),
                "--help",
            ],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "--research-root" in result.stdout
    elif n == 17:
        replay_source = (ROOT / "scripts/ops/replay_alpha_energy_company.py").read_text()
        assert '"network_provider_calls": 0' in replay_source
        assert "recover_bridge" in replay_source and "load_closed_run" in replay_source
    elif n == 18:
        assert bundle.verification["status"] == "PASS"
        emitted = {
            kind: json.loads(
                (bundle.bundle_root / "artifacts" / f"{kind}.json").read_text()
            )
            for kind in artifacts
        }
        assert sha256_json(emitted) == sha256_json(artifacts)
    elif n == 19:
        assert not any(
            name in str(ROOT / "research_agent/alpha_energy")
            for name in ("alpha_saas", "alpha_reit", "alpha_bank")
        )
        assert RANKING_PROFILE["issuer_specific_rules"] is False
    elif n == 20:
        assert bundle.verification["status"] == "PASS"
        assert artifacts["compile_verdict"]["verdict"] == "PASS"
    elif n == 21:
        assert MAPPING_REGISTRY["selection"]["issuer_specific_rules"] is False
        source = "\n".join(
            file.read_text() for file in (ROOT / "research_agent/alpha_energy").glob("*.py")
        )
        assert '"CVX"' not in source and '"XOM"' not in source


def test_registry_contracts_are_hashable():
    registries = (
        MAPPING_REGISTRY,
        PERIOD_BASIS_POLICY,
        FRESHNESS_POLICY,
        FORMULA_REGISTRY,
        RANKING_PROFILE,
    )
    assert all(len(sha256_json(item)) == 64 for item in registries)
