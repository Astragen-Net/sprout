# Phase 0 pre-registration

Written **before** any outcome analysis. The live capture started 2026-11-13. Thresholds and definitions below are frozen; changes must be recorded as a dated amendment with a reason, and the original analysis remains the primary result.

## Question

Do pumpfun launch-time signals computed at T+60s separate launches that rug from launches that survive, and is the effect strong enough to sell?

## Data

- Source: live Yellowstone gRPC capture of the pumpfun program (`6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P`), decoded by `validation/capture`.
- Window: 72 hours of capture starting 2026-11-13; launches need 24 hours of follow-up, so the analysis uses launches from the first 48 hours.
- Venue: pumpfun only. SOL-quoted coins only (`quote_kind` in `sol`/`wsol`); USDC/other quote mints are excluded in the primary analysis and reported separately.
- One row per launch; duplicate events are removed by `(sig, ix_path, event_ord)`.

## Time definition

- T+60s is **slot-based**: `launch_slot + 150` slots (~60 s at 400 ms/slot). Wall-clock ingest time is never used for features or outcomes.
- Horizons: 1 h = `+9,000` slots, 6 h = `+54,000`, 24 h = `+216,000`.
- Block times come from the captured `blocks_meta` feed; if a slot is missing, the update `created_at` is used only for display, not for window boundaries.

## Signals (computed at T+60s, no lookahead)

Let `early buys` be buy trades for the launch mint with `launch_slot <= slot <= launch_slot + 150` and SOL/WSOL quote.

- **bundle_score** — share of early bought base tokens bought by "bundle wallets." A slot is flagged when at least **4 distinct wallets** buy in that same slot. All buyers in flagged slots are bundle wallets. `bundle_score = sum(base_raw of bundle-wallet buys) / sum(base_raw of all early buys)`.
- **sniper_score** — share of early bought base tokens bought in the first **5 slots** of the launch.
- **concentration_top10** — net early position per wallet (`buy base - sell base`), top 10 positive positions divided by total early bought base. This is **trade-derived**, not a true holder metric; named accordingly.
- **insider_score** (exploratory) — share of early bought base tokens bought by wallets that also bought in an earlier launch by the same creator. Requires at least one prior launch in the capture; `insider_known = false` otherwise.
- **creator_prior_launches** — count of earlier launches by the same creator (point-in-time).
- Baselines: **early_buyers**, **early_trades**, **early_volume_sol** (sum quote), **early_buy_volume_sol**, **concentration_top10**, **creator_prior_launches**, random.

## Outcomes

Price at any point is the last SOL/WSOL trade price `quote/base` for the mint.

- `price_60s` — last price at or before `launch_slot + 150`.
- `rug_1h` / `rug_24h` — minimum price in the horizon window is **≤ 10% of `price_60s`** (a 90% drawdown). This is a price-based definition; liquidity-pull data is not available in v0.
- `max_drawdown_24h` — `min_price_24h / price_60s - 1`.
- `peak_multiple_24h` — `max_price_24h / price_60s`.
- `graduated` — a `migrate`/`migrate_v2` event for the mint within 24 h.
- `dead_24h` — no trades after T+60s through the 24 h horizon.
- `censored_24h` — the capture ends before `launch_slot + 216,000`.

## Exclusions

- Launches with no SOL/WSOL trade in the first 60 s (`price_60s` missing) are reported as the "no-trade" cohort but excluded from AUC.
- USDC/other-quoted launches are excluded from the primary analysis.
- Censored launches are excluded from 24 h outcomes; 1 h outcomes use launches with 1 h maturity.
- Post-migration AMM trades are not captured; outcomes after migration are stale and flagged, not silently treated as complete.

## Primary hypothesis and success bar

**H1: bundle_score predicts `rug_24h`.**

Success requires **all** of:
1. AUC ≥ **0.70** on the held-out confirmation period.
2. Bootstrap 95% CI lower bound > **0.60**.
3. Top-decile rug rate ≥ **1.5×** the bottom-decile rug rate.
4. Precision in the top decile ≥ **1.3×** the base rug rate.
5. At least **500** eligible launches with 24 h outcomes (expected far more; a smaller sample is reported as underpowered, not as a pass).

The 1.5× bar (not 2×) is deliberate: at high rug prevalence a 2× decile lift can be mathematically unreachable even for a strong AUC.

## Secondary hypotheses

- sniper_score, concentration_top10, and insider_score (known creators only) predict `rug_24h` with AUC ≥ 0.65 and CI lower bound > 0.55.
- creator_prior_launches predicts `graduated`.
- Multiple comparisons: Holm-BH across the secondary signals; report raw and adjusted p-values from a 500-permutation label test.

## Split and analysis discipline

- Sort launches by `launch_slot`; the first 70% is the exploration period, the last 30% is confirmation. The primary success bar is evaluated on confirmation; exploration numbers are reported for context only.
- No threshold may be tuned on the confirmation period. Any threshold is chosen on exploration and applied unchanged.
- Calibration is reported as observed rug rate by bundle-score decile plus Brier score against the decile base rate. AUC is not the only reported metric; precision at a fixed alert volume (top 10% of launches) is the product-relevant number.
- Definition sensitivity: repeat the primary analysis with 1 h and 6 h outcomes, terminal price instead of minimum, and a 3-buyer same-slot threshold. These are sensitivity checks, not alternative primary results.

## Known limitations

- No RPC-traced funding graph in v0; bundle detection uses same-slot co-buying, which misses multi-slot bundles and flags crowded slots.
- Concentration is trade-derived; transfers, airdrops, burns and closed accounts are invisible.
- Migration/AMM coverage is absent; successful tokens' post-migration prices are stale.
- Creator history is cold-start constrained by the 72 h capture.
- One venue and one quote asset; results may not transfer to Raydium, Meteora or Boop.

## Amendment 1 — 2026-11-14 (before 24h outcomes)

Feature inspection after 9.5 h of capture (15,840 launches; **no outcomes examined**) shows `bundle_score` is zero for ~94% of launches. A rank-based top decile is therefore dominated by arbitrary tie-breaking at zero. The primary alert cohort is amended to:

- **flagged:** `bundle_score > 0`
- **unflagged:** `bundle_score == 0`

Success requires all of:
1. AUC ≥ 0.70 on confirmation, bootstrap 95% CI lower bound > 0.60.
2. Flagged 24h rug rate ≥ 1.5× unflagged.
3. Flagged 24h rug rate ≥ 1.3× the confirmation base rate (precision multiple).
4. At least 500 eligible launches and at least 200 flagged launches on confirmation.

The decile table is reported for context only. Threshold sensitivity (`bundle_score` ≥ 0.1/0.25/0.5 and `bundle_score_3`) remains secondary. No 24h outcome was inspected before this amendment.

## Amendment 2 — 2026-11-14 (time calibration)

The measured slot rate in the capture is **4.649 slots/s (~215 ms/slot)**, not the 400 ms assumed in the original T+60s definition. Consequently, 150 slots was ~32 s, and 216,000 slots was ~12.9 h, not 24 h. All windows are redefined in **chain time** from `blocks_meta`:

- T+60s = `launch block_time + 60 s`.
- Horizons = `+3,600 / +21,600 / +43,200 / +86,400 s` for 1h/6h/12h/24h.
- Block-time coverage of captured launches, trades and migrations is 100%.

The pre-registered primary remains the **24 h** outcome. The slot-based result is retained as a sensitivity. This amendment corrects a measurement assumption; it does not change a threshold. The 12 h horizon is reported as an interim while the 24 h sample matures.

## Decision rule

**Go** if H1 passes on the confirmation period **and** at least one arm's-length buyer commits to a paid pilot (see the buyer-validation section). **Pivot or stop** if H1 fails or no buyer pays. A pass on H1 alone is not a go.
