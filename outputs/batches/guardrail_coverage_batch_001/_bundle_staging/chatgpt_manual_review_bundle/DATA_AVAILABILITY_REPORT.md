# Data Availability Report - guardrail_coverage_batch_001

- Prompt ticker count claim: `42`
- Enumerated ticker count used: `41`
- Count note: The operator prompt says 42 tickers, but the enumerated universe contains 41 symbols. The batch uses the listed universe only.
- Requested price basis: `latest_available`
- Local broad deterministic source basis used: `2026-05-05`
- Price CSV dir: `outputs/source_inputs/phase12_operating_pilot_050/prices`
- SEC companyfacts dir: `outputs/source_inputs/phase12_real_pilot_030/sec_companyfacts`
- Data unavailable tickers: `19`

## Missing Inputs

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

## Interpretation

- These are provider/input coverage gaps, not report-generation crashes.
- Guardrails were not relaxed and no ticker-specific fallback data was fabricated.
- The affected tickers should be rerun after price, SEC/companyfacts, and IR/source inputs are present for the same source-ingestion lane.
