from __future__ import annotations

import json
import shutil
import subprocess

from research_agent.current import room16_os_compiler as compiler


def _write(path, payload) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _bundle(tmp_path, *, currency: str | None = "USD"):
    root = tmp_path / "authority_bundle"
    root.mkdir()
    artifact_hashes = {
        "data_packet": "a" * 64,
        "source_registry": "b" * 64,
        "source_snapshot_manifest": "c" * 64,
        "evidence_ledger": "d" * 64,
        "metrics_packet": "e" * 64,
        "decision_packet": "f" * 64,
    }
    _write(
        root / "authority_manifest.json",
        {
            "generated_at": "2026-11-20T12:00:00+00:00",
            "artifacts": {
                role: {"path": f"{role}.json", "sha256": digest}
                for role, digest in artifact_hashes.items()
            },
        },
    )
    _write(
        root / "data_packet.json",
        {
            "ticker": "ACME",
            "as_of_date": "2026-11-20",
            "company_name": "Acme Corporation",
            "jurisdiction": "US",
            "exchange": "NYSE",
        },
    )
    _write(
        root / "source_registry.json",
        {"sources": [{"source_id": "ACME_SEC", "source_type": "sec_filing"}]},
    )
    _write(
        root / "source_snapshot_manifest.json",
        {
            "artifacts": [
                {
                    "snapshot_id": "snapshot_acme_sec",
                    "sha256": "1" * 64,
                    "captured_at": "2026-11-20T11:00:00+00:00",
                },
            ],
            "source_dispositions": [
                {
                    "source_id": "ACME_SEC",
                    "source_type": "sec_filing",
                    "disposition": "material_evidence",
                    "snapshot_ids": ["snapshot_acme_sec"],
                    "url": "https://www.sec.gov/Archives/example",
                    "retrieved_at": {"value": "2026-11-20T11:00:00+00:00"},
                },
            ],
        },
    )
    evidence = {
        "evidence_items": [
            {
                "evidence_id": "ACME_REVENUE",
                "source_id": "ACME_SEC",
                "supports_metrics": ["revenue_ttm"],
                "normalized_value": 100.0,
                "period": "TTM",
                "dimension": "currency",
            },
        ],
    }
    if currency is not None:
        evidence["evidence_items"][0]["currency"] = currency
    _write(root / "evidence_ledger.json", evidence)
    _write(root / "metrics_packet.json", {"fundamentals": {"revenue_ttm": 100.0}})
    _write(root / "decision_packet.json", {"conclusion_status": "rated"})
    return root


def test_compiler_emits_verified_private_source_native_dossier(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        compiler,
        "verify_authority_bundle",
        lambda _root: {"status": "pass", "blocking_failures": []},
    )
    target = tmp_path / "room16_os_dossier.json"
    receipt = compiler.compile_current_authority_bundle(
        authority_bundle_dir=_bundle(tmp_path), output_path=target
    )

    assert receipt["status"] == "verified_private"
    assert receipt["dossier"]["quality_verdict"] == "verified"
    assert receipt["dossier"]["public_evidence_status"] == "blocked"
    assert receipt["evidence_graph"]["facts"][0]["value"] == "100.0"
    assert compiler.verify_current_room16_os_receipt(target)["status"] == "pass"


def test_compiler_blocks_unknown_currency_instead_of_inferring_it(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        compiler,
        "verify_authority_bundle",
        lambda _root: {"status": "pass", "blocking_failures": []},
    )
    target = tmp_path / "room16_os_dossier.json"
    receipt = compiler.compile_current_authority_bundle(
        authority_bundle_dir=_bundle(tmp_path, currency=None), output_path=target
    )

    assert receipt["status"] == "blocked"
    assert "CURRENCY_UNKNOWN" in receipt["dossier"]["quality_blocker_codes"]
    assert compiler.verify_current_room16_os_receipt(target)["status"] == "pass"


def test_verified_receipt_hash_matches_the_product_node_canonicalizer(monkeypatch, tmp_path) -> None:
    """Protect the Python compiler → Node reader handoff from hash drift."""

    node = shutil.which("node")
    if node is None:
        # The Python compiler remains testable in isolated Python environments;
        # desktop/product CI exercises this interoperability check where Node is
        # part of the release toolchain.
        return
    monkeypatch.setattr(
        compiler,
        "verify_authority_bundle",
        lambda _root: {"status": "pass", "blocking_failures": []},
    )
    receipt = compiler.compile_current_authority_bundle(authority_bundle_dir=_bundle(tmp_path))
    body = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    node_program = r'''
const crypto = require("node:crypto");
let input = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (chunk) => { input += chunk; });
process.stdin.on("end", () => {
  const value = JSON.parse(input);
  function canonicalValue(item) {
    if (Array.isArray(item)) return item.map(canonicalValue);
    if (item && typeof item === "object") {
      return Object.fromEntries(Object.keys(item).sort().map((key) => [key, canonicalValue(item[key])]));
    }
    return item;
  }
  process.stdout.write(crypto.createHash("sha256").update(JSON.stringify(canonicalValue(value))).digest("hex"));
});
'''
    result = subprocess.run(
        [node, "-e", node_program],
        input=json.dumps(body, ensure_ascii=False),
        text=True,
        check=True,
        capture_output=True,
    )
    assert result.stdout == receipt["receipt_sha256"]


def test_receipt_verifier_rejects_rehashed_unknown_status_and_schema(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        compiler,
        "verify_authority_bundle",
        lambda _root: {"status": "pass", "blocking_failures": []},
    )
    target = tmp_path / "room16_os_dossier.json"
    receipt = compiler.compile_current_authority_bundle(
        authority_bundle_dir=_bundle(tmp_path), output_path=target
    )

    unknown_status = {**receipt, "status": "unexpected"}
    unknown_status_body = {
        key: value for key, value in unknown_status.items() if key != "receipt_sha256"
    }
    unknown_status["receipt_sha256"] = compiler.sha256_json(unknown_status_body)
    target.write_text(json.dumps(unknown_status), encoding="utf-8")
    status_result = compiler.verify_current_room16_os_receipt(target)
    assert status_result["status"] == "fail"
    assert "receipt_status" in status_result["blocking_failures"]

    unexpected_field = {**receipt, "untrusted_extra": "must not be accepted"}
    unexpected_field_body = {
        key: value for key, value in unexpected_field.items() if key != "receipt_sha256"
    }
    unexpected_field["receipt_sha256"] = compiler.sha256_json(unexpected_field_body)
    target.write_text(json.dumps(unexpected_field), encoding="utf-8")
    schema_result = compiler.verify_current_room16_os_receipt(target)
    assert schema_result["status"] == "fail"
    assert "receipt_schema" in schema_result["blocking_failures"]
