from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from pipeline.errors import MissingCredential


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    gemini_api_key: SecretStr | None = None
    cloudflare_account_id: str | None = None
    cloudflare_api_token: SecretStr | None = None
    kaggle_username: str | None = None
    kaggle_key: SecretStr | None = None

    text_model: str = "gemini-3.8-flash"
    max_attempts: int = Field(default=3, ge=1, le=10)
    root: Path = Field(default_factory=Path.cwd)

    @property
    def storyboard_path(self) -> Path:
        return self.root / "storyboard.json"

    @property
    def schema_path(self) -> Path:
        return self.root / "schema" / "storyboard.schema.json"

    @property
    def ethics_path(self) -> Path:
        return self.root / "ETHICS.md"

    @property
    def outputs_dir(self) -> Path:
        return self.root / "outputs"

    @property
    def runs_path(self) -> Path:
        return self.root / "runs.jsonl"

    def secret(self, name: str) -> str:
        value = getattr(self, name)
        if not value:
            raise MissingCredential(name.upper())
        return value.get_secret_value() if isinstance(value, SecretStr) else value
