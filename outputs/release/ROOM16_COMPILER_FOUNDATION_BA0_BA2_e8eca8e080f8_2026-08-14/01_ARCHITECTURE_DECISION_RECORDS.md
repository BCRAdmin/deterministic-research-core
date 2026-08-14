
# Architecture Decision Records

## ADR-001 — Shadow Strangler statt Rewrite

Der Legacy-Pfad bleibt während BA0-BA2 Ausführungsautorität. Der neue Kernel beobachtet nur
eingefrorene Artefakte. Es besteht keine Aufrufkante vom Kernel zum Legacy-Orchestrator.

## ADR-002 — Eine fachliche Wahrheit

Sources, Facts, Metrics, Evidence, Claims, Decisions, Diagnostics und Verdicts gehören
ausschließlich Research. Product darf diese Semantik weder ergänzen noch überschreiben.

## ADR-003 — Content-addressed Compiler Contracts

IR, Registries, Cache und Replay werden mit kanonischem UTF-8-JSON und SHA-256 gebunden.
Non-finite Zahlen, unbekannte Felder, unbekannte IDs und Major-Versionen scheitern geschlossen.

## ADR-004 — Diagnostics getrennt von Release-Wirkung

Fachliche Severity ist nicht mit der Release-Wirkung gekoppelt. Ein informativer Fehler kann
einen Release blockieren; ein kritischer Hinweis kann fachlich kritisch und dennoch nicht
automatisch blockierend sein. Der Verdict wird ausschließlich aus expliziten Release-Effekten
abgeleitet.
