import base64

from google import genai
from google.genai import types


TIMEOUT_MS = 90_000  # without a limit a busy Gemini call can hang forever


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
        interaction = self._client.interactions.create(
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
        )
        if not interaction.output_audio or not interaction.output_audio.data:
            raise RuntimeError("Gemini TTS returned no audio")
        return base64.b64decode(interaction.output_audio.data)
