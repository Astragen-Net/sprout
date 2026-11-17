# Capture event schema

The capture writes zstd-compressed JSONL: one JSON object per line, one file per
hour and process run. All timestamps are Unix seconds. All public keys,
signatures and mints are base58 strings.

## `launch`

```json
{"kind":"launch","mint":"...","curve":"...","creator":"...","name":"...","symbol":"...","uri":"...","slot":123,"tx_index":4,"ix_path":0,"event_ord":0,"sig":"...","created_at":1760000000}
```

## `trade`

```json
{"kind":"trade","mint":"...","wallet":"...","curve":"...","side":"buy","base_raw":"...","base_decimals":6,"quote_raw":"...","quote_decimals":9,"quote_mint":"...","quote_kind":"sol","slot":123,"tx_index":4,"ix_path":65536,"event_ord":0,"sig":"...","created_at":1760000000}
```

`base_raw` and `quote_raw` are integer strings in base units. `quote_kind` is
`sol`, `wsol`, `usdc` or `other`. `side` is `buy` or `sell`.

## `migration`

```json
{"kind":"migration","mint":"...","pool":"...","slot":123,"tx_index":4,"ix_path":0,"event_ord":0,"sig":"...","created_at":1760000000}
```

## `block`

```json
{"kind":"block","slot":123,"block_time":1760000000}
```

`block` events map slots to chain time. The analysis uses `block_time`, not
`created_at`, for all windows.

## Identifiers

- `slot`, `tx_index`, `ix_path`, `event_ord` form a deterministic trade ID.
- `sig` is the transaction signature; the loader de-duplicates by
  `(sig, ix_path, event_ord)`.
- `event_ord` is reserved for multiple events from one instruction; the current
  decoder emits `0`.

## Limits

The capture stores decoded events, not raw transactions. See
[`../KNOWN_ISSUES.md`](../KNOWN_ISSUES.md) for coverage and re-decoding limits.
