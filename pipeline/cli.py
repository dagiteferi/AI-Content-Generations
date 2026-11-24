import shutil
from pathlib import Path
from typing import Annotated, Literal

import typer
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from pipeline.config import Settings
from pipeline.context import StageContext
from pipeline.core.runlog import RunLog
from pipeline.errors import PipelineError
from pipeline.gpu import export_bundle, import_results
from pipeline.models import Storyboard
from pipeline.orchestrator import STAGES, run_stages
from pipeline.providers.gemini import GeminiText
from pipeline.smoke import run_smoke
from pipeline.stages.reference import candidate_path
from pipeline.stages.script import draft_storyboard
from pipeline.storyboard import (
    ensure_consent,
    export_schema,
    load_storyboard,
    missing_consent,
    save_storyboard,
)

app = typer.Typer(help="Heritage Short: storyboard in, film out.", no_args_is_help=True, add_completion=False)
gpu_app = typer.Typer(help="Hand GPU jobs (video, music) to Kaggle and bring results back.", no_args_is_help=True)
app.add_typer(gpu_app, name="gpu")
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


@app.command("approve-reference")
def approve_reference(
    character: Annotated[str, typer.Argument(help="Character id, e.g. grandmother.")],
    seed: Annotated[int, typer.Argument(help="Seed of the candidate to approve.")],
) -> None:
    """Approve a reference candidate as the character's golden reference."""
    settings = Settings()
    storyboard = load_valid_storyboard(settings)
    match = next((c for c in storyboard.characters if c.id == character), None)
    if match is None:
        fail(f"No character '{character}' in storyboard.json")
    candidate = candidate_path(settings.outputs_dir, match, storyboard, seed)
    if not candidate.exists():
        fail(f"No candidate for seed {seed}. Run: heritage run --stage reference")

    target = settings.root / "references" / f"{character}.jpg"
    target.parent.mkdir(exist_ok=True)
    shutil.copy2(candidate, target)
    match.reference_image = str(target.relative_to(settings.root))
    save_storyboard(storyboard, settings.storyboard_path)
    console.print(f"[green]approved[/]  {candidate.name} -> {match.reference_image}")


@gpu_app.command("export")
def gpu_export(
    kind: Annotated[Literal["shots", "music"], typer.Argument(help="Which jobs to export.")],
    all_jobs: Annotated[bool, typer.Option("--all", help="Include jobs whose output already exists.")] = False,
) -> None:
    """Write a job bundle (zip) to upload to Kaggle as a dataset."""
    settings = Settings()
    archive, count = export_bundle(settings, load_valid_storyboard(settings), kind, all_jobs)
    console.print(f"[green]exported[/]  {count} {kind} job(s) -> {archive.relative_to(settings.root)}")
    console.print("  next: upload it to Kaggle and follow kaggle/README.md")


@gpu_app.command("import")
def gpu_import(
    source: Annotated[Path, typer.Argument(help="out.zip or folder downloaded from the notebook.")],
) -> None:
    """Import finished GPU outputs as cache hits and log them to runs.jsonl."""
    settings = Settings()
    if not source.exists():
        fail(f"{source} not found")
    summary = import_results(settings, load_valid_storyboard(settings), source, RunLog(settings.runs_path))
    for label, items, style in (
        ("imported", summary.imported, "green"),
        ("already present", summary.already_present, "dim"),
        ("failed on GPU", summary.failed, "red"),
        ("stale (storyboard changed)", summary.stale, "yellow"),
    ):
        if items:
            console.print(f"  [{style}]{label}:[/] {', '.join(items)}")


def main() -> None:
    try:
        app()
    except PipelineError as error:
        console.print(f"[red]error:[/] {error}")
        raise SystemExit(1) from None
