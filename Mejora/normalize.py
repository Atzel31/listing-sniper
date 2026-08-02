"""
Modelo de evento, fechas difusas y generacion de terminos de busqueda.

Es la pieza central del Batch 1: define el `Event` que todas las fuentes
producen y que `store.upsert_event` compara. La deteccion del catalizador
"anuncio de fecha" vive en `precision_tightened`: una transicion de la
precision de la fecha hacia `exact` es, por si misma, la señal.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone

# Orden de certeza de una fecha. Subir en este ranking = anuncio de fecha.
PRECISION_RANK = {"rumor": 0, "quarter": 1, "month": 2, "exact": 3}


def now_iso() -> str:
    """Timestamp UTC en ISO, sin microsegundos."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def precision_tightened(old: str, new: str) -> bool:
    """True si la fecha se volvio mas concreta (p. ej. rumor -> exact).
    Ese salto ES el catalizador de anuncio de fecha del que sale la alerta
    mas limpia: por definicion nadie lo tenia posicionado."""
    return PRECISION_RANK.get(new or "rumor", 0) > PRECISION_RANK.get(old or "rumor", 0)


def fuzzy_date(year, month, day) -> tuple[str | None, str]:
    """
    Convierte una fecha desglosada (con nulls) en (ISO | None, precision).

      year+month+day -> ("YYYY-MM-DD", "exact")
      year+month     -> ("YYYY-MM-01", "month")   # primer dia como ancla
      year           -> (None,         "quarter") # sabemos el año, no el dia
      nada            -> (None,         "rumor")
    """
    try:
        y = int(year) if year else 0
        m = int(month) if month else 0
        d = int(day) if day else 0
    except (TypeError, ValueError):
        return None, "rumor"

    if not y:
        return None, "rumor"
    if y and m and d:
        return f"{y:04d}-{m:02d}-{d:02d}", "exact"
    if y and m:
        return f"{y:04d}-{m:02d}-01", "month"
    return None, "quarter"


# Ruido que no ayuda al matcher a encontrar el ticker.
_STOP = {
    "the", "a", "an", "of", "and", "to", "in", "movie", "film", "season",
    "part", "the movie", "el", "la", "los", "las", "de", "y",
}


def _slug(text: str) -> str:
    """Minusculas sin acentos, colapsando espacios. Conserva kana/kanji tal cual."""
    text = unicodedata.normalize("NFKC", text).strip().lower()
    # quitar acentos latinos, dejar CJK intacto
    text = "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )
    text = re.sub(r"[^\w\s　-鿿가-힯]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def build_search_terms(titles) -> list[str]:
    """
    A partir de los titulos/alias de un IP, genera los terminos que el matcher
    (Batch 2) usara para buscar el ticker en DexScreener. Devuelve una lista
    dedup, en orden de utilidad: titulos completos primero, luego la primera
    palabra distintiva (los tickers suelen ser una sola palabra: CHIIKAWA).
    """
    terms: list[str] = []
    seen: set[str] = set()

    def _push(t: str):
        t = t.strip()
        if not t:
            return
        key = t.lower()
        if key not in seen:
            seen.add(key)
            terms.append(t)

    for t in titles or []:
        if not t:
            continue
        s = _slug(t)
        if not s:
            continue
        _push(s)
        # primera palabra "de peso" (>=3 chars y no stopword) como termino corto
        for w in s.split():
            if len(w) >= 3 and w not in _STOP:
                _push(w)
                break

    return terms[:8]


def _event_id(source: str, external_id: str) -> str:
    """Hash determinista source+external_id (mismo evento -> mismo id)."""
    return hashlib.sha1(f"{source}:{external_id}".encode("utf-8")).hexdigest()[:16]


@dataclass
class Event:
    source: str
    external_id: str
    ip_name: str
    aliases: list
    search_terms: list
    event_type: str
    event_date: str | None
    date_precision: str
    region: str | None = None
    audience_proxy: int = 0
    source_url: str | None = None
    raw: dict | None = None

    def to_row(self) -> dict:
        """Aplana el evento a las columnas de la tabla `events`.
        Las listas y el payload crudo se serializan a JSON."""
        return {
            "id": _event_id(self.source, str(self.external_id)),
            "source": self.source,
            "external_id": str(self.external_id),
            "ip_name": self.ip_name or "?",
            "aliases": json.dumps(self.aliases or [], ensure_ascii=False),
            "search_terms": json.dumps(self.search_terms or [], ensure_ascii=False),
            "event_type": self.event_type,
            "event_date": self.event_date,
            "date_precision": self.date_precision,
            "region": self.region,
            "audience_proxy": int(self.audience_proxy or 0),
            "source_url": self.source_url,
            "raw": json.dumps(self.raw, ensure_ascii=False) if self.raw is not None else None,
        }
