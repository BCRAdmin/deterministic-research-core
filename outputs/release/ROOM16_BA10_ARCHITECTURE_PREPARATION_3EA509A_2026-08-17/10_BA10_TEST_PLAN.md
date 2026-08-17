# BA10 Test Plan

## Test levels

1. Contract and canonicalization unit tests.
2. Pass/emitter, bridge and bundle integration tests.
3. Shared Python/JavaScript differential conformance.
4. Product dual-read and renderer contract tests.
5. Frozen WM/COST/ABT end-to-end shadow replays.
6. Reproducible evidence-bundle build and independent architecture review.

No new company, report rebuild or model run is required for BA10 validation.

## Mandatory cases

| Test family | Required proof | Pass criterion |
|---|---|---|
| Bundle determinism | two clean builds from identical frozen inputs | manifest, artifacts and ZIP hash identical |
| Bundle tamper | mutate manifest, artifact, dependency and index | exact stable diagnostic; consumption blocked |
| v3 compatibility | original v3 vs compatibility view | byte parity where copied; declared canonical semantic parity where regenerated |
| Python/JS conformance | shared golden corpus in both runtimes | identical canonical bytes, hashes, diagnostics and verdict |
| No-new-facts | inject renderer-only fact/value | `RENDERER_NEW_TRUTH_DETECTED` |
| No-new-claims | inject/rewrite claim | block with exact diagnostic |
| No-new-decisions | change rating/risk/permission | block with exact diagnostic |
| Visible-number lineage | enumerate Markdown/JSON/UI/PDF/DOCX numbers | every factual token maps to compiler display token |
| Render parity | semantic spans, tables, citations and values | zero unexplained mismatch; layout defects separately reported |
| Legacy vs bundle diff | dual-read all current Product surfaces | zero unexplained semantic difference |
| Unsupported version | unknown major/minor/canonicalization | deterministic capability rejection |
| Capability negotiation | exact, superset and missing support | declared decision; missing required capability blocks |
| Missing artifacts | remove every required kind in turn | exact missing-artifact diagnostic |
| Unknown field/enum | additive optional and semantic required values | optional accepted; required blocks |
| Null/missing/numeric | JS safe range, decimals, null, absent, -0 | identical cross-language result |
| Unicode/order | NFC/NFD, German names, set/list order | canonical corpus result identical |
| Compile verdict | blocked and eligible fixtures | blocked can never render; eligible is not publication approval |
| Annotation isolation | let debate text contain number/rating | cannot enter canonical projection or alter verdict |
| Parallel-truth detector | re-enable Product metric/claim rule | `PRODUCT_PARALLEL_TRUTH_DETECTED` |

## Required red/green/reintroduction pattern

For each migrated Product semantic rule:

1. the old defect fixture fails before compiler-owned remediation;
2. the corrected compiler artifact passes;
3. the real frozen candidate passes;
4. reintroducing the defect produces the exact promised diagnostic;
5. WM, COST and ABT show no cross-company regression.

## Frozen canary acceptance

- Input archives and accepted baseline hashes remain byte-identical.
- Legacy output hashes remain unchanged through sidecar and dual-read phases.
- Bundle output is deterministic across two builds.
- Bundle→v3 view matches each accepted v3 input according to the bridge policy.
- Python and JavaScript agree on all three candidates and all negative fixtures.
- Renderers create zero facts, claims and decisions.

Canaries validate architecture; they do not create company-specific rules and
do not authorize publication.

## Baseline guards

Run before and after implementation:

- semantic freeze verifier;
- Foundation and Registry Foundation freeze verifiers;
- full Research tests and lint;
- unskipped Product full verification and type/lint/build gates;
- shared ABI/conformance corpus;
- project-boundary and documents-root hygiene audits;
- clean worktree and pushed commit verification.

Any test that depends on refreshing a timestamp without new evidence is not a
valid quality proof.

## Evidence required from implementation

- exact commands, versions, exit codes and machine-readable results;
- changed-file list and RFC mapping;
- pass/emitter execution records;
- bundle and bridge manifests;
- diagnostic fixture matrix;
- Python/JS differential output;
- Product dual-read diff;
- renderer inventories and visual/text/table parity;
- WM/COST/ABT unchanged hashes;
- deterministic second build;
- separate flags for implementation, cutover, release and publication.

