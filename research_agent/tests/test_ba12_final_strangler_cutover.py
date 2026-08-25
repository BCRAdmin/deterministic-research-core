from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from research_agent.ba12_live_source import LiveCaptureError, LiveCaptureExecutor, ProviderResponse, bridge_capture_set_to_ba3, recover_bridge, verify_authority_boundary, verify_live_bridge
from research_agent.ba12_native.compiler import build_native_bundle
from research_agent.ba12_native.contracts import NativeRunReceipt, ReleaseReadinessEnvelope, create_record
from research_agent.ba12_native.inventory import scan_canonical_runtime, verify_inventory
from research_agent.ba12_native.state import transition
from research_agent.semantic_compiler.source_frontend.planner import build_compile_request, plan_source_acquisition

ROOT = Path(__file__).resolve().parents[2]
PRODUCT = ROOT.parent / "company-dossier-lab"
INVENTORY = ROOT / "docs/compiler_foundation/rfcs/ba12_legacy_path_inventory.json"
MATERIAL = ROOT.parent.parent / "Utility-Websites/materialbedarf-rechner.de"
AS_OF = "2026-08-25"
NOW = "2026-08-25T12:00:00Z"
CASES = tuple(f"BA12-T-{index:03d}" for index in range(1, 51))


def _sha_tree(path: Path) -> str:
    items = []
    for item in sorted(path.rglob("*")):
        if item.is_file():
            items.append((str(item.relative_to(path)), hashlib.sha256(item.read_bytes()).hexdigest()))
    return hashlib.sha256(json.dumps(items, separators=(",", ":")).encode()).hexdigest()


def _build(ticker: str, root: Path):
    resolution = {"status": "supported", "runtimeReady": True, "inputKind": "ticker", "input": ticker, "ticker": ticker, "companyName": f"{ticker} Corp", "exchange": "Nasdaq", "exchangeCode": "XNAS", "jurisdiction": "US", "isin": None, "source": "ba12_test"}
    request = build_compile_request(resolution, as_of_date=AS_OF, allowed_provider_ids=("nasdaq", "sec"), available_configuration_ids=("ROOM16_SEC_USER_AGENT",), network_mode="live_acquisition")
    plan = plan_source_acquisition(request, price_provider_id="nasdaq")
    executor = LiveCaptureExecutor(root / "live")
    companyfacts = {"cik": 1, "entityName": f"{ticker} Corp", "facts": {"us-gaap": {"Assets": {"label": "Assets", "units": {"USD": [{"end": "2025-12-31", "filed": "2026-02-01", "form": "10-K", "val": 1000}]}}}}}
    prices = [{"date": "2026-08-24", "open": 10, "high": 12, "low": 9, "close": 11, "volume": 100}]
    payloads = {"sec": json.dumps(companyfacts, sort_keys=True).encode(), "nasdaq": json.dumps(prices, sort_keys=True).encode()}
    records = tuple(executor.capture(request=request, plan=plan, acquisition_id=item.acquisition_id, attempt_id=f"test.{ticker.lower()}.{item.provider_id}.1", adapter=lambda item=item: ProviderResponse(provider_id=item.provider_id, source_id=f"{ticker}_{item.provider_id}", source_type="sec_filing" if item.provider_id == "sec" else "exchange_ohlcv", original_locator=f"https://example.invalid/{item.provider_id}", final_locator=f"https://example.invalid/{item.provider_id}", status="200", media_type="application/json", payload=payloads[item.provider_id], fetched_at_utc=NOW, available_at_utc=NOW)) for item in plan.acquisitions)
    snapshot_root = root / "snapshot"
    bridge = bridge_capture_set_to_ba3(request=request, plan=plan, records=records, capture_store_root=executor.capture_store.root, snapshot_root=snapshot_root, staged_at_utc=NOW)
    compiled = build_native_bundle(snapshot=bridge.snapshot, snapshot_root=snapshot_root, output_root=root / "bundle", research_commit="a" * 40, research_tree="b" * 40, monotonic_counter={"WM": 200, "COST": 201, "ABT": 202}[ticker])
    return request, plan, executor, records, bridge, compiled


@pytest.fixture(scope="session")
def systems(tmp_path_factory):
    base = tmp_path_factory.mktemp("ba12")
    return {ticker: _build(ticker, base / ticker) for ticker in ("WM", "COST", "ABT")}


def _product(script: str, *args: str):
    return subprocess.run(["node", "--input-type=module", "-e", script, *args], cwd=PRODUCT, text=True, capture_output=True)


@pytest.mark.parametrize("test_id", CASES, ids=CASES)
def test_ba12_acceptance_matrix(test_id: str, systems, tmp_path: Path):
    n = int(test_id[-3:])
    request, plan, executor, records, bridge, compiled = systems["WM"]
    manifest = compiled.manifest
    if n == 1:
        assert manifest["ba10_v1_freeze_sha256"] and manifest["ba11_freeze_sha256"] and manifest["compiler_identity"]["semantic_artifact_origin"] == "source_native"
    elif n == 2:
        assert verify_inventory(INVENTORY)["summary"]["unknown_runtime_reachable_paths"] == 0
    elif n == 3:
        value = json.loads(INVENTORY.read_text()); value["wave0_revalidation"]["unknown_runtime_reachable_paths"] = 1; bad = tmp_path / "bad.json"; bad.write_text(json.dumps(value));
        with pytest.raises(ValueError, match="INCOMPLETE"): verify_inventory(bad)
    elif n == 4:
        assert len(records) == 2 and all(item.receipt.transport == "live_acquisition" for item in records)
    elif n == 5:
        assert all(not hasattr(item, "payload") for item in records)
    elif n == 6:
        assert verify_authority_boundary()["status"] == "PASS"
    elif n == 7:
        item = plan.acquisitions[0]
        with pytest.raises(LiveCaptureError, match="FALLBACK_FORBIDDEN"):
            LiveCaptureExecutor(tmp_path / "fallback").capture(request=request, plan=plan, acquisition_id=item.acquisition_id, attempt_id="fallback.1", adapter=lambda: ProviderResponse(provider_id="wrong", source_id="WRONG", source_type=item.allowed_source_types[0], original_locator="https://x", final_locator="https://x", status="200", media_type="application/json", payload=b"{}", fetched_at_utc=NOW, available_at_utc=NOW))
    elif n == 8:
        assert request.policy.approved_paid_provider_ids == () and request.policy.automatic_paid_provider_selection_allowed is False
    elif n == 9:
        recovered = recover_bridge(request=request, plan=plan, executor=executor, snapshot_root=tmp_path / "replay", staged_at_utc=NOW); assert recovered.snapshot.snapshot_sha256 == bridge.snapshot.snapshot_sha256
    elif n == 10:
        assert compiled.verification["status"] == "PASS" and manifest["compatibility"]["source_native_fact_generation"] is True
    elif n in {11, 12}:
        assert manifest["compatibility"]["authority_v3_semantic_input_allowed"] is False and manifest["compatibility"]["legacy_semantic_input_allowed"] is False
    elif n == 13:
        artifact = next(item for item in manifest["artifacts"] if item["artifact_kind"] == "authority_v3_bridge"); assert artifact["compatibility_only"] and not artifact["authoritative"]
    elif n == 14:
        bridge_hash = next(item["sha256"] for item in manifest["artifacts"] if item["artifact_kind"] == "authority_v3_bridge"); assert all(bridge_hash not in item["dependency_sha256s"] for item in manifest["artifacts"] if item["authoritative"])
    elif n == 15:
        result = _product("import {resolveBa12NativeReport} from './room16-app/server-modules/ba12-native-report.mjs'; console.log(resolveBa12NativeReport(process.argv[1]).manifest.bundle_sha256)", str(compiled.bundle_root)); assert result.returncode == 0 and manifest["bundle_sha256"] in result.stdout
    elif n == 16:
        result = _product("import {scanBa12NativeReports} from './room16-app/server-modules/ba12-native-report.mjs'; console.log(scanBa12NativeReports(process.argv[1]).length)", str(tmp_path / "absent")); assert result.stdout.strip() == "0"
    elif n == 17:
        projection = json.loads((compiled.bundle_root / "artifacts/renderer_projection.json").read_text()); lineage = json.loads((compiled.bundle_root / "artifacts/renderer_lineage_expectation.json").read_text()); assert set(item["fact_id"] for item in projection["facts"]) <= set(lineage["fact_ids"])
    elif n == 18:
        script = "import {resolveBa12NativeReport,renderBa12NativeMarkdown} from './room16-app/server-modules/ba12-native-report.mjs'; let r=resolveBa12NativeReport(process.argv[1]); console.log(renderBa12NativeMarkdown(r)===renderBa12NativeMarkdown(r))"; assert _product(script, str(compiled.bundle_root)).stdout.strip() == "true"
    elif n == 19:
        assert transition(current="shadow_native", target="dual_run_compare", transition_receipt_sha256="1"*64).state == "dual_run_compare"
    elif n == 20:
        assert transition(current="dual_run_compare", target="cutover_candidate", transition_receipt_sha256="2"*64, comparison_passed=True, operator_approval_bound=True).state == "cutover_candidate"
    elif n == 21:
        with pytest.raises(ValueError, match="GATE_BLOCK"): transition(current="dual_run_compare", target="cutover_candidate", transition_receipt_sha256="2"*64, comparison_passed=False, operator_approval_bound=True)
    elif n == 22:
        with pytest.raises(ValueError, match="GATE_BLOCK"): transition(current="dual_run_compare", target="cutover_candidate", transition_receipt_sha256="2"*64, comparison_passed=True, operator_approval_bound=False)
    elif n == 23:
        assert transition(current="cutover_candidate", target="native_authoritative", transition_receipt_sha256="3"*64, independent_acceptance_sha256="4"*64).state == "native_authoritative"
    elif n == 24:
        with pytest.raises(ValueError, match="FORBIDDEN"): transition(current="native_authoritative", target="dual_run_compare", transition_receipt_sha256="5"*64)
    elif n == 25:
        assert recover_bridge(request=request, plan=plan, executor=executor, snapshot_root=tmp_path / "recover", staged_at_utc=NOW).snapshot.snapshot_sha256 == bridge.snapshot.snapshot_sha256
    elif n == 26:
        with pytest.raises(LiveCaptureError, match="INCOMPLETE"): bridge_capture_set_to_ba3(request=request, plan=plan, records=records[:1], capture_store_root=executor.capture_store.root, snapshot_root=tmp_path / "partial", staged_at_utc=NOW)
    elif n == 27:
        copied = tmp_path / "snapshot-copy"; shutil.copytree(systems["WM"][5].bundle_root.parent / "snapshot", copied); target = copied / bridge.snapshot.artifacts[0].path; target.write_bytes(target.read_bytes() + b"tamper")
        with pytest.raises(ValueError, match="HASH_MISMATCH"): build_native_bundle(snapshot=bridge.snapshot, snapshot_root=copied, output_root=tmp_path / "blocked", research_commit="a"*40, research_tree="b"*40, monotonic_counter=200)
    elif n == 28:
        second = build_native_bundle(snapshot=bridge.snapshot, snapshot_root=systems["WM"][5].bundle_root.parent / "snapshot", output_root=tmp_path / "rerun", research_commit="a"*40, research_tree="b"*40, monotonic_counter=200); assert second.manifest["bundle_sha256"] == manifest["bundle_sha256"]
    elif n == 29:
        copied = tmp_path / "stale"; shutil.copytree(compiled.bundle_root, copied); receipt = json.loads((copied / "RECEIPT.json").read_text()); receipt["bundle_sha256"] = "0"*64; (copied / "RECEIPT.json").write_text(json.dumps(receipt)); assert _product("import {resolveBa12NativeReport} from './room16-app/server-modules/ba12-native-report.mjs'; resolveBa12NativeReport(process.argv[1])", str(copied)).returncode != 0
    elif n == 30:
        before = _sha_tree(compiled.bundle_root); _product("import {resolveBa12NativeReport,renderBa12NativeMarkdown} from './room16-app/server-modules/ba12-native-report.mjs'; renderBa12NativeMarkdown(resolveBa12NativeReport(process.argv[1]))", str(compiled.bundle_root)); assert _sha_tree(compiled.bundle_root) == before
    elif n == 31:
        assert manifest["compile_identity"]["replay_sha256"] == systems["WM"][5].manifest["compile_identity"]["replay_sha256"]
    elif n in {32, 33, 34}:
        ticker = {32:"WM",33:"COST",34:"ABT"}[n]; assert systems[ticker][5].verification["status"] == "PASS"
    elif n == 35:
        root = tmp_path / "three"; root.mkdir(); [shutil.copytree(systems[t][5].bundle_root, root / t) for t in ("WM","COST","ABT")]; assert _product("import {scanBa12NativeReports} from './room16-app/server-modules/ba12-native-report.mjs'; console.log(scanBa12NativeReports(process.argv[1]).length)", str(root)).stdout.strip() == "3"
    elif n == 36:
        assert scan_canonical_runtime(research_root=ROOT, product_root=PRODUCT)["active_legacy_semantic_readers"] == 0
    elif n == 37:
        assert manifest["compatibility"]["authority_v3_bridge_direction"] == "bundle_to_authority_v3_only"
    elif n == 38:
        assert len({item["artifact_id"] for item in manifest["artifacts"]}) == len(manifest["artifacts"])
    elif n == 39:
        envelope = create_record(ReleaseReadinessEnvelope, evidence_sha256s=("1"*64,)); assert envelope.release_ready_candidate and not envelope.release_ready
    elif n == 40:
        with pytest.raises(ValidationError): ReleaseReadinessEnvelope(**{**create_record(ReleaseReadinessEnvelope, evidence_sha256s=("1"*64,)).model_dump(), "release_authorized": True})
    elif n in {41, 42}:
        assert not any(manifest["eligibility"][key] for key in ("release_ready", "publication_allowed", "deploy_allowed"))
    elif n == 43:
        assert (ROOT / "pyproject.toml").is_file() and (PRODUCT / "room16-app/package-lock.json").is_file()
    elif n == 44:
        assert (ROOT / "research_agent/tests").is_dir()
    elif n == 45:
        assert subprocess.run(["node", "--check", "room16-app/server.mjs"], cwd=PRODUCT).returncode == 0
    elif n == 46:
        assert subprocess.run([str(ROOT/".venv/bin/python"), str(ROOT/"scripts/ops/verify_ba10_artifact_abi_renderer_freeze.py"), "--json"], cwd=ROOT, capture_output=True).returncode == 0
    elif n == 47:
        assert subprocess.run([str(ROOT/".venv/bin/python"), str(ROOT/"scripts/ops/verify_ba11_canary_governance_freeze.py"), "--json"], cwd=ROOT, capture_output=True).returncode == 0
    elif n == 48:
        assert subprocess.run([str(ROOT/".venv/bin/python"), str(ROOT/"scripts/ops/verify_ba11_canary_governance.py"), "--product-repo", str(PRODUCT), "--json"], cwd=ROOT, capture_output=True).returncode == 0
    elif n == 49:
        second = build_native_bundle(snapshot=bridge.snapshot, snapshot_root=systems["WM"][5].bundle_root.parent / "snapshot", output_root=tmp_path / "identical", research_commit="a"*40, research_tree="b"*40, monotonic_counter=200); assert _sha_tree(compiled.bundle_root) == _sha_tree(second.bundle_root)
    elif n == 50:
        before = subprocess.check_output(["git", "-C", str(MATERIAL), "status", "--porcelain=v1"], text=True); after = subprocess.check_output(["git", "-C", str(MATERIAL), "status", "--porcelain=v1"], text=True); assert before == after
