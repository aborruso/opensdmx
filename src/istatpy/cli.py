"""CLI for istatpy — ISTAT SDMX REST API."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

_HELP_FLAGS = {"--help", "-h"}

import httpx
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .base import _RATE_LIMIT_FILE, get_base_url

app = typer.Typer(help="istatpy — ISTAT SDMX REST API CLI")
console = Console()
err_console = Console(stderr=True)


def _check_api_reachable() -> None:
    """If no rate-limit log exists, do a lightweight HEAD check on the API."""
    if _RATE_LIMIT_FILE.exists():
        return
    try:
        with httpx.Client(timeout=5.0) as client:
            client.head(get_base_url())
    except (httpx.ConnectTimeout, httpx.NetworkError):
        err_console.print(
            "[red]⚠ ISTAT API unreachable.[/red] "
            "Your IP may be blocked (rate limit: max 5 req/min). "
            "The block can last 1-2 days."
        )
        raise typer.Exit(1)


@app.callback(invoke_without_command=True)
def _startup(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is not None and not _HELP_FLAGS.intersection(sys.argv):
        _check_api_reachable()


@app.command()
def search(
    keyword: str = typer.Argument(..., help="Keyword to search in dataset descriptions"),
    semantic: bool = typer.Option(False, "--semantic", "-s", help="Use semantic search via Ollama embeddings"),
    n: int = typer.Option(10, "--n", help="Number of results (semantic mode only)"),
):
    """Search datasets by keyword (or semantically with --semantic)."""
    if semantic:
        from .embed import semantic_search
        try:
            df = semantic_search(keyword, n=n)
        except FileNotFoundError as e:
            err_console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)
        except Exception as e:
            err_console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)

        table = Table(title=f"Semantic search: {keyword}", show_lines=False)
        table.add_column("df_id", style="cyan", no_wrap=True)
        table.add_column("df_description")
        table.add_column("score", style="dim")

        for row in df.iter_rows(named=True):
            table.add_row(row["df_id"], row["df_description"] or "", f"{row['score']:.3f}")

        console.print(table)
        return

    from . import search_dataset
    try:
        df = search_dataset(keyword)
    except Exception as e:
        err_console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    if df.is_empty():
        err_console.print(f"[yellow]No datasets found for:[/yellow] {keyword}")
        raise typer.Exit(1)

    table = Table(title=f"Search: {keyword}", show_lines=False)
    table.add_column("df_id", style="cyan", no_wrap=True)
    table.add_column("df_description")

    for row in df.iter_rows(named=True):
        table.add_row(row["df_id"], row["df_description"] or "")

    console.print(table)


@app.command()
def info(dataset_id: str = typer.Argument(..., help="Dataset ID (e.g. 139_176)")):
    """Show metadata and dimensions for a dataset."""
    from . import dimensions_info, istat_dataset
    try:
        ds = istat_dataset(dataset_id)
    except Exception as e:
        err_console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    meta = (
        f"ID:          {ds['df_id']}\n"
        f"Version:     {ds['version']}\n"
        f"Description: {ds['df_description']}\n"
        f"Structure:   {ds['df_structure_id']}"
    )
    console.print(Panel(meta, title="Dataset Info", expand=False))

    try:
        dim_df = dimensions_info(ds)
    except Exception as e:
        err_console.print(f"[yellow]Warning:[/yellow] could not fetch dimension info: {e}")
        return

    if dim_df.is_empty():
        console.print("[yellow]No dimensions found.[/yellow]")
        return

    table = Table(title="Dimensions", show_lines=False)
    table.add_column("dimension_id", style="cyan", no_wrap=True)
    table.add_column("position")
    table.add_column("codelist_id")
    table.add_column("description")

    for row in dim_df.iter_rows(named=True):
        table.add_row(
            row["dimension_id"],
            str(row["position"]) if row["position"] is not None else "",
            row["codelist_id"] or "",
            row.get("description") or "",
        )

    console.print(table)


@app.command()
def values(
    dataset_id: str = typer.Argument(..., help="Dataset ID"),
    dim: str = typer.Argument(..., help="Dimension ID (e.g. FREQ)"),
):
    """Show available values for a dimension."""
    from . import get_dimension_values, istat_dataset
    try:
        ds = istat_dataset(dataset_id)
        val_df = get_dimension_values(ds, dim)
    except Exception as e:
        err_console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    if val_df.is_empty():
        err_console.print(f"[yellow]No values found for dimension:[/yellow] {dim}")
        raise typer.Exit(1)

    table = Table(title=f"{dataset_id} / {dim}", show_lines=False)
    table.add_column("id", style="cyan", no_wrap=True)
    table.add_column("name")

    for row in val_df.iter_rows(named=True):
        table.add_row(row["id"] or "", row["name"] or "")

    console.print(table)


@app.command()
def embed():
    """Build semantic embeddings cache for the dataset catalog."""
    from .embed import build_embeddings
    try:
        build_embeddings(progress=True)
    except Exception as e:
        err_console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def get(
    ctx: typer.Context,
    dataset_id: str = typer.Argument(..., help="Dataset ID"),
    out: Optional[Path] = typer.Option(None, "--out", help="Output file (.csv/.parquet/.json)"),
):
    """Get data for a dataset. Extra --DIM VALUE pairs are used as filters."""
    from . import get_data, istat_dataset, set_filters

    # Parse extra args as --KEY VALUE pairs
    extra = ctx.args
    filters = {}
    i = 0
    while i < len(extra):
        arg = extra[i]
        if arg.startswith("--") and i + 1 < len(extra):
            key = arg[2:]
            filters[key] = extra[i + 1]
            i += 2
        else:
            err_console.print(f"[red]Unexpected argument:[/red] {arg}")
            raise typer.Exit(1)

    try:
        ds = istat_dataset(dataset_id)
        if filters:
            ds = set_filters(ds, **filters)
        df = get_data(ds)
    except Exception as e:
        err_console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    if out is None:
        # Write CSV to stdout
        sys.stdout.write(df.write_csv())
    else:
        suffix = out.suffix.lower()
        if suffix == ".parquet":
            df.write_parquet(out)
        elif suffix == ".json":
            df.write_ndjson(out)
        else:
            df.write_csv(out)
        console.print(f"[green]Saved:[/green] {out}")


@app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def plot(
    ctx: typer.Context,
    dataset_id: str = typer.Argument(..., help="Dataset ID"),
    x: str = typer.Option("TIME_PERIOD", "--x", help="Column for X axis"),
    y: str = typer.Option("OBS_VALUE", "--y", help="Column for Y axis"),
    color: Optional[str] = typer.Option(None, "--color", help="Column for color grouping"),
    title: Optional[str] = typer.Option(None, "--title", help="Chart title (default: dataset description)"),
    xlabel: Optional[str] = typer.Option(None, "--xlabel", help="X axis label (default: column name)"),
    ylabel: Optional[str] = typer.Option(None, "--ylabel", help="Y axis label (default: column name)"),
    out: Path = typer.Option(Path("chart.png"), "--out", help="Output file (.png/.pdf/.svg)"),
    width: float = typer.Option(10.0, "--width", help="Chart width in inches"),
    height: float = typer.Option(5.0, "--height", help="Chart height in inches"),
):
    """Plot data for a dataset as a line chart. Extra --DIM VALUE pairs are used as filters."""
    from plotnine import aes, geom_line, geom_point, ggplot, labs, scale_x_date, theme_minimal

    import polars as pl

    from . import get_data, istat_dataset, set_filters

    # Parse extra args as --KEY VALUE filters (same as get)
    extra = ctx.args
    filters = {}
    i = 0
    while i < len(extra):
        arg = extra[i]
        if arg.startswith("--") and i + 1 < len(extra):
            key = arg[2:]
            filters[key] = extra[i + 1]
            i += 2
        else:
            err_console.print(f"[red]Unexpected argument:[/red] {arg}")
            raise typer.Exit(1)

    try:
        ds = istat_dataset(dataset_id)
        if filters:
            ds = set_filters(ds, **filters)
        df = get_data(ds)
    except Exception as e:
        err_console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    if x not in df.columns or y not in df.columns:
        err_console.print(f"[red]Error:[/red] columns '{x}' or '{y}' not found in data.")
        err_console.print(f"Available columns: {', '.join(df.columns)}")
        raise typer.Exit(1)

    df = df.with_columns(pl.col(y).cast(pl.Float64, strict=False))
    pdf = df.to_pandas()

    aes_mapping = aes(x=x, y=y, color=color) if color else aes(x=x, y=y)
    p = (
        ggplot(pdf, aes_mapping)
        + geom_line(size=1)
        + geom_point(size=1.5)
        + labs(
            title=title or ds["df_description"],
            x=xlabel or x,
            y=ylabel or y,
            caption="Source: ISTAT",
        )
        + theme_minimal()
    )

    # Add date scale if x column is a date
    if hasattr(pdf[x], "dt"):
        p = p + scale_x_date(date_breaks="2 years", date_labels="%Y")

    p.save(str(out), dpi=150, width=width, height=height)
    console.print(f"[green]Saved:[/green] {out}")


@app.command()
def wizard():
    """Interactive wizard to discover, explore and download ISTAT datasets."""
    import questionary
    from .base import get_agency_id, get_base_url
    from .discovery import get_dimension_values, istat_dataset
    from .embed import semantic_search

    # Step 1: query
    query = questionary.text("Search query (in any language):").ask()
    if not query:
        raise typer.Exit(0)

    # Step 2: paginated dataset selection
    page = 0
    page_size = 10
    df_results = None
    selected_id = None

    while True:
        if df_results is None:
            try:
                df_results = semantic_search(query, n=100)
            except FileNotFoundError:
                err_console.print("[red]Embeddings cache not found. Run: istatpy embed[/red]")
                raise typer.Exit(1)

        slice_ = df_results.slice(page * page_size, page_size)
        if slice_.is_empty():
            page = max(0, page - 1)
            continue

        total = len(df_results)
        choices = [
            questionary.Choice(
                title=f"{row['df_id']:<40} {row['df_description'] or ''}  ({row['score']:.3f})",
                value=row["df_id"],
            )
            for row in slice_.iter_rows(named=True)
        ]
        if page > 0:
            choices.insert(0, questionary.Choice(title="← Previous 10", value="__prev__"))
        if (page + 1) * page_size < total:
            shown_end = min((page + 1) * page_size, total)
            choices.append(questionary.Choice(
                title=f"→ Next 10  ({page * page_size + 1}–{shown_end} of {total})",
                value="__next__",
            ))
        choices.append(questionary.Choice(title="✕ Cancel", value="__cancel__"))

        answer = questionary.select(
            f"Select a dataset  (page {page + 1}):", choices=choices
        ).ask()

        if answer is None or answer == "__cancel__":
            raise typer.Exit(0)
        elif answer == "__next__":
            page += 1
        elif answer == "__prev__":
            page -= 1
        else:
            selected_id = answer
            break

    # Step 3: load dataset info (from SQLite cache if available)
    console.print(f"\n[cyan]Loading dataset[/cyan] [bold]{selected_id}[/bold]...")
    try:
        ds = istat_dataset(selected_id)
    except Exception as e:
        err_console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    console.print(Panel(
        f"ID:          {ds['df_id']}\n"
        f"Description: {ds['df_description']}\n"
        f"Structure:   {ds['df_structure_id']}\n"
        f"Dimensions:  {', '.join(ds['dimensions'].keys())}",
        title="Dataset",
        expand=False,
    ))

    dims = ds["dimensions"]
    if not dims:
        err_console.print("[yellow]No dimensions found.[/yellow]")
        raise typer.Exit(1)

    # Step 4: for each dimension, load values and let user pick (or skip with "all")
    filters = {}
    for dim_id, dim_info in dims.items():
        console.print(f"\n[cyan]Loading values for[/cyan] [bold]{dim_id}[/bold]"
                      f"[dim]  ({dim_info.get('codelist_id', '')})[/dim]...")
        try:
            val_df = get_dimension_values(ds, dim_id)
        except Exception as e:
            err_console.print(f"[yellow]Warning:[/yellow] could not load {dim_id}: {e}")
            continue

        # Auto-select if df_id matches a value in this dimension
        ids = val_df["id"].to_list()
        if ds["df_id"] in ids:
            filters[dim_id] = ds["df_id"]
            console.print(f"[dim]  → auto-selected {ds['df_id']}[/dim]")
            continue

        from InquirerPy import inquirer
        from InquirerPy.base.control import Choice as IChoice

        val_choices = [IChoice(value="", name="(all)  — no filter")] + [
            IChoice(value=row["id"], name=f"{row['id']}  {row['name'] or ''}")
            for row in val_df.iter_rows(named=True)
        ]

        chosen = inquirer.fuzzy(
            message=f"{dim_id}:",
            choices=val_choices,
            default=None,
            max_height="40%",
            instruction="(type to filter · ↑↓ navigate · PgUp/PgDn scroll · Enter confirm)",
        ).execute()

        if chosen is None:
            raise typer.Exit(0)
        if chosen:
            filters[dim_id] = chosen

    # Step 5: build SDMX URL
    key_parts = [filters.get(dim_id, "") for dim_id in dims]
    key = ".".join(key_parts)

    base = get_base_url()
    agency = get_agency_id()
    version = ds["version"]
    url = f"{base}/data/{agency},{ds['df_id']},{version}/{key}?format=csv"

    active = {k: v for k, v in filters.items() if v}
    filter_summary = "\n".join(f"  {k} = {v}" for k, v in active.items()) if active else "  (none — full dataset)"

    console.print(Panel(
        f"[bold]Dataset:[/bold]\n  {ds['df_id']}  {ds['df_description']}\n\n"
        f"[bold]Filters:[/bold]\n{filter_summary}\n\n"
        f"[bold]URL:[/bold]\n{url}\n\n"
        f"[bold]Download:[/bold]\ncurl -s \"{url}\" -o data.csv",
        title="Download",
        expand=False,
    ))


def main():
    app()
