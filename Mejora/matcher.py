"""
Catalyst Radar :: Batch 2 — Matcher (eventos -> tokens).

Toma las filas de store.upcoming() (eventos con fecha exacta en ventana) y por
cada una busca el ticker en DexScreener. La tesis no es "hay un catalizador",
es ASIMETRIA DE ATENCION: un evento enorme para cientos de miles de personas,
invisible para cripto twitter, con un ticker ya existente y dormido.

Señales que SI salen de los datos:
  - Fecha publica y fija      -> el evento ya viene con date_precision=exact
  - Audiencia masiva          -> audience_proxy del evento
  - Ventana 2-8 semanas       -> days_until
  - Ticker existente y dormido-> el token tiene liquidez pero volumen casi nulo
  - Conflicto / atencion fragmentada -> 2do token DISTINTO con >40% de la
    liquidez del 1ro (el caso GTA6: decenas de CAs compitiendo)

Señales que NO se automatizan bien (quedan como flags para revision manual):
  - Cobertura baja en CT (se aproxima por ausencia de redes en el par)
  - Afinidad cultural con el cripto-nativo

Sin dependencias externas (stdlib). Uso:
    python matcher.py                 # reporte de oportunidades actuales
    python matcher.py --validate      # corre los casos Chiikawa / GTA6 por el scorer
    python matcher.py --window 14 56  # ventana en dias (default 14-56 = 2-8 semanas)
"""
from __future__ import annotations

import argparse
import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request

from store import connect, upcoming

import os

SEARCH_URL = "https://api.dexscreener.com/latest/dex/search"
USER_AGENT = "catalyst-radar/1.0 (listing-sniper)"

# Redes donde buscar el ticker (chainId de DexScreener). Por defecto: Solana,
# Ethereum, Base, BSC y Robinhood Chain. Ampliable/reducible con CATALYST_CHAINS.
ALLOWED_CHAINS = {
    c.strip().lower()
    for c in os.environ.get("CATALYST_CHAINS", "solana,ethereum,base,bsc,robinhood").split(",")
    if c.strip()
}

# Ventana de timing "2 a 8 semanas" en dias.
WINDOW_LO, WINDOW_HI = 14, 56
CONFLICT_RATIO = 0.40        # 2do token con >40% de liq del 1ro = atencion fragmentada
MIN_TRADEABLE_LIQ = 10_000   # por debajo no es un "ticker en la repisa", es intradeable
DORMANT_MIN_LIQ = 20_000     # hay que poder entrar/salir
DORMANT_MAX_TURNOVER = 0.05  # vol24/liq bajo = nadie lo esta operando aun
DORMANT_MIN_AGE_DAYS = 30    # ticker viejo, no recien lanzado


def _dex_search(term: str, retries: int = 3) -> list[dict]:
    url = f"{SEARCH_URL}?q={urllib.parse.quote(term)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return (json.loads(r.read()) or {}).get("pairs") or []
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries - 1:
                time.sleep(int(e.headers.get("Retry-After", 3)))
                continue
            return []
        except Exception:
            return []
    return []


def _token_key(pair: dict) -> tuple:
    bt = pair.get("baseToken") or {}
    return (pair.get("chainId"), (bt.get("address") or "").lower())


def _collect_tokens(terms: list[str], max_terms: int = 4) -> list[dict]:
    """Busca por varios terminos y agrega por token distinto (dedup por address,
    quedandose con el par de mayor liquidez de cada token)."""
    best: dict[tuple, dict] = {}
    for term in terms[:max_terms]:
        if not term or len(term) < 3:
            continue
        for p in _dex_search(term):
            # Solo redes permitidas (por defecto Solana + Ethereum)
            if (p.get("chainId") or "").lower() not in ALLOWED_CHAINS:
                continue
            liq = (p.get("liquidity") or {}).get("usd", 0) or 0
            key = _token_key(p)
            if not key[1]:
                continue
            cur = best.get(key)
            if cur is None or liq > cur["liq"]:
                bt = p.get("baseToken") or {}
                info = p.get("info") or {}
                created = p.get("pairCreatedAt")
                age_days = (time.time() - created / 1000) / 86400 if created else None
                try:
                    price = float(p.get("priceUsd") or 0)
                except (TypeError, ValueError):
                    price = 0.0
                best[key] = {
                    "symbol": bt.get("symbol", "?"),
                    "name": bt.get("name", ""),
                    "address": bt.get("address", ""),
                    "chain": p.get("chainId", "?"),
                    "liq": liq,
                    "vol24": (p.get("volume") or {}).get("h24", 0) or 0,
                    "price": price,
                    "age_days": age_days,
                    "socials": len(info.get("socials") or []) + len(info.get("websites") or []),
                    "url": p.get("url", ""),
                }
        time.sleep(0.25)  # cortesia con el rate limit
    return sorted(best.values(), key=lambda t: t["liq"], reverse=True)


# Palabras genericas que NO distinguen un IP: si el ticker es una de estas, es
# ruido (p. ej. $SEAS por "season", $The por "the"). Evita falsos positivos.
_GENERIC = {
    "the", "season", "movie", "film", "part", "story", "chapter", "final",
    "arc", "saga", "special", "anime", "series", "and", "new", "next", "of",
    "for", "with", "kun", "san", "chan", "tv", "ova", "ona",
}


def _distinctive_term(t: str) -> str | None:
    """La palabra 'de peso' de un titulo: la primera con >=4 chars y no generica.
    Es la que tiende a volverse el ticker (CHIIKAWA)."""
    for w in t.split():
        if len(w) >= 4 and w not in _GENERIC:
            return w
    return None


def _match_quality(term_list: list[str], token: dict) -> float:
    """0..1 de que tan bien el token corresponde al evento. Estricto a proposito:
    solo cuenta cuando el TICKER coincide con el termino distintivo del IP, no
    cuando es un substring generico del titulo."""
    sym = (token["symbol"] or "").lower().strip()
    name = (token["name"] or "").lower().strip()
    if not sym or len(sym) < 3 or sym in _GENERIC:
        return 0.0
    best = 0.0
    for t in term_list:
        t = (t or "").lower().strip()
        if not t:
            continue
        short = _distinctive_term(t)
        if sym == t:
            best = max(best, 1.0)                    # ticker == titulo completo (corto)
        elif short and sym == short:
            best = max(best, 0.95)                   # ticker == palabra distintiva
        elif short and len(short) >= 5 and (sym.startswith(short) or short.startswith(sym)) \
                and abs(len(sym) - len(short)) <= 2:
            best = max(best, 0.8)                     # casi (CHIIKAWA vs CHIIKAW)
        elif len(t) >= 6 and t in name:
            best = max(best, 0.7)                     # el titulo aparece en el nombre del token
    return best


def match_event(event: dict) -> dict | None:
    """Busca el mejor token para un evento y evalua conflicto. None si no hay
    match razonable."""
    try:
        terms = json.loads(event["search_terms"]) if event.get("search_terms") else []
    except Exception:
        terms = []
    if not terms:
        return None

    tokens = _collect_tokens(terms)
    if not tokens:
        return None

    # Elegir el mejor token con match de nombre/ticker aceptable
    scored = [(t, _match_quality(terms, t)) for t in tokens]
    # Match fuerte Y token realmente tradeable (descarta liq ~0 = ticker fantasma)
    scored = [(t, q) for t, q in scored if q >= 0.7 and t["liq"] >= MIN_TRADEABLE_LIQ]
    if not scored:
        return None
    scored.sort(key=lambda x: (x[1], x[0]["liq"]), reverse=True)
    best_token, best_q = scored[0]

    # Conflicto: 2do token DISTINTO (no el mismo address) con liq alta relativa
    conflict = False
    runner_up = None
    for t, q in scored[1:]:
        if t["address"].lower() == best_token["address"].lower():
            continue
        runner_up = t
        if best_token["liq"] > 0 and t["liq"] >= CONFLICT_RATIO * best_token["liq"]:
            conflict = True
        break

    # Proxy de atencion: cuanta actividad total tiene la narrativa (todos los
    # tokens que matchean el termino). Poco volumen agregado = aun invisible.
    narrative_volume = sum(t.get("vol24", 0) or 0 for t in tokens)

    return {"token": best_token, "match_quality": best_q,
            "conflict": conflict, "runner_up": runner_up,
            "n_candidates": len(tokens), "narrative_volume": narrative_volume}


def score_opportunity(event: dict, match: dict) -> dict:
    """Score 0-100 de asimetria de atencion. Devuelve total + desglose + flags."""
    token = match["token"]
    days = event.get("days_until")
    aud = event.get("audience_proxy", 0) or 0
    breakdown = {}

    # Audiencia masiva (log-escalada)
    breakdown["audiencia"] = round(min(35, 9 * math.log10(max(aud, 1))))

    # Ventana 2-8 semanas
    if days is None:
        w = 0
    elif WINDOW_LO <= days <= WINDOW_HI:
        w = 20
    elif days < WINDOW_LO:
        w = max(0, 20 - (WINDOW_LO - days) * 3)   # muy cerca = tarde
    else:
        w = max(0, 20 - (days - WINDOW_HI) * 0.5)  # muy lejos = pronto
    breakdown["ventana"] = round(w)

    # Calidad de match (el ticker corresponde al IP)
    breakdown["match"] = round(match["match_quality"] * 20)

    # Ticker existente y DORMIDO: liquidez suficiente, volumen casi nulo, viejo
    liq, vol, age = token["liq"], token["vol24"], token.get("age_days")
    turnover = (vol / liq) if liq else 999
    dorm = 0
    if liq >= DORMANT_MIN_LIQ:
        dorm += 8
        if turnover < DORMANT_MAX_TURNOVER:
            dorm += 8   # nadie lo opera aun = no descubierto
        if age is not None and age >= DORMANT_MIN_AGE_DAYS:
            dorm += 4   # viejo, no recien lanzado
    breakdown["dormido"] = dorm

    # ── Proxy de ATENCION BAJA (la asimetria = el edge). Data-driven, sin costo:
    #    narrativa poco poblada (pocos tickers compitiendo) + volumen agregado
    #    bajo (nadie la esta operando) + par sin redes = sigue invisible.
    n_distinct = match.get("n_candidates", 1)
    narrative_vol = match.get("narrative_volume", 0)
    att = 0
    if n_distinct <= 2:       att += 8    # narrativa nicho, no contestada
    elif n_distinct <= 5:     att += 4
    if narrative_vol < 50_000:    att += 5   # aun no descubierta
    elif narrative_vol < 250_000: att += 2
    if token["socials"] == 0: att += 2       # ni redes tiene el par
    breakdown["atencion_baja"] = att

    # Penalizacion por conflicto / atencion fragmentada
    breakdown["conflicto"] = -25 if match["conflict"] else 0

    total = max(0, min(100, sum(breakdown.values())))

    flags = []
    if match["conflict"]:
        flags.append("CONFLICTO: atencion fragmentada entre varios tickers")
    if n_distinct > 5:
        flags.append(f"narrativa poblada ({n_distinct} tickers): posible sobre-cobertura")
    if narrative_vol >= 250_000:
        flags.append(f"volumen de narrativa alto ({narrative_vol:,.0f}): puede estar descubierta")
    if token["socials"] > 0:
        flags.append("revisar cobertura CT (el par tiene redes)")
    flags.append("verificar afinidad cultural a mano")
    if turnover >= DORMANT_MAX_TURNOVER and liq >= DORMANT_MIN_LIQ:
        flags.append("el token ya tiene volumen propio: puede estar siendo descubierto")

    return {"score": total, "breakdown": breakdown, "flags": flags}


def find_opportunities(conn, lo: int = WINDOW_LO, hi: int = WINDOW_HI,
                       min_audience: int = 5000) -> list[dict]:
    """Recorre eventos en ventana con fecha exacta y devuelve oportunidades
    rankeadas por score."""
    events = upcoming(conn, lo=lo, hi=hi, only_exact=True, min_audience=min_audience)
    out = []
    for e in events:
        ev = dict(e)
        m = match_event(ev)
        if not m:
            continue
        s = score_opportunity(ev, m)
        out.append({"event": ev, "match": m, **s})
    out.sort(key=lambda x: x["score"], reverse=True)
    return out


# ─── Validacion del scorer (no es backtest historico) ────────────────────────
def validate() -> None:
    """
    Corre los dos casos guia por el scorer para sanidad de calibracion.
    NO es un backtest historico real: DexScreener solo da liquidez ACTUAL, y en
    abril (cuando estaba el edge) Chiikawa estaba dormido; hoy ya exploto. Por
    eso este check evalua la LOGICA del scorer con perfiles conocidos, no snap-
    shots del pasado. El backtest historico fiel requeriria guardar snapshots
    de liquidez a lo largo del tiempo (Batch futuro).
    """
    print("== Validacion de logica del scorer (perfiles conocidos) ==\n")

    # Chiikawa como estaba el edge: evento masivo, ventana ~5 semanas, ticker
    # dormido (liq moderada, volumen casi nulo, viejo), sin conflicto real.
    chiikawa_event = {"ip_name": "Chiikawa Movie", "audience_proxy": 52000,
                      "days_until": 35, "search_terms": json.dumps(["chiikawa"])}
    chiikawa_match = {"token": {"symbol": "CHIIKAWA", "name": "Chiikawa", "address": "0xaaa",
                                "chain": "solana", "liq": 60000, "vol24": 800,
                                "age_days": 100, "socials": 0},
                      "match_quality": 1.0, "conflict": False, "runner_up": None,
                      "n_candidates": 2, "narrative_volume": 1500}
    s = score_opportunity(chiikawa_event, chiikawa_match)
    print(f"CHIIKAWA -> score {s['score']}")
    print(f"  desglose: {s['breakdown']}")
    print(f"  flags: {s['flags']}\n")

    # GTA6: fecha que sabe todo el planeta, decenas de CAs compitiendo -> conflicto.
    gta_event = {"ip_name": "GTA VI", "audience_proxy": 60000, "days_until": 120,
                 "search_terms": json.dumps(["gta"])}
    gta_match = {"token": {"symbol": "GTA", "name": "Grand Theft Auto", "address": "0xbbb",
                           "chain": "solana", "liq": 15000000, "vol24": 5000000,
                           "age_days": 200, "socials": 3},
                 "match_quality": 1.0, "conflict": True,
                 "runner_up": {"symbol": "GTAVI", "liq": 8000000}, "n_candidates": 12,
                 "narrative_volume": 9000000}
    s2 = score_opportunity(gta_event, gta_match)
    print(f"GTA VI -> score {s2['score']}")
    print(f"  desglose: {s2['breakdown']}")
    print(f"  flags: {s2['flags']}\n")

    ok = s["score"] > s2["score"]
    print(f"Chiikawa ({s['score']}) {'>' if ok else '<='} GTA6 ({s2['score']}): "
          f"{'OK, el scorer premia la asimetria' if ok else 'REVISAR calibracion'}")


def report(conn, lo: int, hi: int, min_audience: int) -> None:
    ops = find_opportunities(conn, lo=lo, hi=hi, min_audience=min_audience)
    print(f"\n== Oportunidades ({len(ops)}) — ventana {lo}-{hi}d, fecha exacta ==")
    if not ops:
        print("  (sin matches; la tabla de eventos puede estar vacia: corre ingest.py primero)")
        return
    for o in ops[:20]:
        e, t = o["event"], o["match"]["token"]
        conf = " [CONFLICTO]" if o["match"]["conflict"] else ""
        print(f"\n  {o['score']:>3}  {e['ip_name'][:40]:40} en {e['days_until']}d")
        print(f"       ${t['symbol']} ({t['chain']}) liq=${t['liq']:,.0f} vol24=${t['vol24']:,.0f}{conf}")
        print(f"       {o['breakdown']}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--window", nargs=2, type=int, metavar=("LO", "HI"))
    ap.add_argument("--min-audience", type=int, default=5000)
    args = ap.parse_args()

    if args.validate:
        validate()
        return

    lo, hi = args.window if args.window else (WINDOW_LO, WINDOW_HI)
    conn = connect()
    report(conn, lo, hi, args.min_audience)
    conn.close()


if __name__ == "__main__":
    main()
