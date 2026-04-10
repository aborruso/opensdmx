# Future Ideas

## Feynman-Inspired: opensdmx as a Statistical Research Agent

Inspired by [Feynman](https://github.com/getcompanion-ai/feynman), an open-source AI research agent for academic workflows.

### Core Analogy

Feynman is to academic papers what opensdmx could be to statistical data. Both aim at the same goal: verifiable, traceable information retrieval from primary sources. Every claim grounded, every number traceable.

### Ideas

**1. High-level research workflows**

Feynman exposes `/deepresearch`, `/compare`, `/watch` commands. opensdmx has granular primitives but no high-level workflows. Candidates:

- `opensdmx research "eurozone inflation 2020-2024"` — agent that discovers relevant dataflows across providers, fetches data, and produces a grounded report
- `opensdmx compare --indicator CPI --providers oecd,imf,istat` — cross-provider comparison of the same indicator, with discrepancy reporting
- `opensdmx watch <dataflow>` — periodic polling, notifies on new data releases

**2. Systematic provenance**

Feynman generates a `.provenance.md` for every output. opensdmx already has some provenance work (StatGPT validation), but it could be formalized: every `opensdmx data` call could optionally emit a provenance file — DSD used, codelist version, observation attributes, query URL, timestamp.

**3. Multi-agent cross-source verification**

Feynman has a `Verifier` agent that validates every citation. opensdmx could have a `verify` command that takes a numeric value and searches it across alternative providers — "is this figure confirmed by both IMF and OECD?"

**4. Natural language statistical research assistant**

The most ambitious idea: a mode where the user asks a question in natural language and the system:

1. Discovers relevant dataflows (already works via `catalog`)
2. Resolves dimensions and filters (already works via `values`/`constraints`)
3. Fetches the data
4. Answers with figures traced to the exact SDMX source

This would be the statistical equivalent of Feynman.

### Architectural Direction

Feynman has a multi-agent orchestration layer (Pi runtime + 4 specialized subagents). opensdmx is currently a one-shot CLI. The interesting evolution would be adding an agentic/conversational layer **on top of** the existing CLI — not replacing it, but using it as the reliable, verifiable tool that agents call.

The `sdmx-explorer` skill is already an embryo of this pattern. Feynman suggests going deeper: persistent state, structured artifacts, verification loops, composable workflows.
