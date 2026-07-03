"""
insider_quality.py - Filtro de calidad para wallets insider/smart money.

Objetivo (spec Modulo 2): sacar bots y market makers de las wallets
trackeadas. Se usa en dos momentos:
  1. Antes de agregar una wallet al top-N (register_smart_wallet en bot.py).
  2. Purga inicial de las ya listadas (purge_wallets, al arrancar el bot).

Una wallet se DESCARTA si:
  - Es un contrato (eth_getCode != 0x)               -> no es un insider humano
  - TX totales > MAX_TX_COUNT (nonce)                -> bot / infraestructura
  - Tokens distintos en 30 dias > MAX_UNIQUE_TOKENS  -> market maker / spray bot

Usa Etherscan V2 multichain (misma ETHERSCAN_KEY del bot). SOL no es
verificable con estas APIs: se acepta sin filtrar (igual que el bot ya hace).

Regla de oro: cualquier fallo de API deja la wallet como "pending" y NO la
descarta (no perdemos insiders buenos por un 429). Solo se actua ante un
veredicto CONFIRMADO de baja calidad. Nunca crashea.

Umbrales configurables por entorno: MAX_TX_COUNT, MAX_UNIQUE_TOKENS.
"""

import os
import time

import requests

API = "https://api.etherscan.io/v2/api"

# Mapa de cadena -> chainid de Etherscan V2. SOL no aplica.
CHAIN_IDS = {"ETH": 1, "ETHEREUM": 1, "BNB": 56, "BSC": 56, "BASE": 8453}

ETHERSCAN_KEY = os.environ.get("ETHERSCAN_KEY", "").strip()

# Umbrales (spec: bot/MM probable). Overridable por entorno.
MAX_TX_COUNT = int(os.environ.get("MAX_TX_COUNT", "5000"))       # nonce > esto = bot
MAX_UNIQUE_TOKENS = int(os.environ.get("MAX_UNIQUE_TOKENS", "100"))  # tokens 30d > esto = MM

_REQ_SLEEP = 0.25  # ~5 req/s free tier


def _escan_get(params):
    """GET a Etherscan V2. Devuelve el JSON o None si la API falla (-> pending)."""
    p = dict(params)
    p["apikey"] = ETHERSCAN_KEY or "YourApiKeyToken"
    try:
        r = requests.get(API, params=p, timeout=20)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:
        return None


def _is_contract(chain_id, address):
    """True/False si es contrato, None si no se pudo determinar (pending)."""
    j = _escan_get({
        "chainid": chain_id, "module": "proxy",
        "action": "eth_getCode", "address": address, "tag": "latest",
    })
    if not j:
        return None
    code = j.get("result")
    # Un resultado valido es bytecode hex ("0x..."). Errores tipo
    # "Missing/Invalid API Key" o NOTOK NO son concluyentes -> pending.
    if not isinstance(code, str) or not code.startswith("0x"):
        return None
    return len(code) > 2  # "0x" = EOA; "0x60..." = contrato


def _total_tx(chain_id, address):
    """Nonce = tx salientes totales. int, o None si falla (pending)."""
    j = _escan_get({
        "chainid": chain_id, "module": "proxy",
        "action": "eth_getTransactionCount", "address": address, "tag": "latest",
    })
    if not j or "result" not in j:
        return None
    try:
        return int(j["result"], 16)  # viene en hex
    except (ValueError, TypeError):
        return None


def _unique_tokens_30d(chain_id, address):
    """Tokens ERC-20 distintos tocados en 30 dias. int, o None si falla."""
    j = _escan_get({
        "chainid": chain_id, "module": "account", "action": "tokentx",
        "address": address, "sort": "desc", "page": 1, "offset": 10000,
    })
    if not j:
        return None
    # status "0" con message "No transactions found" es un resultado valido (0 tokens)
    result = j.get("result")
    if not isinstance(result, list):
        if j.get("message", "").lower().startswith("no transactions"):
            return 0
        return None  # error real de API -> pending
    cutoff = int(time.time()) - 30 * 86400
    tokens = {
        tx.get("contractAddress", "").lower()
        for tx in result
        if tx.get("contractAddress") and int(tx.get("timeStamp", 0)) >= cutoff
    }
    return len(tokens)


def wallet_quality(address, chain="ETH"):
    """
    Evalua una wallet. Devuelve dict con:
      status: "ok" (verificada) | "pending" (fallo de API, no concluyente)
      valid:  True = insider valido | False = descartar (bot/MM/contrato)
      reason, is_contract, tx_total, tokens_30d
    NUNCA descarta por un fallo de API: en ese caso status="pending", valid=True
    (se mantiene la wallet; se reintentara luego).
    """
    chain = str(chain).upper()
    chain_id = CHAIN_IDS.get(chain)
    if chain_id is None:
        # SOL u otra cadena no verificable con Etherscan: aceptar sin filtrar.
        return {"status": "ok", "valid": True, "reason": "cadena no verificable (SOL)",
                "is_contract": False, "tx_total": 0, "tokens_30d": 0}

    # 1. Contrato?
    is_contract = _is_contract(chain_id, address)
    time.sleep(_REQ_SLEEP)
    if is_contract is None:
        return {"status": "pending", "valid": True, "reason": "api_error (getCode)",
                "is_contract": None, "tx_total": None, "tokens_30d": None}
    if is_contract:
        return {"status": "ok", "valid": False, "reason": "es un contrato (no insider humano)",
                "is_contract": True, "tx_total": None, "tokens_30d": None}

    # 2. TX totales (nonce)
    tx_total = _total_tx(chain_id, address)
    time.sleep(_REQ_SLEEP)
    if tx_total is None:
        return {"status": "pending", "valid": True, "reason": "api_error (txCount)",
                "is_contract": False, "tx_total": None, "tokens_30d": None}
    if tx_total > MAX_TX_COUNT:
        return {"status": "ok", "valid": False,
                "reason": f"demasiadas tx ({tx_total} > {MAX_TX_COUNT}) = bot/infra",
                "is_contract": False, "tx_total": tx_total, "tokens_30d": None}

    # 3. Tokens distintos en 30 dias
    tokens_30d = _unique_tokens_30d(chain_id, address)
    time.sleep(_REQ_SLEEP)
    if tokens_30d is None:
        return {"status": "pending", "valid": True, "reason": "api_error (tokentx)",
                "is_contract": False, "tx_total": tx_total, "tokens_30d": None}
    if tokens_30d > MAX_UNIQUE_TOKENS:
        return {"status": "ok", "valid": False,
                "reason": f"toca demasiados tokens en 30d ({tokens_30d} > {MAX_UNIQUE_TOKENS}) = MM/spray",
                "is_contract": False, "tx_total": tx_total, "tokens_30d": tokens_30d}

    return {"status": "ok", "valid": True, "reason": "insider selectivo",
            "is_contract": False, "tx_total": tx_total, "tokens_30d": tokens_30d}


def purge_wallets(wallets, chain_of, log=print):
    """
    Purga una coleccion de wallets ya listadas.
      wallets: iterable de addresses.
      chain_of: fn(address) -> chain ("ETH"/"BNB"/"BASE"/"SOL").
      log: funcion de logging (bot.log).
    Devuelve (a_descartar:set, motivos:dict). Las "pending" NO se descartan.
    Solo devuelve las direcciones; el caller decide como removerlas de sus
    estructuras (para no acoplar este modulo al estado del bot).
    """
    to_remove = set()
    reasons = {}
    n_checked = 0
    n_pending = 0
    for addr in list(wallets):
        q = wallet_quality(addr, chain_of(addr))
        n_checked += 1
        if q["status"] == "pending":
            n_pending += 1
            continue
        if not q["valid"]:
            to_remove.add(addr)
            reasons[addr] = q["reason"]
            log(f"  [purga insider] descartada {addr[:10]}... — {q['reason']}")
    log(f"[purga insider] revisadas {n_checked}, descartadas {len(to_remove)}, "
        f"pendientes {n_pending} (se reintentan luego)")
    return to_remove, reasons


if __name__ == "__main__":
    # Test rapido manual
    import sys
    addr = sys.argv[1] if len(sys.argv) > 1 else "0xab5801a7d398351b8be11c439e05c5b3259aec9b"
    chain = sys.argv[2] if len(sys.argv) > 2 else "ETH"
    print(f"Evaluando {addr} en {chain} (MAX_TX={MAX_TX_COUNT}, MAX_TOKENS={MAX_UNIQUE_TOKENS})")
    print(wallet_quality(addr, chain))
