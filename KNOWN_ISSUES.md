# Known issues and data status

**Status: research-grade; effect sizes are provisional.**

The 72-hour dataset behind the published reports was captured with a decoder
that misread the first buy of a create+buy transaction. The decoder is fixed in
this tree, but the existing capture stores only decoded events, so the published
numbers cannot be repaired without re-capturing or backfilling the affected
transactions. Do not cite the effect sizes as final until that data is regenerated.

## First-buy balance bug (fixed in code; old captures affected)

`token_pair` used transaction-level pre/post token balances and treated a missing
pre-balance as zero. When the curve token vault is created and funded in the same
transaction as the first buy, `pre` is absent and `post` is the remaining curve
supply, not the amount bought.

- ~24,914 launches have a first buy >500M tokens; 19,932 are >900M (total supply
  is 1B).
- Common exact first-buy values are `999,964,676`, `965,800,797` and
  `933,714,286` — the curve remainder, not a purchase.
- Example: a first buy recorded as `999,964,676` tokens for `0.0025` SOL; the
  next buy is `35,322` tokens for `0.001` SOL.
- Effect: `early_buy_base` and every share feature are inflated or diluted for
  affected launches; `sniper_score` and `concentration_top10` can be ~1.0. For
  launches whose only T+60s trade is the first buy, `price_60s` is wrong.
- Fix: base amounts now come from the user's associated base token account
  (legacy index 5, v2 14, v3 9), not the curve vault.

The first-buy **quote** for native SOL can still include the curve account's
rent-exempt balance. That is small relative to most fills but can matter for tiny
first buys.

The current data was not regenerated. Re-capture 72 hours with the fixed decoder,
or backfill the affected create transactions via RPC, before treating the
published numbers as final.

## Dead-launch outcome fixed; old reports were mislabeled

`signals.py` previously assigned `dead_*` from a Series indexed only by mints with
post-window trades, so dead launches received NaN and were silently dropped by
`dropna`. The code now reindexes to the full launch index.

24-hour cohort:

- 54,629 uncensored launches with a T+60s price and early trades;
- 27,950 dead (no post-T+60s trade);
- 26,679 observed 24h outcomes.

v2 fresh window: 23,709 uncensored launches, 11,721 dead, 11,988 observed,
3,083 known-creator launches with observed outcomes; primary n = 3,025.
Price-based rug AUC excludes dead launches by construction; they are reported
separately in the generated reports.

## Coverage caveats

- The capture log reports `ignored=3,923,051` pumpfun instructions
  (fee/admin/non-trade) over 72 hours. `decode_errors=0` means zero
  balance-lookup failures, not complete trade coverage.
- `multi_hop_curve_swap` (a trade instruction) and
  `migrate_bonding_curve_creator` (a migration) are in the public IDL but are not
  decoded; they fall into the ignored bucket.
- `zero_delta` counts recognized trades with a zero base or quote delta. These
  are not emitted. Reconcile the counters before describing a capture as
  complete.
- No raw transaction is stored. The JSONL contains decoded events only, so a
  decoder fix cannot be applied retroactively to old captures.
- Balances are transaction-level. If a transaction contains multiple fills for
  the same mint, the base side is now read from each user's token account, but
  the quote side still uses the curve vault and is netted across fills. This is
  rare for a single user and common in bundled transactions. Parse the trade
  event CPI if exact per-instruction quote amounts are required.

## Other limitations

- No post-migration AMM trades; migrated-token outcomes are stale.
- No USDC/other quote mints in the primary analysis.
- No RPC funding graph; insider is a repeat-buyer proxy.
- Restarting the capture truncates the current hourly file and does not resume
  from a persisted slot checkpoint. Do not restart mid-hour until this is fixed;
  use a fresh output directory or wait for the hour boundary.
- The fixture is one minute of public on-chain data. It contains third-party
  token metadata and URIs; those are not endorsed.

## Decision impact

The stop/pivot decision is unchanged. Excluding the provably corrupt first-buy
launches leaves the v2 AUC at ~0.646 (still below 0.65); the dead-launch
extremes give 0.649 (dead=rug) or 0.558 (dead=not-rug); the v1 inversions
persist. The published effect sizes are provisional, but none of the known issues
reverses the negative result.
