# Scientific transition gates · IDEA LAB

Status: PARTIAL. This document tracks independent institutional functionality without importing any earlier source code, state, history or attribution.

| Research capability | Institutional evidence | Current status | Blocking condition |
| --- | --- | --- | --- |
| Static demonstration and navigation | Versioned client application | DEMONSTRATION | Production parity unverified |
| Synthetic paper competition | 23 independent example rule sets | DEMONSTRATION | Not certified reproductions |
| Order simulation, cash and fee logic | Existing illustrative close-mark engine plus separate next-open OHLC synthetic cash/share ledger, commissions and slippage | EXPERIMENTAL | Independent open candles, corporate actions, market hours and verified fills absent; classification still uses previous-close illustrative engine |
| Statistical forecasting | Locally fitted linear and logistic estimators with forward-only tests | EXPERIMENTAL | Only artificial observations; no financial OOS evaluation |
| Larger neural and temporal model families | None independently reimplemented | BLOCKED | Reproducible datasets, computation and evaluation protocol |
| Parameter-search and evolutionary methods | Fixed example weights only | BLOCKED | Real optimizers and untouched test periods |
| Market data and corporate actions | No externally connected source | BLOCKED | License, availability timestamps and split/dividend policy |
| Capital allocation and drawdown-aware families | Demonstration rules | EXPERIMENTAL | Parameters and validation not independently established |
| Company research and scenarios | 25 public issuer identities, eight SEC indexes, one independently sourced dated MSFT EPS–PER exploratory screen and six fictitious demonstrations | PARTIAL | No validated DCF, current-price feed, corporate action handling or approved forecasts; historic MSFT close is not live |
| Historical orders and performance | No transferred observations | EXCLUDED | Reproduction, rights and attribution reviews |
| Scheduled scientific operation | Static-page CI and publication workflow only | PARTIAL | Independent institutional data and persistence |
| Source quality, privacy and identity gates | Allowlisted static build and institutional author checks | PARTIAL | External cross-correlation review not certifiable automatically |

## Mandatory evidence for a production claim

Every dataset requires identifier, permitted usage, source URI, license or terms, observation interval, received-at time, exchange calendar, currency, corporate-action adjustments, immutability/revision history and a reconciliation status. Never silently interpolate missing historical prices or create fills from absent quotes.

Every trained strategy requires a frozen specification, point-in-time universe, chronological split, training-only preprocessing, training and evaluation dates, seeds, versioned dependencies, fee and slippage assumptions, return attribution, missing-data and execution policies, a prospective signal ledger and untouched out-of-sample evaluation.

A green website deployment demonstrates delivery and elementary integrity checks; it never demonstrates profitable, accurate or scientifically superior strategies.

## Publication boundary

A: Verifiable public facts that may legally be republished and have no significant attribution risk.

B: Independent calculations reproduced from legitimately accessible inputs with new methods and documented lineage.

C: Private financial records, licensed but non-redistributable materials, unidentified provenance, historical author metadata or highly linkable outputs. Class C stays outside this repository and its commit history.

Do not ingest external project URLs, import Git histories, push unknown spreadsheets, automatically enable strategies to trade, or introduce paid data services. Review similarity and cross-project attribution separately before any release containing historical facts. Absolute unlinkability cannot be guaranteed.


## Incremental execution safeguards

The independently implemented next-open test harness is not yet the source of displayed competition returns. For a hypothetical signal computed after session D closes, it reads only closes through D for decisions and uses the next artificial OHLC opening price as the earliest execution reference. It records fills, positions, cash, explicit notional fees, assumed spread/slippage and the closing equity. Invalid, missing, misaligned or inconsistent bars cause failure, rather than forward-filling. Synthetic opens were algorithmically derived from synthetic closes: this protects timing semantics for testing, not market validity.

Eight independently identified US registrants link only to official SEC filing indexes. No real-time quotes, filings, corporate financial figures or investment forecasts have been imported from those pages, and SEC CIK confirmation does not constitute fundamental-analysis completion. Non-US and unverified entities retain missing source status.


## First independently sourced exploratory issuer screen

An example for Microsoft uses the FY2026 annual report's adjusted diluted EPS (USD 17.28), the FY2027 first-quarter investor announcement and an explicitly dated 2026-10-30 closing price of USD 521.91 from a publicly accessible historical-prices page. Its sources are embedded as absolute, independently reviewed URLs. There is no imported investment report, portfolio or account metadata.

It uses an **assumed**, not predicted or company-guided, five-year adjusted-EPS growth rate of 7%/13%/18% for bear/base/bull and a terminal P/E of 20×/27×/34×. The formula is EPS × (1+g)^5 × terminal P/E; price-only annualized growth compares scenario value against the dated close. The entry threshold for a 15% annual return divides the base case by (1.15)^5. The screen has the hardcoded status EXPLORATORY_NOT_RATIFIED and lacks a full DCF, 5 quality gates, reinvestment/lease normalization, equity dilution review, dividend attribution and corporate action policy. It must never be labeled the canonical company valuation. Fresh company filings or spot prices do not automatically change it.


## Public feature-equivalence verification — October 2026

This institutionally developed interface has three distinct functional surfaces: (1) sortable synthetic paper competition, (2) source-gated issuer research, and (3) separated method catalogue and unavailable historical campaigns. All clickable competition rows open accessible algorithm dossiers with synthetic activity, exposure, latest artificial-session return, cumulative result, 5/21/63-session comparisons (missing windows remain N/D), volatility, drawdown, Sharpe and NAV visualization. The research table allows header sorting across eleven decision columns, name/ticker search, keyboard row opening, result count and CSV export. Missing corporate evidence is never presented as zero.

**Not yet equivalent to a prospective production quantitative service:** no real provider OHLC freshness report, no verified natural-run GitHub Actions chain, no scheduled model training or state persistence, no independently migrated individual strategy rules, no verifiable 503-member market universe, no real open orders or positions, no adjusted portfolio histories, and no externally approved public investment reports. The institution displays a fail-closed "source unavailable" state rather than synthesizing healthy runtime telemetry. The separate next-open paper harness remains experimental and is not silently substituted into the earlier 23-method ranking.

Public issuer counts reflect identified companies, not approved dossiers. A preliminary EPS sensitivity is not a full valuation. Public feature parity does not justify importing private notes or execution journals, and it does not prove identity unlinkability.
