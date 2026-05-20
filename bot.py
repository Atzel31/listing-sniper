import os
import re
import time
import requests

# ─── CONFIGURACIÓN ────────────────────────────────────────────────────────────
NTFY_TOPIC        = os.environ.get("NTFY_TOPIC",        "listingsniper-atzel")
ETHERSCAN_KEY     = os.environ.get("ETHERSCAN_KEY",     "")
HELIUS_KEY        = os.environ.get("HELIUS_KEY",        "")
PUMP_THRESHOLD    = int(os.environ.get("PUMP_THRESHOLD",    "30"))  # % pump para analizar insiders
SCAN_INTERVAL     = int(os.environ.get("SCAN_INTERVAL",     "60"))  # segundos entre ciclos
MIN_SCORE         = int(os.environ.get("MIN_SCORE",         "55"))  # score minimo para notificar
MIN_LIQUIDITY     = int(os.environ.get("MIN_LIQUIDITY",     "5000"))# liquidez minima USD
MIN_AGE_HOURS     = int(os.environ.get("MIN_AGE_HOURS",     "0"))   # edad minima del par en horas
MAX_AGE_HOURS     = int(os.environ.get("MAX_AGE_HOURS",     "6"))   # edad maxima para "nuevo" token
MIN_BUY_RATIO     = int(os.environ.get("MIN_BUY_RATIO",     "45"))  # % minimo de buys sobre total txns
MULTI_DEX_BONUS   = os.environ.get("MULTI_DEX_BONUS",      "true") == "true"

# ─── WATCHLIST ────────────────────────────────────────────────────────────────
WATCHLIST = [
    {"contract": "9AvytnUKsLxPxFHFqS6VLxaxt5p6BhYNr53SD2Chpump", "chain": "SOL", "name": "TOKEN-1"},
    {"contract": "Dz9mQ9NzkBcCsuGPFJ3r1bS4wgqKMHBPiVuniW8Mbonk",  "chain": "SOL", "name": "TOKEN-2"},
    {"contract": "63LfDmNb3MQ8mw9MtZ2To9bEA2M71kZUUGq5tiJxcqj9",  "chain": "SOL", "name": "TOKEN-3"},
    {"contract": "BFgdzMkTPdKKJeTipv2njtDEwhKxkgFueJQfJGt1jups",  "chain": "SOL", "name": "TOKEN-4"},
    {"contract": "8wXtPeU6557ETkp9WHFY1n1EcU6NxDvbAggHGsMYiHsB",  "chain": "SOL", "name": "TOKEN-5"},
    {"contract": "0xE0f63A424a4439cBE457D80E4f4b51aD25b2c56C",     "chain": "ETH", "name": "SPX6900"},
]

# ─── EXCHANGE WALLETS ETH ─────────────────────────────────────────────────────
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

EXCHANGE_WALLETS_SOL = [
    {"address": "ASTyfSima4LLAdDgoFGkgqoKowG1LZFDr9fAQrg7iaJZ", "exchange": "MEXC"},
    {"address": "AC5RDfQFmDS1deWZos921JfqscXdByf8BKHs5ACWjtW2",  "exchange": "BYBIT"},
    {"address": "iGdFcQoyR2MwbXMHQskhmNsqddZ6rinsipHc4TNSdwu",   "exchange": "BYBIT"},
    {"address": "5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9", "exchange": "BINANCE"},
    {"address": "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM",  "exchange": "BINANCE"},
    {"address": "53unSgGWqEWANcPYRF35B2Bgf8BkszUtcccKiXwGGLyr",  "exchange": "BINANCE"},
]

# Mapa para lookup rapido: address -> exchange
ETH_WALLET_MAP = {w["address"].lower(): w["exchange"] for w in EXCHANGE_WALLETS_ETH}
SOL_WALLET_MAP = {w["address"]: w["exchange"] for w in EXCHANGE_WALLETS_SOL}

WHALE_WALLETS = [
    {"address": "0xab5801a7d398351b8be11c439e05c5b3259aec9b", "label": "Vitalik.eth",     "chain": "ETH"},
    {"address": "0x220866B1A2219f40e72f5c628B65D54268cA3A9D", "label": "ETH Alpha Whale",  "chain": "ETH"},
    {"address": "0x8894E0a0c962CB723c1976a4421c95949bE2D4E3", "label": "ETH Smart Money",  "chain": "ETH"},
    {"address": "DfXygSm4jCyNCybVYYK6DwvWqjKee8pbDmJGcLWNDXjh", "label": "SOL Smart Money", "chain": "SOL"},
    {"address": "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM",  "label": "SOL Whale Alpha", "chain": "SOL"},
]

# ─── ESTADO GLOBAL ────────────────────────────────────────────────────────────
seen_contracts    = set()
seen_new_pairs    = set()
seen_whale_moves  = set()
seen_pump_analysis= set()
seen_signals      = set()
watchlist_prev    = {}
whale_buys        = {}
discovered_whales = set()
# Cache de volumen 5min para detectar aceleracion
vol5m_prev        = {}

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
    return addr[:6] + "..." + addr[-4:] if addr else "?"

def safe_encode(text):
    """Elimina caracteres no-latin1 para headers HTTP."""
    return text.encode("utf-8").decode("latin-1", errors="replace")

def dedup_key(base, window_minutes=5):
    """Genera una key de deduplicacion por ventana de tiempo."""
    return f"{base}-{int(time.time() // (window_minutes * 60))}"

# ─── FILTROS DE CALIDAD ───────────────────────────────────────────────────────
SPAM_PATTERNS = [
    r"^[A-Z]{8,}$",           # Solo mayusculas random tipo XKQZWTFB
    r"^0x[a-fA-F0-9]{6,}$",   # Nombres que son direcciones
    r"^\d+$",                  # Solo numeros
    r"^[A-Z]{1,2}\d+[A-Z]{1,2}$",  # Tipo A1B, Z99X
]

def is_spam_name(name):
    """Detecta nombres de tokens que son spam/bots."""
    if not name or name == "UNKNOWN":
        return True
    for pattern in SPAM_PATTERNS:
        if re.match(pattern, name):
            return True
    return False

def check_honeypot_eth(contract):
    """
    Verifica si un token ETH es honeypot via honeypot.is API.
    Retorna: (is_honeypot: bool, reason: str)
    """
    try:
        r = requests.get(
            f"https://api.honeypot.is/v2/IsHoneypot?address={contract}",
            timeout=8
        )
        if not r.ok:
            return False, "API unavailable"
        data = r.json()
        is_hp = data.get("isHoneypot", False)
        reason = data.get("honeypotReason", "")
        return is_hp, reason
    except:
        return False, "check failed"

def check_contract_verified_eth(contract, api_key=""):
    """Verifica si el contrato esta verificado en Etherscan."""
    try:
        k = api_key or "YourApiKeyToken"
        r = requests.get(
            f"https://api.etherscan.io/api?module=contract&action=getabi"
            f"&address={contract}&apikey={k}",
            timeout=8
        )
        data = r.json()
        return data.get("status") == "1"
    except:
        return False

def detect_multi_dex(pairs, chain_id):
    """Detecta si el token cotiza en multiples DEX."""
    if not pairs:
        return False, []
    chain_pairs = [p for p in pairs if p.get("chainId") == chain_id]
    dex_ids = list({p.get("dexId") for p in chain_pairs if p.get("dexId")})
    return len(dex_ids) >= 2, dex_ids

def detect_volume_acceleration(contract, current_vol5m):
    """
    Detecta si el volumen de los ultimos 5min esta acelerando
    comparado con el ciclo anterior.
    Retorna: (accelerating: bool, change_pct: float)
    """
    prev = vol5m_prev.get(contract, 0)
    vol5m_prev[contract] = current_vol5m
    if prev <= 0 or current_vol5m <= 0:
        return False, 0.0
    change = ((current_vol5m - prev) / prev) * 100
    return change >= 50, change  # 50%+ de aceleracion en 5min

def get_exchange_origin_eth(contract, api_key=""):
    """
    Encuentra que exchange(s) ETH han interactuado con este contrato recientemente.
    Retorna lista de exchanges detectados.
    """
    try:
        k = api_key or "YourApiKeyToken"
        r = requests.get(
            f"https://api.etherscan.io/api?module=account&action=tokentx"
            f"&contractaddress={contract}&sort=desc&page=1&offset=50&apikey={k}",
            timeout=12
        )
        data = r.json()
        if data.get("status") != "1":
            return []
        txs = data.get("result", [])
        found = set()
        for tx in txs:
            from_addr = tx.get("from", "").lower()
            to_addr   = tx.get("to",   "").lower()
            if from_addr in ETH_WALLET_MAP:
                found.add(ETH_WALLET_MAP[from_addr])
            if to_addr in ETH_WALLET_MAP:
                found.add(ETH_WALLET_MAP[to_addr])
        return list(found)
    except:
        return []

def get_exchange_origin_sol(mint):
    """
    Encuentra que exchange(s) SOL han interactuado con este mint.
    """
    found = set()
    for wallet in EXCHANGE_WALLETS_SOL:
        try:
            mints = get_sol_wallet_transfers(wallet["address"])
            if mint in mints:
                found.add(wallet["exchange"])
        except:
            continue
        time.sleep(0.2)
    return list(found)

# ─── SCORE ────────────────────────────────────────────────────────────────────
def compute_score(d):
    s = 50
    liq      = d.get("liq", 0)
    vol      = d.get("vol", 0)
    ch1h     = float(d.get("ch1h", 0) or 0)
    txns     = d.get("txns", 0)
    wc       = d.get("wc", 0)
    src      = d.get("src", "")
    chain    = d.get("chain", "ETH")
    flow     = d.get("flow", "NEUTRAL")
    accum    = d.get("accum", False)
    liqG     = d.get("liqG", 0)
    insiders = d.get("insiders", 0)
    bp       = d.get("bp", 50)
    multi    = d.get("multi", False)
    verified = d.get("verified", False)
    multi_dex= d.get("multi_dex", False)
    vol_accel= d.get("vol_accel", False)
    age_h    = d.get("age_hours", None)

    # Liquidez
    if liq > 200000:      s += 18
    elif liq > 80000:     s += 12
    elif liq > 20000:     s += 5
    else:                 s -= 18

    # Volumen
    if vol > 500000:      s += 12
    elif vol > 100000:    s += 6
    elif vol > 10000:     s += 2
    else:                 s -= 8

    # Actividad
    if txns > 1000:       s += 10
    elif txns > 300:      s += 5
    elif txns < 30:       s -= 8

    # Precio
    if ch1h > 50:         s -= 10
    elif ch1h > 20:       s -= 4
    elif ch1h > 5:        s += 6
    elif ch1h < -20:      s -= 6

    # Whales
    if wc >= 3:           s += wc * 5
    elif wc >= 2:         s += 10
    elif wc == 1:         s += 5

    # Insiders
    if insiders > 0:      s += insiders * 6

    # Flujo exchanges
    if flow == "OUT":     s += 12
    elif flow == "IN":    s -= 10

    # Acumulacion y liquidez
    if accum:             s += 14
    if liqG > 50:         s += 12
    elif liqG > 25:       s += 6

    # Presion compradora
    if bp > 70:           s += 8
    elif bp < 30:         s -= 8

    # Nuevos filtros de calidad
    if verified:          s += 5
    if multi_dex:         s += 8
    if vol_accel:         s += 10
    if age_h is not None:
        if 1 <= age_h <= 6:   s += 6   # nuevo pero no instantaneo
        elif age_h < 1:       s -= 5   # demasiado nuevo, riesgoso
        elif age_h > 48:      s += 3   # establecido

    # Fuente
    bonuses = {
        "MEXC": 8, "BITGET": 5, "BYBIT": 6, "BINANCE": 4, "OKX": 4,
        "DEXSCREENER": 2, "WHALE": 8, "NEW_PAIR": 3, "INSIDER": 10,
    }
    s += bonuses.get(src, 0)
    if chain == "SOL":    s += 4
    if multi:             s += 10

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
        all_pairs = data.get("pairs") or []
        pairs = [p for p in all_pairs if p.get("chainId") == chain_id]
        if not pairs:
            pairs = all_pairs
        if not pairs:
            return None

        best = sorted(pairs, key=lambda p: p.get("liquidity", {}).get("usd", 0), reverse=True)[0]
        buys  = best.get("txns", {}).get("h24", {}).get("buys",  0)
        sells = best.get("txns", {}).get("h24", {}).get("sells", 0)
        total = buys + sells
        vol5m = best.get("volume", {}).get("m5", 0)
        pair  = best.get("pairAddress", "")
        rc    = best.get("chainId", chain_id)

        # Detectar multi-dex
        is_multi_dex, dex_list = detect_multi_dex(all_pairs, chain_id)

        # Edad del par
        created_at = best.get("pairCreatedAt")
        age_hours  = None
        if created_at:
            age_hours = (time.time() - created_at / 1000) / 3600

        return {
            "name":        best.get("baseToken", {}).get("symbol", "UNKNOWN"),
            "liq":         best.get("liquidity", {}).get("usd", 0),
            "vol":         best.get("volume",    {}).get("h24", 0),
            "vol5m":       vol5m,
            "ch5m":        best.get("priceChange", {}).get("m5",  0),
            "ch1h":        best.get("priceChange", {}).get("h1",  0),
            "ch24h":       best.get("priceChange", {}).get("h24", 0),
            "txns":        total,
            "buys":        buys,
            "sells":       sells,
            "bp":          round((buys / total) * 100) if total > 0 else 50,
            "price":       best.get("priceUsd", "0"),
            "fdv":         best.get("fdv", 0),
            "pair":        pair,
            "age_hours":   age_hours,
            "multi_dex":   is_multi_dex,
            "dex_list":    dex_list,
            "vol5m":       vol5m,
            "url":         f"https://dexscreener.com/{rc}/{pair}" if pair else f"https://dexscreener.com/{chain_id}/{address}",
            "buy_url":     f"https://jup.ag/swap/SOL-{address}" if chain == "SOL" else f"https://app.uniswap.org/#/swap?outputCurrency={address}",
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

# ─── ETHERSCAN / SOLSCAN ─────────────────────────────────────────────────────
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
        buyers = {}
        for tx in data.get("result", []):
            addr = tx.get("to", "").lower()
            if not addr:
                continue
            if addr not in buyers:
                buyers[addr] = {"address": tx.get("to"), "tx_count": 0, "first_buy": int(tx.get("timeStamp", 0))}
            buyers[addr]["tx_count"] += 1
        return sorted(buyers.values(), key=lambda b: b["first_buy"])[:10]
    except:
        return []

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

# ─── NTFY ─────────────────────────────────────────────────────────────────────
def notify(title, body, priority="default", tags="bell"):
    try:
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=body.encode("utf-8"),
            headers={
                "Title":        safe_encode(title),
                "Priority":     priority,
                "Tags":         tags,
                "Content-Type": "text/plain; charset=utf-8",
            },
            timeout=10,
        )
        log(f"Notif: {title[:60]}")
    except Exception as e:
        log(f"[ntfy error] {e}")

# ─── NOTIFY HELPERS ───────────────────────────────────────────────────────────
def notify_new_token(name, chain, score, dex, source, extra_info=""):
    if score < MIN_SCORE:
        return
    emoji  = "BAJO RIESGO" if score >= 70 else "MEDIO" if score >= 45 else "ALTO"
    star   = score >= 70
    prio   = "urgent" if score >= 70 else "high" if score >= 45 else "default"
    tags   = "rocket,fire" if star else "bell"
    flags  = []
    if dex.get("multi_dex"):    flags.append("Multi-DEX: " + ", ".join(dex.get("dex_list", [])))
    if dex.get("age_hours"):    flags.append(f"Edad: {dex['age_hours']:.1f}h")
    flags_str = "\n" + " | ".join(flags) if flags else ""
    notify(
        f"NUEVO TOKEN: {name} ({chain}) {score}/100 [{emoji}]",
        f"Fuente: {source}\n"
        f"Liq: {fmt_usd(dex['liq'])} | Vol: {fmt_usd(dex['vol'])}\n"
        f"1h: {pct(dex['ch1h'])} | Buys: {dex['buys']} / Sells: {dex['sells']}\n"
        f"{extra_info}"
        f"{flags_str}\n"
        f"Comprar: {dex['buy_url']}\n"
        f"Chart: {dex['url']}",
        priority=prio, tags=tags,
    )

def notify_whale_move(whale_label, token_name, chain, dex, wc=1, convergence=False):
    if convergence:
        notify(
            f"CONVERGENCIA x{wc} WHALES: {token_name} ({chain})",
            f"{wc} wallets conocidas compraron el mismo token\n"
            f"Liq: {fmt_usd(dex['liq'])} | Vol: {fmt_usd(dex['vol'])}\n"
            f"1h: {pct(dex['ch1h'])} | Buys: {dex['buys']} / Sells: {dex['sells']}\n"
            f"Comprar: {dex['buy_url']}\n"
            f"Chart: {dex['url']}",
            priority="urgent", tags="rotating_light,whale",
        )
    else:
        notify(
            f"WHALE: {whale_label} compro {token_name} ({chain})",
            f"Liq: {fmt_usd(dex['liq'])} | Vol: {fmt_usd(dex['vol'])}\n"
            f"1h: {pct(dex['ch1h'])}\n"
            f"Chart: {dex['url']}",
            priority="high", tags="whale",
        )

def notify_exchange_move(exchange, token_name, chain, dex, is_watchlist=False):
    prio = "high" if is_watchlist else "default"
    prefix = "[WATCHLIST] " if is_watchlist else ""
    notify(
        f"{prefix}EXCHANGE {exchange}: {token_name} ({chain})",
        f"Posible pre-listing detectado\n"
        f"Liq: {fmt_usd(dex['liq'])} | Vol: {fmt_usd(dex['vol'])}\n"
        f"1h: {pct(dex['ch1h'])}\n"
        f"Comprar: {dex['buy_url']}\n"
        f"Chart: {dex['url']}",
        priority=prio, tags="fire" if is_watchlist else "bell",
    )

def notify_watchlist_signal(token_name, chain, signal_type, dex, score, exchange_origin=None):
    if score < MIN_SCORE:
        return
    signals = {
        "liq_growth":   ("Liquidez creciendo",      "high",   "chart_with_upwards_trend"),
        "accumulation": ("Acumulacion silenciosa",   "high",   "eyes"),
        "exchange_out": ("Retiro de exchanges",      "urgent", "fire"),
        "pump":         ("Pump detectado",           "urgent", "rocket"),
        "whale_in":     ("Whale compro",             "urgent", "whale"),
        "vol_accel":    ("Volumen acelerando",       "high",   "zap"),
    }
    label, prio, tags = signals.get(signal_type, ("Senal", "default", "bell"))
    score_str = f"{score}/100"
    origin_str = f"Exchange origen: {', '.join(exchange_origin)}\n" if exchange_origin else ""
    notify(
        f"{label} en {token_name} ({chain}) - {score_str}",
        f"{origin_str}"
        f"Liq: {fmt_usd(dex['liq'])} | Vol: {fmt_usd(dex['vol'])}\n"
        f"1h: {pct(dex['ch1h'])} | 24h: {pct(dex['ch24h'])}\n"
        f"Buys: {dex['buys']} / Sells: {dex['sells']}\n"
        f"Comprar: {dex['buy_url']}\n"
        f"Chart: {dex['url']}",
        priority=prio, tags=tags,
    )

def notify_insider(token_name, chain, buyers, pump_pct, dex):
    recurrent = [b for b in buyers if b.get("appears_multiple")]
    notify(
        f"INSIDER: {token_name} ({chain}) +{pump_pct:.0f}%",
        f"{len(buyers)} compradores antes del pump\n"
        f"{'WALLETS RECURRENTES: ' + str(len(recurrent)) + chr(10) if recurrent else ''}"
        f"Liq: {fmt_usd(dex['liq'])} | Pump 1h: +{pump_pct:.0f}%\n"
        f"Top comprador: {short(buyers[0]['address']) if buyers else '?'}\n"
        f"Chart: {dex['url']}",
        priority="urgent", tags="eyes,rotating_light",
    )

# ─── FILTRO PRINCIPAL DE CALIDAD ──────────────────────────────────────────────
def passes_quality_filter(dex, chain, contract="", check_hp=False, check_verified=False):
    """
    Retorna (passed: bool, reason: str)
    Aplica todos los filtros de calidad en secuencia.
    """
    name = dex.get("name", "")

    # 1. Nombre spam
    if is_spam_name(name):
        return False, f"Nombre spam: {name}"

    # 2. Liquidez minima
    if dex.get("liq", 0) < MIN_LIQUIDITY:
        return False, f"Liquidez insuficiente: {fmt_usd(dex.get('liq', 0))}"

    # 3. Ratio de compras minimo
    bp = dex.get("bp", 50)
    if bp < MIN_BUY_RATIO:
        return False, f"Presion vendedora alta: {bp}% buys"

    # 4. Edad del par
    age = dex.get("age_hours")
    if age is not None:
        if age < MIN_AGE_HOURS:
            return False, f"Par demasiado nuevo: {age:.1f}h"

    # 5. Honeypot (solo ETH, opcional por velocidad)
    if check_hp and chain == "ETH" and contract:
        is_hp, reason = check_honeypot_eth(contract)
        if is_hp:
            return False, f"Honeypot detectado: {reason}"
        time.sleep(0.3)

    return True, "OK"

# ─── MÓDULO 1: EXCHANGE WALLETS ETH ──────────────────────────────────────────
def scan_exchange_wallets_eth():
    log("-- Scan exchange wallets ETH --")
    watchlist_eth = {w["contract"].lower(): w for w in WATCHLIST if w["chain"] == "ETH"}

    for wallet in EXCHANGE_WALLETS_ETH:
        txs = get_eth_token_txs(wallet["address"], ETHERSCAN_KEY)
        time.sleep(0.4)
        if not txs:
            continue

        now    = time.time()
        recent = [tx for tx in txs if now - int(tx.get("timeStamp", 0)) < 14400]
        contracts = list({tx.get("contractAddress", "").lower()
                          for tx in recent if tx.get("contractAddress")})

        for contract in contracts:
            is_watchlist = contract in watchlist_eth
            if contract in seen_contracts and not is_watchlist:
                continue

            dex = get_dex(contract, "ETH")
            time.sleep(0.4)
            if not dex:
                continue

            passed, reason = passes_quality_filter(dex, "ETH", contract, check_hp=True)
            if not passed and not is_watchlist:
                log(f"  Filtrado: {dex.get('name')} — {reason}")
                continue

            multi = any(
                w2["exchange"] != wallet["exchange"] and
                any(tx.get("from", "").lower() == w2["address"].lower() or
                    tx.get("to",   "").lower() == w2["address"].lower()
                    for tx in recent)
                for w2 in EXCHANGE_WALLETS_ETH
            )

            # Detectar exchange de origen
            exchange_origins = get_exchange_origin_eth(contract, ETHERSCAN_KEY)
            time.sleep(0.3)

            # Contrato verificado
            verified = check_contract_verified_eth(contract, ETHERSCAN_KEY)
            time.sleep(0.3)

            dex["verified"]  = verified
            token_name = watchlist_eth[contract]["name"] if is_watchlist else dex["name"]

            score = compute_score({
                **dex, "src": wallet["exchange"], "chain": "ETH",
                "wc": 0, "flow": "NEUTRAL", "accum": False,
                "liqG": 0, "multi": multi, "insiders": 0,
                "verified": verified,
            })

            origin_str = f"Origen: {', '.join(exchange_origins)}" if exchange_origins else ""

            if is_watchlist:
                log(f"WATCHLIST+EXCHANGE: {wallet['exchange']} toco {token_name}")
                notify_exchange_move(wallet["exchange"], token_name, "ETH", dex, is_watchlist=True)
            elif contract not in seen_contracts:
                log(f"Pre-listing {wallet['exchange']}: {dex['name']} score={score}")
                notify_new_token(dex["name"], "ETH", score, dex, wallet["exchange"], origin_str)
                seen_contracts.add(contract)

            if float(dex.get("ch1h", 0) or 0) >= PUMP_THRESHOLD:
                analyze_insiders(contract, "ETH", dex)

            time.sleep(0.4)
        time.sleep(0.3)

# ─── MÓDULO 2: EXCHANGE WALLETS SOL ──────────────────────────────────────────
def scan_exchange_wallets_sol():
    log("-- Scan exchange wallets SOL --")
    watchlist_sol = {w["contract"]: w for w in WATCHLIST if w["chain"] == "SOL"}

    for wallet in EXCHANGE_WALLETS_SOL:
        mints = get_sol_wallet_transfers(wallet["address"])
        time.sleep(0.5)

        for mint in mints:
            if not mint:
                continue
            is_watchlist = mint in watchlist_sol
            if mint in seen_contracts and not is_watchlist:
                continue

            dex = get_dex(mint, "SOL")
            time.sleep(0.4)
            if not dex:
                continue

            passed, reason = passes_quality_filter(dex, "SOL")
            if not passed and not is_watchlist:
                log(f"  Filtrado SOL: {dex.get('name')} — {reason}")
                continue

            token_name = watchlist_sol[mint]["name"] if is_watchlist else dex["name"]
            score = compute_score({
                **dex, "src": wallet["exchange"], "chain": "SOL",
                "wc": 0, "flow": "NEUTRAL", "accum": False,
                "liqG": 0, "multi": False, "insiders": 0,
            })

            if is_watchlist:
                log(f"WATCHLIST+EXCHANGE SOL: {wallet['exchange']} toco {token_name}")
                notify_exchange_move(wallet["exchange"], token_name, "SOL", dex, is_watchlist=True)
            elif mint not in seen_contracts:
                log(f"Pre-listing SOL {wallet['exchange']}: {dex['name']} score={score}")
                notify_new_token(dex["name"], "SOL", score, dex, wallet["exchange"])
                seen_contracts.add(mint)

            time.sleep(0.4)
        time.sleep(0.4)

# ─── MÓDULO 3: WHALE WALLETS ──────────────────────────────────────────────────
def scan_whale_wallets():
    log("-- Scan whale wallets --")
    watchlist_eth = {w["contract"].lower(): w for w in WATCHLIST if w["chain"] == "ETH"}
    watchlist_sol = {w["contract"]: w for w in WATCHLIST if w["chain"] == "SOL"}

    for whale in WHALE_WALLETS:
        if whale["chain"] == "ETH":
            txs  = get_eth_token_txs(whale["address"], ETHERSCAN_KEY)
            time.sleep(0.4)
            now  = time.time()
            recent = [tx for tx in txs if now - int(tx.get("timeStamp", 0)) < 10800]

            for tx in recent[:5]:
                contract  = tx.get("contractAddress", "").lower()
                if not contract:
                    continue
                move_key  = f"{whale['address']}-{contract}"
                if move_key in seen_whale_moves:
                    continue

                dex = get_dex(contract, "ETH")
                time.sleep(0.35)
                if not dex or dex["liq"] < MIN_LIQUIDITY:
                    continue

                # Filtro de calidad basico (sin honeypot para no ralentizar)
                passed, reason = passes_quality_filter(dex, "ETH")
                if not passed:
                    continue

                seen_whale_moves.add(move_key)
                is_watchlist = contract in watchlist_eth
                token_name   = watchlist_eth[contract]["name"] if is_watchlist else dex["name"]

                if contract not in whale_buys:
                    whale_buys[contract] = set()
                whale_buys[contract].add(whale["address"])
                wc = len(whale_buys[contract])

                log(f"WHALE ETH: {whale['label']} -> {token_name} (wc={wc})")

                if wc >= 2:
                    notify_whale_move(whale["label"], token_name, "ETH", dex, wc=wc, convergence=True)
                else:
                    notify_whale_move(whale["label"], token_name, "ETH", dex)

                if is_watchlist:
                    score = compute_score({
                        **dex, "src": "WHALE", "chain": "ETH",
                        "wc": wc, "flow": "NEUTRAL", "accum": False,
                        "liqG": 0, "multi": False, "insiders": 0,
                    })
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
                if not dex or dex["liq"] < MIN_LIQUIDITY:
                    continue

                passed, _ = passes_quality_filter(dex, "SOL")
                if not passed:
                    continue

                seen_whale_moves.add(move_key)
                is_watchlist = mint in watchlist_sol
                token_name   = watchlist_sol[mint]["name"] if is_watchlist else dex["name"]

                if mint not in whale_buys:
                    whale_buys[mint] = set()
                whale_buys[mint].add(whale["address"])
                wc = len(whale_buys[mint])

                log(f"WHALE SOL: {whale['label']} -> {token_name} (wc={wc})")

                if wc >= 2:
                    notify_whale_move(whale["label"], token_name, "SOL", dex, wc=wc, convergence=True)
                else:
                    notify_whale_move(whale["label"], token_name, "SOL", dex)

                if is_watchlist:
                    score = compute_score({
                        **dex, "src": "WHALE", "chain": "SOL",
                        "wc": wc, "flow": "NEUTRAL", "accum": False,
                        "liqG": 0, "multi": False, "insiders": 0,
                    })
                    notify_watchlist_signal(token_name, "SOL", "whale_in", dex, score)

                time.sleep(0.4)
        time.sleep(0.4)

# ─── MÓDULO 4: WATCHLIST ─────────────────────────────────────────────────────
def scan_watchlist():
    log("-- Scan watchlist --")
    for token in WATCHLIST:
        dex = get_dex(token["contract"], token["chain"])
        time.sleep(0.5)
        if not dex:
            continue

        name     = dex["name"] if dex["name"] not in ("UNKNOWN", "") else token["name"]
        contract = token["contract"]
        chain    = token["chain"]

        prev_liq = watchlist_prev.get(contract, dex["liq"])
        liq_growth = ((dex["liq"] - prev_liq) / prev_liq * 100) if prev_liq > 0 else 0
        watchlist_prev[contract] = dex["liq"]

        flow  = ("OUT" if dex["buys"] > dex["sells"] * 1.3
                 else "IN" if dex["sells"] > dex["buys"] * 1.3
                 else "NEUTRAL")
        accum = (abs(float(dex.get("ch1h", 0) or 0)) < 3
                 and dex["txns"] > 100
                 and dex["vol"] > 3000)
        ch1h  = float(dex.get("ch1h", 0) or 0)

        # Aceleracion de volumen 5min
        vol_accel, vol_accel_pct = detect_volume_acceleration(contract, dex.get("vol5m", 0))

        # Score
        score = compute_score({
            **dex, "src": "WATCHLIST", "chain": chain,
            "wc": 0, "flow": flow, "accum": accum,
            "liqG": liq_growth, "multi": False, "insiders": 0,
            "vol_accel": vol_accel,
        })

        # Detectar exchange de origen si hay retiro
        exchange_origins = []
        if flow == "OUT" and chain == "ETH":
            exchange_origins = get_exchange_origin_eth(contract, ETHERSCAN_KEY)
            time.sleep(0.3)

        base = contract
        # Liquidez creciendo
        if liq_growth > 30:
            k = dedup_key(base + "-liq")
            if k not in seen_signals:
                seen_signals.add(k)
                log(f"Watchlist liq+{liq_growth:.0f}%: {name}")
                notify_watchlist_signal(name, chain, "liq_growth", dex, score)

        # Acumulacion silenciosa
        if accum:
            k = dedup_key(base + "-accum")
            if k not in seen_signals:
                seen_signals.add(k)
                log(f"Watchlist acumulacion: {name}")
                notify_watchlist_signal(name, chain, "accumulation", dex, score)

        # Retiro de exchanges
        if flow == "OUT":
            k = dedup_key(base + "-flow")
            if k not in seen_signals:
                seen_signals.add(k)
                log(f"Watchlist retiro exchanges: {name}" +
                    (f" [{', '.join(exchange_origins)}]" if exchange_origins else ""))
                notify_watchlist_signal(name, chain, "exchange_out", dex, score, exchange_origins)

        # Pump
        if ch1h >= PUMP_THRESHOLD:
            k = dedup_key(base + "-pump")
            if k not in seen_signals:
                seen_signals.add(k)
                log(f"Watchlist pump +{ch1h:.0f}%: {name}")
                notify_watchlist_signal(name, chain, "pump", dex, score)
                if chain == "ETH":
                    analyze_insiders(contract, "ETH", dex)

        # Volumen acelerando
        if vol_accel:
            k = dedup_key(base + "-volaccel")
            if k not in seen_signals:
                seen_signals.add(k)
                log(f"Watchlist vol accel +{vol_accel_pct:.0f}% 5min: {name}")
                notify_watchlist_signal(name, chain, "vol_accel", dex, score)

        time.sleep(0.3)

# ─── MÓDULO 5: NUEVOS TOKENS ─────────────────────────────────────────────────
def scan_new_tokens():
    log("-- Scan nuevos tokens --")

    for chain_id, chain_label in [("ethereum", "ETH"), ("solana", "SOL")]:
        min_liq = MIN_LIQUIDITY if chain_label == "ETH" else max(2000, MIN_LIQUIDITY // 2)

        # Token profiles
        profiles = get_new_token_profiles(chain_id)
        for profile in profiles:
            addr = profile.get("tokenAddress")
            if not addr or addr in seen_new_pairs:
                continue

            dex = get_dex(addr, chain_label)
            time.sleep(0.4)
            if not dex or dex["liq"] < min_liq:
                continue

            # Filtro de calidad completo con honeypot para ETH
            check_hp = (chain_label == "ETH")
            passed, reason = passes_quality_filter(dex, chain_label, addr, check_hp=check_hp)
            if not passed:
                log(f"  Filtrado nuevo {chain_label}: {dex.get('name')} — {reason}")
                seen_new_pairs.add(addr)  # No reintentar
                continue

            # Verificar contrato ETH
            verified = False
            if chain_label == "ETH":
                verified = check_contract_verified_eth(addr, ETHERSCAN_KEY)
                time.sleep(0.3)

            # Aceleracion de volumen
            vol_accel, _ = detect_volume_acceleration(addr, dex.get("vol5m", 0))

            dex["verified"] = verified
            score = compute_score({
                **dex, "src": "NEW_PAIR", "chain": chain_label,
                "wc": 0, "flow": "NEUTRAL", "accum": False,
                "liqG": 0, "multi": dex.get("multi_dex", False),
                "insiders": 0, "verified": verified, "vol_accel": vol_accel,
            })

            seen_new_pairs.add(addr)

            if score >= MIN_SCORE:
                # Info extra para la notificacion
                extra = []
                if verified:          extra.append("Contrato verificado")
                if dex.get("multi_dex"): extra.append("Multi-DEX: " + ", ".join(dex.get("dex_list", [])))
                if vol_accel:         extra.append("Volumen acelerando en 5min")
                age = dex.get("age_hours")
                if age is not None:   extra.append(f"Edad del par: {age:.1f}h")
                extra_str = "\n".join(extra) + "\n" if extra else ""

                log(f"Nuevo token {chain_label}: {dex['name']} score={score}")
                notify_new_token(dex["name"], chain_label, score, dex, "NEW_PAIR", extra_str)

            # Analizar insiders si hay pump fuerte
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
            if not dex or dex["liq"] < min_liq:
                continue

            passed, reason = passes_quality_filter(dex, chain_label, addr, check_hp=(chain_label=="ETH"))
            if not passed:
                log(f"  Filtrado boosted: {dex.get('name')} — {reason}")
                seen_contracts.add(addr)
                continue

            vol_accel, _ = detect_volume_acceleration(addr, dex.get("vol5m", 0))
            score = compute_score({
                **dex, "src": "DEXSCREENER", "chain": chain_label,
                "wc": 0, "flow": "NEUTRAL", "accum": False,
                "liqG": 0, "multi": dex.get("multi_dex", False),
                "insiders": 0, "vol_accel": vol_accel,
            })

            seen_contracts.add(addr)

            if score >= MIN_SCORE:
                log(f"Boosted {chain_label}: {dex['name']} score={score}")
                notify_new_token(dex["name"], chain_label, score, dex, "DEXSCREENER")

            if float(dex.get("ch1h", 0) or 0) >= PUMP_THRESHOLD and chain_label == "ETH":
                analyze_insiders(addr, "ETH", dex)

            time.sleep(0.3)

# ─── MÓDULO 6: INSIDERS ───────────────────────────────────────────────────────
def analyze_insiders(contract, chain, dex):
    if contract in seen_pump_analysis:
        return
    seen_pump_analysis.add(contract)
    log(f"Analizando insiders: {dex['name']}")

    buyers = get_early_buyers(contract, ETHERSCAN_KEY)
    if not buyers:
        return

    for buyer in buyers:
        addr = buyer["address"].lower()
        buyer["appears_multiple"] = addr in discovered_whales
        discovered_whales.add(addr)

    pump_pct = float(dex.get("ch1h", 0) or 0)
    notify_insider(dex["name"], chain, buyers, pump_pct, dex)

# ─── CICLO PRINCIPAL ──────────────────────────────────────────────────────────
def scan():
    log("=== Iniciando ciclo completo ===")
    scan_exchange_wallets_eth()
    scan_exchange_wallets_sol()
    scan_whale_wallets()
    scan_watchlist()
    scan_new_tokens()
    log(f"=== Ciclo completo. Esperando {SCAN_INTERVAL}s ===\n")

# ─── INICIO ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    log("Alpha Terminal Bot v2 iniciado")
    log(f"  Ntfy topic     : {NTFY_TOPIC}")
    log(f"  Etherscan key  : {'OK' if ETHERSCAN_KEY else 'sin key (modo lento)'}")
    log(f"  Helius key     : {'OK' if HELIUS_KEY else 'sin key (Solscan publico)'}")
    log(f"  Pump threshold : +{PUMP_THRESHOLD}%")
    log(f"  Score minimo   : {MIN_SCORE}/100")
    log(f"  Liquidez min   : {fmt_usd(MIN_LIQUIDITY)}")
    log(f"  Edad min par   : {MIN_AGE_HOURS}h")
    log(f"  Edad max nuevo : {MAX_AGE_HOURS}h")
    log(f"  Buy ratio min  : {MIN_BUY_RATIO}%")
    log(f"  Watchlist      : {len(WATCHLIST)} tokens")
    log(f"  Exchanges ETH  : {len(EXCHANGE_WALLETS_ETH)} wallets")
    log(f"  Exchanges SOL  : {len(EXCHANGE_WALLETS_SOL)} wallets")
    log(f"  Whales         : {len(WHALE_WALLETS)} wallets")
    log("")

    notify(
        "Alpha Terminal v2 activo",
        f"Bot iniciado con filtros de calidad:\n"
        f"Score minimo: {MIN_SCORE}/100\n"
        f"Liquidez minima: {fmt_usd(MIN_LIQUIDITY)}\n"
        f"Pump threshold: +{PUMP_THRESHOLD}%\n"
        f"Honeypot check: activo\n"
        f"Watchlist: {len(WATCHLIST)} tokens\n"
        f"Exchanges ETH+SOL: {len(EXCHANGE_WALLETS_ETH)+len(EXCHANGE_WALLETS_SOL)} wallets\n"
        f"Whales: {len(WHALE_WALLETS)} wallets",
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
