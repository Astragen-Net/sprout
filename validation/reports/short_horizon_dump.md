# Short-horizon dump harness

> **Exploratory; provisional data.** The capture predates the first-buy decoder fix; see [`KNOWN_ISSUES.md`](../../KNOWN_ISSUES.md). This is not financial advice.

## Method

- Label: minimum trade price in `(T+60s, T+60s+W]` is at or below `price_60s * (1 - 50%)`.
- `price_60s` is the last SOL/WSOL trade at or before T+60s.
- A launch with no trade in the window is `no_trade` and is reported separately. By default it is excluded from the AUC because it has no observable dump path; `--include-no-trade` includes it as a non-dump.
- Features are the launch-time features from `signals.py` plus the creator/dev features from `dev_dump.py`.
- Windows: 5s, 15s, 30s, 60s; minimum n = 50.
- AUC with 300-sample bootstrap CIs; top decile at 10%.

## Prevalence

| Window | Launches | No trade | Traded | Dumps | Dump rate (traded) |
|---|---:|---:|---:|---:|---:|
| 5s | 81,747 | 59,671 | 22,076 | 3,535 | 16.0% |
| 15s | 81,747 | 54,948 | 26,799 | 7,938 | 29.6% |
| 30s | 81,747 | 52,360 | 29,387 | 10,723 | 36.5% |
| 60s | 81,747 | 49,727 | 32,020 | 13,008 | 40.6% |

## Results by window

### 5s

| Feature | n | Base | AUC | 95% CI | Top-decile dump | Top-decile lift |
|---|---:|---:|---:|---|---:|---:|
| insider_score | 5,319 | 14.8% | 0.578 | 0.561–0.594 | 17.0% | 1.15× |
| creator_prior_launches | 22,076 | 16.0% | 0.569 | 0.559–0.579 | 19.1% | 1.19× |
| early_buy_volume_sol | 22,007 | 16.0% | 0.551 | 0.541–0.562 | 10.9% | 0.68× |
| sell_only_network_share | 22,007 | 16.0% | 0.500 | 0.499–0.501 | 16.0% | 1.00× |
| creator_prior_dump_rate | 19,010 | 17.4% | 0.480 | 0.477–0.484 | 17.4% | 1.00× |
| creator_sold_5s | 22,007 | 16.0% | 0.478 | 0.476–0.480 | 16.0% | 1.00× |
| creator_sold_60s | 22,007 | 16.0% | 0.474 | 0.471–0.478 | 16.0% | 1.00× |
| creator_create_buy | 22,007 | 16.0% | 0.474 | 0.471–0.477 | 16.0% | 1.00× |
| bundle_score | 22,007 | 16.0% | 0.460 | 0.457–0.463 | 16.0% | 1.00× |
| early_buyers | 22,007 | 16.0% | 0.450 | 0.441–0.458 | 2.0% | 0.12× |
| sniper_score | 22,007 | 16.0% | 0.444 | 0.436–0.452 | 3.6% | 0.23× |
| concentration_top10 | 22,007 | 16.0% | 0.422 | 0.413–0.431 | 2.9% | 0.18× |
| creator_create_buy_share | 1,333 | 4.4% | 0.363 | 0.289–0.440 | 0.0% | 0.00× |
| creator_net_share | 658 | 8.2% | 0.332 | 0.249–0.415 | 6.1% | 0.74× |
| creator_sell_share | 1,608 | 6.5% | 0.281 | 0.237–0.326 | 1.0% | 0.15× |
| creator_buy_share | 1,466 | 5.9% | 0.280 | 0.218–0.350 | 0.0% | 0.00× |

### 15s

| Feature | n | Base | AUC | 95% CI | Top-decile dump | Top-decile lift |
|---|---:|---:|---:|---|---:|---:|
| insider_score | 6,623 | 27.5% | 0.602 | 0.589–0.615 | 32.8% | 1.19× |
| creator_prior_launches | 26,799 | 29.6% | 0.597 | 0.590–0.604 | 36.2% | 1.22× |
| early_buy_volume_sol | 26,666 | 29.7% | 0.561 | 0.554–0.568 | 20.0% | 0.67× |
| sell_only_network_share | 26,666 | 29.7% | 0.498 | 0.497–0.499 | 29.7% | 1.00× |
| creator_prior_dump_rate | 22,638 | 32.9% | 0.467 | 0.464–0.470 | 32.9% | 1.00× |
| creator_sold_5s | 26,666 | 29.7% | 0.467 | 0.465–0.469 | 29.7% | 1.00× |
| creator_create_buy | 26,666 | 29.7% | 0.463 | 0.461–0.466 | 29.7% | 1.00× |
| creator_sold_60s | 26,666 | 29.7% | 0.458 | 0.455–0.461 | 29.7% | 1.00× |
| bundle_score | 26,666 | 29.7% | 0.448 | 0.445–0.450 | 29.7% | 1.00× |
| early_buyers | 26,666 | 29.7% | 0.420 | 0.413–0.426 | 4.4% | 0.15× |
| sniper_score | 26,666 | 29.7% | 0.411 | 0.405–0.417 | 5.8% | 0.20× |
| concentration_top10 | 26,666 | 29.7% | 0.397 | 0.391–0.404 | 5.1% | 0.17× |
| creator_create_buy_share | 1,862 | 7.5% | 0.326 | 0.280–0.371 | 0.5% | 0.07× |
| creator_sell_share | 2,310 | 9.7% | 0.310 | 0.278–0.339 | 3.0% | 0.31× |
| creator_net_share | 927 | 11.7% | 0.283 | 0.229–0.335 | 7.5% | 0.65× |
| creator_buy_share | 2,033 | 9.4% | 0.259 | 0.221–0.299 | 0.5% | 0.05× |

### 30s

| Feature | n | Base | AUC | 95% CI | Top-decile dump | Top-decile lift |
|---|---:|---:|---:|---|---:|---:|
| insider_score | 7,353 | 34.0% | 0.625 | 0.613–0.637 | 41.9% | 1.23× |
| creator_prior_launches | 29,387 | 36.5% | 0.610 | 0.604–0.617 | 44.4% | 1.22× |
| early_buy_volume_sol | 29,213 | 36.6% | 0.564 | 0.557–0.571 | 25.7% | 0.70× |
| sell_only_network_share | 29,213 | 36.6% | 0.497 | 0.496–0.498 | 36.6% | 1.00× |
| creator_sold_5s | 29,213 | 36.6% | 0.462 | 0.460–0.465 | 36.6% | 1.00× |
| creator_prior_dump_rate | 24,561 | 40.7% | 0.459 | 0.456–0.461 | 40.7% | 1.00× |
| creator_create_buy | 29,213 | 36.6% | 0.456 | 0.454–0.459 | 36.6% | 1.00× |
| creator_sold_60s | 29,213 | 36.6% | 0.452 | 0.449–0.455 | 36.6% | 1.00× |
| bundle_score | 29,213 | 36.6% | 0.444 | 0.441–0.447 | 36.6% | 1.00× |
| sniper_score | 29,213 | 36.6% | 0.391 | 0.386–0.397 | 7.3% | 0.20× |
| early_buyers | 29,213 | 36.6% | 0.388 | 0.382–0.394 | 7.6% | 0.21× |
| concentration_top10 | 29,213 | 36.6% | 0.384 | 0.378–0.390 | 5.6% | 0.15× |
| creator_sell_share | 2,726 | 12.6% | 0.339 | 0.312–0.370 | 5.5% | 0.44× |
| creator_create_buy_share | 2,230 | 10.1% | 0.317 | 0.284–0.355 | 0.9% | 0.09× |
| creator_net_share | 1,094 | 14.8% | 0.289 | 0.241–0.330 | 7.3% | 0.49× |
| creator_buy_share | 2,426 | 11.8% | 0.268 | 0.236–0.297 | 0.8% | 0.07× |

### 60s

| Feature | n | Base | AUC | 95% CI | Top-decile dump | Top-decile lift |
|---|---:|---:|---:|---|---:|---:|
| insider_score | 8,012 | 38.5% | 0.646 | 0.634–0.657 | 49.0% | 1.27× |
| creator_prior_launches | 32,020 | 40.6% | 0.620 | 0.613–0.625 | 49.6% | 1.22× |
| early_buy_volume_sol | 31,793 | 40.8% | 0.572 | 0.566–0.579 | 31.0% | 0.76× |
| sell_only_network_share | 31,793 | 40.8% | 0.498 | 0.497–0.498 | 40.8% | 1.00× |
| creator_sold_5s | 31,793 | 40.8% | 0.461 | 0.458–0.463 | 40.8% | 1.00× |
| creator_prior_dump_rate | 26,403 | 45.5% | 0.456 | 0.453–0.458 | 45.5% | 1.00× |
| creator_create_buy | 31,793 | 40.8% | 0.450 | 0.448–0.453 | 40.8% | 1.00× |
| creator_sold_60s | 31,793 | 40.8% | 0.449 | 0.446–0.452 | 40.8% | 1.00× |
| bundle_score | 31,793 | 40.8% | 0.446 | 0.444–0.449 | 40.8% | 1.00× |
| sniper_score | 31,793 | 40.8% | 0.378 | 0.373–0.383 | 7.9% | 0.19× |
| early_buyers | 31,793 | 40.8% | 0.373 | 0.366–0.379 | 13.2% | 0.32× |
| concentration_top10 | 31,793 | 40.8% | 0.373 | 0.368–0.379 | 5.3% | 0.13× |
| creator_sell_share | 3,119 | 15.7% | 0.350 | 0.326–0.375 | 7.5% | 0.48× |
| creator_net_share | 1,241 | 18.5% | 0.303 | 0.269–0.339 | 5.6% | 0.30× |
| creator_create_buy_share | 2,682 | 12.4% | 0.284 | 0.259–0.312 | 0.4% | 0.03× |
| creator_buy_share | 2,899 | 13.9% | 0.253 | 0.228–0.277 | 0.3% | 0.02× |

## Verdict

No feature clears the exploratory bar (AUC ≥ 0.70, CI lower > 0.60, n ≥ 50). Best: `insider_score` at 60s, AUC 0.646 (95% CI 0.634–0.657).

This is an exploratory, multiple-testing-heavy harness on a pre-fix capture. It does not model execution, liquidity, or post-migration trades; a positive result would require a fresh pre-registered study.