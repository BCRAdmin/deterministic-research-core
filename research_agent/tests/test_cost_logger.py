from research_agent.batch.cost_logger import ModelUsageRecord, append_model_usage, load_model_usage


def test_cost_logger_appends_model_usage_jsonl(tmp_path):
    path = tmp_path / "model_usage.jsonl"
    append_model_usage(
        ModelUsageRecord(
            ticker="NVDA",
            agent_name="repair",
            model_provider="deepseek",
            model_name="deepseek-v4",
            input_tokens=100,
            output_tokens=50,
            estimated_cost_usd=0.01,
            latency_seconds=1.2,
        ),
        path,
    )

    records = load_model_usage(path)

    assert len(records) == 1
    assert records[0].ticker == "NVDA"
    assert records[0].output_tokens == 50
