# Ingest Summary - Getrennte Roadmap Quellwert/Steuer

- Generated at: `2026-05-27T19:05:00+02:00`
- Source file: `/Users/BjornRosinger/Downloads/GETRENNTE_ROADMAP_QUELLWERT_STEUER.md`
- Source type: `roadmap_prompt_pack`
- Status: `ingested_as_scope_split`
- Affected tracks: `Quellwert/Room16/LIONCOM`, `Steuer/Kanzlei Rollforward Assist`

## Decision

The source is accepted as project-governance truth: Quellwert/Room16 and Steuer/Kanzlei Rollforward are two separate product tracks. They may share quality patterns, but must not share domain artifacts, claims, source data, launch criteria, or next-step execution.

Important correction: `Vega` is not part of the tax product, tax runtime, or tax decision logic. In this context, Vega only means the external project/coding/governance assistant role that helps organize implementation and verification. The Steuer/Kanzlei Rollforward product itself remains local, deterministic, Excel-first, and non-AI/non-LLM.

## Stable Findings

- Quellwert/Room16 is the launch/revenue track: public non-advice research surface, Founding Circle, custom dossiers, public gate, outcome monitoring.
- Steuer/Kanzlei Rollforward is the Excel-first tax-office track: real-template fixture, KAP mapping, Excel integrity, dry-run, controlled pilot.
- Both tracks may reuse SHA manifests, source/evidence registries, verifier discipline, runbooks, operator gates, and read-only-first policies.
- Quellwert must not absorb KAP/DATEV/ERL tax logic.
- Steuer must not absorb Room16 equities research, Founding Circle, investment research signals, or Quellwert launch criteria.
- Verified local blocker: `/Users/BjornRosinger/Documents/New project/steuerbuero-rollforward-assist/fixtures/anonymized/templates/ERL_2024.xlsx` is currently missing.

## Operator Implication

Next work should happen in separate sessions:

1. Quellwert launch/revenue session: execute the 48h Launch Pack Sprint.
2. Steuer Rollforward session: if `ERL_2024.xlsx` is missing, create/maintain a Blocked/Pending package only; if present, run real-template intake and audit before any feature expansion. Do not introduce AI/LLM tax processing.
