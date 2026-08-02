"""
Fuente TMDB (REST, requiere API key gratuita).

Complementa a AniList en lo que AniList no cubre: cine no-anime, y sobre
todo mercados como CN y KR.

El punto critico es la fecha POR REGION. En el caso Chiikawa la fecha que
importaba era la japonesa (24 de julio), no la internacional, que llega
meses despues. Un calendario que solo mire fechas US llega tarde siempre.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta

from normalize import Event, build_search_terms, fuzzy_date

BASE = "https://api.themoviedb.org/3"
API_KEY = os.getenv("TMDB_API_KEY")

# Mercados donde el evento es grande y la cobertura cripto es baja.
# US queda fuera a proposito: ahi no hay asimetria de atencion.
REGIONS = ("JP", "CN", "KR", "TW", "HK")


def _get(path: str, params: dict, retries: int = 3) -> dict:
    if not API_KEY:
        raise RuntimeError("falta TMDB_API_KEY")
    params = {**params, "api_key": API_KEY}
    url = f"{BASE}{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "catalyst-radar/1.0 (listing-sniper)",
    })
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries - 1:
                time.sleep(int(e.headers.get("Retry-After", 5)))
                continue
            raise
    raise RuntimeError("tmdb: reintentos agotados")


def fetch(days_back: int = 7, horizon_days: int = 180,
          min_popularity: float = 8.0, max_pages: int = 5):
    today = date.today()
    gte = (today - timedelta(days=days_back)).isoformat()
    lte = (today + timedelta(days=horizon_days)).isoformat()

    for region in REGIONS:
        page = 1
        while page <= max_pages:
            data = _get("/discover/movie", {
                "region": region,
                "with_release_type": 3,          # estreno en salas
                "primary_release_date.gte": gte,
                "primary_release_date.lte": lte,
                "sort_by": "popularity.desc",
                "page": page,
            })

            for m in data.get("results", []):
                pop = m.get("popularity") or 0
                if pop < min_popularity:
                    continue

                rd = m.get("release_date")
                if rd:
                    y, mo, d = (int(x) for x in rd.split("-"))
                    iso, precision = fuzzy_date(y, mo, d)
                else:
                    iso, precision = None, "rumor"

                titles = [m.get("title"), m.get("original_title")]
                aliases = [x for x in titles if x]

                yield Event(
                    source="tmdb",
                    external_id=f"{m['id']}:{region}",
                    ip_name=m.get("title") or m.get("original_title") or "?",
                    aliases=aliases,
                    search_terms=build_search_terms(titles),
                    event_type="film_release",
                    event_date=iso,
                    date_precision=precision,
                    region=region,
                    # popularity de TMDB es un float chico; lo escalamos para que
                    # sea comparable con el de AniList dentro del mismo ranking.
                    audience_proxy=int(pop * 100),
                    source_url=f"https://www.themoviedb.org/movie/{m['id']}",
                    raw=m,
                )

            if page >= data.get("total_pages", 1):
                break
            page += 1
            time.sleep(0.3)
