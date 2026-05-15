import os
import time
import requests

NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "listingsniper-atzel")
ETHERSCAN_KEY = os.environ.get("ETHERSCAN_KEY", "")
SCAN_INTERVAL = 60

EXCHANGE_WALLETS = [
    {"address": "0x75e89d5979E4f6Fba9F97c104c2F0AFB3F1dcB88", "exchange": "MEXC"},
    {"address": "0x6cc5f688a315f3dc28a7781717a9a798a59fda7b", "exchange": "MEXC"},
    {"address": "0xd24400ae8BfEBb18cA49Be86258a3C749cf46853", "exchange": "MEXC"},
    {"address": "0x1ab4973a48dc892cd9971ece8e01dcc7688f8f23", "exchange": "BITGET"},
    {"address": "0x0d0707963952f2fba59dd06f2b425ace40b492fe", "exchange": "BITGET"},
]

seen = set()

def send_ntfy(title, body, priority="default"):
    try:
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=body.encode("utf-8"),
            headers={
                "Title": title,
                "Priority": priority,
                "Tags": "rotating_light" if priority == "urgent" else "bell",
            },
            timeout=10,
        )
    except Exception as e:
        print(f"[ntfy error] {e}")

def fmt_usd(n):
    if n >= 1_000_000:
        return f"${n/1_000_000:.2f}M"
    if n >= 1_000:
        return f"${n/1_000:.1f}K"
    return f"${n:.0f}"

def get_wallet_tokens(address):
    try:
        key = ETHERSCAN_KEY or "YourApiKeyToken"
        url = (
            f"https://api.etherscan.io/api"
            f"?module=account&action=tokentx"
            f"&address={address}&sort=desc&page=1&offset=30"
            f"&apikey={key}"
        )
        r = requests.get(url, timeout=10)
        data = r.json()
        if data.get("status") != "1":
            return []
        now = time.time()
        recent = [tx for tx in data["result"] if now - int(tx["timeStamp"]) < 14400]
        return list({tx["contractAddress"] for tx in recent if tx.get("contractAddress")})
    except Exception as e:
        print(f"[etherscan error] {e}")
        return []

def get_dexscreener(contract, chain_id="ethereum"):
    try:
        url = f"https://api.dexscreener.com/latest/dex/tokens/{contract}"
        r = requests.get(url, timeout=10)
        data = r.json()
        pairs = [p for p in (data.get("pairs") or []) if p.get("chainId") == chain_id]
        if not pairs:
            return None
        best = sorted(pairs, key=lambda p: p.get("liquidity", {}).get("usd", 0), reverse=True)[0]
        return {
            "name": best.get("baseToken", {}).get("symbol", "UNKNOWN"),
            "liquidity": best.get("liquidity", {}).get("usd", 0),
            "volume24h": best.get("volume", {}).get("h24", 0),
            "price_change_1h": best.get("priceChange", {}).get("h1", 0),
            "txns": (best.get("txns", {}).get("h24", {}).get("buys", 0) +
                     best.get("txns", {}).get("h24", {}).get("sells", 0)),
            "url": f"https://dexscreener.com/ethereum/{contract}",
        }
    except Exception as e:
        print(f"[dexscreener error] {e}")
        return None

def get_boosted_tokens(chain_id):
    try:
        r = requests.get("https://api.dexscreener.com/token-boosts/latest/v1", timeout=10)
        data = r.json()
        return [t for t in (data if isinstance(data, list) else []) if t.get("chainId") == chain_id][:6]
    except:
        return []

def score_token(liq, vol, change_1h, txns, exchange):
    s = 50
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

    if change_1h > 50: s -= 10
    elif change_1h > 20: s -= 4
    elif change_1h > 5: s += 6
    elif change_1h < -20: s -= 6

    if exchange == "MEXC": s += 6
    elif exchange == "BITGET": s += 4

    return max(5, min(95, round(s)))

def alert_token(name, contract, chain, exchange, dex, score):
    emoji = "🟢" if score >= 70 else "🟡" if score >= 45 else "🔴"
    priority = "urgent" if score >= 70 else "high" if score >= 45 else "default"
    title = f"{emoji} {name} ({chain}) — Score {score}/100"
    body = "\n".join([
        f"Fuente: {exchange}",
        f"Liquidez: {fmt_usd(dex['liquidity'])}",
        f"Vol 24h: {fmt_usd(dex['volume24h'])}",
        f"Precio 1h: {'+' if dex['price_change_1h'] >= 0 else ''}{dex['price_change_1h']:.1f}%",
        f"Contrato: {contract[:20]}...",
        f"Ver: {dex['url']}",
    ])
    print(f"[ALERTA] {title}")
    send_ntfy(title, body, priority)

def scan():
    print(f"[scan] Iniciando ciclo — {time.strftime('%H:%M:%S')}")

    # Scan wallets ETH
    for w in EXCHANGE_WALLETS:
        contracts = get_wallet_tokens(w["address"])
        time.sleep(0.5)
        for contract in contracts:
            if contract in seen:
                continue
            dex = get_dexscreener(contract)
            time.sleep(0.4)
            if not dex or dex["liquidity"] < 5000:
                continue
            seen.add(contract)
            score = score_token(
                dex["liquidity"], dex["volume24h"],
                dex["price_change_1h"], dex["txns"], w["exchange"]
            )
            alert_token(dex["name"], contract, "ETH", w["exchange"], dex, score)
            time.sleep(0.5)

    # Scan DexScreener boosted
    for chain_id, chain_label in [("ethereum", "ETH"), ("solana", "SOL")]:
        boosted = get_boosted_tokens(chain_id)
        for token in boosted:
            addr = token.get("tokenAddress")
            if not addr or addr in seen:
                continue
            dex = get_dexscreener(addr, chain_id)
            time.sleep(0.4)
            if not dex or dex["liquidity"] < 5000:
                continue
            seen.add(addr)
            score = score_token(
                dex["liquidity"], dex["volume24h"],
                dex["price_change_1h"], dex["txns"], "DEXSCREENER"
            )
            dex["url"] = f"https://dexscreener.com/{chain_id}/{addr}"
            alert_token(dex["name"], addr, chain_label, "DEXSCREENER", dex, score)
            time.sleep(0.4)

    print(f"[scan] Ciclo completo. Esperando {SCAN_INTERVAL}s...")

if __name__ == "__main__":
    print(f"[bot] Listing Sniper iniciado — topic ntfy: {NTFY_TOPIC}")
    send_ntfy("🚀 Listing Sniper", "Bot iniciado correctamente. Monitoreando MEXC y Bitget.", "high")
    while True:
        try:
            scan()
        except Exception as e:
            print(f"[error] {e}")
        time.sleep(SCAN_INTERVAL)
