# Guardrail Coverage Matrix - guardrail_coverage_batch_001

- Price basis request: `latest_available`
- Local deterministic price basis used: `2026-05-05`
- Listed ticker count: `41`
- Prompt count note: `The operator prompt says 42 tickers, but the enumerated universe contains 41 symbols. The batch uses the listed universe only.`

## Summary

- Passed: `9`
- Manual review: `13`
- Failed: `0`
- Data unavailable: `19`

## Matrix

| Ticker | Company | Bucket | Expected Archetype | Actual Archetype | Status | Publishable | Public Ready | External Display | Publish Q | Internal Q | Data Conf | Artifact | Evidence | FP? | FN? | Next Action |
|---|---|---|---|---|---|---:|---:|---|---:|---:|---:|---|---|---|---|---|
| GOOGL | Alphabet Inc. | Gold-/Kontrollgruppe | MEGA_CAP_PLATFORM or MEGA_CAP_CLOUD_PLATFORM | MEGA_CAP_PLATFORM | passed | true | false | Hold | 95 | 100 | 83 | clean | clean | no | no | Keep in passed review bundle; no public routing without Promotion Gate. |
| SNOW | Snowflake Inc. | Gold-/Kontrollgruppe | SAAS_CONSUMPTION / STANDARD_GROWTH | SAAS_CONSUMPTION | passed | true | false | Tactical Underweight | 95 | 100 | 85 | clean | clean | no | no | Keep in passed review bundle; no public routing without Promotion Gate. |
| MSFT | Microsoft Corporation | Gold-/Kontrollgruppe | MEGA_CAP_PLATFORM or MEGA_CAP_CLOUD_PLATFORM | MEGA_CAP_PLATFORM | passed | true | false | Hold | 92 | 100 | 77 | clean | clean | no | no | Keep in passed review bundle; no public routing without Promotion Gate. |
| AAPL | Apple Inc. | Mega-Cap / Platform / Ads / Cloud | MEGA_CAP_PLATFORM or MEGA_CAP_CLOUD_PLATFORM | MEGA_CAP_PLATFORM | passed | true | false | Accumulate | 92 | 100 | 77 | clean | clean | no | no | Keep in passed review bundle; no public routing without Promotion Gate. |
| META | Meta Platforms, Inc. | Mega-Cap / Platform / Ads / Cloud | MEGA_CAP_PLATFORM or MEGA_CAP_CLOUD_PLATFORM | MEGA_CAP_PLATFORM | passed | true | false | Hold | 95 | 100 | 77 | clean | clean | no | no | Keep in passed review bundle; no public routing without Promotion Gate. |
| AMZN | Amazon.com, Inc. | Mega-Cap / Platform / Ads / Cloud | MEGA_CAP_PLATFORM or MEGA_CAP_CLOUD_PLATFORM | MEGA_CAP_PLATFORM | manual_review | false | false | Hold | 76 | 100 | 63 | clean | low_confidence | no | no | Keep manual_review and resolve blockers before any promotion. |
| NFLX | Netflix, Inc. | Mega-Cap / Platform / Ads / Cloud | MEGA_CAP_PLATFORM or MEGA_CAP_CLOUD_PLATFORM | MEGA_CAP_PLATFORM | passed | true | false | Hold | 90 | 100 | 77 | clean | clean | no | no | Keep in passed review bundle; no public routing without Promotion Gate. |
| CRM | Salesforce, Inc. | SaaS / Consumption / Cybersecurity / High-SBC | SAAS_CONSUMPTION / SAAS_SECURITY / STANDARD_GROWTH | SAAS_CONSUMPTION | passed | true | false | Hold | 88 | 100 | 75 | clean | clean | no | no | Keep in passed review bundle; no public routing without Promotion Gate. |
| DDOG | Datadog, Inc. | SaaS / Consumption / Cybersecurity / High-SBC | SAAS_CONSUMPTION / SAAS_SECURITY / STANDARD_GROWTH | SAAS_CONSUMPTION | passed | true | false | Hold | 92 | 100 | 90 | clean | clean | no | no | Keep in passed review bundle; no public routing without Promotion Gate. |
| NOW | ServiceNow, Inc. | SaaS / Consumption / Cybersecurity / High-SBC | SAAS_CONSUMPTION / SAAS_SECURITY / STANDARD_GROWTH | STANDARD_GROWTH | manual_review | false | false | Hold | 78 | 100 | 77 | clean | clean | no | no | Keep manual_review and resolve blockers before any promotion. |
| MDB | MongoDB, Inc. | SaaS / Consumption / Cybersecurity / High-SBC | SAAS_CONSUMPTION / SAAS_SECURITY / STANDARD_GROWTH | SAAS_CONSUMPTION | manual_review | false | false | Hold | 78 | 100 | 77 | clean | clean | no | no | Keep manual_review and resolve blockers before any promotion. |
| NET | Cloudflare, Inc. | SaaS / Consumption / Cybersecurity / High-SBC | SAAS_CONSUMPTION / SAAS_SECURITY / STANDARD_GROWTH | STANDARD_GROWTH | manual_review | false | false | Hold | 78 | 100 | 90 | clean | clean | no | no | Keep manual_review and resolve blockers before any promotion. |
| ZS | Zscaler, Inc. | SaaS / Consumption / Cybersecurity / High-SBC | SAAS_CONSUMPTION / SAAS_SECURITY / STANDARD_GROWTH | STANDARD_GROWTH | manual_review | false | false | Hold | 78 | 100 | 90 | clean | clean | no | no | Keep manual_review and resolve blockers before any promotion. |
| CRWD | CrowdStrike Holdings, Inc. | SaaS / Consumption / Cybersecurity / High-SBC | SAAS_CONSUMPTION / SAAS_SECURITY / STANDARD_GROWTH | STANDARD_GROWTH | manual_review | false | false | Hold | 60 | 100 | 69 | clean | clean | no | no | Keep manual_review and resolve blockers before any promotion. |
| PANW | Palo Alto Networks, Inc. | SaaS / Consumption / Cybersecurity / High-SBC | SAAS_CONSUMPTION / SAAS_SECURITY / STANDARD_GROWTH | STANDARD_GROWTH | manual_review | false | false | Hold | 57 | 65 | 4 | clean | low_confidence | no | no | Keep manual_review and resolve blockers before any promotion. |
| NVDA | NVIDIA Corporation | Semiconductors / AI Infrastructure / Cyclical AI | SEMICONDUCTOR_AI_INFRA or SEMICONDUCTOR_CYCLICAL | SEMICONDUCTOR_AI_INFRA | manual_review | false | false | Hold | 75 | 100 | 60 | clean | low_confidence | no | no | Keep manual_review and resolve blockers before any promotion. |
| AMD | Advanced Micro Devices, Inc. | Semiconductors / AI Infrastructure / Cyclical AI | SEMICONDUCTOR_AI_INFRA or SEMICONDUCTOR_CYCLICAL | SEMICONDUCTOR_AI_INFRA | manual_review | false | false | Hold | 74 | 100 | 63 | clean | low_confidence | no | no | Keep manual_review and resolve blockers before any promotion. |
| AVGO | Broadcom Inc. | Semiconductors / AI Infrastructure / Cyclical AI | SEMICONDUCTOR_AI_INFRA or SEMICONDUCTOR_CYCLICAL | SEMICONDUCTOR_AI_INFRA | passed | true | false | Hold | 90 | 100 | 83 | clean | clean | no | no | Keep in passed review bundle; no public routing without Promotion Gate. |
| QCOM | QUALCOMM Incorporated | Semiconductors / AI Infrastructure / Cyclical AI | SEMICONDUCTOR_AI_INFRA or SEMICONDUCTOR_CYCLICAL | SEMICONDUCTOR_AI_INFRA | manual_review | false | false | Hold Pending FCF Support | 87 | 100 | 75 | clean | clean | no | no | Keep manual_review and resolve blockers before any promotion. |
| MU | Micron Technology, Inc. | Semiconductors / AI Infrastructure / Cyclical AI | SEMICONDUCTOR_AI_INFRA or SEMICONDUCTOR_CYCLICAL | SEMICONDUCTOR_AI_INFRA | manual_review | false | false | Hold | 74 | 100 | 63 | clean | low_confidence | no | no | Keep manual_review and resolve blockers before any promotion. |
| MRVL | Marvell Technology, Inc. | Semiconductors / AI Infrastructure / Cyclical AI | SEMICONDUCTOR_AI_INFRA or SEMICONDUCTOR_CYCLICAL | SEMICONDUCTOR_AI_INFRA | manual_review | false | false | Hold | 78 | 100 | 77 | clean | clean | no | no | Keep manual_review and resolve blockers before any promotion. |
| INTC | Intel Corporation | Semiconductors / AI Infrastructure / Cyclical AI | SEMICONDUCTOR_AI_INFRA or SEMICONDUCTOR_CYCLICAL | SEMICONDUCTOR_AI_INFRA | manual_review | false | false | Hold | 78 | 100 | 81 | clean | clean | no | no | Keep manual_review and resolve blockers before any promotion. |
| TSM | Taiwan Semiconductor Manufacturing Company Limited | Semiconductors / AI Infrastructure / Cyclical AI | SEMICONDUCTOR_AI_INFRA or SEMICONDUCTOR_CYCLICAL | UNKNOWN | data_unavailable | false | false |  |  |  |  | not_applicable_data_unavailable | data_unavailable | no | no | Ingest missing price/SEC/companyfacts/IR inputs and rerun source_ingestion_mode. |
| ASML | ASML Holding N.V. | Semiconductors / AI Infrastructure / Cyclical AI | SEMICONDUCTOR_AI_INFRA or SEMICONDUCTOR_CYCLICAL | UNKNOWN | data_unavailable | false | false |  |  |  |  | not_applicable_data_unavailable | data_unavailable | no | no | Ingest missing price/SEC/companyfacts/IR inputs and rerun source_ingestion_mode. |
| RGTI | Rigetti Computing, Inc. | Speculative Deep-Tech / Quantum / Story Stocks | SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL | UNKNOWN | data_unavailable | false | false |  |  |  |  | not_applicable_data_unavailable | data_unavailable | no | no | Ingest missing price/SEC/companyfacts/IR inputs and rerun source_ingestion_mode. |
| IONQ | IonQ, Inc. | Speculative Deep-Tech / Quantum / Story Stocks | SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL | UNKNOWN | data_unavailable | false | false |  |  |  |  | not_applicable_data_unavailable | data_unavailable | no | no | Ingest missing price/SEC/companyfacts/IR inputs and rerun source_ingestion_mode. |
| QBTS | D-Wave Quantum Inc. | Speculative Deep-Tech / Quantum / Story Stocks | SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL | UNKNOWN | data_unavailable | false | false |  |  |  |  | not_applicable_data_unavailable | data_unavailable | no | no | Ingest missing price/SEC/companyfacts/IR inputs and rerun source_ingestion_mode. |
| QUBT | Quantum Computing Inc. | Speculative Deep-Tech / Quantum / Story Stocks | SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL / UNKNOWN manual_review | UNKNOWN | data_unavailable | false | false |  |  |  |  | not_applicable_data_unavailable | data_unavailable | no | no | Ingest missing price/SEC/companyfacts/IR inputs and rerun source_ingestion_mode. |
| SOUN | SoundHound AI, Inc. | Speculative Deep-Tech / Quantum / Story Stocks | SPECULATIVE_AI_STORY_STOCK / UNKNOWN manual_review | UNKNOWN | data_unavailable | false | false |  |  |  |  | not_applicable_data_unavailable | data_unavailable | no | no | Ingest missing price/SEC/companyfacts/IR inputs and rerun source_ingestion_mode. |
| BBAI | BigBear.ai Holdings, Inc. | Speculative Deep-Tech / Quantum / Story Stocks | SPECULATIVE_AI_STORY_STOCK / UNKNOWN manual_review | UNKNOWN | data_unavailable | false | false |  |  |  |  | not_applicable_data_unavailable | data_unavailable | no | no | Ingest missing price/SEC/companyfacts/IR inputs and rerun source_ingestion_mode. |
| RKLB | Rocket Lab USA, Inc. | Early-Commercial Capital-Intensive Tech / Space / Mobility / Energy | EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH | UNKNOWN | data_unavailable | false | false |  |  |  |  | not_applicable_data_unavailable | data_unavailable | no | no | Ingest missing price/SEC/companyfacts/IR inputs and rerun source_ingestion_mode. |
| ASTS | AST SpaceMobile, Inc. | Early-Commercial Capital-Intensive Tech / Space / Mobility / Energy | EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH / DISTRESSED_CAPITAL_INTENSIVE | UNKNOWN | data_unavailable | false | false |  |  |  |  | not_applicable_data_unavailable | data_unavailable | no | no | Ingest missing price/SEC/companyfacts/IR inputs and rerun source_ingestion_mode. |
| ACHR | Archer Aviation Inc. | Early-Commercial Capital-Intensive Tech / Space / Mobility / Energy | EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH / DISTRESSED_CAPITAL_INTENSIVE | UNKNOWN | data_unavailable | false | false |  |  |  |  | not_applicable_data_unavailable | data_unavailable | no | no | Ingest missing price/SEC/companyfacts/IR inputs and rerun source_ingestion_mode. |
| JOBY | Joby Aviation, Inc. | Early-Commercial Capital-Intensive Tech / Space / Mobility / Energy | EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH / DISTRESSED_CAPITAL_INTENSIVE | UNKNOWN | data_unavailable | false | false |  |  |  |  | not_applicable_data_unavailable | data_unavailable | no | no | Ingest missing price/SEC/companyfacts/IR inputs and rerun source_ingestion_mode. |
| RIVN | Rivian Automotive, Inc. | Early-Commercial Capital-Intensive Tech / Space / Mobility / Energy | EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH / DISTRESSED_CAPITAL_INTENSIVE | UNKNOWN | data_unavailable | false | false |  |  |  |  | not_applicable_data_unavailable | data_unavailable | no | no | Ingest missing price/SEC/companyfacts/IR inputs and rerun source_ingestion_mode. |
| LCID | Lucid Group, Inc. | Early-Commercial Capital-Intensive Tech / Space / Mobility / Energy | EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH / DISTRESSED_CAPITAL_INTENSIVE | UNKNOWN | data_unavailable | false | false |  |  |  |  | not_applicable_data_unavailable | data_unavailable | no | no | Ingest missing price/SEC/companyfacts/IR inputs and rerun source_ingestion_mode. |
| PLUG | Plug Power Inc. | Early-Commercial Capital-Intensive Tech / Space / Mobility / Energy | EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH / DISTRESSED_CAPITAL_INTENSIVE | UNKNOWN | data_unavailable | false | false |  |  |  |  | not_applicable_data_unavailable | data_unavailable | no | no | Ingest missing price/SEC/companyfacts/IR inputs and rerun source_ingestion_mode. |
| PYPL | PayPal Holdings, Inc. | Turnaround / Distressed / Business-Model Pressure | TURNAROUND / BUSINESS_MODEL_PRESSURE / STANDARD_WITH_RISK | UNKNOWN | data_unavailable | false | false |  |  |  |  | not_applicable_data_unavailable | data_unavailable | no | no | Ingest missing price/SEC/companyfacts/IR inputs and rerun source_ingestion_mode. |
| SNAP | Snap Inc. | Turnaround / Distressed / Business-Model Pressure | TURNAROUND / BUSINESS_MODEL_PRESSURE / STANDARD_WITH_RISK | UNKNOWN | data_unavailable | false | false |  |  |  |  | not_applicable_data_unavailable | data_unavailable | no | no | Ingest missing price/SEC/companyfacts/IR inputs and rerun source_ingestion_mode. |
| WBA | Walgreens Boots Alliance, Inc. | Turnaround / Distressed / Business-Model Pressure | TURNAROUND / BUSINESS_MODEL_PRESSURE / STANDARD_WITH_RISK | UNKNOWN | data_unavailable | false | false |  |  |  |  | not_applicable_data_unavailable | data_unavailable | no | no | Ingest missing price/SEC/companyfacts/IR inputs and rerun source_ingestion_mode. |
| PARA | Paramount Global | Turnaround / Distressed / Business-Model Pressure | TURNAROUND / BUSINESS_MODEL_PRESSURE / STANDARD_WITH_RISK | UNKNOWN | data_unavailable | false | false |  |  |  |  | not_applicable_data_unavailable | data_unavailable | no | no | Ingest missing price/SEC/companyfacts/IR inputs and rerun source_ingestion_mode. |

## Top Manual Review Reasons

- `EARNINGS_DATE_UNAVAILABLE`: `13`
- `PERIOD_TYPE_MISMATCH_IGNORED`: `13`
- `TRUE_SOURCE_VALUE_DISAGREEMENT`: `11`
- `SOURCE_FRAME_VARIANT_IGNORED`: `10`
- `FINANCIAL_SANITY_PRICE_TO_FCF_ANOMALY`: `5`
- `TRUE_FINANCIAL_ANOMALY`: `5`
- `GUARD_THRESHOLD_REVIEW`: `1`
- `FCF_UNAVAILABLE_WITHOUT_IR_SUPPORT`: `1`
- `MISSING_CURRENT_PERIOD_KPI_CONTEXT`: `1`
- `MISSING_FCF_SUPPORT_FOR_ACCUMULATE`: `1`

## Data Availability

- `TSM`: Missing CSV price history: outputs/source_inputs/phase12_operating_pilot_050/prices/TSM.csv
- `ASML`: Missing CSV price history: outputs/source_inputs/phase12_operating_pilot_050/prices/ASML.csv
- `RGTI`: Missing CSV price history: outputs/source_inputs/phase12_operating_pilot_050/prices/RGTI.csv
- `IONQ`: Missing CSV price history: outputs/source_inputs/phase12_operating_pilot_050/prices/IONQ.csv
- `QBTS`: Missing CSV price history: outputs/source_inputs/phase12_operating_pilot_050/prices/QBTS.csv
- `QUBT`: Missing CSV price history: outputs/source_inputs/phase12_operating_pilot_050/prices/QUBT.csv
- `SOUN`: Missing CSV price history: outputs/source_inputs/phase12_operating_pilot_050/prices/SOUN.csv
- `BBAI`: Missing CSV price history: outputs/source_inputs/phase12_operating_pilot_050/prices/BBAI.csv
- `RKLB`: Missing CSV price history: outputs/source_inputs/phase12_operating_pilot_050/prices/RKLB.csv
- `ASTS`: Missing CSV price history: outputs/source_inputs/phase12_operating_pilot_050/prices/ASTS.csv
- `ACHR`: Missing CSV price history: outputs/source_inputs/phase12_operating_pilot_050/prices/ACHR.csv
- `JOBY`: Missing CSV price history: outputs/source_inputs/phase12_operating_pilot_050/prices/JOBY.csv
- `RIVN`: Missing CSV price history: outputs/source_inputs/phase12_operating_pilot_050/prices/RIVN.csv
- `LCID`: Missing CSV price history: outputs/source_inputs/phase12_operating_pilot_050/prices/LCID.csv
- `PLUG`: Missing CSV price history: outputs/source_inputs/phase12_operating_pilot_050/prices/PLUG.csv
- `PYPL`: Missing CSV price history: outputs/source_inputs/phase12_operating_pilot_050/prices/PYPL.csv
- `SNAP`: Missing CSV price history: outputs/source_inputs/phase12_operating_pilot_050/prices/SNAP.csv
- `WBA`: Missing CSV price history: outputs/source_inputs/phase12_operating_pilot_050/prices/WBA.csv
- `PARA`: Missing CSV price history: outputs/source_inputs/phase12_operating_pilot_050/prices/PARA.csv
