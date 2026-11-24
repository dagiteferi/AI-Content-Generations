from pipeline.config import Settings
from pipeline.providers.base import ImageModel
from pipeline.providers.cloudflare import CloudflareFlux


def image_model(settings: Settings, model: str) -> ImageModel:
    if model.startswith("@cf/"):
        return CloudflareFlux(
            settings.secret("cloudflare_account_id"),
            settings.secret("cloudflare_api_token"),
            model=model,
        )
    raise ValueError(f"No image provider for model '{model}'")
