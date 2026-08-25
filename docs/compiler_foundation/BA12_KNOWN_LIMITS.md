# BA12 Frozen Known Limits and Non-Blockers

Status: `ACCEPTED / FROZEN`

1. The historical Product server remains in the repository as an explicit,
   acknowledgement-gated and loopback-only archive runtime. It is not a
   canonical semantic reader.
2. Foreign Materialbedarf worktrees may drift independently. Room16 Boundary
   Gate v2 proves causal non-interference; Room16 neither mutates nor consumes
   them as authority input.
3. The freeze reuses the already validated R4 WM/COST/ABT live lineage and
   re-verifies the exact signed native bundles. No redundant network fetch is
   required.
4. Release, deployment, publication, member visibility, commerce, payment and
   external communication remain unauthorized.
5. Historical v1 and Authority-v3 artifacts remain available only for archive
   and replay evidence, not as canonical semantic inputs.
6. The outer freeze-handoff manifest contains a noncanonical
   `manifest_sha256` metadata value. Its raw bytes are independently bound by
   `SHA256SUMS.txt`, all ten declared payload hashes are exact, the outer ZIP
   SHA-256 is exact, and the embedded accepted R5 package passes its standalone
   verifier. This evidence-metadata wording defect does not alter accepted
   runtime, source, security or Git identity.

A future material change to the frozen architecture requires a new change or
RFC decision. It does not retroactively reopen BA12.
