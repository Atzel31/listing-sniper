"""
hit_rate.py - Hit rate historico de las señales de Alpha Terminal.

Reconstruye el desempeño de todas las señales ya guardadas leyendo el estado
persistido del bot (data/state.json: combo_history, signal_outcomes,
insider_convergences, my_positions) y consultando GeckoTerminal OHLCV
(gratis, sin API key) para obtener max/min a 24h y 72h de cada señal.

Se usa de dos formas:
  1. Script:  python hit_rate.py [ruta/al/state.json] [--limit N]
     Sin ruta usa data/state.json local. --limit N procesa solo N señales
     (para el test rapido antes del histórico completo).
  2. Importado por bot.py, que expone el endpoint Flask /api/hitrate.

Escala de clasificacion (spec Modulo 1):
  BIG_WIN : max 72h >= +100%
  WIN     : max 24h >= +30%
  LOSS    : min 24h <= -20%  y nunca toco +30% antes
  NEUTRAL : resto (entre -20% y +30%)

Reglas: cualquier fallo de API deja la señal como "pendiente" (nunca crashea).
Señales sin contract address se cuentan como "no_medible".
"""

import os
import sys
import json
import time

import requests

API = "https://api.geckoterminal.com/api/v2"
STATE_PATH = "data/state.json"
REPORT_PATH = "hit_rate_report.json"
CACHE_PATH = "hit_rate_cache.json"

# GeckoTerminal usa estos nombres de red
CHAIN_MAP = {
    "ETH": "eth", "ETHEREUM": "eth", "ETHER": "eth",
    "BNB": "bsc", "BSC": "bsc",
    "BASE": "base",
    "SOL": "solana", "SOLANA": "solana",
}

# Escala de outcomes (fracciones, no %)
WIN_24H = 0.30      # +30% en 24h  -> WIN
BIG_WIN_72H = 1.00  # +100% en 72h -> BIG WIN
LOSS_24H = -0.20    # -20% en 24h  -> LOSS (si no toco +30% antes)

REQUEST_SLEEP = 2.0  # GeckoTerminal ~30 req/min -> 2s entre requests

# ─── Cache local (para reruns sin re-pegarle a la API) ───────────────────────
_cache = None


def _load_cache():
    global _cache
    if _cache is None:
        if os.path.exists(CACHE_PATH):
            try:
                with open(CACHE_PATH, encoding="utf-8") as f:
                    _cache = json.load(f)
            except Exception:
                _cache = {}
        else:
            _cache = {}
    return _cache


def _save_cache():
    if _cache is not None:
        try:
            with open(CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump(_cache, f)
        except Exception:
            pass


# ─── GeckoTerminal ───────────────────────────────────────────────────────────
class ApiError(Exception):
    """Fallo transitorio de GeckoTerminal (429/5xx/red). -> señal 'pending'."""


def _check(r):
    """Distingue fallo de API (429/5xx -> pending) de un 200 vacio (no_data)."""
    if r.status_code == 200:
        return
    # 429 rate limit o 5xx: es transitorio -> pendiente, reintentar despues.
    raise ApiError(f"HTTP {r.status_code}")


def _retry(fn, tries=3, backoff=5.0):
    """Reintenta una llamada a la API ante ApiError (429/5xx) con backoff.
    Tras agotar los intentos, re-lanza -> la señal queda 'pending'."""
    for attempt in range(tries):
        try:
            return fn()
        except ApiError:
            if attempt == tries - 1:
                raise
            time.sleep(backoff * (attempt + 1))


def _get_main_pool(network, contract):
    """Pool principal (mas liquidez) del token. Devuelve None si el token no
    tiene pools (200 vacio); lanza ApiError si la API falla (429/5xx)."""
    r = requests.get(f"{API}/networks/{network}/tokens/{contract}/pools", timeout=15)
    _check(r)
    pools = r.json().get("data", [])
    return pools[0]["attributes"]["address"] if pools else None


def _get_ohlcv(network, pool, ts_from, ts_to):
    """Velas horarias del pool en [ts_from, ts_to]. Cada vela: [ts,o,h,l,c,v].
    Lanza ApiError si la API falla (429/5xx)."""
    r = requests.get(
        f"{API}/networks/{network}/pools/{pool}/ohlcv/hour",
        params={"before_timestamp": int(ts_to), "limit": 1000},
        timeout=15,
    )
    _check(r)
    candles = r.json().get("data", {}).get("attributes", {}).get("ohlcv_list", [])
    return [c for c in candles if ts_from <= c[0] <= ts_to]


def measure_signal(contract, chain, ts):
    """
    Mide una señal: precio de entrada + max/min a 24h y 72h desde GeckoTerminal.
    Devuelve dict con status:
      "ok"          -> outcome + porcentajes
      "no_data"     -> no hubo pool/velas (medible pero sin datos historicos)
      "pending"     -> fallo de API; reintentar despues (NO crashea)
      "no_measurable" -> sin contract o cadena desconocida
    Cachea resultados "ok"/"no_data" por (network, contract, ts).
    """
    if not contract:
        return {"status": "no_measurable", "reason": "sin_contract"}
    network = CHAIN_MAP.get(str(chain).upper()) if chain else None
    if not network:
        return {"status": "no_measurable", "reason": f"chain_desconocida:{chain}"}

    cache = _load_cache()
    ckey = f"{network}:{contract.lower()}:{int(ts)}"
    if ckey in cache:
        return cache[ckey]

    try:
        pool = _retry(lambda: _get_main_pool(network, contract))
        time.sleep(REQUEST_SLEEP)
        if not pool:
            res = {"status": "no_data", "reason": "sin_pool"}
            cache[ckey] = res
            _save_cache()
            return res

        ts_end_72 = ts + 72 * 3600
        candles = _retry(lambda: _get_ohlcv(network, pool, ts, ts_end_72))
        time.sleep(REQUEST_SLEEP)
    except Exception as e:
        # Fallo de red/API tras reintentos: dejar pendiente, no cachear, no crashear.
        return {"status": "pending", "reason": f"api_error:{type(e).__name__}"}

    if not candles:
        res = {"status": "no_data", "reason": "sin_velas"}
        cache[ckey] = res
        _save_cache()
        return res

    candles.sort(key=lambda c: c[0])
    entry = candles[0][1]  # open de la primera vela dentro de la ventana
    if not entry or entry <= 0:
        res = {"status": "no_data", "reason": "entry_cero"}
        cache[ckey] = res
        _save_cache()
        return res

    ts_end_24 = ts + 24 * 3600
    c24 = [c for c in candles if c[0] <= ts_end_24]
    c72 = candles

    max_high_24 = max((c[2] for c in c24), default=entry)
    min_low_24 = min((c[3] for c in c24), default=entry)
    max_high_72 = max((c[2] for c in c72), default=entry)

    max_gain_24 = (max_high_24 - entry) / entry
    max_loss_24 = (min_low_24 - entry) / entry
    max_gain_72 = (max_high_72 - entry) / entry

    if max_gain_72 >= BIG_WIN_72H:
        outcome = "BIG_WIN"
    elif max_gain_24 >= WIN_24H:
        outcome = "WIN"
    elif max_loss_24 <= LOSS_24H and max_gain_24 < WIN_24H:
        outcome = "LOSS"
    else:
        outcome = "NEUTRAL"

    res = {
        "status": "ok",
        "outcome": outcome,
        "entry_price": entry,
        "max_gain_24h_pct": round(max_gain_24 * 100, 1),
        "max_loss_24h_pct": round(max_loss_24 * 100, 1),
        "max_gain_72h_pct": round(max_gain_72 * 100, 1),
        "candles": len(candles),
    }
    cache[ckey] = res
    _save_cache()
    return res


# ─── Extraccion de señales desde el estado persistido ────────────────────────
def _symbol_map():
    """
    Mapa SIMBOLO -> {contract, chain} para resolver señales que solo guardan
    el symbol (combo_history / signal_outcomes). Se arma desde las listas del
    bot si estan disponibles; si no, queda vacio y esas señales caen como
    no_medible (comportamiento honesto).
    """
    smap = {}
    try:
        from bot import ACCUMULATION_LIST, WATCHLIST
        for t in list(ACCUMULATION_LIST) + list(WATCHLIST):
            sym = str(t.get("name", "")).upper()
            if sym and sym not in smap:
                smap[sym] = {"contract": t["contract"], "chain": t["chain"]}
    except Exception:
        pass
    return smap


def build_signals(state, symbol_map=None):
    """
    Convierte el estado persistido en una lista uniforme de señales medibles:
      {token, contract, chain, ts, signals:[...], source}
    Fuentes:
      - insider_convergences: traen contract + chain + detected_at (medibles)
      - my_positions:         traen contract + chain + entry_ts (medibles)
      - combo_history:        solo symbol -> resuelto via symbol_map
      - signal_outcomes:      solo symbol -> resuelto via symbol_map
    Señales sin contract resoluble se marcan igual (contract=None) para
    contarlas como "no_medible" mas adelante.
    """
    if symbol_map is None:
        symbol_map = _symbol_map()
    out = []
    seen = set()

    def _add(token, contract, chain, ts, signals, source):
        key = (str(contract).lower() if contract else token, int(ts) // 3600)
        if key in seen:
            return
        seen.add(key)
        out.append({
            "token": token, "contract": contract, "chain": chain,
            "ts": int(ts), "signals": signals or [], "source": source,
        })

    # insider_convergences: dict contract -> {symbol, chain, detected_at, ...}
    conv = state.get("insider_convergences", {})
    if isinstance(conv, dict):
        conv = conv.values()
    for e in conv or []:
        c = e.get("contract") or e.get("address")
        _add(e.get("symbol", "?"), c, e.get("chain"),
             e.get("detected_at", e.get("ts", 0)),
             ["insider_convergence"], "insider_convergences")

    # my_positions: dict contract -> {symbol, chain, entry_ts, ...}
    pos = state.get("my_positions", {})
    if isinstance(pos, dict):
        for c, p in pos.items():
            _add(p.get("symbol", "?"), c, p.get("chain"),
                 p.get("entry_ts", 0), ["my_position"], "my_positions")

    # combo_history: [{symbol, signals, combo_key, ts, ...}]
    for c in state.get("combo_history", []) or []:
        sym = str(c.get("symbol", "?")).upper()
        m = symbol_map.get(sym, {})
        _add(c.get("symbol", "?"), m.get("contract"), m.get("chain"),
             c.get("ts", 0), c.get("signals", []), "combo_history")

    # signal_outcomes: [{symbol, signals, hour_utc, ts, ...}]
    for o in state.get("signal_outcomes", []) or []:
        sym = str(o.get("symbol", "?")).upper()
        m = symbol_map.get(sym, {})
        _add(o.get("symbol", "?"), m.get("contract"), m.get("chain"),
             o.get("ts", 0), o.get("signals", []), "signal_outcomes")

    return out


# ─── Reconstruccion y reporte ────────────────────────────────────────────────
def run_hit_rate(signals, limit=None, progress=None):
    """
    Mide una lista de señales y arma el reporte agregado.
    limit: procesar solo las primeras N (test rapido).
    progress: callback opcional progress(i, total, result) para logging.
    """
    if limit:
        signals = signals[:limit]
    total = len(signals)
    results = []
    for i, s in enumerate(signals):
        res = measure_signal(s.get("contract"), s.get("chain"), s.get("ts", 0))
        row = {
            "token": s.get("token", "?"),
            "contract": s.get("contract"),
            "chain": s.get("chain"),
            "ts": s.get("ts", 0),
            "signals": s.get("signals", []),
            "source": s.get("source", "?"),
            **res,
        }
        results.append(row)
        if progress:
            progress(i + 1, total, row)
    return _aggregate(results)


def _aggregate(results):
    ok = [r for r in results if r["status"] == "ok"]
    no_medible = [r for r in results if r["status"] == "no_measurable"]
    no_data = [r for r in results if r["status"] == "no_data"]
    pending = [r for r in results if r["status"] == "pending"]

    wins = [r for r in ok if r["outcome"] in ("WIN", "BIG_WIN")]
    hit_rate = round(len(wins) / len(ok) * 100, 1) if ok else 0.0

    # Por tipo de combo (clave = combinacion de señales ordenada)
    by_combo = {}
    for r in ok:
        key = "+".join(sorted(r["signals"])) or "sin_señal"
        d = by_combo.setdefault(key, {"total": 0, "wins": 0, "big_wins": 0})
        d["total"] += 1
        if r["outcome"] in ("WIN", "BIG_WIN"):
            d["wins"] += 1
        if r["outcome"] == "BIG_WIN":
            d["big_wins"] += 1
    combo_stats = []
    for key, d in by_combo.items():
        combo_stats.append({
            "combo": key, "total": d["total"], "wins": d["wins"],
            "big_wins": d["big_wins"],
            "hit_rate": round(d["wins"] / d["total"] * 100, 1) if d["total"] else 0,
        })
    combo_stats.sort(key=lambda x: (x["hit_rate"], x["total"]), reverse=True)

    best = max(ok, key=lambda r: r["max_gain_72h_pct"], default=None)
    worst = min(ok, key=lambda r: r["max_loss_24h_pct"], default=None)

    outcome_counts = {"BIG_WIN": 0, "WIN": 0, "NEUTRAL": 0, "LOSS": 0}
    for r in ok:
        outcome_counts[r["outcome"]] = outcome_counts.get(r["outcome"], 0) + 1

    return {
        "generated_at": int(time.time()),
        "total_signals": len(results),
        "measured": len(ok),
        "no_data": len(no_data),
        "pending": len(pending),
        "no_measurable": len(no_medible),
        "hit_rate_global": hit_rate,
        "outcomes": outcome_counts,
        "by_combo": combo_stats,
        "best": best,
        "worst": worst,
        "results": results,
    }


def generate_report(state=None, limit=None, progress=None, write=True):
    """Punto de entrada de alto nivel: estado -> reporte agregado."""
    if state is None:
        state = load_state_file()
    signals = build_signals(state)
    report = run_hit_rate(signals, limit=limit, progress=progress)
    if write:
        try:
            with open(REPORT_PATH, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    return report


def load_state_file(path=STATE_PATH):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


# ─── CLI ─────────────────────────────────────────────────────────────────────
def _cli():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    limit = None
    for a in sys.argv[1:]:
        if a.startswith("--limit"):
            try:
                limit = int(a.split("=")[1]) if "=" in a else int(sys.argv[sys.argv.index(a) + 1])
            except Exception:
                limit = None
    path = args[0] if args else STATE_PATH
    state = load_state_file(path)
    signals = build_signals(state)
    print(f"Señales encontradas en el estado: {len(signals)}")
    if limit:
        print(f"TEST: procesando solo {limit} señales\n")

    def prog(i, total, row):
        out = row.get("outcome", row["status"])
        g = row.get("max_gain_24h_pct")
        extra = f"  (24h max {g:+.1f}%)" if g is not None else ""
        print(f"  [{i}/{total}] {row['token']:<10} {out}{extra}")

    report = generate_report(state, limit=limit, progress=prog)
    print("\n=== HIT RATE ===")
    print(f"Medibles: {report['measured']}  |  sin datos: {report['no_data']}  |  "
          f"pendientes: {report['pending']}  |  no medibles: {report['no_measurable']}")
    if report["measured"]:
        print(f"Hit rate global (WIN+BIG_WIN): {report['hit_rate_global']}%")
        print(f"Outcomes: {report['outcomes']}")
        print("\nPor combo:")
        for c in report["by_combo"]:
            print(f"  {c['combo']:<40} {c['wins']}/{c['total']}  ({c['hit_rate']}%)")
        if report["best"]:
            b = report["best"]
            print(f"\nMejor: {b['token']} +{b['max_gain_72h_pct']}% (72h)")
        if report["worst"]:
            w = report["worst"]
            print(f"Peor:  {w['token']} {w['max_loss_24h_pct']}% (24h)")
    print(f"\nGuardado en {REPORT_PATH}")


if __name__ == "__main__":
    _cli()
