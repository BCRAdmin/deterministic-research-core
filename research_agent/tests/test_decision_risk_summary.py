from research_agent.run_pipeline import _complete_risk_summary


def test_risk_summary_never_ends_mid_word() -> None:
    source = (
        "The issuer recorded a liability for the proposed remediation. "
        "The remaining sentence contains extensive additional context that must not be cut mid-word."
    )

    result = _complete_risk_summary(source, limit=75)

    assert result == "The issuer recorded a liability for the proposed remediation."
    assert not result.endswith("rem")


def test_risk_summary_without_sentence_boundary_ends_as_complete_token() -> None:
    result = _complete_risk_summary(
        "A long risk description without punctuation that continues beyond the configured boundary",
        limit=54,
    )

    assert result.endswith(".")
    assert result == "A long risk description without punctuation that."
