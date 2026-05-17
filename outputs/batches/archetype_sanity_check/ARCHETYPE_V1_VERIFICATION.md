# SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL - Archetype-v1 Verification

Batch: `archetype_sanity_check`  
As of: `2026-05-16`  
Status: `verified_archetype_v1`

## Verification Result

`SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL` is now marked as a verified Archetype-v1 guard for Room 16 / Research-Core.

The sanity batch confirms that the archetype behaves generically rather than as an RGTI-specific exception.

## Correct Positive Triggers

The following early-commercial deep-tech names correctly trigger the archetype:

- `RGTI`
- `IONQ`
- `QBTS`

These names combine multiple early-commercial / story-stock risk features such as very low revenue, extreme market-cap-to-revenue ratios, negative operating income, negative free cash flow, vendor-only hard metrics, limited commercial adoption language, derivative/warrant fair-value effects, and missing or incomplete SEC/IR current-period evidence.

## Correct Non-Triggers

The following names do not falsely trigger the deep-tech archetype:

- `GOOGL`: classified as `MEGA_CAP_PLATFORM`
- `SNOW`: classified as `SAAS_CONSUMPTION`
- `MSFT`: classified as `MEGA_CAP_PLATFORM`
- `QCOM`: classified as `SEMICONDUCTOR_AI_INFRA`

`QCOM` remains covered by the existing FCF-support display rule when FCF support is missing; it is not reclassified as speculative deep-tech.

## Operating Behavior

When `SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL` is active:

- status remains `manual_review`
- publishability remains blocked unless SEC/IR evidence and blocking-issue conditions are clean
- external display is `Manual Review / Preliminary Underweight`
- clean Buy / Accumulate remains blocked
- Underweight remains preliminary only
- order / contract / roadmap materiality must cover contract value, delivery or revenue timing, contract value vs market cap, contract value vs annual revenue, recurring vs one-off, commercial vs government/research/prototype, and valuation support

Deep-tech titles are therefore internal-draft / manual-review candidates, not clean publishable reports.

## Freeze Rule

No further guard expansion should be made for this archetype without a real operating false positive or false negative.

Examples of acceptable future change triggers:

- a normal company is incorrectly blocked as `SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL`
- an early-commercial speculative deep-tech / hardware / story-stock company clean-passes when it should not
- a real report shows a material issue not covered by the current v1 guard behavior

Absent such evidence, Archetype-v1 is considered stable.
