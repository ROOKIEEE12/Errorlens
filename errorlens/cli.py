from __future__ import annotations
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

from . import __version__
from .core.analyze import analyze_text
from .core.llm import enrich
from .core.ocr import IMAGE_EXT, OCRUnavailable, ocr_image
from .core.redact import redact as redact_text
from .core.report import render
from .storage import sqlite as store

app = typer.Typer(help="ErrorLens — local-first debugging assistant for build logs, tracebacks and screenshots.", no_args_is_help=True)
console = Console()
RISK_COLOR = {"low": "green", "medium": "yellow", "high": "red", "critical": "bold red"}


def _read(path: Optional[Path], show_ocr: bool = False) -> str:
    if path is None or str(path) == "-":
        if sys.stdin.isatty():
            console.print("[red]Provide a file or pipe a log via stdin.[/red]")
            raise typer.Exit(2)
        return sys.stdin.read()
    if not path.exists():
        console.print(f"[red]File not found:[/red] {path}")
        raise typer.Exit(2)
    if path.suffix.lower() in IMAGE_EXT:
        try:
            text = ocr_image(path.read_bytes())
        except OCRUnavailable as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(2)
        if show_ocr:
            console.print(Panel(text, title="OCR text (check for recognition mistakes)", border_style="dim"))
        return text
    return path.read_text(errors="replace")


@app.command()
def analyze(
    file: Optional[Path] = typer.Argument(None, help="Log file, screenshot (.png/.jpg), or '-' / pipe for stdin"),
    json_out: bool = typer.Option(False, "--json", help="Machine-readable output"),
    no_save: bool = typer.Option(False, "--no-save", help="Do not record this in local history"),
    repo: Optional[Path] = typer.Option(None, "--repo", help="Project folder: enables a verified diff for import errors"),
    ai: bool = typer.Option(False, "--ai", help="Add an LLM explanation (sends only redacted, structured facts; needs ANTHROPIC_API_KEY)"),
    show_ocr: bool = typer.Option(False, "--show-ocr", help="Print OCR text for screenshots"),
):
    """Find the root cause in a build log, traceback or screenshot."""
    d = analyze_text(_read(file, show_ocr), repo=repo)
    seen = None if no_save else store.record(d)
    d.related = store.related(d.error_type, d.fingerprint)
    if ai:
        d.ai = enrich(d)
        if d.ai is None:
            console.print("[yellow]AI explanation unavailable (set ANTHROPIC_API_KEY). Showing deterministic result.[/yellow]")
    if json_out:
        typer.echo(d.model_dump_json(indent=2))
        return

    c = d.context
    console.print(f"[bold]ErrorLens v{__version__}[/bold]")
    console.print(f"Detected: {c.framework} · {c.platform}" + (f" · {c.package_manager}" if c.package_manager else ""))
    console.print(f"Fingerprint: [cyan]{d.fingerprint}[/cyan]   Confidence: {int(d.confidence * 100)}%")
    if seen and seen["count"] > 1:
        console.print(f"[yellow]Recurring:[/yellow] seen {seen['count']}x · first {seen['first_seen']} · last {seen['last_seen']}")
        if seen["resolution"]:
            console.print(f"[green]Known resolution:[/green] {seen['resolution']}")
    console.print()
    console.print(Panel(d.root_cause, title=d.title, border_style="red"))
    if d.suspected_file:
        f = d.suspected_file
        console.print(f"[bold]Likely location:[/bold] {f.path}" + (f":{f.line}" if f.line else "") + f"  ({int(f.confidence*100)}%)")
    console.print("\n[bold]Evidence:[/bold]")
    for e in d.evidence:
        console.print(f"  [dim][{e.line}][/dim] {e.text}")
    if d.cascade:
        console.print("\n[dim]Cascade (consequences, not causes):[/dim]")
        for e in d.cascade[:3]:
            console.print(f"  [dim][{e.line}] {e.text}[/dim]")
    console.print("\n[bold]Fix:[/bold]")
    for n, s in enumerate(d.fix_steps, 1):
        console.print(f"  {n}. {s}")
    if d.suggested_diff:
        console.print(f"\n[bold]Suggested diff[/bold] [dim]({d.diff_note})[/dim]")
        console.print(Syntax(d.suggested_diff, "diff", theme="ansi_dark"))
    elif d.diff_note:
        console.print(f"\n[dim]{d.diff_note}[/dim]")
    if d.verification_commands:
        console.print("\n[bold]Verify:[/bold]")
        for v in d.verification_commands:
            console.print(f"  $ {v}")
    col = RISK_COLOR[d.risk.level]
    console.print(f"\n[bold]Risk:[/bold] [{col}]{d.risk.level.upper()}[/{col}] — {d.risk.reason}")
    if d.ai:
        console.print(Panel(f"{d.ai.explanation_en}\n\n{d.ai.explanation_hi}", title="AI explanation (from redacted facts only)", border_style="blue"))
        for h in d.ai.alternative_hypotheses:
            console.print(f"  • maybe: {h}")
    if d.related:
        console.print("\n[bold]Related past issues:[/bold]")
        for r in d.related:
            console.print(f"  [cyan]{r['fingerprint']}[/cyan] {r['count']}x {r['title']}" + (f" — [green]{r['resolution']}[/green]" if r["resolution"] else ""))
    if d.redaction_summary:
        n = sum(d.redaction_summary.values())
        console.print(f"\n[green]Security scan:[/green] {n} sensitive value(s) redacted ({', '.join(d.redaction_summary)}). Raw log not stored.")


@app.command("redact")
def redact_cmd(file: Path, output: Optional[Path] = typer.Option(None, "--output", "-o")):
    """Write a copy of a log with secrets removed."""
    safe, counts = redact_text(file.read_text(errors="replace"))
    if output:
        output.write_text(safe)
        console.print(f"Wrote {output} — redacted: {counts or 'nothing found'}")
    else:
        typer.echo(safe)


@app.command()
def fingerprint(file: Path):
    """Print only the fingerprint ID for a log."""
    typer.echo(analyze_text(_read(file)).fingerprint)


@app.command()
def report(
    file: Path,
    fmt: str = typer.Option("markdown", "--format", "-f", help="markdown | github | json | text"),
    output: Optional[Path] = typer.Option(None, "--output", "-o"),
    repo: Optional[Path] = typer.Option(None, "--repo"),
):
    """Generate a share-safe report (secrets removed)."""
    try:
        out = render(analyze_text(_read(file), repo=repo), fmt)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(2)
    if output:
        output.write_text(out)
        console.print(f"Wrote {output}")
    else:
        typer.echo(out)


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8000):
    """Start the local API (used by the web UI)."""
    try:
        import uvicorn
    except ImportError:
        console.print("[red]Install the API extras: pip install 'errorlens[api]'[/red]")
        raise typer.Exit(2)
    uvicorn.run("errorlens.api.main:app", host=host, port=port)


history_app = typer.Typer(help="Local incident history.", no_args_is_help=True)
app.add_typer(history_app, name="history")


def _table(rows):
    if not rows:
        console.print("[dim]No incidents found.[/dim]")
    for r in rows:
        tag = " [green]✓ resolved[/green]" if r["resolution"] else ""
        console.print(f"[cyan]{r['fingerprint']}[/cyan]  {r['count']}x  {r['last_seen']}  {r['title']}{tag}")


@history_app.command("list")
def history_list(limit: int = 20):
    """Recent incidents."""
    _table(store.recent(limit))


@history_app.command("search")
def history_search(query: str):
    """Search past incidents."""
    _table(store.search(query))


@history_app.command("resolve")
def history_resolve(fingerprint: str, note: str):
    """Attach a known resolution to a fingerprint."""
    console.print("Saved." if store.resolve(fingerprint, note) else "[red]Fingerprint not found.[/red]")


if __name__ == "__main__":
    app()
