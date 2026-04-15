# Configurable Multi-Ticker Architecture Implementation Plan

## User Review Required

> [!NOTE]
> Please review the plan below. Once you approve it, I will execute the changes across the codebase. 

## Proposed Changes

### [config.py](file:///d:/Aryan/Trading-engine/config.py)
#### [MODIFY] [config.py](file:///d:/Aryan/Trading-engine/config.py)
We will replace the `TICKER` configuration with independent configurations that you can quickly toggle:
- `TICKER_ENABILITY`: `"single"` or `"multi"`
- `SINGLE_TICKER`: `"NVDA"`
- `MULTI_TICKER`: `["NVDA", "AAPL", "TSLA"]` (this will automatically be limited to a maximum bandwidth of 3 during execution).

### [main.py](file:///d:/Aryan/Trading-engine/main.py)
#### [MODIFY] [main.py](file:///d:/Aryan/Trading-engine/main.py)
- **[run_backtest_mode()](file:///d:/Aryan/Trading-engine/main.py#10-36)**: Will completely adapt to use `CONFIG["SINGLE_TICKER"]`. I will rewrite all sections that check for `CONFIG["TICKER"]` to pull from `SINGLE_TICKER` instead.
- **[run_forward_mode()](file:///d:/Aryan/Trading-engine/main.py#38-62)**: 
  - Will read `CONFIG["TICKER_ENABILITY"]`.
  - If `"single"`, it uses `SINGLE_TICKER` and runs the standard forward test.
  - If `"multi"`, it loads the `MULTI_TICKER` list, limits it to 3 tickers max, drops into the `while True` loop, and iterates continuously over each ticker to fire off the respective Telegram alerts (consecutively for each ticker in the iteration pass).

### Engine Level Overrides
#### [MODIFY] [forward_test_engine.py](file:///d:/Aryan/Trading-engine/forward_test/forward_test_engine.py)
- *If necessary*, I will ensure that the forward test uses a clean copy of `CONFIG` during evaluation so we avoid variable collisions or console print discrepancies during iteration. Currently, [_print_signal](file:///d:/Aryan/Trading-engine/forward_test/forward_test_engine.py#71-89) and [_format_telegram](file:///d:/Aryan/Trading-engine/forward_test/forward_test_engine.py#91-114) read from `config`. When running "multi", [main.py](file:///d:/Aryan/Trading-engine/main.py) will inject the specific ticker into the config overriding the target so the engine outputs look correct.

## Verification Plan
### Automated Tests
- N/A
### Manual Verification
- Verify [config.py](file:///d:/Aryan/Trading-engine/config.py) toggling correctly changes behavior in [main.py](file:///d:/Aryan/Trading-engine/main.py) for both Forward and Backtest modes.
- Verify the system gracefully refuses more than 3 tickers in multi-mode and falls back to a single ticker seamlessly.
