# Catalyst Radar :: Batch 1

Calendario de eventos culturales con fecha pública. Este batch **no toca tokens**:
solo construye y mantiene la tabla de eventos, que es la entrada del matcher.

## Por qué así

- **Se parte de los eventos, no de los tokens.** Son unos cientos por trimestre y
  vienen estructurados. Enumerar el universo de tokens no es viable ni barato.
- **APIs, no scrapers.** AniList y TMDB devuelven JSON estable. Los scrapers de
  prensa se rompen solos y se dejan para una fase posterior.
- **El diff es la feature.** Una transición de `date_precision` hacia `exact`
  significa que el estudio acaba de anunciar la fecha. Es un catalizador no
  programado, y aquí se detecta como un cambio de campo, sin NLP ni sentiment.

## Instalación

Sin dependencias externas. Solo stdlib de Python 3.11+.

```bash
export CATALYST_DB=/data/catalyst.db     # Railway Volume
export TMDB_API_KEY=...                  # opcional; sin esto solo corre AniList

python ingest.py            # ingiere y reporta
python ingest.py --report   # solo reporta
```

## Cadencia en Railway

Ingesta diaria. Las fechas cambian poco, y cuando cambian eso es la señal.
El rematch por hora llega en el Batch 2, no aquí.

## Estado

| Archivo | Qué hace |
|---|---|
| `schema.sql` | Tablas `events`, `event_changes`, `ingest_runs` |
| `normalize.py` | Modelo `Event`, fechas difusas, generación de términos de búsqueda |
| `store.py` | Upsert con detección de diffs y marcado de catalizadores |
| `sources/anilist.py` | Anime y cine japonés (sin auth) |
| `sources/tmdb.py` | Cine por región JP/CN/KR/TW/HK |
| `ingest.py` | Entry point |

## Verificado y no verificado

Probado en local: normalización, fechas difusas, upsert, detección del
catalizador de anuncio de fecha, consultas de ventana.

**No probado contra las APIs en vivo** (el entorno donde se escribió no tiene
salida a AniList ni TMDB). La primera corrida real puede necesitar ajustes en
el parseo de respuestas. Corre `python ingest.py --source anilist` y revisa
`ingest_runs.error` si algo falla.

## Siguiente

**Batch 2**: matcher. Para cada fila de `upcoming()`, buscar en DexScreener por
`search_terms`, rankear por liquidez, y marcar conflicto si el segundo candidato
tiene más del 40% de la liquidez del primero (atención fragmentada = señal
negativa).

Antes de las alertas, el backtest: cargar eventos de ago 2025 a jul 2026 y
comprobar que Chiikawa aparece en el top 15 el 20 de julio. Si no aparece,
el scorer está mal calibrado.
