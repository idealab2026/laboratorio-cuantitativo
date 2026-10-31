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
| Market data and corporate actions | Daily ECB EUR/USD reference observations with source digest and UTC provenance; no stock OHLC | PARTIAL | ECB fixing is not executable, no equity feed or corporate-action adjustments |
| Capital allocation and drawdown-aware families | Demonstration rules | EXPERIMENTAL | Parameters and validation not independently established |
| Company research and scenarios | 25 public issuer identities, eight SEC indexes, one independently sourced dated MSFT EPS–PER exploratory screen and six fictitious demonstrations | PARTIAL | No validated DCF, current-price feed, corporate action handling or approved forecasts; historic MSFT close is not live |
| Historical orders and performance | No transferred observations | EXCLUDED | Reproduction, rights and attribution reviews |
| Scheduled scientific operation | Separate institutional weekday forecast-ledger persistence plus source-validated ECB publication | EXPERIMENTAL | Await first successful scheduled write and public release; no equity forecasts, broker ledger or stock OHLC |
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


## ECB official-source data pilot

The institutional CI captures daily ECB USD-per-EUR reference fixings (EXR/D.USD.EUR.SP00.A), retaining a raw-response SHA-256 digest, UTC retrieval timestamp, source URL, exact numeric literals and dated observations. It rejects missing or stale dates, inconsistent dimensions, weekends, duplicates and implausible values. Statistics are reused with the explicit attribution **Source: ECB statistics** and the ECB published reuse policy. The ECB Pages scheduled action is weekdays 18:25 UTC, but a declared schedule does not prove any future successful execution.

These are **statistical reference observations**, not transaction prices, corporate-action-adjusted equity data, broker marks, executable opening prices or paper-order fills. The daily fixing feed is kept separate from all 23 synthetic equity strategies. No historical private data, source projects, broker positions or investment dossiers are copied. Errors prevent deployment rather than replace the data with invented observations.


## Source-gated prospective research journal

The institutional journal started **without historical events**. A real first run on 2026-10-31 stored an issued signal referring to the 2026-10-30 ECB fixing. It exposed an input-order defect: the two final observations had been reversed by the prototype forecast function. The original event has been retained, explicitly INVALIDATED by a hash-linked additional event, and excluded from all accuracy scoring. The forecasting input order has been corrected and invariant tests now require the unchanged baseline to equal the current observed fixing. No valid prospective outcome has been scored yet. After a subsequent distinct official fixing, the machine adds a separate outcome event referring to the original signal hash. Only then does a forecast become scoreable. Rules are fixed one-step baselines (no-change, momentum and reversal), and errors are measured as absolute USD/EUR deviations. They are not simulated profit, tradable fills, or investment recommendations. The 23 existing equity paper strategies remain entirely synthetic.

The journal checks chronological order, unique fixing dates, source digests, an event hash chain and model-score reconciliation. Failed downloads, missing source windows, invalid rates, branch restrictions or insufficient GitHub token permissions must stop the update without inventing observations. The expected schedule is 17:40 UTC on weekdays for persistence and 18:25 UTC for Pages; GitHub scheduling can be delayed or skipped. A push-triggered institutional ledger write has succeeded; natural weekday scheduled persistence and subsequent-scoring runs still require independent verification. A hash chain only provides tamper evidence anchored by trusted Git history; an authorized complete rewrite of that history remains possible.


## SEC filing-index collector: explicitly non-price evidence

A separate institutional EDGAR collector is configured for eight currently CIK-verified issuers, at most one SEC submissions API call per issuer with 0.4 seconds between requests, below the 10-requests/second fair-access guidance. The declared user agent identifies the IDEA LAB institutional GitHub identity and public issue-tracker contact. The collector rejects ticker/CIK mismatches, source redirects, missing 10-K/10-Q evidence, malformed accession numbers, unsafe primary-document paths, future filing dates, duplicate accessions and partial results. Only selected SEC filing metadata and raw payload SHA-256 are stored, not financial claims, trading account or private research files. The initial public data class is **not_collected**, never simulated as live. After a first complete live run, the state may be **verified_filings**, with up to twelve latest 10-K/10-Q/8-K records per issuer and exact source links. The daily cron or initial bootstrap must be independently checked before claiming delivery.

SEC filing metadata does not imply approved valuation, next earnings calendar, adjusted earnings, or automatic synchronization of older private research. Company XBRL facts require subsequent point-in-time, period/unit-aware extraction and issuer-specific accounting reconciliation. GitHub actions for this collector have only content-write permission. GitHub-token commits may not cause a Pages push event; the separate scheduled Pages build will eventually include the persisted snapshot when both workflows succeed.


### Observed SEC access block (2026-10-31)

The first actual institution-only SEC EDGAR submissions retrieval from a hosted GitHub runner failed with HTTP **403 Forbidden**. No issuer result was stored: the public source status remains `not_collected` and no fake filings are shown. The weekday SEC job has been **disabled**, retaining only an explicit manual invocation. Further attempts require a monitored institutional contact in a GitHub Actions secret `SEC_CONTACT_EMAIL`; the collector rejects absent, malformed and no-reply addresses, and the secret is never committed. Such a contact does not guarantee network permission or circumvent SEC fair-access controls. The separate public site, ECB data and prospectively audited research journal are not dependent on this source. This is an operational blocker, not an implemented live SEC collection.


## ECB AAA euro 10-year yield reference for future EUR valuation research

The independent macro section now includes the ECB's public yield-curve key `YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y`, a modelled AAA euro sovereign zero-coupon 10-year spot yield in percentage per annum with continuous compounding. The original CSV source, observation date, unit, raw-response SHA-256 and receipt timestamp are retained. The static build fails closed on bad dimensions or out-of-window fixings; a successful build attests only to the observed macro reference data, not to a tradeable bond yield or financial performance. No USD-denominated issuer receives this rate as a default WACC or risk-free assumption and no existing company screens are recomputed.

## Independently implemented technical signals and paper accounting (2026-10-31)

Nine labelled research methods now have executable close-only signal functions: a buy-and-hold baseline, a 20-session moving average, fixed EMA/RSI, frozen genetic EMA/RSI parameters, MACD, RSI reversal, Bollinger, and two long breakout horizons. The institutional synthetic sandbox now maintains separate portfolios with immutable configuration, a synchronized OHLC contract, queued close-date signals, next-session open model fills, fees and slippage, corporate-action bookkeeping, a first-touch stop assumption and an inspectable NAV/event ledger. Source data are explicitly generated and the replay is **not** forward paper trading. Tests cover historical revision, idempotence, missing decisions, next-open timing, cash integrity, and portfolio isolation.

**Feature-equality matrix, public release gate:**

| Capability | Proven at this release | Still required for operational parity |
| --- | --- | --- |
| Close-only technical decisions | Nine independently implemented rules on artificial bars | Precise regression comparisons across all target universes, including different market calendars |
| Execution model | Synthetic next-open fills, commissions, slippage, cash, splits and dividends | Independent persistent execution with actual legally reusable OHLC, timestamps, and portfolio reconciliations |
| Competing strategies | Separate standalone nine-policy synthetic accounting; earlier 23 synthetic dashboard methods remain separate | Reconcile algorithm identities, versions, universes, schedules, activity, allocation and comparable actual returns; no silent merger |
| Model classes | Simple real fitted forecasting algorithms trained exclusively on synthetic input | Verified point-in-time training, model registry, walk-forward evaluation and prospective equity predictions |
| Fundamental theses | Issuer identity catalog and limited exploratory screening | Source-backed issuer filings, primary-statement normalization, per-company approved valuation scenarios and recurring updates |
| Risk and history | Synthetic drawdown, model fees, source checks | Session-by-session immutable real feed snapshots, full drawdown attribution and verified historical continuity |
| Independent automation | ECB reference ingestion and Git-versioned FX fixing forecasts | Separate scheduled equity engine with source licensing, writable ledger, missed-session alerts and recovery |
| Privacy | New files are independently written and directly screened for personal identifiers | Full public-history review and external re-identification risk review; never claim guaranteed unlinkability |

The current benchmark replays use eight mathematically generated artificial equity symbols plus a ninth artificial benchmark index, and 51 measured sessions after an 80-bar warm-up. The earlier single-symbol prototype has been superseded. They must **not** replace the existing 23-row competition, be treated as nine active trades, or be labelled market performance. Source code, real/private historical positions, personal research documents, secrets and account links have not been migrated. Functional correspondence is partial and cannot be declared exactly equal without the remaining acceptance gates.

## Benchmark and capital-allocation contract

An independently derived equal-weight reference now holds eight different generated symbols, whereas a separate artificial index reference holds a ninth generated symbol. The latter is **not SPY and not a historical index series**. All nine policies have independent virtual account balances; market orders triggered on a prior close receive equal planned cash allocations from the same pre-trade cash snapshot, after which trades deduct their own fees. No portfolio is allowed to borrow another portfolio's cash, and the synthetic outcomes remain distinct from any operational competition. The public equity price feed, official splits/dividends and real benchmark are still not available.

The independent virtual execution study now enforces a 15% of simulated open-NAV upper limit on each technical entry, consistent with its configuration contract; the benchmark proxy alone may target 100% NAV, subject to a 95% cash-investment fraction. All orders remain artificial, non-leveraged and separately funded. This is not a matching claim for live benchmark OHLC or execution realism.

## Equity-price provider parity — independently implemented Yahoo/yfinance

The original source architecture has been verified directly: Yahoo Finance via `yfinance` produces the canonical common XNYS daily RAW OHLC feed (unadjusted OHLC, volume, dividends, splits), with 503 frozen constituents plus independently requested SPY, exact session checks, at least 90% constituent coverage, SHA-256 provenance and explicit missing symbols. Downstream adjusted data, fundamentals and currency products remain separate. The institutionally rewritten module `scripts/yahoo_source.py` now validates those critical scientific source contracts without connecting to private source paths or reusing the personal snapshot history. It does NOT declare a new vendor such as Alpha Vantage.

Its tests use wholly synthetic bars; live Yahoo pulls are not included in GitHub Pages builds, are not scheduled in the institutional site, and cannot write into the public repo. A local, explicitly authorized capture can write only to existing storage outside the repository and refuses to overwrite a verified previous day. Vendor usage and public redistribution rights must be established separately. Since `yfinance` documentation describes Yahoo's endpoint as personal-use, no public daily equity prices, investment NAV, or real market returns are claimed. Full operational parity requires a properly authorized non-public data plane and prospectively verified trading logs, not merely matching a Python package name.


## Full 64-line functional migration contract

The public competition previously showed only 23 wholly synthetic prototype strategies. The legacy dashboard audit revealed **64 distinct track records** across 12 families, including historic nonexecuting experiments and legacy books that are not directly comparable. A new institution-only coverage manifest models 64 newly keyed functional slots without private repository identifiers, source paths or copied account histories. The screen now supports the equivalent fields for timestamp, currency, activity, equity return, daily P/L, positions/orders, volatility, maximum drawdown, comparability and curve. It supports family filtering, text search and CSV export.

No track is currently marked migrated, and financial fields remain null. Any attempt to report synthetic numbers as institutional source-verified ledger data is rejected by the source verifier. Before live-state integration, require a separate institutional ingestion, provenance and a rights-cleared execution source. Track names are nonidentical neutral descriptions, but complete mathematical non-correlation with public prior records cannot be guaranteed from naming alone. Existing 23 synthetic demonstrations and nine artificial accounting replays must not be merged silently into the 64-row roster. This implementation closes the *inventory and table-interface gap*, NOT the market/algorithm/persistence/forecast/issuer-documentation gaps.


## Exact frozen 503-ticker public issuer universe

The independent public symbol-only file `data/universe-xnys.json` contains the exact 503 XNYS constituency symbols corresponding to the 2026-09-29 frozen reference and a separately defined SPY benchmark. Its bytes and filing organization are newly generated in the institutional repository, and it includes no personal URLs, financial account holdings, notes, or legacy diary values. The Yahoo source validator accepts hyphenated class symbols (BRK-B, BF-B) and performs the dated PSKY-to-SKYD provider transition on and after 2026-10-06, without changing the canonical security identity. The build checks this symbol contract fully offline; institutional source collection is still disabled pending rights and private data storage. Matching the frozen universe is necessary but insufficient to certify identical portfolio returns, signals or production schedules.


## Maximum five missed decisions — causal replay parity

The institution-only synthetic accounting engine now accepts up to five skipped completed trading sessions *only when configured*, settling previously frozen pending orders, split/dividend events, stops/targets and NAV in their actual session order. No buy/sell decision is retrospectively generated for an omitted close; every missed decision receives a dedicated event and the leaderboard exposes its cumulative count. Any source-history revision, unbounded gap or changed campaign configuration fails closed. The model uses OHLC after the fact for passive fills, therefore this is an accounting reconstruction and is not evidence of actual simulated order acceptance before the next open. This closes a specific functional gap against the historical source implementation, but remains tested on artificial bars.


## Authenticated non-public core -> public 64-track summary boundary

The new publicly allowed `institutional-paper-feed.json` contains only a disconnected placeholder until a **separate institutional private core** can supply a signed, source-checked summary. The exact property allowlist prohibits account IDs, broker secrets, source repo URLs, raw OHLC, private diary content, or arbitrary text. The Python CI validator requires HMAC-SHA256 with the institutional GitHub Actions secret `IDEALAB_PAPER_FEED_KEY` whenever status is `source_verified`, rejects malformed or nonexistent strategy IDs, reconciles cumulative and daily return against dated NAV evidence, validates drawdown against the same history, and binds every strategy configuration to the full XNYS source SHA-256. Source validation requires Yahoo/yfinance exact client, 503 observed constituent coverage floor, SPY separately, and an explicit rights attestation. Client-side checks are defense in depth only and **cannot** verify HMAC without the private key; CI owns cryptographic admission. No key is committed or included in Pages.

The source record is **not_connected**, not paper-trading-live; no institutional ticker prices or model forecasts have been transported, and zero of 64 records are certified. A valid signature authenticates the authorized signer, but cannot itself certify the truth of every forecast, execution decision, training method, or market-data license. Actual production parity still depends on commissioning independent private hosting with permissions, running all eligible algorithms and verifying subsequent scheduled operations. Never silently map legacy private returns to these public slots.


## Public-repo-only operational runner (new, not activated)

The previous private-repository prerequisite has been dropped. The independent institutional GitHub Actions runtime now lives in this **same public repository**, with only the authentication key held in GitHub Actions Secrets and a source-rights condition held as a repository variable. `scripts/public_market_runner.py` integrates the original-provider Yahoo/yfinance 503+SPY capture contract with a *new* prospective only two-book reference cohort: SPY and a separate eight-symbol equal-weight basket. Holdings, fees, split/dividend events, dated NAV and a signed redacted summary are written only after an original valid market session. The raw OHLC snapshot exists in runner memory only and is not committed, uploaded as an artifact or printed to logs. A commit includes only `data/public-paper-book.json` and `data/institutional-paper-feed.json`. Identical-day reruns and missing-source/missed-session replays cannot manufacture trades.

The standalone scheduled workflow uses 23:07 UTC weekdays. Its offline source/engine preflight runs without any Yahoo data access; the market execution job is skipped unless `MIDAS_YAHOO_RIGHTS_CONFIRMED=true` is expressly configured *and* `IDEALAB_PAPER_FEED_KEY` is present. A value in a variable cannot by itself prove external license rights, and neither a signature nor the algorithm source license confers market-data redistribution rights; those must be established separately. The startup state is `not_started` with zero economic activity. The nine standalone synthetic method comparisons and older 64-slot registry remain separate. This is one implemented reference engine, not complete parity with the original 64 lines.

The precise initial eight-ticker basket and known strategy parameter families are publicly observable; combined with public histories they may permit statistical linkage between projects even if direct personal links are removed. Avoid copying original account histories and commit metadata, and never promise irreversible non-attribution.


## Frozen 503 classical signal engine (source-independent implementation)

A new institutional strategy selector implements the **eight** published S&P 500 classic methods plus SPY benchmark against the exact 503-frozen-constituent universe, rather than incorrectly treating the original eight-stock archival experiment as that campaign. Model decisions include EMA12/26+RSI14, frozen EMA4/22+RSI6, MACD, RSI reversal, Bollinger, breakouts 20/10 and 55/20, and equal-weight hold. It requires at least 453 valid 80+-session histories, the exact target closing session, chronological OHLC, and the separate SPY reference. It ranks entry candidates by prior 21-session momentum with deterministic ticker ties; pending buy and sell *intents* are bounded by eight holdings and frozen only after the close. The Yahoo/yfinance 420-calendar-day historical loader is rights-gated and emits no raw data into the repository. Unit tests are wholly offline. This **does not yet include a persistent 503-account execution ledger, independent position costs, stop-first settlement, corporate action accounting or prospective verified P/L**, which are distinct acceptance gates. Preflight passes must not be described as strategy operating status.


## Prospective 503 classical accounting and single-writer join

Source-matched eight classical strategies plus SPY now have a separate HMAC-authenticated 503-constituent paper ledger `data/classic-503-book.json`; the existing two 8-stock reference accounts remain a separate campaign with independently allocated 100k USD capital per strategy. Once institutional rights are verified, **one shared daily Yahoo/XNYS capture** supports both state transitions. Each initial session only freezes close-date intents. The next dated NYSE open settles buys/sells with 10 bps modeled commissions and 5 bps slippage, applies corporate actions and stop-first intraday exits, then marks independent NAV and queues subsequent close-only orders. Equal weight may hold all 503 constituents and budgets 95% NAV divided by 503; technical methods cap eight positions with a 15% per-entry ceiling. Missing held bars cause *per-book quarantine* with stale NAV expressly flagged, rather than using the prior close or wrongly pausing every strategy. The same source-derived signed public feed then contains eleven rows from two HMAC books; all results must be successfully validated before the single GitHub writer can commit. No raw prices, historical personal positions or original accounts are imported. The rights gate remains OFF and actual scheduled strategy execution has not begun. Further parity checks include 503-session independent reconciliation, actual market data permissions, FX, archived experimental models and the 25-company fundamental thesis lifecycle.


## Two distinct monthly fundamental allocation contracts

The independently implemented `monthly_selection.py` restores the **selection / position target** decisions of the capital scarcity strategy (IL-038) and the Buy The Dip process (IL-039). It preserves their separate risk and concentration settings, 3-month conditional holding hysteresis, hard solvency/quality exits, monthly market-close timing, composite factor weights, and exposure ramp 0/50/70/90/95% for dip selection. At least 35 vs 80 point-in-time scored issuers must be available with a date-attested 3-4-year financial history; future filing availability, missing factor fields, foreign constituents, corrupt values and weaker coverage fail closed. The implementation consumes already scored source-validated fundamental candidates: it does NOT yet extract or normalize real historical filings, calculate the full issuer factor pipeline or publish an economic portfolio NAV. Its return value is explicitly research targets for **next-open** execution, not real fills or paper performance. This is a partial phase toward the 64-line parity contract.
