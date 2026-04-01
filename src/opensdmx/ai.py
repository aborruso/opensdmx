"""AI-assisted filter selection via chatlas (multi-turn conversation)."""
from __future__ import annotations


def _structured_extract(text: str, model_cls, prompt: str) -> object:
    """Extract structured data from text using a second chat (no tools)."""
    from chatlas import ChatGoogle
    chat = ChatGoogle(model="gemini-2.5-flash")
    return chat.chat_structured(
        f"{prompt}\n\nTesto da analizzare:\n{text}",
        data_model=model_cls,
    )


def guide_session(ds: dict, objective: str) -> dict:
    """Multi-turn AI conversation to select filters for a dataset.

    Returns {'filters': dict[str,str], 'reasoning': str}.
    """
    from chatlas import ChatGoogle
    from pydantic import BaseModel
    from rich.console import Console

    from .base import get_provider, set_rate_limit_context
    from .discovery import _get_dimension_description, get_available_values, get_dimension_values

    console = Console()
    dims = ds["dimensions"]
    dims_list = list(dims.keys())

    # Fetch available constraints once (cached) — used by lookup_actual_values
    console.print("[dim]Caricamento valori disponibili...[/dim]")
    set_rate_limit_context(f"Scaricando valori disponibili per {ds['df_id']}")
    try:
        _avail = {dim_id: df["id"].to_list() for dim_id, df in get_available_values(ds).items()}
    except Exception as _e:
        _avail = {}
        console.print(f"[yellow]⚠ Valori disponibili non caricati: {_e}[/yellow]")
    set_rate_limit_context("")
    if not _avail:
        console.print("[yellow]⚠ Conteggio valori non disponibile per questo dataset.[/yellow]")

    def lookup_actual_values(dimension_id: str) -> str:
        """Restituisce i valori EFFETTIVAMENTE presenti nel dataset per una dimensione,
        con descrizione testuale se disponibile in cache.
        Usa questo tool per ottenere i codici da usare nei filtri."""
        from .db_cache import get_cached_codelist_values
        try:
            if not _avail:
                return "Valori disponibili non caricati."
            if dimension_id not in _avail:
                return f"Dimensione '{dimension_id}' non trovata. Disponibili: {', '.join(_avail.keys())}"
            codes = sorted(str(v) for v in _avail[dimension_id] if v is not None)
            # Try to enrich with descriptions from codelist cache (no API call)
            codelist_id = dims.get(dimension_id, {}).get("codelist_id")
            labels = {}
            if codelist_id:
                cached = get_cached_codelist_values(codelist_id)
                if cached:
                    labels = {r["id"]: r["name"] for r in cached}
            if labels:
                lines = [f"{c} = {labels[c]}" if c in labels else c for c in codes]
                return f"Valori disponibili per {dimension_id}:\n" + "\n".join(lines)
            return f"Valori disponibili per {dimension_id}: {', '.join(codes)}"
        except Exception as e:
            return f"Errore: {e}"

    def lookup_dimension_values(dimension_id: str) -> str:
        """Restituisce le descrizioni testuali dei codici di una dimensione (dalla codelist).
        Usa questo tool solo per capire il significato dei codici, NON per scegliere i filtri."""
        try:
            if dimension_id not in dims:
                return f"Dimensione '{dimension_id}' non trovata. Disponibili: {', '.join(dims.keys())}"
            set_rate_limit_context(f"Scaricando codelist per la dimensione {dimension_id}")
            val_df = get_dimension_values(ds, dimension_id)
            set_rate_limit_context("")
            return "\n".join(f"{r['id']}={r['name']}" for r in val_df.iter_rows(named=True))
        except Exception as e:
            set_rate_limit_context("")
            return f"Errore: {e}"

    # Build dimension info: description only (no codelist samples — unreliable)
    dim_info_parts = []
    for dim_id, dim_meta in dims.items():
        codelist_id = dim_meta.get("codelist_id")
        set_rate_limit_context(f"Scaricando info per la dimensione {dim_id}")
        description = _get_dimension_description(codelist_id) or dim_id
        n_vals = len(_avail.get(dim_id, []))
        count_str = f" ({n_vals} valori)" if n_vals else ""
        dim_info_parts.append(f"  {dim_id}: {description}{count_str}")
    set_rate_limit_context("")

    dim_block = "\n".join(dim_info_parts)

    # Print dimension summary directly to the user (counts visible regardless of AI phrasing)
    from rich.table import Table as _Table
    _dim_table = _Table(show_header=True, header_style="bold", box=None, padding=(0, 1))
    _dim_table.add_column("Dimensione", style="cyan", no_wrap=True)
    _dim_table.add_column("Descrizione")
    _dim_table.add_column("Valori", style="dim", justify="right")
    for dim_id, dim_meta in dims.items():
        codelist_id = dim_meta.get("codelist_id")
        description = _get_dimension_description(codelist_id) or dim_id
        n_vals = len(_avail.get(dim_id, []))
        _dim_table.add_row(dim_id, description, str(n_vals) if n_vals else "?")
    console.print("\n[bold]Dimensioni del dataset:[/bold]")
    console.print(_dim_table)
    console.print()

    provider_name = get_provider().get("agency_id", "SDMX")
    system_prompt = (
        f"You are a statistical data assistant for {provider_name}. "
        "Your ONLY task is to help the user choose the right filters for the dataset.\n\n"
        f"Dataset: {ds['df_id']} — {ds['df_description']}\n\n"
        f"Dimensions: {dim_block}\n\n"
        "MANDATORY RULES (no exceptions):\n"
        "1. Always reply in the user's language.\n"
        "2. EVERY TIME you present a dimension to the user, call lookup_actual_values FIRST.\n"
        "   Show the available values with their description BEFORE asking any question about the dimension.\n"
        "   Never ask 'what data type do you want?' without first showing the available values.\n"
        "   The codes returned by lookup_actual_values are the ONLY valid codes.\n"
        "   NEVER use codes from the codelist, memory, or any other source.\n"
        "3. lookup_dimension_values is ONLY for reading the textual meaning of an already validated code.\n"
        "4. Before proposing the final filters, call test_filter_combination with the chosen combination.\n"
        "   If it returns NO DATA, adjust the filters (change AGE, REF_AREA, etc.) and retest.\n"
        "5. Only propose filters that test_filter_combination has confirmed as working.\n"
        "6. When the user confirms (e.g. 'ok', 'go', 'yes', 'perfect', 'proceed'), "
        "   reply ONLY with the summary of chosen filters. Do not ask further questions.\n"
        "7. NEVER discuss downloading, visualizations, or data analysis: "
        "   these are handled by the external CLI. "
        "   If the user asks to download or analyze, tell them to do so after with the CLI.\n"
        "8. Never enter a question loop. If filters are ready and the user has confirmed, stop."
    )

    def test_filter_combination(**kwargs) -> str:
        """Verifica se una combinazione di filtri produce dati reali.
        Passa i filtri come argomenti chiave-valore (es. FREQ='A', AGE='Y15-24', REF_AREA='ITC1').
        IMPORTANTE: controlla che i valori richiesti siano effettivamente presenti nei dati restituiti.
        L'API può restituire dati anche se un filtro è ignorato — questo tool lo rileva."""
        try:
            from .discovery import set_filters
            from .retrieval import get_data
            test_ds = set_filters(ds, **kwargs)
            df = get_data(test_ds, last_n_observations=1)
            if df.is_empty():
                return "NESSUN DATO: la combinazione non produce risultati."
            # Verify each requested value is actually in the returned data
            issues = []
            confirmed = {}
            for col, requested in kwargs.items():
                if col not in df.columns:
                    continue
                actual_vals = sorted(str(v) for v in df[col].unique().to_list() if v is not None)
                confirmed[col] = actual_vals
                req_list = requested if isinstance(requested, list) else [requested]
                missing = [r for r in req_list if str(r) not in actual_vals]
                if missing:
                    issues.append(
                        f"{col}={missing} NON trovato nei dati reali (trovato: {actual_vals})"
                    )
            if issues:
                return (
                    f"FILTRI NON VALIDI: {'; '.join(issues)}. "
                    "Usa i valori effettivamente trovati nei dati."
                )
            return f"OK: {len(df)} righe. Valori confermati nei dati: {confirmed}"
        except Exception as e:
            return f"ERRORE: {e}"

    import warnings
    warnings.filterwarnings("ignore")
    chat = ChatGoogle(model="gemini-2.5-flash", system_prompt=system_prompt)
    chat.register_tool(lookup_actual_values)
    chat.register_tool(lookup_dimension_values)
    chat.register_tool(test_filter_combination)

    import contextlib
    import io

    def _chat(msg: str) -> str:
        with warnings.catch_warnings(), contextlib.redirect_stderr(io.StringIO()):
            warnings.simplefilter("ignore")
            chat.chat(msg, echo="none")
        turn = chat.get_last_turn()
        text = (turn.text or "") if turn is not None else ""
        if not text:
            with warnings.catch_warnings(), contextlib.redirect_stderr(io.StringIO()):
                warnings.simplefilter("ignore")
                chat.chat("Riassumi in testo la situazione e proponi i filtri se sei pronto.", echo="none")
            turn = chat.get_last_turn()
            text = (turn.text or "") if turn is not None else ""
        return text

    # First turn: AI explains the dataset
    ai_text = _chat(
        f"L'utente vuole analizzare: {objective}\n\nSpiega il dataset e cosa si può fare con esso."
    )

    # Multi-turn loop (max 20 turns to avoid infinite loops)
    _max_turns = 20
    _turn = 0
    while _turn < _max_turns:
        _turn += 1
        from rich.markdown import Markdown
        console.print("\n[bold cyan]AI:[/bold cyan]")
        console.print(Markdown(ai_text))
        console.print()

        try:
            user_input = input("Tu: ").strip()
        except (KeyboardInterrupt, EOFError):
            raise SystemExit(0)

        if not user_input:
            continue

        _words = user_input.lower().split()
        _confirm_words = {"sì", "si", "ok", "confermo", "conferma", "yes", "vai", "procedi", "avanti", "perfetto", "esatto", "bene", "andiamo"}
        confirmed = (
            len(_words) <= 3
            and bool(_confirm_words & set(_words))
        )

        ai_text = _chat(user_input)

        if confirmed and ai_text:
            break

    # Ask AI for a final structured summary
    final_text = _chat(
        f"L'utente ha confermato. Elenca i filtri scelti per le dimensioni: {', '.join(dims_list)}. "
        "Per ogni dimensione scrivi DIM=CODICE (usa stringa vuota se nessun filtro). "
        "Poi spiega brevemente il motivo in una riga."
    )

    class FilterItem(BaseModel):
        dimension_id: str
        codes: list[str]  # empty list = no filter; multiple = multi-value

    class FilterResult(BaseModel):
        filters: list[FilterItem]
        reasoning: str

    result = _structured_extract(
        final_text,
        FilterResult,
        f"Estrai i filtri per le dimensioni ({', '.join(dims_list)}) e il reasoning. "
        "Per ogni dimensione senza filtro usa codes=[]. "
        "Se una dimensione ha più valori selezionati, mettili tutti in codes.",
    )
    return {
        "filters": {item.dimension_id: item.codes for item in result.filters},
        "reasoning": result.reasoning,
    }
