# Cache Reference

opensdmx uses two types of local cache files, stored under `~/.cache/opensdmx/{AGENCY_ID}/`. Each provider has its own isolated cache namespace.

---

## Files

| File | Format | Content | TTL |
|---|---|---|---|
| `dataflows.parquet` | Parquet | Provider dataset catalog | 24h |
| `embeddings.parquet` | Parquet | Semantic embeddings (per dataset) | No expiry |
| `cache.db` | SQLite | Dimensions, codelists, constraints, blacklist | 7 days (per row) |

Examples for Eurostat (agency `ESTAT`) and ISTAT (agency `IT1`):

```
~/.cache/opensdmx/ESTAT/dataflows.parquet
~/.cache/opensdmx/ESTAT/embeddings.parquet
~/.cache/opensdmx/ESTAT/cache.db

~/.cache/opensdmx/IT1/dataflows.parquet
~/.cache/opensdmx/IT1/embeddings.parquet
~/.cache/opensdmx/IT1/cache.db
```

---

## Parquet files

### `dataflows.parquet`

Downloaded from the SDMX `dataflow/{agency_id}` endpoint. Refreshed if older than 24 hours.

Columns:

| Column | Type | Description |
|---|---|---|
| `df_id` | String | Dataset identifier (e.g. `une_rt_m`, `151_914`) |
| `version` | String | Dataflow version |
| `df_description` | String | Human-readable dataset name |
| `df_structure_id` | String | Referenced Data Structure Definition ID |

### `embeddings.parquet`

Built locally by `opensdmx embed` using Ollama (`nomic-embed-text-v2-moe`). Not automatically refreshed; rebuild manually when the catalog changes.

Columns:

| Column | Type | Description |
|---|---|---|
| `df_id` | String | Dataset identifier |
| `embedding` | List[Float32] | Embedding vector (dimension depends on the model) |

---

## SQLite: `cache.db`

### Tables

#### `structure_dims`

Dimension metadata for a Data Structure Definition (fetched from the `datastructure` endpoint).

| Column | Type | Notes |
|---|---|---|
| `structure_id` | TEXT | SDMX structure ID — PK part |
| `dimension_id` | TEXT | Dimension code (e.g. `FREQ`, `REF_AREA`) — PK part |
| `position` | INTEGER | Position in the SDMX key (1-based) |
| `codelist_id` | TEXT | References a codelist in `codelist_info` |
| `cached_at` | REAL | Unix timestamp |

#### `codelist_info`

Human-readable description of a codelist (e.g. "Frequency of collection").

| Column | Type | Notes |
|---|---|---|
| `codelist_id` | TEXT | PK |
| `description` | TEXT | Label in English |
| `cached_at` | REAL | Unix timestamp |

#### `codelist_values`

Individual code entries within a codelist (e.g. `A = Annual`).

| Column | Type | Notes |
|---|---|---|
| `codelist_id` | TEXT | FK → `codelist_info` — PK part |
| `code_id` | TEXT | Code value (e.g. `A`, `IT`) — PK part |
| `code_name` | TEXT | Human-readable label |
| `cached_at` | REAL | Unix timestamp |

#### `available_constraints`

Codes actually present in a dataset, fetched from the `availableconstraint` (or `contentconstraint`) endpoint. More reliable than codelist values for filter selection because not all theoretically valid codes are present in every dataset.

| Column | Type | Notes |
|---|---|---|
| `df_id` | TEXT | Dataset ID — PK part |
| `dimension_id` | TEXT | Dimension code — PK part |
| `code_id` | TEXT | Available code — PK part |
| `cached_at` | REAL | Unix timestamp |

On write, the existing rows for `df_id` are deleted before re-inserting, so the table always reflects the latest constraint snapshot.

#### `invalid_datasets`

Datasets that failed an API availability check (triggered during `guide`). These are excluded from all future searches and listings. There is no automatic expiry; entries must be removed manually via `opensdmx blacklist`.

| Column | Type | Notes |
|---|---|---|
| `df_id` | TEXT | PK |
| `description` | TEXT | Dataset name at the time of marking |
| `marked_at` | REAL | Unix timestamp |

---

## ER diagram

```mermaid
erDiagram
    structure_dims {
        TEXT structure_id PK
        TEXT dimension_id PK
        INTEGER position
        TEXT codelist_id FK
        REAL cached_at
    }
    codelist_info {
        TEXT codelist_id PK
        TEXT description
        REAL cached_at
    }
    codelist_values {
        TEXT codelist_id PK
        TEXT code_id PK
        TEXT code_name
        REAL cached_at
    }
    available_constraints {
        TEXT df_id PK
        TEXT dimension_id PK
        TEXT code_id PK
        REAL cached_at
    }
    invalid_datasets {
        TEXT df_id PK
        TEXT description
        REAL marked_at
    }

    structure_dims }o--|| codelist_info : "codelist_id"
    codelist_info ||--|{ codelist_values : "codelist_id"
```
