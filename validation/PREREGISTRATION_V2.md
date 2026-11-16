# Phase 0 v2 — insider-network validation (pre-registered 2026-11-15)

## Why this exists

The v1 primary hypothesis (`bundle_score` → 24h rug) **failed and inverted**. The only positive signal was `insider_score`, the share of early tokens bought by wallets that also bought an earlier launch by the same creator: AUC 0.670 (CI 0.624–0.717), 2.37× decile lift, BH-adjusted p = 0.006 on the 12h interim.

That result is exploratory — it came from the same capture. This document pre-registers a clean out-of-sample test on a non-overlapping window.

## Fresh window

- Launches with `launch_time >= 2026-11-15T00:00:00Z` and `launch_time + 24h <= capture_end` (~2026-11-16T22:08Z).
- The v1 analysis used data through ~2026-11-14T23:00Z. **No fresh-window outcome has been inspected.**
- No launch from the v1 window appears in the v2 test.

## Signals (T+60s, chain time, no lookahead)

- **Primary (replication):** `insider_score` — share of early bought base bought by wallets that bought early in at least one earlier launch by the same creator. Same definition as v1, including the creator cap of ≤50 total launches.
- **Secondary — expanded:** `insider_score_expanded` — all creators, considering up to the 50 most recent prior launches per creator.
- **Secondary — sharpened:** `insider_score_2plus` — only wallets that bought early in at least two prior launches by the same creator.
- **Secondary — creator history:** `creator_prior_launches`.
- **Secondary — combined:** logistic model with creator history + insider + early buy volume, fit on the v1 window and evaluated on v2.
- **Negative control:** `bundle_score`, expected to remain inverted.

## Outcome

24h rug: minimum price within 24 hours is ≤10% of the T+60s price, using SOL/WSOL quote prices. Same exclusions as v1 (no-trade launches, USDC/other quote, censored launches).

## Success bar

**Primary:** AUC ≥ 0.65, bootstrap 95% CI lower bound > 0.55, high-insider cohort (`insider_score ≥ 0.9`) rug rate ≥ 1.5× the rest, precision ≥ 1.3× the base rate, and at least **200** known-creator launches.

**Secondary:** expanded and 2-plus AUC ≥ 0.65; combined model AUC ≥ 0.70; report raw and Holm-BH-adjusted permutation p-values.

No threshold may be tuned on the fresh window. If the primary fails, the insider thesis is not confirmed even if a secondary passes; that would require another fresh window.

## Decision

**Pass + a paid buyer pilot** → proceed to product work, scoped to creator/insider network risk.
**Fail** → stop the product effort or pivot to sybil/airdrop clustering or custom indexer consulting. No rewrite.

## Limitations

Pumpfun and SOL-quoted coins only; price-based rug definition; no funding-graph tracing; insider coverage depends on prior launches; 24h maturity limits the fresh window to ~22 hours of launches.
