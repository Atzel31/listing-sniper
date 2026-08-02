"""
catalyst_radar.py - Puente entre bot.py y el Catalyst Radar (carpeta Mejora/).

Corre la ingesta de eventos (AniList/TMDB) + el matcher contra DexScreener una
vez al dia, guarda las oportunidades rankeadas en memoria y las expone para el
API/dashboard. La persistencia de la tabla de eventos es la SQLite del Volume
(/data/catalyst.db); las oportunidades y el set de ya-alertadas viajan dentro
de state.json como el resto del estado.

Nunca crashea el bot: todo run_daily va envuelto y cualquier fallo de API deja
el estado anterior intacto.
"""
from __future__ import annotations

import os
import sys
import time

# La logica del radar vive en Mejora/ (modulos stdlib, sin dependencias).
_MEJORA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Mejora")
if _MEJORA not in sys.path:
    sys.path.insert(0, _MEJORA)

# La DB del radar va en el mismo Volume que state.json.
os.environ.setdefault("CATALYST_DB", os.path.join(os.environ.get("DATA_DIR", "/data"), "catalyst.db"))

try:
    import store as _store          # noqa: E402  (Mejora/store.py)
    import matcher as _matcher      # noqa: E402
    import anilist as _anilist      # noqa: E402
    _AVAILABLE = True
except Exception as _e:  # si la carpeta no existe o falla el import, degradar
    _store = _matcher = _anilist = None
    _AVAILABLE = False
    _IMPORT_ERR = str(_e)

try:
    import tmdb as _tmdb            # noqa: E402
except Exception:
    _tmdb = None

MIN_ALERT_SCORE = int(os.environ.get("CATALYST_MIN_ALERT_SCORE", "70"))
WINDOW_LO = int(os.environ.get("CATALYST_WINDOW_LO", "14"))
WINDOW_HI = int(os.environ.get("CATALYST_WINDOW_HI", "56"))
MIN_AUDIENCE = int(os.environ.get("CATALYST_MIN_AUDIENCE", "8000"))

_state = {
    "opportunities": [],   # lista serializable, top N
    "last_run": 0,
    "last_error": None,
    "events": 0,
    "alerted": [],         # keys ya notificadas por Ntfy (dedup)
    "snapshots": 0,        # fotos acumuladas para backtest
    "backtest": {},        # resumen de calibracion (se llena con el tiempo)
}

_log = print


def set_logger(fn):
    global _log
    _log = fn


def available() -> bool:
    return _AVAILABLE


def _sources():
    s = {"anilist": _anilist.fetch}
    if os.environ.get("TMDB_API_KEY") and _tmdb:
        s["tmdb"] = _tmdb.fetch
    return s


def _serialize_op(o: dict) -> dict:
    """Aplana una oportunidad del matcher a un dict JSON-safe para API/estado."""
    e = o["event"]
    t = o["match"]["token"]
    return {
        "score": o["score"],
        "ip_name": e.get("ip_name"),
        "event_date": e.get("event_date"),
        "days_until": e.get("days_until"),
        "region": e.get("region"),
        "audience": e.get("audience_proxy"),
        "event_type": e.get("event_type"),
        "source_url": e.get("source_url"),
        "token_symbol": t.get("symbol"),
        "token_chain": t.get("chain"),
        "token_liq": round(t.get("liq", 0)),
        "token_vol24": round(t.get("vol24", 0)),
        "token_url": t.get("url"),
        "conflict": o["match"]["conflict"],
        "match_quality": round(o["match"]["match_quality"], 2),
        "breakdown": o["breakdown"],
        "flags": o["flags"],
    }


def _op_key(op: dict) -> str:
    return f"{op.get('ip_name')}|{op.get('token_symbol')}|{op.get('event_date')}"


def run_daily(window=None, min_audience=None) -> list[dict]:
    """Ingesta + match. Actualiza el estado en memoria. Devuelve las
    oportunidades. Cualquier fallo deja el estado previo y no crashea."""
    if not _AVAILABLE:
        _state["last_error"] = f"radar no disponible: {_IMPORT_ERR}"
        return _state["opportunities"]
    lo = (window or (WINDOW_LO, WINDOW_HI))[0]
    hi = (window or (WINDOW_LO, WINDOW_HI))[1]
    min_aud = min_audience if min_audience is not None else MIN_AUDIENCE
    try:
        conn = _store.connect()
        total_seen = 0
        for name, fetch in _sources().items():
            rid = _store.start_run(conn, name)
            seen = new = changed = 0
            try:
                for ev in fetch():
                    seen += 1
                    isnew, ch = _store.upsert_event(conn, ev)
                    new += int(isnew)
                    changed += int(bool(ch))
                _store.finish_run(conn, rid, seen, new, changed)
                conn.commit()
            except Exception as e:
                conn.rollback()
                _store.finish_run(conn, rid, seen, new, changed, error=str(e)[:500])
                conn.commit()
                _log(f"[catalyst] fuente {name} fallo: {e}")
            total_seen += seen

        ops = _matcher.find_opportunities(conn, lo=lo, hi=hi, min_audience=min_aud)
        _state["opportunities"] = [_serialize_op(o) for o in ops[:30]]

        # Backtest: guardar una foto de CADA candidato (no solo el top) para
        # construir la serie temporal hacia adelante.
        for o in ops:
            ev, t = o["event"], o["match"]["token"]
            _store.record_snapshot(conn, {
                "event_id": ev.get("id"), "ip_name": ev.get("ip_name"),
                "event_date": ev.get("event_date"), "days_until": ev.get("days_until"),
                "score": o["score"], "conflict": o["match"]["conflict"],
                "token_symbol": t.get("symbol"), "token_address": t.get("address"),
                "token_chain": t.get("chain"), "liq": t.get("liq"),
                "vol24": t.get("vol24"), "price": t.get("price"),
            })
        conn.commit()

        try:
            _state["events"] = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            _state["snapshots"] = _store.snapshot_count(conn)
            _state["backtest"] = _store.backtest_summary(conn)
        except Exception as e:
            _log(f"[catalyst] backtest resumen fallo: {e}")
        _state["last_run"] = int(time.time())
        _state["last_error"] = None
        conn.close()
        _log(f"[catalyst] {total_seen} eventos vistos, {len(ops)} oportunidades "
             f"({sum(1 for o in _state['opportunities'] if not o['conflict'])} sin conflicto)")
    except Exception as e:
        _state["last_error"] = str(e)[:300]
        _log(f"[catalyst] error: {e}")
    return _state["opportunities"]


def pop_new_alerts(min_score: int = None) -> list[dict]:
    """Oportunidades nuevas dignas de alerta: score alto, sin conflicto y aun no
    notificadas. Las marca como alertadas (dedup persistente)."""
    thr = MIN_ALERT_SCORE if min_score is None else min_score
    alerted = set(_state.get("alerted", []))
    fresh = []
    for op in _state["opportunities"]:
        if op["score"] >= thr and not op["conflict"]:
            k = _op_key(op)
            if k not in alerted:
                fresh.append(op)
                alerted.add(k)
    _state["alerted"] = list(alerted)[-500:]
    return fresh


# ─── API / estado ────────────────────────────────────────────────────────────
def get_state() -> dict:
    return {
        "opportunities": _state["opportunities"],
        "last_run": _state["last_run"],
        "last_error": _state["last_error"],
        "events": _state["events"],
        "snapshots": _state["snapshots"],
        "backtest": _state["backtest"],
        "available": _AVAILABLE,
        "window": [WINDOW_LO, WINDOW_HI],
    }


def export_state() -> dict:
    return {
        "catalyst_opportunities": _state["opportunities"],
        "catalyst_last_run": _state["last_run"],
        "catalyst_events": _state["events"],
        "catalyst_alerted": _state.get("alerted", [])[-500:],
        "catalyst_snapshots": _state["snapshots"],
        "catalyst_backtest": _state["backtest"],
    }


def load_state(state: dict) -> None:
    if not isinstance(state, dict):
        return
    _state["opportunities"] = state.get("catalyst_opportunities", []) or []
    _state["last_run"] = state.get("catalyst_last_run", 0) or 0
    _state["events"] = state.get("catalyst_events", 0) or 0
    _state["alerted"] = state.get("catalyst_alerted", []) or []
    _state["snapshots"] = state.get("catalyst_snapshots", 0) or 0
    _state["backtest"] = state.get("catalyst_backtest", {}) or {}


if __name__ == "__main__":
    set_logger(print)
    print("radar disponible:", available())
    run_daily()
    st = get_state()
    print(f"eventos={st['events']} last_run={st['last_run']} err={st['last_error']}")
    for o in st["opportunities"][:10]:
        c = " [CONFLICTO]" if o["conflict"] else ""
        print(f"  {o['score']:>3} {o['ip_name'][:34]:34} {o['days_until']}d -> ${o['token_symbol']} liq=${o['token_liq']:,}{c}")
