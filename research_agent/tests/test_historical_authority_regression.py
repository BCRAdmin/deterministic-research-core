from __future__ import annotations

import json
import shutil
from pathlib import Path

from research_agent.evidence.evidence_item import EvidenceItem
from research_agent.evidence.evidence_ledger import (
    build_technical_derivation_evidence,
)
from research_agent.integration.authority_bundle import build_authority_bundle
from research_agent.research_core.ingestion.source_registry import (
    SourceRegistry,
    merge_evidence_sources,
    save_source_registry,
)
from research_agent.research_core.models.metrics_packet import MetricsPacket


PACKET_ROOT = Path(__file__).resolve().parents[1] / "data" / "packets"
HISTORICAL_DATE = "2026-05-17"
REQUIRED_PACKETS = (
    "data_packet.json",
    "metrics_packet.json",
    "validation_report.json",
    "decision_packet.json",
    "evidence_ledger.json",
)


def test_legacy_historical_corpus_is_rejected_by_hardened_authority_contract(
    tmp_path: Path,
) -> None:
    """Keep the stored pre-hardening corpus as a company-agnostic negative fixture."""

    cases = [
        path
        for path in sorted(PACKET_ROOT.glob(f"*/{HISTORICAL_DATE}"))
        if all((path / name).is_file() for name in REQUIRED_PACKETS)
    ]
    assert len(cases) >= 20

    failures: dict[str, list[str]] = {}
    for source_dir in cases:
        ticker = source_dir.parent.name
        packet_dir = tmp_path / "packets" / ticker
        packet_dir.mkdir(parents=True)
        for name in REQUIRED_PACKETS:
            shutil.copy2(source_dir / name, packet_dir / name)

        data_packet = json.loads((source_dir / "data_packet.json").read_text())
        metrics_packet = MetricsPacket(
            **json.loads((source_dir / "metrics_packet.json").read_text())
        )
        ledger_payload = json.loads(
            (source_dir / "evidence_ledger.json").read_text()
        )
        evidence_items = [
            EvidenceItem(**item)
            for item in ledger_payload.get("evidence_items", [])
        ]
        registry_path = (
            PACKET_ROOT / f"{data_packet['source_registry_id']}_source_registry.json"
        )
        registry = (
            SourceRegistry(**json.loads(registry_path.read_text()))
            if registry_path.is_file()
            else None
        )
        evidence_items.extend(
            build_technical_derivation_evidence(
                ticker=ticker,
                as_of_date=HISTORICAL_DATE,
                metrics_packet=metrics_packet,
                source_registry=registry,
                runtime_evidence=evidence_items,
            )
        )
        registry = merge_evidence_sources(
            registry,
            registry_id=data_packet["source_registry_id"],
            ticker=ticker,
            evidence_items=evidence_items,
        )
        local_registry = packet_dir / "source_registry.json"
        save_source_registry(registry, local_registry)
        (packet_dir / "evidence_ledger.json").write_text(
            json.dumps(
                {
                    "ticker": ticker,
                    "as_of_date": HISTORICAL_DATE,
                    "evidence_items": [
                        item.model_dump(mode="json") for item in evidence_items
                    ],
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

        manifest = build_authority_bundle(
            packet_dir=packet_dir,
            output_dir=tmp_path / "bundles" / ticker,
            source_registry_path=local_registry,
        )
        if not manifest["analysis_allowed"]:
            failures[ticker] = manifest["blocking_failures"]

    assert set(failures) == {path.parent.name for path in cases}
    hardened_blockers = {
        "ttm_formula_operands_evidenced",
        "fcf_definition_explicit",
        "analytical_rating_independent_present",
    }
    assert all(
        hardened_blockers.intersection(blockers)
        for blockers in failures.values()
    )


def test_authority_runtime_paths_do_not_contain_company_overrides() -> None:
    roots = (
        Path(__file__).resolve().parents[1] / "integration",
        Path(__file__).resolve().parents[1] / "evidence",
        Path(__file__).resolve().parents[1] / "decision",
        Path(__file__).resolve().parents[1] / "research_core",
        Path(__file__).resolve().parents[1] / "content",
    )
    known_fixture_tickers = (
        "AMZN",
        "NVDA",
        "DDOG",
        "MDB",
        "RR",
        "RYCEY",
        "GOOGL",
        "SNOW",
        "MSFT",
        "META",
        "AAPL",
        "NFLX",
        "AVGO",
        "CRM",
    )
    violations: list[str] = []
    for root in roots:
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for ticker in known_fixture_tickers:
                if f'"{ticker}"' in text or f"'{ticker}'" in text:
                    violations.append(f"{path.relative_to(root)}:{ticker}")
    assert not violations
