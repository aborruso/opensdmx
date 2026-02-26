# LOG

## 2026-02-26

- Rate limiter: 12s minimi tra chiamate API, log in `/tmp/istatpy_rate_limit.log`
- Cache dataflow: `/tmp/istatpy_dataflows.parquet`, TTL 24h (evita chiamata pesante a ogni `istat_dataset()`)
- Aggiunto `pyarrow` come dipendenza (necessario per `polars.to_pandas()`)

## 2026-02-26 (init)

- Creato progetto `istatpy` con `uv init --package`
- Aggiunto `httpx`, `tenacity`, `lxml`, `polars`, `duckdb`, `plotnine`
- Implementati moduli: `base.py`, `utils.py`, `discovery.py`, `retrieval.py`
- API pubblica esposta in `__init__.py`
- Tutte le funzioni speculari a `istatR`:
  - `all_available()`, `search_dataset()`, `istat_dataset()`
  - `dimensions_info()`, `get_dimension_values()`, `get_available_values()`
  - `set_filters()`, `reset_filters()`
  - `get_data()`, `istat_get()`, `istat_timeout()`
- DataFrame: Polars (non pandas)
- Grafici: plotnine (esempio disoccupazione nel README)
