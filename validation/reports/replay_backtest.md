# Replay backtest

> **Exploratory; provisional data.** The capture predates the first-buy decoder fix; see [`KNOWN_ISSUES.md`](../../KNOWN_ISSUES.md). Entry and exit prices use post-T+60s trades, but the signal features are provisional. This is not financial advice.

## Strategy

- Signal: `insider_score >= 0.9`
- Window: `2026-11-15T00:00:00Z` to capture end
- Entry: first trade after T+65s and at or before T+360s
- Exit: last trade at or before T+86400s
- Costs: 100 bps fee and 100 bps slippage on each side
- Sizing: 0.1 SOL per filled trade, equal-weight; no capital constraints or overlapping-position limit

## Coverage

| Cohort | Signals | Filled | Fill rate | No entry | Unsellable |
|---|---:|---:|---:|---:|---:|
| insider_score >= 0.9 | 4,039 | 1,830 | 45.3% | 2,209 | 190 |
| insider_score < 0.9 | 1,327 | 738 | 55.6% | 589 | 127 |
| random n=4,039 | 4,039 | 1,962 | 48.6% | 2,077 | 241 |
| all | 5,366 | 2,568 | 47.9% | 2,798 | 317 |

## Net returns after costs (filled trades)

| Cohort | Mean (95% CI) | Median (95% CI) | Win rate | Total PnL (SOL) | Avg PnL/trade |
|---|---|---|---:|---:|---:|
| insider_score >= 0.9 | -34.9% (-40.2% to -29.0%) | -67.0% (-70.7% to -62.7%) | 13.9% | -63.904 | -0.0349 |
| insider_score < 0.9 | -30.2% (-36.5% to -22.8%) | -33.7% (-40.4% to -27.9%) | 10.4% | -22.286 | -0.0302 |
| random n=4,039 | -35.0% (-40.1% to -29.4%) | -58.5% (-63.3% to -53.2%) | 12.8% | -68.761 | -0.0350 |
| all | -33.6% (-38.0% to -28.9%) | -57.0% (-61.2% to -52.4%) | 12.9% | -86.189 | -0.0336 |

## Return distribution (filled trades)

| Cohort | P10 | P25 | Median | P75 | P90 | Max |
|---|---:|---:|---:|---:|---:|---:|
| insider_score >= 0.9 | -100.0% | -96.1% | -67.0% | -7.9% | +24.1% | 22.9x |
| insider_score < 0.9 | -100.0% | -88.2% | -33.7% | -8.0% | +0.8% | 10.5x |
| random n=4,039 | -100.0% | -95.1% | -58.5% | -8.4% | +13.6% | 18.6x |
| all | -100.0% | -95.4% | -57.0% | -8.0% | +15.1% | 22.9x |

## Sensitivity

Each row is a separate replay with the same entry rule; this is not a parameter search.

| Variant | High mean | High median | Rest mean | Rest median |
|---|---:|---:|---:|---:|
| zero costs | -32.3% | -65.6% | -27.3% | -30.9% |
| 50% stop | -29.4% | -53.9% | -30.1% | -37.9% |
| 1h horizon | -35.7% | -68.6% | -30.5% | -35.9% |

## Verdict

No robust profit edge is visible after costs: the high-signal cohort's mean is -34.9% and its median is -67.0% (win rate 13.9%), versus -30.2% / -33.7% for the rest. The random and all-launch cohorts are also negative, and the zero-cost / stop-loss / 1h-horizon variants remain negative.

Treat this as an exploratory replay, not a validation. It excludes post-migration AMM liquidity, order-book depth, MEV, failed transactions, and capital constraints; the last captured trade is an optimistic exit. The signal itself failed its pre-registered AUC bar.
