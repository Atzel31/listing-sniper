"""
outcome_tracker.py - Tracker de outcomes hacia adelante (Modulo 3).

Cada señal/combo nuevo que emite Alpha Terminal se registra en un ledger y su
resultado se mide solo a 72h. Es la base de datos de contenido para OnChain
Sentinel (recap en X).

Flujo:
  1. Al emitir un combo/alerta -> register_signal(): guarda token, contract,
     chain, precio de entrada, tipo de combo, timestamp y contexto BTC.
  2. Job cada 6h -> check_pending(): actualiza max/min de las señales abiertas
     (<72h) y cierra las que cumplen 72h con la MISMA escala del Modulo 1
     (BIG_WIN/WIN/NEUTRAL/LOSS).
  3. /api/outcomes (bot.py): ultimas 10 cerradas + hit rate rolling 7 y 30 dias.
  4. get_weekly_recap(): texto para el recap semanal (wins y losses, sin
     cherry-picking).

Persistencia: el ledger se serializa via export_ledger()/load_ledger() y viaja
dentro del snapshot de estado que el bot ya commitea a GitHub (data/state.json).

Regla de oro: cualquier fallo de API deja la señal abierta/"pending" y nunca
crashea. Se reintenta en el siguiente ciclo de 6h.

Escala (identica al Modulo 1):
  BIG_WIN : max >= +100% (72h)
  WIN     : max >= +30%
  LOSS    : min <= -20% y nunca llego a +30%
  NEUTRAL : resto
"""

import time
from datetime import datetime, timezone, timedelta

import requests

import hit_rate  # reutiliza CHAIN_MAP, ApiError y el backoff de GeckoTerminal

API = hit_rate.API
CHAIN_MAP = hit_rate.CHAIN_MAP

WIN = 0.30
BIG_WIN = 1.00
LOSS = -0.20
WINDOW_H = 72

# Ledger en memoria; se persiste via export/load_ledger dentro del estado.
_ledger = {"pending": [], "closed": []}


# ─── Precio en vivo (GeckoTerminal, sin key) ─────────────────────────────────
def _live_price(network, contract):
    """Precio USD actual del token. float, o None si la API falla (-> pending)."""
    def _call():
        r = requests.get(f"{API}/networks/{network}/tokens/{contract}", timeout=15)
        hit_rate._check(r)  # 429/5xx -> ApiError -> reintento/pending
        attr = r.json().get("data", {}).get("attributes", {})
        p = attr.get("price_usd")
        return float(p) if p else None
    try:
        return hit_rate._retry(_call)
    except Exception:
        return None


# ─── Registro de señales ─────────────────────────────────────────────────────
def register_signal(token, contract, chain, signals, entry_price=None, btc_context=""):
    """
    Registra una señal recien emitida. No crashea nunca.
    - chain: 'ETH'/'BNB'/'BASE'/'SOL' (se normaliza a red de GeckoTerminal).
    - entry_price: si viene del dex, se usa; si no, se intenta en vivo.
    Evita duplicar el mismo contract si ya hay una señal abierta reciente.
    """
    if not contract:
        return None
    network = CHAIN_MAP.get(str(chain).upper()) if chain else None
    contract_l = str(contract).lower()

    # Anti-duplicado: mismo contract ya abierto -> no re-registrar
    for s in _ledger["pending"]:
        if s["contract"].lower() == contract_l:
            return None

    price = None
    if entry_price is not None:
        try:
            price = float(entry_price)
            if price <= 0:
                price = None
        except (ValueError, TypeError):
            price = None
    if price is None and network:
        price = _live_price(network, contract)

    entry = {
        "token": token,
        "contract": contract,
        "chain": chain,
        "network": network,
        "signals": list(signals) if signals else [],
        "combo_key": "+".join(sorted(signals)) if signals else "",
        "btc_context": btc_context,
        "entry_price": price,
        "max_price": price,
        "min_price": price,
        "last_price": price,
        # "pending": aun sin precio de entrada; se completa en el proximo check.
        "status": "open" if price else "pending",
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    _ledger["pending"].append(entry)
    return entry


# ─── Job de 6h: actualizar y cerrar ──────────────────────────────────────────
def check_pending(now=None):
    """
    Actualiza max/min de las señales abiertas y cierra las que cumplen 72h.
    Devuelve dict con contadores. Nunca crashea; un fallo de API deja la señal
    abierta para el siguiente ciclo.
    """
    now = now or datetime.now(timezone.utc)
    still, closed_now = [], 0
    for s in _ledger["pending"]:
        network = s.get("network") or CHAIN_MAP.get(str(s.get("chain", "")).upper())

        # Completar precio de entrada si quedo pendiente
        p = _live_price(network, s["contract"]) if network else None
        if s.get("entry_price") is None and p:
            s["entry_price"] = s["max_price"] = s["min_price"] = p
            s["status"] = "open"
        if p:
            s["last_price"] = p
            if s.get("max_price") is None or p > s["max_price"]:
                s["max_price"] = p
            if s.get("min_price") is None or p < s["min_price"]:
                s["min_price"] = p

        # Edad
        try:
            ts0 = datetime.fromisoformat(s["ts"])
        except Exception:
            ts0 = now
        age = now - ts0

        if age >= timedelta(hours=WINDOW_H):
            entry = s.get("entry_price")
            if not entry:
                # Nunca conseguimos precio de entrada: no medible, cerrar como tal.
                s["outcome"] = "NO_DATA"
                s["closed_at"] = now.isoformat()
                _ledger["closed"].append(s)
                closed_now += 1
                continue
            max_gain = (s["max_price"] - entry) / entry
            min_loss = (s["min_price"] - entry) / entry
            if max_gain >= BIG_WIN:
                outcome = "BIG_WIN"
            elif max_gain >= WIN:
                outcome = "WIN"
            elif min_loss <= LOSS and max_gain < WIN:
                outcome = "LOSS"
            else:
                outcome = "NEUTRAL"
            s["outcome"] = outcome
            s["max_gain_pct"] = round(max_gain * 100, 1)
            s["min_loss_pct"] = round(min_loss * 100, 1)
            s["closed_at"] = now.isoformat()
            _ledger["closed"].append(s)
            closed_now += 1
        else:
            still.append(s)

    _ledger["pending"] = still
    # Podar histórico de cerradas
    if len(_ledger["closed"]) > 1000:
        _ledger["closed"] = _ledger["closed"][-1000:]
    return {"open": len(still), "closed_now": closed_now,
            "total_closed": len(_ledger["closed"])}


# ─── Consultas / stats ───────────────────────────────────────────────────────
def recent_closed(n=10):
    return list(reversed(_ledger["closed"][-n:]))


def rolling_stats(days=7):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    closed = []
    for s in _ledger["closed"]:
        if s.get("outcome") in (None, "NO_DATA"):
            continue
        try:
            if datetime.fromisoformat(s["ts"]) >= cutoff:
                closed.append(s)
        except Exception:
            continue
    wins = [s for s in closed if s["outcome"] in ("WIN", "BIG_WIN")]
    best = max(closed, key=lambda s: s.get("max_gain_pct", 0), default=None)
    return {
        "days": days,
        "total": len(closed),
        "wins": len(wins),
        "hit_rate": round(len(wins) / len(closed) * 100, 1) if closed else 0.0,
        "best": best,
    }


def get_weekly_recap():
    """
    Texto del recap semanal para OnChain Sentinel (X). Transparente: incluye
    wins y losses. Devuelve None si no hay señales cerradas esta semana.
    """
    st = rolling_stats(7)
    if not st["total"]:
        return None
    closed7 = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    for s in _ledger["closed"]:
        if s.get("outcome") in (None, "NO_DATA"):
            continue
        try:
            if datetime.fromisoformat(s["ts"]) >= cutoff:
                closed7.append(s)
        except Exception:
            continue

    winners = sorted(
        [s for s in closed7 if s["outcome"] in ("WIN", "BIG_WIN")],
        key=lambda s: s.get("max_gain_pct", 0), reverse=True,
    )[:3]
    losers = [s for s in closed7 if s["outcome"] == "LOSS"]

    lines = [
        "Recap semanal de señales on-chain",
        "",
        f"Señales cerradas: {st['total']}",
        f"Hit rate (+30% en 72h): {st['hit_rate']}%",
    ]
    if winners:
        lines.append("")
        lines.append("Mejores calls:")
        for s in winners:
            lines.append(f"  ${s['token']} +{s.get('max_gain_pct', 0)}%")
    if losers:
        lines.append("")
        lines.append(f"Fallos incluidos ({len(losers)}): "
                     + ", ".join(f"${s['token']} {s.get('min_loss_pct', 0)}%" for s in losers[:3]))
    lines += ["", "Todas publicadas antes del movimiento. Números completos, sin cherry-picking."]
    return "\n".join(lines)


def alert_post(token, signals, chain):
    """Texto de alerta en tiempo real para Sentinel cuando se emite una señal."""
    tags = {
        "insider_buy": "insider comprando", "insider_convergence": "CONVERGENCIA de insiders",
        "whale_convergence": "convergencia de ballenas", "holder_growth": "holders creciendo",
        "prelisting_confirmed": "pre-listing confirmado", "prelisting_unconfirmed": "posible pre-listing",
        "multi_exchange": "multi-exchange", "high_pump_prob": "prob. de pump alta",
        "vol_accel": "volumen acelerando",
    }
    desc = " + ".join(tags.get(s, s) for s in signals)
    return f"Señal on-chain [{str(chain).upper()}]: ${token}\n{desc}\n\nNFA. Outcome trackeado en 72h."


# ─── Persistencia (via estado del bot) ───────────────────────────────────────
def export_ledger():
    """Snapshot serializable para meter en serialize_state()."""
    return {"pending": _ledger["pending"][-300:], "closed": _ledger["closed"][-1000:]}


def load_ledger(data):
    """Restaura el ledger desde el estado cargado. Tolerante a formatos viejos."""
    if not isinstance(data, dict):
        return
    _ledger["pending"] = data.get("pending", []) or []
    _ledger["closed"] = data.get("closed", []) or []


if __name__ == "__main__":
    # Smoke test sin red pesada
    register_signal("PEPE", "0x6982508145454Ce325dDbE47a25d4ec3d2311933", "ETH",
                    ["insider_convergence", "holder_growth"], entry_price=0.000001,
                    btc_context="BTC +1.2% 24h")
    print("pending:", len(_ledger["pending"]))
    print(check_pending())
    print(rolling_stats(7))
    print(get_weekly_recap())
