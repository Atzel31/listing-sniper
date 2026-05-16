import os
import time
import requests

# ─── CONFIGURACIÓN ────────────────────────────────────────────────────────────
NTFY_TOPIC     = os.environ.get("NTFY_TOPIC", "listingsniper-atzel")
ETHERSCAN_KEY  = os.environ.get("ETHERSCAN_KEY", "")
HELIUS_KEY     = os.environ.get("HELIUS_KEY", "")
SCAN_INTERVAL  = 60  # segundos entre ciclos

# ─── WALLETS ETH — verificadas en Etherscan con etiqueta oficial ──────────────
WALLETS_ETH = [
    # MEXC
    {"address": "0x75e89d5979E4f6Fba9F97c104c2F0AFB3F1dcB88", "exchange": "MEXC"},
    {"address": "0x6cc5f688a315f3dc28a7781717a9a798a59fda7b", "exchange": "MEXC"},
    {"address": "0xd24400ae8BfEBb18cA49Be86258a3C749cf46853", "exchange": "MEXC"},
    {"address": "0x4976a4a02f38326660d17bf34b431dc6e2eb2327", "exchange": "MEXC"},
    # BITGET
    {"address": "0x1ab4973a48dc892cd9971ece8e01dcc7688f8f23", "exchange": "BITGET"},
    {"address": "0x0d0707963952f2fba59dd06f2b425ace40b492fe", "exchange": "BITGET"},
    {"address": "0xf89d7b9c864f589bbF53a82105107622B35EaA40", "exchange": "BITGET"},
    # BYBIT
    {"address": "0xf89d7b9c864f589bbf53a82105107622b35eaa40", "exchange": "BYBIT"},
    {"address": "0xbaed383ede0e5d9d72430661f3285daa77e9439f", "exchange": "BYBIT"},
    {"address": "0xa7a93fd0a276fc1c0197a5b5623ed117786eed06", "exchange": "BYBIT"},
    {"address": "0x18e296053cbdf986196903e889b7dca7a73882f6", "exchange": "BYBIT"},
    # BINANCE
    {"address": "0xf977814e90da44bfa03b6295a0616a897441acec", "exchange": "BINANCE"},
    {"address": "0x631fc1ea2270e98fbd9d92658ece0f5a269aa161", "exchange": "BINANCE"},
    {"address": "0x161ba15a5f335c9f06bb5bbb0a9ce14076fbb645", "exchange": "BINANCE"},
    {"address": "0xbd612a3f30dca67bf60a39fd0d35e39b7ab80774", "exchange": "BINANCE"},
    # OKX
    {"address": "0x4b4e14a3773ee558b6597070797fd51eb48606e5", "exchange": "OKX"},
    {"address": "0x4e7b110335511f662fdbb01bf958a7844118c0d4", "exchange": "OKX"},
    {"address": "0xa9ac43f5b5e38155a288d1a01d2cbc4478e14573", "exchange": "OKX"},
    {"address": "0xa7efae728d2936e78bda97dc267687568dd593f3", "exchange": "OKX"},
]

# ─── WALLETS SOL — verificadas en Solscan con etiqueta oficial ────────────────
WALLETS_SOL = [
    # MEXC
    {"address": "ASTyfSima4LLAdDgoFGkgqoKowG1LZFDr9fAQrg7iaJZ", "exchange": "MEXC"},
    # BYBIT
    {"address": "AC5RDfQFmDS1deWZos921JfqscXdByf8BKHs5ACWjtW2", "exchange": "BYBIT"},
    {"address": "iGdFcQoyR2MwbXMHQskhmNsqddZ6rinsipHc4TNSdwu",  "exchange": "BYBIT"},
    # BINANCE
    {"address": "5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9", "exchange": "BINANCE"},
    {"address": "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM", "exchange": "BINANCE"},
    {"address": "53unSgGWqEWANcPYRF35B2Bgf8BkszUtcccKiXwGGLyr",  "exchange": "BINANCE"},
]

# ─── HELPERS ──────────────────────────────────────────────────────────────────
seen = set()  # contratos/mints ya alertados esta sesión

def fmt_usd(n):
    if not n or n != n: return "$0"
    if n >= 1_000_000: return f"${n/1_000_000:.2f}M"
    if n >= 1_000:     return f"${n/1_000:.1f}K"
    return f"${n:.0f}"

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

# ─── NTFY ─────────────────────────────────────────────────────────────────────
def send_ntfy(title, body, priority="default"):
    try:
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=body.encode("utf-8"),
            headers={
                "Title": title,
                "Priority": priority,
                "Tags": "rocket" if priority == "urgent" else "bell",
            },
            timeout=10,
        )
        log(f"📲 Ntfy enviado: {title}")
    except Exception as e:
        log(f"[ntfy error] {e}")

# ─── SCORE ────────────────────────────────────────────────────────────────────
def compute_score(liq, vol, change_1h, txns, exchange, chain):
    s = 50

    # Liquidez
    if liq > 200_000:  s += 18
    elif liq > 80_000: s += 12
    elif liq > 20_000: s += 5
    else:              s -= 18

    # Volumen 24h
    if vol > 500_000:   s += 12
    elif vol > 100_000: s += 6
    elif vol > 10_000:  s += 2
    else:               s -= 8

    # Txns
    if txns > 1000:  s += 10
    elif txns > 300: s += 5
    elif txns < 30:  s -= 8

    # Cambio precio 1h
    pc = float(change_1h or 0)
    if pc > 50:    s -= 10
    elif pc > 20:  s -= 4
    elif pc > 5:   s += 6
    elif pc < -20: s -= 6

    # Exchange bonus
    bonuses = {"MEXC": 8, "BITGET": 5, "BYBIT": 6, "BINANCE": 4, "OKX": 4, "DEXSCREENER": 2}
    s += bonuses.get(exchange, 0)

    # SOL bonus — ecosystem más rápido para meme listings
    if chain == "SOL":
        s += 4

    return max(5, min(95, round(s)))

# ─── DEXSCREENER ──────────────────────────────────────────────────────────────
def get_dex_token(address, chain_id):
    """Obtiene datos de un token desde DexScreener. Sin API key."""
    try:
        r = requests.get(
            f"https://api.dexscreener.com/latest/dex/tokens/{address}",
            timeout=12
        )
        data = r.json()
        pairs = [p for p in (data.get("pairs") or []) if p.get("chainId") == chain_id]
        if not pairs:
            return None
        best = sorted(pairs, key=lambda p: p.get("liquidity", {}).get("usd", 0), reverse=True)[0]
        return {
            "name":     best.get("baseToken", {}).get("symbol", "UNKNOWN"),
            "liq":      best.get("liquidity", {}).get("usd", 0),
            "vol":      best.get("volume", {}).get("h24", 0),
            "change1h": best.get("priceChange", {}).get("h1", 0),
            "txns":     (best.get("txns", {}).get("h24", {}).get("buys", 0) +
                         best.get("txns", {}).get("h24", {}).get("sells", 0)),
            "price":    best.get("priceUsd", "0"),
        }
    except Exception as e:
        log(f"[dexscreener] {e}")
        return None

def get_boosted_tokens(chain_id):
    """Tokens con boost activo en DexScreener — señal de momentum."""
    try:
        r = requests.get(
            "https://api.dexscreener.com/token-boosts/latest/v1",
            timeout=12
        )
        data = r.json()
        return [t for t in (data if isinstance(data, list) else [])
                if t.get("chainId") == chain_id][:8]
    except:
        return []

# ─── ALERTA ───────────────────────────────────────────────────────────────────
def fire_alert(name, address, chain, exchange, dex):
    score = compute_score(dex["liq"], dex["vol"], dex["change1h"], dex["txns"], exchange, chain)
    emoji = "🟢" if score >= 70 else "🟡" if score >= 45 else "🔴"
    priority = "urgent" if score >= 70 else "high" if score >= 45 else "default"

    explorer = (f"https://dexscreener.com/solana/{address}"
                if chain == "SOL"
                else f"https://dexscreener.com/ethereum/{address}")
    buy_link = (f"https://jup.ag/swap/SOL-{address}"
                if chain == "SOL"
                else f"https://app.uniswap.org/#/swap?outputCurrency={address}")

    title = f"{emoji} {name} ({chain}) — Score {score}/100"
    body = "\n".join([
        f"Exchange: {exchange}",
        f"Liquidez: {fmt_usd(dex['liq'])} | Vol24h: {fmt_usd(dex['vol'])}",
        f"Precio 1h: {'+' if float(dex['change1h'] or 0) >= 0 else ''}{float(dex['change1h'] or 0):.1f}%",
        f"Contrato: {address[:28]}...",
        f"Comprar: {buy_link}",
        f"Chart: {explorer}",
    ])

    log(f"🔔 ALERTA [{score}/100] {name} ({chain}) — {exchange}")
    send_ntfy(title, body, priority)

# ─── SCAN ETH — wallets de exchanges ─────────────────────────────────────────
def scan_eth_wallets():
    key = ETHERSCAN_KEY or "YourApiKeyToken"
    for w in WALLETS_ETH:
        try:
            log(f"ETH scan: {w['exchange']} {w['address'][:10]}...")
            url = (f"https://api.etherscan.io/api"
                   f"?module=account&action=tokentx"
                   f"&address={w['address']}&sort=desc&page=1&offset=30"
                   f"&apikey={key}")
            r = requests.get(url, timeout=12)
            data = r.json()
            if data.get("status") != "1":
                time.sleep(0.5)
                continue

            now = time.time()
            # Txs de las últimas 4 horas
            recent = [tx for tx in data["result"]
                      if now - int(tx["timeStamp"]) < 14400]
            contracts = list({tx["contractAddress"]
                              for tx in recent
                              if tx.get("contractAddress")})

            for contract in contracts:
                if contract in seen:
                    continue
                dex = get_dex_token(contract, "ethereum")
                time.sleep(0.4)
                if not dex or dex["liq"] < 5000:
                    continue
                seen.add(contract)
                fire_alert(dex["name"], contract, "ETH", w["exchange"], dex)
                time.sleep(0.5)

            time.sleep(0.4)
        except Exception as e:
            log(f"[eth wallet error] {e}")
            time.sleep(1)

# ─── SCAN SOL — wallets via Solscan público (sin key) ────────────────────────
def get_sol_wallet_transfers(address):
    """
    Usa el API público de Solscan para obtener transferencias SPL recientes.
    Sin API key — hasta 100 req/día gratis.
    Si tienes Helius key, usa esa vía (más límite).
    """
    try:
        # Helius tiene mejor rate limit si hay key disponible
        if HELIUS_KEY:
            url = (f"https://api.helius.xyz/v0/addresses/{address}/transactions"
                   f"?api-key={HELIUS_KEY}&limit=30&type=TRANSFER")
            r = requests.get(url, timeout=12)
            if r.ok:
                txs = r.json()
                mints = set()
                for tx in txs:
                    for transfer in tx.get("tokenTransfers", []):
                        mint = transfer.get("mint")
                        if mint:
                            mints.add(mint)
                return list(mints)

        # Fallback: Solscan API público
        url = (f"https://public-api.solscan.io/account/splTransfers"
               f"?account={address}&limit=30&offset=0")
        r = requests.get(url, timeout=12,
                         headers={"User-Agent": "listing-sniper-bot/1.0"})
        if not r.ok:
            return []
        data = r.json()
        items = data.get("data", [])
        mints = {item.get("tokenAddress") for item in items if item.get("tokenAddress")}
        return list(mints)

    except Exception as e:
        log(f"[sol transfers error] {e}")
        return []

def scan_sol_wallets():
    for w in WALLETS_SOL:
        try:
            log(f"SOL scan: {w['exchange']} {w['address'][:10]}...")
            mints = get_sol_wallet_transfers(w["address"])
            time.sleep(0.5)

            for mint in mints:
                if not mint or mint in seen:
                    continue
                dex = get_dex_token(mint, "solana")
                time.sleep(0.4)
                if not dex or dex["liq"] < 3000:  # umbral más bajo para SOL (tokens más nuevos)
                    continue
                seen.add(mint)
                fire_alert(dex["name"], mint, "SOL", w["exchange"], dex)
                time.sleep(0.5)

            time.sleep(0.5)
        except Exception as e:
            log(f"[sol wallet error] {e}")
            time.sleep(1)

# ─── SCAN DEXSCREENER BOOSTED — ETH + SOL ────────────────────────────────────
def scan_dex_boosted():
    for chain_id, chain_label in [("ethereum", "ETH"), ("solana", "SOL")]:
        log(f"DexScreener boosted scan ({chain_label})...")
        tokens = get_boosted_tokens(chain_id)
        for token in tokens:
            addr = token.get("tokenAddress")
            if not addr or addr in seen:
                continue
            dex = get_dex_token(addr, chain_id)
            time.sleep(0.4)
            if not dex or dex["liq"] < 3000:
                continue
            seen.add(addr)
            fire_alert(dex["name"], addr, chain_label, "DEXSCREENER", dex)
            time.sleep(0.4)

# ─── CICLO PRINCIPAL ──────────────────────────────────────────────────────────
def scan():
    log("── Iniciando ciclo ──")

    # 1. Wallets ETH de exchanges
    scan_eth_wallets()

    # 2. Wallets SOL de exchanges
    scan_sol_wallets()

    # 3. Tokens boosted en DexScreener (ETH + SOL)
    scan_dex_boosted()

    log(f"✓ Ciclo completo. Esperando {SCAN_INTERVAL}s...\n")

# ─── INICIO ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    log(f"🚀 Listing Sniper iniciado")
    log(f"   Ntfy topic : {NTFY_TOPIC}")
    log(f"   Etherscan  : {'✓ key configurada' if ETHERSCAN_KEY else '⚠ sin key (modo lento)'}")
    log(f"   Helius SOL : {'✓ key configurada' if HELIUS_KEY else '⚠ sin key (usando Solscan público)'}")
    log(f"   Wallets ETH: {len(WALLETS_ETH)} | Wallets SOL: {len(WALLETS_SOL)}")
    log("")

    send_ntfy(
        "🚀 Listing Sniper activo",
        f"Bot iniciado.\nMonitoreando {len(WALLETS_ETH)} wallets ETH y {len(WALLETS_SOL)} wallets SOL.\nExchanges: MEXC, Bitget, Bybit, Binance, OKX",
        "high"
    )

    while True:
        try:
            scan()
        except Exception as e:
            log(f"[error crítico] {e}")
            time.sleep(10)
        time.sleep(SCAN_INTERVAL)
