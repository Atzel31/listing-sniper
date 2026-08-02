"""
Fuente AniList (GraphQL, sin auth, ~90 req/min).

Es la mejor fuente del vertical anime por tres razones:
  1. startDate viene desglosado en year/month/day con nulls, que mapea
     directo a date_precision sin heuristicas.
  2. popularity y favourites son tu audience_proxy gratis.
  3. synonyms trae los alias en kana y romaji, que es justo lo que el
     matcher necesita para encontrar el ticker.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from datetime import date, timedelta

from normalize import Event, build_search_terms, fuzzy_date

ENDPOINT = "https://graphql.anilist.co"
# AniList responde 403 al User-Agent por defecto de urllib; hay que identificarse.
USER_AGENT = "catalyst-radar/1.0 (listing-sniper)"

QUERY = """
query ($page: Int, $after: FuzzyDateInt) {
  Page(page: $page, perPage: 50) {
    pageInfo { hasNextPage currentPage }
    media(
      type: ANIME
      sort: POPULARITY_DESC
      startDate_greater: $after
      status_in: [NOT_YET_RELEASED, RELEASING]
    ) {
      id
      format
      countryOfOrigin
      popularity
      favourites
      siteUrl
      title { romaji english native }
      synonyms
      startDate { year month day }
    }
  }
}
"""

FORMAT_TO_TYPE = {
    "MOVIE": "film_release",
    "TV": "season_premiere",
    "TV_SHORT": "season_premiere",
    "ONA": "season_premiere",
    "OVA": "season_premiere",
    "SPECIAL": "season_premiere",
}


def _post(query: str, variables: dict, retries: int = 3) -> dict:
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        ENDPOINT, data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json",
                 "User-Agent": USER_AGENT},
    )
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries - 1:
                wait = int(e.headers.get("Retry-After", 60))
                time.sleep(wait)
                continue
            raise
    raise RuntimeError("anilist: reintentos agotados")


def fetch(days_back: int = 7, max_pages: int = 8, min_popularity: int = 2000):
    """
    Trae anime con fecha de inicio futura, ordenado por popularidad.

    min_popularity filtra la cola larga. Un IP con menos de ~2000 de
    popularity no va a mover un token por si solo, y solo te ensucia el
    matcher con falsos positivos.
    """
    cutoff = date.today() - timedelta(days=days_back)
    after = int(cutoff.strftime("%Y%m%d"))

    page = 1
    while page <= max_pages:
        data = _post(QUERY, {"page": page, "after": after})
        payload = data.get("data", {}).get("Page")
        if not payload:
            break

        for m in payload["media"]:
            pop = m.get("popularity") or 0
            if pop < min_popularity:
                continue

            sd = m.get("startDate") or {}
            iso, precision = fuzzy_date(sd.get("year"), sd.get("month"), sd.get("day"))

            t = m.get("title") or {}
            titles = [t.get("english"), t.get("romaji"), t.get("native")]
            aliases = [x for x in titles + (m.get("synonyms") or []) if x]

            yield Event(
                source="anilist",
                external_id=str(m["id"]),
                ip_name=t.get("english") or t.get("romaji") or t.get("native") or "?",
                aliases=aliases[:12],
                search_terms=build_search_terms(titles + (m.get("synonyms") or [])[:3]),
                event_type=FORMAT_TO_TYPE.get(m.get("format"), "season_premiere"),
                event_date=iso,
                date_precision=precision,
                region=m.get("countryOfOrigin") or "JP",
                audience_proxy=max(pop, m.get("favourites") or 0),
                source_url=m.get("siteUrl"),
                raw=m,
            )

        if not payload["pageInfo"]["hasNextPage"]:
            break
        page += 1
        time.sleep(0.8)  # cortesia con el rate limit
