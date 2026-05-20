# Utility Websites 14-Day GSC / Event Review

Generated: 2026-05-21T00:14:40+02:00

Review status: `pending_not_mature`

Decision: `continue_monitoring`

Secondary decision: `no_action`

## Readiness

The requested 14-day review window is not locally data-complete. Existing operating artifacts set the better 14-day review date to 2026-06-01. The local workspace contains GSC baselines ending 2026-05-14 and event implementation verification, but no fresh GSC export or Plausible event-count export for the requested 14-day outcome window.

## Data Availability

| Metric | Data available | Value | Source / note |
|---|---:|---|---|
| GSC impressions | no | unavailable for outcome window | Only baseline window 2026-04-20 to 2026-05-14 is local. |
| GSC clicks | no | unavailable for outcome window | Only baseline window 2026-04-20 to 2026-05-14 is local. |
| GSC CTR | no | unavailable for outcome window | Only baseline window 2026-04-20 to 2026-05-14 is local. |
| GSC average position | no | unavailable for outcome window | Only baseline window 2026-04-20 to 2026-05-14 is local. |
| `calculator_submit` | no | unavailable | Event implemented/tested; live Plausible counts unavailable. |
| `purchase_prep_expand` | no | unavailable | Event implemented/tested; live Plausible counts unavailable. |
| `purchase_prep_copy` | no | unavailable | Event implemented/tested; live Plausible counts unavailable. |
| `result_pdf_click` | no | unavailable | Event implemented/tested; live Plausible counts unavailable. |
| `copy_material_list` | no | unavailable | Event implemented/tested; live Plausible counts unavailable. |
| `email_draft_click` | no | unavailable | Event implemented; not suitable for forced local E2E due external mailto side effects. |
| `outbound_product_category_click_placeholder` | no | unavailable | Placeholder path only; live counts unavailable. |
| Affiliate partner prep status | yes | readiness_only | Applications not started; no live links allowed. |
| CMP remains deferred | yes | true | CMP branch closed; paid CMP threshold not met locally. |
| Ads remain disabled | yes | true | AdSense freeze remains active. |

## Baseline Reference

These are not 14-day outcome values; they are the last local GSC baseline values.

| Site | Baseline window | Clicks | Impressions | CTR | Average position |
|---|---|---:|---:|---:|---:|
| materialbedarf-rechner.de | 2026-04-20 to 2026-05-14 | 25 | 1,770 | 1.4% | 21.1 |
| mein-elterngeldrechner.de | 2026-04-20 to 2026-05-14 | 8 | 2,130 | 0.4% | 19.0 |

## Decision Check

| Possible decision | Result | Reason |
|---|---|---|
| `continue_monitoring` | yes | 14-day data is not available/mature. |
| `small_ctr_adjustment` | no | No fresh GSC export for the outcome window. |
| `materialbedarf_result_ux_adjustment` | no | No live event counts showing drop-off. |
| `affiliate_partner_application_ready` | no | Partner prep exists, but event thresholds and partner data are missing. |
| `no_action` | yes | No data-backed action is allowed now. |

## Guardrails Confirmed

- No Ads.
- No paid CMP.
- No affiliate live links.
- No large rewrites.
- No new roadmap cuts without data.

## Next Allowed Step

Run the same review after 2026-06-01 with:

- GSC page/query export for Materialbedarf and Elterngeld.
- Plausible event counts for Materialbedarf readiness events.
- Affiliate partner prep status.
- CMP/Ads freeze confirmation.
