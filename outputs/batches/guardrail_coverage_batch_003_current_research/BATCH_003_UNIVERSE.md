# Batch 003 Universe

- Included ticker count: `32`
- Minimum viable count: `32`

| Ticker | Benchmark | Expected Archetype | MVD | Fresh Price | SEC CompanyFacts | Reason |
|---|---|---|---|---|---|---|
| GOOGL | QQQ | MEGA_CAP_PLATFORM or MEGA_CAP_CLOUD_PLATFORM | yes | yes | yes | Gold/control regression case. |
| SNOW | QQQ | SAAS_CONSUMPTION / SAAS_SECURITY / STANDARD_GROWTH | yes | yes | yes | Gold/control regression case. |
| MSFT | QQQ | MEGA_CAP_PLATFORM or MEGA_CAP_CLOUD_PLATFORM | yes | yes | yes | Gold/control regression case. |
| AAPL | QQQ | MEGA_CAP_PLATFORM or MEGA_CAP_CLOUD_PLATFORM | yes | yes | yes | Current research coverage candidate with fresh price and SEC source path. |
| META | QQQ | MEGA_CAP_PLATFORM or MEGA_CAP_CLOUD_PLATFORM | yes | yes | yes | Current research coverage candidate with fresh price and SEC source path. |
| AMZN | QQQ | MEGA_CAP_PLATFORM or MEGA_CAP_CLOUD_PLATFORM | yes | yes | yes | Current research coverage candidate with fresh price and SEC source path. |
| NFLX | QQQ | MEGA_CAP_PLATFORM or MEGA_CAP_CLOUD_PLATFORM | yes | yes | yes | Current research coverage candidate with fresh price and SEC source path. |
| CRM | QQQ | SAAS_CONSUMPTION / SAAS_SECURITY / STANDARD_GROWTH | yes | yes | yes | Current research coverage candidate with fresh price and SEC source path. |
| DDOG | QQQ | SAAS_CONSUMPTION / SAAS_SECURITY / STANDARD_GROWTH | yes | yes | yes | Current research coverage candidate with fresh price and SEC source path. |
| NOW | QQQ | SAAS_CONSUMPTION / SAAS_SECURITY / STANDARD_GROWTH | yes | yes | yes | Current research coverage candidate with fresh price and SEC source path. |
| MDB | QQQ | SAAS_CONSUMPTION / SAAS_SECURITY / STANDARD_GROWTH | yes | yes | yes | Current research coverage candidate with fresh price and SEC source path. |
| NET | QQQ | SAAS_CONSUMPTION / SAAS_SECURITY / STANDARD_GROWTH | yes | yes | yes | Current research coverage candidate with fresh price and SEC source path. |
| ZS | QQQ | SAAS_CONSUMPTION / SAAS_SECURITY / STANDARD_GROWTH | yes | yes | yes | Current research coverage candidate with fresh price and SEC source path. |
| CRWD | QQQ | SAAS_CONSUMPTION / SAAS_SECURITY / STANDARD_GROWTH | yes | yes | yes | Current research coverage candidate with fresh price and SEC source path. |
| PANW | QQQ | SAAS_CONSUMPTION / SAAS_SECURITY / STANDARD_GROWTH | yes | yes | yes | Current research coverage candidate with fresh price and SEC source path. |
| NVDA | SMH | SEMICONDUCTOR_AI_INFRA or SEMICONDUCTOR_CYCLICAL | yes | yes | yes | Current research coverage candidate with fresh price and SEC source path. |
| AMD | SMH | SEMICONDUCTOR_AI_INFRA or SEMICONDUCTOR_CYCLICAL | yes | yes | yes | Current research coverage candidate with fresh price and SEC source path. |
| AVGO | SMH | SEMICONDUCTOR_AI_INFRA or SEMICONDUCTOR_CYCLICAL | yes | yes | yes | Current research coverage candidate with fresh price and SEC source path. |
| QCOM | SMH | SEMICONDUCTOR_AI_INFRA or SEMICONDUCTOR_CYCLICAL | yes | yes | yes | FCF-support display rule regression case. |
| MU | SMH | SEMICONDUCTOR_AI_INFRA or SEMICONDUCTOR_CYCLICAL | yes | yes | yes | Current research coverage candidate with fresh price and SEC source path. |
| MRVL | SMH | SEMICONDUCTOR_AI_INFRA or SEMICONDUCTOR_CYCLICAL | yes | yes | yes | Current research coverage candidate with fresh price and SEC source path. |
| INTC | SMH | SEMICONDUCTOR_AI_INFRA or SEMICONDUCTOR_CYCLICAL | yes | yes | yes | Current research coverage candidate with fresh price and SEC source path. |
| RGTI | QQQ | SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL | yes | yes | yes | Speculative deep-tech guardrail case. |
| IONQ | QQQ | SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL | yes | yes | yes | Speculative deep-tech guardrail case. |
| QBTS | QQQ | SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL | yes | yes | yes | Speculative deep-tech guardrail case. |
| RKLB | QQQ | EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH / DISTRESSED_CAPITAL_INTENSIVE | yes | yes | yes | Early-commercial capital-intensive guardrail case. |
| ASTS | QQQ | EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH / DISTRESSED_CAPITAL_INTENSIVE | yes | yes | yes | Early-commercial capital-intensive guardrail case. |
| ACHR | QQQ | EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH / DISTRESSED_CAPITAL_INTENSIVE | yes | yes | yes | Early-commercial capital-intensive guardrail case. |
| JOBY | QQQ | EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH / DISTRESSED_CAPITAL_INTENSIVE | yes | yes | yes | Early-commercial capital-intensive guardrail case. |
| RIVN | QQQ | EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH / DISTRESSED_CAPITAL_INTENSIVE | yes | yes | yes | Early-commercial capital-intensive guardrail case. |
| LCID | QQQ | EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH / DISTRESSED_CAPITAL_INTENSIVE | yes | yes | yes | Early-commercial capital-intensive guardrail case. |
| PLUG | QQQ | EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH / DISTRESSED_CAPITAL_INTENSIVE | yes | yes | yes | Early-commercial capital-intensive guardrail case. |

## Excluded

| Ticker | Reason |
|---|---|
| TSM | Foreign issuer / ADR support is not explicit in this deterministic source-ingestion lane. |
| ASML | Foreign issuer / ADR support is not explicit in this deterministic source-ingestion lane. |
| QUBT | Lower-priority speculative case; keep out until the higher-value quantum set is current-data-ready. |
| SOUN | Lower-priority speculative AI story-stock; keep out until core deep-tech coverage is stable. |
| BBAI | Lower-priority speculative AI story-stock; keep out until core deep-tech coverage is stable. |
| PYPL | Useful turnaround case, but lower priority than the required Batch-003 guardrail universe. |
| SNAP | Useful turnaround case, but lower priority than the required Batch-003 guardrail universe. |
| WBA | Useful distressed case, but lower priority than the required Batch-003 guardrail universe. |
| PARA | Useful distressed case, but lower priority than the required Batch-003 guardrail universe. |
