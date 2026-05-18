# GitHub Deep Research Roadmap 2026-05-18

## Scope

Deterministic Research Core bleibt Berechnungs- und Validierungsschicht. LLMs interpretieren validierte Pakete; Public Output bleibt promotion-gated.

## P0

- Standard-CI fuer Installation, `compileall` und `pytest` einfuehren.
- Branch Protection, Required Checks, Secret Scanning und Push Protection sind Remote-GitHub-Gates und brauchen Operator-Go im GitHub-UI.

## P1

- Ruff/Coverage-Baseline und spaeter Mypy einfuehren.
- Auditor-Regeln in Registry mit Rule-ID, Severity, Inputs, Tests und Golden Fixtures ueberfuehren.
- Source-date-Resolver als Batch-Preflight staerken, damit Date-/Source-Mismatch nicht zu zufaelligen Failure-Wellen fuehrt.

## P2

- Public-ready strikt trennen: `passed_internal`, `manual_review`, `public_candidate`, `public_final`.
- Outcome-Tracking 5D/10D/20D/60D reifen lassen, bevor Ratings oder Modellregeln veraendert werden.
