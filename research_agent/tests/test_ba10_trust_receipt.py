from research_agent.productization.trust_receipt import build_receipt_set, verify_receipt_set


def _manifest():
    return {
        "bundle_sha256": "1" * 64,
        "compiler_identity": {"compiler_version": "1.0.0"},
        "emitter_identity": {"consumer_policy_sha256": "2" * 64},
        "compile_identity": {"ticker": "GENERIC", "as_of_date": "2026-08-18"},
    }


def test_detached_receipt_set_is_deterministic_and_tamper_evident():
    first = build_receipt_set([_manifest()], issued_by_key_id="research:test", research_commit="a" * 40)
    second = build_receipt_set([_manifest()], issued_by_key_id="research:test", research_commit="a" * 40)
    assert first == second
    verify_receipt_set(first)
    first["receipts"][0]["compile_identity"]["ticker"] = "TAMPER"
    try:
        verify_receipt_set(first)
    except ValueError as error:
        assert str(error) == "ABI_BUNDLE_RECEIPT_SET_INVALID"
    else:
        raise AssertionError("tampered receipt set accepted")
