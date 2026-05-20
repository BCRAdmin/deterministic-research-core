# Operating Status Summary

Current operating status: GREEN internal operating pilot, with QCOM handled through the manual-focus supersession overlay. Public remains Promotion-gated.

What is safe to use:
- Batch004 internal research surfaces for controlled review.
- Passed-sample reports excluding raw QCOM as a passed decision; QCOM must use manual-focus state.
- Manual-review/internal-best artifacts as internal analysis only.
- Room16 dashboard as operator workbench, not unattended public publishing.

What remains blocked:
- Any public release without Promotion Gate and human/operator approval.
- Outcome scoring until local price/benchmark CSVs contain mature target-date closes.
- Manual-review names until direct IR/earnings-release or correctly labeled SEC replacements are landed where required.

Next review dates:
- 1D: 2026-05-18, pending local price availability.
- 5D: 2026-05-22, pending.
- 10D: 2026-06-01, pending.
- 20D: 2026-06-15, pending.
- 60D: 2026-08-12, pending.

Top risks:
- Operators accidentally reading raw Batch004 QCOM as current passed state.
- Direct IR replacements not yet landed for P0 names.
- Outcome pressure before price windows are actually mature.
- Dashboard live state may not always expose every lane, so verifier/package samples remain part of smoke QA.

Next 7-day plan:
- Land P0 Data-Ops replacements: IONQ, NVDA, QBTS, QCOM, RGTI.
- Re-run affected-subset regression after each replacement batch.
- Re-check 1D outcome only after local CSVs include 2026-05-18 for all required tickers and benchmarks.
- Keep Public Gate closed until promotion_status.public_ready=true plus human/operator approval.
- Preserve GOOGL/SNOW Gold-v1 and Deep-Tech manual review regression checks.

QA run summary:
- Research compileall: pass.
- Research pytest: 253 collected tests passed.
- Room16 lint/build/verify/report-machine/manual-review-workbench/review-operations: pass.
- git diff --check in both repos: pass.

Generated at: 2026-05-19T02:28:39Z

QCOM superseded cleanup 2026-05-20:
- Superseded by manual_focus_guardrail_final_check. Do not use for promotion.
- Operator-facing status is `manual_review / Hold Pending FCF Support`.
- QCOM is removed from public/passed bundles and remains only manual-review/focus context.
