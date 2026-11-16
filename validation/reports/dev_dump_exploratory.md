# Dev-dump exploratory test (not pre-registered)

Uses the existing 122k-launch dataset already used by v1/v2; **exploratory only**. A feature must reach AUC ≥ 0.70 with CI lower > 0.60 before a fresh pre-registered capture is justified.

- Eligible 24h launches: **26,679**
- 24h rug prevalence: **19.1%**

| Feature | n | AUC | 95% CI | Flagged n | Flagged rug | Lift | Precision multiple |
|---|---:|---:|---|---:|---:|---:|---:|
| creator_create_buy_share | 2,782 | 0.286 | 0.211–0.365 | 2,782 | 0.018 | n/a× | 1.00× |
| creator_create_buy | 26,333 | 0.441 | 0.438–0.444 | 2,782 | 0.018 | 0.09× | 0.10× |
| creator_buy_share | 2,993 | 0.261 | 0.196–0.337 | 2,993 | 0.022 | n/a× | 1.00× |
| creator_sell_share | 3,236 | 0.211 | 0.155–0.270 | 3,236 | 0.018 | n/a× | 1.00× |
| creator_net_share | 1,379 | 0.472 | 0.320–0.609 | 1,295 | 0.017 | 0.24× | 0.84× |
| creator_sold_5s | 26,333 | 0.448 | 0.445–0.450 | 2,323 | 0.008 | 0.04× | 0.04× |
| creator_sold_60s | 26,333 | 0.431 | 0.428–0.434 | 3,236 | 0.018 | 0.08× | 0.09× |
| creator_prior_dump_rate | 21,125 | 0.443 | 0.440–0.445 | 2,076 | 0.021 | 0.08× | 0.09× |
| sell_only_network_share | 26,333 | 0.499 | 0.498–0.500 | 141 | 0.142 | 0.73× | 0.74× |
| bundle_score | 26,333 | 0.444 | 0.441–0.446 | 2,545 | 0.012 | 0.06× | 0.06× |
| insider_score | 6,716 | 0.657 | 0.642–0.671 | 5,692 | 0.215 | 2.75× | 1.11× |

**Caveat:** the creator wallet may not be the dev-buy wallet; the repo notes dev-buys are often paid by a sub-wallet. This test only detects a direct creator buy. A null result does not fully rule out the pattern.
