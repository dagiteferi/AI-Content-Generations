from typing import Protocol


class TextModel(Protocol):
    provider: str
    model: str

    def generate_json(self, prompt: str) -> str: ...


class SpeechModel(Protocol):
    provider: str
    model: str

    def synthesize(self, text: str, *, voice: str, style: str) -> bytes:
        """Return a WAV file as bytes."""
        ...


class ImageModel(Protocol):
    provider: str
    model: str

    def generate(self, prompt: str, *, seed: int) -> bytes:
        """Return an encoded image as bytes."""
        ...
