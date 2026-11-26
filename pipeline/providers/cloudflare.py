import base64

import httpx

from pipeline.models import DEFAULT_IMAGE_MODEL

API_BASE = "https://api.cloudflare.com/client/v4/accounts"
IMAGE_SIZE = 1024


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
        if "flux-2" in self.model:
            # FLUX.2 takes form fields, not JSON.
            fields = {"prompt": prompt, "seed": str(seed), "width": str(IMAGE_SIZE), "height": str(IMAGE_SIZE)}
            request = {"files": {name: (None, value) for name, value in fields.items()}}
        else:
            # FLUX.1 schnell rejects a seed on Workers AI, so it can't be pinned.
            request = {"json": {"prompt": prompt, "steps": steps}}

        response = httpx.post(self._url, headers=self._headers, timeout=self._timeout_s, **request)
        if response.is_error:
            # Keep it an HTTPStatusError so 429/5xx are still retried, but show Cloudflare's reason.
            message = f"Cloudflare {response.status_code}: {response.text[:300]}"
            raise httpx.HTTPStatusError(message, request=response.request, response=response)

        body = response.json()
        image = (body.get("result") or {}).get("image")
        if not image:
            raise RuntimeError(f"Cloudflare returned no image: {body.get('errors')}")
        return base64.b64decode(image)
