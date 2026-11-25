import base64
import threading

from google import genai
from google.genai import types


TIMEOUT_MS = 90_000  # without a limit a busy Gemini call can hang forever
DEADLINE_S = 120  # total time per call; the read timeout resets while data trickles in


def with_deadline(operation, seconds: float = DEADLINE_S):
    """Run `operation`, but give up after `seconds` even if the connection is still alive."""
    result: dict = {}

    def target() -> None:
        try:
            result["value"] = operation()
        except Exception as error:  # handed back to the caller below
            result["error"] = error

    worker = threading.Thread(target=target, daemon=True)
    worker.start()
    worker.join(seconds)
    if worker.is_alive():
        raise TimeoutError(f"Gemini call took longer than {seconds:.0f}s")
    if "error" in result:
        raise result["error"]
    return result["value"]


def _client(api_key: str) -> genai.Client:
    return genai.Client(api_key=api_key, http_options={"api_version": "v1beta", "timeout": TIMEOUT_MS})


class GeminiText:
    provider = "gemini"

    def __init__(self, api_key: str, model: str) -> None:
        self.model = model
        self._client = _client(api_key)

    def generate_json(self, prompt: str) -> str:
        response = self._client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.7,
            ),
        )
        if not response.text:
            raise RuntimeError("Gemini returned an empty response")
        return response.text


class GeminiSpeech:
    provider = "gemini"

    def __init__(self, api_key: str, model: str) -> None:
        self.model = model
        self._client = _client(api_key)

    def synthesize(self, text: str, *, voice: str, style: str) -> bytes:
        interaction = with_deadline(lambda: self._client.interactions.create(
            model=self.model,
            input=[
                {
                    "type": "user_input",
                    "content": [
                        {
                            "type": "text",
                            "text": text,
                            "annotations": [{"type": "speech_metadata", "style": style}],
                        }
                    ],
                }
            ],
            response_format={"type": "audio"},
            generation_config={"speech_config": [{"voice": voice}]},
        ))
        if not interaction.output_audio or not interaction.output_audio.data:
            raise RuntimeError("Gemini TTS returned no audio")
        return base64.b64decode(interaction.output_audio.data)
