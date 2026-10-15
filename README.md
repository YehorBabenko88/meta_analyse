# Meta Analyse — MetaScalp Windows companion (experimental v0.1)

Standalone Python/PySide6 desktop that uses the official [MetaScalp SDK](https://metascalp.github.io/metascalp-sdk/) localhost REST and WebSocket API, public Bybit V5, and optionally a dedicated PostgreSQL schema. **Paper-only; never submits exchange orders.**

## Implemented

- Top 20 USDT linear instruments by absolute 24h percentage change, filtered to >= $1m 24h turnover. Dynamic refresh each 5 min, multi-selection, and MetaScalp combo launcher.
- Localhost MetaScalp discovery (ports 17845–17855); REST bridge for signal levels and combo windows; websocket trade/orderbook subscriptions and auto-reconnect. It opens NO listening ports.
- Candle history pagination client for minute, hourly, daily, weekly, and monthly Bybit bars. Pure function detecting candidate closed-bar high/low levels, rejecting earlier levels when later candles wick through or touch.
- Minute profile and POC from observed MetaScalp updates, rolling 1m/5m/1h trade-flow metrics, provisional wall/turnover ratios.
- Paper $100 notional entry at +/-1.5% from previous closed minute's POC during only the next minute, target at POC, stop 0.5%, configurable 0.06% each-side fees plus 2 bps slippage. One position per ticker, simulated PnL and enable/disable UI.
- Optional PostgreSQL schema meta_analyse: candles, profiles, paper_fills, checkpoints, level_map. Tests and Windows CI.

## Install / run

Clone or download this repository on the **separate MetaScalp PC**. In PowerShell from the downloaded directory:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
& "$env:LOCALAPPDATA\MetaAnalyse\run.cmd"
```

Python 3.12 and dependencies can be installed in user space; script tries winget if Python launcher is absent. PostgreSQL is NOT installed, modified or connected by default to protect other local databases; set `META_ANALYSE_DSN` to an account allowed to create objects in its dedicated schema, and manually start monitoring in the UI. MetaScalp must be running with an active Bybit connection. Without configured PostgreSQL the program remains in-memory only.

## Known blockers — production not yet ready

1. **Auto signal placement is NOT connected to the running pipeline.** Individual MetaScalp create/list/delete methods exist, but lifecycle reconciliation and ownership mapping need implementation and tests before creating/removing any line. Do NOT delete user-created MetaScalp signal levels. An unbroken high should trigger GreaterThanEqual and an unbroken low LessThanEqual. MetaScalp needs live order book data before creating a level.
2. **Historical backfill is not yet automatically orchestrated** and cannot be called complete. Must discover listing dates, paginate all available historical bars with persistent checkpoints, validate gaps and coverage, roll daily candles to UTC calendar-year bars, only evaluate *closed* historical candles, and maintain incremental validity with live candle wicks.
3. MetaScalp may aggregate several raw trades by default (~200ms). Its highPrice/lowPrice preserves extremes, not the full per-price volume distribution. Existing POC thus reflects observed aggregated prints, not guaranteed raw Bybit per-price POC. Before using statistics seriously integrate raw publicTrade feed or configure verified zero aggregation and add deduplication, timestamp/gap audits.
4. Orderbook subscriptions are sent, but deltas are not yet applied to a sequenced L2 book; wall persistence/cancellation/spoofing filters and acceleration baselines are unimplemented. Wall scores based on trade turnover alone cannot predict bounces.
5. Paper trade execution uses observed prices, not a tick-accurate order simulator. Cannot guarantee fill order, gap handling, latency, variable tick size, variable exchange commissions, liquidity or funding. Restart currently loses open paper positions and can strand them on watchlist churn.
6. **No automatic version updater or autostart yet**. For safe auto-update implement pinned verified release manifests, staged atomic rollout, rollback, data migration and one-instance lock; never execute arbitrary GitHub branch contents on a live trading machine.
7. Need Windows end-to-end tests with live MetaScalp installed, Bybit adapter verification, PostgreSQL integration tests, UI thread safety, migrations, market-data outage recovery and bounded raw-event retention.
8. The current implementation is a technical MVP, **not a reliable 24/7 service**; do not rely on it for real-money decisions.

## Layout

`src/meta_analyse/core.py` deterministic levels/POC/paper rules
`exchange.py` public Bybit V5 HTTP
`ports.py` MetaScalp REST without binding a port
`runtime.py` MetaScalp WS subscriptions and ingestion
`storage.py` PostgreSQL schema and persistence
`desktop.py` PySide6 interface

## Development

```bash
python -m pip install -e ".[test]"
python -m pytest -q
```

Nine local unit tests passed in development. CI execution against GitHub Windows runners must be checked independently. All GitHub changes are staged in a feature branch and offered through a draft PR, not merged automatically.
