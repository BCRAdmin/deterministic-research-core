# Scope Split - Quellwert/Room16 vs Steuer/Kanzlei Rollforward

- Generated at: `2026-05-27T19:05:00+02:00`
- Source: `/Users/BjornRosinger/Downloads/GETRENNTE_ROADMAP_QUELLWERT_STEUER.md`
- Status: `active_governance`

## Quellwert / Room16 / LIONCOM

Quellwert is the public and revenue-facing research surface. Room16 remains the internal evidence engine.

Allowed next work:

- Build the 48h Quellwert Launch Pack.
- Verify public routes: landing, analyses, methodology, archive, verifier, legal pages, contact.
- Draft the `Founding Circle` offer as waitlist/interest, not aggressive financial advertising.
- Review/neutralize public sample analyses.
- Add/verify public gate matrix, no-trading-token checks, no-advice-copy checks, visual smoke, operator checklist.

Blocked:

- Personalised investment advice.
- Buy/Sell-now language.
- Price targets.
- Model portfolios.
- Promised returns.
- Public/member/financial-advice release from Room16 outcome monitoring alone.
- Guard/rating/report/calibration changes from 1D/5D alone.
- Payment/checkout/production without operator and compliance gate.
- KAP, DATEV, ERL workbook, or Kanzlei tax workflow work.

## Steuer / Kanzlei Rollforward Assist

Steuer/Kanzlei Rollforward is the Excel-first tax-office MVP. It must stay separate from Quellwert and Room16.

Definition: this tax rail runs without AI/LLM in the product workflow. It is local, deterministic, Excel-first tooling for workbook inspection, rollforward, KAP mapping, writeback on copies, status sheets, and integrity checks. `Vega` may appear only as the external project/coding/governance assistant that writes code, checks artifacts, and updates memory; it is not a runtime module, tax logic, or autonomous tax decision-maker.

Allowed next work:

- Check whether `fixtures/anonymized/templates/ERL_2024.xlsx` exists.
- If missing, create or maintain blocked/pending artifacts only.
- If present, run SHA/manifest, privacy/anonymization, workbook inspection, real-template structure audit, KAP mapping calibration, real-fixture dry-run on a copy, Excel Integrity Guard, and operator runbook.

Blocked:

- UI expansion.
- OCR.
- DATEV integration.
- Cloud LLM/provider processing.
- Local LLMs for tax decisions.
- New tax domains such as account statements, pensions, special expenses, or donations unless explicitly scoped.
- Real client/person data in repo or chat.
- Final tax decisions without human professional review.
- Writing into original Excel files.
- Quellwert, Founding Circle, equities reports, Room16 outcomes, or investment-research launch logic.
- AI/LLM-based tax processing or tax decisions.

## Shared Patterns Only

Allowed shared patterns:

- SHA/file manifests.
- Source/evidence registries.
- Verifier discipline.
- Operator gates.
- Runbooks.
- Read-only-first workflow.
- Status semantics such as `PASS`, `WARN`, `BLOCKED`, `OPERATOR_GATED`, `PUBLIC_READY=false`.

Not allowed:

- Sharing domain evidence.
- Sharing launch criteria.
- Treating green local verifier status as public/production/payment/auth readiness.
- Using Room16 outcome signals as Steuer quality signals.
- Using KAP mapping status as Quellwert launch maturity.
- Treating Vega/Codex governance work as part of the tax product runtime.
