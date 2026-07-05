"""
publisher.py - Publicacion en X (Twitter) con cola persistente y anti-spam.

Dos fuentes alimentan la cola:
  1. Event-driven: bot.py llama enqueue("whale"/"convergence"/"listing", ...)
     cuando detecta la señal (ademas del Ntfy). NO publica directo, encola.
  2. Programado: enqueue_daily_recap() 1x al dia con un resumen simple.

Un tick() (llamado desde el scheduler del bot) publica como maximo un tweet por
llamada, respetando los limites anti-spam.

Persistencia: la cola y el log NO usan archivos propios. Se exportan/cargan via
export_state()/load_state() y viajan dentro de /data/state.json (Railway Volume),
bajo las claves "tweet_queue" y "published_tweets".

Anti-spam / rate limit:
  - MAX_PER_DAY tweets al dia (default 8)
  - MAX_PER_MONTH ~500/mes (free tier de X)
  - MIN_INTERVAL_MIN minutos minimo entre publicaciones (default 20)
  - Dedup por hash del contenido (no republica lo mismo)

Reintentos: si la API falla, el tweet se queda en cola con contador; tras
MAX_RETRIES se descarta y se loguea. Nunca crashea el bot.

DRY_RUN (default true): loguea el tweet que publicaria pero no llama a la API.

Credenciales (env): X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET
"""

import os
import time
import hashlib
import threading
from datetime import datetime, timezone, timedelta

# tweepy es opcional: en DRY_RUN no hace falta. Guard para no romper el arranque.
try:
    import tweepy
except ImportError:
    tweepy = None


def _env_bool(name, default):
    return os.environ.get(name, str(default)).strip().lower() not in ("false", "0", "no", "")


DRY_RUN = _env_bool("DRY_RUN", True)
MAX_PER_DAY = int(os.environ.get("X_MAX_PER_DAY", "8"))
MAX_PER_MONTH = int(os.environ.get("X_MAX_PER_MONTH", "450"))  # margen bajo 500/mes
MIN_INTERVAL_MIN = int(os.environ.get("X_MIN_INTERVAL_MIN", "20"))
MAX_RETRIES = int(os.environ.get("X_MAX_RETRIES", "3"))
MAX_LEN = 280

X_API_KEY = os.environ.get("X_API_KEY", "").strip()
X_API_SECRET = os.environ.get("X_API_SECRET", "").strip()
X_ACCESS_TOKEN = os.environ.get("X_ACCESS_TOKEN", "").strip()
X_ACCESS_SECRET = os.environ.get("X_ACCESS_SECRET", "").strip()

# Estado en memoria (se persiste dentro de state.json del bot)
_queue = []       # [{id, kind, text, hash, created_ts, retries}]
_published = []   # [{id, hash, kind, ts, text}]
_lock = threading.Lock()

_log = print  # bot.py inyecta su logger via set_logger()


def set_logger(fn):
    global _log
    _log = fn


# ─── Formateo de tweets ──────────────────────────────────────────────────────
def _fmt_usd(n):
    try:
        n = float(n or 0)
    except (ValueError, TypeError):
        return ""
    if n >= 1e6:
        return f"${n/1e6:.1f}M"
    if n >= 1e3:
        return f"${n/1e3:.0f}K"
    return f"${n:.0f}" if n else ""


def _clean_ticker(sym):
    """Solo el ticker en mayuscula, sin '$' duplicado ni basura."""
    s = str(sym or "").strip().lstrip("$").upper()
    return s or "?"


def _btc_str(btc):
    """Contexto BTC compacto. Acepta ya-formateado o vacio."""
    return f" · {btc}".rstrip() if btc else ""


def _format(kind, data):
    """Construye el texto del tweet segun el tipo. Nunca incluye contract ni
    links de compra: solo ticker y datos. Devuelve None si falta lo esencial."""
    chain = str(data.get("chain", "")).upper()
    chain_tag = f" [{chain}]" if chain else ""
    btc = _btc_str(data.get("btc", ""))

    if kind == "whale":
        tok = _clean_ticker(data.get("token"))
        amt = _fmt_usd(data.get("amount_usd"))
        amt_str = f" (~{amt})" if amt else ""
        text = f"🐋 Ballena comprando ${tok}{chain_tag}{amt_str}{btc}"

    elif kind == "convergence":
        tok = _clean_ticker(data.get("token"))
        n = int(data.get("n_insiders", 2) or 2)
        text = f"🎯 {n} smart wallets compraron ${tok}{chain_tag} casi a la vez. Convergencia de dinero inteligente.{btc}"

    elif kind == "listing":
        tok = _clean_ticker(data.get("token"))
        exch = str(data.get("exchange", "")).strip().upper()
        exch_str = f" en {exch}" if exch else ""
        text = f"📢 Nuevo listing: ${tok}{exch_str}."

    elif kind == "recap":
        # data trae texto ya armado por make_daily_recap()
        text = data.get("text", "")

    else:
        return None

    # Normalizar espacios dentro de cada linea, preservando saltos de linea.
    text = "\n".join(" ".join(line.split()) for line in text.splitlines())
    if len(text) > MAX_LEN:
        text = text[:MAX_LEN - 1].rstrip() + "…"
    return text or None


def make_daily_recap(signals_today=0, highlights=None, btc=""):
    """Arma el texto del recap diario a partir de datos ya existentes.
    highlights: lista de tickers destacados del dia (sin '$')."""
    highlights = [_clean_ticker(h) for h in (highlights or [])][:4]
    lines = ["📊 Resumen on-chain del dia"]
    lines.append(f"Señales detectadas: {signals_today}")
    if highlights:
        lines.append("En el radar: " + ", ".join(f"${h}" for h in highlights))
    if btc:
        lines.append(btc)
    lines.append("No es consejo financiero.")
    text = "\n".join(lines)
    if len(text) > MAX_LEN:
        text = text[:MAX_LEN - 1].rstrip() + "…"
    return text


# ─── Cola ────────────────────────────────────────────────────────────────────
def _hash(text):
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def _already_seen(h):
    """True si ese contenido ya esta en cola o ya se publico (dedup)."""
    if any(q["hash"] == h for q in _queue):
        return True
    # revisar publicados recientes (ultimos 30 dias)
    cutoff = time.time() - 30 * 86400
    return any(p["hash"] == h and p.get("ts", 0) >= cutoff for p in _published)


def enqueue(kind, **data):
    """Encola un tweet (event-driven). No publica. Nunca crashea.
    Devuelve el dict encolado o None si se descarto (dedup/formato)."""
    try:
        text = _format(kind, data)
        if not text:
            return None
        h = _hash(text)
        with _lock:
            if _already_seen(h):
                return None
            item = {
                "id": f"{int(time.time()*1000)}-{h[:6]}",
                "kind": kind, "text": text, "hash": h,
                "created_ts": int(time.time()), "retries": 0,
            }
            _queue.append(item)
        _log(f"[publisher] encolado ({kind}): {text[:70]}")
        return item
    except Exception as e:
        _log(f"[publisher enqueue error] {e}")
        return None


def enqueue_daily_recap(signals_today=0, highlights=None, btc=""):
    """Encola el recap diario programado."""
    text = make_daily_recap(signals_today, highlights, btc)
    return enqueue("recap", text=text)


# ─── Publicacion ─────────────────────────────────────────────────────────────
def _count_since(seconds):
    cutoff = time.time() - seconds
    return sum(1 for p in _published if p.get("ts", 0) >= cutoff)


def _last_publish_ts():
    return max((p.get("ts", 0) for p in _published), default=0)


def _do_publish(text):
    """Publica en X. Devuelve (ok, tweet_id_o_motivo). Respeta DRY_RUN."""
    if DRY_RUN:
        _log(f"[publisher][DRY_RUN] publicaria: {text!r}")
        return True, f"dryrun-{int(time.time())}"
    if tweepy is None:
        _log("[publisher] tweepy no instalado; no se puede publicar (revisa requirements)")
        return False, "no_tweepy"
    if not (X_API_KEY and X_API_SECRET and X_ACCESS_TOKEN and X_ACCESS_SECRET):
        _log("[publisher] faltan credenciales X_*; no se publica")
        return False, "no_creds"
    try:
        client = tweepy.Client(
            consumer_key=X_API_KEY, consumer_secret=X_API_SECRET,
            access_token=X_ACCESS_TOKEN, access_token_secret=X_ACCESS_SECRET,
        )
        resp = client.create_tweet(text=text)
        tid = str(resp.data.get("id")) if getattr(resp, "data", None) else "ok"
        _log(f"[publisher] PUBLICADO id={tid}: {text[:60]}")
        return True, tid
    except Exception as e:
        _log(f"[publisher] error API: {e}")
        return False, str(e)[:100]


def tick():
    """Publica como maximo un tweet, si toca. Llamar desde el scheduler del bot.
    Aplica limites: intervalo minimo, tope diario y mensual. Nunca bloquea de
    forma indefinida ni crashea."""
    if not _lock.acquire(blocking=False):
        return  # ya hay un tick corriendo
    try:
        if not _queue:
            return
        now = time.time()
        if now - _last_publish_ts() < MIN_INTERVAL_MIN * 60:
            return
        if _count_since(86400) >= MAX_PER_DAY:
            return
        if _count_since(30 * 86400) >= MAX_PER_MONTH:
            _log("[publisher] tope mensual alcanzado; en pausa")
            return

        item = _queue[0]
        ok, info = _do_publish(item["text"])
        if ok:
            _queue.pop(0)
            _published.append({
                "id": info, "hash": item["hash"], "kind": item["kind"],
                "ts": int(now), "text": item["text"],
            })
            if len(_published) > 500:
                del _published[:len(_published) - 500]
        else:
            item["retries"] += 1
            if item["retries"] > MAX_RETRIES:
                _queue.pop(0)
                _log(f"[publisher] descartado tras {MAX_RETRIES} reintentos: {item['text'][:60]}")
    except Exception as e:
        _log(f"[publisher tick error] {e}")
    finally:
        _lock.release()


# ─── Persistencia (via state.json del bot) ───────────────────────────────────
def export_state():
    """Snapshot para meter en serialize_state() del bot."""
    return {
        "tweet_queue": _queue[-200:],
        "published_tweets": _published[-500:],
    }


def load_state(tweet_queue=None, published_tweets=None):
    """Restaura cola y log desde el estado cargado del Volume."""
    global _queue, _published
    if isinstance(tweet_queue, list):
        _queue = tweet_queue
    if isinstance(published_tweets, list):
        _published = published_tweets


def stats():
    """Para debug / endpoint opcional."""
    return {
        "dry_run": DRY_RUN,
        "queue": len(_queue),
        "published_total": len(_published),
        "published_today": _count_since(86400),
        "published_30d": _count_since(30 * 86400),
        "last_publish_ts": _last_publish_ts(),
    }


if __name__ == "__main__":
    # Smoke test en DRY_RUN
    enqueue("whale", token="ENA", chain="ETH", amount_usd=25000, btc="BTC +1.2% 🟢")
    enqueue("convergence", token="PEPE", chain="ETH", n_insiders=3, btc="BTC -0.8% 🔴")
    enqueue("listing", token="TOSHI", exchange="MEXC")
    enqueue_daily_recap(signals_today=12, highlights=["ENA", "PEPE"], btc="BTC +1.2% 🟢")
    print("cola:", len(_queue))
    for q in _queue:
        print(f"  [{q['kind']}] ({len(q['text'])} chars) {q['text']!r}")
    tick()  # publica 1 (dry run)
    print("stats:", stats())
