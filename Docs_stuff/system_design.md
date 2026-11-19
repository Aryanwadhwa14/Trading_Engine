# Trading Engine --- System Design and Low-Level Design

**Repository:** https://github.com/Aryanwadhwa14/Trading_Engine\
**Status:** Target architecture; not a claim that every component exists
today.\
**Audience:** Antigravity coding agent, project owner, quant/ML
engineering reviewers.

## 1. Executive summary

Evolve the current EMA strategy/backtest project into a **research-first
quantitative trading platform** with causal simulation, risk-based
sizing, portfolio-level accounting, reproducible experiments, an ML
research lane, factor/regime experiments and persistent paper trading.

Priorities: 1. Correctness and prevention of look-ahead/leakage. 2.
Risk-aware portfolio accounting and realistic costs. 3. Reproducibility
and tests. 4. Quant research capability. 5. ML/software engineering
capability.

Use a modular monolith first. Do not add microservices or distributed
infrastructure just to appear production-grade. No architecture
guarantees profitability.

## 2. Current baseline and known risks

The repository has included historical/live loaders, EMA and ATR
indicators, `strategies/ema_pullback.py`, `backtest/backtest_engine.py`,
`forward_test/forward_test_engine.py`, `config.py`, `main.py`, Telegram
alerts, CSV reports and Google Sheets integration. Verify the current
checkout before editing; code is authoritative, docs may be
aspirational.

Risks to verify: - Position sizing has used
`max(1, int(balance / entry_price))`, effectively allocating nearly all
affordable capital instead of applying `RISK_PERCENT`. - A signal based
on a completed candle close may use the same candle's earlier open as
its fill. - Fees/slippage may be absent. - OHLC data cannot reveal
intrabar order when both stop and target are crossed. - Per-symbol
backtests may each restart with full capital rather than sharing one
portfolio. - Forward scanner/Telegram alerting is not a persistent paper
broker. - Strategy, execution, reporting and Google Sheets side effects
may be coupled. - Timezone, stale/incomplete candles and missing-data
policies need explicit contracts.

Record the current commit, environment, data source, dates, timeframe,
costs, sizing and fill assumptions before changes. Never fabricate a
baseline if credentials/data are unavailable.

## 3. Goals and non-goals

### Goals

-   Causal backtesting.
-   Risk-based sizing and portfolio limits.
-   Net-of-cost performance measurement.
-   Multi-asset shared portfolio.
-   Walk-forward experiments and reproducible metadata.
-   Rule-based and ML research through a shared simulator.
-   Factor/regime experiments with leakage controls.
-   Persistent paper trading and operational recovery.
-   Strong documentation and portfolio-quality engineering.

### Non-goals initially

-   HFT/colocation, guaranteed alpha, full order-book replay without
    data, distributed services by default, live orders without explicit
    approval, and derivatives/leverage without instrument-specific
    accounting.

## 4. Architectural principles

1.  One domain model, multiple adapters.
2.  Pure/deterministic functions for sizing, metrics and feature logic
    where practical.
3.  Explicit signal availability and fill timestamps.
4.  One source of truth for portfolio state.
5.  Simulated fills are not broker-confirmed fills.
6.  Risk manager can veto strategy signals.
7.  Every experiment is tied to data, code, config, costs and dates.
8.  Fail closed on invalid data, stale prices or invalid risk settings.
9.  Simple baselines before advanced ML.
10. No performance claims without evidence.

## 5. High-level architecture

``` text
CLI / Run Controller
        |
Validated Run Configuration
        |
Market Data Interface (CSV / yfinance / Polygon / future providers)
        |
Data Validation + Timestamp Normalization
        |
Feature / Indicator Engine (EMA, ATR, factors, ML features)
        |
Strategy / Signal Engine (rule-based or ML-assisted)
        |
Risk Manager (quantity, exposure, limits)
        |
Order Manager
        |
Execution Adapter (historical simulator / paper broker)
        |
Portfolio Ledger (cash, positions, equity, P&L)
        |
Analytics + Experiment Store + Reports
```

Cross-cutting concerns: config validation, structured logging, market
calendars, run IDs, alerts, tests and data-quality checks.

### Runtime modes

  ---------------------------------------------------------------------------
  Mode              Data              Execution         Purpose
  ----------------- ----------------- ----------------- ---------------------
  `backtest`        Historical        Deterministic     Strategy research
                                      simulator         

  `research`        Historical        Same simulator    Parameter/factor/ML
                                      across candidates experiments

  `scan`            Latest completed  Signal/alert only Monitoring
                    market data                         

  `paper`           Historical/live   Paper broker      Operational
                    provider data                       validation

  `live`            Broker/provider   Real broker       Out of scope until
                                                        explicitly approved
  ---------------------------------------------------------------------------

`live` must never be the default or be reachable accidentally from
`paper`.

## 6. Target repository structure

Introduce gradually; do not create empty modules only to match the
diagram.

``` text
Trading_Engine/
├── main.py
├── config.py
├── data/
│   ├── historical_loader.py
│   ├── live_data_loader.py
│   ├── download_polygon_data.py
│   ├── providers/{base.py,csv_provider.py,yfinance_provider.py,polygon_provider.py}
│   └── validation.py
├── indicators/{ema.py,atr.py}
├── strategies/{base.py,ema_pullback.py}
├── risk/{position_sizing.py,portfolio_limits.py,risk_manager.py}
├── portfolio/{models.py,portfolio_manager.py,ledger.py}
├── execution/{models.py,order_manager.py,fill_simulator.py}
├── execution/brokers/{base.py,paper_broker.py}
├── backtest/{backtest_engine.py,event_loop.py,performance.py}
├── research/{experiment_tracker.py,walk_forward.py,parameter_search.py,factor_analysis.py,reports.py}
├── ml/{features.py,labels.py,splits.py,baselines.py,train.py,evaluate.py,inference.py}
├── storage/{database.py,repositories.py}
├── forward_test/forward_test_engine.py
├── alerts/telegram_bot.py
├── tests/
├── results/
└── Docs_stuff/{phases.md,system_design.md,implementation_audit.md}
```

## 7. Low-level domain models

Use dataclasses or one validation library such as Pydantic; select one
consistently. Public interfaces need type hints.

### 7.1 Candle

Fields: `symbol`, timezone-aware `timestamp`, `available_at`, OHLCV and
optional source metadata.

Invariants: - valid numeric prices and OHLC relationship; -
chronological and unique timestamps per symbol/timeframe; - explicit
bar-open/bar-close timestamp convention; - incomplete candles are
unavailable to completed-bar strategies.

### 7.2 Signal

Fields: `signal_id`, `symbol`, `strategy_id/version`, `side`,
`signal_time`, `available_at`, `reference_price`, `stop_loss`,
`take_profit`, `timeframe`, `reason`, optional feature/model metadata.

A signal is a proposal, not an approved order. It cannot execute before
`available_at`. Model long-only exits separately from opening shorts; do
not overload `SELL` ambiguously.

### 7.3 Order

Fields: `order_id`, `idempotency_key`, `signal_id`, `symbol`, `side`,
`quantity`, `order_type`, timestamps, optional limit/stop prices,
status, rejection reason and broker ID.

States: `CREATED`, `RISK_REJECTED`, `APPROVED`, `SUBMITTED`,
`PARTIALLY_FILLED`, `FILLED`, `CANCEL_PENDING`, `CANCELLED`, `REJECTED`,
`EXPIRED`. Validate legal transitions; deduplicate retries.

### 7.4 Fill

Fields: `fill_id`, `order_id`, `symbol`, `timestamp`, `quantity`,
`price`, commissions/fees, slippage estimate, source (`SIMULATED` or
`BROKER`) and provider execution ID where applicable.

Never confuse a simulated fill with an actual broker fill.

### 7.5 Position

Fields: `symbol`, `quantity`, `average_entry_price`, `mark_price`,
`market_value`, `realized_pnl`, `unrealized_pnl`, currency and
multiplier if needed.

Start with ordinary cash equities. Futures/options/FX/borrow/leverage
require additional accounting and risk models.

### 7.6 PortfolioState

Fields: cash, positions, equity, buying power, gross/net exposure,
realized/unrealized P&L, daily P&L, peak equity and drawdown.

For a basic cash-equity model:
`equity = cash + sum(marked position values)`. Represent fees and cash
movements explicitly.

### 7.7 RunConfig / ExperimentRecord

Record mode, symbols, dates, timeframe, timezone, provider/data version,
strategy/version/parameters, initial capital, risk settings, costs, fill
policies, code revision, package versions, random seed and output paths.
A report without this metadata is not reproducible.

## 8. Module contracts

### Market data

Common interface concept:

``` python
class MarketDataProvider:
    def get_history(self, symbol, timeframe, start, end):
        """Return canonical chronological OHLCV data."""
```

Provider adapters handle API/CSV mechanics, retries, rate limits,
timezone conversion and source metadata. Strategies must not call
providers directly. Verify current provider plans and data entitlements;
do not assume a free plan provides real-time data.

### Data validation

Validate schema, numeric values, OHLC invariants, timestamp order,
duplicates, freshness and candle completion. Missing-data repair must be
explicit. Never silently forward-fill tradable OHLC prices.

### Indicators/features

All calculations must be causal. A feature at time `t` uses only data
available by `t`. ML preprocessing must be fitted only within training
splits. Avoid duplicate feature implementations that diverge.

### Strategy

Input: validated candles and causally available features. Output:
`Signal | None`.

Strategy does not choose quantity, mutate cash, calculate final P&L,
call brokers/Telegram, write Google Sheets, or access future bars.

### Risk manager

Responsibilities: - calculate risk budget and quantity; - validate stop
direction/distance; - cap by cash/buying power and instrument
constraints; - enforce per-trade, per-symbol and portfolio exposure; -
enforce daily loss/drawdown limits; - return approval with quantity or a
rejection reason.

For simple cash equities: `risk_budget = equity * risk_fraction`\
`risk_per_share = abs(entry_reference - stop_price)`\
`quantity_by_risk = floor(risk_budget / risk_per_share)`\
`quantity_by_cash = floor(available_cash / expected_cash_per_share)`\
`quantity = min(risk quantity, cash quantity, other caps)`.

This is an estimate, not a guarantee: gaps, fees, slippage and execution
failures can increase loss. Never force quantity to at least one.

### Execution and fill simulation

-   A signal confirmed at candle `t` close can first fill on candle
    `t+1`.
-   Do not fill at a price that occurred before the signal was
    available.
-   Simulate gaps through stops conservatively.
-   If stop and target both occur within one OHLC bar, use a documented
    `stop_first` policy or mark the outcome ambiguous; never choose the
    more profitable path.
-   Apply costs consistently to entry and exit.
-   Define final-bar and end-of-day position behavior.

Fixed basis-point slippage is a useful baseline, not a true
market-impact model.

### Portfolio and ledger

The portfolio manager owns one shared state. The ledger records fills,
fees and position changes. Backtests can start in memory; paper mode
should persist to SQLite. Define one source of truth and reconciliation
rules.

### Backtest event loop

1.  Load and validate data.
2.  Build a chronological event stream across symbols.
3.  Update available marks/features.
4.  Evaluate strategy only on available data.
5.  Ask risk manager to approve/reject.
6.  Create order and submit to simulator.
7.  Apply fills/fees to ledger.
8.  Update equity/exposure/drawdown.
9.  Save events, metrics and run metadata.

Multiple symbols must share cash. Same-timestamp event ordering must be
deterministic.

### Analytics

Calculate metrics from the equity series and ledger. Document return
frequency and annualization. Core metrics: net return,
benchmark-relative return, max drawdown/duration, volatility and Sharpe
with assumptions, win rate, average win/loss, expectancy, profit factor,
turnover, costs, exposure and attribution. Metrics are descriptive, not
promises.

## 9. Quant research design

### Experiment lifecycle

1.  State hypothesis before testing.
2.  Define universe, data, strategy/target, costs and metrics.
3.  Reserve chronological training/validation/test periods.
4.  Run baseline and benchmark.
5.  Tune only on train/validation.
6.  Evaluate selected setup on untouched test data.
7.  Run walk-forward windows and sensitivity analysis.
8.  Save all tried configurations, including failures.
9.  Document limitations and selection bias.

Do not select the best of hundreds of trials and report only that
result.

### Baselines and benchmarks

Keep EMA as a reference strategy and compare with a suitable
buy-and-hold/index benchmark on matching dates. For ML include naive and
simple linear baselines. New models/factors must show incremental value
after costs and risk normalization.

### Walk-forward validation

Train on earlier data, select on validation, test on the next unseen
period, then roll forward. Preserve a final holdout. For overlapping
future-return labels, use purging/embargo or an appropriate
leakage-aware split.

### Parameter search

Declare ranges and selection criteria. Log every trial. Report stability
and cost sensitivity; narrow parameter optima are a fragility warning.

### Factor research

Candidate factors: momentum/trend, volatility, volume/liquidity where
reliable, benchmark-relative strength, market breadth where historical
constituent data exists, and fundamentals only with point-in-time data.

Every factor needs a definition, units, lookback, availability
timestamp, missing-data policy, hypothesis, normalization method and
ablation result. Avoid survivorship bias from using only current index
constituents historically.

### Regime research

A Markov chain or HMM may be tested as a filter or risk modifier, not
assumed to be an upgrade. Fit on training windows, use only causal state
estimates, avoid retrospective smoothing that uses future observations,
and compare with the unfiltered baseline.

## 10. ML research design

### Initial research question

Define a target before looking at test results. Example: using features
known at the close of bar `t`, can a model estimate whether the next
`h`-bar outcome exceeds a predeclared threshold in a way that improves a
strategy after costs? The horizon and threshold must be fixed as part of
the hypothesis.

### Pipeline

``` text
Causal historical data
 -> timestamped features
 -> forward outcome labels (training target only)
 -> chronological split / purge / embargo
 -> preprocessing fit on training only
 -> naive baseline -> linear baseline -> tree model if justified
 -> walk-forward predictions
 -> predictive metrics + calibration
 -> trading simulation after costs
 -> ablation and stability report
```

Leakage controls: - Features at `t` cannot use prices after `t`. -
Labels can look forward only as targets; never expose them as
features. - Fit scaling/imputation/selection/calibration only on
training. - Do not randomly shuffle financial time series by default. -
Handle overlapping horizons with purging/embargo as needed. - Do not use
revised/future fundamentals as historical knowledge. - Inference feature
schema must match training exactly.

Evaluate AUC/PR-AUC, precision/recall, Brier score/calibration where
appropriate, then simulate trading after costs. A high AUC alone does
not prove a trading edge. Compare against naive, linear, non-ML EMA and
ablated feature sets.

Save model, feature schema, label definition, train/evaluation dates,
split rules, hyperparameters, seed, package versions, metrics and
data/code hashes. Do not load untrusted model artifacts.

## 11. Paper trading and operational design

Implement a `PaperBroker` through the same narrow interface planned for
future brokers. Persist signals, orders, fills, positions, cash and
equity in SQLite initially. Use transactions and idempotency keys.
Define legal order-state transitions and restart recovery.

At startup: 1. Load state and ledger. 2. Reconcile/replay records. 3.
Verify cash/positions. 4. Block new orders if state is inconsistent. 5.
Resume only once state is known.

Add structured logs, bounded retries/timeouts, freshness checks, alerts
for stale data/rejections/risk breaches, a kill switch, safe shutdown
and secret-safe logs. Paper fills do not reproduce queue position,
market impact, exchange matching or all broker failures.

## 12. Configuration

Keep existing `config.py` during early phases; validate it and migrate
only when useful. Illustrative target:

``` yaml
run:
  mode: backtest
  initial_balance: 10000
  random_seed: 42
market:
  symbols: ["NVDA", "AAPL", "MSFT"]
  timeframe: "5m"
  timezone: "America/New_York"
strategy:
  name: ema_pullback
  version: "1"
  parameters: {}
risk:
  risk_per_trade: 0.01
  max_open_positions: 3
  max_gross_exposure: 0.80
  max_daily_loss: 0.02
simulation:
  commission_rate: 0.0005
  slippage_bps: 5
  entry_timing: "next_bar"
  stop_target_conflict: "stop_first"
  close_positions_at_end: true
```

Values are illustrative engineering examples, not actual trading
recommendations. Validate modes, dates, symbols, risk ranges, supported
instruments and costs. Live mode must require separate explicit
approval.

## 13. Storage trade-offs

  -------------------------------------------------------------------------
  Option              Benefits          Drawbacks         Decision
  ------------------- ----------------- ----------------- -----------------
  CSV                 Transparent and   Weak schema, poor Keep for
                      easy to inspect   transactions      exports/simple
                                                          datasets

  Parquet             Compact, typed,   Extra             Consider for
                      efficient         library/schema    larger history
                      analytics         management        

  SQLite              Local,            Limited           Initial paper
                      transactional,    concurrent        ledger/metadata
                      simple            writers           

  PostgreSQL          Concurrency and   Operational setup Add when needed
                      centralized state                   

  Warehouse/feature   Scalable shared   Cost/complexity   Not needed
  store               analytics                           initially
  -------------------------------------------------------------------------

Cache/version historical data for reproducible experiments. Do not
silently fetch changing data during a research run.

## 14. Provider and dependency trade-offs

-   **yfinance:** convenient for prototyping/history; delay, coverage
    and reliability may not suit production.
-   **Paid data provider:** potentially clearer feed/coverage, but costs
    and licensing apply. Use adapters and verify the actual plan.
-   **CSV/local history:** reproducible and fast but needs versioning.
-   **Dataclasses:** standard library and light; validation is manual.
-   **Pydantic:** stronger validation but adds dependency. Choose one
    approach.
-   **SQLite:** right for local single-process persistence; PostgreSQL
    later if concurrency requires it.
-   **scikit-learn/simple models:** easier to validate and explain.
-   **Deep learning:** more flexible but needs more quality data and
    stronger overfitting controls. Start with baselines.

## 15. Security and reliability

-   Keep secrets in environment variables/secret store; ignore `.env`.
-   Inspect tracked files/history for accidental secrets without
    exposing values.
-   Validate provider payloads and fail closed on malformed/stale data.
-   Use bounded retries and timeouts.
-   Prevent duplicate orders with idempotency keys.
-   Persist state before declaring operations complete.
-   In any future live mode, broker-confirmed positions are
    authoritative and must be reconciled.
-   Provide a kill switch and explicit live-mode opt-in.
-   Never log secrets or credential-bearing URLs.
-   Document financial, operational and regulatory risks.

## 16. Testing strategy

### Unit tests

Data/timezone validation; EMA/ATR; known strategy signals; position
sizing; gross/net P&L; fees/slippage; ledger; order state
transitions/idempotency; metrics and edge cases.

### Integration tests

Historical data through feature → strategy → risk → fills → ledger →
report; multiple symbols sharing cash; paper state survives restart;
provider failure cannot create a trade from stale data.

### Research correctness tests

No future data in features; chronological splits; preprocessing fitted
on training only; final holdout not used for selection; run metadata
sufficient to reproduce results.

Use deterministic fixtures; external APIs should not be required for
normal unit tests. If randomness is used, record seeds.

## 17. Performance and scalability

Initial target: one developer, modest symbol universe, candle-based
historical research and one paper process. Profile before optimizing;
cache/version data; avoid duplicate indicator calculations.

Do not introduce Kafka, Redis, Kubernetes or microservices without
measured need. They add network failure modes, deployment work and
schema complexity without fixing backtest correctness. Shared portfolio
state requires chronological processing even if indicators are
vectorized.

## 18. Observability and reporting

Every run should include run ID, status, config hash, code revision,
data source/date/timeframe/timezone, data-quality warnings,
signals/rejections, orders/fills/costs, equity curve/drawdown, metrics,
runtime/errors and output locations.

Telegram and Google Sheets should be optional adapters. A network
failure during report upload must not alter simulated fills or P&L.

## 19. Job-portfolio evidence

**Quant / quant developer:** event-driven backtest, sizing, portfolio
risk, cost model, drawdown, benchmarks, walk-forward validation, factor
ablation, reproducibility.

**ML engineering:** causal feature/label pipelines, leakage-safe splits,
baselines, model metadata, inference schema, evaluation and
reproducibility.

**Backend/software engineering:** typed domain models, adapter
interfaces, state machines, idempotency, transactions, reconciliation,
logging, errors, retries, tests and CI.

Do not claim guaranteed alpha, production-grade execution, real-time
feeds, or performance numbers without reproducible evidence. A rigorous
negative result is better than an unsupported claim.

## 20. Architecture decision register

  ------------------------------------------------------------------------------------------------
  Decision       Choice           Alternative          Reason                Revisit when
  -------------- ---------------- -------------------- --------------------- ---------------------
  Architecture   Modular monolith Microservices        Easy local            Independent
                                                       development/testing   deployment is
                                                                             justified

  Signal fill    Next eligible    Same-bar optimistic  Causal timing         Valid intrabar
                 bar              fill                                       data/event model
                                                                             exists

  Stop+target    Stop-first or    Target-first         Avoid optimistic bias Intrabar sequence is
  same bar       ambiguous                                                   available

  Storage        CSV reports +    Full                 Low operational       Scale/concurrency
                 SQLite if needed database/warehouse   overhead              requires migration

  Data           Provider         Provider-specific    Replaceable sources   Provider contract is
                 adapters         strategy code                              insufficient

  Sizing         Risk-based plus  Use all available    Explicit risk budget  Instrument-specific
                 caps             capital                                    model is needed

  ML             Baselines first  Deep model first     Easier diagnosis      Evidence/data justify
                                                                             complexity

  Research       Walk-forward +   Best in-sample       Reduce selection bias Keep as principle
                 holdout          result                                     

  Execution      Paper first      Live orders first    Safer validation      Explicit
                                                                             readiness/approval
                                                                             gates pass

  Alerts         Optional         Core dependency      Network failure must  Keep decoupled
                 adapters                              not affect P&L        
  ------------------------------------------------------------------------------------------------

## 21. Recommended build order

1.  Audit and tests.
2.  Risk-based sizing.
3.  Data validation and causal signal timing.
4.  Fill simulator, costs and ledger.
5.  Performance analytics.
6.  Shared multi-asset portfolio.
7.  Walk-forward research and experiment registry.
8.  ML baseline pipeline.
9.  Factor ablation and optional regime model.
10. Persistent paper trading.
11. Documentation/CI and portfolio reports.
12. Optional broker adapter only after explicit approval.

## 22. Antigravity execution contract

Before each task: 1. Read this file and `phases.md`. 2. Inspect current
code and git status. 3. State the smallest planned change, files and
acceptance tests. 4. Implement only the approved phase/subtask. 5. Run
targeted and relevant regression tests. 6. Report actual results or why
a test could not run. 7. Summarize diff, risks and next step. 8. Stop at
the phase boundary and wait for approval.

Never rewrite the project wholesale, silently alter strategy rules,
invent test/performance results, use future data, use random time-series
splits by default, enable live execution automatically, add
infrastructure without need, or commit secrets.

### First implementation task

If a current audit does not exist, execute Phase 0 only. Then propose
Phase 1: add `risk/position_sizing.py`, deterministic tests, minimal
backtest integration, preserve EMA rules, compare outputs, explain
differences, and stop for approval.
