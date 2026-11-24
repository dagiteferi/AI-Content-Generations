from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from pipeline.config import Settings
from pipeline.context import StageContext
from pipeline.core.runlog import RunLog
from pipeline.errors import PipelineError
from pipeline.models import Storyboard
from pipeline.orchestrator import STAGES, run_stages
from pipeline.providers.gemini import GeminiText
from pipeline.smoke import run_smoke
from pipeline.stages.script import draft_storyboard
from pipeline.storyboard import (
    ensure_consent,
    export_schema,
    load_storyboard,
    missing_consent,
    save_storyboard,
)

app = typer.Typer(help="Heritage Short: storyboard in, film out.", no_args_is_help=True, add_completion=False)
console = Console()


def fail(message: str) -> None:
    console.print(f"[red]error:[/] {message}")
    raise typer.Exit(code=1)


def load_valid_storyboard(settings: Settings) -> Storyboard:
    path = settings.storyboard_path
    if not path.exists():
        fail(f"{path.name} not found. Draft one with: heritage draft")
    try:
        storyboard = load_storyboard(path)
    except ValidationError as error:
        fail(f"{path.name} is invalid:\n{error}")
    ensure_consent(storyboard, settings.ethics_path)
    return storyboard


@app.command()
def validate() -> None:
    """Validate storyboard.json against the schema and the consent records."""
    storyboard = load_valid_storyboard(Settings())
    console.print(
        f"[green]valid[/]  {storyboard.title!r}: {len(storyboard.shots)} shots, "
        f"{storyboard.planned_duration_s:.1f}s planned"
    )


@app.command()
def schema() -> None:
    """Export the storyboard JSON Schema from the data models."""
    settings = Settings()
    export_schema(settings.schema_path)
    console.print(f"wrote {settings.schema_path.relative_to(settings.root)}")


@app.command()
def smoke() -> None:
    """Call every provider once and log its latency to runs.jsonl."""
    settings = Settings()
    results = run_smoke(settings, RunLog(settings.runs_path))

    table = Table(title="Smoke test", show_edge=False)
    for column in ("Check", "Model", "Result", "Latency", "Detail"):
        table.add_column(column)
    for result in results:
        mark = "[green]ok[/]" if result.ok else "[red]fail[/]"
        table.add_row(result.name, result.model, mark, f"{result.latency_s:.2f}s", result.detail)
    console.print(table)

    if not all(result.ok for result in results):
        raise typer.Exit(code=1)


@app.command()
def draft(
    brief: Annotated[Path, typer.Option(help="Story brief to turn into a storyboard.")] = Path("story.md"),
    force: Annotated[bool, typer.Option(help="Overwrite an existing storyboard.json.")] = False,
) -> None:
    """Draft storyboard.json from a story brief with Gemini."""
    settings = Settings()
    if not brief.exists():
        fail(f"{brief} not found")
    text = brief.read_text(encoding="utf-8")
    if "TODO" in text:
        fail(f"Fill in the TODOs in {brief} first")
    if settings.storyboard_path.exists() and settings.storyboard_path.read_text().strip() not in ("", "{}") and not force:
        fail("storyboard.json already exists. Use --force to overwrite it.")

    model = GeminiText(settings.secret("gemini_api_key"), settings.text_model)
    with console.status("Drafting storyboard..."):
        storyboard = draft_storyboard(text, model, RunLog(settings.runs_path), settings.max_attempts)

    save_storyboard(storyboard, settings.storyboard_path)
    console.print(
        f"[green]drafted[/]  {len(storyboard.shots)} shots, "
        f"{storyboard.planned_duration_s:.1f}s -> storyboard.json"
    )
    for character_id in missing_consent(storyboard, settings.ethics_path):
        console.print(f"[yellow]consent needed[/] for '{character_id}' in ETHICS.md before generating")


@app.command()
def run(
    stage: Annotated[list[str] | None, typer.Option(help=f"Stage(s) to run: {', '.join(STAGES)}.")] = None,
    shot: Annotated[str | None, typer.Option(help="Only this shot, e.g. s03.")] = None,
    force: Annotated[bool, typer.Option(help="Ignore the cache.")] = False,
    dry_run: Annotated[bool, typer.Option(help="Show what would run without calling any model.")] = False,
) -> None:
    """Run the pipeline. Cached outputs are reused, so only what changed is regenerated."""
    settings = Settings()
    storyboard = load_valid_storyboard(settings)
    if shot is not None:
        try:
            storyboard.shot(shot)
        except KeyError as error:
            fail(str(error))

    ctx = StageContext(
        storyboard=storyboard,
        settings=settings,
        log=RunLog(settings.runs_path),
        console=console,
        shot_id=shot,
        force=force,
        dry_run=dry_run,
    )
    try:
        run_stages(ctx, stage)
    except ValueError as error:
        fail(str(error))
    console.print(f"[dim]run {ctx.log.run_id} logged to runs.jsonl[/]")


def main() -> None:
    try:
        app()
    except PipelineError as error:
        console.print(f"[red]error:[/] {error}")
        raise SystemExit(1) from None
