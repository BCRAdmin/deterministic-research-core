# COST_AND_RUNTIME_ESTIMATE

- Typical fresh batch runtime from the latest run: `0.0` minutes.
- Operating pilot runtime from the latest run: `0.1` minutes.
- Model usage / token / cost logging is not consistently populated in the checked-in batch artifacts; current estimates should be treated as partial.
- Logged generation baseline uses `ollama / deepseek-v4-pro` for the deterministic pilot runs.

## DeepSeek vs GPT-Review

- DeepSeek: primary batch generation / deterministic pilot throughput.
- GPT-Review: selective human-supervised publish review, release-note polish and edge-case challenge runs.

## Empfohlener Betriebsmodus zur Kostensenkung

- Grosser Batch in `source_ingestion_mode` laufen lassen.
- Nur passed Reports in den Publish-Review-Bundle nehmen.
- GPT nur fuer Passed-Stichprobe und Manual-Review-Sonderfaelle zuschalten.
