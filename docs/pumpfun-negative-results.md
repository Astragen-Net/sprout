---
title: "72 Hours of pump.fun: Three Launch-Signal Tests, All Failed"
description: "We captured 122,000 launches, pre-registered two launch-signal tests, ran one exploratory check, and replayed the signals with fees and slippage. All failed. Here is the method, the numbers, and why the negative result is the useful part."
date: 2026-11-17
author: Rahul Jaguste
category: Research & Data
readTime: 10 min read
artwork: trading
---

# 72 Hours of pump.fun: Three Launch-Signal Tests, All Failed

*By Rahul Jaguste · Astragen · November 17, 2026*

**TL;DR:** We captured 72 hours of pump.fun mainnet activity, built a Rust gRPC decoder and a DuckDB research pipeline, pre-registered two launch-signal tests, and ran one exploratory check. Same-slot bundle and sniper signals were inverted. The insider network was real but missed its pre-registered bar. The creator dev-dump pattern was inverted at 24 hours. A replay that entered after T+60s and applied fees and slippage lost money in every cohort, including at zero costs. The useful output was not alpha. It was a reusable data layer and a process for killing bad ideas before they reach production.

<!-- Publication note: replace the local report links below with public repository URLs before publishing on Astragen. -->

## Why pre-register a crypto signal?

Crypto signal research has an incentive problem. If you look at the outcomes first, it is easy to find a threshold, a window, or a cohort that “works.” The result looks impressive and rarely survives contact with a live market.

We wanted the opposite. We pre-registered the bundle test (v1) and the insider test (v2) before evaluating their outcomes, and labeled the creator dev-dump check exploratory. For the pre-registered tests, we wrote down:

- the feature definitions and the exact T+60s cutoff;
- the outcome definition;
- the success bar, including AUC, confidence interval, lift, precision, and sample size;
- the analysis population and exclusions;
- the split between exploration and confirmation.

Then we ran the tests. The bars were deliberately modest: an AUC of 0.70 for the bundle signal, 0.65 for the insider signal, and a precision multiple of 1.3× the base rate. We did not lower them after seeing the results.

## The data

- **Window:** 2026-11-13 22:08 to 2026-11-16 22:08 UTC.
- **Capture:** Yellowstone gRPC, confirmed commitment, failed transactions excluded.
- **Decoder:** Rust, pump.fun V1/V2/V3 instructions, balances-as-truth, native SOL/WSOL quote paths.
- **Volume:** 21.2M transactions, 122,660 launch events (122,121 unique mints), 7.55M trade events (7.52M after de-duplication), 3,868 migrations.
- **Time:** all windows use chain time from `blocks_meta`, not ingest time. The measured slot rate was ~4.65 slots/s (~215 ms/slot), not 400 ms.
- **Analysis:** DuckDB, pre-registered features at T+60s, 24-hour rug as the primary outcome.

Two data-quality points matter for reading the numbers below:

1. The capture stores decoded events, not raw transactions. The first version of the decoder misread the first buy in a create+buy transaction: the curve vault is created and funded in the same transaction, so its transaction-level post balance is the remaining supply, not the amount bought. About 24,914 launches have a first buy above 500M tokens as a result. The decoder is fixed, but the existing capture cannot be re-decoded without re-capturing or backfilling the affected transactions.
2. About 27,950 of 54,629 uncensored launches had no trade after T+60s. Those launches are dead for a price-based rug label and are reported separately, not silently treated as survivors.

The effect sizes below are therefore **provisional**. Excluding the provably corrupt first-buy launches leaves the v2 insider AUC at ~0.646, still below the bar. The replay enters on post-T+60s trades rather than the T+60s snapshot, so it is less exposed to the first-buy bug, but not immune: a launch whose first buy happens after T+60s can still be affected. The direction of the conclusion survives the cleanup, but the exact numbers should be read as evidence, not gospel. The full caveats are in [`KNOWN_ISSUES.md`](../KNOWN_ISSUES.md).

## Test 1: Same-slot bundle score — inverted

**Hypothesis:** launches whose early buyers cluster in the same slot are coordinated bundles, and should rug more often.

`bundle_score` is the share of early bought tokens bought by wallets in slots with at least four distinct buyers.

| Horizon | n (confirmation) | AUC | 95% CI | Flagged rug | Unflagged rug |
|---|---:|---:|---|---:|---:|
| 12h interim | 2,170 | 0.452 | 0.444–0.461 | 1.6% | 18.4% |
| 24h full dataset | 7,896 | 0.450 | 0.446–0.455 | 1.9% | 22.5% |

The signal is not weak. It is **backwards**. Flagged launches had more early buyers (12.5 vs 2.1), more early volume (11.1 vs 1.8 SOL), and higher trade-derived concentration (0.75 vs 0.37). They were high-demand launches, and high-demand launches were less likely to draw down 90% within 24 hours.

The same pattern showed up in the secondary features: `sniper_score` (AUC 0.358), `concentration_top10` (0.437), and `early_buyers` (0.374) were all inverted on the full 24-hour dataset. The flag was measuring demand and liquidity, not coordination.

**Conclusion:** the original bundle-detection wedge is not supported. A crowded slot is not evidence of a bundle; it is often evidence of a launch people wanted.

## Test 2: Insider repeat-buyer network — real, but below the bar

**Hypothesis:** wallets that bought an earlier launch by the same creator are an insider network, and their share of the current launch predicts a rug.

We pre-registered v2 on a fresh window, 2026-11-15 onward, after the v1 bundle result failed.

| Metric | v2 result |
|---|---:|
| n (known creator + observed 24h outcome) | 3,025 |
| AUC | **0.649** (95% CI 0.628–0.671) |
| High-insider cohort (≥0.9) | 2,151 launches |
| High cohort rug rate | 24.4% |
| Rest rug rate | 7.1% |
| Lift | 3.44× |
| Precision multiple | 1.26× |
| Pre-registered bar | AUC ≥ 0.65, CI low > 0.55, lift ≥ 1.5×, precision ≥ 1.3×, n ≥ 200 → **FAIL** |

This is the most interesting result in the study. The direction is real: the high-insider cohort rugs at 24.4% versus 7.1% for the rest. But the signal is broad. About 70% of the primary known-creator cohort falls into the high cohort, and the precision multiple is only 1.26× the base rate, below the 1.3× bar.

The expanded and repeat-≥2 variants were weaker (AUC 0.607 and 0.618). The bundle negative control stayed inverted (0.448). The combined model fit on v1 and tested on the fresh window reached 0.628.

**Conclusion:** creator/insider history carries information, but not enough to be a standalone product. It is a risk prior, not a trading signal.

## Test 3: Creator dev-buy / fast-sell — inverted at 24h (exploratory)

The open-source [`pumpfunbots-reverse`](https://github.com/zostaff/pumpfunbots-reverse) research describes a different pattern: the creator dev-buys in the create transaction, sells within seconds, and repeats across launches. We tested those features against 24-hour rugs on the existing dataset. This was exploratory, not pre-registered.

| Feature | n | AUC | 95% CI |
|---|---:|---:|---|
| creator_create_buy_share | 2,782 | 0.286 | 0.211–0.365 |
| creator_sold_5s | 26,333 | 0.448 | 0.445–0.450 |
| creator_prior_dump_rate | 21,125 | 0.443 | 0.440–0.445 |
| sell_only_network_share | 26,333 | 0.499 | 0.498–0.500 |
| insider_score (comparator) | 6,716 | 0.657 | 0.642–0.671 |

Direct creator buying and selling predicted **survival**, not a 24-hour rug. Launches where the creator sold within five seconds rugs at ~0.8%, against a 19.1% base rate at 24 hours. The likely explanation is that the pattern is a **5–60 second** dump, not a 24-hour rug; a 24-hour label is too slow to see it.

## The replay: the signal is not a trade

A risk flag is not a P&L. We replayed the insider high cohort with a realistic entry:

- entry at the first trade after T+65s, within five minutes of the signal;
- exit at the last trade at or before T+24h;
- 1% fee and 1% slippage on each side;
- 0.1 SOL equal-weight per filled trade;
- no capital constraints, no order-book depth, no MEV model.

| Cohort | Filled | Mean | Median | Win rate |
|---|---:|---:|---:|---:|
| insider_score ≥ 0.9 | 1,830 | **−34.9%** | **−67.0%** | 13.9% |
| insider_score < 0.9 | 738 | −30.2% | −33.7% | 10.4% |
| random | 1,962 | −35.0% | −58.5% | 12.8% |
| all | 2,568 | −33.6% | −57.0% | 12.9% |

The high-signal cohort is worse than the rest on median return. Every cohort loses money. The sensitivity runs are just as bleak:

| Variant | High mean | High median |
|---|---:|---:|
| zero fees and zero slippage | −32.3% | −65.6% |
| 50% stop loss | −29.4% | −53.9% |
| 1-hour horizon | −35.7% | −68.6% |

The earlier, naive backtest that entered at `price_60s` showed a huge positive mean. That was an artifact: it was dominated by a handful of extreme outliers and an optimistic entry. The replay enters at the first executable trade after the signal, which is the realistic choice, and the mean turns negative. Fees are not the only problem. The trade is bad before costs.

## The short-horizon check

If the dev-dump pattern is a short-horizon phenomenon, does it show up after T+60s? We built a harness that labels a 50% drop within 5, 15, 30, or 60 seconds after T+60s and evaluates launch-time and creator/dev features. No-trade launches are excluded from the AUC; otherwise a liquidity feature can look predictive simply by predicting whether a trade happens at all.

| Window | Traded launches | Dump rate | Best feature | AUC (95% CI) |
|---|---:|---:|---|---|
| 5s | 22,076 | 16.0% | insider_score | 0.578 (0.561–0.594) |
| 15s | 26,799 | 29.6% | insider_score | 0.602 (0.589–0.615) |
| 30s | 29,387 | 36.5% | insider_score | 0.625 (0.613–0.637) |
| 60s | 32,020 | 40.6% | insider_score | 0.646 (0.634–0.657) |

No feature clears the exploratory bar. `creator_sold_5s`, `creator_create_buy`, and the other creator/dev features are inverted (AUC < 0.5) at every window. The weak positive is insider/creator history, consistent with the 24-hour result but not strong enough.

This harness anchors at T+60s. It does **not** test the first-five-second dev-dump pattern; that needs a launch-anchored variant. The result here is narrower: after the signal is available, there is no short-horizon edge in these features.

## What we learned

- **Demand is not coordination.** A crowded early slot is a signal of interest, not necessarily a bundle.
- **A risk signal is not a trade.** The insider cohort had a 3.44× rug lift and still lost money after realistic entry and costs.
- **A high lift can hide a broad cohort.** A signal that covers about 70% of the primary known-creator cohort is a weak prior, not an alert.
- **The label defines the finding.** The dev-dump pattern may be real at five seconds and invisible at 24 hours. Test the horizon the behavior actually lives in.
- **The decoder is part of the result.** A first-buy bug can change every share-based feature. Validate the data layer before trusting the model.
- **Replay is the cheapest kill switch.** It is much cheaper than building a bot and finding out with real capital.

## What we do with this

We are not selling a signal. The evidence does not support one.

We build the layer underneath: custom Solana capture and decoding, DuckDB/Postgres pipelines, pre-registered validation, and replay backtests with fees, slippage, and realistic exits. If you have a launch signal, a bot thesis, or a dataset, the useful first question is not “does it have a high AUC?” It is “does it survive the replay?”

The pump.fun research kit is a worked example of the method, including its negative results. The full findings are in [`FINDINGS.md`](../FINDINGS.md); the replay is in [`replay_backtest.md`](../validation/reports/replay_backtest.md); the short-horizon harness is in [`short_horizon_dump.md`](../validation/reports/short_horizon_dump.md). The data-quality caveats are in [`KNOWN_ISSUES.md`](../KNOWN_ISSUES.md).

If you want an independent test before you ship, talk to us at [hello@astragen.net](mailto:hello@astragen.net).

---

*Astragen builds blockchain data and infrastructure for production systems. This article is research and education, not financial advice. The capture predates the first-buy decoder fix; effect sizes are provisional. No warranty.*
