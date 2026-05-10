#!/usr/bin/env python3
"""
pma — Postmortem Memory Agent CLI

  pma ingest <file.md>          Ingest a postmortem, generate artifacts
  pma ingest <dir/>             Ingest all .md files in a directory
  pma review <diff.patch>       Review a PR diff — SAFE / NEEDS REVIEW / BLOCK
  pma query  "<alert text>"     Semantic search over incident memory
  pma memory                    List all stored incidents
  pma clear                     Wipe memory (with confirmation)
"""

import sys
from pathlib import Path

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
from rich import box

load_dotenv()
console = Console()


# ── helpers ───────────────────────────────────────────────────────────────────

def _require_api_key():
    import os
    if not os.environ.get("ANTHROPIC_API_KEY"):
        console.print("[red]Error:[/red] ANTHROPIC_API_KEY not set.")
        console.print("  export ANTHROPIC_API_KEY=sk-ant-...")
        sys.exit(1)


def _severity_color(sev: str) -> str:
    return {"SEV-1": "red", "SEV-2": "yellow", "SEV-3": "cyan", "SEV-4": "green"}.get(sev, "white")


# ── commands ──────────────────────────────────────────────────────────────────

@click.group()
@click.version_option("0.1.0", prog_name="pma")
def main():
    """Postmortem Memory Agent — semantic memory for incident responders."""
    pass


@main.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--no-artifacts", is_flag=True, help="Skip artifact generation.")
def ingest(path: str, no_artifacts: bool):
    """Ingest a postmortem file or a directory of .md files."""
    _require_api_key()

    from agent.parser import parse_postmortem
    from agent.memory import store, count
    from agent.artifact_generator import generate_all, save_artifacts

    p = Path(path)
    files = sorted(p.glob("*.md")) if p.is_dir() else [p]

    if not files:
        console.print("[yellow]No .md files found.[/yellow]")
        return

    for f in files:
        console.print(f"\n[bold]Ingesting:[/bold] {f.name}")
        with console.status("Parsing with Claude..."):
            chunk = parse_postmortem(f.read_text())
            store(chunk)

        sev_color = _severity_color(chunk.severity)
        console.print(f"  [green]✓[/green] [{sev_color}]{chunk.severity}[/{sev_color}] {chunk.component} — {chunk.date}")
        console.print(f"  [dim]Root cause:[/dim] {chunk.root_cause}")
        console.print(f"  [dim]Tags:[/dim] {', '.join(chunk.tags)}")

        if not no_artifacts:
            with console.status("Generating artifacts..."):
                artifacts = generate_all(chunk)
                saved = save_artifacts(chunk, artifacts)

            console.print(f"  [green]✓[/green] Artifacts → [bold]generated/[/bold]")
            for name in saved:
                console.print(f"    [dim]{name}[/dim]")

    total = count()
    console.print(f"\n[green]Memory:[/green] {total} incident{'s' if total != 1 else ''} stored")


@main.command()
@click.argument("diff_file", type=click.Path(exists=True))
def review(diff_file: str):
    """Review a PR diff for incident risk. Returns SAFE / NEEDS REVIEW / BLOCK."""
    _require_api_key()

    from agent.memory import count
    from agent.router import route

    if count() == 0:
        console.print("[yellow]Warning:[/yellow] Memory is empty — run [bold]pma ingest[/bold] first for grounded analysis.")

    diff = Path(diff_file).read_text()

    with console.status("Searching memory + analyzing diff..."):
        result = route(diff)

    decision = result["decision"]
    score = result["risk_score"]

    if decision == "safe":
        style, icon = "green", "✅"
    elif decision == "needs-review":
        style, icon = "yellow", "⚠️"
    else:
        style, icon = "red", "🚫"

    label = result["decision_label"].split("—", 1)[-1].strip()
    console.print(Panel(
        f"[bold {style}]{icon}  {result['decision_label']}[/bold {style}]",
        subtitle=f"Risk score: {score}/10",
        border_style=style,
    ))

    if result["matched_incidents"]:
        console.print("\n[bold]Matched past incidents:[/bold]")
        for c in result["matched_incidents"]:
            sev_color = _severity_color(c.severity)
            console.print(f"  • [{sev_color}]{c.severity}[/{sev_color}] [bold]{c.component}[/bold] ({c.date})")
            console.print(f"    [dim]{c.raw_summary}[/dim]")

    if result["warnings"]:
        console.print("\n[bold]Warnings:[/bold]")
        for w in result["warnings"]:
            console.print(f"  [yellow]•[/yellow] {w}")

    if result["recommendation"]:
        console.print(f"\n[bold]Recommendation:[/bold]")
        console.print(f"  {result['recommendation']}")


@main.command()
@click.argument("alert_text")
@click.option("-k", "--top-k", default=3, show_default=True, help="Number of results to return.")
def query(alert_text: str, top_k: int):
    """Semantic search over incident memory with an alert or description."""
    _require_api_key()

    from agent.memory import query as mem_query

    with console.status("Searching memory..."):
        chunks = mem_query(alert_text, top_k=top_k)

    if not chunks:
        console.print("[yellow]No incidents in memory.[/yellow] Run [bold]pma ingest[/bold] first.")
        return

    console.print(f"\n[bold]Top {len(chunks)} relevant incident{'s' if len(chunks) != 1 else ''}:[/bold]\n")
    for i, c in enumerate(chunks, 1):
        sev_color = _severity_color(c.severity)
        console.print(f"  [bold]{i}.[/bold] [{sev_color}]{c.severity}[/{sev_color}] [bold]{c.component}[/bold] — {c.date}")
        console.print(f"     [dim]Root cause:[/dim]  {c.root_cause}")
        console.print(f"     [dim]Fix:[/dim]          {c.fix_pattern}")
        console.print(f"     [dim]Detection:[/dim]    {c.detection_signal}")
        console.print(f"     [dim]Tags:[/dim]         {', '.join(c.tags)}")
        if i < len(chunks):
            console.print()


@main.command(name="memory")
def list_memory():
    """List all stored incidents."""
    from agent.memory import all_chunks, count

    chunks = all_chunks()
    n = count()
    if n == 0:
        console.print("[yellow]Memory is empty.[/yellow] Run [bold]pma ingest <file.md>[/bold] to add incidents.")
        return

    table = Table(box=box.SIMPLE, show_header=True, header_style="bold")
    table.add_column("SEV", style="bold", width=6)
    table.add_column("Component", min_width=20)
    table.add_column("Date", width=12)
    table.add_column("Root Cause")
    table.add_column("Tags", style="dim")

    for c in sorted(chunks, key=lambda x: x.date, reverse=True):
        sev_color = _severity_color(c.severity)
        table.add_row(
            f"[{sev_color}]{c.severity}[/{sev_color}]",
            c.component,
            c.date,
            c.root_cause[:70] + "…" if len(c.root_cause) > 70 else c.root_cause,
            ", ".join(c.tags[:4]),
        )

    token_stored = n * 150
    token_full = n * 2000
    console.print(table)
    console.print(
        f"[dim]{n} incidents · ~{token_stored:,} tokens stored "
        f"(vs ~{token_full:,} for full docs — {token_full // token_stored}× compression)[/dim]"
    )


@main.command()
@click.confirmation_option(prompt="This will wipe all stored incidents. Continue?")
def clear():
    """Wipe all incident memory."""
    import shutil
    from agent.memory import CHROMA_PATH, MEMORY_JSON

    shutil.rmtree(CHROMA_PATH, ignore_errors=True)
    if MEMORY_JSON.exists():
        MEMORY_JSON.unlink()

    # Reset the module-level singleton
    import agent.memory as _mem
    _mem._collection = None

    console.print("[green]✓[/green] Memory cleared.")


if __name__ == "__main__":
    main()
