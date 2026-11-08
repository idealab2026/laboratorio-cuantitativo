# MIDAS Debate Alpha · zero-cost experimental strategy

**Scientific status: IMPLEMENTED CODE / NO VERIFIED FORWARD RETURNS YET.**

Independent institutional reimplementation inspired by the *roles* of
[TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents)
(Apache-2.0 project). No vendor code, prompts, decision memory or histories
were copied. This is **NOT the TradingAgents LLM**, and it makes **zero**
LLM calls. Do not describe its rule-based specialists as AI model inference.

## Committee and causal signal

- **Technical specialist:** five observed session intervals of price momentum.
- **Relative-strength specialist:** performance minus same-window SPY.
- **Risk specialist:** realized volatility and risk veto.
- **Bull / bear debate:** fixed counterarguments, market-wide risk check.
- **Fundamental and sentiment roles:** explicit ABSTAIN. Verified point-in-time
  financial statements and news archives are unavailable; no invented evidence.
- **Portfolio manager:** up to 5 long-only US equities, max 18% initial
  capital per name, up to 90% total gross, the balance in paper USD cash.

These transparent roles are deterministic **heuristics**, not trained neural
networks or generative agents. Their thresholds are frozen in
`multi_agent/run.py` and hashed in the output state; they are **research
hypotheses**, not an assertion of an optimal trading model.

Data: existing validated common XNYS daily RAW OHLC observations from the
institutional frozen 503-name universe plus SPY. Six chronologically ordered
snapshots form a five-interval signal. Signals are emitted **after** a
Friday close; full-position sell/reconstitution is queued at the **next
eligible market session's opening**, never on the signal day's close.
Execution assumptions: 0.10% commission **and** 0.05% adverse slippage per
side. State includes SHA-256 checksum, source digests, decisions, open-date
fills, cash, holdings, dividends, splits and NAV. Missing exact-session
prices for required held/target securities block settlement. No broker
connection, margin, borrow, option, capital real or discretionary rewrite.

## Zero-cost and access controls

- Python standard library for the signal and book.
- Reuses the **already installed** market-data pipeline. No extra data
  vendor, API subscription, LangGraph, paid inference, OpenAI token or cloud
  model. GitHub Actions public-repo standard runner is used, subject to
  GitHub account and platform limits; *no guarantee of permanently free usage*.
- Automatic financial use remains **gated by**
  `vars.MIDAS_YAHOO_RIGHTS_CONFIRMED == 'true'`. A public snapshot's
  presence **is not proof of public redistribution rights**. The source
  gate is inherited from the institution's public-market workflow; do not
  bypass it to claim that the strategy is trading.
- A schedule is only an intention. Production requires observed natural
  Action run, exact snapshot date, ledger commit, next-session fill and
  dashboard reconciliation. A green unit test or deployment is not proof.
- Run identity: `idealab2026/laboratorio-cuantitativo`, not any personal
  financial account. Never read or import private portfolios or private
  histories; no automatic mirror of the private MIDAS repository.

## Reproduce offline checks

```bash
python -m unittest discover -s multi_agent/tests -v
python multi_agent/run.py --check
```

The `--daily` entry point is reserved for the guarded main-branch workflow.
It consumes only the **most recently eligible complete XNYS session** and
rejects duplicate or reverse-date executions. Do not pass synthetic,
historical or recalled prices to the production ledger.

## Public competition integration gate

`data/strategy-candidates.json` registers this as a **candidate**. The
existing 64-slot competition is immutable under this PR. To promote it,
first demonstrate a valid natural scheduled signal and later next-open fill,
a non-synthetic source and corporate-action reconciliation, loss/risk limits,
same-session benchmarks and a forward record of sufficient duration. Only
then add a new comparable roster slot and a dashboard row with independently
recomputed cumulative return. *No backfill of performance.*

## Next scientific experiment

Compare this deterministic committee against a single comparable momentum
rule under the **same** universe, sessions, signal time, costs and NAV
accounting. Test its vote ablations and OOS regimes without optimizing on
future data. A true LLM committee (e.g. Ollama locally or a verified free
hosted quota) would be a separately named, explicitly consented variant;
it cannot be represented by this deterministic baseline.
