# Room16 Analytical Core v0.2

## Purpose

Room16 uses one deterministic analytical core for internal, free-public and
paid reports. The publication tier may change depth and review requirements;
it must not change the underlying facts or calculations.

The core remains a research screen, not a personalized recommendation. It
fails closed when an instrument, period, share basis or source cannot be
verified.

## Long-term conclusion and timing

The long-term company conclusion uses:

1. measured fundamentals;
2. calibrated valuation evidence when available; and
3. measured financial-risk downside.

Technical indicators are a separate timing overlay. Their score is reported,
but it is excluded from the long-term composite score and cannot create or
block a company rating. An unadjusted or provider-default price series is
explicitly provisional. A corporate-action-adjusted series is measured; a
post-corporate-action-only series remains limited to its shorter history.

## Valuation sensitivity

The current valuation layer is a standardized five-year equity-DCF
sensitivity. It uses operating cash flow minus capital expenditure as an
equity cash-flow proxy. It is not an FCFF enterprise valuation and is not a
company forecast.

Capital expenditure has one canonical cross-jurisdiction meaning: a positive
cash-outflow magnitude. Providers that publish cash-flow outflows with a
negative accounting sign are normalized before reconciliation, evidence
generation and FCF calculation. The original filing remains the source of
record; Room16 must not expose one sign in the report while calculating with
another.

The deterministic scenarios are:

| Scenario | FCF-growth anchor | Discount rate | Terminal growth |
| --- | --- | ---: | ---: |
| Bear | capped reported revenue growth minus 10 percentage points | 12% | 1% |
| Base | reported revenue growth capped to -5% through 15% | 10% | 2% |
| Bull | capped base growth plus 10 percentage points | 8% | 3% |

Room16 also solves the five-year FCF growth implied by the current equity
value under the base discount and terminal assumptions. Every assumption and
result is present in the evidence ledger.

Status rules:

- `scenario_measured`: positive FCF and a verified listed/economic share basis;
- `illustrative_only`: a scenario can be calculated, but the current value or
  per-share comparison relies on unverified cross-class price equivalence;
- `not_measured`: no positive FCF anchor or no usable value basis.

The sensitivity does not produce an automatic valuation score until a
separately validated calibration set supports that use. It may explain market
expectations and scenario dependence, but it must not be described as precise
fair value.

The admission and maturity rules for that future calibration set are defined
in [`VALUATION_CALIBRATION_V1.md`](VALUATION_CALIBRATION_V1.md). The readiness
runner is shadow-only and cannot activate a valuation score.

## Financial-risk screen

The numeric screen uses only reproducible financial-statement inputs:

| Component | Weight | Examples of inputs |
| --- | ---: | --- |
| Financial resilience | 35% | equity, current ratio, debt/equity, interest coverage, net debt/revenue |
| Cash-flow durability | 30% | FCF sign, FCF margin, FCF conversion |
| Dilution and SBC | 20% | diluted-share change, SBC/revenue |
| Capital-allocation coverage | 15% | shareholder distributions compared with FCF |

The 0–100 number is a transparent policy screen, not an empirical probability
of loss. Missing inputs reduce coverage. An incomplete screen can identify
downside, but it must never be labelled low risk. The count of issuer risk
headings does not change the score.

SEC or issuer risk disclosures are categorized for reviewer coverage. Their
competitive, regulatory, governance, customer, cyber and execution severity
remains a mandatory human-review question.

Financial risk can reduce the long-term composite score. It cannot add a
positive rating bonus.

## Rating contract

- Missing core fundamentals produce a neutral safety fallback, not a positive
  or negative company call.
- Constructive fundamentals without calibrated valuation support remain Hold.
- A non-neutral constructive rating requires both constructive fundamentals
  and calibrated valuation evidence.
- An Underweight conclusion requires negative fundamentals corroborated by
  measured valuation or financial-risk downside.
- Validation and publication quality can block release, but they cannot rewrite
  the company conclusion.

## Evidence and review

DCF outputs, DCF policy assumptions, reverse-DCF growth, financial-risk score
and financial-input coverage are deterministic evidence items. The Markdown
auditor maps each number to its own metric; DCF discount or terminal assumptions
must not be mistaken for reported FCF, price or growth facts.

Human review remains bound to the exact report, fact ledger, quality report,
PDF and DOCX hashes. A later edit invalidates that review.

For SEC Item 2.02 filings, Room16 selects the primary results exhibit from the
complete visible link description per target document. Supplemental exhibits
remain secondary even when SEC inline markup splits their labels across
several anchors. An unresolved tie still fails closed.

An Item 2.02 exhibit may bind to either a matching quarterly CompanyFacts
period or an explicitly labelled full fiscal year covered by the same current
10-K accession. Guidance-only full-year wording is not treated as a result
period. Current OCF and capex commentary must use the newest exact period pair,
including annual facts when the latest fiscal year is newer than interim data.

The report auditor distinguishes an issuer guidance claim from an explicit
disclaimer such as “not management guidance”. A disclaimer can clear only its
own sentence fragment; it cannot mask a separate unsupported forecast in the
same report.

## Current limits

- Nasdaq public OHLCV does not establish corporate-action adjustment by
  itself; technical conclusions therefore remain provisional unless an
  adjusted provider or verified post-action series is available.
- The DCF is sensitivity evidence, not calibrated valuation alpha.
- Qualitative business-risk severity is not automatically scored.
- International jurisdictions require their own official-source adapters.
- No report becomes public or paid solely because the deterministic bundle is
  valid; publication and human-review gates still apply.
