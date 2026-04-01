# Provider Reference

opensdmx supports 8 built-in SDMX 2.1 providers, configured in `src/opensdmx/portals.json`. Any SDMX 2.1-compliant endpoint can also be used as a custom provider.

---

## Built-in providers

### eurostat (default)

| Field | Value |
|---|---|
| Name | Eurostat |
| `base_url` | `https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1` |
| `agency_id` | `ESTAT` |
| `rate_limit` | 0.5 s |
| `language` | `en` |
| `dataflow_params` | `detail=allstubs&references=none` |
| `constraint_endpoint` | `contentconstraint` |
| `datastructure_agency` | `ESTAT` |
| `data_format_param` | `SDMX-CSV` |

Quirks: Eurostat does not accept `Accept: text/csv`. Data must be requested with `Accept: application/xml` and the `format=SDMX-CSV` query parameter. The `contentconstraint` endpoint is used instead of `availableconstraint`. The `dataflow` request includes `detail=allstubs` and `references=none` for performance.

### istat

| Field | Value |
|---|---|
| Name | ISTAT |
| `base_url` | `https://esploradati.istat.it/SDMXWS/rest` |
| `agency_id` | `IT1` |
| `rate_limit` | 13.0 s |
| `language` | `it` |

Quirks: ISTAT enforces a strict rate limit. The 13-second minimum interval between calls avoids HTTP 429 errors. Data is fetched using `Accept: text/csv` (no `data_format_param`). Dataset descriptions are in Italian; the embedded catalog language is `it`. The `constraint_endpoint` defaults to `availableconstraint`.

### ecb

| Field | Value |
|---|---|
| Name | European Central Bank |
| `base_url` | `https://data-api.ecb.europa.eu/service` |
| `agency_id` | `ECB` |
| `rate_limit` | 0.5 s |
| `language` | `en` |

### oecd

| Field | Value |
|---|---|
| Name | OECD |
| `base_url` | `https://sdmx.oecd.org/public/rest` |
| `agency_id` | `OECD` |
| `rate_limit` | 0.5 s |
| `language` | `en` |

### insee

| Field | Value |
|---|---|
| Name | INSEE (France) |
| `base_url` | `https://www.bdm.insee.fr/series/sdmx` |
| `agency_id` | `FR1` |
| `rate_limit` | 0.5 s |
| `language` | `en` |

### bundesbank

| Field | Value |
|---|---|
| Name | Deutsche Bundesbank |
| `base_url` | `https://api.statistiken.bundesbank.de/rest` |
| `agency_id` | `BBK` |
| `rate_limit` | 0.5 s |
| `language` | `en` |

### worldbank

| Field | Value |
|---|---|
| Name | World Bank |
| `base_url` | `https://api.worldbank.org/v2/sdmx/rest` |
| `agency_id` | `WB` |
| `rate_limit` | 0.5 s |
| `language` | `en` |

### abs

| Field | Value |
|---|---|
| Name | Australian Bureau of Statistics |
| `base_url` | `https://data.api.abs.gov.au/rest` |
| `agency_id` | `ABS` |
| `rate_limit` | 0.5 s |
| `language` | `en` |

---

## Provider configuration fields

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | string | — | Human-readable provider name |
| `base_url` | string | — | SDMX 2.1 REST base URL (required) |
| `agency_id` | string | — | Agency code used in SDMX endpoints (required) |
| `rate_limit` | float | `0.5` | Minimum seconds between API calls |
| `language` | string | `"en"` | Preferred language for dataset descriptions |
| `dataflow_params` | dict | `{}` | Extra query parameters appended to `dataflow/{agency_id}` requests |
| `constraint_endpoint` | string | `"availableconstraint"` | Endpoint for fetching available values (`availableconstraint` or `contentconstraint`) |
| `datastructure_agency` | string | `"ALL"` | Agency used in `datastructure/{agency}/...` requests |
| `data_format_param` | string | absent | If present, sent as `?format={value}` for data requests instead of `Accept: text/csv` |

Fields not specified in `portals.json` fall back to the defaults listed above (applied in `base.py` at load time).

---

## Using a custom provider

Any SDMX 2.1-compliant REST endpoint can be used as a custom provider:

```python
import opensdmx

opensdmx.set_provider(
    "https://mysdmx.example.org/rest",
    agency_id="XYZ",
    rate_limit=1.0,
    language="en",
)
```

From the CLI:

```bash
opensdmx search "unemployment" --provider https://mysdmx.example.org/rest
```

When a custom URL is given, `agency_id` is required. The custom provider uses all default field values unless overridden via `set_provider()` parameters. The cache directory will be `~/.cache/opensdmx/XYZ/`.

Custom providers are not persisted; they must be set each time.
