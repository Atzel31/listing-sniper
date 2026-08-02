"""
Persistencia y deteccion de cambios.

Todo el valor del modulo pasa por upsert_event: no solo guarda, tambien
compara contra lo que ya habia y marca cuando el cambio es en si mismo
una senal (anuncio de fecha).
"""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

from normalize import Event, now_iso, precision_tightened

DB_PATH = Path(os.getenv("CATALYST_DB", "/data/catalyst.db"))
SCHEMA = Path(__file__).parent / "schema.sql"

# Campos que vigilamos. Si cambia otra cosa (audience_proxy sube), no es noticia.
WATCHED = ("event_date", "date_precision", "ip_name", "event_type", "region")


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    p = Path(path or DB_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA.read_text())
    return conn


def upsert_event(conn: sqlite3.Connection, ev: Event) -> tuple[bool, list[dict]]:
    """
    Devuelve (es_nuevo, cambios).

    Un cambio se marca is_catalyst=1 cuando la fecha se vuelve mas concreta.
    Ese es el evento no programado del que sale la alerta mas limpia:
    'rumor' -> 'exact' significa que el estudio acaba de anunciar la fecha,
    y por definicion nadie lo tenia posicionado.
    """
    row = ev.to_row()
    ts = now_iso()
    prev = conn.execute(
        "SELECT * FROM events WHERE source = ? AND external_id = ?",
        (ev.source, ev.external_id),
    ).fetchone()

    if prev is None:
        conn.execute(
            """INSERT INTO events
               (id, source, external_id, ip_name, aliases, search_terms, event_type,
                event_date, date_precision, region, audience_proxy, source_url,
                first_seen_at, last_changed_at, raw)
               VALUES (:id, :source, :external_id, :ip_name, :aliases, :search_terms,
                       :event_type, :event_date, :date_precision, :region,
                       :audience_proxy, :source_url, :ts, :ts, :raw)""",
            {**row, "ts": ts},
        )
        return True, []

    changes: list[dict] = []
    for f in WATCHED:
        old, new = prev[f], row[f]
        if old == new:
            continue
        is_cat = f == "date_precision" and precision_tightened(old or "rumor", new)
        changes.append(
            {"event_id": prev["id"], "field": f, "old_value": old,
             "new_value": new, "is_catalyst": int(is_cat)}
        )

    # Una fecha que se corre tambien importa: es riesgo de delay, no oportunidad.
    if any(c["field"] == "event_date" for c in changes) and prev["event_date"]:
        for c in changes:
            if c["field"] == "event_date":
                c["is_catalyst"] = 1

    conn.execute(
        """UPDATE events SET ip_name=:ip_name, aliases=:aliases, search_terms=:search_terms,
           event_type=:event_type, event_date=:event_date, date_precision=:date_precision,
           region=:region, audience_proxy=:audience_proxy, source_url=:source_url,
           raw=:raw, last_changed_at=CASE WHEN :touched=1 THEN :ts ELSE last_changed_at END
           WHERE id=:id""",
        {**row, "ts": ts, "touched": int(bool(changes))},
    )

    for c in changes:
        conn.execute(
            """INSERT INTO event_changes (event_id, field, old_value, new_value,
                                          changed_at, is_catalyst)
               VALUES (?,?,?,?,?,?)""",
            (c["event_id"], c["field"], c["old_value"], c["new_value"], ts, c["is_catalyst"]),
        )

    return False, changes


def pending_catalysts(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Cambios que son senal y todavia no se notificaron. Lo consume el Batch 4."""
    return conn.execute(
        """SELECT c.*, e.ip_name, e.event_date, e.date_precision, e.audience_proxy, e.source_url
           FROM event_changes c JOIN events e ON e.id = c.event_id
           WHERE c.is_catalyst = 1 AND c.notified = 0
           ORDER BY e.audience_proxy DESC"""
    ).fetchall()


def upcoming(conn: sqlite3.Connection, lo: int = 5, hi: int = 70,
             only_exact: bool = True, min_audience: int = 0) -> list[sqlite3.Row]:
    """
    Ventana de trabajo del scorer. Por defecto 5 a 70 dias y solo fecha exacta,
    que son los filtros de timing y certeza.
    """
    q = """SELECT *, CAST(julianday(event_date) - julianday('now') AS INTEGER) AS days_until
           FROM events
           WHERE event_date IS NOT NULL
             AND days_until BETWEEN ? AND ?
             AND audience_proxy >= ?"""
    params: list = [lo, hi, min_audience]
    if only_exact:
        q += " AND date_precision = 'exact'"
    q += " ORDER BY audience_proxy DESC"
    return conn.execute(q, params).fetchall()


def start_run(conn: sqlite3.Connection, source: str) -> int:
    cur = conn.execute(
        "INSERT INTO ingest_runs (source, started_at) VALUES (?, ?)", (source, now_iso())
    )
    return cur.lastrowid


def finish_run(conn: sqlite3.Connection, run_id: int, seen: int, new: int,
               changed: int, error: str | None = None) -> None:
    conn.execute(
        """UPDATE ingest_runs SET finished_at=?, n_seen=?, n_new=?, n_changed=?, error=?
           WHERE id=?""",
        (now_iso(), seen, new, changed, error, run_id),
    )
