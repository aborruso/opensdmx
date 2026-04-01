# Technical Specifications

This document covers non-obvious behaviors of opensdmx that are not immediately apparent from the public API.

---

## TIME_PERIOD conversion

When a dataset contains a `TIME_PERIOD` column, `get_data()` and `fetch()` automatically convert the raw SDMX time strings to Python `datetime.date` objects using `parse_time_period()`.

### Why it is done

SDMX providers return time periods in various textual formats (`2015`, `2015-Q1`, `2015-12`, etc.). These are strings, not dates. Converting them to `date` objects enables:

- Correct chronological sorting (the result is always sorted by `TIME_PERIOD` ascending).
- Compatibility with plotnine's `scale_x_date` for time-series charts.
- Standard comparisons in Polars without type coercion.

### Formats handled

| Raw SDMX string | Converted to |
|---|---|
| `2015` | `2015-01-01` |
| `2015-07` | `2015-07-01` |
| `2015-Q2` | `2015-04-01` |
| `2015-S1` | `2015-01-01` |
| `2015-S2` | `2015-07-01` |
| `2015-W03` | First day of that ISO week |
| `2015-07-15` | `2015-07-15` (pass-through) |

Strings that do not match any pattern are returned as `null`. Conversion uses `polars.Series.str.to_date` with `strict=False`.

---

## SDMX URL key construction (`make_url_key`)

The SDMX REST data URL uses a positional key: each dimension's filter values are dot-separated, in the order defined by the `position` field of the DSD (Data Structure Definition).

`make_url_key(filters: dict) -> str` builds this string from the `dataset["filters"]` dict.

### Rules

- The `filters` dict is ordered by dimension position (guaranteed because `_get_dimensions` sorts by `position`).
- For each dimension:
  - Empty string, `"."`, or `[""]` → empty segment (wildcard: all values).
  - Single value (string) → that value as-is.
  - Multiple values (list or tuple) → joined with `+` (SDMX multi-value operator).
- Segments are joined with `.`.

### Examples

| `filters` dict | Result key |
|---|---|
| `{"FREQ": "M", "geo": "IT"}` | `M.IT` |
| `{"FREQ": "M", "geo": ["IT", "DE"]}` | `M.IT+DE` |
| `{"FREQ": ".", "geo": "IT"}` | `.IT` |
| `{}` (no filters) | `""` (empty → URL path segment omitted) |

### URL construction

The full data URL is assembled as:

```
{base_url}/data/{agency_id},{df_id},{version}/{key}
```

If the key is empty (no filters), the key segment is omitted and the URL ends at `/{df_id}`.

---

## Output formats

`get_data()` returns a Polars DataFrame. The CLI `get` command writes data based on the `--out` file extension:

| Extension | Format | Notes |
|---|---|---|
| `.csv` | CSV text | Default if `--out` is given with `.csv` |
| `.parquet` | Parquet binary | `df.write_parquet()` |
| `.json` | NDJSON (newline-delimited JSON) | `df.write_ndjson()` |
| (no `--out`) | CSV to stdout | `sys.stdout.write(df.write_csv())` |

---

## Rate limiting

Each provider has a `rate_limit` field (minimum seconds between API calls). The mechanism is file-based, not in-memory, so it persists across subprocesses.

### How it works

1. A lock file is stored at `{tempdir}/opensdmx_{agency_id}_rate_limit.log`.
2. Before each HTTP request, `_rate_limit_check()` reads the file for the last-call timestamp.
3. If the elapsed time is less than `rate_limit`, the process sleeps in 0.2 s increments, printing a countdown.
4. After the wait (or immediately if no wait needed), the file is updated with the current timestamp.

A human-readable label can be set via `set_rate_limit_context(msg)` to display in the countdown line.

### Per-provider defaults

| Provider | `rate_limit` (seconds) |
|---|---|
| eurostat | 0.5 |
| istat | 13.0 |
| ecb | 0.5 |
| oecd | 0.5 |
| insee | 0.5 |
| bundesbank | 0.5 |
| worldbank | 0.5 |
| abs | 0.5 |

The default for any unspecified provider (or custom providers without an explicit value) is `0.5` s.

---

## Retry logic

All HTTP requests go through `sdmx_request()`, which wraps the call with `tenacity.retry`:

- Up to **3 attempts** total.
- Exponential backoff: multiplier `0.5`, minimum `0.5 s`, maximum `4 s`.
- Any exception from `httpx` or from `raise_for_status()` triggers a retry.

---

## Data fetching: Accept header vs format query parameter

SDMX providers differ in how they return CSV data.

`sdmx_request_csv()` checks whether the active provider has a `data_format_param` field:

- **Present** (e.g. Eurostat with `"data_format_param": "SDMX-CSV"`): sends `Accept: application/xml` and appends `?format=SDMX-CSV` to the query string.
- **Absent** (e.g. ISTAT): sends `Accept: text/csv` and no extra query parameter.

Both paths return the raw response body, parsed into a Polars DataFrame via `polars.read_csv`.

---

## Filter handling (`set_filters`)

`set_filters(dataset, **kwargs)` modifies the `filters` dict inside a copy of the dataset dict.

- Dimension matching is **case-insensitive**: `set_filters(ds, freq="M")` matches dimension `FREQ`.
- Unrecognized dimension names raise a `UserWarning` and are silently ignored.
- A filter value can be:
  - A string (`"M"`): single value.
  - A list (`["IT", "DE"]`): multiple values, joined with `+` in the URL key.
  - `"."` or `""`: wildcard (all values).
- `reset_filters(dataset)` resets all dimensions back to `"."`.

### CLI extra args

In the `get` and `plot` commands, dimension filters are passed as extra `--KEY VALUE` pairs after the dataset ID. The CLI parses `ctx.args` in sequential pairs:

```bash
opensdmx get une_rt_m --freq M --geo IT+DE --out data.csv
```

This sets `filters["freq"] = "M"` and `filters["geo"] = "IT+DE"`. Multi-value `+` syntax is passed through to `set_filters` as a string and then to `make_url_key` which keeps it as-is if it is already a string.

---

## Dimension ordering

`_get_dimensions(structure_id)` fetches the Data Structure Definition (DSD) from the SDMX `datastructure` endpoint. For each `Dimension` element it reads:

- `id` attribute.
- `position` attribute (integer).
- `LocalRepresentation/Ref` for the `codelist_id`.

Dimensions are sorted by `position` ascending before being stored and returned. The `filters` dict in the dataset object preserves this order, so `make_url_key` always produces a correctly ordered SDMX key.

---

## Dataflow cache invalidation

`all_available()` caches the provider's dataflow list as a Parquet file at `~/.cache/opensdmx/{AGENCY_ID}/dataflows.parquet`. The TTL is **24 hours** (checked via file modification time). If the file is older than 24 hours or does not exist, a fresh SDMX `dataflow/{agency_id}` request is made.

Invalid datasets (blacklisted via `guide`) are filtered from every returned DataFrame, regardless of whether the data came from cache or a fresh request.
