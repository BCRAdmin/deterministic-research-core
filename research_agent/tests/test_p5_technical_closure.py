from __future__ import annotations

import json
from pathlib import Path

from research_agent.ops.p5_technical_closure import (
    PRODUCT_ROOT,
    RESEARCH_ROOT,
    _product_snapshot_binding,
    evaluate,
)


def test_current_p5_surface_is_technically_ready_for_human_verification() -> None:
    report = evaluate()
    assert report["status"] == "technically_ready_for_human_verification"
    assert report["technicalScopeComplete"] is True
    assert report["scopeExpansionAllowed"] is False
    assert report["automaticPaidProviderActivationAllowed"] is False
    assert report["automaticMonitoringAllowed"] is False
    assert report["counts"] == {"requirements": 7, "passed": 7, "blocked": 0}


def test_changed_product_snapshot_breaks_canonical_binding(tmp_path: Path) -> None:
    research = tmp_path / "research"
    product = tmp_path / "product"
    source = RESEARCH_ROOT / "research_agent/capabilities/market_capabilities.json"
    snapshot = PRODUCT_ROOT / "room16-app/config/market-capabilities.snapshot.json"
    binding = PRODUCT_ROOT / "room16-app/config/market-capabilities.binding.json"
    resolver = PRODUCT_ROOT / "room16-app/server-modules/symbol-resolver.mjs"
    target_source = research / "research_agent/capabilities/market_capabilities.json"
    target_snapshot = product / "room16-app/config/market-capabilities.snapshot.json"
    target_binding = product / "room16-app/config/market-capabilities.binding.json"
    target_resolver = product / "room16-app/server-modules/symbol-resolver.mjs"
    for path in (target_source, target_snapshot, target_binding, target_resolver):
        path.parent.mkdir(parents=True, exist_ok=True)
    target_source.write_bytes(source.read_bytes())
    value = json.loads(snapshot.read_text(encoding="utf-8"))
    value["jurisdictions"][2]["status"] = "supported"
    target_snapshot.write_text(json.dumps(value), encoding="utf-8")
    target_binding.write_bytes(binding.read_bytes())
    target_resolver.write_bytes(resolver.read_bytes())

    result = _product_snapshot_binding(research, product)
    assert result["status"] == "fail"
    assert "product_snapshot_differs_from_canonical_registry" in result["evidence"]["errors"]
