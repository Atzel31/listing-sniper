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
    }
    global daily_notif_count
    daily_notif_count += 1

def update_tracking():
    """Actualiza el rendimiento de los tokens trackeados y detecta rugpulls."""
    now = time.time()
    to_remove = []
    for contract, t in list(tracked_tokens.items()):
        # Expirar tras TRACK_HOURS
        age_h = (now - t["notified_at"]) / 3600
        if age_h > TRACK_HOURS and t["status"] == "tracking":
            t["status"] = "expired"
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

# ─── ETHERSCAN V2 MULTICHAIN ─────────────────────────────────────────────────
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
            if is_watchlist:
                notify_exchange_move(wallet["exchange"], token_name, "ETH", dex, is_watchlist=True)
            elif contract not in seen_contracts:
                origins = get_exchange_origin_evm(contract, "ETH")
                time.sleep(0.3)
                origin_str = f"Origen: {', '.join(origins)}\n" if origins else ""
                origin_str += f"Prob. de pump: {pprob}%\n"
                notify_new_token(dex["name"], "ETH", score, dex, wallet["exchange"], origin_str)
                start_tracking(contract, dex["name"], "ETH", dex, pprob, wallet["exchange"])
                seen_contracts.add(contract)
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
            if is_watchlist:
                notify_exchange_move(wallet["exchange"], token_name, "SOL", dex, is_watchlist=True)
            elif mint not in seen_contracts:
                notify_new_token(dex["name"], "SOL", score, dex, wallet["exchange"], f"Prob. de pump: {pprob}%\n")
                start_tracking(mint, dex["name"], "SOL", dex, pprob, wallet["exchange"])
                seen_contracts.add(mint)
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
        time.sleep(0.3)

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
                register_smart_wallet(to_addr, chain, entry)
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

def register_smart_wallet(addr, chain, entry, forensic=False, label=""):
    """Crea o actualiza una smart wallet y recalcula su score de insider."""
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
        sw = register_smart_wallet(addr, chain, existing, forensic=True,
                                   label=f"Insider hist. {symbol}")
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
        for tx in recent:
            c = tx.get("contractAddress", "").lower()
            to_addr = tx.get("to", "").lower()
            if c and to_addr == addr:  # la wallet RECIBIO el token (compro)
                new_tokens.add(c)
        prev_seen = w.get("last_seen_tokens", set())
        fresh = new_tokens - prev_seen
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
            insider_alerts.insert(0, {
                "ts": int(now), "wallet": addr, "token": dex["name"],
                "chain": chain, "tag": w.get("tag"), "score": w.get("insider_score"),
                "url": dex.get("url", ""),
            })
            del insider_alerts[50:]
        w["last_seen_tokens"] = new_tokens
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

    body = (
        f"Resumen de las ultimas 24h:\n\n"
        f"Tokens notificados: {total_notif}\n"
        f"Pumpearon (+30%+): {pumped_count}\n"
        f"Win rate: {win_rate}%\n"
        f"{best_str}"
        f"\nMejores resultados:\n{pump_str}"
        f"{rug_str}\n\n"
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
        from flask import Flask, jsonify
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
            })

        @app.route("/api/forensic")
        def api_forensic():
            # Endpoint para disparar forense manualmente desde la UI
            try:
                threading.Thread(target=run_forensic_analysis, daemon=True).start()
                return jsonify({"status": "started"})
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
    # Bootstrap: correr forense una vez al arrancar (tras acumular algo de datos)
    if cycle_count == 3:
        log("-- Bootstrap forense inicial --")
        try:
            run_forensic_analysis()
        except Exception as e:
            log(f"[forense bootstrap error] {e}")
    check_daily_report()
    check_weekly_report()
    log(f"=== Ciclo {cycle_count} completo. Esperando {SCAN_INTERVAL}s ===\n")

# ─── INICIO ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    log("Alpha Terminal Bot v5 iniciado")
    log(f"  Ntfy           : {NTFY_TOPIC}")
    log(f"  Etherscan V2   : {'OK (ETH+BNB+BASE)' if ETHERSCAN_KEY else 'sin key'}")
    log(f"  GitHub         : {'OK' if GITHUB_TOKEN and GITHUB_REPO else 'sin configurar'}")
    log(f"  Vercel URL     : {VERCEL_URL or 'sin configurar'}")
    log(f"  Acumulacion    : {len(ACCUMULATION_LIST)} tokens DEX + {len(COINGECKO_TOKENS)} CEX")
    log(f"  Watchlist      : {len(WATCHLIST)} | Exchanges: {len(EXCHANGE_WALLETS_ETH)+len(EXCHANGE_WALLETS_SOL)} | Whales: {len(WHALE_WALLETS)}")
    log(f"  Reporte semanal: Lunes {WEEKLY_UTC_HOUR}:00 UTC ({WEEKLY_UTC_HOUR-5}:00 Peru)")
    log(f"  Forense+diario : {DAILY_UTC_HOUR}:00 UTC ({DAILY_UTC_HOUR-5}:00 Peru)")
    log(f"  Insiders       : top {MAX_TRACKED_WHALES} smart wallets, min {INSIDER_MIN_TOKENS} tokens")
    log(f"  Prob pump min  : {MIN_PUMP_PROB}% | Rug si liq cae >{RUG_LIQ_DROP}% | Track {TRACK_HOURS}h")
    log("")

    # Iniciar API en thread separado
    api_thread = threading.Thread(target=start_api_server, daemon=True)
    api_thread.start()

    notify(
        "Alpha Terminal v5 activo",
        f"Nuevo modulo de INSIDERS:\n"
        f"Forense historico diario ({DAILY_UTC_HOUR-5}:00 am Peru)\n"
        f"Smart wallets que compran 2+ tokens de tu lista\n"
        f"Score de insider (dinero + coincidencias + actividad)\n"
        f"Seguimiento de top {MAX_TRACKED_WHALES} wallets activas\n\n"
        f"Mantiene: prob. pump, tracking, rugpull, resumen diario\n"
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
