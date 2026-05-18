import os
import time
import requests

# ─── CONFIGURACIÓN ────────────────────────────────────────────────────────────
NTFY_TOPIC       = os.environ.get("NTFY_TOPIC",       "listingsniper-atzel")
ETHERSCAN_KEY    = os.environ.get("ETHERSCAN_KEY",    "")
HELIUS_KEY       = os.environ.get("HELIUS_KEY",       "")
PUMP_THRESHOLD   = int(os.environ.get("PUMP_THRESHOLD", "30"))   # % para analizar insiders
SCAN_INTERVAL    = int(os.environ.get("SCAN_INTERVAL",  "60"))   # segundos entre ciclos

# ─── WATCHLIST — tus monedas personales ──────────────────────────────────────
WATCHLIST = [
    {"contract": "9AvytnUKsLxPxFHFqS6VLxaxt5p6BhYNr53SD2Chpump", "chain": "SOL", "name": "TOKEN-1"},
    {"contract": "Dz9mQ9NzkBcCsuGPFJ3r1bS4wgqKMHBPiVuniW8Mbonk",  "chain": "SOL", "name": "TOKEN-2"},
    {"contract": "63LfDmNb3MQ8mw9MtZ2To9bEA2M71kZUUGq5tiJxcqj9",  "chain": "SOL", "name": "TOKEN-3"},
    {"contract": "BFgdzMkTPdKKJeTipv2njtDEwhKxkgFueJQfJGt1jups",  "chain": "SOL", "name": "TOKEN-4"},
    {"contract": "8wXtPeU6557ETkp9WHFY1n1EcU6NxDvbAggHGsMYiHsB",  "chain": "SOL", "name": "TOKEN-5"},
    {"contract": "0xE0f63A424a4439cBE457D80E4f4b51aD25b2c56C",     "chain": "ETH", "name": "SPX6900"},
]

# ─── WALLETS DE EXCHANGES (ETH) ───────────────────────────────────────────────
EXCHANGE_WALLETS_ETH = [
    {"address": "0x75e89d5979E4f6Fba9F97c104c2F0AFB3F1dcB88", "exchange": "MEXC"},
    {"address": "0x6cc5f688a315f3dc28a7781717a9a798a59fda7b", "exchange": "MEXC"},
    {"address": "0xd24400ae8BfEBb18cA49Be86258a3C749cf46853", "exchange": "MEXC"},
    {"address": "0x4976a4a02f38326660d17bf34b431dc6e2eb2327", "exchange": "MEXC"},
    {"address": "0x1ab4973a48dc892cd9971ece8e01dcc7688f8f23", "exchange": "BITGET"},
    {"address": "0x0d0707963952f2fba59dd06f2b425ace40b492fe", "exchange": "BITGET"},
    {"address": "0xf89d7b9c864f589bbf53a82105107622b35eaa40", "exchange": "BYBIT"},
    {"address": "0xbaed383ede0e5d9d72430661f3285daa77e9439f", "exchange": "BYBIT"},
    {"address": "0xa7a93fd0a276fc1c0197a5b5623ed117786eed06", "exchange": "BYBIT"},
    {"address": "0xf977814e90da44bfa03b6295a0616a897441acec", "exchange": "BINANCE"},
    {"address": "0x631fc1ea2270e98fbd9d92658ece0f5a269aa161", "exchange": "BINANCE"},
    {"address": "0x161ba15a5f335c9f06bb5bbb0a9ce14076fbb645", "exchange": "BINANCE"},
    {"address": "0x4b4e14a3773ee558b6597070797fd51eb48606e5", "exchange": "OKX"},
    {"address": "0xa9ac43f5b5e38155a288d1a01d2cbc4478e14573", "exchange": "OKX"},
    {"address": "0xa7efae728d2936e78bda97dc267687568dd593f3", "exchange": "OKX"},
]

# ─── WALLETS DE EXCHANGES (SOL) ───────────────────────────────────────────────
EXCHANGE_WALLETS_SOL = [
    {"address": "ASTyfSima4LLAdDgoFGkgqoKowG1LZFDr9fAQrg7iaJZ", "exchange": "MEXC"},
    {"address": "AC5RDfQFmDS1deWZos921JfqscXdByf8BKHs5ACWjtW2",  "exchange": "BYBIT"},
    {"address": "iGdFcQoyR2MwbXMHQskhmNsqddZ6rinsipHc4TNSdwu",   "exchange": "BYBIT"},
    {"address": "5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9", "exchange": "BINANCE"},
    {"address": "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM",  "exchange": "BINANCE"},
    {"address": "53unSgGWqEWANcPYRF35B2Bgf8BkszUtcccKiXwGGLyr",  "exchange": "BINANCE"},
]

# ─── WALLETS WHALE ────────────────────────────────────────────────────────────
WHALE_WALLETS = [
    {"address": "0xab5801a7d398351b8be11c439e05c5b3259aec9b", "label": "Vitalik.eth",     "chain": "ETH"},
    {"address": "0x220866B1A2219f40e72f5c628B65D54268cA3A9D", "label": "ETH Alpha Whale",  "chain": "ETH"},
    {"address": "0x8894E0a0c962CB723c1976a4421c95949bE2D4E3", "label": "ETH Smart Money",  "chain": "ETH"},
    {"address": "DfXygSm4jCyNCybVYYK6DwvWqjKee8pbDmJGcLWNDXjh", "label": "SOL Smart Money", "chain": "SOL"},
    {"address": "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM",  "label": "SOL Whale Alpha", "chain": "SOL"},
]

# ─── ESTADO GLOBAL ────────────────────────────────────────────────────────────
seen_contracts   = set()   # tokens ya alertados (sniper)
seen_new_pairs   = set()   # pares nuevos ya alertados
seen_whale_moves = set()   # movimientos whale ya alertados
seen_pump_analysis = set() # tokens ya analizados por insider
watchlist_prev   = {}      # liquidez previa para detectar cambios
whale_buys       = {}      # contract -> set de whale addresses (convergencia)
discovered_whales = set()  # wallets descubiertas como insiders recurrentes

# ─── UTILS ────────────────────────────────────────────────────────────────────
def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

def fmt_usd(n):
    if not n or n != n: return "$0"
    if n >= 1e9: return f"${n/1e9:.2f}B"
    if n >= 1e6: return f"${n/1e6:.2f}M"
    if n >= 1e3: return f"${n/1e3:.1f}K"
    return f"${n:.2f}"

def pct(n):
    try:
        v = float(n or 0)
        return f"+{v:.1f}%" if v >= 0 else f"{v:.1f}%"
    except:
        return "0%"

def short(addr):
    return addr[:6] + "..." + addr[-4:] if addr else "—"

# ─── NTFY ─────────────────────────────────────────────────────────────────────
def notify(title, body, priority="default", tags="bell"):
    try:
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=body.encode("utf-8"),
            headers={
                "Title":    title,
                "Priority": priority,
                "Tags":     tags,
            },
            timeout=10,
        )
        log(f"📲 {title}")
    except Exception as e:
        log(f"[ntfy error] {e}")

# ─── SCORE ────────────────────────────────────────────────────────────────────
def compute_score(d):
    s = 50

    liq = d.get("liq", 0)
    vol = d.get("vol", 0)
    ch1h = float(d.get("ch1h", 0) or 0)
    txns = d.get("txns", 0)
    wc   = d.get("wc", 0)
    src  = d.get("src", "")
    chain = d.get("chain", "ETH")
    flow  = d.get("flow", "NEUTRAL")
    accum = d.get("accum", False)
    liqG  = d.get("liqG", 0)
    insiders = d.get("insiders", 0)
    bp    = d.get("bp", 50)
    multi = d.get("multi", False)

    if liq > 200000:   s += 18
    elif liq > 80000:  s += 12
    elif liq > 20000:  s += 5
    else:              s -= 18

    if vol > 500000:   s += 12
    elif vol > 100000: s += 6
    elif vol > 10000:  s += 2
    else:              s -= 8

    if txns > 1000:    s += 10
    elif txns > 300:   s += 5
    elif txns < 30:    s -= 8

    if ch1h > 50:      s -= 10
    elif ch1h > 20:    s -= 4
    elif ch1h > 5:     s += 6
    elif ch1h < -20:   s -= 6

    if wc >= 3:        s += wc * 5
    elif wc >= 2:      s += 10
    elif wc == 1:      s += 5

    if insiders > 0:   s += insiders * 6
    if flow == "OUT":  s += 12
    elif flow == "IN": s -= 10
    if accum:          s += 14
    if liqG > 50:      s += 12
    elif liqG > 25:    s += 6
    if bp > 70:        s += 8
    elif bp < 30:      s -= 8

    bonuses = {"MEXC":8,"BITGET":5,"BYBIT":6,"BINANCE":4,"OKX":4,
               "DEXSCREENER":2,"WHALE":8,"NEW_PAIR":3,"INSIDER":10}
    s += bonuses.get(src, 0)
    if chain == "SOL": s += 4
    if multi:          s += 10

    return max(5, min(95, round(s)))

# ─── DEXSCREENER ──────────────────────────────────────────────────────────────
def get_dex(address, chain):
    chain_id = "solana" if chain == "SOL" else "ethereum"
    try:
        r = requests.get(
            f"https://api.dexscreener.com/latest/dex/tokens/{address}",
            timeout=12
        )
        if not r.ok:
            return None
        data = r.json()
        pairs = [p for p in (data.get("pairs") or []) if p.get("chainId") == chain_id]
        if not pairs:
            pairs = data.get("pairs") or []
        if not pairs:
            return None
        best = sorted(pairs, key=lambda p: p.get("liquidity", {}).get("usd", 0), reverse=True)[0]
        buys  = best.get("txns", {}).get("h24", {}).get("buys",  0)
        sells = best.get("txns", {}).get("h24", {}).get("sells", 0)
        total = buys + sells
        pair  = best.get("pairAddress", "")
        rc    = best.get("chainId", chain_id)
        return {
            "name":   best.get("baseToken", {}).get("symbol", "UNKNOWN"),
            "liq":    best.get("liquidity", {}).get("usd", 0),
            "vol":    best.get("volume",    {}).get("h24", 0),
            "ch1h":   best.get("priceChange", {}).get("h1",  0),
            "ch24h":  best.get("priceChange", {}).get("h24", 0),
            "txns":   total,
            "buys":   buys,
            "sells":  sells,
            "bp":     round((buys / total) * 100) if total > 0 else 50,
            "price":  best.get("priceUsd", "0"),
            "fdv":    best.get("fdv", 0),
            "pair":   pair,
            "url":    f"https://dexscreener.com/{rc}/{pair}" if pair else f"https://dexscreener.com/{chain_id}/{address}",
            "buy_url": f"https://jup.ag/swap/SOL-{address}" if chain == "SOL" else f"https://app.uniswap.org/#/swap?outputCurrency={address}",
        }
    except Exception as e:
        log(f"[dex error] {e}")
        return None

def get_boosted(chain_id):
    try:
        r = requests.get("https://api.dexscreener.com/token-boosts/latest/v1", timeout=12)
        if not r.ok:
            return []
        data = r.json()
        return [t for t in (data if isinstance(data, list) else []) if t.get("chainId") == chain_id][:10]
    except:
        return []

def get_new_token_profiles(chain_id):
    try:
        r = requests.get("https://api.dexscreener.com/token-profiles/latest/v1", timeout=12)
        if not r.ok:
            return []
        data = r.json()
        return [t for t in (data if isinstance(data, list) else []) if t.get("chainId") == chain_id][:15]
    except:
        return []

# ─── ETHERSCAN ────────────────────────────────────────────────────────────────
def get_eth_token_txs(address, key=""):
    try:
        k = key or "YourApiKeyToken"
        r = requests.get(
            f"https://api.etherscan.io/api?module=account&action=tokentx"
            f"&address={address}&sort=desc&page=1&offset=25&apikey={k}",
            timeout=12
        )
        data = r.json()
        return data.get("result", []) if data.get("status") == "1" else []
    except:
        return []

def get_early_buyers(contract, key=""):
    """Obtiene los primeros compradores de un token (pre-pump)."""
    try:
        k = key or "YourApiKeyToken"
        r = requests.get(
            f"https://api.etherscan.io/api?module=account&action=tokentx"
            f"&contractaddress={contract}&sort=asc&page=1&offset=30&apikey={k}",
            timeout=12
        )
        data = r.json()
        if data.get("status") != "1":
            return []
        txs = data.get("result", [])
        buyers = {}
        for tx in txs:
            addr = tx.get("to", "").lower()
            if not addr:
                continue
            if addr not in buyers:
                buyers[addr] = {"address": tx.get("to"), "tx_count": 0, "first_buy": int(tx.get("timeStamp", 0))}
            buyers[addr]["tx_count"] += 1
        return sorted(buyers.values(), key=lambda b: b["first_buy"])[:10]
    except:
        return []

# ─── SOLSCAN / HELIUS ─────────────────────────────────────────────────────────
def get_sol_wallet_transfers(address):
    try:
        if HELIUS_KEY:
            r = requests.get(
                f"https://api.helius.xyz/v0/addresses/{address}/transactions"
                f"?api-key={HELIUS_KEY}&limit=20&type=TRANSFER",
                timeout=12
            )
            if r.ok:
                txs = r.json()
                mints = set()
                for tx in txs:
                    for transfer in tx.get("tokenTransfers", []):
                        mint = transfer.get("mint")
                        if mint:
                            mints.add(mint)
                return list(mints)
        # Fallback: Solscan público
        r = requests.get(
            f"https://public-api.solscan.io/account/splTransfers?account={address}&limit=20",
            headers={"User-Agent": "alpha-terminal-bot/1.0"},
            timeout=12
        )
        if not r.ok:
            return []
        items = r.json().get("data", [])
        return list({item.get("tokenAddress") for item in items if item.get("tokenAddress")})
    except:
        return []

# ─── NOTIFY HELPERS ───────────────────────────────────────────────────────────
def notify_new_token(name, chain, score, dex, source):
    emoji = "🟢" if score >= 70 else "🟡" if score >= 45 else "🔴"
    priority = "urgent" if score >= 70 else "high" if score >= 45 else "default"
    notify(
        f"{emoji} NUEVO TOKEN: {name} ({chain}) — {score}/100",
        f"Fuente: {source}\n"
        f"Liquidez: {fmt_usd(dex['liq'])} | Vol 24h: {fmt_usd(dex['vol'])}\n"
        f"Precio 1h: {pct(dex['ch1h'])} | Buys: {dex['buys']} / Sells: {dex['sells']}\n"
        f"Comprar: {dex['buy_url']}\n"
        f"Chart: {dex['url']}",
        priority=priority,
        tags="rocket" if score >= 70 else "bell",
    )

def notify_whale_move(whale_label, token_name, chain, dex, wc=1, convergence=False):
    if convergence:
        notify(
            f"🐋 x{wc} CONVERGENCIA: {token_name} ({chain})",
            f"{wc} whales compraron el mismo token\n"
            f"Liquidez: {fmt_usd(dex['liq'])} | Vol: {fmt_usd(dex['vol'])}\n"
            f"Precio 1h: {pct(dex['ch1h'])}\n"
            f"Comprar: {dex['buy_url']}\n"
            f"Chart: {dex['url']}",
            priority="urgent",
            tags="rotating_light",
        )
    else:
        notify(
            f"🐋 {whale_label} compró {token_name} ({chain})",
            f"Liquidez: {fmt_usd(dex['liq'])} | Vol: {fmt_usd(dex['vol'])}\n"
            f"Precio 1h: {pct(dex['ch1h'])}\n"
            f"Chart: {dex['url']}",
            priority="high",
            tags="whale",
        )

def notify_exchange_move(exchange, token_name, chain, dex, is_watchlist=False):
    tag = "fire" if is_watchlist else "bell"
    prefix = "📍 WATCHLIST + " if is_watchlist else ""
    notify(
        f"📡 {prefix}{exchange} movió {token_name} ({chain})",
        f"Posible pre-listing detectado\n"
        f"Liquidez: {fmt_usd(dex['liq'])} | Vol: {fmt_usd(dex['vol'])}\n"
        f"Precio 1h: {pct(dex['ch1h'])}\n"
        f"Comprar: {dex['buy_url']}\n"
        f"Chart: {dex['url']}",
        priority="high" if is_watchlist else "default",
        tags=tag,
    )

def notify_watchlist_signal(token_name, chain, signal_type, dex, score):
    emoji = "🟢" if score >= 70 else "🟡" if score >= 45 else "🔴"
    signals = {
        "liq_growth":  ("💧 Liquidez creciendo",  "high",    "chart_with_upwards_trend"),
        "accumulation":("🔮 Acumulación silenciosa","high",   "eyes"),
        "exchange_out":("📤 Retiro de exchanges",  "urgent",  "fire"),
        "pump":        ("🚀 Pump detectado",        "urgent",  "rocket"),
        "whale_in":    ("🐋 Whale compró",          "urgent",  "whale"),
    }
    title_prefix, priority, tags = signals.get(signal_type, ("⚡ Señal", "default", "bell"))
    notify(
        f"{emoji} {title_prefix} en {token_name} ({chain}) — {score}/100",
        f"Liquidez: {fmt_usd(dex['liq'])} | Vol: {fmt_usd(dex['vol'])}\n"
        f"Precio 1h: {pct(dex['ch1h'])} | 24h: {pct(dex['ch24h'])}\n"
        f"Buys: {dex['buys']} / Sells: {dex['sells']}\n"
        f"Comprar: {dex['buy_url']}\n"
        f"Chart: {dex['url']}",
        priority=priority,
        tags=tags,
    )

def notify_insider(token_name, chain, buyers, pump_pct, dex):
    recurrent = [b for b in buyers if b.get("appears_multiple")]
    notify(
        f"🎯 INSIDER detectado: {token_name} ({chain}) +{pump_pct:.0f}%",
        f"{len(buyers)} compradores antes del pump\n"
        f"{'⚠️ ' + str(len(recurrent)) + ' wallet(s) RECURRENTE(S)\n' if recurrent else ''}"
        f"Liquidez: {fmt_usd(dex['liq'])} | Pump 1h: +{pump_pct:.0f}%\n"
        f"Top comprador: {short(buyers[0]['address']) if buyers else '—'}\n"
        f"Chart: {dex['url']}",
        priority="urgent",
        tags="eyes,rotating_light",
    )

# ─── MÓDULO 1: SCAN DE EXCHANGE WALLETS (ETH) ─────────────────────────────────
def scan_exchange_wallets_eth():
    log("── Scan exchange wallets ETH ──")
    watchlist_contracts = {w["contract"].lower(): w for w in WATCHLIST if w["chain"] == "ETH"}

    for wallet in EXCHANGE_WALLETS_ETH:
        txs = get_eth_token_txs(wallet["address"], ETHERSCAN_KEY)
        time.sleep(0.4)
        if not txs:
            continue

        now = time.time()
        recent = [tx for tx in txs if now - int(tx.get("timeStamp", 0)) < 14400]
        contracts = list({tx.get("contractAddress", "").lower() for tx in recent if tx.get("contractAddress")})

        for contract in contracts:
            is_watchlist = contract in watchlist_contracts

            # Si ya fue alertado como nuevo, solo alertar si es watchlist
            if contract in seen_contracts and not is_watchlist:
                continue

            dex = get_dex(contract, "ETH")
            time.sleep(0.4)
            if not dex or dex["liq"] < 5000:
                continue

            # Detectar multi-exchange
            multi = any(
                w["exchange"] != wallet["exchange"] and
                any(tx.get("from", "").lower() == w["address"].lower() or
                    tx.get("to", "").lower()   == w["address"].lower()
                    for tx in recent)
                for w in EXCHANGE_WALLETS_ETH
            )

            token_name = watchlist_contracts[contract]["name"] if is_watchlist else dex["name"]
            score = compute_score({**dex, "src": wallet["exchange"], "chain": "ETH",
                                   "wc": 0, "flow": "NEUTRAL", "accum": False,
                                   "liqG": 0, "multi": multi, "insiders": 0})

            if is_watchlist:
                log(f"📍 Exchange {wallet['exchange']} tocó watchlist: {token_name}")
                notify_exchange_move(wallet["exchange"], token_name, "ETH", dex, is_watchlist=True)
            elif contract not in seen_contracts:
                log(f"📡 Pre-listing {wallet['exchange']}: {dex['name']} (score {score})")
                notify_new_token(dex["name"], "ETH", score, dex, wallet["exchange"])
                seen_contracts.add(contract)

            # Analizar insiders si hay pump
            if float(dex.get("ch1h", 0) or 0) >= PUMP_THRESHOLD:
                analyze_insiders(contract, "ETH", dex)

            time.sleep(0.4)
        time.sleep(0.3)

# ─── MÓDULO 2: SCAN DE EXCHANGE WALLETS (SOL) ────────────────────────────────
def scan_exchange_wallets_sol():
    log("── Scan exchange wallets SOL ──")
    watchlist_mints = {w["contract"]: w for w in WATCHLIST if w["chain"] == "SOL"}

    for wallet in EXCHANGE_WALLETS_SOL:
        mints = get_sol_wallet_transfers(wallet["address"])
        time.sleep(0.5)

        for mint in mints:
            if not mint:
                continue
            is_watchlist = mint in watchlist_mints

            if mint in seen_contracts and not is_watchlist:
                continue

            dex = get_dex(mint, "SOL")
            time.sleep(0.4)
            if not dex or dex["liq"] < 3000:
                continue

            token_name = watchlist_mints[mint]["name"] if is_watchlist else dex["name"]
            score = compute_score({**dex, "src": wallet["exchange"], "chain": "SOL",
                                   "wc": 0, "flow": "NEUTRAL", "accum": False,
                                   "liqG": 0, "multi": False, "insiders": 0})

            if is_watchlist:
                log(f"📍 Exchange {wallet['exchange']} tocó watchlist SOL: {token_name}")
                notify_exchange_move(wallet["exchange"], token_name, "SOL", dex, is_watchlist=True)
            elif mint not in seen_contracts:
                log(f"📡 Pre-listing SOL {wallet['exchange']}: {dex['name']} (score {score})")
                notify_new_token(dex["name"], "SOL", score, dex, wallet["exchange"])
                seen_contracts.add(mint)

            time.sleep(0.4)
        time.sleep(0.4)

# ─── MÓDULO 3: SCAN DE WHALE WALLETS ─────────────────────────────────────────
def scan_whale_wallets():
    log("── Scan whale wallets ──")
    watchlist_eth = {w["contract"].lower(): w for w in WATCHLIST if w["chain"] == "ETH"}
    watchlist_sol = {w["contract"]: w for w in WATCHLIST if w["chain"] == "SOL"}

    for whale in WHALE_WALLETS:
        if whale["chain"] == "ETH":
            txs = get_eth_token_txs(whale["address"], ETHERSCAN_KEY)
            time.sleep(0.4)
            now = time.time()
            recent = [tx for tx in txs if now - int(tx.get("timeStamp", 0)) < 10800]

            for tx in recent[:5]:
                contract = tx.get("contractAddress", "").lower()
                if not contract:
                    continue
                move_key = f"{whale['address']}-{contract}"
                if move_key in seen_whale_moves:
                    continue

                dex = get_dex(contract, "ETH")
                time.sleep(0.35)
                if not dex or dex["liq"] < 5000:
                    continue

                seen_whale_moves.add(move_key)
                is_watchlist = contract in watchlist_eth
                token_name = watchlist_eth[contract]["name"] if is_watchlist else dex["name"]

                # Rastrear convergencia
                if contract not in whale_buys:
                    whale_buys[contract] = set()
                whale_buys[contract].add(whale["address"])
                wc = len(whale_buys[contract])

                log(f"🐋 {whale['label']} compró {token_name} (wc={wc}{'  📍WATCHLIST' if is_watchlist else ''})")

                if wc >= 2:
                    notify_whale_move(whale["label"], token_name, "ETH", dex, wc=wc, convergence=True)
                else:
                    notify_whale_move(whale["label"], token_name, "ETH", dex, wc=1, convergence=False)

                # Señal extra si es de la watchlist
                if is_watchlist:
                    score = compute_score({**dex, "src": "WHALE", "chain": "ETH",
                                           "wc": wc, "flow": "NEUTRAL", "accum": False,
                                           "liqG": 0, "multi": False, "insiders": 0})
                    notify_watchlist_signal(token_name, "ETH", "whale_in", dex, score)

                time.sleep(0.4)

        elif whale["chain"] == "SOL":
            mints = get_sol_wallet_transfers(whale["address"])
            time.sleep(0.5)
            for mint in mints[:5]:
                if not mint:
                    continue
                move_key = f"{whale['address']}-{mint}"
                if move_key in seen_whale_moves:
                    continue
                dex = get_dex(mint, "SOL")
                time.sleep(0.4)
                if not dex or dex["liq"] < 3000:
                    continue
                seen_whale_moves.add(move_key)
                is_watchlist = mint in watchlist_sol
                token_name = watchlist_sol[mint]["name"] if is_watchlist else dex["name"]

                if mint not in whale_buys:
                    whale_buys[mint] = set()
                whale_buys[mint].add(whale["address"])
                wc = len(whale_buys[mint])

                log(f"🐋 SOL {whale['label']} compró {token_name}")
                if wc >= 2:
                    notify_whale_move(whale["label"], token_name, "SOL", dex, wc=wc, convergence=True)
                else:
                    notify_whale_move(whale["label"], token_name, "SOL", dex)

                if is_watchlist:
                    score = compute_score({**dex, "src": "WHALE", "chain": "SOL",
                                           "wc": wc, "flow": "NEUTRAL", "accum": False,
                                           "liqG": 0, "multi": False, "insiders": 0})
                    notify_watchlist_signal(token_name, "SOL", "whale_in", dex, score)
                time.sleep(0.4)
        time.sleep(0.4)

# ─── MÓDULO 4: WATCHLIST MONITORING ──────────────────────────────────────────
def scan_watchlist():
    log("── Scan watchlist ──")
    for token in WATCHLIST:
        dex = get_dex(token["contract"], token["chain"])
        time.sleep(0.5)
        if not dex:
            continue

        name = dex["name"] if dex["name"] != "UNKNOWN" else token["name"]
        prev_liq = watchlist_prev.get(token["contract"], dex["liq"])
        liq_growth = ((dex["liq"] - prev_liq) / prev_liq * 100) if prev_liq > 0 else 0
        flow = "OUT" if dex["buys"] > dex["sells"] * 1.3 else "IN" if dex["sells"] > dex["buys"] * 1.3 else "NEUTRAL"
        accum = abs(float(dex.get("ch1h", 0) or 0)) < 3 and dex["txns"] > 100 and dex["vol"] > 3000
        ch1h = float(dex.get("ch1h", 0) or 0)

        score = compute_score({**dex, "src": "WATCHLIST", "chain": token["chain"],
                                "wc": 0, "flow": flow, "accum": accum,
                                "liqG": liq_growth, "multi": False, "insiders": 0})

        watchlist_prev[token["contract"]] = dex["liq"]

        # Alertas según señal
        sig_key_base = token["contract"] + "-" + str(int(time.time() // 300))

        if liq_growth > 30 and (sig_key_base + "-liq") not in seen_whale_moves:
            seen_whale_moves.add(sig_key_base + "-liq")
            log(f"💧 Watchlist liq+{liq_growth:.0f}%: {name}")
            notify_watchlist_signal(name, token["chain"], "liq_growth", dex, score)

        if accum and (sig_key_base + "-accum") not in seen_whale_moves:
            seen_whale_moves.add(sig_key_base + "-accum")
            log(f"🔮 Watchlist acumulacion: {name}")
            notify_watchlist_signal(name, token["chain"], "accumulation", dex, score)

        if flow == "OUT" and (sig_key_base + "-flow") not in seen_whale_moves:
            seen_whale_moves.add(sig_key_base + "-flow")
            log(f"📤 Watchlist retiro exchanges: {name}")
            notify_watchlist_signal(name, token["chain"], "exchange_out", dex, score)

        if ch1h >= PUMP_THRESHOLD and (sig_key_base + "-pump") not in seen_whale_moves:
            seen_whale_moves.add(sig_key_base + "-pump")
            log(f"🚀 Watchlist pump +{ch1h:.0f}%: {name}")
            notify_watchlist_signal(name, token["chain"], "pump", dex, score)
            if token["chain"] == "ETH":
                analyze_insiders(token["contract"], "ETH", dex)

        time.sleep(0.3)

# ─── MÓDULO 5: NUEVOS TOKENS (DexScreener) ────────────────────────────────────
def scan_new_tokens():
    log("── Scan nuevos tokens ──")
    for chain_id, chain_label in [("ethereum","ETH"), ("solana","SOL")]:
        # Token profiles (más nuevos)
        profiles = get_new_token_profiles(chain_id)
        for profile in profiles:
            addr = profile.get("tokenAddress")
            if not addr or addr in seen_new_pairs:
                continue
            dex = get_dex(addr, chain_label)
            time.sleep(0.4)
            if not dex or dex["liq"] < 3000:
                continue
            seen_new_pairs.add(addr)
            score = compute_score({**dex, "src": "NEW_PAIR", "chain": chain_label,
                                   "wc": 0, "flow": "NEUTRAL", "accum": False,
                                   "liqG": 0, "multi": False, "insiders": 0})
            if score >= 55:
                log(f"⚡ Nuevo token {chain_label}: {dex['name']} (score {score})")
                notify_new_token(dex["name"], chain_label, score, dex, "NEW_PAIR")
            if float(dex.get("ch1h", 0) or 0) >= PUMP_THRESHOLD and chain_label == "ETH":
                analyze_insiders(addr, "ETH", dex)
            time.sleep(0.3)

        # Boosted como complemento
        boosted = get_boosted(chain_id)
        for t in boosted:
            addr = t.get("tokenAddress")
            if not addr or addr in seen_contracts or addr in seen_new_pairs:
                continue
            dex = get_dex(addr, chain_label)
            time.sleep(0.4)
            if not dex or dex["liq"] < (3000 if chain_label == "SOL" else 5000):
                continue
            seen_contracts.add(addr)
            score = compute_score({**dex, "src": "DEXSCREENER", "chain": chain_label,
                                   "wc": 0, "flow": "NEUTRAL", "accum": False,
                                   "liqG": 0, "multi": False, "insiders": 0})
            log(f"🔥 Boosted {chain_label}: {dex['name']} (score {score})")
            notify_new_token(dex["name"], chain_label, score, dex, "DEXSCREENER")
            if float(dex.get("ch1h", 0) or 0) >= PUMP_THRESHOLD and chain_label == "ETH":
                analyze_insiders(addr, "ETH", dex)
            time.sleep(0.3)

# ─── MÓDULO 6: ANÁLISIS DE INSIDERS ──────────────────────────────────────────
def analyze_insiders(contract, chain, dex):
    if contract in seen_pump_analysis:
        return
    seen_pump_analysis.add(contract)
    log(f"🎯 Analizando insiders: {dex['name']}")

    buyers = get_early_buyers(contract, ETHERSCAN_KEY)
    if not buyers:
        return

    # Detectar recurrentes (ya aparecieron en análisis previos)
    for buyer in buyers:
        addr = buyer["address"].lower()
        if addr in discovered_whales:
            buyer["appears_multiple"] = True
        else:
            buyer["appears_multiple"] = False
        discovered_whales.add(addr)

    pump_pct = float(dex.get("ch1h", 0) or 0)
    notify_insider(dex["name"], chain, buyers, pump_pct, dex)

# ─── CICLO PRINCIPAL ──────────────────────────────────────────────────────────
def scan():
    log("═══ Iniciando ciclo completo ═══")
    scan_exchange_wallets_eth()
    scan_exchange_wallets_sol()
    scan_whale_wallets()
    scan_watchlist()
    scan_new_tokens()
    log(f"═══ Ciclo completo. Esperando {SCAN_INTERVAL}s ═══\n")

# ─── INICIO ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    log("🚀 Alpha Terminal Bot iniciado")
    log(f"   Ntfy topic    : {NTFY_TOPIC}")
    log(f"   Etherscan key : {'✓' if ETHERSCAN_KEY else '⚠ sin key (modo lento)'}")
    log(f"   Helius key    : {'✓' if HELIUS_KEY else '⚠ sin key (Solscan público)'}")
    log(f"   Pump threshold: +{PUMP_THRESHOLD}%")
    log(f"   Watchlist     : {len(WATCHLIST)} tokens")
    log(f"   Exchange ETH  : {len(EXCHANGE_WALLETS_ETH)} wallets")
    log(f"   Exchange SOL  : {len(EXCHANGE_WALLETS_SOL)} wallets")
    log(f"   Whales        : {len(WHALE_WALLETS)} wallets")
    log("")

    notify(
        "🚀 Alpha Terminal activo",
        f"Monitoreando:\n"
        f"• {len(WATCHLIST)} tokens en watchlist\n"
        f"• {len(EXCHANGE_WALLETS_ETH)} wallets ETH de exchanges\n"
        f"• {len(EXCHANGE_WALLETS_SOL)} wallets SOL de exchanges\n"
        f"• {len(WHALE_WALLETS)} wallets whale\n"
        f"• Pump threshold: +{PUMP_THRESHOLD}%",
        priority="high",
        tags="white_check_mark",
    )

    while True:
        try:
            scan()
        except Exception as e:
            log(f"[error critico] {e}")
            time.sleep(10)
        time.sleep(SCAN_INTERVAL)
