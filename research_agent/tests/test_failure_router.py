from research_agent.batch.failure_router import classify_failure


def test_failure_router_classifies_common_errors():
    assert classify_failure("Blocking validation errors") == "validation_error"
    assert classify_failure("Markdown audit failed") == "audit_error"
    assert classify_failure("SEC companyfacts request failed") == "source_ingestion_error"
    assert classify_failure("LLM model timeout") == "llm_error"
    assert classify_failure("totally unexpected") == "unknown_error"
