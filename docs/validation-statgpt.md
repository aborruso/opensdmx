# Validation against the StatGPT benchmark

## Background

The IMF Statistics Department published [*StatGPT: AI for Official Statistics*](https://www.imf.org/en/publications/departmental-papers-policy-papers/issues/2026/03/10/statgpt-ai-for-official-statistics-573514) (2026), a paper
that benchmarks how well AI systems retrieve official statistics. The finding is stark: **off-the-shelf
large language models (ChatGPT, Gemini) return inaccurate numerical statistics up to two-thirds of
the time**, with errors ranging from 0.8 to 12.6 percentage points compared to published WEO values —
even when the correct figures are explicitly uploaded into the conversation.

The paper proposes a different architecture: use AI to *generate structured API queries* against
official statistical endpoints, not to generate the numbers. The LLM interprets the question;
the API returns the exact published figure.

**This is exactly what opensdmx does.** The CLI is a thin, precise layer over SDMX 2.1 REST APIs.
When paired with an AI agent (via the `sdmx-explorer` skill), the LLM handles discovery and query
construction; opensdmx handles the retrieval. Numbers are never fabricated.

This document reports a validation test inspired by the StatGPT paper, run in April 2026.

---

## The test

Three AI agents were launched in parallel, in complete isolation — no shared context, no shared
memory. Each received the same natural language request:

> *"I need GDP growth data for G7 countries (Canada, France, Germany, Italy, Japan, United Kingdom,
> United States) from 2019 to 2024."*

Each agent worked autonomously through the full `sdmx-explorer` skill loop:

1. **Discovery** — search for relevant datasets across providers
2. **Schema** — explore the dataset structure and available filter codes
3. **Retrieval** — build and execute the query, save the CSV

The outputs were then compared: Did the agents choose the same provider and dataset? Did they
construct the same query? Did they produce the same numbers?

---

## Results

### Query convergence

All three agents independently converged on the same answer:

| | Agent 1 | Agent 2 | Agent 3 |
|---|---|---|---|
| Provider | OECD | OECD | OECD |
| Dataset | `DSD_NAMAIN10@DF_TABLE1_EXPENDITURE_GROWTH` | same | same |
| Key filter | `TRANSACTION=B1GQ`, `UNIT_MEASURE=PC` | same | same |
| Countries | CAN+DEU+FRA+GBR+ITA+JPN+USA | same | same |

All three rejected Eurostat (which lacks US, Japan, Canada) and chose OECD for the same reason:
full G7 coverage. The reasoning was identical across agents despite complete isolation.

### Value convergence

The three output CSV files were compared row by row:

```
42 / 42 observations match exactly — zero divergence
```

| Country | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 |
|---|---|---|---|---|---|---|
| Canada | 1.91 | -5.04 | 5.95 | 4.70 | 1.95 | 2.05 |
| France | 2.03 | -7.44 | 6.88 | 2.72 | 1.44 | 1.19 |
| Germany | 0.98 | -4.13 | 3.91 | 1.81 | -0.87 | -0.50 |
| Italy | 0.43 | -8.87 | 8.93 | 4.82 | 0.92 | 0.78 |
| Japan | -0.31 | -4.28 | 3.56 | 1.33 | 0.72 | -0.24 |
| United Kingdom | 1.26 | -10.05 | 8.54 | 5.15 | 0.27 | 1.08 |
| United States | 2.58 | -2.08 | 6.15 | 2.52 | 2.93 | 2.79 |

*Source: OECD National Accounts, chain-linked volume, % change on previous year.
Retrieved via opensdmx, April 2026.*

---

## Why this matters

The StatGPT paper tests ChatGPT with the same question across 10 separate conversations.
The results vary by 0.8–12.6 percentage points per series — the model fabricates plausible
but incorrect figures, and the figures change with each call.

This test inverts the experiment: three separate agents, same question, same tool.

The result demonstrates two properties that make opensdmx suitable as an AI data layer:

**1. The AI layer converges when the question has a clear best answer.**
LLMs are non-deterministic, but the skill's discovery logic has a dominant correct path for
well-defined questions. All three agents independently reached the same dataset and the same
filters — the LLM variance is absorbed at the reasoning level, not at the number level.

**2. The data layer is deterministic by construction.**
Once the query is built, `opensdmx get` calls the SDMX API and returns exactly what the
provider publishes. There is no generation, no interpolation, no hallucination. Running the
same query a hundred times returns the same number every time.

The combination — convergent reasoning + deterministic retrieval — produces results that are
both consistent across agents and grounded in official published data.

---

## Additional verification: single-series repeatability

The same WEO series (Japan GDP growth 2021) was queried three consecutive times:

```bash
opensdmx get WEO --provider imf \
  --COUNTRY JPN --INDICATOR NGDP_RPCH --FREQUENCY A \
  --start-period 2021 --end-period 2021
```

Result: **2.697** — identical across all three calls.

The response also includes provenance metadata:

| Field | Value |
|---|---|
| Historical data source | Cabinet Office of Japan via Haver Analytics |
| Methodology | System of National Accounts (SNA) 2008 |
| Chain weighted | Yes, from 1980 |
| Base year | 2015 |
| Last updated | 2025-11-19 |

Not only is the number identical every time — you also know exactly where it came from,
how it was calculated, and when it was last updated. An LLM generating statistics provides
none of this.

---

## Full test report

The complete validation report — covering discovery, schema exploration, cross-source accuracy
(Eurostat vs OECD vs IMF WEO), and all test details — is available at
[`tmp/statgpt-tests/REPORT.md`](../tmp/statgpt-tests/REPORT.md).
