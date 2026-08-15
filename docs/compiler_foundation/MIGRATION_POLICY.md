# Compiler Foundation Migration Policy

## RFC-0002 Semantic Spine

Authority Bundle v3 darf während der Strangler-Migration ausschließlich über
benannte und hashgebundene Compatibility Source Inputs konsumiert werden. Ein
Compatibility Adapter darf keine fachliche Parallelwahrheit erzeugen. Nach dem
Parse-Pass konsumieren alle nachfolgenden Compiler-Pässe ausschließlich
vorgelagerte IRs.

Der alte BA4–BA9-Shadowpfad bleibt als reproduzierbare Migration Scaffolding
erhalten, ist aber kein Completion-Gate mehr. Completion wird nur durch den
RFC-0002-L10-Verification-Pass und berechnete Cross-Company-Gates bestimmt.

BA10, Renderer-Cutover und Publication bleiben bis zu einem expliziten
unabhängigen Architektur-PASS gesperrt.

## Registry Foundation 1.1.0

Registry Foundation 1.1.0 ist ein additiver Strangler-Layer oberhalb der
unveränderten Foundation 1.0.0. Legacy-IDs werden nicht still umbenannt oder
gelöscht, sondern eindeutig an generische Definitionen gebunden, als Alias bzw.
Instanz klassifiziert oder fail closed quarantänisiert. Product darf diese
Zuordnung weder bearbeiten noch ergänzen.

Ab dem Freeze `room16-registry-foundation-v1.1.0` gilt:

- neue Semantik nur über versionierte Research-Contracts;
- keine Ticker-, Firmen- oder Canary-spezifischen Definitionen;
- keine Promotion unbekannter oder quarantänisierter IDs ohne RFC und
  Negativfixture;
- keine Formel ohne registrierte Operandrollen, Ergebnisdimension und
  Reproduktionsprüfung;
- keine Änderung der neun BA4–BA9-Pass-Contracts ohne RFC;
- keine Authority-Bundle-v4-Erzeugung in dieser Welle;
- BA10 erst nach separater Operatorfreigabe.

## Purpose

This policy protects Compiler Foundation v1 while BA3–BA12 replace legacy
pipeline behavior through a shadow/strangler migration.

## Normal development

Normal development occurs above the Foundation. A new compiler wave must:

1. consume versioned Foundation contracts;
2. define its own input, output, side-effect, determinism, cache, replay and
   failure contracts;
3. run in shadow mode before gaining authority;
4. preserve Authority Bundle v3 and legacy output until an explicit ABI migration;
5. use frozen source inputs for WM/COST/ABT differential tests;
6. fail closed for unknown IDs, unsupported versions, tamper and incomplete input;
7. remain company-agnostic.

## RFC boundary

An RFC is mandatory when a proposed change affects any frozen layer,
ownership, registry, pass, IR or ABI contract. The RFC must include:

- problem and general root cause;
- alternatives and why normal BA3+ extension is insufficient;
- compatibility classification and proposed version bump;
- affected hashes, mirrors, caches and replay records;
- migration and rollback procedure;
- positive, negative, tamper, versioning, unknown-ID, order, skip, replay and
  cross-language tests where applicable;
- WM/COST/ABT differential results and independent-review trigger decision.

No RFC is approved merely because one company does not fit. A company may
expose a missing general contract, but the resulting proposal must be valid
without naming that company.

## ABI migration

Authority Bundle v3 remains the transition ABI. A successor requires an
approved RFC, dual-read compatibility window, deterministic v3-to-successor
migration, Product consumer verification, full canary replay and explicit
operator acceptance. There is no silent in-place reinterpretation of v3.

## Registry migration

Research remains the only registry authority. Additive entries require the
compatibility rules of the active Registry Envelope. Removing, renaming or
semantically changing an ID is breaking and requires RFC approval. Product
mirrors are generated or copied from Research and accepted only after exact
hash verification.

## Completion rule

A semantic compiler wave may become authoritative only when shadow replay,
legacy parity, contract tests, canary regression and required human review all
pass on the same version lock. Passing a single company is insufficient.
