# istatPy - Piano di sviluppo

## Obiettivo
Versione Python del pacchetto R `istatR`, gestita con `uv`.
API ISTAT SDMX REST: `https://esploradati.istat.it/SDMXWS/rest`

## Struttura progetto
```
istatPy/
├── pyproject.toml
├── README.md
├── LOG.md
├── tasks/todo.md
└── src/
    └── istatpy/
        ├── __init__.py
        ├── base.py       # Config API, funzioni HTTP
        ├── utils.py      # Helper XML, make_url_key
        ├── discovery.py  # all_available, search_dataset, IstatDataset
        └── retrieval.py  # get_data, istat_get, parse_time_period
```

## Dipendenze
- `httpx` - HTTP (con retry via `tenacity`)
- `lxml` - parsing XML con namespace
- `polars` - DataFrame (al posto di tibble/dplyr)
- `duckdb` - query SQL su dati
- `plotnine` - grafici statici

## Fasi

### Fase 1 - Setup progetto
- [x] `uv init istatPy` nella cartella padre
- [x] Aggiungere dipendenze con `uv add`
- [x] Creare struttura `src/istatpy/`

### Fase 2 - base.py
- [x] Config: `BASE_URL`, `AGENCY_ID`, `TIMEOUT`
- [x] `istat_timeout()` - get/set timeout
- [x] `istat_request()` - HTTP con retry (3 tentativi)
- [x] `istat_request_xml()` - risposta XML con namespace
- [x] `istat_request_csv()` - risposta CSV → Polars DataFrame

### Fase 3 - utils.py
- [x] `xml_text_safe()` - estrai testo XML sicuro
- [x] `xml_attr_safe()` - estrai attributo XML sicuro
- [x] `make_url_key()` - costruisce chiave filtro SDMX
- [x] `get_name_by_lang()` - nome per lingua da XML

### Fase 4 - discovery.py
- [x] `all_available()` - lista tutti i dataset ISTAT
- [x] `search_dataset(keyword)` - cerca per parola chiave
- [x] Funzioni standalone (non classe):
  - `istat_dataset()` - crea dict dataset
  - `print_dataset()` - stampa info
  - `dimensions_info()` - info dimensioni
  - `get_dimension_values()` - valori disponibili
  - `get_available_values()` - tutti i valori disponibili
  - `set_filters()` - imposta filtri
  - `reset_filters()` - azzera filtri
- [x] `_get_dimensions()` - interno

### Fase 5 - retrieval.py
- [x] `parse_time_period(x)` - parse formati SDMX: YYYY, YYYY-MM, YYYY-Qn, YYYY-Sn, YYYY-Wnn, YYYY-MM-DD
- [x] `get_data(dataset, ...)` - recupera dati con filtri
- [x] `istat_get(dataflow_id, ...)` - shortcut all-in-one

### Fase 6 - __init__.py
- [x] Esporta API pubblica

### Fase 7 - Documentazione
- [x] README.md con esempi (incluso plot disoccupazione con plotnine)
- [x] LOG.md

## Domande aperte
- Nome pacchetto: `istatpy` o `istat-py`?
- Usare `httpx` invece di `requests` (async support)?

---

## Fase 8 - Rate limiting + Cache dataflow

### Contesto
ISTAT: limite **5 query/minuto per IP**. Superato → blocco 1-2 giorni.

### Phase 1 — Rate limiter in `base.py`

- [x] Aggiungere `_rate_limit_check()` in `base.py`
  - Timestamp in `/tmp/istatpy_rate_limit.log`
  - Se `elapsed < 12s`: stampa avviso e `time.sleep(12 - elapsed)`
  - Sovrascrive il log con timestamp corrente dopo ogni chiamata
- [x] Chiamare `_rate_limit_check()` dentro `_do_request()` in `istat_request()`

### Phase 2 — Cache lista dataflow in `discovery.py`

- [x] Aggiungere `_load_cached_dataflows()` in `discovery.py`
  - Cache in `/tmp/istatpy_dataflows.parquet`, TTL 24h
  - Se file esiste ed è < 24h: legge il parquet (0 query API)
  - Se scaduto o assente: chiama API, salva parquet, ritorna DataFrame
- [x] `all_available()` usa la cache

---

## Review

- Struttura a 4 moduli: `base`, `utils`, `discovery`, `retrieval`
- API identica a istatR: stesse funzioni, stessi nomi
- Dataset rappresentato come `dict` Python (equivalente alla lista S3 di R)
- DataFrame: Polars al posto di tibble
- HTTP: httpx + tenacity per retry automatico
- XML: lxml con namespace-aware XPath
- `parse_time_period` gestisce tutti i formati SDMX via Polars `map_elements`
- `set_filters` e `reset_filters` restituiscono un nuovo dict (immutabilità)
- README include esempio completo con plotnine
