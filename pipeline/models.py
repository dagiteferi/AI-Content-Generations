from __future__ import annotations

from collections import Counter
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

MIN_SHOTS, MAX_SHOTS = 8, 12
MIN_FILM_S, MAX_FILM_S = 60.0, 90.0

DEFAULT_TTS_MODEL = "gemini-3.8-flash-tts"
DEFAULT_IMAGE_MODEL = "@cf/black-forest-labs/flux-2-klein-4b"
DEFAULT_VIDEO_MODEL = "wan2.2-ti2v-5b"
DEFAULT_MUSIC_MODEL = "ace-step-1.5"

ShotSize = Literal[
    "extreme-wide",
    "wide",
    "medium",
    "medium-close-up",
    "close-up",
    "extreme-close-up",
    "insert",
]
Fallback = Literal["kenburns", "still", "none"]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Character(Contract):
    id: str = Field(pattern=r"^[a-z0-9_-]+$")
    description: str = Field(min_length=10)
    reference_image: str | None = None
    real_person: bool = False
    consent_ref: str | None = Field(
        default=None,
        description="Identifier of this person's consent record in ETHICS.md.",
    )
    reference_seeds: list[int] = Field(default_factory=lambda: [11, 12, 13, 14], min_length=1, max_length=8)


class Voice(Contract):
    model: str = DEFAULT_TTS_MODEL
    voice_name: str = "Sulafat"
    style: str = "calm, warm and unhurried"


class MusicCue(Contract):
    id: str
    start_s: float = Field(ge=0)
    end_s: float = Field(gt=0)
    caption: str
    bpm: int | None = Field(default=None, ge=40, le=200)
    key: str | None = None
    instrumental: bool = True


class Music(Contract):
    model: str = DEFAULT_MUSIC_MODEL
    cues: list[MusicCue] = Field(default_factory=list)
    seeds: list[int] = Field(default_factory=lambda: [1001, 1002, 1003], min_length=1, max_length=8)
    chosen_seed: int | None = None
    choice_reason: str | None = None

    @model_validator(mode="after")
    def check_choice(self) -> Music:
        if self.chosen_seed is not None and self.chosen_seed not in self.seeds:
            raise ValueError(f"music.chosen_seed {self.chosen_seed} is not one of music.seeds")
        return self


class Keyframe(Contract):
    prompt: str = Field(min_length=10)
    seed: int = Field(ge=0)
    model: str = DEFAULT_IMAGE_MODEL


class Motion(Contract):
    prompt: str = Field(min_length=5, description="Only the motion and the camera.")
    seed: int = Field(ge=0)
    model: str = DEFAULT_VIDEO_MODEL
    resolution: Literal["480p", "720p"] = "480p"
    frames: int = Field(default=121, ge=17, le=121, description="Wan frame count, 4k+1 (121 = 5 s at 24 fps).")

    @model_validator(mode="after")
    def check_frames(self) -> Motion:
        if (self.frames - 1) % 4:
            raise ValueError(f"motion.frames must be 4k+1, got {self.frames}")
        return self


class Narration(Contract):
    text: str = Field(min_length=1, description="Spoken line in the narration language.")
    subtitle: str = Field(min_length=1, description="English subtitle for the line.")


class Shot(Contract):
    id: str = Field(pattern=r"^s\d{2}$")
    duration_s: float = Field(ge=2, le=15)
    purpose: str = Field(min_length=5, description="Why this shot exists.")
    shot_size: ShotSize
    camera: str
    characters: list[str] = Field(default_factory=list)
    keyframe: Keyframe
    motion: Motion
    narration: Narration | None = Field(default=None, description="Omit for a silent shot that shows instead of tells.")
    fallback: Fallback = "kenburns"


class EndCard(Contract):
    text: str = Field(min_length=1)
    duration_s: float = Field(default=3.0, ge=2, le=5)


class Storyboard(Contract):
    version: Literal[1] = 1
    title: str = Field(min_length=1)
    language: str = Field(description="BCP-47 code of the narration language, e.g. 'am'.")
    subtitle_language: str = "en"
    target_duration_s: float = Field(ge=MIN_FILM_S, le=MAX_FILM_S)
    style_block: str = Field(min_length=10, description="Look appended to every image prompt.")
    characters: list[Character] = Field(default_factory=list)
    voice: Voice = Field(default_factory=Voice)
    music: Music = Field(default_factory=Music)
    shots: list[Shot] = Field(min_length=MIN_SHOTS, max_length=MAX_SHOTS)
    end_card: EndCard

    @property
    def planned_duration_s(self) -> float:
        return sum(shot.duration_s for shot in self.shots) + self.end_card.duration_s

    def shot(self, shot_id: str) -> Shot:
        for shot in self.shots:
            if shot.id == shot_id:
                return shot
        raise KeyError(f"No shot with id '{shot_id}'")

    @model_validator(mode="after")
    def check_consistency(self) -> Storyboard:
        duplicates = [i for i, n in Counter(s.id for s in self.shots).items() if n > 1]
        if duplicates:
            raise ValueError(f"Duplicate shot ids: {', '.join(duplicates)}")

        known = {c.id for c in self.characters}
        for shot in self.shots:
            unknown = set(shot.characters) - known
            if unknown:
                raise ValueError(f"Shot {shot.id} uses unknown characters: {', '.join(sorted(unknown))}")

        for character in self.characters:
            if character.real_person and not character.consent_ref:
                raise ValueError(
                    f"Character '{character.id}' is a real person but has no consent_ref"
                )

        total = self.planned_duration_s
        if not MIN_FILM_S <= total <= MAX_FILM_S:
            raise ValueError(
                f"Shots plus end card last {total:.1f}s; the film must be "
                f"{MIN_FILM_S:.0f}-{MAX_FILM_S:.0f}s"
            )
        return self
