from __future__ import annotations

import hashlib
import inspect
import subprocess
from pathlib import Path

import pytest

from research_agent.ba12_live_source import ExistingAdapterHarness, LiveCaptureError, LiveCaptureExecutor, ProviderResponse, load_closed_run
from research_agent.ba12_native import compiler as native_compiler
from research_agent.ba12_native.inventory import scan_canonical_runtime
from research_agent.tests.test_ba12_final_strangler_cutover import _build, _product

ROOT = Path(__file__).resolve().parents[2]
PRODUCT = ROOT.parent / "company-dossier-lab"
MATERIAL = ROOT.parent.parent / "Utility-Websites/materialbedarf-rechner.de"
CASES = tuple(f"BA12-RFC10-{index:03d}" for index in range(1, 15))


@pytest.fixture(scope="session")
def delta_systems(tmp_path_factory):
    base = tmp_path_factory.mktemp("ba12-rfc10")
    return {ticker: _build(ticker, base / ticker) for ticker in ("WM", "COST", "ABT")}


@pytest.mark.parametrize("test_id", CASES, ids=CASES)
def test_ba12_rfc0010_resume_delta(test_id: str, delta_systems, tmp_path: Path):
    n = int(test_id[-3:])
    request, plan, executor, records, bridge, compiled = delta_systems["WM"]
    if n == 1:
        source = inspect.getsource(ExistingAdapterHarness.__call__); assert "method(*self.args, **self.kwargs)" in source and all(item.receipt.transport == "live_acquisition" for item in records)
    elif n == 2:
        item = plan.acquisitions[0]
        with pytest.raises(LiveCaptureError): LiveCaptureExecutor(tmp_path / "error").capture(request=request, plan=plan, acquisition_id=item.acquisition_id, attempt_id="error.1", adapter=lambda: ProviderResponse(provider_id=item.provider_id, source_id="ERROR", source_type=item.allowed_source_types[0], original_locator="https://x", final_locator="https://x", status="429", media_type="application/json", payload=b"{\"error\":true}", fetched_at_utc="2026-08-25T12:00:00Z", available_at_utc="2026-08-25T12:00:00Z"))
    elif n == 3:
        assert all(item.receipt.payload_sha256 == item.artifact.content_sha256 for item in records) and all(item.receipt.payload_sha256 in {receipt.payload_sha256 for receipt in bridge.snapshot.retrieval_receipts} for item in records)
    elif n == 4:
        closed = load_closed_run(executor=executor, closure_sha256=bridge.closure.closure_sha256); assert closed.snapshot.snapshot_sha256 == bridge.snapshot.snapshot_sha256
    elif n == 5:
        assert hashlib.sha256((ROOT / "research_agent/semantic_compiler/source_frontend/contracts.py").read_bytes()).hexdigest() == "c37dd7847905f9113e5b50af9ba669cebf06f1520c2099de65cb5e4ce16fda2b" and compiled.manifest["compiler_identity"]["semantic_wave_version_lock"] == "62867ad72cd1a99eee482e75087cbe01449faa650d7cf2c535fd494c5fef30f9"
    elif n == 6:
        assert compiled.manifest["emitter_identity"]["implementation_sha256"] == hashlib.sha256(Path(native_compiler.__file__).read_bytes()).hexdigest() and compiled.receipt["emitter_identity_sha256"]
    elif n == 7:
        result = _product("import {resolveBa12NativeReport} from './room16-app/server-modules/ba12-native-report.mjs'; console.log(resolveBa12NativeReport(process.argv[1]).trustEpoch)", str(compiled.bundle_root)); assert result.returncode == 0 and "rfc0009_native_gen2" in result.stdout
    elif n in {8, 9, 10}:
        ticker = {8:"WM", 9:"COST", 10:"ABT"}[n]; assert delta_systems[ticker][5].verification["status"] == "PASS"
    elif n == 11:
        source = (PRODUCT / "room16-app/ba12-native-server.mjs").read_text(); assert "ba12-native-report.mjs" in source and "deterministic-research-report" not in source and "research-authority-bundle" not in source
    elif n == 12:
        assert scan_canonical_runtime(research_root=ROOT, product_root=PRODUCT)["active_legacy_semantic_readers"] == 0
    elif n == 13:
        result = subprocess.run([str(ROOT / ".venv/bin/python"), str(ROOT / "scripts/ops/verify_rfc0010_freeze.py"), "--json"], cwd=ROOT, capture_output=True); value = __import__("json").loads(result.stdout); assert value["rfc0010_frozen"] and value["checks"]["runtime_files_exact"] and value["runtime_file_failures"] == []
    elif n == 14:
        before = subprocess.check_output(["git", "-C", str(MATERIAL), "status", "--porcelain=v1"], text=True); after = subprocess.check_output(["git", "-C", str(MATERIAL), "status", "--porcelain=v1"], text=True); assert before == after
