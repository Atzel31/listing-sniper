#!/usr/bin/env python3
"""
Catalyst Radar :: Batch 1
Ingesta de eventos con fecha publica. Todavia no toca tokens.

Uso:
    python ingest.py                # corre todas las fuentes disponibles
    python ingest.py --source anilist
    python ingest.py --report       # solo muestra estado, no ingiere

Cadencia sugerida en Railway: diaria. Las fechas no cambian a menudo,
y cuando cambian eso ES la senal.
"""
from __future__ import annotations

import argparse
import os
import sys
import traceback

from store import (connect, upsert_event, pending_catalysts, upcoming,
                   start_run, finish_run)

SOURCES = {}

import anilist  # noqa: E402
SOURCES["anilist"] = anilist.fetch

if os.getenv("TMDB_API_KEY"):
    import tmdb  # noqa: E402
    SOURCES["tmdb"] = tmdb.fetch


def run_source(conn, name: str, fetch) -> tuple[int, int, int]:
    run_id = start_run(conn, name)
    seen = new = changed = 0
    try:
        for ev in fetch():
            seen += 1
            is_new, changes = upsert_event(conn, ev)
            new += int(is_new)
            changed += int(bool(changes))
            for c in changes:
                if c["is_catalyst"]:
                    print(f"  [!] {ev.ip_name}: {c['field']} "
                          f"{c['old_value']} -> {c['new_value']}")
        finish_run(conn, run_id, seen, new, changed)
        conn.commit()
    except Exception as e:
        conn.rollback()
        finish_run(conn, run_id, seen, new, changed, error=traceback.format_exc()[-2000:])
        conn.commit()
        print(f"  error en {name}: {e}", file=sys.stderr)
    return seen, new, changed


def report(conn) -> None:
    cats = pending_catalysts(conn)
    if cats:
        print(f"\n== Catalizadores sin notificar ({len(cats)}) ==")
        for c in cats[:20]:
            print(f"  {c['ip_name'][:44]:44} {c['field']}: "
                  f"{c['old_value']} -> {c['new_value']}")
    else:
        print("\n== Sin catalizadores nuevos ==")

    rows = upcoming(conn, lo=5, hi=70, only_exact=True)
    print(f"\n== Ventana 5-70 dias, fecha exacta ({len(rows)}) ==")
    print(f"  {'dias':>5}  {'audiencia':>9}  {'region':6}  IP / terminos de busqueda")
    for r in rows[:30]:
        import json as _json
        terms = ", ".join(_json.loads(r["search_terms"])[:3])
        print(f"  {r['days_until']:>5}  {r['audience_proxy']:>9}  "
              f"{(r['region'] or '?'):6}  {r['ip_name'][:38]:38}  [{terms}]")
    print("\n  Estas filas son la entrada del Batch 2 (matcher contra DexScreener).")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=list(SOURCES))
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()

    conn = connect()

    if not args.report:
        targets = {args.source: SOURCES[args.source]} if args.source else SOURCES
        for name, fetch in targets.items():
            print(f"[{name}] ingiriendo...")
            seen, new, changed = run_source(conn, name, fetch)
            print(f"[{name}] {seen} vistos, {new} nuevos, {changed} modificados")

    report(conn)
    conn.close()


if __name__ == "__main__":
    main()
