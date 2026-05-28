# Quellwert Public Gate Matrix

- Generated at: `2026-05-27T21:53:31+02:00`
- Matrix status: `preview_pass_operator_gated`

| Gate | Status | Evidence | Decision |
|---|---|---|---|
| Public routes reachable | `PASS` | `verify:quellwert-softlaunch-readiness` | Preview route layer ready |
| Public catalog contract | `PASS` | `verify:quellwert-public-catalog-contract` | Catalog structure ready |
| Non-advice copy visible | `PASS` | Public pages and catalog metadata | Required for preview |
| Forbidden trading tokens absent | `PASS` | Catalog verifier + static scan | No Buy/Sell/Kursziel/Modellportfolio language found |
| Hidden review cases hidden | `PASS` | `NVDA`, `MU` return hidden/404 in verifier | No hidden-case leak |
| Robots block indexing | `PASS` | Softlaunch verifier | External indexing remains blocked |
| GOOGL source review | `WARN` | `sourceReview=needs_review` | Keep gate visible; no external go |
| Legal copy finality | `WARN` | Impressum/Datenschutz are preview-gated | Needs operator/legal review |
| Founding Circle offer | `DRAFT` | Offer draft only | Interest/waitlist only, no checkout |
| Payment/checkout | `BLOCKED` | Operator decision | No activation yet |
| External soft launch | `OPERATOR_GATED` | This matrix | Needs explicit operator go |

## Current Gate Verdict

`preview_pass_operator_gated`

The 48h launch pack can proceed to operator review. It does not authorize external public launch, payment, checkout, paid investment-recommendation-like output, or indexing.
