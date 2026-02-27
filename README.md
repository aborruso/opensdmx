# istatpy

Python interface to the Italian National Institute of Statistics (ISTAT) SDMX REST API.

## Acknowledgements

Special thanks to [@jfulponi](https://github.com/jfulponi) for the R package [istatR](https://github.com/jfulponi/istatR), which inspired this project and provided the foundation for the API design.

Also inspired by the Python package [istatapi](https://github.com/Attol8/istatapi) by [@Attol8](https://github.com/Attol8).

## Installation

```bash
uv add istatpy
# or
pip install istatpy
```

## Quick start

```python
import istatpy

# List all available datasets
datasets = istatpy.all_available()
print(datasets.head())

# Search by keyword
unemp = istatpy.search_dataset("unemployment")

# One-liner retrieval
data = istatpy.istat_get(
    "139_176",
    FREQ="M",
    TIPO_DATO="ISAV",
    PAESE_PARTNER="WORLD",
    start_period="2022-01-01",
)
```

## API

| Function | Description |
|---|---|
| `all_available()` | List all ISTAT datasets → Polars DataFrame |
| `search_dataset(keyword)` | Search by keyword in description |
| `istat_dataset(id)` | Create a dataset object (dict) |
| `print_dataset(ds)` | Print dataset summary |
| `dimensions_info(ds)` | Dimension metadata → Polars DataFrame |
| `get_dimension_values(ds, dim)` | Values for a dimension |
| `get_available_values(ds)` | All available values (via constraint API) |
| `set_filters(ds, **kwargs)` | Set dimension filters |
| `reset_filters(ds)` | Reset all filters to `"."` (all) |
| `get_data(ds, ...)` | Retrieve data → Polars DataFrame |
| `istat_get(id, ...)` | Shortcut combining all steps |
| `istat_timeout(seconds)` | Get/set API timeout (default: 300 s) |

## Example: Italian Unemployment Rate

```python
import istatpy
from plotnine import (
    ggplot, aes, geom_line, geom_point,
    labs, theme_minimal, scale_x_date,
)

# Build dataset
ds = istatpy.istat_dataset("151_1178")
ds = istatpy.set_filters(
    ds,
    FREQ="Q",
    REF_AREA="IT",
    DATA_TYPE="UNEM_R",
    SEX="9",
    AGE="Y_GE15",
)

data = istatpy.get_data(ds)

# Remove duplicates and convert OBS_VALUE to float
import polars as pl
data = (
    data
    .unique(subset=["TIME_PERIOD"])
    .sort("TIME_PERIOD")
    .with_columns(pl.col("OBS_VALUE").cast(pl.Float64))
)

# Plot with plotnine
plot = (
    ggplot(data.to_pandas(), aes(x="TIME_PERIOD", y="OBS_VALUE"))
    + geom_line(color="#1f77b4", size=1)
    + geom_point(color="#1f77b4", size=0.8)
    + labs(
        title="Italian Unemployment Rate (Quarterly, Seasonally Adjusted)",
        x="Year",
        y="Unemployment Rate (%)",
        caption="Source: ISTAT",
    )
    + scale_x_date(date_breaks="2 years", date_labels="%Y")
    + theme_minimal()
)
plot.save("unemployment_rate.png", dpi=150, width=10, height=5)
```

## CLI

Install globally:

```bash
uv tool install istatpy
```

### Commands

| Command | Description |
|---|---|
| `istatpy search <keyword>` | Keyword search in dataset descriptions |
| `istatpy search --semantic <query>` | Semantic search (multilingual, requires `istatpy embed`) |
| `istatpy embed` | Build semantic embeddings cache via Ollama |
| `istatpy info <id>` | Show dataset metadata and dimensions |
| `istatpy values <id> <dim>` | Show available values for a dimension |
| `istatpy get <id> [--DIM VALUE] [--out file]` | Download data (CSV/parquet/JSON) |
| `istatpy plot <id> [--DIM VALUE] [--out file]` | Plot data as line chart |
| `istatpy wizard` | Interactive wizard to discover, filter and get download URL |

### Wizard

```bash
istatpy wizard
```

Step-by-step interactive flow:

1. Type a query in any language (Italian or English)
2. Select a dataset from paginated results
3. For each dimension: fuzzy-filter values and choose one (or skip with "all")
4. Get the SDMX download URL and `curl` command

### Semantic search setup

Requires [Ollama](https://ollama.com) with the `nomic-embed-text-v2-moe` model:

```bash
ollama pull nomic-embed-text-v2-moe
istatpy embed   # run once, builds /tmp/istatpy_embeddings.parquet
istatpy search --semantic "disoccupazione"   # cross-language search
```

### Caching

| File | Content | TTL |
|---|---|---|
| `/tmp/istatpy_dataflows.parquet` | Full catalog (4714 datasets) | 24h |
| `/tmp/istatpy_embeddings.parquet` | Semantic embeddings (768-dim) | manual |
| `/tmp/istatpy_cache.db` | Dimensions and codelist values (SQLite) | 7 days |

## API Reference

- Base URL: `https://esploradati.istat.it/SDMXWS/rest`
- Agency ID: `IT1`
- Docs: [developers.italia.it](https://developers.italia.it/it/api/istat-sdmx-rest)

## Timeout

The ISTAT API can be slow. Default timeout is 300 seconds.

```python
istatpy.istat_timeout()      # get current timeout
istatpy.istat_timeout(600)   # set to 10 minutes
```

## License

Apache License 2.0
