import base64

import httpx

from pipeline.models import DEFAULT_IMAGE_MODEL

API_BASE = "https://api.cloudflare.com/client/v4/accounts"


class CloudflareFlux:
    provider = "cloudflare"

    def __init__(
        self,
        account_id: str,
        api_token: str,
        model: str = DEFAULT_IMAGE_MODEL,
        timeout_s: float = 90.0,
    ) -> None:
        self.model = model
        self._url = f"{API_BASE}/{account_id}/ai/run/{model}"
        self._headers = {"Authorization": f"Bearer {api_token}"}
        self._timeout_s = timeout_s

    def generate(self, prompt: str, *, seed: int, steps: int = 4) -> bytes:
        response = httpx.post(
            self._url,
            headers=self._headers,
            json={"prompt": prompt, "seed": seed, "steps": steps},
            timeout=self._timeout_s,
        )
        response.raise_for_status()
        body = response.json()
        image = body.get("result", body).get("image")
        if not image:
            raise RuntimeError(f"Cloudflare returned no image: {body.get('errors')}")
        return base64.b64decode(image)
