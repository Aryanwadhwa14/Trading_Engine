# Trading Engine --- Implementation Phases & Agent Execution Contract

**Repository:** https://github.com/Aryanwadhwa14/Trading_Engine\
**Audience:** Antigravity coding agent and project owner\
**Goal:** Turn the existing Python project into a reproducible
quant-research and ML-engineering platform through small, testable
phases.\
**Default mode:** Backtesting and paper trading only. Never activate
live orders without explicit owner approval.

## 0. Instructions for Antigravity --- Read Before Coding

Treat this file and `system_design.md` as project-level instructions.
Read both before editing.

1.  **Inspect before editing.** Read the current tree, git status,
    README, requirements, config, main entry point, strategy, loaders,
    backtester, forward scanner, report code, and docs. Code is
    authoritative; docs may describe plans rather than implemented
    features.
2.  **One phase at a time.** State the proposed change and acceptance
    tests, implement only that change, run tests, summarize the diff,
    and stop for approval.
3.  **No big-bang rewrite.** Preserve existing behavior unless a
    documented bug requires a change.
4.  **Do not silently change trading rules.** Infrastructure fixes and
    strategy changes must be separate.
5.  **Never fabricate performance.** Do not claim a return, Sharpe,
    alpha, accuracy, latency, or improvement unless actually measured
    and reproducible.
6.  **Prevent look-ahead and leakage.** Features, labels, normalization,
    fitting, parameter selection, and fills must respect
    information-availability timestamps.
7.  **Paper by default.** Do not add or enable live broker orders
    without explicit approval.
8.  **Protect credentials.** Never print or commit `.env` values, API
    keys, Telegram tokens, Google credentials, broker identifiers, or
    private account data. Inspect tracked files safely without exposing
    secret contents.
9.  **Keep complexity proportional.** Start with a modular monolith,
    pandas, pytest, and SQLite if persistence is needed. Do not add
    Kafka, Kubernetes, Redis, microservices, or a feature store without
    a measured requirement.
10. **Test failures honestly.** Do not delete or weaken tests to make a
    build pass. If an API or data is unavailable, report that
    limitation.
11. **Reproducibility is mandatory.** Every result should record data
    source/version, symbols, dates, timeframe, config, costs,
    assumptions, and code revision where available.
12. **Stop at phase boundaries.** Do not automatically proceed to the
    next phase.

After each task report: what changed, files changed, commands/tests
actually run, results, behavior changes, known limitations, and the
exact next step.

## 1. Vision and scope

Build a research-first platform that demonstrates: - causal backtesting
and correct portfolio accounting; - risk-based position sizing and
portfolio limits; - realistic fees, slippage and fill assumptions; -
reproducible experiments, benchmarks and walk-forward validation; -
shared multi-asset portfolio simulation; - leakage-resistant ML
experiments with simple baselines; - factor and regime research; -
persistent paper trading and operational reliability; - clean
interfaces, tests, documentation and credible evidence for quant, ML and
software roles.

This project tests hypotheses; it does not guarantee profitable trading.

### Not in scope until separately approved

Live-money execution, HFT/latency-arbitrage claims, derivatives/leverage
without instrument-specific accounting, distributed infrastructure
without a concrete need, and claims of "AI alpha" without evidence.

## 2. Baseline issues to verify against current code

The project has included historical/live loaders, EMA/ATR indicators,
`strategies/ema_pullback.py`, `backtest/backtest_engine.py`,
`forward_test/forward_test_engine.py`, config, Telegram alerts, CSV
output and Google Sheets output.

Verify current code before relying on these known concerns: - Position
sizing has used `max(1, int(balance / entry_price))`, effectively
allocating nearly all affordable capital instead of using
`RISK_PERCENT`. - Signal timing and entry prices may be inconsistent
where a signal uses a completed candle close but the fill uses that
candle's earlier open. - Fees and slippage may be absent. - OHLC candles
cannot reveal whether a stop or target was hit first when both are
crossed in one bar. - Per-symbol backtests may each start with full
capital instead of sharing one portfolio. - Forward scanning/Telegram
alerts are not a paper broker or persistent order ledger. - Backtesting,
reporting, and external Google Sheets calls may be too tightly
coupled. - Timezones, stale/incomplete candles, missing bars and data
quality need explicit policies.

## 3. Definition of done

A phase is complete only when: - code and relevant automated tests
exist; - tests pass or failures are clearly explained; - existing
behavior is preserved or migration is documented; - no secrets/generated
data are accidentally committed; - a reproducible command or minimal
example is documented; - metrics reconcile to trade/fill/equity
records; - acceptance criteria are met and owner is informed.

Use `pytest`. If no test harness exists, establish the smallest useful
setup first.

------------------------------------------------------------------------

# Phase 0 --- Audit and reproducible baseline

### Tasks

-   Inspect tree, git status, `.gitignore`, README, dependencies,
    config, main, loaders, strategy, backtester, forward scanner,
    reports and docs.
-   Map actual runtime flow and dependencies.
-   Safely inspect for accidentally tracked secrets without printing
    their values.
-   Record commands, prerequisites, and what can/cannot be run.
-   Run current tests and one small existing workflow if possible.
-   Build a tiny deterministic OHLCV fixture for tests.
-   Record data source, symbol, timeframe, dates, timezone, costs,
    sizing and fill assumptions.

### Deliverables

-   `Docs_stuff/implementation_audit.md`
-   Test scaffold if absent.
-   Reproducible baseline command and known-issues list.

### Acceptance

We can explain the actual call flow and reproduce a baseline or
explicitly document why it could not run. Do not change strategy
behavior in this phase.

------------------------------------------------------------------------

# Phase 1 --- Risk-based position sizing (first implementation)

### Tasks

-   Add `risk/position_sizing.py` with a pure, deterministic sizing
    function.
-   Use validated `RISK_PERCENT`.
-   For initial cash-equity support:
    -   `risk_budget = equity * risk_fraction`
    -   `risk_per_unit = abs(entry - stop) * point_value`
    -   `quantity_by_risk = floor(risk_budget / risk_per_unit)`
    -   `quantity_by_cash = floor(available_cash / cash_required_per_unit)`
    -   quantity is the minimum of risk, cash, instrument and portfolio
        limits.
-   Reject invalid prices, invalid stop direction, zero stop distance,
    negative equity and invalid risk fractions.
-   Never force at least one unit.
-   Add tests for long/short, insufficient cash, invalid stop, zero
    distance and boundary cases.
-   Integrate into backtest with minimal changes; do not change EMA
    entry/exit rules.
-   Log equity, risk budget, stop distance, quantity, estimated risk and
    rejection reason.

### Trade-offs

Risk-based sizing makes the intended loss budget explicit but does not
guarantee realized loss stays within it because gaps, fees, slippage and
execution failures can increase losses. Start with cash equities;
derivatives, leverage, short borrow and contract multipliers require
separate models.

### Acceptance

Quantity respects risk and buying power, invalid trades are rejected,
tests pass, and old/new result differences are explained.

------------------------------------------------------------------------

# Phase 2 --- Test foundation and data integrity

### Tasks

-   Add deterministic `pytest` fixtures.
-   Validate required OHLCV columns, numeric values, positive prices,
    OHLC invariants, sorted/unique timestamps, timezone, duplicates,
    freshness and incomplete candles.
-   Define missing-candle policies. Never silently forward-fill tradable
    OHLC prices.
-   Normalize all providers to one canonical schema.
-   Keep external API tests separate from unit tests.
-   Test malformed data, duplicate timestamps, timezone boundaries,
    missing bars and stale data.

### Trade-offs

Strict validation may reject imperfect provider data, but silently
trading on invalid data is worse. Handle provider quirks in adapters,
not strategy code.

### Acceptance

Invalid data fails with actionable errors; valid providers return a
consistent schema; timestamp and candle-completion assumptions are
documented.

------------------------------------------------------------------------

# Phase 3 --- Signal contract and causal timing

### Tasks

-   Add a typed `Signal` model with symbol, side, strategy ID/version,
    signal time, `available_at`, reference price, stop, target,
    timeframe and reason.
-   Define that a signal confirmed at candle `t` close cannot fill at
    candle `t` open.
-   Initial bar-based policy: evaluate completed candle `t`, then
    simulate earliest eligible fill on `t+1`.
-   Inspect all EMA rules for future data use and same-bar assumptions.
-   Make indicator warm-up explicit.
-   Add regression tests with known candles.
-   Separate signal generation from order/fill simulation.

### Trade-offs

Next-bar fills may be less optimistic than old reports but are more
defensible. Intrabar simulation can be added later if suitable data
exists.

### Acceptance

Signals and fills have explicit timestamps; no future information or
impossible fill timing is used; existing rules pass deterministic tests.

------------------------------------------------------------------------

# Phase 4 --- Fill simulator, costs and accounting

### Tasks

-   Separate order management, fill simulation, ledger updates and
    report generation.
-   Model configurable commission/fees and slippage on entry and exit.
-   Default to a documented conservative `stop_first` policy when a
    candle crosses both stop and target, or explicitly mark the result
    ambiguous.
-   Handle gap-through-stop conservatively.
-   Define final-bar and end-of-day position behavior.
-   Correctly compute long/short gross P&L, net P&L, cash, positions,
    realized/unrealized P&L and equity.
-   Test costs, short P&L, gaps, same-bar stop/target conflict,
    final-bar exits and ledger reconciliation.

### Trade-offs

Fixed basis-point slippage is transparent and easy to test but is not a
full market-impact model. Do not claim precision the data cannot
support.

### Acceptance

Net P&L reconciles to fills and fees; equity reconciles to cash plus
marked positions; assumptions are tested and documented.

------------------------------------------------------------------------

# Phase 5 --- Performance analytics and benchmarks

### Tasks

Add `backtest/performance.py` for: - net return and benchmark-relative
return; - maximum drawdown and drawdown duration; - win rate, average
win/loss, expectancy and profit factor; - volatility and Sharpe with
explicit return frequency/annualization; - turnover, exposure, time in
market, fees and slippage; - per-strategy attribution and total
portfolio metrics.

Save an equity curve, drawdown series and complete run metadata. Compare
with an appropriate benchmark over matching dates. Mark metrics
unavailable when sample size/frequency makes them meaningless.

### Acceptance

Metrics reconcile with the equity series and trades; reports state
assumptions and distinguish in-sample, validation and test results.

------------------------------------------------------------------------

# Phase 6 --- Shared multi-asset portfolio

### Tasks

-   Replace separate full-balance ticker backtests with a shared
    chronological portfolio event loop.
-   Align symbols without assuming identical calendars/timezones.
-   Share cash, positions, buying power, risk budget and exposure.
-   Define deterministic ordering for same-timestamp events.
-   Add maximum positions, gross exposure, per-symbol exposure, daily
    loss/drawdown halts and stale-data protections.
-   Start with simple exposure limits; add rolling correlation only when
    justified.
-   Keep single-symbol mode as a special case of the same engine.

### Trade-offs

More complex than independent ticker tests, but required to model real
capital allocation. Avoid naive correlation controls that add complexity
without validated value.

### Acceptance

No double-spending of cash; all positions and P&L reconcile;
single-symbol regression tests pass.

------------------------------------------------------------------------

# Phase 7 --- Experiment tracking and walk-forward validation

### Tasks

-   Add immutable experiment configuration and an experiment registry.
-   Use chronological train/validation/test periods.
-   Add walk-forward windows.
-   Log every tried parameter set, data version, code revision, costs,
    assumptions and metrics.
-   Compare candidates against a simple strategy and benchmark.
-   Preserve a final holdout from model/parameter selection.
-   Report parameter sensitivity, cost sensitivity and selection-bias
    limitations.
-   Do not optimize return alone; include drawdown, turnover and
    robustness.

### Trade-offs

Walk-forward results may look weaker than a single optimized backtest.
That is useful evidence, not a failure.

### Acceptance

Every run is reproducible; no random shuffle by default; the final test
set is not used for selection; results are shown across windows.

------------------------------------------------------------------------

# Phase 8 --- ML research lane

### First research question

Define a measurable target before looking at final test results. For
example: whether a future `h`-bar outcome exceeds a predeclared
threshold, using features known at decision time. This is an example,
not a mandated target.

### Tasks

Create modules only after the baseline engine is reliable: -
`ml/features.py` - `ml/labels.py` - `ml/splits.py` - `ml/baselines.py` -
`ml/train.py` - `ml/evaluate.py` - `ml/inference.py`

Start with naive and linear/logistic baselines, then consider a tree
model. Fit preprocessing only on training data. Use chronological
walk-forward evaluation; use purging/embargo when labels overlap. Save
model, feature schema, label definition, dates, split details,
parameters, versions, seed and hash. Compare predictive metrics with
simulated net trading results after costs. Add feature ablation and
stability analysis.

### Trade-offs

ML may not improve the baseline. Deep learning is not the default: it
needs enough quality data and stronger controls against overfitting. AUC
alone is not a trading edge.

### Acceptance

Features are causal, labels do not leak into features, inference schema
matches training, and models are compared with simple baselines and the
non-ML strategy.

------------------------------------------------------------------------

# Phase 9 --- Factor research and market regimes

### Tasks

-   Add independent factor calculations for momentum/trend, volatility,
    volume/liquidity where reliable, benchmark-relative strength, and
    fundamentals only if point-in-time data is available.
-   Document each factor's definition, units, lookback, timestamp,
    missing-data policy and hypothesis.
-   Normalize using training/rolling historical data only.
-   Evaluate factors individually before combining them.
-   Optionally research Markov-chain/HMM regimes after the baseline is
    stable.
-   Ensure regime estimates use only information available at each
    decision time; do not use retrospective smoothed states using future
    observations.
-   Compare each factor/filter against the same baseline without it.

### Trade-offs

More factors create more degrees of freedom, data needs and
multiple-testing risk. HMM states can be unstable and not economically
meaningful. Complexity must show out-of-sample value.

### Acceptance

Every factor has an ablation result; regime predictions are causal and
tested out of sample; no unsupported improvement claims.

------------------------------------------------------------------------

# Phase 10 --- Paper trading and persistent state

### Tasks

-   Implement a `PaperBroker` using the same interface planned for
    future brokers.
-   Persist signals, orders, fills, positions, cash and equity in SQLite
    initially.
-   Use unique IDs/idempotency keys to avoid duplicate orders after
    retries/restarts.
-   Define legal order-state transitions.
-   Handle partial fills/rejections if modeled, market closures, stale
    prices, API outages and restart recovery.
-   Reconcile the ledger at startup; block new orders if state is
    inconsistent.
-   Keep signal scanning separate from paper order simulation.
-   Add risk halts, kill switch, logs and alerts.

### Trade-offs

SQLite is simple for a single-process prototype; PostgreSQL is a later
option for real concurrent deployment. Paper fills do not perfectly
model queues, market impact or broker behavior.

### Acceptance

Restarts do not duplicate orders or lose paper state; ledger reconciles;
failures are visible and do not generate trades from stale data.

------------------------------------------------------------------------

# Phase 11 --- Optional broker adapter (explicit approval required)

Do not implement or activate this phase automatically.

### Preconditions

Previous critical tests pass; paper trading has been evaluated across
meaningful periods; risk controls, kill switch, reconciliation,
monitoring and credential handling are reviewed; owner explicitly
approves broker/instruments/order types; current broker documentation
and applicable regulations are checked.

### Tasks

-   Implement a narrow broker interface and one adapter.
-   Support order submission/cancel/status, fills, positions and account
    state.
-   Reconcile broker-confirmed positions with internal state.
-   Handle rate limits, timeouts, duplicate requests, partial fills and
    market closures.
-   Default to dry-run/paper; require explicit live opt-in.
-   Document emergency behavior for orders and positions.

### Acceptance

No accidental live path; explicit approval; idempotency, reconciliation,
monitoring and emergency controls tested.

------------------------------------------------------------------------

# Phase 12 --- Documentation, CI and portfolio presentation

### Tasks

-   Maintain README, `phases.md`, `system_design.md`, and an
    implementation audit.
-   Document setup, environment variables, test/backtest commands and
    limitations.
-   Add a legal-to-redistribute sample dataset or synthetic fixture.
-   Add a reproducible example and sample report with honest labels.
-   Add type hints/docstrings to public interfaces.
-   Adopt Ruff/CI if compatible and useful.
-   Ignore generated results, local databases and private datasets.
-   Include methodology, assumptions, risks and limitations in the
    README.

### Evidence for roles

**Quant:** risk sizing, portfolio accounting, costs, drawdown,
benchmarks, walk-forward validation, factor ablation.\
**ML:** leakage-resistant pipelines, baselines, model metadata,
inference schema, evaluation and reproducibility.\
**Software/backend:** interfaces, state machine, idempotency,
transactions, adapters, logging, error handling and tests.

Do not claim "guaranteed alpha," "production-grade execution,"
"real-time" or any performance metric without reproducible evidence.

------------------------------------------------------------------------

## Dependency policy

Add dependencies only when required by a phase. Keep the initial stack
small: existing Python/pandas/NumPy/providers, `pytest`, either
dataclasses or Pydantic for models, SQLite via the standard library, and
scikit-learn only in the ML phase. Avoid dependency sprawl.

## Git and change management

-   Record pre-existing changes; prefer a branch per phase.
-   Use small, descriptive commits.
-   Never commit `.env`, credentials, private trade logs or large
    generated datasets.
-   Do not force-push or rewrite history.
-   Document output-schema changes and migration behavior.
-   Report changed files and actual tests after each task.

## First task

If no current audit exists, execute **Phase 0 only**. Then propose Phase
1: 1. Add `risk/position_sizing.py`. 2. Add deterministic tests. 3.
Integrate into existing backtest with minimal changes. 4. Keep EMA
entry/exit logic unchanged. 5. Run tests and one sample backtest. 6.
Explain old/new result differences. 7. Stop for owner approval.

Make the project quant-heavy through correctness, measurement and
reproducibility---not by adding advanced models before the engine is
trustworthy.
