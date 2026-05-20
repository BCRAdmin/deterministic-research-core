# External Analysis Integration Review

Generated: 2026-05-21

Status: `computed`

This review reconciles the older/external Materialbedarf and Elterngeld analysis with the current Utility Websites operating state. The current 2026-05-21 operating state wins over older Deep Research claims, older Obsidian notes, and older utility output artifacts.

## Source Precedence

1. Current 2026-05-21 operator state.
2. Skill-governance docs in `docs/skills` and `docs/memory` as read-only references.
3. Obsidian utility roadmap and reconciliation notes as historical context.
4. Existing utility outputs in `/Users/BjornRosinger/Downloads/Utility webseiten/outputs/utility_websites`.
5. Raw old Deep Research files only if locally available.

## Global Decisions

- Ads remain disabled.
- Paid CMP remains deferred.
- Free Google CMP debugging remains closed.
- Affiliate is readiness-only; no live links without partner data and Operator-Go.
- Elterngeld remains trust/monitor, not a monetization or funnel build.
- External skill patterns remain documentation/reference only; no runtime installation or new rights.

## Materialbedarf Review

| Topic | Decision | Reason | Next action |
|---|---|---|---|
| Ergebnis-UX | `already_done` | Result and PurchasePrep modules were improved. More rewrite work needs event evidence. | Measure result and purchase-intent events. |
| Einkaufsliste | `adopt_now` | Material list clarity supports purchase intent without monetization risk. | Keep list/copy/email/PDF paths measurable. |
| Reserve/Verschnitt | `adopt_now` | Reserve explanation is useful user help and reduces result ambiguity. | Keep explanatory copy, avoid new calculator logic. |
| PDF/Druck/Copy/E-Mail | `already_done` | Prepared as readiness events and utility actions. | Monitor clicks before expanding features. |
| PurchasePrep | `already_done` | Improved and tracking fix for `purchase_prep_copy` is part of current state. | Measure `purchase_prep_expand` and `purchase_prep_copy`. |
| Produktkategorie-Uebergaenge | `adopt_later` | Useful no-ads revenue route, but only as readiness until partner data exists. | Prepare slots and partner shortlist, no live links. |
| Affiliate | `requires_operator_gate` | Potential revenue path, but partner approvals/disclosure/rel attributes are missing. | Partner prep only. |
| AdSense | `reject` | CMP path failed and Ads are frozen. | No AdSense work before threshold. |
| CMP | `outdated` | Free Google CMP path is closed; paid CMP deferred. | No further CMP debugging unless threshold. |
| GSC/CTR | `requires_data` | Allowed only as small data-driven action cuts. | Wait for post-change GSC window. |
| Blog/Content | `requires_data` | Mass content without signals is rejected. | Only content backed by GSC/event evidence. |
| FAQ | `monitor` | User help is fine; FAQ schema is not a primary SEO lever. | Keep helpful FAQ, no schema-chasing. |
| Interne Links | `adopt_later` | Can support UX/SEO if tied to measured paths. | Use only with GSC-backed targets. |
| Mobile UX | `monitor` | Important, but no new broad feature pass without evidence. | Watch engagement/drop-off. |
| Performance/Core Web Vitals | `monitor` | Keep healthy, no new optimization sprint without issue evidence. | Review only if measurements degrade. |

## Elterngeld Review

| Topic | Decision | Reason | Next action |
|---|---|---|---|
| Trust/Quellen | `already_done` | Trust, sources, result copy, FAQ, and meta were improved. | Keep source/date/disclaimer visible. |
| Rechner/Ergebnis | `monitor` | Technically clean; no new calculator work requested. | Monitor GSC and user signals. |
| FAQ | `monitor` | Helpful FAQ is allowed, but not as schema bait. | Edit only if user/GSC data supports. |
| Ratgeber | `requires_data` | No mass guide expansion without post-change evidence. | Wait for GSC. |
| Rueckwirkend beantragen | `adopt_later` | Sensitive topic can be useful, but needs source/legal care and data signal. | Consider only with official-source review. |
| Meta/CTR | `requires_data` | CTR changes need fresh GSC data after prior updates. | Review after waiting window. |
| Disclaimer | `already_done` | Current state includes no legal/tax advice posture. | Keep conservative disclaimer. |
| E-Mail-Opt-in | `reject` | Funnel is too aggressive for current trust/monitor mode. | No opt-in now. |
| AdSense | `reject` | Ads disabled and monetization blocked. | No AdSense work. |
| Funnel | `reject` | Aggressive funnels are outside current Elterngeld mode. | Keep trust/monitor. |
| Rechtliche Sensibilitaet | `monitor` | High-sensitivity content requires careful official-source posture. | Keep no-advice framing. |
| GSC-Waiting-Window | `adopt_now` | Current policy says wait for more data. | Do not rewrite without fresh data. |

## Outcome

The older analysis contains useful UX and revenue-shaping ideas, but only the data-backed, low-risk parts move forward. Monetization claims that depended on Ads, CMP, sticky affiliate CTAs, or funnels are rejected or gated.
