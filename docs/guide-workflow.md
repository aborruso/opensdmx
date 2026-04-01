# `opensdmx guide` — workflow

## Summary

The `opensdmx guide` command leads the user from a natural-language goal to a ready-to-use SDMX data URL, in six main phases.

**Phase 1 — Query.** If not provided as an argument, the query is requested interactively. Any language is accepted.

**Phase 2 — Dataset selection.** The query is compared semantically against the embeddings of the provider catalog (Ollama `nomic-embed-text-v2-moe`). Results are shown in a paged list (10 at a time, sorted by score). The user navigates and selects a dataset.

**Phase 3 — Confirmation and availability check.** A panel shows the dataset ID, description, and dimensions. The user confirms or returns to the list. If confirmed, an API check is performed with `lastNObservations=1`: if the dataset does not respond correctly it is added to the SQLite blacklist and removed from the current result list, then the selection restarts.

**Phase 4 — AI session.** A multi-turn conversation starts with Gemini 2.5 Flash. The model loads the values actually available for each dimension (from `availableconstraint`, cached 7 days) and the textual descriptions of codes (from codelists, cached 7 days). The user describes what they want; the AI proposes filters using only real codes. When the user confirms with a short input (e.g. "ok", "yes"), filters are extracted in structured form.

**Phase 5 — Validation.** The codes proposed by the AI are checked against `availableconstraint`. If any codes are invalid, the user can return to the AI with corrections or proceed anyway. A sample request is then made with the full filter combination: if it returns no data, the user is offered the option to ask the AI for an alternative or to display the URL anyway.

**Phase 6 — Result.** A panel shows the dataset, active filters, AI reasoning, SDMX URL, `curl` command, and `opensdmx get` command ready for download.

---

## Flowchart

```mermaid
flowchart TD
    A([Start]) --> B{Query provided?}
    B -- No --> C[Prompt: enter goal]
    B -- Yes --> D
    C --> D[Semantic search<br>on embeddings<br>top 100 results]

    D --> E[Paged dataset list<br>10 per page]
    E --> F{User selects}
    F -- Prev / Next --> E
    F -- Cancel --> Z([Exit])
    F -- Dataset selected --> G[Load dataset metadata<br>from SDMX structure endpoint]

    G --> H[Show panel:<br>ID, description, dimensions]
    H --> I{Confirm?}
    I -- No, go back --> E
    I -- Exit --> Z
    I -- Yes --> J[Check API availability<br>lastNObservations=1]

    J -- Not available --> K[Save to blacklist<br>Remove from current list]
    K --> E

    J -- Available --> L[AI multi-turn session<br>gemini-2.5-flash<br>with 3 tools]

    subgraph AI ["AI session (guide_session)"]
        L --> L1[Load available<br>constraints — cached 7d]
        L1 --> L2[Load dimension<br>descriptions — cached 7d]
        L2 --> L3[Conversation loop<br>with user]
        L3 --> L4{User input<br>is confirmation?<br>max 3 words}
        L4 -- No --> L3
        L4 -- Yes --> L5[Extract structured<br>filters with<br>gemini structured output]
    end

    L5 --> M[Validate codes<br>against availableconstraint]
    M -- Invalid codes --> N{What to do?}
    N -- Ask AI to fix --> L
    N -- Use anyway --> O
    N -- Exit --> Z
    M -- OK --> O[Apply filters<br>Build SDMX URL]

    O --> P[Verify filter combination<br>with real sample]
    P -- No data --> Q{What to do?}
    Q -- Ask AI --> L
    Q -- Show anyway --> R
    Q -- Exit --> Z
    P -- OK --> R

    R([Show result:<br>Dataset · Filters · Reasoning<br>URL · curl · opensdmx get])
```

---

## Steps described

| Step | Description |
|---|---|
| Semantic search | `opensdmx embed` pre-builds embeddings; search uses cosine similarity on Ollama `nomic-embed-text-v2-moe` |
| Availability check | Request with `lastNObservations=1`; if it fails the dataset goes to the SQLite blacklist and disappears from the list |
| AI session | Multi-turn chat with Gemini 2.5 Flash; tools `lookup_actual_values` and `lookup_dimension_values` use the SQLite cache (7d) |
| Code validation | Comparison between AI-proposed codes and those present in `availableconstraint` |
| Combination validation | Real sample with active filters; if empty, offers to return to the AI |
| Result | SDMX URL · `curl` command · `opensdmx get` command ready for download |

## Tools available to the AI

| Tool | Purpose |
|---|---|
| `lookup_actual_values(dim)` | Codes **actually present** in the dataset (from `availableconstraint`, cached) |
| `lookup_dimension_values(dim)` | Textual descriptions of codes (from codelist, cached) |
| `test_filter_combination(**kwargs)` | Verifies that a filter combination returns real data |

---

## Caching

| Resource | Cache location | TTL |
|---|---|---|
| Dataflow list | `~/.cache/opensdmx/{AGENCY_ID}/dataflows.parquet` | 24h |
| Embeddings | `~/.cache/opensdmx/{AGENCY_ID}/embeddings.parquet` | No expiry |
| Dimensions | SQLite `~/.cache/opensdmx/{AGENCY_ID}/cache.db` | 7 days |
| Codelist values | SQLite `cache.db` | 7 days |
| Available constraints | SQLite `cache.db` | 7 days |
| Invalid datasets | SQLite `cache.db` | Permanent |

---

## Known limitations

- `availableconstraint` shows values present in the dataset overall, but not all combinations are valid (e.g. a code valid at national level may not exist at regional level for a specific data type).
- `test_filter_combination` mitigates this: it verifies that the full combination produces real data.
- Rate limit for ISTAT: 13 seconds between API calls.
