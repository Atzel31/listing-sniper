import os
import re
import time
import json
import base64
import threading
import requests

# ─── CONFIGURACIÓN ────────────────────────────────────────────────────────────
NTFY_TOPIC      = os.environ.get("NTFY_TOPIC",      "listingsniper-atzel")
ETHERSCAN_KEY   = os.environ.get("ETHERSCAN_KEY",   "")
HELIUS_KEY      = os.environ.get("HELIUS_KEY",      "")
GITHUB_TOKEN    = os.environ.get("GITHUB_TOKEN",    "")
GITHUB_REPO     = os.environ.get("GITHUB_REPO",     "")   # ej: "atzel/listing-sniper"
VERCEL_URL      = os.environ.get("VERCEL_URL",      "")   # ej: "https://alpha-terminal.vercel.app"
PUMP_THRESHOLD  = int(os.environ.get("PUMP_THRESHOLD",  "30"))
SCAN_INTERVAL   = int(os.environ.get("SCAN_INTERVAL",   "60"))
MIN_SCORE       = int(os.environ.get("MIN_SCORE",       "55"))
MIN_LIQUIDITY   = int(os.environ.get("MIN_LIQUIDITY",   "5000"))
MIN_AGE_HOURS   = int(os.environ.get("MIN_AGE_HOURS",   "0"))
MIN_BUY_RATIO   = int(os.environ.get("MIN_BUY_RATIO",   "45"))
ACCUM_EVERY     = int(os.environ.get("ACCUM_EVERY",     "5"))    # ciclos entre scans de acumulacion
WEEKLY_UTC_HOUR = int(os.environ.get("WEEKLY_UTC_HOUR", "13"))   # 13 UTC = 8am Peru
DAILY_UTC_HOUR  = int(os.environ.get("DAILY_UTC_HOUR",  "12"))   # 12 UTC = 7am Peru — resumen diario + forense
FORCE_WEEKLY    = os.environ.get("FORCE_WEEKLY", "false") == "true"
PORT            = int(os.environ.get("PORT", "8080"))
# Filtros reforzados (moderados pero mejores)
MIN_PUMP_PROB   = int(os.environ.get("MIN_PUMP_PROB",   "45"))   # prob minima de pump para notificar nuevos
RUG_LIQ_DROP    = int(os.environ.get("RUG_LIQ_DROP",    "75"))   # % caida de liquidez = rugpull
TRACK_HOURS     = int(os.environ.get("TRACK_HOURS",     "48"))   # horas de seguimiento post-notificacion
# Modulo de insiders / smart money
MAX_TRACKED_WHALES = int(os.environ.get("MAX_TRACKED_WHALES", "20"))  # top wallets a seguir
INSIDER_MIN_TOKENS = int(os.environ.get("INSIDER_MIN_TOKENS", "2"))   # min monedas de la lista para ser smart wallet
FORENSIC_LOOKBACK_H = int(os.environ.get("FORENSIC_LOOKBACK_H", "48"))# ventana antes del pump para buscar insiders
# Modulo de combo y verificacion de listing
COMBO_WINDOW_H  = int(os.environ.get("COMBO_WINDOW_H", "3"))     # horas para apilar senales del mismo token
COMBO_MIN_SCORE = int(os.environ.get("COMBO_MIN_SCORE", "2"))    # min senales apiladas para alerta combo
LISTING_CACHE_MIN = int(os.environ.get("LISTING_CACHE_MIN", "60")) # min entre refrescos de listas de exchanges

# ─── CHAINS ───────────────────────────────────────────────────────────────────
CHAINS = {
    "ETH":  {"dex": "ethereum", "escan": 1},
    "SOL":  {"dex": "solana",   "escan": None},
    "BNB":  {"dex": "bsc",      "escan": 56},
    "BASE": {"dex": "base",     "escan": 8453},
}
BUY_URLS = {
    "solana":   "https://jup.ag/swap/SOL-{c}",
    "ethereum": "https://app.uniswap.org/#/swap?outputCurrency={c}",
    "bsc":      "https://pancakeswap.finance/swap?outputCurrency={c}",
    "base":     "https://app.uniswap.org/#/swap?chain=base&outputCurrency={c}",
}

# ─── LISTA DE ACUMULACIÓN ─────────────────────────────────────────────────────
ACCUMULATION_LIST = [
    {"contract": "0x57e114B691Db790C35207b2e685D4A43181e6061", "chain": "ETH",  "name": "ENA"},
    {"contract": "0xfAbA6f8e4a5E8Ab82F62fe7C39859FA577269BE3", "chain": "ETH",  "name": "ONDO"},
    {"contract": "0x6982508145454Ce325dDbE47a25d4ec3d2311933", "chain": "ETH",  "name": "PEPE"},
    {"contract": "0xE0f63A424a4439cBE457D80E4f4b51aD25b2c56C", "chain": "ETH",  "name": "SPX6900"},
    {"contract": "0x1495bc9e44af1f8bcb62278d2bec4540cf0c05ea", "chain": "ETH",  "name": "DEAI"},
    {"contract": "0x54991328ab43c7d5d31c19d1b9fa048e77b5cd16", "chain": "ETH",  "name": "SOIL"},
    {"contract": "0x1865dc79a9e4b5751531099057d7ee801033d268", "chain": "ETH",  "name": "LKI"},
    {"contract": "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R", "chain": "SOL", "name": "RAY"},
    {"contract": "5UUH9RTDiSpq6HKS6bp4NdU9PNJpXRXuiw6ShBTBhgH2", "chain": "SOL", "name": "TROLL"},
    {"contract": "63LfDmNb3MQ8mw9MtZ2To9bEA2M71kZUUGq5tiJxcqj9", "chain": "SOL", "name": "GIGA"},
    {"contract": "GtDZKAqvMZMnti46ZewMiXCa4oXF4bZxwQPoKzXPFxZn", "chain": "SOL", "name": "NUB"},
    {"contract": "Dz9mQ9NzkBcCsuGPFJ3r1bS4wgqKMHBPiVuniW8Mbonk",  "chain": "SOL", "name": "USELESS"},
    {"contract": "BFgdzMkTPdKKJeTipv2njtDEwhKxkgFueJQfJGt1jups",  "chain": "SOL", "name": "URANUS"},
    {"contract": "9AvytnUKsLxPxFHFqS6VLxaxt5p6BhYNr53SD2Chpump", "chain": "SOL", "name": "67"},
    {"contract": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",  "chain": "SOL", "name": "WIF"},
    {"contract": "0xf4c8e32eadec4bfe97e0f595add0f4450a863a11", "chain": "BNB",  "name": "THE"},
    {"contract": "0x0A43fC31a73013089DF59194872Ecae4cAe14444", "chain": "BNB",  "name": "4"},
    {"contract": "0xAC1Bd2486aAf3B5C0fc3Fd868558b082a531B2B4", "chain": "BASE", "name": "TOSHI"},
    {"contract": "0x532f27101965dd16442E59d40670FaF5eBB142E4", "chain": "BASE", "name": "BRETT"},
]
# Tokens que cotizan principalmente en CEX — via CoinGecko
COINGECKO_TOKENS = [
    {"id": "ronin",   "name": "RON"},
    {"id": "arweave", "name": "AR"},
]

# ─── WATCHLIST (modulo original) ──────────────────────────────────────────────
WATCHLIST = [
    {"contract": "9AvytnUKsLxPxFHFqS6VLxaxt5p6BhYNr53SD2Chpump", "chain": "SOL", "name": "67"},
    {"contract": "Dz9mQ9NzkBcCsuGPFJ3r1bS4wgqKMHBPiVuniW8Mbonk",  "chain": "SOL", "name": "USELESS"},
    {"contract": "63LfDmNb3MQ8mw9MtZ2To9bEA2M71kZUUGq5tiJxcqj9",  "chain": "SOL", "name": "GIGA"},
    {"contract": "BFgdzMkTPdKKJeTipv2njtDEwhKxkgFueJQfJGt1jups",  "chain": "SOL", "name": "URANUS"},
    {"contract": "8wXtPeU6557ETkp9WHFY1n1EcU6NxDvbAggHGsMYiHsB",  "chain": "SOL", "name": "GME"},
    {"contract": "0xE0f63A424a4439cBE457D80E4f4b51aD25b2c56C",     "chain": "ETH", "name": "SPX6900"},
]

# ─── EXCHANGE WALLETS ─────────────────────────────────────────────────────────
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
seen_contracts     = set()
seen_new_pairs     = set()
seen_whale_moves   = set()
seen_pump_analysis = set()
seen_signals       = set()
watchlist_prev     = {}
whale_buys         = {}
discovered_whales  = set()
vol5m_prev         = {}

# Estado del modulo de acumulacion
accum_state        = {}    # symbol -> datos completos
accum_prev         = {}    # symbol -> snapshot anterior (para detectar cambios)
accum_big_buyers   = {}    # wallet -> {"tokens": set, "count": int, "total_usd": float, "last_buy": ts, "buys": int}
week_events        = []    # eventos importantes de la semana
last_weekly_week   = None  # ISO week del ultimo reporte enviado
cycle_count        = 0

# Estado de tracking post-notificacion y deteccion de rugpull
tracked_tokens     = {}    # contract -> {symbol, chain, notified_at, notified_price, notified_liq, max_price, max_mult, pump_prob, source, url, status}
rugged_tokens      = {}    # contract -> {symbol, chain, rugged_at, liq_before, liq_after, was_tracked}
daily_notif_count  = 0     # notificaciones de nuevos tokens hoy
last_daily_day     = None  # dia del ultimo resumen diario

# Estado del modulo de insiders / smart money
smart_wallets      = {}    # address -> {chain, tokens:set, total_usd, buys, insider_score, last_seen, tag, forensic, label}
tracked_whale_set  = {}    # address -> {chain, label, last_check, last_seen_tokens:set} — top wallets en seguimiento activo
forensic_done      = set() # symbols ya analizados forensicamente (para no repetir el mismo dia)
last_forensic_day  = None  # dia del ultimo analisis forense
insider_alerts     = []    # historico de alertas de insiders activos
insider_convergences = {}  # contract -> {symbol, chain, n_insiders, avg_score, holders, detected_at}
insider_sells      = []    # historico de ventas de insiders [{wallet, token, chain, ts, score}]

# Estado de verificacion de listing y combo
exchange_pairs     = {}    # exchange -> set de simbolos listados (spot)
exchange_pairs_ts  = {}    # exchange -> timestamp del ultimo refresco
exchange_futures   = {}    # exchange -> set de simbolos en futuros
exchange_futures_ts= {}    # exchange -> timestamp del ultimo refresco de futuros
korean_seen_notices= set() # IDs de anuncios de Upbit/Bithumb ya vistos
combo_history      = []    # combos que terminaron en pump [{signals, symbol, max_mult, ts}]
my_positions       = {}    # contract -> {symbol, chain, entry_price, entry_ts, peak_price, peak_mult, targets_hit:set, last_price, last_alert_ts}
holder_counts      = {}    # contract -> {symbol, chain, count, ts} para detectar crecimiento
combo_signals      = {}    # contract -> {symbol, chain, signals:{tipo: ts}, first_seen, notified_combo}
signal_outcomes    = []    # [{signals:[tipos], result_pct, max_mult, hour_utc, status}] para win rate por tipo

# ─── UTILS ────────────────────────────────────────────────────────────────────
def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

def fmt_usd(n):
    try:
        n = float(n or 0)
    except:
        return "$0"
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
    return addr[:6] + "..." + addr[-4:] if addr and len(addr) > 12 else (addr or "?")

def safe_encode(text):
    return text.encode("utf-8").decode("latin-1", errors="replace")

def dedup_key(base, window_minutes=5):
    return f"{base}-{int(time.time() // (window_minutes * 60))}"

def iso_week_now():
    t = time.gmtime()
    return f"{t.tm_year}-W{time.strftime('%W', t)}"

# ─── FILTROS DE CALIDAD ───────────────────────────────────────────────────────
SPAM_PATTERNS = [
    r"^[A-Z]{8,}$",
    r"^0x[a-fA-F0-9]{6,}$",
    r"^\d+$",
]

def is_spam_name(name):
    if not name or name == "UNKNOWN":
        return True
    for pattern in SPAM_PATTERNS:
        if re.match(pattern, name):
            return True
    return False

def check_honeypot_eth(contract):
    try:
        r = requests.get(f"https://api.honeypot.is/v2/IsHoneypot?address={contract}", timeout=8)
        if not r.ok:
            return False, "API unavailable"
        data = r.json()
        return data.get("isHoneypot", False), data.get("honeypotReason", "")
    except:
        return False, "check failed"

def check_contract_verified_evm(contract, chain="ETH"):
    try:
        chainid = CHAINS.get(chain, {}).get("escan")
        if not chainid:
            return False
        k = ETHERSCAN_KEY or "YourApiKeyToken"
        r = requests.get(
            f"https://api.etherscan.io/v2/api?chainid={chainid}&module=contract"
            f"&action=getabi&address={contract}&apikey={k}",
            timeout=8
        )
        return r.json().get("status") == "1"
    except:
        return False

def detect_volume_acceleration(contract, current_vol5m):
    prev = vol5m_prev.get(contract, 0)
    vol5m_prev[contract] = current_vol5m
    if prev <= 0 or current_vol5m <= 0:
        return False, 0.0
    change = ((current_vol5m - prev) / prev) * 100
    return change >= 50, change

def passes_quality_filter(dex, chain, contract="", check_hp=False):
    name = dex.get("name", "")
    if is_spam_name(name):
        return False, f"Nombre spam: {name}"
    if dex.get("liq", 0) < MIN_LIQUIDITY:
        return False, f"Liquidez insuficiente: {fmt_usd(dex.get('liq', 0))}"
    if dex.get("bp", 50) < MIN_BUY_RATIO:
        return False, f"Presion vendedora alta: {dex.get('bp')}% buys"
    age = dex.get("age_hours")
    if age is not None and age < MIN_AGE_HOURS:
        return False, f"Par demasiado nuevo: {age:.1f}h"
    # ── Filtros reforzados (moderados pero mejores que los anteriores) ──
    # 1. Volumen/liquidez sano: vol muerto = probable trampa
    liq = dex.get("liq", 1)
    vol = dex.get("vol", 0)
    if liq > 0 and vol / liq < 0.02:
        return False, f"Volumen casi nulo vs liquidez (turnover {vol/liq:.3f})"
    # 2. Liquidez sospechosamente baja para el volumen (posible wash trading/trampa)
    if vol > 0 and liq > 0 and vol / liq > 50:
        return False, f"Volumen irreal vs liquidez (posible wash trading)"
    # 3. Numero minimo de transacciones (evita tokens fantasma)
    if dex.get("txns", 0) < 20:
        return False, f"Muy pocas transacciones: {dex.get('txns', 0)}"
    # 4. Sells = 0 con muchos buys es señal clasica de honeypot (no se puede vender)
    if dex.get("buys", 0) > 30 and dex.get("sells", 0) == 0:
        return False, "Cero ventas con muchas compras (posible honeypot)"
    if check_hp and chain == "ETH" and contract:
        is_hp, reason = check_honeypot_eth(contract)
        if is_hp:
            return False, f"Honeypot: {reason}"
        time.sleep(0.3)
    return True, "OK"

# ─── PROBABILIDAD DE PUMP (0-100%) ───────────────────────────────────────────
def pump_probability(dex):
    """
    Score de PROBABILIDAD DE PUMP, distinto al de riesgo.
    No es prediccion magica: identifica condiciones que suelen PRECEDER
    movimientos. Baja si el pump ya esta ocurriendo (mal punto de entrada).
    Retorna (probabilidad 0-100, factores).
    """
    p = 30
    factors = []
    def add(v, reason):
        nonlocal p
        p += v
        factors.append({"effect": v, "reason": reason})

    liq   = dex.get("liq", 0)
    vol   = dex.get("vol", 0)
    bp    = dex.get("bp", 50)
    ch5m  = float(dex.get("ch5m", 0) or 0)
    ch1h  = float(dex.get("ch1h", 0) or 0)
    ch6h  = float(dex.get("ch6h", 0) or 0)
    txns  = dex.get("txns", 0)
    age   = dex.get("age_hours")
    vol_accel = dex.get("vol_accel", False)
    multi_dex = dex.get("multi_dex", False)

    # Presion compradora — el factor mas importante para un pump temprano
    if bp >= 70:    add(18, f"Presion compradora muy fuerte ({bp}% buys)")
    elif bp >= 60:  add(12, f"Presion compradora alta ({bp}%)")
    elif bp >= 52:  add(5,  f"Mas compras que ventas ({bp}%)")
    elif bp < 45:   add(-12, f"Presion vendedora ({bp}% buys)")

    # Volumen acelerando = interes creciente AHORA
    if vol_accel:   add(15, "Volumen acelerando en 5min")

    # Turnover alto sin que el precio haya volado todavia
    if liq > 0:
        turnover = vol / liq
        if turnover > 2:    add(12, "Turnover muy alto (interes intenso)")
        elif turnover > 0.8: add(7, "Turnover saludable")
        elif turnover < 0.1: add(-10, "Sin interes real (turnover bajo)")

    # Liquidez en zona ideal: ni microscopica (rug) ni gigante (ya despego)
    if 15000 <= liq <= 300000:  add(8, "Liquidez en rango ideal de entrada")
    elif liq < 8000:            add(-10, "Liquidez muy baja (riesgo rug)")
    elif liq > 2000000:         add(-5, "Liquidez muy alta (poco margen)")

    # Actividad
    if txns > 500:   add(8, "Actividad alta")
    elif txns > 150: add(4, "Actividad media")
    elif txns < 40:  add(-6, "Poca actividad")

    # Edad — el sweet spot es joven pero no recien nacido
    if age is not None:
        if 2 <= age <= 24:   add(8, f"Edad ideal ({age:.0f}h)")
        elif age < 1:        add(-12, "Demasiado nuevo (riesgo rug alto)")
        elif age > 72:       add(-4, "Ya no es nuevo")

    # Multi-DEX = mas traccion organica
    if multi_dex:   add(6, "Cotiza en multiples DEX")

    # ── PENALIZACIONES: si el pump YA esta ocurriendo, baja la probabilidad ──
    if ch5m > 15:   add(-15, "Pump explotando AHORA (5min) — entrada tardia")
    if ch1h > 40:   add(-20, "Ya subio +40% en 1h — entrada muy tardia")
    elif ch1h > 20: add(-10, "Ya subio +20% en 1h — entrada tardia")
    elif 3 < ch1h <= 15: add(6, "Momentum iniciando (buena entrada)")
    if ch6h > 80:   add(-12, "Ya hizo +80% en 6h — pico probable")

    return max(2, min(98, round(p))), factors

# ─── TRACKING POST-NOTIFICACIÓN ──────────────────────────────────────────────
def start_tracking(contract, symbol, chain, dex, pump_prob, source):
    """Registra un token al momento de notificarlo para medir su rendimiento."""
    try:
        price = float(dex.get("price", 0) or 0)
    except:
        price = 0
    if contract in tracked_tokens or price <= 0:
        return
    # Etiquetar con las señales activas de este token (para win rate por tipo)
    sig_entry = combo_signals.get(contract.lower(), {})
    active_signals = list(sig_entry.get("signals", {}).keys())
    # La fuente tambien cuenta como "tipo" para el analisis
    signal_tags = active_signals[:]
    if source == "DEXSCREENER":
        signal_tags.append("boosted")
    elif source == "NEW_PAIR":
        signal_tags.append("new_pair")
    elif source in ("MEXC", "BINANCE", "BITGET", "BYBIT", "OKX"):
        signal_tags.append("exchange_wallet")
    if pump_prob >= 60:
        signal_tags.append("high_pump_prob")
    tracked_tokens[contract] = {
        "symbol": symbol, "chain": chain,
        "notified_at": int(time.time()),
        "notified_price": price,
        "notified_liq": dex.get("liq", 0),
        "max_price": price,
        "max_mult": 1.0,
        "pump_prob": pump_prob,
        "source": source,
        "url": dex.get("url", ""),
        "buy_url": dex.get("buy_url", ""),
        "status": "tracking",  # tracking | pumped | rugged | expired
        "result_pct": 0,
        "signal_tags": list(set(signal_tags)),
        "hour_utc": time.gmtime().tm_hour,
        "outcome_recorded": False,
    }
    global daily_notif_count
    daily_notif_count += 1

def record_outcome(t):
    """Guarda el resultado final de un token trackeado para el analisis de win rate."""
    if t.get("outcome_recorded"):
        return
    t["outcome_recorded"] = True
    pumped = t.get("max_mult", 1) >= 1.3
    tags = t.get("signal_tags", [])
    signal_outcomes.append({
        "symbol": t["symbol"],
        "signals": tags,
        "result_pct": t.get("result_pct", 0),
        "max_mult": t.get("max_mult", 1),
        "hour_utc": t.get("hour_utc", 0),
        "status": t.get("status", "expired"),
        "pumped": pumped,
        "ts": int(time.time()),
    })
    # Mantener maximo 500 outcomes
    if len(signal_outcomes) > 500:
        del signal_outcomes[:100]
    # Historico de combos: si tenia 2+ señales reales de combo, guardar el resultado
    combo_tags = [s for s in tags if s in COMBO_WEIGHTS]
    if len(combo_tags) >= 2:
        combo_history.append({
            "symbol": t["symbol"],
            "signals": sorted(combo_tags),
            "combo_key": "+".join(sorted(combo_tags)),
            "max_mult": round(t.get("max_mult", 1), 2),
            "pumped": pumped,
            "ts": int(time.time()),
        })
        if len(combo_history) > 300:
            del combo_history[:50]

def compute_combo_winrate():
    """Calcula que COMBINACIONES de señales aciertan mas, a partir del historico."""
    by_combo = {}
    for c in combo_history:
        key = c["combo_key"]
        d = by_combo.setdefault(key, {"total": 0, "pumped": 0, "best": 1.0, "signals": c["signals"]})
        d["total"] += 1
        if c["pumped"]: d["pumped"] += 1
        d["best"] = max(d["best"], c["max_mult"])
    out = []
    for key, d in by_combo.items():
        out.append({
            "combo": key,
            "signals": d["signals"],
            "total": d["total"],
            "win_rate": round(d["pumped"] / d["total"] * 100) if d["total"] else 0,
            "best_mult": round(d["best"], 2),
        })
    out.sort(key=lambda x: (x["win_rate"], x["total"]), reverse=True)
    return out

def compute_winrate_by_type():
    """Calcula win rate por tipo de señal y por horario a partir de los outcomes."""
    by_signal = {}
    by_hour = {}
    for o in signal_outcomes:
        for s in o["signals"]:
            d = by_signal.setdefault(s, {"total": 0, "pumped": 0, "best": 1.0})
            d["total"] += 1
            if o["pumped"]: d["pumped"] += 1
            d["best"] = max(d["best"], o["max_mult"])
        h = o["hour_utc"]
        dh = by_hour.setdefault(h, {"total": 0, "pumped": 0})
        dh["total"] += 1
        if o["pumped"]: dh["pumped"] += 1
    # Calcular porcentajes
    sig_rates = []
    for s, d in by_signal.items():
        if d["total"] >= 1:
            sig_rates.append({
                "signal": s, "total": d["total"],
                "win_rate": round(d["pumped"] / d["total"] * 100),
                "best_mult": round(d["best"], 2),
            })
    sig_rates.sort(key=lambda x: x["win_rate"], reverse=True)
    hour_rates = []
    for h, d in by_hour.items():
        if d["total"] >= 1:
            hour_rates.append({
                "hour_peru": (h - 5) % 24, "hour_utc": h,
                "total": d["total"],
                "win_rate": round(d["pumped"] / d["total"] * 100),
            })
    hour_rates.sort(key=lambda x: x["win_rate"], reverse=True)
    return sig_rates, hour_rates

def add_position(contract, symbol, chain, entry_price):
    """Marca una moneda como 'estoy dentro' para vigilar la salida."""
    contract = contract.lower()
    my_positions[contract] = {
        "symbol": symbol, "chain": chain,
        "entry_price": float(entry_price),
        "entry_ts": int(time.time()),
        "peak_price": float(entry_price),
        "peak_mult": 1.0,
        "targets_hit": [],
        "last_price": float(entry_price),
        "last_alert_ts": 0,
    }
    log(f"  Posicion agregada: {symbol} @ {entry_price}")
    return my_positions[contract]

def remove_position(contract):
    my_positions.pop(contract.lower(), None)

def monitor_positions():
    """
    Vigila las posiciones marcadas 'estoy dentro'.
    Avisa al llegar a multiplos objetivo (x2, x3, x5, x10) o al caer fuerte tras un pico.
    """
    if not my_positions:
        return
    log(f"-- Monitoreando {len(my_positions)} posiciones propias --")
    now = time.time()
    TARGETS = [2, 3, 5, 10]
    for contract, p in list(my_positions.items()):
        chain = p["chain"]
        dex = get_dex(contract, chain)
        time.sleep(0.3)
        if not dex:
            continue
        try:
            cur = float(dex.get("price", 0) or 0)
        except:
            cur = 0
        if cur <= 0 or p["entry_price"] <= 0:
            continue
        p["last_price"] = cur
        mult = cur / p["entry_price"]
        # Actualizar pico
        if cur > p["peak_price"]:
            p["peak_price"] = cur
            p["peak_mult"] = mult

        # 1. Alertas de objetivo alcanzado (x2, x3, x5, x10)
        for tgt in TARGETS:
            if mult >= tgt and tgt not in p["targets_hit"]:
                p["targets_hit"].append(tgt)
                gain_pct = (mult - 1) * 100
                notify(
                    f"OBJETIVO x{tgt}: {p['symbol']} ({chain})",
                    f"Tu posicion en {p['symbol']} alcanzo x{tgt}\n"
                    f"Entrada: {p['entry_price']:.8f}\n"
                    f"Ahora: {cur:.8f} (+{gain_pct:.0f}%)\n"
                    f"Considera tomar ganancias parciales.\n"
                    f"{market_ctx_str()}\n"
                    f"Chart: {dex.get('url','')}",
                    priority="urgent", tags="moneybag,rocket",
                    click_url=VERCEL_URL,
                )
                register_week_event(p["symbol"], "exit_target",
                                    f"{p['symbol']} alcanzo x{tgt} desde tu entrada")

        # 2. Alerta de caida fuerte tras pico (proteccion de ganancias)
        if p["peak_mult"] >= 1.5:  # solo si llego a subir al menos 50%
            drop_from_peak = (1 - cur / p["peak_price"]) * 100
            # Avisar si cae 25%+ desde el pico, max 1 alerta cada 2h
            if drop_from_peak >= 25 and (now - p["last_alert_ts"]) > 7200:
                p["last_alert_ts"] = now
                still_up = (mult - 1) * 100
                notify(
                    f"CAIDA TRAS PICO: {p['symbol']} ({chain}) -{drop_from_peak:.0f}%",
                    f"{p['symbol']} cayo {drop_from_peak:.0f}% desde su pico\n"
                    f"Pico fue: x{p['peak_mult']:.2f}\n"
                    f"Ahora: {'+'if still_up>=0 else ''}{still_up:.0f}% vs tu entrada\n"
                    f"Posible momento de salir para proteger ganancias.\n"
                    f"Chart: {dex.get('url','')}",
                    priority="urgent", tags="warning,chart_with_downwards_trend",
                    click_url=VERCEL_URL,
                )
                register_week_event(p["symbol"], "exit_drop",
                                    f"{p['symbol']} cayo {drop_from_peak:.0f}% desde pico")

def update_tracking():
    """Actualiza el rendimiento de los tokens trackeados y detecta rugpulls."""
    now = time.time()
    to_remove = []
    for contract, t in list(tracked_tokens.items()):
        # Expirar tras TRACK_HOURS
        age_h = (now - t["notified_at"]) / 3600
        if age_h > TRACK_HOURS and t["status"] == "tracking":
            t["status"] = "expired"
            record_outcome(t)
            to_remove.append(contract)
            continue
        if t["status"] not in ("tracking",):
            if age_h > TRACK_HOURS:
                to_remove.append(contract)
            continue

        dex = get_dex(contract, t["chain"])
        time.sleep(0.35)
        if not dex:
            continue

        try:
            cur_price = float(dex.get("price", 0) or 0)
        except:
            cur_price = 0
        cur_liq = dex.get("liq", 0)

        # ── Deteccion de RUGPULL: caida brutal de liquidez ──
        if t["notified_liq"] > 0:
            liq_drop = (1 - cur_liq / t["notified_liq"]) * 100
            if liq_drop >= RUG_LIQ_DROP:
                t["status"] = "rugged"
                t["result_pct"] = -100
                rugged_tokens[contract] = {
                    "symbol": t["symbol"], "chain": t["chain"],
                    "rugged_at": int(now),
                    "liq_before": t["notified_liq"], "liq_after": cur_liq,
                    "liq_drop_pct": round(liq_drop),
                    "was_tracked": True,
                    "hours_after_notif": round(age_h, 1),
                }
                log(f"  RUGPULL detectado: {t['symbol']} — liquidez cayo {liq_drop:.0f}%")
                notify(
                    f"RUGPULL: {t['symbol']} ({t['chain']})",
                    f"Liquidez colapso {liq_drop:.0f}%\n"
                    f"Antes: {fmt_usd(t['notified_liq'])} -> Ahora: {fmt_usd(cur_liq)}\n"
                    f"Habian pasado {age_h:.1f}h desde la alerta\n"
                    f"Marcada y removida del seguimiento.",
                    priority="high", tags="warning,skull",
                )
                register_week_event(t["symbol"], "rugpull",
                                    f"Rugpull {liq_drop:.0f}% caida liquidez, {age_h:.1f}h tras alerta")
                record_outcome(t)
                continue

        # ── Actualizar maximo y multiplicador ──
        if cur_price > t["max_price"]:
            t["max_price"] = cur_price
            if t["notified_price"] > 0:
                t["max_mult"] = cur_price / t["notified_price"]

        if t["notified_price"] > 0:
            t["result_pct"] = round((cur_price / t["notified_price"] - 1) * 100)

        # ── Marcar como "pumped" si alcanzo +30% en algun momento ──
        if t["max_mult"] >= 1.3 and t["status"] == "tracking":
            t["status"] = "pumped"
            mult_str = f"x{t['max_mult']:.2f}" if t["max_mult"] >= 2 else f"+{(t['max_mult']-1)*100:.0f}%"
            log(f"  PUMP confirmado: {t['symbol']} hizo {mult_str} desde la alerta")
            register_week_event(t["symbol"], "pump_confirmed",
                                f"Hizo {mult_str} desde la notificacion ({age_h:.1f}h)")
            record_outcome(t)

    for c in to_remove:
        tracked_tokens.pop(c, None)

# ─── DEXSCREENER ──────────────────────────────────────────────────────────────
def get_dex(address, chain):
    chain_id = CHAINS.get(chain, CHAINS["ETH"])["dex"]
    try:
        r = requests.get(f"https://api.dexscreener.com/latest/dex/tokens/{address}", timeout=12)
        if not r.ok:
            return None
        data = r.json()
        all_pairs = data.get("pairs") or []
        pairs = [p for p in all_pairs if p.get("chainId") == chain_id]
        if not pairs:
            pairs = all_pairs
        if not pairs:
            return None

        best  = sorted(pairs, key=lambda p: p.get("liquidity", {}).get("usd", 0), reverse=True)[0]
        buys  = best.get("txns", {}).get("h24", {}).get("buys",  0)
        sells = best.get("txns", {}).get("h24", {}).get("sells", 0)
        total = buys + sells
        pair  = best.get("pairAddress", "")
        rc    = best.get("chainId", chain_id)

        # Multi-DEX
        chain_pairs = [p for p in all_pairs if p.get("chainId") == rc]
        dex_ids = list({p.get("dexId") for p in chain_pairs if p.get("dexId")})
        multi_dex = len(dex_ids) >= 2

        # Edad
        created_at = best.get("pairCreatedAt")
        age_hours = (time.time() - created_at / 1000) / 3600 if created_at else None

        # Presencia social (proxy de actividad de comunidad/marketing)
        info = best.get("info", {}) or {}
        socials  = info.get("socials", []) or []
        websites = info.get("websites", []) or []
        has_socials = len(socials) > 0 or len(websites) > 0

        buy_url = BUY_URLS.get(rc, BUY_URLS["ethereum"]).format(c=address)

        return {
            "name":       best.get("baseToken", {}).get("symbol", "UNKNOWN"),
            "liq":        best.get("liquidity", {}).get("usd", 0),
            "vol":        best.get("volume",    {}).get("h24", 0),
            "vol5m":      best.get("volume",    {}).get("m5", 0),
            "ch5m":       best.get("priceChange", {}).get("m5",  0),
            "ch1h":       best.get("priceChange", {}).get("h1",  0),
            "ch6h":       best.get("priceChange", {}).get("h6",  0),
            "ch24h":      best.get("priceChange", {}).get("h24", 0),
            "txns":       total,
            "buys":       buys,
            "sells":      sells,
            "bp":         round((buys / total) * 100) if total > 0 else 50,
            "price":      best.get("priceUsd", "0"),
            "fdv":        best.get("fdv", 0),
            "mcap":       best.get("marketCap", 0),
            "pair":       pair,
            "real_chain": rc,
            "age_hours":  age_hours,
            "multi_dex":  multi_dex,
            "dex_list":   dex_ids,
            "has_socials": has_socials,
            "socials_count": len(socials),
            "url":        f"https://dexscreener.com/{rc}/{pair}" if pair else f"https://dexscreener.com/{chain_id}/{address}",
            "buy_url":    buy_url,
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

# ─── COINGECKO (para RON y AR) ────────────────────────────────────────────────
def get_coingecko(coin_id):
    try:
        r = requests.get(
            f"https://api.coingecko.com/api/v3/coins/{coin_id}"
            f"?localization=false&tickers=false&market_data=true"
            f"&community_data=false&developer_data=false",
            timeout=12
        )
        if not r.ok:
            return None
        d = r.json()
        md = d.get("market_data", {})
        return {
            "name":   d.get("symbol", coin_id).upper(),
            "price":  md.get("current_price", {}).get("usd", 0),
            "mcap":   md.get("market_cap", {}).get("usd", 0),
            "vol":    md.get("total_volume", {}).get("usd", 0),
            "ch24h":  md.get("price_change_percentage_24h", 0) or 0,
            "ch7d":   md.get("price_change_percentage_7d", 0) or 0,
            "ch30d":  md.get("price_change_percentage_30d", 0) or 0,
            "ath_change": md.get("ath_change_percentage", {}).get("usd", 0) or 0,
            "url":    f"https://www.coingecko.com/en/coins/{coin_id}",
        }
    except Exception as e:
        log(f"[coingecko error] {e}")
        return None

# ─── CONTEXTO DE MERCADO (BTC verde/rojo) ────────────────────────────────────
_market_ctx = {"ch24h": 0, "ts": 0, "status": "neutral", "btc_price": 0}

def get_market_context():
    """
    Devuelve el contexto de mercado global via BTC. Cache de 5 min.
    Retorna {ch24h, status: 'verde'|'rojo'|'neutral', btc_price, emoji}.
    """
    now = time.time()
    if now - _market_ctx["ts"] < 300 and _market_ctx["ts"] > 0:
        return _market_ctx
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price"
            "?ids=bitcoin&vs_currencies=usd&include_24hr_change=true",
            timeout=10
        )
        if r.ok:
            d = r.json().get("bitcoin", {})
            ch = d.get("usd_24h_change", 0) or 0
            _market_ctx["ch24h"] = round(ch, 1)
            _market_ctx["btc_price"] = d.get("usd", 0)
            _market_ctx["ts"] = now
            if ch >= 1.5:
                _market_ctx["status"] = "verde"
                _market_ctx["emoji"] = "🟢"
            elif ch <= -1.5:
                _market_ctx["status"] = "rojo"
                _market_ctx["emoji"] = "🔴"
            else:
                _market_ctx["status"] = "neutral"
                _market_ctx["emoji"] = "⚪"
    except Exception as e:
        log(f"[market ctx] {e}")
    return _market_ctx

def market_ctx_str():
    """String corto del contexto de mercado para meter en notificaciones."""
    m = get_market_context()
    emoji = m.get("emoji", "⚪")
    return f"Mercado: BTC {pct(m['ch24h'])} 24h {emoji}"


def get_evm_token_txs_v2(address, chain="ETH", by_contract=False, sort="desc", offset=25):
    """Transacciones de token via Etherscan V2 multichain (ETH/BNB/BASE)."""
    try:
        chainid = CHAINS.get(chain, {}).get("escan")
        if not chainid:
            return []
        k = ETHERSCAN_KEY or "YourApiKeyToken"
        param = "contractaddress" if by_contract else "address"
        r = requests.get(
            f"https://api.etherscan.io/v2/api?chainid={chainid}&module=account"
            f"&action=tokentx&{param}={address}&sort={sort}&page=1&offset={offset}&apikey={k}",
            timeout=12
        )
        data = r.json()
        return data.get("result", []) if data.get("status") == "1" else []
    except:
        return []

def get_eth_token_txs(address, key=""):
    return get_evm_token_txs_v2(address, "ETH")

def get_early_buyers(contract, key="", chain="ETH"):
    txs = get_evm_token_txs_v2(contract, chain, by_contract=True, sort="asc", offset=30)
    buyers = {}
    for tx in txs:
        addr = tx.get("to", "").lower()
        if not addr:
            continue
        if addr not in buyers:
            buyers[addr] = {"address": tx.get("to"), "tx_count": 0, "first_buy": int(tx.get("timeStamp", 0))}
        buyers[addr]["tx_count"] += 1
    return sorted(buyers.values(), key=lambda b: b["first_buy"])[:10]

def get_sol_wallet_transfers(address):
    try:
        if HELIUS_KEY:
            r = requests.get(
                f"https://api.helius.xyz/v0/addresses/{address}/transactions"
                f"?api-key={HELIUS_KEY}&limit=20&type=TRANSFER",
                timeout=12
            )
            if r.ok:
                mints = set()
                for tx in r.json():
                    for tr in tx.get("tokenTransfers", []):
                        if tr.get("mint"):
                            mints.add(tr["mint"])
                return list(mints)
        r = requests.get(
            f"https://public-api.solscan.io/account/splTransfers?account={address}&limit=20",
            headers={"User-Agent": "alpha-terminal/1.0"},
            timeout=12
        )
        if not r.ok:
            return []
        return list({i.get("tokenAddress") for i in r.json().get("data", []) if i.get("tokenAddress")})
    except:
        return []

def get_exchange_origin_evm(contract, chain="ETH"):
    txs = get_evm_token_txs_v2(contract, chain, by_contract=True, offset=50)
    found = set()
    for tx in txs:
        fa = tx.get("from", "").lower()
        ta = tx.get("to",   "").lower()
        if fa in ETH_WALLET_MAP: found.add(ETH_WALLET_MAP[fa])
        if ta in ETH_WALLET_MAP: found.add(ETH_WALLET_MAP[ta])
    return list(found)

# ─── VERIFICACIÓN DE LISTING (APIs publicas de exchanges) ────────────────────
def fetch_exchange_pairs(exchange):
    """
    Trae la lista de simbolos listados en un exchange via su API publica.
    Retorna set de simbolos en mayuscula (ej. {'BTC', 'ETH', ...}).
    """
    try:
        symbols = set()
        if exchange == "MEXC":
            r = requests.get("https://api.mexc.com/api/v3/exchangeInfo", timeout=12)
            if r.ok:
                for s in r.json().get("symbols", []):
                    base = s.get("baseAsset", "")
                    if base: symbols.add(base.upper())
        elif exchange == "BINANCE":
            r = requests.get("https://api.binance.com/api/v3/exchangeInfo", timeout=12)
            if r.ok:
                for s in r.json().get("symbols", []):
                    base = s.get("baseAsset", "")
                    if base: symbols.add(base.upper())
        elif exchange == "BITGET":
            r = requests.get("https://api.bitget.com/api/v2/spot/public/symbols", timeout=12)
            if r.ok:
                for s in r.json().get("data", []):
                    base = s.get("baseCoin", "")
                    if base: symbols.add(base.upper())
        elif exchange == "BYBIT":
            r = requests.get("https://api.bybit.com/v5/market/instruments-info?category=spot", timeout=12)
            if r.ok:
                for s in r.json().get("result", {}).get("list", []):
                    base = s.get("baseCoin", "")
                    if base: symbols.add(base.upper())
        elif exchange == "OKX":
            r = requests.get("https://www.okx.com/api/v5/public/instruments?instType=SPOT", timeout=12)
            if r.ok:
                for s in r.json().get("data", []):
                    base = s.get("baseCcy", "")
                    if base: symbols.add(base.upper())
        return symbols
    except Exception as e:
        log(f"[listing {exchange}] {e}")
        return set()

def fetch_exchange_futures(exchange):
    """
    Trae la lista de simbolos en FUTUROS (perpetuos) de un exchange.
    Retorna set de simbolos base en mayuscula.
    """
    try:
        symbols = set()
        if exchange == "MEXC":
            r = requests.get("https://contract.mexc.com/api/v1/contract/detail", timeout=12)
            if r.ok:
                for s in r.json().get("data", []):
                    base = s.get("baseCoin", "")
                    if base: symbols.add(base.upper())
        elif exchange == "BINANCE":
            r = requests.get("https://fapi.binance.com/fapi/v1/exchangeInfo", timeout=12)
            if r.ok:
                for s in r.json().get("symbols", []):
                    base = s.get("baseAsset", "")
                    if base: symbols.add(base.upper())
        elif exchange == "BITGET":
            r = requests.get("https://api.bitget.com/api/v2/mix/market/contracts?productType=usdt-futures", timeout=12)
            if r.ok:
                for s in r.json().get("data", []):
                    base = s.get("baseCoin", "")
                    if base: symbols.add(base.upper())
        elif exchange == "BYBIT":
            r = requests.get("https://api.bybit.com/v5/market/instruments-info?category=linear", timeout=12)
            if r.ok:
                for s in r.json().get("result", {}).get("list", []):
                    base = s.get("baseCoin", "")
                    if base: symbols.add(base.upper())
        elif exchange == "OKX":
            r = requests.get("https://www.okx.com/api/v5/public/instruments?instType=SWAP", timeout=12)
            if r.ok:
                for s in r.json().get("data", []):
                    base = s.get("ctValCcy", "") or s.get("settleCcy", "")
                    # OKX swap: el simbolo base esta en instId tipo "BTC-USDT-SWAP"
                    inst = s.get("instId", "")
                    if inst and "-" in inst:
                        symbols.add(inst.split("-")[0].upper())
        return symbols
    except Exception as e:
        log(f"[futures {exchange}] {e}")
        return set()

def get_exchange_listing(exchange):
    """Devuelve el set de simbolos listados en SPOT, con cache de LISTING_CACHE_MIN minutos."""
    now = time.time()
    last = exchange_pairs_ts.get(exchange, 0)
    if exchange not in exchange_pairs or now - last > LISTING_CACHE_MIN * 60:
        pairs = fetch_exchange_pairs(exchange)
        if pairs:  # solo actualizar si trajo algo
            exchange_pairs[exchange] = pairs
            exchange_pairs_ts[exchange] = now
            log(f"  Listing {exchange} spot: {len(pairs)} simbolos cacheados")
        time.sleep(0.3)
    return exchange_pairs.get(exchange, set())

def get_exchange_futures(exchange):
    """Devuelve el set de simbolos en FUTUROS, con cache."""
    now = time.time()
    last = exchange_futures_ts.get(exchange, 0)
    if exchange not in exchange_futures or now - last > LISTING_CACHE_MIN * 60:
        futs = fetch_exchange_futures(exchange)
        if futs:
            exchange_futures[exchange] = futs
            exchange_futures_ts[exchange] = now
            log(f"  Listing {exchange} futuros: {len(futs)} simbolos cacheados")
        time.sleep(0.3)
    return exchange_futures.get(exchange, set())

def is_listed_on(exchange, symbol):
    """
    Verifica si un simbolo esta listado en SPOT de un exchange.
    Retorna: True (listado spot), False (NO en spot), None (no se pudo verificar).
    """
    if not symbol or symbol == "UNKNOWN":
        return None
    listing = get_exchange_listing(exchange)
    if not listing:
        return None  # no se pudo traer la lista
    return symbol.upper() in listing

def get_listing_status(exchange, symbol):
    """
    Estado de listing completo de un simbolo en un exchange.
    Retorna uno de: 'spot' (ya en spot), 'futures_only' (solo futuros),
    'not_listed' (en nada), o None (no verificable).
    """
    if not symbol or symbol == "UNKNOWN":
        return None
    spot = get_exchange_listing(exchange)
    if not spot:
        return None
    sym = symbol.upper()
    if sym in spot:
        return "spot"
    futures = get_exchange_futures(exchange)
    if sym in futures:
        return "futures_only"
    return "not_listed"

# ─── MONITOR DE ANUNCIOS COREANOS (Upbit / Bithumb) ──────────────────────────
def fetch_upbit_notices():
    """
    Consulta los anuncios oficiales de Upbit buscando nuevos listings.
    Retorna lista de {id, title, symbols:set}.
    """
    out = []
    try:
        # API publica de anuncios de Upbit
        url = "https://api-manager.upbit.com/api/v1/announcements?os=web&page=1&per_page=20&category=trade"
        r = requests.get(url, timeout=12, headers={"Accept": "application/json"})
        if not r.ok:
            return out
        data = r.json().get("data", {})
        notices = data.get("notices", []) if isinstance(data, dict) else []
        for n in notices:
            title = n.get("title", "")
            nid = str(n.get("id", ""))
            # Buscar tickers entre parentesis tipo "(BTC)" o listings de mercado
            syms = set(re.findall(r"\(([A-Z0-9]{2,10})\)", title))
            # Solo anuncios que parecen de listing
            low = title.lower()
            if any(k in low for k in ["디지털 자산 추가", "신규 거래", "market support", "거래 지원", "listing", "추가"]):
                out.append({"id": "upbit-" + nid, "title": title, "symbols": syms})
    except Exception as e:
        log(f"[upbit] {e}")
    return out

def fetch_bithumb_notices():
    """
    Consulta los anuncios oficiales de Bithumb buscando nuevos listings.
    Retorna lista de {id, title, symbols:set}.
    """
    out = []
    try:
        url = "https://api.bithumb.com/v1/notices?count=20"
        r = requests.get(url, timeout=12, headers={"Accept": "application/json"})
        if not r.ok:
            return out
        data = r.json()
        notices = data if isinstance(data, list) else data.get("data", [])
        for n in notices:
            title = n.get("title", "") if isinstance(n, dict) else ""
            nid = str(n.get("id", "") or n.get("pid", "")) if isinstance(n, dict) else ""
            syms = set(re.findall(r"\(([A-Z0-9]{2,10})\)", title))
            low = title.lower()
            if any(k in low for k in ["원화 마켓", "신규", "거래지원", "마켓 추가", "listing", "상장"]):
                out.append({"id": "bithumb-" + nid, "title": title, "symbols": syms})
    except Exception as e:
        log(f"[bithumb] {e}")
    return out

def scan_korean_listings():
    """
    Revisa anuncios de Upbit y Bithumb. Si un token de la watchlist o
    lista de acumulacion aparece en un anuncio nuevo, notifica al instante.
    """
    log("-- Scan anuncios Upbit/Bithumb --")
    # Simbolos que nos importan: watchlist + acumulacion
    watched = {w["name"].upper() for w in WATCHLIST}
    watched |= {t["name"].upper() for t in ACCUMULATION_LIST}

    notices = fetch_upbit_notices() + fetch_bithumb_notices()
    time.sleep(0.3)
    for n in notices:
        if n["id"] in korean_seen_notices:
            continue
        korean_seen_notices.add(n["id"])
        # Coincidencia con nuestros tokens
        matched = n["symbols"] & watched
        exchange = "Upbit" if n["id"].startswith("upbit") else "Bithumb"
        if matched:
            for sym in matched:
                log(f"  LISTING COREANO: {sym} en {exchange}")
                notify(
                    f"LISTING COREANO: {sym} en {exchange}",
                    f"{exchange} anuncio listing de un token de tu lista:\n{sym}\n\n"
                    f"Titulo: {n['title'][:120]}\n\n"
                    f"Los listings en Upbit/Bithumb suelen mover fuerte el precio. "
                    f"Revisa rapido antes de que reaccione el mercado.",
                    priority="urgent", tags="rotating_light,kr,fire",
                    click_url=VERCEL_URL,
                )
                register_week_event(sym, "korean_listing",
                                    f"{exchange} anuncio listing de {sym}")
    # Limpiar IDs viejos para no crecer infinito
    if len(korean_seen_notices) > 500:
        korean_seen_notices.clear()

def get_wallet_portfolio(address, chain="ETH", max_tokens=15):
    """
    Portfolio superficial de una wallet: tokens que ha recibido recientemente
    y que probablemente aun tiene. Usa el historial de transferencias (gratis).
    No es valoracion exacta, es un vistazo de en que esta metida la wallet.
    """
    if CHAINS.get(chain, {}).get("escan") is None:
        return []  # SOL no soportado con APIs gratis de forma confiable
    txs = get_evm_token_txs_v2(address, chain, sort="desc", offset=100)
    if not txs:
        return []
    addr_l = address.lower()
    balances = {}  # contract -> {symbol, net_amount, last_ts}
    for tx in txs:
        c = tx.get("contractAddress", "").lower()
        if not c:
            continue
        sym = tx.get("tokenSymbol", "?")
        try:
            amt = float(tx.get("value", 0)) / (10 ** int(tx.get("tokenDecimal", 18)))
        except:
            continue
        ts = int(tx.get("timeStamp", 0))
        b = balances.setdefault(c, {"symbol": sym, "net": 0.0, "last_ts": ts, "contract": c})
        if tx.get("to", "").lower() == addr_l:
            b["net"] += amt   # recibio
        elif tx.get("from", "").lower() == addr_l:
            b["net"] -= amt   # envio
        b["last_ts"] = max(b["last_ts"], ts)
    # Quedarse con las que tienen balance neto positivo (aun las tiene)
    holding = [v for v in balances.values() if v["net"] > 0]
    holding.sort(key=lambda x: x["last_ts"], reverse=True)
    out = []
    for h in holding[:max_tokens]:
        out.append({
            "symbol": h["symbol"],
            "contract": h["contract"],
            "last_activity": h["last_ts"],
        })
    return out

# ─── NTFY ─────────────────────────────────────────────────────────────────────
def notify(title, body, priority="default", tags="bell", click_url=""):
    try:
        headers = {
            "Title":        safe_encode(title),
            "Priority":     priority,
            "Tags":         tags,
            "Content-Type": "text/plain; charset=utf-8",
        }
        if click_url:
            headers["Click"] = click_url
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=body.encode("utf-8"),
            headers=headers,
            timeout=10,
        )
        log(f"Notif: {title[:60]}")
    except Exception as e:
        log(f"[ntfy error] {e}")

# ─── SCORE ENGINE (sniper) ────────────────────────────────────────────────────
def compute_score(d):
    s = 50
    liq, vol = d.get("liq", 0), d.get("vol", 0)
    ch1h = float(d.get("ch1h", 0) or 0)
    txns, wc = d.get("txns", 0), d.get("wc", 0)
    if liq > 200000: s += 18
    elif liq > 80000: s += 12
    elif liq > 20000: s += 5
    else: s -= 18
    if vol > 500000: s += 12
    elif vol > 100000: s += 6
    elif vol > 10000: s += 2
    else: s -= 8
    if txns > 1000: s += 10
    elif txns > 300: s += 5
    elif txns < 30: s -= 8
    if ch1h > 50: s -= 10
    elif ch1h > 20: s -= 4
    elif ch1h > 5: s += 6
    elif ch1h < -20: s -= 6
    if wc >= 3: s += wc * 5
    elif wc >= 2: s += 10
    elif wc == 1: s += 5
    if d.get("insiders", 0) > 0: s += d["insiders"] * 6
    flow = d.get("flow", "NEUTRAL")
    if flow == "OUT": s += 12
    elif flow == "IN": s -= 10
    if d.get("accum"): s += 14
    liqG = d.get("liqG", 0)
    if liqG > 50: s += 12
    elif liqG > 25: s += 6
    bp = d.get("bp", 50)
    if bp > 70: s += 8
    elif bp < 30: s -= 8
    if d.get("verified"): s += 5
    if d.get("multi_dex"): s += 8
    if d.get("vol_accel"): s += 10
    age = d.get("age_hours")
    if age is not None:
        if 1 <= age <= 6: s += 6
        elif age < 1: s -= 5
        elif age > 48: s += 3
    bonuses = {"MEXC":8,"BITGET":5,"BYBIT":6,"BINANCE":4,"OKX":4,
               "DEXSCREENER":2,"WHALE":8,"NEW_PAIR":3,"INSIDER":10}
    s += bonuses.get(d.get("src", ""), 0)
    if d.get("chain") == "SOL": s += 4
    if d.get("multi"): s += 10
    return max(5, min(95, round(s)))

# ─── SCORE DE ACUMULACIÓN (0-100%) ───────────────────────────────────────────
def accum_score(d):
    """
    Score especifico para acumulacion en mercado bajista.
    Premia: liquidez solida, presion compradora, whales, dip estabilizandose,
    flujo OUT de exchanges, presencia social, actividad de big buyers.
    """
    s = 40
    reasons = []
    def add(v, reason):
        nonlocal s
        s += v
        reasons.append({"effect": v, "reason": reason})

    liq   = d.get("liq", 0)
    vol   = d.get("vol", 0)
    bp    = d.get("bp", 50)
    ch1h  = float(d.get("ch1h", 0) or 0)
    ch24h = float(d.get("ch24h", 0) or 0)
    flow  = d.get("flow", "NEUTRAL")
    wc    = d.get("whale_count", 0)
    bb    = d.get("big_buyers", 0)

    # Liquidez — solidez de la base
    if liq > 1000000:   add(15, "Liquidez muy solida (>$1M)")
    elif liq > 200000:  add(10, "Liquidez solida (>$200K)")
    elif liq > 50000:   add(4,  "Liquidez media")
    elif liq > 0:       add(-12, "Liquidez fragil (<$50K)")

    # Turnover vol/liq — interes real
    if liq > 0:
        turnover = vol / liq
        if turnover > 1.0:    add(8, "Volumen mayor a liquidez (interes alto)")
        elif turnover > 0.3:  add(5, "Turnover saludable")
        elif turnover < 0.05: add(-6, "Volumen muerto")

    # Presion compradora
    if bp >= 65:     add(10, f"Presion compradora fuerte ({bp}% buys)")
    elif bp >= 55:   add(5,  f"Presion compradora positiva ({bp}%)")
    elif bp <= 40:   add(-8, f"Presion vendedora ({bp}% buys)")

    # Patron dip-estabilizacion (ideal para acumular en bear market)
    if ch24h < -5 and abs(ch1h) < 2:
        add(12, "Dip estabilizandose (ideal para DCA)")
    elif ch24h < -15 and ch1h > 0:
        add(10, "Rebote tras caida fuerte")
    elif ch1h > 15:
        add(-5, "Pump activo (mal punto de entrada)")

    # Flujo de exchanges
    if flow == "OUT":   add(12, "Retiro neto de exchanges (alcista)")
    elif flow == "IN":  add(-10, "Deposito neto a exchanges (bajista)")

    # Whales conocidas
    if wc >= 2:    add(12, f"{wc} whales conocidas posicionadas")
    elif wc == 1:  add(6,  "1 whale conocida posicionada")

    # Big buyers nuevos detectados
    if bb >= 3:    add(10, f"{bb} compradores grandes nuevos")
    elif bb >= 1:  add(5,  f"{bb} comprador(es) grande(s) nuevo(s)")

    # Presencia social
    if d.get("has_socials"): add(4, "Presencia social activa")

    # Multi-DEX
    if d.get("multi_dex"): add(4, "Cotiza en multiples DEX")

    # Datos CoinGecko (RON/AR)
    ch7d = d.get("ch7d")
    if ch7d is not None:
        if ch7d < -10 and ch24h > -2: add(8, "Semana bajista pero estabilizando")
        elif ch7d > 15: add(-4, "Subida semanal fuerte (entrada tardia)")
    ath = d.get("ath_change")
    if ath is not None and ath < -70:
        add(6, f"Lejos del ATH ({ath:.0f}%) — potencial de recuperacion")

    return max(5, min(98, round(s))), reasons

# ─── NOTIFY HELPERS (sniper) ──────────────────────────────────────────────────
def notify_new_token(name, chain, score, dex, source, extra_info=""):
    if score < MIN_SCORE:
        return
    label = "BAJO RIESGO" if score >= 70 else "MEDIO" if score >= 45 else "ALTO"
    prio  = "urgent" if score >= 70 else "high" if score >= 45 else "default"
    notify(
        f"NUEVO TOKEN: {name} ({chain}) {score}/100 [{label}]",
        f"Fuente: {source}\n"
        f"Liq: {fmt_usd(dex['liq'])} | Vol: {fmt_usd(dex['vol'])}\n"
        f"1h: {pct(dex['ch1h'])} | Buys: {dex['buys']} / Sells: {dex['sells']}\n"
        f"{extra_info}"
        f"{market_ctx_str()}\n"
        f"Comprar: {dex['buy_url']}\n"
        f"Chart: {dex['url']}",
        priority=prio, tags="rocket,fire" if score >= 70 else "bell",
    )

def notify_whale_move(whale_label, token_name, chain, dex, wc=1, convergence=False):
    if convergence:
        notify(
            f"CONVERGENCIA x{wc} WHALES: {token_name} ({chain})",
            f"{wc} wallets conocidas compraron el mismo token\n"
            f"Liq: {fmt_usd(dex['liq'])} | Vol: {fmt_usd(dex['vol'])}\n"
            f"1h: {pct(dex['ch1h'])}\n"
            f"Comprar: {dex['buy_url']}\nChart: {dex['url']}",
            priority="urgent", tags="rotating_light,whale",
        )
    else:
        notify(
            f"WHALE: {whale_label} compro {token_name} ({chain})",
            f"Liq: {fmt_usd(dex['liq'])} | Vol: {fmt_usd(dex['vol'])}\n"
            f"1h: {pct(dex['ch1h'])}\nChart: {dex['url']}",
            priority="high", tags="whale",
        )

def notify_exchange_move(exchange, token_name, chain, dex, is_watchlist=False):
    prefix = "[WATCHLIST] " if is_watchlist else ""
    notify(
        f"{prefix}EXCHANGE {exchange}: {token_name} ({chain})",
        f"Posible pre-listing\n"
        f"Liq: {fmt_usd(dex['liq'])} | Vol: {fmt_usd(dex['vol'])}\n"
        f"1h: {pct(dex['ch1h'])}\n"
        f"Comprar: {dex['buy_url']}\nChart: {dex['url']}",
        priority="high" if is_watchlist else "default",
        tags="fire" if is_watchlist else "bell",
    )

def notify_watchlist_signal(token_name, chain, signal_type, dex, score, exchange_origin=None):
    if score < MIN_SCORE:
        return
    signals = {
        "liq_growth":   ("Liquidez creciendo",    "high",   "chart_with_upwards_trend"),
        "accumulation": ("Acumulacion silenciosa", "high",   "eyes"),
        "exchange_out": ("Retiro de exchanges",    "urgent", "fire"),
        "pump":         ("Pump detectado",         "urgent", "rocket"),
        "whale_in":     ("Whale compro",           "urgent", "whale"),
        "vol_accel":    ("Volumen acelerando",     "high",   "zap"),
    }
    label, prio, tags = signals.get(signal_type, ("Senal", "default", "bell"))
    origin_str = f"Exchange origen: {', '.join(exchange_origin)}\n" if exchange_origin else ""
    notify(
        f"{label} en {token_name} ({chain}) - {score}/100",
        f"{origin_str}"
        f"Liq: {fmt_usd(dex['liq'])} | Vol: {fmt_usd(dex['vol'])}\n"
        f"1h: {pct(dex['ch1h'])} | 24h: {pct(dex['ch24h'])}\n"
        f"Buys: {dex['buys']} / Sells: {dex['sells']}\n"
        f"Comprar: {dex['buy_url']}\nChart: {dex['url']}",
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

# ─── SISTEMA DE COMBO (apila senales del mismo token) ────────────────────────
# Pesos de cada tipo de senal (prioridad confirmada por el usuario)
COMBO_WEIGHTS = {
    "insider_convergence":    5,  # 2+ insiders en la misma moneda (lo mas fuerte de todo)
    "prelisting_unconfirmed": 4,  # exchange toca token NO listado aun
    "multi_exchange":         3,  # varios exchanges tocan el mismo token
    "insider_buy":            3,  # smart wallet / insider activo compro
    "high_pump_prob":         2,  # probabilidad de pump alta
    "whale_convergence":      2,  # convergencia de whales conocidas
    "exchange_out":           1,  # retiro neto de exchanges
    "vol_accel":              1,  # volumen acelerando
    "prelisting_confirmed":   1,  # exchange toca token YA listado (menos jugoso)
}
COMBO_LABELS = {
    "insider_convergence":    "CONVERGENCIA INSIDER",
    "prelisting_unconfirmed": "Pre-listing NO confirmado",
    "multi_exchange":         "Multi-exchange",
    "insider_buy":            "Insider/smart wallet dentro",
    "high_pump_prob":         "Prob. de pump alta",
    "whale_convergence":      "Convergencia de whales",
    "exchange_out":           "Retiro de exchanges",
    "vol_accel":              "Volumen acelerando",
    "prelisting_confirmed":   "Exchange activo (ya listado)",
}

def register_signal(contract, symbol, chain, signal_type, dex=None):
    """Apila una senal sobre un token. Si se acumulan varias en la ventana, dispara combo."""
    if not contract:
        return
    contract = contract.lower()
    now = time.time()
    entry = combo_signals.setdefault(contract, {
        "symbol": symbol, "chain": chain, "signals": {},
        "first_seen": now, "notified_combo": 0,
        "dex": dex,
    })
    entry["symbol"] = symbol
    entry["chain"] = chain
    if dex:
        entry["dex"] = dex  # solo actualizar si viene un dex valido (no pisar con None)
    # Registrar/refrescar la senal
    entry["signals"][signal_type] = now
    # Limpiar senales viejas (fuera de la ventana)
    cutoff = now - COMBO_WINDOW_H * 3600
    entry["signals"] = {k: v for k, v in entry["signals"].items() if v >= cutoff}
    # Evaluar combo
    evaluate_combo(contract, entry)

def evaluate_combo(contract, entry):
    """Calcula el score de combo y notifica si supera el umbral."""
    signals = entry["signals"]
    if len(signals) < COMBO_MIN_SCORE:
        return
    combo_score = sum(COMBO_WEIGHTS.get(s, 1) for s in signals)
    now = time.time()
    # No re-notificar el mismo combo en menos de 1h, salvo que crezca
    n_signals = len(signals)
    last_notified = entry.get("notified_combo", 0)
    last_count = entry.get("notified_count", 0)
    if last_notified and (now - last_notified < 3600) and n_signals <= last_count:
        return
    # Umbral: al menos 2 senales y score combinado >= 5, o 3+ senales
    if not (combo_score >= 5 or n_signals >= 3):
        return

    entry["notified_combo"] = now
    entry["notified_count"] = n_signals
    dex = entry.get("dex") or {}
    symbol = entry["symbol"]
    chain = entry["chain"]

    signal_lines = "\n".join(f"  + {COMBO_LABELS.get(s, s)}" for s in sorted(signals, key=lambda x: -COMBO_WEIGHTS.get(x, 1)))
    buy_url = dex.get("buy_url", "")
    url = dex.get("url", "")
    extra = ""
    if dex:
        extra = (f"Liq: {fmt_usd(dex.get('liq', 0))} | Vol: {fmt_usd(dex.get('vol', 0))}\n"
                 f"1h: {pct(dex.get('ch1h', 0))} | Prob pump: {dex.get('pump_prob', '?')}%\n")

    log(f"  COMBO {symbol}: {n_signals} senales, score {combo_score}")
    notify(
        f"COMBO x{n_signals}: {symbol} ({chain}) — score {combo_score}",
        f"Varias senales se alinearon en este token:\n{signal_lines}\n\n"
        f"{extra}"
        f"{'Comprar: ' + buy_url + chr(10) if buy_url else ''}"
        f"{'Chart: ' + url if url else ''}",
        priority="urgent", tags="rotating_light,fire,dart",
        click_url=VERCEL_URL,
    )
    register_week_event(symbol, "combo",
                        f"Combo de {n_signals} senales (score {combo_score}): " +
                        ", ".join(COMBO_LABELS.get(s, s) for s in signals))

def cleanup_combo_signals():
    """Elimina tokens cuyas senales ya expiraron todas."""
    now = time.time()
    cutoff = now - COMBO_WINDOW_H * 3600
    to_remove = []
    for contract, entry in combo_signals.items():
        entry["signals"] = {k: v for k, v in entry["signals"].items() if v >= cutoff}
        if not entry["signals"]:
            to_remove.append(contract)
    for c in to_remove:
        combo_signals.pop(c, None)

# ─── MÓDULOS SNIPER (1-6, igual que v2 pero con Etherscan V2) ────────────────
def scan_exchange_wallets_eth():
    log("-- Scan exchange wallets ETH --")
    watchlist_eth = {w["contract"].lower(): w for w in WATCHLIST if w["chain"] == "ETH"}
    for wallet in EXCHANGE_WALLETS_ETH:
        txs = get_eth_token_txs(wallet["address"])
        time.sleep(0.4)
        if not txs:
            continue
        now = time.time()
        recent = [tx for tx in txs if now - int(tx.get("timeStamp", 0)) < 14400]
        contracts = list({tx.get("contractAddress", "").lower() for tx in recent if tx.get("contractAddress")})
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
                continue
            multi = any(
                w2["exchange"] != wallet["exchange"] and
                any(tx.get("from", "").lower() == w2["address"].lower() or
                    tx.get("to", "").lower() == w2["address"].lower() for tx in recent)
                for w2 in EXCHANGE_WALLETS_ETH
            )
            verified = check_contract_verified_evm(contract, "ETH")
            time.sleep(0.3)
            vol_accel, _ = detect_volume_acceleration(contract, dex.get("vol5m", 0))
            dex["verified"] = verified
            dex["vol_accel"] = vol_accel
            token_name = watchlist_eth[contract]["name"] if is_watchlist else dex["name"]
            score = compute_score({**dex, "src": wallet["exchange"], "chain": "ETH",
                                   "multi": multi, "verified": verified, "vol_accel": vol_accel})
            pprob, _ = pump_probability(dex)
            dex["pump_prob"] = pprob

            # ── Verificacion de listing: spot / solo-futuros / no-listado
            lstatus = get_listing_status(wallet["exchange"], dex["name"])
            listing_str = ""
            if lstatus == "not_listed":
                listing_str = f"*** NO LISTADO en {wallet['exchange']} (ni spot ni futuros) — posible pre-listing ***\n"
            elif lstatus == "futures_only":
                listing_str = f"Solo en FUTUROS de {wallet['exchange']} (no spot aun) — movimiento normal de futuros\n"
            elif lstatus == "spot":
                listing_str = f"Ya en SPOT de {wallet['exchange']} (actividad normal)\n"

            if is_watchlist:
                notify_exchange_move(wallet["exchange"], token_name, "ETH", dex, is_watchlist=True)
            elif contract not in seen_contracts:
                origins = get_exchange_origin_evm(contract, "ETH")
                time.sleep(0.3)
                origin_str = f"Origen: {', '.join(origins)}\n" if origins else ""
                origin_str += listing_str
                origin_str += f"Prob. de pump: {pprob}%\n"
                notify_new_token(dex["name"], "ETH", score, dex, wallet["exchange"], origin_str)
                start_tracking(contract, dex["name"], "ETH", dex, pprob, wallet["exchange"])
                seen_contracts.add(contract)

            # ── Registrar senales para el sistema de combo
            # Solo "no listado en nada" es pre-listing jugoso. Futuros-solo NO cuenta como pre-listing.
            if lstatus == "not_listed":
                register_signal(contract, dex["name"], "ETH", "prelisting_unconfirmed", dex)
            elif lstatus == "spot":
                register_signal(contract, dex["name"], "ETH", "prelisting_confirmed", dex)
            # futures_only: no registra señal de prelisting (era el falso positivo que arreglamos)
            if multi:
                register_signal(contract, dex["name"], "ETH", "multi_exchange", dex)
            if pprob >= 60:
                register_signal(contract, dex["name"], "ETH", "high_pump_prob", dex)
            if vol_accel:
                register_signal(contract, dex["name"], "ETH", "vol_accel", dex)

            if float(dex.get("ch1h", 0) or 0) >= PUMP_THRESHOLD:
                analyze_insiders(contract, "ETH", dex)
            time.sleep(0.4)
        time.sleep(0.3)

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
            passed, _ = passes_quality_filter(dex, "SOL")
            if not passed and not is_watchlist:
                continue
            vol_accel, _ = detect_volume_acceleration(mint, dex.get("vol5m", 0))
            dex["vol_accel"] = vol_accel
            token_name = watchlist_sol[mint]["name"] if is_watchlist else dex["name"]
            score = compute_score({**dex, "src": wallet["exchange"], "chain": "SOL", "vol_accel": vol_accel})
            pprob, _ = pump_probability(dex)
            dex["pump_prob"] = pprob

            # Verificacion de listing: spot / solo-futuros / no-listado
            lstatus = get_listing_status(wallet["exchange"], dex["name"])
            listing_str = ""
            if lstatus == "not_listed":
                listing_str = f"*** NO LISTADO en {wallet['exchange']} (ni spot ni futuros) — posible pre-listing ***\n"
            elif lstatus == "futures_only":
                listing_str = f"Solo en FUTUROS de {wallet['exchange']} (no spot aun)\n"
            elif lstatus == "spot":
                listing_str = f"Ya en SPOT de {wallet['exchange']}\n"

            if is_watchlist:
                notify_exchange_move(wallet["exchange"], token_name, "SOL", dex, is_watchlist=True)
            elif mint not in seen_contracts:
                notify_new_token(dex["name"], "SOL", score, dex, wallet["exchange"], listing_str + f"Prob. de pump: {pprob}%\n")
                start_tracking(mint, dex["name"], "SOL", dex, pprob, wallet["exchange"])
                seen_contracts.add(mint)

            # Registrar senales de combo
            if lstatus == "not_listed":
                register_signal(mint, dex["name"], "SOL", "prelisting_unconfirmed", dex)
            elif lstatus == "spot":
                register_signal(mint, dex["name"], "SOL", "prelisting_confirmed", dex)
            if pprob >= 60:
                register_signal(mint, dex["name"], "SOL", "high_pump_prob", dex)
            if vol_accel:
                register_signal(mint, dex["name"], "SOL", "vol_accel", dex)

            time.sleep(0.4)
        time.sleep(0.4)

def scan_whale_wallets():
    log("-- Scan whale wallets --")
    watchlist_eth = {w["contract"].lower(): w for w in WATCHLIST if w["chain"] == "ETH"}
    watchlist_sol = {w["contract"]: w for w in WATCHLIST if w["chain"] == "SOL"}
    for whale in WHALE_WALLETS:
        if whale["chain"] == "ETH":
            txs = get_eth_token_txs(whale["address"])
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
                if not dex or dex["liq"] < MIN_LIQUIDITY:
                    continue
                passed, _ = passes_quality_filter(dex, "ETH")
                if not passed:
                    continue
                seen_whale_moves.add(move_key)
                is_watchlist = contract in watchlist_eth
                token_name = watchlist_eth[contract]["name"] if is_watchlist else dex["name"]
                whale_buys.setdefault(contract, set()).add(whale["address"])
                wc = len(whale_buys[contract])
                if wc >= 2:
                    notify_whale_move(whale["label"], token_name, "ETH", dex, wc=wc, convergence=True)
                    register_signal(contract, dex["name"], "ETH", "whale_convergence", dex)
                else:
                    notify_whale_move(whale["label"], token_name, "ETH", dex)
                if is_watchlist:
                    score = compute_score({**dex, "src": "WHALE", "chain": "ETH", "wc": wc})
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
                token_name = watchlist_sol[mint]["name"] if is_watchlist else dex["name"]
                whale_buys.setdefault(mint, set()).add(whale["address"])
                wc = len(whale_buys[mint])
                if wc >= 2:
                    notify_whale_move(whale["label"], token_name, "SOL", dex, wc=wc, convergence=True)
                    register_signal(mint, dex["name"], "SOL", "whale_convergence", dex)
                else:
                    notify_whale_move(whale["label"], token_name, "SOL", dex)
                if is_watchlist:
                    score = compute_score({**dex, "src": "WHALE", "chain": "SOL", "wc": wc})
                    notify_watchlist_signal(token_name, "SOL", "whale_in", dex, score)
                time.sleep(0.4)
        time.sleep(0.4)

def scan_watchlist():
    log("-- Scan watchlist --")
    for token in WATCHLIST:
        dex = get_dex(token["contract"], token["chain"])
        time.sleep(0.5)
        if not dex:
            continue
        name = dex["name"] if dex["name"] not in ("UNKNOWN", "") else token["name"]
        contract, chain = token["contract"], token["chain"]
        prev_liq = watchlist_prev.get(contract, dex["liq"])
        liq_growth = ((dex["liq"] - prev_liq) / prev_liq * 100) if prev_liq > 0 else 0
        watchlist_prev[contract] = dex["liq"]
        flow = ("OUT" if dex["buys"] > dex["sells"] * 1.3
                else "IN" if dex["sells"] > dex["buys"] * 1.3 else "NEUTRAL")
        accum = (abs(float(dex.get("ch1h", 0) or 0)) < 3 and dex["txns"] > 100 and dex["vol"] > 3000)
        ch1h = float(dex.get("ch1h", 0) or 0)
        vol_accel, va_pct = detect_volume_acceleration(contract, dex.get("vol5m", 0))
        score = compute_score({**dex, "src": "WATCHLIST", "chain": chain,
                               "flow": flow, "accum": accum, "liqG": liq_growth,
                               "vol_accel": vol_accel})
        origins = []
        if flow == "OUT" and chain == "ETH":
            origins = get_exchange_origin_evm(contract, "ETH")
            time.sleep(0.3)
        checks = [
            (liq_growth > 30, "liq", "liq_growth"),
            (accum, "accum", "accumulation"),
            (flow == "OUT", "flow", "exchange_out"),
            (ch1h >= PUMP_THRESHOLD, "pump", "pump"),
            (vol_accel, "volaccel", "vol_accel"),
        ]
        for condition, suffix, signal in checks:
            if condition:
                k = dedup_key(contract + "-" + suffix)
                if k not in seen_signals:
                    seen_signals.add(k)
                    notify_watchlist_signal(name, chain, signal, dex, score,
                                            origins if signal == "exchange_out" else None)
                    if signal == "pump" and chain == "ETH":
                        analyze_insiders(contract, "ETH", dex)
        # Deteccion de crecimiento de holders (solo EVM)
        if chain in ("ETH", "BNB", "BASE"):
            check_holder_growth(contract, name, chain)
            time.sleep(0.3)
        time.sleep(0.3)

def check_holder_growth(contract, symbol, chain):
    """
    Detecta crecimiento inusual de holders aproximado contando direcciones unicas
    que recibieron el token recientemente. Es un proxy gratuito, no el conteo exacto
    de holders (eso requiere API PRO). Sirve como señal temprana de interes.
    """
    txs = get_evm_token_txs_v2(contract, chain, by_contract=True, sort="desc", offset=100)
    if not txs:
        return
    now = time.time()
    # Direcciones unicas que recibieron en las ultimas 6h
    recent_receivers = set()
    for tx in txs:
        ts = int(tx.get("timeStamp", 0))
        if now - ts > 21600:  # 6h
            continue
        to = tx.get("to", "").lower()
        if to and to not in ETH_WALLET_MAP:
            recent_receivers.add(to)
    cur_count = len(recent_receivers)
    prev = holder_counts.get(contract.lower())
    holder_counts[contract.lower()] = {"symbol": symbol, "chain": chain, "count": cur_count, "ts": now}
    if not prev:
        return  # primera medicion, solo guardar baseline
    prev_count = prev["count"]
    if prev_count < 5:
        return  # muy pocos para comparar
    growth = (cur_count - prev_count) / prev_count * 100
    # Alertar si crecio 50%+ y hay al menos 10 receptores nuevos
    if growth >= 50 and cur_count >= prev_count + 8:
        k = dedup_key("holdergrowth-" + contract, 180)
        if k not in seen_signals:
            seen_signals.add(k)
            log(f"  CRECIMIENTO HOLDERS: {symbol} +{growth:.0f}%")
            notify(
                f"HOLDERS CRECIENDO: {symbol} ({chain}) +{growth:.0f}%",
                f"{symbol} esta atrayendo compradores nuevos rapido\n"
                f"Receptores recientes (6h): {prev_count} -> {cur_count}\n"
                f"Puede ser señal temprana de interes antes de que el precio se mueva.\n"
                f"{market_ctx_str()}",
                priority="high", tags="busts_in_silhouette,chart_with_upwards_trend",
                click_url=VERCEL_URL,
            )
            register_week_event(symbol, "holder_growth",
                                f"{symbol} holders +{growth:.0f}% ({prev_count}->{cur_count})")

def scan_new_tokens():
    log("-- Scan nuevos tokens --")
    for chain_id, chain_label in [("ethereum", "ETH"), ("solana", "SOL")]:
        min_liq = MIN_LIQUIDITY if chain_label == "ETH" else max(2000, MIN_LIQUIDITY // 2)
        for source_fn, src_label in [(get_new_token_profiles, "NEW_PAIR"), (get_boosted, "DEXSCREENER")]:
            items = source_fn(chain_id)
            for item in items:
                addr = item.get("tokenAddress")
                if not addr or addr in seen_new_pairs or addr in seen_contracts:
                    continue
                dex = get_dex(addr, chain_label)
                time.sleep(0.4)
                if not dex or dex["liq"] < min_liq:
                    continue
                passed, reason = passes_quality_filter(dex, chain_label, addr, check_hp=(chain_label == "ETH"))
                seen_new_pairs.add(addr)
                if not passed:
                    continue
                verified = check_contract_verified_evm(addr, "ETH") if chain_label == "ETH" else False
                if chain_label == "ETH":
                    time.sleep(0.3)
                vol_accel, _ = detect_volume_acceleration(addr, dex.get("vol5m", 0))
                dex["vol_accel"] = vol_accel
                dex["verified"] = verified
                score = compute_score({**dex, "src": src_label, "chain": chain_label,
                                       "multi": dex.get("multi_dex", False),
                                       "verified": verified, "vol_accel": vol_accel})
                # Probabilidad de pump (distinta al score de riesgo)
                pprob, pfactors = pump_probability(dex)
                dex["pump_prob"] = pprob

                # Solo notifica si el score Y la probabilidad de pump pasan el umbral
                if score >= MIN_SCORE and pprob >= MIN_PUMP_PROB:
                    extra = []
                    extra.append(f"Prob. de pump: {pprob}%")
                    if verified: extra.append("Contrato verificado")
                    if dex.get("multi_dex"): extra.append("Multi-DEX")
                    if vol_accel: extra.append("Volumen acelerando")
                    age = dex.get("age_hours")
                    if age is not None: extra.append(f"Edad: {age:.1f}h")
                    extra_str = " | ".join(extra) + "\n" if extra else ""
                    notify_new_token(dex["name"], chain_label, score, dex, src_label, extra_str)
                    # Iniciar tracking post-notificacion
                    start_tracking(addr, dex["name"], chain_label, dex, pprob, src_label)
                if float(dex.get("ch1h", 0) or 0) >= PUMP_THRESHOLD and chain_label == "ETH":
                    analyze_insiders(addr, "ETH", dex)
                time.sleep(0.3)

def analyze_insiders(contract, chain, dex):
    if contract in seen_pump_analysis:
        return
    seen_pump_analysis.add(contract)
    buyers = get_early_buyers(contract, chain=chain)
    if not buyers:
        return
    for buyer in buyers:
        addr = buyer["address"].lower()
        buyer["appears_multiple"] = addr in discovered_whales
        discovered_whales.add(addr)
    notify_insider(dex["name"], chain, buyers, float(dex.get("ch1h", 0) or 0), dex)

# ─── MÓDULO 7: ACUMULACIÓN ────────────────────────────────────────────────────
def check_insider_convergence(contract, symbol, chain):
    """
    Detecta cuando 2+ smart wallets distintas (insiders) tienen el mismo token.
    Si hay convergencia, etiqueta el token y lo agrega a seguimiento automatico.
    """
    if not contract:
        return
    contract = contract.lower()
    # Contar cuantas smart wallets tienen este symbol entre sus tokens
    holders = [addr for addr, sw in smart_wallets.items() if symbol in sw.get("tokens", set())]
    if len(holders) < 2:
        return
    # Hay convergencia: 2+ insiders en la misma moneda
    k = dedup_key("convergencia-" + contract, 360)  # no repetir en 6h
    if k in seen_signals:
        return
    seen_signals.add(k)
    # Score promedio de los insiders involucrados
    scores = [smart_wallets[a].get("insider_score", 0) for a in holders]
    avg_score = round(sum(scores) / len(scores))
    top_holders = sorted(holders, key=lambda a: smart_wallets[a].get("insider_score", 0), reverse=True)[:3]
    holders_str = "\n".join(
        f"  {smart_wallets[a].get('label', short(a))} (score {smart_wallets[a].get('insider_score', 0)})"
        for a in top_holders
    )
    # Registrar en convergencias para la UI
    insider_convergences[contract] = {
        "symbol": symbol, "chain": chain,
        "n_insiders": len(holders),
        "avg_score": avg_score,
        "holders": [short(a) for a in top_holders],
        "detected_at": int(time.time()),
    }
    # Registrar como señal de combo de maximo peso
    register_signal(contract, symbol, chain, "insider_convergence", None)
    # Iniciar tracking automatico de precio sobre esta moneda
    dex = get_dex(contract, chain)
    time.sleep(0.3)
    if dex and dex.get("liq", 0) >= MIN_LIQUIDITY:
        if contract not in tracked_tokens:
            start_tracking(contract, symbol, chain, dex, dex.get("pump_prob", 0), "CONVERGENCIA")
    log(f"  CONVERGENCIA INSIDER: {symbol} con {len(holders)} insiders")
    notify(
        f"CONVERGENCIA INSIDER: {symbol} ({chain}) — {len(holders)} insiders",
        f"{len(holders)} smart wallets distintas tienen {symbol}:\n{holders_str}\n\n"
        f"Score promedio: {avg_score}\n"
        f"Agregada a seguimiento automatico.\n"
        f"{'Chart: ' + dex.get('url', '') if dex else ''}",
        priority="urgent", tags="rotating_light,busts_in_silhouette,dart",
        click_url=VERCEL_URL,
    )
    register_week_event(symbol, "insider_convergence",
                        f"{len(holders)} insiders convergen en {symbol} (score prom. {avg_score})")

def detect_big_buyers(contract, chain, symbol, price_usd=0):
    """Registra compradores grandes recientes en tokens EVM de la lista.
    Captura monto en USD y frecuencia para alimentar el score de insider."""
    if CHAINS.get(chain, {}).get("escan") is None:
        return 0
    txs = get_evm_token_txs_v2(contract, chain, by_contract=True, offset=40)
    now = time.time()
    new_count = 0
    for tx in txs:
        ts = int(tx.get("timeStamp", 0))
        if now - ts > 86400:
            continue
        to_addr = tx.get("to", "").lower()
        if not to_addr or to_addr in ETH_WALLET_MAP:
            continue
        try:
            tokens_amt = float(tx.get("value", 0)) / (10 ** int(tx.get("tokenDecimal", 18)))
        except:
            continue
        if tokens_amt <= 0:
            continue
        usd = tokens_amt * price_usd if price_usd > 0 else 0

        entry = accum_big_buyers.setdefault(to_addr, {
            "tokens": set(), "count": 0, "total_usd": 0.0,
            "last_buy": ts, "buys": 0, "chain": chain,
        })
        entry["buys"] += 1
        entry["total_usd"] += usd
        entry["last_buy"] = max(entry["last_buy"], ts)
        entry["chain"] = chain

        if symbol not in entry["tokens"]:
            entry["tokens"].add(symbol)
            entry["count"] += 1
            new_count += 1
            # Registrar/actualizar como smart wallet si compra 2+ tokens de la lista
            if len(entry["tokens"]) >= INSIDER_MIN_TOKENS:
                sw = register_smart_wallet(to_addr, chain, entry)
                # Solo notificar si paso el filtro de calidad (sw no es None)
                if sw is not None:
                    # Registrar señal de insider para el combo
                    register_signal(contract, symbol, chain, "insider_buy", None)
                    # Detectar convergencia: 2+ insiders distintos en el mismo token
                    check_insider_convergence(contract, symbol, chain)
                    k = dedup_key("smartmoney-" + to_addr, 240)
                    if k not in seen_signals:
                        seen_signals.add(k)
                        tokens_str = ", ".join(sorted(entry["tokens"]))
                        usd_str = f" | ~{fmt_usd(entry['total_usd'])} movidos" if entry["total_usd"] > 0 else ""
                        notify(
                            f"SMART MONEY: wallet en {len(entry['tokens'])} tokens de tu lista",
                            f"Wallet: {short(to_addr)}\n"
                            f"Comprando: {tokens_str}{usd_str}\n"
                            f"Ver: https://etherscan.io/address/{to_addr}",
                            priority="high", tags="eyes,moneybag",
                        )
                        register_week_event(symbol, "smart_money",
                                            f"Wallet {short(to_addr)} en {len(entry['tokens'])} tokens: {tokens_str}")
    return new_count

def assess_wallet_quality(addr, chain):
    """
    Evalua si una wallet parece bot/market-maker (baja calidad) o insider real.
    Retorna (es_calidad: bool, razon: str, n_txs: int, n_tokens_distintos: int).
    Un insider real es SELECTIVO: pocas monedas, no miles de transacciones.
    """
    if CHAINS.get(chain, {}).get("escan") is None:
        return True, "SOL (no verificable)", 0, 0  # en SOL no podemos verificar, aceptar
    txs = get_evm_token_txs_v2(addr, chain, sort="desc", offset=100)
    time.sleep(0.3)
    if not txs:
        return True, "sin historial visible", 0, 0
    n_txs = len(txs)
    distinct_tokens = len({tx.get("contractAddress", "").lower() for tx in txs if tx.get("contractAddress")})
    # Bot/market-maker: muchisimas transacciones tocando muchos tokens distintos
    # (offset es 100, asi que si llena los 100 es muy activa)
    if n_txs >= 100 and distinct_tokens >= 50:
        return False, f"posible bot ({distinct_tokens} tokens en {n_txs} txs)", n_txs, distinct_tokens
    if distinct_tokens >= 70:
        return False, f"toca demasiados tokens ({distinct_tokens})", n_txs, distinct_tokens
    return True, "selectiva (insider real)", n_txs, distinct_tokens

def examine_wallet(addr, chain):
    """
    Examen manual de una wallet. Devuelve un veredicto honesto:
    comportamiento, coincidencias con la lista de acumulacion, portfolio y score estimado.
    """
    addr = addr.lower().strip()
    if not addr.startswith("0x") or len(addr) != 42:
        if chain != "SOL":
            return {"error": "Direccion EVM invalida (debe empezar con 0x y tener 42 caracteres)"}
    if CHAINS.get(chain, {}).get("escan") is None:
        return {"error": f"La cadena {chain} no es verificable con APIs gratuitas (solo ETH/BNB/BASE)"}

    # 1. Comportamiento (filtro de calidad)
    is_quality, reason, n_txs, distinct_tokens = assess_wallet_quality(addr, chain)

    # 2. Coincidencias con la lista de acumulacion
    accum_symbols = {t["name"].upper() for t in ACCUMULATION_LIST}
    txs = get_evm_token_txs_v2(addr, chain, sort="desc", offset=100)
    time.sleep(0.3)
    touched_symbols = {}
    for tx in txs:
        sym = tx.get("tokenSymbol", "").upper()
        if sym:
            touched_symbols[sym] = touched_symbols.get(sym, 0) + 1
    matches = sorted(set(touched_symbols.keys()) & accum_symbols)

    # 3. Portfolio actual
    portfolio = get_wallet_portfolio(addr, chain, max_tokens=12)
    time.sleep(0.2)

    # 4. Score estimado (simula lo que tendria como smart wallet)
    fake_entry = {
        "tokens": set(matches),
        "total_usd": 0,  # no calculable sin precios historicos por wallet
        "buys": sum(touched_symbols.get(m, 0) for m in matches),
        "last_buy": int(time.time()),
    }
    fake_sw = {
        "tokens": set(matches), "total_usd": 0,
        "buys": fake_entry["buys"], "last_seen": int(time.time()),
        "forensic": False,
    }
    est_score = compute_insider_score(fake_sw)

    # 5. Veredicto honesto
    if not is_quality:
        verdict = "DESCARTAR"
        verdict_detail = f"Parece bot o infraestructura ({reason}). No es un insider selectivo."
        verdict_color = "red"
    elif len(matches) == 0:
        verdict = "SIN RELACION"
        verdict_detail = "Wallet valida pero no ha tocado ninguna moneda de tu lista de acumulacion. No aporta como insider."
        verdict_color = "gray"
    elif len(matches) >= 3:
        verdict = "POSIBLE INSIDER FUERTE"
        verdict_detail = f"Toca {len(matches)} monedas de tu lista y es selectiva. Buen candidato a seguir."
        verdict_color = "green"
    else:
        verdict = "POSIBLE INSIDER DEBIL"
        verdict_detail = f"Toca {len(matches)} moneda(s) de tu lista. Selectiva, pero pocas coincidencias. Vigilar."
        verdict_color = "yellow"

    return {
        "address": addr,
        "chain": chain,
        "is_quality": is_quality,
        "behavior": reason,
        "n_txs_sample": n_txs,
        "distinct_tokens": distinct_tokens,
        "matches": matches,
        "n_matches": len(matches),
        "portfolio": portfolio,
        "est_score": est_score,
        "verdict": verdict,
        "verdict_detail": verdict_detail,
        "verdict_color": verdict_color,
        "already_tracked": addr in smart_wallets,
    }

def add_manual_wallet(addr, chain):
    """Agrega una wallet examinada a las smart wallets (tras el visto bueno del usuario)."""
    addr = addr.lower().strip()
    accum_symbols = {t["name"].upper() for t in ACCUMULATION_LIST}
    txs = get_evm_token_txs_v2(addr, chain, sort="desc", offset=100)
    time.sleep(0.3)
    touched = {}
    for tx in txs:
        sym = tx.get("tokenSymbol", "").upper()
        if sym in accum_symbols:
            touched[sym] = touched.get(sym, 0) + 1
    entry = accum_big_buyers.setdefault(addr, {
        "tokens": set(), "count": 0, "total_usd": 0.0,
        "last_buy": int(time.time()), "buys": 0, "chain": chain,
    })
    entry["tokens"] = set(touched.keys())
    entry["count"] = len(touched)
    entry["buys"] = sum(touched.values())
    entry["chain"] = chain
    # Registrar sin filtro de calidad (el usuario ya lo vio y decidio)
    sw = register_smart_wallet(addr, chain, entry, label=f"Manual {short(addr)}", check_quality=False)
    if sw:
        update_tracked_whales()
        save_state(force=True)
        return sw
    return None

def register_smart_wallet(addr, chain, entry, forensic=False, label="", check_quality=True):
    """Crea o actualiza una smart wallet y recalcula su score de insider."""
    # Filtro de calidad: descartar bots/market-makers (solo al registrar por primera vez)
    if check_quality and addr not in smart_wallets:
        is_quality, reason, n_txs, n_tok = assess_wallet_quality(addr, chain)
        if not is_quality:
            log(f"  Wallet descartada (no insider): {short(addr)} — {reason}")
            return None
    sw = smart_wallets.setdefault(addr, {
        "chain": chain, "tokens": set(), "total_usd": 0.0,
        "buys": 0, "insider_score": 0, "last_seen": 0,
        "tag": "smart", "forensic": False, "label": label or short(addr),
    })
    sw["chain"] = chain
    sw["tokens"] = set(entry.get("tokens", sw["tokens"]))
    sw["total_usd"] = max(sw["total_usd"], entry.get("total_usd", 0))
    sw["buys"] = max(sw["buys"], entry.get("buys", 0))
    sw["last_seen"] = max(sw["last_seen"], entry.get("last_buy", int(time.time())))
    if forensic:
        sw["forensic"] = True
    if label:
        sw["label"] = label
    sw["insider_score"] = compute_insider_score(sw)
    # Etiqueta especial
    if sw["insider_score"] >= 75:
        sw["tag"] = "insider_activo"
    elif sw["forensic"]:
        sw["tag"] = "insider_historico"
    else:
        sw["tag"] = "smart"
    return sw

def compute_insider_score(sw):
    """
    Score de insider (0-100) priorizando:
    - cantidad de dinero movido
    - cantidad de monedas de la lista que coinciden
    - nivel de actividad (frecuencia de compras)
    - bonus si fue detectado en analisis forense (compro antes de un pump real)
    """
    s = 0
    n_tokens = len(sw.get("tokens", set()))
    usd = sw.get("total_usd", 0)
    buys = sw.get("buys", 0)
    now = time.time()
    last_seen = sw.get("last_seen", 0)

    # Coincidencia de monedas (lo mas importante: insider real compra varias)
    if n_tokens >= 5:   s += 35
    elif n_tokens == 4: s += 28
    elif n_tokens == 3: s += 20
    elif n_tokens == 2: s += 10

    # Dinero movido
    if usd >= 100000:   s += 30
    elif usd >= 25000:  s += 22
    elif usd >= 5000:   s += 14
    elif usd >= 1000:   s += 7
    elif usd > 0:       s += 3

    # Actividad / frecuencia
    if buys >= 20:   s += 15
    elif buys >= 10: s += 10
    elif buys >= 4:  s += 5

    # Recencia (activa = mas valiosa)
    if last_seen > 0:
        days_ago = (now - last_seen) / 86400
        if days_ago < 1:    s += 12
        elif days_ago < 3:  s += 8
        elif days_ago < 7:  s += 4
        elif days_ago > 30: s -= 10

    # Bonus forense: compro antes de un pump confirmado historicamente
    if sw.get("forensic"):  s += 15

    return max(0, min(100, round(s)))

def register_week_event(token, event_type, detail):
    week_events.append({
        "ts": int(time.time()),
        "date": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
        "token": token,
        "type": event_type,
        "detail": detail,
    })
    # Mantener maximo 200 eventos
    if len(week_events) > 200:
        del week_events[:50]

def scan_accumulation():
    """Scan completo de la lista de acumulacion. Detecta eventos urgentes mid-week."""
    log("== Scan ACUMULACION ==")

    for token in ACCUMULATION_LIST:
        symbol, chain, contract = token["name"], token["chain"], token["contract"]
        dex = get_dex(contract, chain)
        time.sleep(0.5)
        if not dex:
            log(f"  {symbol}: sin datos DexScreener")
            continue

        flow = ("OUT" if dex["buys"] > dex["sells"] * 1.3
                else "IN" if dex["sells"] > dex["buys"] * 1.3 else "NEUTRAL")

        # Whales conocidas posicionadas en este token
        wc = len(whale_buys.get(contract.lower(), set())) + len(whale_buys.get(contract, set()))

        # Big buyers (solo EVM) — con precio para calcular USD movido
        try:
            price_usd = float(dex.get("price", 0) or 0)
        except:
            price_usd = 0
        bb = detect_big_buyers(contract, chain, symbol, price_usd)
        time.sleep(0.3)

        data = {
            **dex,
            "symbol": symbol, "chain": chain, "contract": contract,
            "flow": flow, "whale_count": wc, "big_buyers": bb,
            "source": "dexscreener",
        }
        score, reasons = accum_score(data)
        data["score"] = score
        data["reasons"] = reasons
        data["updated_at"] = int(time.time())

        # ── Detectar eventos urgentes comparando con snapshot anterior
        prev = accum_prev.get(symbol, {})
        prev_score = prev.get("score", score)
        ch1h = float(dex.get("ch1h", 0) or 0)

        urgent_checks = [
            (ch1h >= PUMP_THRESHOLD,
             "pump", f"Pump +{ch1h:.0f}% en 1h", "urgent", "rocket"),
            (ch1h <= -20,
             "dump", f"Caida {ch1h:.0f}% en 1h", "urgent", "warning"),
            (prev.get("liq", 0) > 0 and (dex["liq"] - prev["liq"]) / prev["liq"] * 100 > 30,
             "liq_growth", f"Liquidez crecio +{((dex['liq']-prev.get('liq',dex['liq']))/max(prev.get('liq',1),1)*100):.0f}%", "high", "chart_with_upwards_trend"),
            (flow == "OUT" and dex["bp"] >= 65,
             "exchange_out", f"Retiro fuerte de exchanges ({dex['bp']}% buys)", "high", "fire"),
            (score >= 80 and prev_score < 80,
             "score_cross", f"Score de acumulacion cruzo 80 ({prev_score} -> {score})", "high", "star"),
        ]

        for condition, etype, detail, prio, tags in urgent_checks:
            if condition:
                k = dedup_key(f"accum-{symbol}-{etype}", 240)  # cooldown 4 horas
                if k not in seen_signals:
                    seen_signals.add(k)
                    log(f"  EVENTO {symbol}: {detail}")
                    notify(
                        f"[ACUMULACION] {symbol} ({chain}): {detail}",
                        f"Score acumulacion: {score}%\n"
                        f"Liq: {fmt_usd(dex['liq'])} | Vol: {fmt_usd(dex['vol'])}\n"
                        f"1h: {pct(dex['ch1h'])} | 24h: {pct(dex['ch24h'])}\n"
                        f"Buys: {dex['buys']} / Sells: {dex['sells']}\n"
                        f"Comprar: {dex['buy_url']}\nChart: {dex['url']}",
                        priority=prio, tags=tags,
                        click_url=VERCEL_URL,
                    )
                    register_week_event(symbol, etype, detail)

        accum_prev[symbol] = {"score": score, "liq": dex["liq"], "vol": dex["vol"]}
        accum_state[symbol] = data
        log(f"  {symbol} ({chain}): {score}% | Liq {fmt_usd(dex['liq'])} | {pct(dex['ch24h'])} 24h")

    # ── Tokens CEX via CoinGecko (RON, AR)
    for cg in COINGECKO_TOKENS:
        data = get_coingecko(cg["id"])
        time.sleep(1.2)  # CoinGecko rate limit
        if not data:
            log(f"  {cg['name']}: sin datos CoinGecko")
            continue
        symbol = cg["name"]
        accum_data = {
            "symbol": symbol, "chain": "CEX", "contract": cg["id"],
            "name": symbol,
            "liq": 0, "vol": data["vol"], "bp": 50,
            "ch1h": 0, "ch24h": data["ch24h"], "ch7d": data["ch7d"],
            "ath_change": data["ath_change"],
            "price": data["price"], "mcap": data["mcap"],
            "flow": "NEUTRAL", "whale_count": 0, "big_buyers": 0,
            "has_socials": True, "multi_dex": False,
            "buys": 0, "sells": 0, "txns": 0,
            "url": data["url"], "buy_url": data["url"],
            "source": "coingecko",
        }
        # Score adaptado para tokens CEX (sin datos on-chain DEX)
        s = 50
        reasons = []
        if data["ch7d"] < -10 and data["ch24h"] > -2:
            s += 12; reasons.append({"effect": 12, "reason": "Semana bajista pero estabilizando"})
        elif data["ch7d"] > 15:
            s -= 4; reasons.append({"effect": -4, "reason": "Subida semanal fuerte"})
        if data["ath_change"] < -70:
            s += 10; reasons.append({"effect": 10, "reason": f"Lejos del ATH ({data['ath_change']:.0f}%)"})
        if data["mcap"] > 500e6:
            s += 8; reasons.append({"effect": 8, "reason": "Market cap solido (>$500M)"})
        elif data["mcap"] > 100e6:
            s += 4; reasons.append({"effect": 4, "reason": "Market cap medio"})
        if data["vol"] > 10e6:
            s += 6; reasons.append({"effect": 6, "reason": "Volumen CEX saludable"})
        if data["ch30d"] < -25:
            s += 5; reasons.append({"effect": 5, "reason": "Mes muy bajista (oportunidad DCA)"})
        accum_data["score"] = max(5, min(98, round(s)))
        accum_data["reasons"] = reasons
        accum_data["updated_at"] = int(time.time())
        accum_state[symbol] = accum_data
        log(f"  {symbol} (CEX): {accum_data['score']}% | MCap {fmt_usd(data['mcap'])} | {pct(data['ch24h'])} 24h")

    log("== Scan ACUMULACION completo ==")

# ─── MÓDULO 7B: FORENSE HISTÓRICO DE INSIDERS ────────────────────────────────
def get_price_peak_evm(contract, chain):
    """
    Encuentra el timestamp aproximado del mayor pump historico de un token EVM
    usando el historial de transferencias (proxy: pico de actividad).
    Retorna timestamp o None.
    """
    txs = get_evm_token_txs_v2(contract, chain, by_contract=True, sort="desc", offset=100)
    if not txs:
        return None
    # Agrupar transacciones por dia y encontrar el dia de mayor actividad
    # (proxy de pump: gran volumen de transferencias)
    buckets = {}
    for tx in txs:
        ts = int(tx.get("timeStamp", 0))
        day = ts // 86400
        buckets[day] = buckets.get(day, 0) + 1
    if not buckets:
        return None
    peak_day = max(buckets, key=buckets.get)
    return peak_day * 86400 + 43200  # mediodia de ese dia

def forensic_analysis_token(token):
    """
    Analisis forense de un token de la lista de acumulacion.
    Busca wallets que compraron ANTES del mayor pump historico (posibles insiders).
    Solo EVM (ETH/BNB/BASE). En SOL es muy limitado con APIs gratis.
    """
    symbol, chain, contract = token["name"], token["chain"], token["contract"]
    if CHAINS.get(chain, {}).get("escan") is None:
        return 0  # SOL/CEX: forense no disponible con APIs gratis

    peak_ts = get_price_peak_evm(contract, chain)
    time.sleep(0.4)
    if not peak_ts:
        return 0

    window_start = peak_ts - FORENSIC_LOOKBACK_H * 3600
    # Traer transacciones antiguas en orden ascendente
    txs = get_evm_token_txs_v2(contract, chain, by_contract=True, sort="asc", offset=100)
    time.sleep(0.4)

    found = 0
    buyers_window = {}
    for tx in txs:
        ts = int(tx.get("timeStamp", 0))
        # Solo los que compraron en la ventana ANTES del pico
        if ts < window_start or ts > peak_ts:
            continue
        to_addr = tx.get("to", "").lower()
        if not to_addr or to_addr in ETH_WALLET_MAP:
            continue
        try:
            amt = float(tx.get("value", 0)) / (10 ** int(tx.get("tokenDecimal", 18)))
        except:
            continue
        if amt <= 0:
            continue
        b = buyers_window.setdefault(to_addr, {"amt": 0.0, "count": 0, "first": ts})
        b["amt"] += amt
        b["count"] += 1

    # Las wallets que compraron fuerte antes del pico = sospechosas de insider
    for addr, b in buyers_window.items():
        # Filtro: que haya comprado al menos 2 veces o un monto relevante
        if b["count"] < 1:
            continue
        existing = accum_big_buyers.setdefault(addr, {
            "tokens": set(), "count": 0, "total_usd": 0.0,
            "last_buy": b["first"], "buys": 0, "chain": chain,
        })
        if symbol not in existing["tokens"]:
            existing["tokens"].add(symbol)
            existing["count"] += 1
        existing["buys"] += b["count"]
        existing["chain"] = chain
        # Marcar como forense (compro antes de un pump real)
        # check_quality=False: el forense consultaria demasiadas APIs; ya filtra por comportamiento
        sw = register_smart_wallet(addr, chain, existing, forensic=True,
                                   label=f"Insider hist. {symbol}", check_quality=False)
        if sw is not None:
            found += 1

    if found > 0:
        log(f"  Forense {symbol}: {found} wallets compraron antes del pico historico")
        register_week_event(symbol, "forensic",
                            f"{found} posibles insiders historicos detectados en {symbol}")
    return found

def run_forensic_analysis():
    """Corre el analisis forense sobre toda la lista de acumulacion (1 vez al dia)."""
    global last_forensic_day
    log("=== ANALISIS FORENSE DE INSIDERS ===")
    total = 0
    evm_tokens = [t for t in ACCUMULATION_LIST if CHAINS.get(t["chain"], {}).get("escan")]
    for token in evm_tokens:
        try:
            total += forensic_analysis_token(token)
            time.sleep(0.5)
        except Exception as e:
            log(f"  [forense error] {token['name']}: {e}")
    # Recalcular ranking de insiders y agendar top
    update_tracked_whales()
    last_forensic_day = time.strftime("%Y-%m-%d", time.gmtime())
    log(f"=== FORENSE COMPLETO: {total} wallets analizadas, {len(smart_wallets)} smart wallets totales ===")
    save_state(force=True)  # persistir los insiders recien encontrados
    if total > 0:
        top = sorted(smart_wallets.items(), key=lambda kv: kv[1]["insider_score"], reverse=True)[:5]
        top_str = "\n".join(
            f"  {sw.get('label', short(addr))}: score {sw['insider_score']} ({len(sw['tokens'])} tokens)"
            for addr, sw in top
        )
        notify(
            f"FORENSE: {total} posibles insiders detectados",
            f"Top smart wallets ahora:\n{top_str}\n\n"
            f"Siguiendo las top {MAX_TRACKED_WHALES} activas.\n{VERCEL_URL or ''}",
            priority="default", tags="detective",
            click_url=VERCEL_URL,
        )

def update_tracked_whales():
    """Selecciona el top N de smart wallets por score y las pone en seguimiento activo."""
    ranked = sorted(smart_wallets.items(), key=lambda kv: kv[1]["insider_score"], reverse=True)
    top = ranked[:MAX_TRACKED_WHALES]
    new_set = {}
    for addr, sw in top:
        prev = tracked_whale_set.get(addr, {})
        new_set[addr] = {
            "chain": sw["chain"],
            "label": sw.get("label", short(addr)),
            "last_check": prev.get("last_check", 0),
            "last_seen_tokens": prev.get("last_seen_tokens", set()),
            "insider_score": sw["insider_score"],
            "tag": sw.get("tag", "smart"),
        }
    tracked_whale_set.clear()
    tracked_whale_set.update(new_set)
    log(f"  Top {len(new_set)} smart wallets en seguimiento activo")

def scan_tracked_whales():
    """Sigue las top smart wallets. Si compran algo nuevo, notifica con prioridad."""
    if not tracked_whale_set:
        return
    log(f"-- Siguiendo {len(tracked_whale_set)} smart wallets --")
    now = time.time()
    for addr, w in list(tracked_whale_set.items()):
        chain = w["chain"]
        if CHAINS.get(chain, {}).get("escan") is None:
            continue  # SOL: seguimiento limitado
        txs = get_evm_token_txs_v2(addr, chain, sort="desc", offset=15)
        time.sleep(0.4)
        if not txs:
            continue
        recent = [tx for tx in txs if now - int(tx.get("timeStamp", 0)) < 7200]  # ultimas 2h
        new_tokens = set()
        sold_tokens = set()
        for tx in recent:
            c = tx.get("contractAddress", "").lower()
            to_addr = tx.get("to", "").lower()
            from_addr = tx.get("from", "").lower()
            if c and to_addr == addr:      # la wallet RECIBIO el token (compro)
                new_tokens.add(c)
            elif c and from_addr == addr:  # la wallet ENVIO el token (vendio/movio)
                sold_tokens.add(c)
        prev_seen = w.get("last_seen_tokens", set())
        fresh = new_tokens - prev_seen

        # ── DETECCION DE VENTA: insider vendiendo una posicion que tenia ──
        for c in sold_tokens:
            # Solo alertar si era un token que la wallet tenia trackeado como posicion
            if c not in prev_seen:
                continue
            k = dedup_key(f"insidersell-{addr}-{c}", 180)
            if k in seen_signals:
                continue
            seen_signals.add(k)
            dex = get_dex(c, chain)
            time.sleep(0.3)
            sym = dex["name"] if dex else short(c)
            tag_label = {"insider_activo": "INSIDER ACTIVO", "insider_historico": "INSIDER HIST."}.get(w.get("tag"), "SMART MONEY")
            log(f"  INSIDER VENDIENDO: {short(addr)} solto {sym}")
            notify(
                f"INSIDER VENDIENDO: {sym} ({chain})",
                f"{tag_label} (score {w.get('insider_score','?')}) esta saliendo de {sym}\n"
                f"Wallet: {short(addr)}\n"
                f"El dinero inteligente puede estar tomando ganancias o saliendo antes del resto.\n"
                f"{'Chart: ' + dex.get('url','') if dex else ''}",
                priority="high", tags="warning,chart_with_downwards_trend",
                click_url=VERCEL_URL,
            )
            insider_sells.insert(0, {
                "ts": int(now), "wallet": addr, "token": sym,
                "chain": chain, "tag": w.get("tag"), "score": w.get("insider_score"),
                "url": dex.get("url", "") if dex else "",
            })
            del insider_sells[50:]
            register_week_event(sym, "insider_sell",
                                f"{tag_label} {short(addr)} vendiendo {sym}")

        for c in fresh:
            dex = get_dex(c, chain)
            time.sleep(0.35)
            if not dex or dex["liq"] < MIN_LIQUIDITY:
                continue
            passed, _ = passes_quality_filter(dex, chain)
            if not passed:
                continue
            tag_label = {"insider_activo": "INSIDER ACTIVO", "insider_historico": "INSIDER HISTORICO"}.get(w.get("tag"), "SMART MONEY")
            prio = "urgent" if w.get("tag") == "insider_activo" else "high"
            notify(
                f"{tag_label} compro: {dex['name']} ({chain})",
                f"Wallet seguida (score {w.get('insider_score','?')}): {short(addr)}\n"
                f"Compro: {dex['name']}\n"
                f"Liq: {fmt_usd(dex['liq'])} | Vol: {fmt_usd(dex['vol'])}\n"
                f"1h: {pct(dex['ch1h'])}\n"
                f"Comprar: {dex.get('buy_url','')}\nChart: {dex.get('url','')}",
                priority=prio, tags="eyes,rotating_light",
                click_url=VERCEL_URL,
            )
            register_week_event(dex["name"], "insider_buy",
                                f"{tag_label} {short(addr)} compro {dex['name']}")
            register_signal(c, dex["name"], chain, "insider_buy", dex)
            insider_alerts.insert(0, {
                "ts": int(now), "wallet": addr, "token": dex["name"],
                "chain": chain, "tag": w.get("tag"), "score": w.get("insider_score"),
                "url": dex.get("url", ""),
            })
            del insider_alerts[50:]
        # Acumular tokens vistos (comprados) menos los que ya vendio, para detectar ventas futuras
        w["last_seen_tokens"] = (prev_seen | new_tokens) - sold_tokens
        w["last_check"] = int(now)

# ─── MÓDULO 8: REPORTE SEMANAL ────────────────────────────────────────────────
def generate_diagnosis(t):
    """Genera diagnostico breve en espanol para un token."""
    parts = []
    score = t.get("score", 0)
    if score >= 75:
        parts.append("Excelente candidato para acumular")
    elif score >= 60:
        parts.append("Buen candidato, entrada gradual recomendada")
    elif score >= 45:
        parts.append("Neutral, esperar mejor punto de entrada")
    else:
        parts.append("No recomendado por ahora")

    ch24h = float(t.get("ch24h", 0) or 0)
    if ch24h < -10:
        parts.append(f"cayo {abs(ch24h):.0f}% en 24h")
    flow = t.get("flow", "NEUTRAL")
    if flow == "OUT":
        parts.append("retiro neto de exchanges (alcista)")
    elif flow == "IN":
        parts.append("deposito a exchanges (precaucion)")
    if t.get("whale_count", 0) > 0:
        parts.append(f"{t['whale_count']} whale(s) posicionada(s)")
    if t.get("big_buyers", 0) > 0:
        parts.append(f"{t['big_buyers']} comprador(es) grande(s) nuevo(s)")
    ath = t.get("ath_change")
    if ath is not None and ath < -70:
        parts.append(f"{abs(ath):.0f}% bajo su ATH")
    return ". ".join(parts).capitalize() + "."

def github_commit_json(path, obj, message):
    if not GITHUB_TOKEN or not GITHUB_REPO:
        log("[github] Sin GITHUB_TOKEN o GITHUB_REPO configurados")
        return False
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"
        headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
        }
        r = requests.get(url, headers=headers, timeout=12)
        sha = r.json().get("sha") if r.ok else None
        content = base64.b64encode(
            json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
        ).decode("utf-8")
        body = {"message": message, "content": content}
        if sha:
            body["sha"] = sha
        r = requests.put(url, json=body, headers=headers, timeout=15)
        if r.ok:
            log(f"[github] Commit OK: {path}")
            return True
        log(f"[github] Error {r.status_code}: {r.text[:150]}")
        return False
    except Exception as e:
        log(f"[github] {e}")
        return False

def github_read_json(path):
    """Lee un JSON desde el repo de GitHub. Retorna el objeto o None."""
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return None
    try:
        url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{path}?t={int(time.time())}"
        r = requests.get(url, timeout=12)
        if r.ok:
            return r.json()
        return None
    except Exception as e:
        log(f"[github read] {e}")
        return None

# ─── PERSISTENCIA DE ESTADO (sobrevive redeploys de Railway) ─────────────────
STATE_PATH = "data/state.json"
last_state_save = 0

def serialize_state():
    """Convierte el estado en memoria a un dict JSON-serializable (sets -> listas)."""
    sw = {}
    for addr, w in smart_wallets.items():
        sw[addr] = {
            "chain": w.get("chain"),
            "tokens": sorted(w.get("tokens", set())),
            "total_usd": w.get("total_usd", 0),
            "buys": w.get("buys", 0),
            "insider_score": w.get("insider_score", 0),
            "last_seen": w.get("last_seen", 0),
            "tag": w.get("tag", "smart"),
            "forensic": w.get("forensic", False),
            "label": w.get("label", ""),
        }
    bb = {}
    for addr, e in accum_big_buyers.items():
        bb[addr] = {
            "tokens": sorted(e.get("tokens", set())),
            "count": e.get("count", 0),
            "total_usd": e.get("total_usd", 0),
            "last_buy": e.get("last_buy", 0),
            "buys": e.get("buys", 0),
            "chain": e.get("chain", "ETH"),
        }
    tw = {}
    for addr, w in tracked_whale_set.items():
        tw[addr] = {
            "chain": w.get("chain"),
            "label": w.get("label", ""),
            "last_check": w.get("last_check", 0),
            "last_seen_tokens": sorted(w.get("last_seen_tokens", set())),
            "insider_score": w.get("insider_score", 0),
            "tag": w.get("tag", "smart"),
        }
    return {
        "saved_at": int(time.time()),
        "smart_wallets": sw,
        "accum_big_buyers": bb,
        "tracked_whale_set": tw,
        "signal_outcomes": signal_outcomes[-300:],
        "discovered_whales": list(discovered_whales)[-500:],
        "insider_convergences": insider_convergences,
        "combo_history": combo_history[-200:],
        "my_positions": my_positions,
    }

def save_state(force=False):
    """Guarda el estado a GitHub. Throttle de 10 min salvo force=True."""
    global last_state_save
    now = time.time()
    if not force and now - last_state_save < 600:
        return
    if not (GITHUB_TOKEN and GITHUB_REPO):
        return
    state = serialize_state()
    if github_commit_json(STATE_PATH, state, f"Estado {time.strftime('%Y-%m-%d %H:%M', time.gmtime())}"):
        last_state_save = now
        log(f"[estado] Guardado: {len(smart_wallets)} smart wallets, {len(accum_big_buyers)} big buyers")

def load_state():
    """Carga el estado desde GitHub al arrancar."""
    state = github_read_json(STATE_PATH)
    if not state:
        log("[estado] Sin estado previo (primer arranque o sin GitHub)")
        return
    try:
        for addr, w in state.get("smart_wallets", {}).items():
            smart_wallets[addr] = {
                "chain": w.get("chain"),
                "tokens": set(w.get("tokens", [])),
                "total_usd": w.get("total_usd", 0),
                "buys": w.get("buys", 0),
                "insider_score": w.get("insider_score", 0),
                "last_seen": w.get("last_seen", 0),
                "tag": w.get("tag", "smart"),
                "forensic": w.get("forensic", False),
                "label": w.get("label", ""),
            }
        for addr, e in state.get("accum_big_buyers", {}).items():
            accum_big_buyers[addr] = {
                "tokens": set(e.get("tokens", [])),
                "count": e.get("count", 0),
                "total_usd": e.get("total_usd", 0),
                "last_buy": e.get("last_buy", 0),
                "buys": e.get("buys", 0),
                "chain": e.get("chain", "ETH"),
            }
        for addr, w in state.get("tracked_whale_set", {}).items():
            tracked_whale_set[addr] = {
                "chain": w.get("chain"),
                "label": w.get("label", ""),
                "last_check": w.get("last_check", 0),
                "last_seen_tokens": set(w.get("last_seen_tokens", [])),
                "insider_score": w.get("insider_score", 0),
                "tag": w.get("tag", "smart"),
            }
        signal_outcomes.extend(state.get("signal_outcomes", []))
        discovered_whales.update(state.get("discovered_whales", []))
        insider_convergences.update(state.get("insider_convergences", {}))
        combo_history.extend(state.get("combo_history", []))
        my_positions.update(state.get("my_positions", {}))
        saved_ago = (time.time() - state.get("saved_at", 0)) / 3600
        log(f"[estado] Cargado: {len(smart_wallets)} smart wallets, {len(tracked_whale_set)} en seguimiento (guardado hace {saved_ago:.1f}h)")
    except Exception as e:
        log(f"[estado load] {e}")

def weekly_report():
    """Genera el analisis semanal, lo sube a GitHub y notifica por Ntfy."""
    global last_weekly_week, week_events
    log("=== GENERANDO REPORTE SEMANAL ===")

    if not accum_state:
        scan_accumulation()

    ranking = sorted(accum_state.values(), key=lambda t: t.get("score", 0), reverse=True)
    report_tokens = []
    for i, t in enumerate(ranking):
        report_tokens.append({
            "rank": i + 1,
            "symbol": t.get("symbol"),
            "chain": t.get("chain"),
            "score": t.get("score"),
            "price": t.get("price"),
            "liq": t.get("liq"),
            "vol": t.get("vol"),
            "mcap": t.get("mcap", 0),
            "ch24h": t.get("ch24h"),
            "ch7d": t.get("ch7d"),
            "flow": t.get("flow"),
            "whale_count": t.get("whale_count", 0),
            "big_buyers": t.get("big_buyers", 0),
            "diagnosis": generate_diagnosis(t),
            "reasons": t.get("reasons", []),
            "url": t.get("url"),
            "buy_url": t.get("buy_url"),
        })

    report = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
        "week": iso_week_now(),
        "market_context": "bajista",
        "ranking": report_tokens,
        "top3": [t["symbol"] for t in report_tokens[:3]],
        "events_count": len(week_events),
        "events": week_events[-100:],
    }

    # Subir a GitHub
    github_commit_json("data/weekly.json", report, f"Reporte semanal {report['week']}")

    # Notificar por Ntfy
    top3 = report["top3"]
    top_str = " | ".join(f"{i+1}. {s} ({report_tokens[i]['score']}%)" for i, s in enumerate(top3)) if top3 else "sin datos"
    notify(
        "ANALISIS SEMANAL LISTO",
        f"TOP acumulacion esta semana:\n{top_str}\n\n"
        f"{len(report_tokens)} tokens analizados\n"
        f"{len(week_events)} eventos registrados en la semana\n\n"
        f"Abre tu dashboard para el analisis completo:"
        f"\n{VERCEL_URL or 'Configura VERCEL_URL en Railway'}",
        priority="urgent", tags="bar_chart,calendar",
        click_url=VERCEL_URL,
    )

    last_weekly_week = iso_week_now()
    week_events = []
    log("=== REPORTE SEMANAL ENVIADO ===")

def daily_report():
    """Resumen diario: cuantas notifico, cuantas pumpearon, mejor resultado, win rate, rugpulls."""
    global daily_notif_count
    log("=== GENERANDO RESUMEN DIARIO ===")

    # Actualizar tracking antes del resumen
    update_tracking()

    now = time.time()
    day_ago = now - 86400

    # Tokens trackeados en las ultimas 24h (incluye los ya removidos via week_events)
    recent_tracked = [t for t in tracked_tokens.values() if t["notified_at"] >= day_ago]
    all_recent = recent_tracked[:]

    pumped = [t for t in all_recent if t["status"] == "pumped" or t["max_mult"] >= 1.3]
    rugged_today = [r for r in rugged_tokens.values() if r["rugged_at"] >= day_ago]

    total_notif = daily_notif_count if daily_notif_count > 0 else len(all_recent)
    pumped_count = len(pumped)
    win_rate = round((pumped_count / total_notif) * 100) if total_notif > 0 else 0

    # Mejor resultado
    best = max(all_recent, key=lambda t: t["max_mult"], default=None)
    best_str = ""
    if best and best["max_mult"] > 1.0:
        m = best["max_mult"]
        ms = f"x{m:.2f}" if m >= 2 else f"+{(m-1)*100:.0f}%"
        best_str = f"Mejor: {best['symbol']} {ms}\n"

    # Lista de pumps
    pump_lines = []
    for t in sorted(pumped, key=lambda x: x["max_mult"], reverse=True)[:5]:
        m = t["max_mult"]
        ms = f"x{m:.2f}" if m >= 2 else f"+{(m-1)*100:.0f}%"
        pump_lines.append(f"  {t['symbol']} ({t['chain']}): {ms} [prob era {t['pump_prob']}%]")
    pump_str = "\n".join(pump_lines) if pump_lines else "  Ninguna alcanzo +30% aun"

    rug_str = ""
    if rugged_today:
        rug_lines = [f"  {r['symbol']}: -{r['liq_drop_pct']}% liq" for r in rugged_today[:5]]
        rug_str = f"\nRUGPULLS hoy ({len(rugged_today)}):\n" + "\n".join(rug_lines)

    # ── Win rate por tipo de señal y horario (si hay suficientes datos) ──
    sig_rates, hour_rates = compute_winrate_by_type()
    type_str = ""
    if sig_rates:
        top_types = [s for s in sig_rates if s["total"] >= 3][:5]
        if top_types:
            lines = [f"  {s['signal']}: {s['win_rate']}% ({s['total']} alertas)" for s in top_types]
            type_str = "\n\nWin rate por tipo de senal:\n" + "\n".join(lines)
    hour_str = ""
    if hour_rates:
        top_hours = [h for h in hour_rates if h["total"] >= 3][:3]
        if top_hours:
            lines = [f"  {h['hour_peru']:02d}:00 Peru: {h['win_rate']}% ({h['total']})" for h in top_hours]
            hour_str = "\n\nMejores horas (hora Peru):\n" + "\n".join(lines)

    body = (
        f"Resumen de las ultimas 24h:\n\n"
        f"Tokens notificados: {total_notif}\n"
        f"Pumpearon (+30%+): {pumped_count}\n"
        f"Win rate: {win_rate}%\n"
        f"{best_str}"
        f"\nMejores resultados:\n{pump_str}"
        f"{rug_str}"
        f"{type_str}"
        f"{hour_str}\n\n"
        f"Recuerda: la mayoria de memecoins van a cero. "
        f"Esto mide si el filtro mejora el ratio.\n"
        f"{VERCEL_URL or ''}"
    )

    notify(
        f"RESUMEN DIARIO — {pumped_count}/{total_notif} pumpearon ({win_rate}%)",
        body,
        priority="high", tags="bar_chart,sunrise",
        click_url=VERCEL_URL,
    )

    # Reset contador diario
    daily_notif_count = 0
    log("=== RESUMEN DIARIO ENVIADO ===")

def check_daily_report():
    """Verifica si toca el resumen diario + forense (cada dia a DAILY_UTC_HOUR = 7am)."""
    global last_daily_day, last_forensic_day
    t = time.gmtime()
    today = time.strftime("%Y-%m-%d", t)
    if t.tm_hour >= DAILY_UTC_HOUR and last_daily_day != today:
        last_daily_day = today
        # Forense primero (alimenta smart wallets), luego resumen
        if last_forensic_day != today:
            try:
                run_forensic_analysis()
            except Exception as e:
                log(f"[forense error] {e}")
        daily_report()

def check_weekly_report():
    """Verifica si toca generar el reporte (Lunes a la hora configurada)."""
    global last_weekly_week
    if FORCE_WEEKLY and last_weekly_week is None:
        weekly_report()
        return
    t = time.gmtime()
    if t.tm_wday == 0 and t.tm_hour >= WEEKLY_UTC_HOUR:
        if last_weekly_week != iso_week_now():
            weekly_report()

# ─── FLASK API (datos en tiempo real para Vercel) ────────────────────────────
def start_api_server():
    try:
        from flask import Flask, jsonify, request
        app = Flask(__name__)

        @app.after_request
        def add_cors(resp):
            resp.headers["Access-Control-Allow-Origin"] = "*"
            resp.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
            return resp

        @app.route("/api/live")
        def api_live():
            tokens = sorted(accum_state.values(), key=lambda t: t.get("score", 0), reverse=True)
            # Datos de tracking para el panel de rendimiento
            tracking = sorted(
                tracked_tokens.values(),
                key=lambda t: t.get("max_mult", 1), reverse=True
            )
            # Smart wallets / insiders rankeadas por score
            wallets_out = []
            for addr, sw in sorted(smart_wallets.items(), key=lambda kv: kv[1]["insider_score"], reverse=True)[:40]:
                wallets_out.append({
                    "address": addr,
                    "chain": sw.get("chain"),
                    "label": sw.get("label", short(addr)),
                    "tokens": sorted(sw.get("tokens", set())),
                    "n_tokens": len(sw.get("tokens", set())),
                    "total_usd": round(sw.get("total_usd", 0)),
                    "buys": sw.get("buys", 0),
                    "insider_score": sw.get("insider_score", 0),
                    "tag": sw.get("tag", "smart"),
                    "forensic": sw.get("forensic", False),
                    "last_seen": sw.get("last_seen", 0),
                    "tracked": addr in tracked_whale_set,
                })
            # Combos activos
            combos_out = []
            for c, e in combo_signals.items():
                if len(e.get("signals", {})) >= 2:
                    dex = e.get("dex") or {}
                    chain = e["chain"]
                    buy_url = dex.get("buy_url", "")
                    combos_out.append({
                        "symbol": e["symbol"], "chain": chain,
                        "contract": c,
                        "signals": list(e["signals"].keys()),
                        "n_signals": len(e["signals"]),
                        "score": sum(COMBO_WEIGHTS.get(s, 1) for s in e["signals"]),
                        "url": dex.get("url", ""),
                        "buy_url": buy_url,
                        "liq": dex.get("liq", 0),
                        "pump_prob": dex.get("pump_prob", 0),
                    })
            combos_out.sort(key=lambda x: x["score"], reverse=True)
            sig_rates, hour_rates = compute_winrate_by_type()
            combo_rates = compute_combo_winrate()
            return jsonify({
                "updated_at": int(time.time()),
                "tokens": tokens,
                "events": week_events[-30:],
                "week": iso_week_now(),
                "tracking": tracking,
                "rugged": list(rugged_tokens.values())[-20:],
                "daily_notif_count": daily_notif_count,
                "smart_wallets": wallets_out,
                "insider_alerts": insider_alerts[:30],
                "tracked_whales": len(tracked_whale_set),
                "combos": combos_out[:15],
                "winrate_by_signal": sig_rates,
                "winrate_by_hour": hour_rates,
                "winrate_by_combo": combo_rates[:15],
                "insider_convergences": sorted(insider_convergences.values(), key=lambda x: x["detected_at"], reverse=True)[:15],
                "insider_sells": insider_sells[:20],
                "market_context": get_market_context(),
                "positions": [
                    {
                        "contract": c, "symbol": p["symbol"], "chain": p["chain"],
                        "entry_price": p["entry_price"], "last_price": p["last_price"],
                        "mult": round(p["last_price"]/p["entry_price"], 2) if p["entry_price"]>0 else 1,
                        "peak_mult": round(p["peak_mult"], 2),
                        "targets_hit": p["targets_hit"],
                        "entry_ts": p["entry_ts"],
                    } for c, p in my_positions.items()
                ],
            })

        @app.route("/api/forensic")
        def api_forensic():
            # Endpoint para disparar forense manualmente desde la UI
            try:
                threading.Thread(target=run_forensic_analysis, daemon=True).start()
                return jsonify({"status": "started"})
            except Exception as e:
                return jsonify({"status": "error", "msg": str(e)})

        @app.route("/api/portfolio/<chain>/<address>")
        def api_portfolio(chain, address):
            # Portfolio superficial de una wallet (tokens que tiene actualmente)
            try:
                holdings = get_wallet_portfolio(address, chain.upper())
                return jsonify({"address": address, "chain": chain, "holdings": holdings})
            except Exception as e:
                return jsonify({"address": address, "holdings": [], "error": str(e)})

        @app.route("/api/examine/<chain>/<address>")
        def api_examine(chain, address):
            # Examen manual de una wallet: veredicto honesto
            try:
                result = examine_wallet(address, chain.upper())
                return jsonify(result)
            except Exception as e:
                return jsonify({"error": str(e)})

        @app.route("/api/add_wallet/<chain>/<address>")
        def api_add_wallet(chain, address):
            # Agrega una wallet examinada a seguimiento (tras visto bueno del usuario)
            try:
                sw = add_manual_wallet(address, chain.upper())
                if sw:
                    return jsonify({"status": "added", "score": sw["insider_score"], "tag": sw["tag"]})
                return jsonify({"status": "error", "msg": "no se pudo agregar"})
            except Exception as e:
                return jsonify({"status": "error", "msg": str(e)})

        @app.route("/api/position/add/<chain>/<address>/<price>")
        def api_add_position(chain, address, price):
            # Marca una moneda como 'estoy dentro'
            try:
                # Si no pasan precio (price=0 o 'auto'), usar el precio actual del dex
                p = float(price) if price not in ("0", "auto", "") else 0
                dex = get_dex(address, chain.upper())
                symbol = dex["name"] if dex else address[:6]
                if p <= 0 and dex:
                    p = float(dex.get("price", 0) or 0)
                if p <= 0:
                    return jsonify({"status": "error", "msg": "no se pudo determinar precio de entrada"})
                pos = add_position(address, symbol, chain.upper(), p)
                save_state(force=True)
                return jsonify({"status": "added", "symbol": symbol, "entry_price": p})
            except Exception as e:
                return jsonify({"status": "error", "msg": str(e)})

        @app.route("/api/position/remove/<address>")
        def api_remove_position(address):
            try:
                remove_position(address)
                save_state(force=True)
                return jsonify({"status": "removed"})
            except Exception as e:
                return jsonify({"status": "error", "msg": str(e)})

        @app.route("/api/health")
        def api_health():
            return jsonify({"status": "ok", "cycle": cycle_count})

        log(f"API server iniciado en puerto {PORT}")
        app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)
    except Exception as e:
        log(f"[api error] {e}")

# ─── CICLO PRINCIPAL ──────────────────────────────────────────────────────────
def scan():
    global cycle_count
    cycle_count += 1
    log(f"=== Ciclo {cycle_count} ===")
    scan_exchange_wallets_eth()
    scan_exchange_wallets_sol()
    scan_whale_wallets()
    scan_watchlist()
    scan_new_tokens()
    if cycle_count % ACCUM_EVERY == 1:
        scan_accumulation()
    # Seguir smart wallets cada 2 ciclos (las top 20 por score de insider)
    if cycle_count % 2 == 0 and tracked_whale_set:
        scan_tracked_whales()
    # Actualizar tracking post-notificacion cada 3 ciclos
    if cycle_count % 3 == 0 and tracked_tokens:
        log(f"-- Actualizando tracking de {len(tracked_tokens)} tokens --")
        update_tracking()
    # Monitorear posiciones propias (alertas de salida) cada 2 ciclos
    if cycle_count % 2 == 0 and my_positions:
        try:
            monitor_positions()
        except Exception as e:
            log(f"[posiciones error] {e}")
    # Limpiar señales de combo expiradas
    cleanup_combo_signals()
    # Monitor de anuncios coreanos (Upbit/Bithumb) cada 2 ciclos
    if cycle_count % 2 == 0:
        try:
            scan_korean_listings()
        except Exception as e:
            log(f"[korean error] {e}")
    # Precargar listas de exchanges en el primer ciclo (para verificacion de listing)
    if cycle_count == 1:
        log("-- Precargando listas de exchanges (spot + futuros) --")
        for ex in ["MEXC", "BINANCE", "BITGET", "BYBIT", "OKX"]:
            get_exchange_listing(ex)
            get_exchange_futures(ex)
    # Bootstrap: correr forense una vez al arrancar SOLO si no se cargo estado previo
    if cycle_count == 3 and len(smart_wallets) < 5:
        log("-- Bootstrap forense inicial (sin estado previo) --")
        try:
            run_forensic_analysis()
        except Exception as e:
            log(f"[forense bootstrap error] {e}")
    # Guardar estado cada 5 ciclos (con throttle interno de 10 min)
    if cycle_count % 5 == 0:
        save_state()
    check_daily_report()
    check_weekly_report()
    log(f"=== Ciclo {cycle_count} completo. Esperando {SCAN_INTERVAL}s ===\n")

# ─── INICIO ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    log("Alpha Terminal Bot v6 iniciado")
    log(f"  Ntfy           : {NTFY_TOPIC}")
    log(f"  Etherscan V2   : {'OK (ETH+BNB+BASE)' if ETHERSCAN_KEY else 'sin key'}")
    log(f"  GitHub         : {'OK' if GITHUB_TOKEN and GITHUB_REPO else 'sin configurar'}")
    log(f"  Vercel URL     : {VERCEL_URL or 'sin configurar'}")
    log(f"  Acumulacion    : {len(ACCUMULATION_LIST)} tokens DEX + {len(COINGECKO_TOKENS)} CEX")
    log(f"  Watchlist      : {len(WATCHLIST)} | Exchanges: {len(EXCHANGE_WALLETS_ETH)+len(EXCHANGE_WALLETS_SOL)} | Whales: {len(WHALE_WALLETS)}")
    log(f"  Reporte semanal: Lunes {WEEKLY_UTC_HOUR}:00 UTC ({WEEKLY_UTC_HOUR-5}:00 Peru)")
    log(f"  Forense+diario : {DAILY_UTC_HOUR}:00 UTC ({DAILY_UTC_HOUR-5}:00 Peru)")
    log(f"  Insiders       : top {MAX_TRACKED_WHALES} smart wallets, min {INSIDER_MIN_TOKENS} tokens")
    log(f"  Combo          : ventana {COMBO_WINDOW_H}h | Listing cache {LISTING_CACHE_MIN}min")
    log(f"  Prob pump min  : {MIN_PUMP_PROB}% | Rug si liq cae >{RUG_LIQ_DROP}% | Track {TRACK_HOURS}h")
    log("")

    # Iniciar API en thread separado
    api_thread = threading.Thread(target=start_api_server, daemon=True)
    api_thread.start()

    # Cargar estado persistido (insiders/smart wallets de sesiones anteriores)
    log("-- Cargando estado persistido --")
    load_state()

    notify(
        "Alpha Terminal v9 activo",
        f"Nuevas mejoras (Grupo D - final):\n"
        f"Alertas de SALIDA (x2/x3 y caida tras pico)\n"
        f"Contexto de mercado BTC en cada alerta\n"
        f"Alertas de crecimiento de holders\n\n"
        f"Marca posiciones con 'estoy dentro' para vigilar salida.\n"
        f"Smart wallets cargadas: {len(smart_wallets)}\n"
        f"{len(ACCUMULATION_LIST)} tokens acumulacion + {len(COINGECKO_TOKENS)} CEX",
        priority="high", tags="white_check_mark",
    )

    while True:
        try:
            scan()
        except Exception as e:
            log(f"[error critico] {e}")
            time.sleep(10)
        time.sleep(SCAN_INTERVAL)
