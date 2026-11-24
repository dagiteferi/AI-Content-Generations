from dataclasses import dataclass
from pathlib import Path

from rich.console import Console

from pipeline.config import Settings
from pipeline.core.runlog import RunLog
from pipeline.models import Shot, Storyboard

STATUS_STYLES = {
    "cached": "dim",
    "generated": "green",
    "would generate": "yellow",
    "fallback": "magenta",
    "skipped": "dim",
}


@dataclass
class StageContext:
    storyboard: Storyboard
    settings: Settings
    log: RunLog
    console: Console
    shot_id: str | None = None
    force: bool = False
    dry_run: bool = False

    def selected_shots(self) -> list[Shot]:
        if self.shot_id is None:
            return list(self.storyboard.shots)
        return [self.storyboard.shot(self.shot_id)]

    def stage_dir(self, stage: str) -> Path:
        path = self.settings.outputs_dir / stage
        path.mkdir(parents=True, exist_ok=True)
        return path

    def status(self, item: str, state: str, path: Path | None = None, note: str = "") -> None:
        style = STATUS_STYLES.get(state, "")
        location = f"  {path.relative_to(self.settings.root)}" if path else ""
        self.console.print(f"  {item:<6} [{style}]{state:<15}[/]{location}  {note}".rstrip())
