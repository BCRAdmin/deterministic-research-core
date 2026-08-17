# BA10 Definition of Done

BA10 is complete only when every mandatory statement below is evidenced by
machine-readable artifacts and independently reviewable output. A green test
subset or one migrated renderer is not completion.

## Architecture and ABI

- `one_canonical_compiler_bundle = true`
- `compiler_artifact_bundle_contract = room16.compiler_artifact_bundle@1`
- `research_is_only_semantic_authority = true`
- `product_parallel_truth = 0`
- `foundation_unchanged = true`
- `registry_foundation_unchanged = true`
- `semantic_wave_ba0_ba9_unchanged = true`
- `authority_bundle_v3_contract_unchanged = true`
- `compiler_mode_truthful = true`
- `source_native_fact_generation = false`

## Bundle integrity

- every required L0–L10 artifact is embedded or content-addressed;
- registry, pass, IR and implementation locks verify;
- manifest and artifact hashing is deterministic;
- missing, unknown-required, tampered or unsupported inputs fail closed;
- compile verdict and diagnostic release effects cannot be overridden;
- two clean bundle builds are byte-identical.

## Authority-v3 bridge

- `authority_bundle_v3_bridge_verified = true`
- copied artifacts prove byte parity;
- generated compatibility fields prove canonical semantic parity and lineage;
- bridge cycle/origin guards pass;
- current legacy consumers accept the compatibility view without semantic
  difference.

## Product and renderers

- Product performs only generic ABI/hash/capability verification and
  operational governance;
- all canonical output surfaces consume the verified bundle or its declared
  projection;
- `renderer_generated_facts = 0`
- `renderer_generated_claims = 0`
- `renderer_generated_decisions = 0`
- every visible factual number has compiler lineage;
- renderer diagnostics cannot suppress compiler diagnostics;
- PDF, DOCX, Markdown, JSON, API and UI satisfy the Renderer Contract;
- TradingAgents/LLM interpretation remains isolated non-authoritative
  annotation with zero verdict, rating, permission and release effect.

## Conformance and migration

- `python_js_conformance = pass`
- shared Research-owned corpus covers all mandatory positive and negative
  cases;
- legacy-vs-bundle semantic diff is zero or each non-semantic difference is
  explicitly classified and accepted;
- every retired Product semantic rule has a compiler-owned replacement and a
  negative reintroduction fixture;
- rollback to the previous proven phase remains possible until final operator
  cutover approval.

## Canaries and regressions

- `wm_canary = pass`
- `cost_canary = pass`
- `abt_canary = pass`
- frozen input and accepted archive hashes are unchanged;
- full Research and Product regression gates pass without skipped required
  checks;
- no company-specific code or rule exists.

## Required status at BA10 completion

- `ba10_implemented = true`
- `renderer_cutover` reflects the actually authorized migration phase; it may
  not be inferred from implementation completion.
- `release_ready = false`
- `publication_allowed = false`
- `ba11_authorized = false`
- `ba12_authorized = false`

BA10 completion makes the productization boundary technically reliable. It
does not qualify archetypes, replace human/legal/editorial review or authorize
selling/publishing a report.

