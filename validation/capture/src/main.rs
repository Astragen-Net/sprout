//! Minimal pumpfun capture for Phase 0 validation.
//!
//! Subscribes to Yellowstone gRPC for the pumpfun program plus block metadata,
//! decodes create/buy/sell/migrate instructions, and writes compact JSONL
//! events compressed with zstd. No database, no product infrastructure.

use std::{
    collections::HashMap,
    env,
    fs::{self, File, OpenOptions},
    io::{BufWriter, Write},
    path::{Path, PathBuf},
    sync::LazyLock,
    time::{Duration, Instant},
};

use anyhow::{Context, Result};
use borsh::BorshDeserialize;
use futures_util::StreamExt;
use rustls::crypto::{CryptoProvider, aws_lc_rs};
use serde::Serialize;
use sha2::{Digest, Sha256};
use yellowstone_grpc_client::{ClientTlsConfig, GeyserGrpcBuilder};
use yellowstone_grpc_proto::{
    geyser::{
        SubscribeRequest, SubscribeRequestFilterBlocksMeta, SubscribeRequestFilterTransactions,
        SubscribeUpdate, SubscribeUpdateTransactionInfo, subscribe_update::UpdateOneof,
    },
    prelude::{Message, TokenBalance, TransactionStatusMeta},
};
use zstd::stream::write::Encoder;

const PUMPFUN_PROGRAM: &str = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P";
const COMMITMENT_CONFIRMED: i32 = 1;

static BUY: LazyLock<[u8; 8]> = LazyLock::new(|| discriminator("buy"));
static SELL: LazyLock<[u8; 8]> = LazyLock::new(|| discriminator("sell"));
static CREATE: LazyLock<[u8; 8]> = LazyLock::new(|| discriminator("create"));
static CREATE_V2: LazyLock<[u8; 8]> = LazyLock::new(|| discriminator("create_v2"));
static MIGRATE: LazyLock<[u8; 8]> = LazyLock::new(|| discriminator("migrate"));
static MIGRATE_V2: LazyLock<[u8; 8]> = LazyLock::new(|| discriminator("migrate_v2"));
static BUY_V2: LazyLock<[u8; 8]> = LazyLock::new(|| discriminator("buy_v2"));
static SELL_V2: LazyLock<[u8; 8]> = LazyLock::new(|| discriminator("sell_v2"));
static BUY_V3: LazyLock<[u8; 8]> = LazyLock::new(|| discriminator("buy_v3"));
static SELL_V3: LazyLock<[u8; 8]> = LazyLock::new(|| discriminator("sell_v3"));
static BUY_EXACT_QUOTE_V2: LazyLock<[u8; 8]> =
    LazyLock::new(|| discriminator("buy_exact_quote_in_v2"));
static BUY_EXACT_QUOTE_V3: LazyLock<[u8; 8]> =
    LazyLock::new(|| discriminator("buy_exact_quote_in_v3"));
static BUY_EXACT_SOL_IN: LazyLock<[u8; 8]> = LazyLock::new(|| discriminator("buy_exact_sol_in"));

/// Anchor event CPI envelope used by pumpfun; not an instruction.
const EVENT_TAG: [u8; 8] = [0xe4, 0x45, 0xa5, 0x2e, 0x51, 0xcb, 0x9a, 0x1d];
const WSOL_MINT: &str = "So11111111111111111111111111111111111111112";
const USDC_MINT: &str = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v";

fn discriminator(name: &str) -> [u8; 8] {
    let mut hasher = Sha256::new();
    hasher.update(format!("global:{name}").as_bytes());
    let digest = hasher.finalize();
    let mut out = [0u8; 8];
    out.copy_from_slice(&digest[..8]);
    out
}

#[derive(BorshDeserialize)]
struct CreateArgs {
    name: String,
    symbol: String,
    uri: String,
    creator: [u8; 32],
}

#[derive(Serialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
enum Event {
    Launch {
        mint: String,
        curve: String,
        creator: String,
        name: String,
        symbol: String,
        uri: String,
        slot: u64,
        tx_index: u64,
        ix_path: u32,
        event_ord: u16,
        sig: String,
        created_at: i64,
    },
    Trade {
        mint: String,
        wallet: String,
        curve: String,
        side: &'static str,
        base_raw: String,
        base_decimals: u32,
        quote_raw: String,
        quote_decimals: u32,
        quote_mint: String,
        quote_kind: &'static str,
        slot: u64,
        tx_index: u64,
        ix_path: u32,
        event_ord: u16,
        sig: String,
        created_at: i64,
    },
    Migration {
        mint: String,
        pool: String,
        slot: u64,
        tx_index: u64,
        ix_path: u32,
        event_ord: u16,
        sig: String,
        created_at: i64,
    },
    Block {
        slot: u64,
        block_time: i64,
    },
}

#[derive(Default)]
struct Stats {
    txs: u64,
    launches: u64,
    trades: u64,
    migrations: u64,
    blocks: u64,
    decode_errors: u64,
    err_create_args: u64,
    err_missing: u64,
    err_sol: u64,
    err_base: u64,
    err_quote: u64,
    zero_delta: u64,
    failure_samples: Vec<String>,
    event_cpis: u64,
    ignored: u64,
    discriminators: HashMap<[u8; 8], u64>,
    programs: HashMap<String, u64>,
    unknown_samples: Vec<String>,
}

struct Writer {
    dir: PathBuf,
    run_id: String,
    encoder: Option<Encoder<'static, BufWriter<File>>>,
    hour: i64,
    lines: u64,
    raw_bytes: u64,
}

impl Writer {
    fn new(dir: PathBuf) -> Result<Self> {
        fs::create_dir_all(&dir).with_context(|| format!("create {}", dir.display()))?;
        let run_id = format!(
            "{}-{}",
            chrono::Utc::now().format("%Y%m%dT%H%M%SZ"),
            std::process::id()
        );
        Ok(Self {
            dir,
            run_id,
            encoder: None,
            hour: i64::MIN,
            lines: 0,
            raw_bytes: 0,
        })
    }

    fn write(&mut self, event: &Event) -> Result<()> {
        let hour = chrono::Utc::now().timestamp() / 3600;
        if self.encoder.is_none() || self.hour != hour {
            self.rotate(hour)?;
        }
        let line = serde_json::to_vec(event)?;
        let encoder = self.encoder.as_mut().expect("encoder exists");
        encoder.write_all(&line)?;
        encoder.write_all(b"\n")?;
        self.lines += 1;
        self.raw_bytes += line.len() as u64;
        Ok(())
    }

    fn rotate(&mut self, hour: i64) -> Result<()> {
        if let Some(encoder) = self.encoder.take() {
            encoder.finish()?;
        }
        // A unique run id per process start means a restart never truncates
        // an existing hour. create_new fails loudly instead of overwriting.
        let hour_time =
            chrono::DateTime::from_timestamp(hour * 3600, 0).context("invalid capture hour")?;
        let name = format!(
            "pumpfun-{}-{}.jsonl.zst",
            hour_time.format("%Y%m%dT%H"),
            self.run_id
        );
        let path = self.dir.join(name);
        let file = OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&path)
            .with_context(|| format!("create {}", path.display()))?;
        let buffered = BufWriter::with_capacity(1 << 20, file);
        self.encoder = Some(Encoder::new(buffered, 3)?);
        self.hour = hour;
        Ok(())
    }

    fn flush(&mut self) -> Result<()> {
        if let Some(encoder) = self.encoder.as_mut() {
            encoder.flush()?;
        }
        Ok(())
    }

    fn finish(&mut self) -> Result<()> {
        if let Some(encoder) = self.encoder.take() {
            encoder.finish()?;
        }
        Ok(())
    }
}

#[tokio::main]
async fn main() -> Result<()> {
    CryptoProvider::install_default(aws_lc_rs::default_provider()).ok();

    let url = env::var("GRPC_URL").context("GRPC_URL is required")?;
    let token = env::var("GRPC_TOKEN")
        .ok()
        .filter(|value| !value.is_empty());
    let minutes: u64 = env::var("CAPTURE_MINUTES")
        .ok()
        .and_then(|value| value.parse().ok())
        .unwrap_or(60);
    let out = env::var("CAPTURE_OUT").unwrap_or_else(|_| "../data/raw/live".to_string());

    let deadline = if minutes == 0 {
        None
    } else {
        Some(Instant::now() + Duration::from_secs(minutes * 60))
    };

    let out_path = PathBuf::from(out);
    let mut writer = Writer::new(out_path.clone())?;
    let checkpoint = out_path.join("checkpoint");
    let mut last_slot = read_checkpoint(&checkpoint).unwrap_or(0);

    loop {
        let result = run_session(
            &url,
            token.clone(),
            &mut writer,
            deadline,
            &mut last_slot,
            &checkpoint,
        )
        .await;
        write_checkpoint(&checkpoint, last_slot)?;
        match result {
            Ok(true) => break,
            Ok(false) => eprintln!("stream ended; reconnecting"),
            Err(error) => eprintln!("session error: {error:#}; reconnecting"),
        }
        if deadline.is_some_and(|deadline| Instant::now() >= deadline) {
            break;
        }
        tokio::time::sleep(Duration::from_secs(5)).await;
    }

    write_checkpoint(&checkpoint, last_slot)?;
    writer.finish()?;
    eprintln!(
        "capture finished: {} lines, {} raw bytes",
        writer.lines, writer.raw_bytes
    );
    Ok(())
}

fn read_checkpoint(path: &Path) -> Option<u64> {
    fs::read_to_string(path).ok()?.trim().parse().ok()
}

fn write_checkpoint(path: &Path, slot: u64) -> Result<()> {
    let tmp = path.with_extension("tmp");
    fs::write(&tmp, format!("{slot}\n")).with_context(|| format!("write {}", tmp.display()))?;
    fs::rename(&tmp, path).with_context(|| format!("rename {}", path.display()))?;
    Ok(())
}

async fn run_session(
    url: &str,
    token: Option<String>,
    writer: &mut Writer,
    deadline: Option<Instant>,
    last_slot: &mut u64,
    checkpoint: &Path,
) -> Result<bool> {
    let mut client = GeyserGrpcBuilder::from_shared(url.to_string())?
        .x_token(token)?
        .timeout(Duration::from_secs(30))
        .buffer_size(Some(64 * 1024 * 1024))
        .max_decoding_message_size(128 * 1024 * 1024)
        .tls_config(ClientTlsConfig::new().with_native_roots())?
        .connect()
        .await?;

    let request = SubscribeRequest {
        transactions: HashMap::from([(
            "pumpfun".to_string(),
            SubscribeRequestFilterTransactions {
                vote: Some(false),
                failed: Some(false),
                signature: None,
                account_include: vec![PUMPFUN_PROGRAM.to_string()],
                account_exclude: vec![],
                account_required: vec![],
            },
        )]),
        blocks_meta: HashMap::from([("blocks".to_string(), SubscribeRequestFilterBlocksMeta {})]),
        commitment: Some(COMMITMENT_CONFIRMED),
        from_slot: (*last_slot > 8).then_some(*last_slot - 8),
        ..Default::default()
    };

    let (_, mut stream) = client.subscribe_with_request(Some(request)).await?;
    let mut stats = Stats::default();
    let mut last_log = Instant::now();
    let mut last_checkpoint = Instant::now();
    let mut shutdown = Box::pin(tokio::signal::ctrl_c());

    loop {
        tokio::select! {
            _ = &mut shutdown => {
                writer.flush()?;
                write_checkpoint(checkpoint, *last_slot)?;
                log_stats(&stats, writer);
                return Ok(true);
            }
            _ = tokio::time::sleep(Duration::from_millis(250)) => {
                if deadline.is_some_and(|deadline| Instant::now() >= deadline) {
                    writer.flush()?;
                    write_checkpoint(checkpoint, *last_slot)?;
                    log_stats(&stats, writer);
                    return Ok(true);
                }
                writer.flush()?;
                if last_checkpoint.elapsed() >= Duration::from_secs(5) {
                    write_checkpoint(checkpoint, *last_slot)?;
                    last_checkpoint = Instant::now();
                }
                if last_log.elapsed() >= Duration::from_secs(10) {
                    log_stats(&stats, writer);
                    last_log = Instant::now();
                }
            }
            message = stream.next() => {
                match message {
                    Some(Ok(update)) => handle_update(update, writer, &mut stats, last_slot)?,
                    Some(Err(error)) => return Err(anyhow::anyhow!("stream error: {error}")),
                    None => return Ok(false),
                }
            }
        }
    }
}

fn log_stats(stats: &Stats, writer: &Writer) {
    let mut top_discriminators: Vec<_> = stats.discriminators.iter().collect();
    top_discriminators.sort_by(|a, b| b.1.cmp(a.1));
    let discriminators = top_discriminators
        .iter()
        .take(6)
        .map(|(disc, count)| format!("{}:{count}", hex(*disc)))
        .collect::<Vec<_>>()
        .join(",");

    let mut top_programs: Vec<_> = stats.programs.iter().collect();
    top_programs.sort_by(|a, b| b.1.cmp(a.1));
    let programs = top_programs
        .iter()
        .take(6)
        .map(|(program, count)| format!("{}:{count}", &program[..program.len().min(10)]))
        .collect::<Vec<_>>()
        .join(",");

    eprintln!(
        "txs={} launches={} trades={} migrations={} blocks={} decode_errors={} (create_args={} missing={} sol={} base={} quote={}) zero_delta={} event_cpis={} ignored={} lines={} raw_mb={:.1} disc=[{discriminators}] programs=[{programs}]",
        stats.txs,
        stats.launches,
        stats.trades,
        stats.migrations,
        stats.blocks,
        stats.decode_errors,
        stats.err_create_args,
        stats.err_missing,
        stats.err_sol,
        stats.err_base,
        stats.err_quote,
        stats.zero_delta,
        stats.event_cpis,
        stats.ignored,
        writer.lines,
        writer.raw_bytes as f64 / 1_000_000.0
    );
    if !stats.failure_samples.is_empty() {
        eprintln!("failure samples: {:?}", stats.failure_samples);
    }
    if !stats.unknown_samples.is_empty() {
        eprintln!("unknown samples: {:?}", stats.unknown_samples);
    }
}

fn hex(bytes: &[u8]) -> String {
    const DIGITS: &[u8; 16] = b"0123456789abcdef";
    let mut out = String::with_capacity(bytes.len() * 2);
    for byte in bytes {
        out.push(DIGITS[(byte >> 4) as usize] as char);
        out.push(DIGITS[(byte & 0x0f) as usize] as char);
    }
    out
}

fn handle_update(
    update: SubscribeUpdate,
    writer: &mut Writer,
    stats: &mut Stats,
    last_slot: &mut u64,
) -> Result<()> {
    let created_at = update
        .created_at
        .as_ref()
        .map(|timestamp| timestamp.seconds)
        .unwrap_or(0);

    match update.update_oneof {
        Some(UpdateOneof::Transaction(transaction)) => {
            *last_slot = (*last_slot).max(transaction.slot);
            stats.txs += 1;
            if let Some(info) = transaction.transaction.as_ref() {
                handle_transaction(info, transaction.slot, created_at, writer, stats)?;
            }
        }
        Some(UpdateOneof::BlockMeta(meta)) => {
            *last_slot = (*last_slot).max(meta.slot);
            stats.blocks += 1;
            let block_time = meta
                .block_time
                .as_ref()
                .map(|timestamp| timestamp.timestamp)
                .unwrap_or(0);
            writer.write(&Event::Block {
                slot: meta.slot,
                block_time,
            })?;
        }
        Some(UpdateOneof::Ping(_)) | Some(UpdateOneof::Pong(_)) => {}
        _ => {}
    }

    Ok(())
}

fn handle_transaction(
    info: &SubscribeUpdateTransactionInfo,
    slot: u64,
    created_at: i64,
    writer: &mut Writer,
    stats: &mut Stats,
) -> Result<()> {
    let Some(transaction) = info.transaction.as_ref() else {
        return Ok(());
    };
    let Some(meta) = info.meta.as_ref() else {
        return Ok(());
    };
    let Some(message) = transaction.message.as_ref() else {
        return Ok(());
    };

    let mut keys: Vec<Vec<u8>> = message.account_keys.clone();
    keys.extend(meta.loaded_writable_addresses.iter().cloned());
    keys.extend(meta.loaded_readonly_addresses.iter().cloned());
    let pumpfun_program = bs58::decode(PUMPFUN_PROGRAM)
        .into_vec()
        .expect("valid pumpfun program id");
    let signature = bs58::encode(&info.signature).into_string();
    let tx_index = info.index;

    for (outer_index, instruction) in message.instructions.iter().enumerate() {
        let ix_path = (outer_index as u32) << 16;
        decode_instruction(
            instruction.program_id_index as usize,
            &instruction.accounts,
            &instruction.data,
            ix_path,
            &keys,
            &pumpfun_program,
            meta,
            &signature,
            slot,
            tx_index,
            created_at,
            writer,
            stats,
        )?;
    }

    for inner in &meta.inner_instructions {
        for (inner_index, instruction) in inner.instructions.iter().enumerate() {
            let ix_path = (inner.index << 16) | ((inner_index as u32) + 1);
            decode_instruction(
                instruction.program_id_index as usize,
                &instruction.accounts,
                &instruction.data,
                ix_path,
                &keys,
                &pumpfun_program,
                meta,
                &signature,
                slot,
                tx_index,
                created_at,
                writer,
                stats,
            )?;
        }
    }

    Ok(())
}

#[allow(clippy::too_many_arguments)]
fn decode_instruction(
    program_index: usize,
    account_indices: &[u8],
    data: &[u8],
    ix_path: u32,
    keys: &[Vec<u8>],
    pumpfun_program: &[u8],
    meta: &TransactionStatusMeta,
    signature: &str,
    slot: u64,
    tx_index: u64,
    created_at: i64,
    writer: &mut Writer,
    stats: &mut Stats,
) -> Result<()> {
    if data.len() < 8 {
        return Ok(());
    }
    let Some(program) = keys.get(program_index) else {
        return Ok(());
    };
    *stats.programs.entry(to_base58(program)).or_insert(0) += 1;
    if program.as_slice() != pumpfun_program {
        return Ok(());
    }

    let discriminator: [u8; 8] = data[..8].try_into().expect("checked length");
    *stats.discriminators.entry(discriminator).or_insert(0) += 1;

    // Anchor events are emitted as self-CPIs with this tag, not instructions.
    if discriminator == EVENT_TAG {
        stats.event_cpis += 1;
        return Ok(());
    }

    let account = |position: usize| -> Option<u8> { account_indices.get(position).copied() };
    let key = |position: usize| -> Option<String> {
        account(position).and_then(|index| keys.get(index as usize).map(|key| to_base58(key)))
    };

    if discriminator == *CREATE || discriminator == *CREATE_V2 {
        let (Some(mint), Some(curve)) = (key(0), key(2)) else {
            stats.decode_errors += 1;
            return Ok(());
        };
        let args = match CreateArgs::deserialize(&mut &data[8..]) {
            Ok(args) => args,
            Err(_) => {
                stats.decode_errors += 1;
                stats.err_create_args += 1;
                if stats.failure_samples.len() < 6 {
                    stats.failure_samples.push(format!(
                        "create_args len={} data={}",
                        data.len(),
                        hex(&data[..data.len().min(96)])
                    ));
                }
                return Ok(());
            }
        };
        writer.write(&Event::Launch {
            mint,
            curve,
            creator: to_base58(&args.creator),
            name: args.name,
            symbol: args.symbol,
            uri: args.uri,
            slot,
            tx_index,
            ix_path,
            event_ord: 0,
            sig: signature.to_string(),
            created_at,
        })?;
        stats.launches += 1;
        return Ok(());
    }

    if discriminator == *BUY || discriminator == *SELL || discriminator == *BUY_EXACT_SOL_IN {
        let side = if discriminator == *SELL {
            "sell"
        } else {
            "buy"
        };
        // Base amount comes from the user's associated token account, not the
        // curve vault. The curve vault is created and funded in the same
        // transaction as the first buy, so its transaction-level post balance
        // is the remaining supply, not the amount bought.
        let (Some(mint), Some(curve), Some(user_ata), Some(wallet), Some(curve_index)) =
            (key(2), key(3), account(5), key(6), account(3))
        else {
            stats.decode_errors += 1;
            return Ok(());
        };
        let Some((pre_sol, post_sol)) = sol_pair(meta, curve_index as usize) else {
            stats.decode_errors += 1;
            stats.err_sol += 1;
            return Ok(());
        };
        let Some((pre_base, post_base, base_decimals)) =
            token_pair(meta, user_ata as usize, &mint, &wallet)
        else {
            stats.decode_errors += 1;
            stats.err_base += 1;
            if stats.failure_samples.len() < 6 {
                stats.failure_samples.push(format!(
                    "native_base disc={} user_ata={} mint={} wallet={} pre={:?} post={:?}",
                    hex(&discriminator),
                    user_ata,
                    mint,
                    wallet,
                    meta.pre_token_balances
                        .iter()
                        .map(|balance| balance.account_index)
                        .collect::<Vec<_>>(),
                    meta.post_token_balances
                        .iter()
                        .map(|balance| balance.account_index)
                        .collect::<Vec<_>>(),
                ));
            }
            return Ok(());
        };
        let quote_raw = pre_sol.abs_diff(post_sol);
        let base_raw = pre_base.abs_diff(post_base);
        if quote_raw == 0 || base_raw == 0 {
            stats.zero_delta += 1;
            return Ok(());
        }
        writer.write(&Event::Trade {
            mint,
            wallet,
            curve,
            side,
            base_raw: base_raw.to_string(),
            base_decimals,
            quote_raw: quote_raw.to_string(),
            quote_decimals: 9,
            quote_mint: WSOL_MINT.to_string(),
            quote_kind: "sol",
            slot,
            tx_index,
            ix_path,
            event_ord: 0,
            sig: signature.to_string(),
            created_at,
        })?;
        stats.trades += 1;
        return Ok(());
    }

    let quote_layout = if discriminator == *BUY_V2
        || discriminator == *SELL_V2
        || discriminator == *BUY_EXACT_QUOTE_V2
    {
        Some((
            1usize,
            2usize,
            10usize,
            14usize,
            12usize,
            13usize,
            discriminator == *SELL_V2,
        ))
    } else if discriminator == *BUY_V3
        || discriminator == *SELL_V3
        || discriminator == *BUY_EXACT_QUOTE_V3
    {
        Some((1, 2, 5, 9, 7, 8, discriminator == *SELL_V3))
    } else {
        None
    };

    if let Some((
        base_mint_pos,
        quote_mint_pos,
        curve_pos,
        base_user_pos,
        quote_vault_pos,
        user_pos,
        is_sell,
    )) = quote_layout
    {
        let side = if is_sell { "sell" } else { "buy" };
        let (
            Some(base_mint),
            Some(quote_mint),
            Some(curve),
            Some(wallet),
            Some(base_user),
            Some(quote_vault),
        ) = (
            key(base_mint_pos),
            key(quote_mint_pos),
            key(curve_pos),
            key(user_pos),
            account(base_user_pos),
            account(quote_vault_pos),
        )
        else {
            stats.decode_errors += 1;
            return Ok(());
        };
        // See the native branch: use the user's base token account so a
        // create+buy first fill is measured by what the user received.
        let Some((pre_base, post_base, base_decimals)) =
            token_pair(meta, base_user as usize, &base_mint, &wallet)
        else {
            stats.decode_errors += 1;
            stats.err_base += 1;
            if stats.failure_samples.len() < 6 {
                stats.failure_samples.push(format!(
                    "quote_base disc={} user_ata={} mint={} wallet={} pre={:?} post={:?}",
                    hex(&discriminator),
                    base_user,
                    base_mint,
                    wallet,
                    meta.pre_token_balances
                        .iter()
                        .map(|balance| balance.account_index)
                        .collect::<Vec<_>>(),
                    meta.post_token_balances
                        .iter()
                        .map(|balance| balance.account_index)
                        .collect::<Vec<_>>(),
                ));
            }
            return Ok(());
        };
        let base_raw = pre_base.abs_diff(post_base);
        // SOL-quoted v2/v3 coins keep the quote in native lamports, not a WSOL
        // token account; fall back to the lamport balances when the token
        // balance lookup fails.
        let quote = token_pair(meta, quote_vault as usize, &quote_mint, &curve)
            .map(|(pre, post, decimals)| (pre.abs_diff(post), decimals, quote_kind(&quote_mint)))
            .or_else(|| {
                if quote_mint == WSOL_MINT {
                    sol_pair(meta, quote_vault as usize)
                        .map(|(pre, post)| (pre.abs_diff(post) as u128, 9, "sol"))
                } else {
                    None
                }
            });
        let Some((quote_raw, quote_decimals, kind)) = quote else {
            stats.decode_errors += 1;
            stats.err_quote += 1;
            if stats.failure_samples.len() < 6 {
                stats.failure_samples.push(format!(
                    "quote_quote disc={} vault={} mint={} curve={} pre={:?} post={:?}",
                    hex(&discriminator),
                    quote_vault,
                    quote_mint,
                    curve,
                    meta.pre_token_balances
                        .iter()
                        .map(|balance| balance.account_index)
                        .collect::<Vec<_>>(),
                    meta.post_token_balances
                        .iter()
                        .map(|balance| balance.account_index)
                        .collect::<Vec<_>>(),
                ));
            }
            return Ok(());
        };
        if base_raw == 0 || quote_raw == 0 {
            stats.zero_delta += 1;
            return Ok(());
        }
        writer.write(&Event::Trade {
            mint: base_mint,
            wallet,
            curve,
            side,
            base_raw: base_raw.to_string(),
            base_decimals,
            quote_raw: quote_raw.to_string(),
            quote_decimals,
            quote_mint: quote_mint.clone(),
            quote_kind: kind,
            slot,
            tx_index,
            ix_path,
            event_ord: 0,
            sig: signature.to_string(),
            created_at,
        })?;
        stats.trades += 1;
        return Ok(());
    }

    if discriminator == *MIGRATE {
        let (Some(mint), Some(pool)) = (key(2), key(9)) else {
            stats.decode_errors += 1;
            return Ok(());
        };
        write_migration(
            mint, pool, slot, tx_index, ix_path, signature, created_at, writer,
        )?;
        stats.migrations += 1;
        return Ok(());
    }

    if discriminator == *MIGRATE_V2 {
        let (Some(base_mint), Some(quote_mint), Some(pool)) = (key(2), key(3), key(10)) else {
            stats.decode_errors += 1;
            return Ok(());
        };
        write_migration(
            pick_mint(&base_mint, &quote_mint),
            pool,
            slot,
            tx_index,
            ix_path,
            signature,
            created_at,
            writer,
        )?;
        stats.migrations += 1;
        return Ok(());
    }

    stats.ignored += 1;
    if stats.unknown_samples.len() < 6 {
        stats.unknown_samples.push(hex(&discriminator));
    }

    Ok(())
}

#[allow(clippy::too_many_arguments)]
fn write_migration(
    mint: String,
    pool: String,
    slot: u64,
    tx_index: u64,
    ix_path: u32,
    signature: &str,
    created_at: i64,
    writer: &mut Writer,
) -> Result<()> {
    writer.write(&Event::Migration {
        mint,
        pool,
        slot,
        tx_index,
        ix_path,
        event_ord: 0,
        sig: signature.to_string(),
        created_at,
    })
}

fn pick_mint(base: &str, quote: &str) -> String {
    if base == WSOL_MINT || base == USDC_MINT {
        quote.to_string()
    } else {
        base.to_string()
    }
}

fn quote_kind(mint: &str) -> &'static str {
    if mint == WSOL_MINT {
        "wsol"
    } else if mint == USDC_MINT {
        "usdc"
    } else {
        "other"
    }
}

fn to_base58(key: &[u8]) -> String {
    bs58::encode(key).into_string()
}

fn sol_pair(meta: &TransactionStatusMeta, index: usize) -> Option<(u64, u64)> {
    let pre = meta.pre_balances.get(index).copied()?;
    let post = meta.post_balances.get(index).copied()?;
    Some((pre, post))
}

fn find_balance<'a>(
    balances: &'a [TokenBalance],
    account_index: usize,
    mint: &str,
    owner: &str,
) -> Option<&'a TokenBalance> {
    balances
        .iter()
        .find(|balance| balance.account_index as usize == account_index)
        .or_else(|| {
            balances
                .iter()
                .find(|balance| balance.mint == mint && balance.owner == owner)
        })
}

fn token_pair(
    meta: &TransactionStatusMeta,
    account_index: usize,
    mint: &str,
    owner: &str,
) -> Option<(u128, u128, u32)> {
    let pre = find_balance(&meta.pre_token_balances, account_index, mint, owner);
    let post = find_balance(&meta.post_token_balances, account_index, mint, owner);
    if pre.is_none() && post.is_none() {
        return None;
    }
    // A vault created in the same transaction (first buy) has no pre-balance;
    // a closed account has no post-balance. Treat the missing side as zero.
    let decimals = post
        .or(pre)
        .and_then(|balance| balance.ui_token_amount.as_ref())
        .map(|amount| amount.decimals)
        .unwrap_or(0);
    let pre_raw = pre
        .and_then(|balance| balance.ui_token_amount.as_ref())
        .and_then(|amount| amount.amount.parse::<u128>().ok())
        .unwrap_or(0);
    let post_raw = post
        .and_then(|balance| balance.ui_token_amount.as_ref())
        .and_then(|amount| amount.amount.parse::<u128>().ok())
        .unwrap_or(0);
    Some((pre_raw, post_raw, decimals))
}

// Keep the Message import used even if the proto changes shape.
#[allow(dead_code)]
fn _message_type(_: &Message) {}

#[cfg(test)]
mod tests {
    use super::*;
    use yellowstone_grpc_proto::prelude::{TokenBalance, UiTokenAmount};

    fn balance(
        account_index: u32,
        mint: &str,
        owner: &str,
        amount: &str,
        decimals: u32,
    ) -> TokenBalance {
        TokenBalance {
            account_index,
            mint: mint.to_string(),
            ui_token_amount: Some(UiTokenAmount {
                decimals,
                amount: amount.to_string(),
                ..Default::default()
            }),
            owner: owner.to_string(),
            ..Default::default()
        }
    }

    #[test]
    fn discriminator_matches_public_idl() {
        assert_eq!(hex(&discriminator("buy")), "66063d1201daebea");
        assert_eq!(discriminator("create_v2"), *CREATE_V2);
    }

    #[test]
    fn first_buy_reads_the_user_balance_not_the_curve_remainder() {
        let meta = TransactionStatusMeta {
            post_token_balances: vec![
                balance(4, "mint", "curve", "999964676", 6),
                balance(5, "mint", "wallet", "35324", 6),
            ],
            ..Default::default()
        };
        // The curve vault is created and funded in the create transaction;
        // its post balance is the remaining supply.
        assert_eq!(
            token_pair(&meta, 4, "mint", "curve"),
            Some((0, 999_964_676, 6))
        );
        // The user's post balance is what was actually bought.
        assert_eq!(token_pair(&meta, 5, "mint", "wallet"), Some((0, 35_324, 6)));
    }

    #[test]
    fn token_pair_returns_none_for_an_absent_account() {
        let meta = TransactionStatusMeta::default();
        assert_eq!(token_pair(&meta, 9, "mint", "wallet"), None);
    }

    #[test]
    fn pick_mint_prefers_the_non_quote_side() {
        assert_eq!(pick_mint(WSOL_MINT, "token"), "token");
        assert_eq!(pick_mint("token", WSOL_MINT), "token");
        assert_eq!(pick_mint("token", "other"), "token");
    }

    #[test]
    fn checkpoint_round_trips() {
        let path = std::env::temp_dir().join(format!(
            "sprout-checkpoint-{}-{}",
            std::process::id(),
            chrono::Utc::now().timestamp_nanos_opt().unwrap_or(0)
        ));
        write_checkpoint(&path, 123_456).unwrap();
        assert_eq!(read_checkpoint(&path), Some(123_456));
        let _ = fs::remove_file(&path);
        let _ = fs::remove_file(path.with_extension("tmp"));
    }
}
