from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ML_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ML_DIR / ".env")

    # Same schema backend/ writes to (see CLAUDE.md's ml/ section) — SQLite
    # locally, mysql:// in production. Relative paths are resolved from ml/'s
    # own directory, not the process's cwd, so `uv run` works from anywhere.
    database_url: str = "sqlite:///../backend/var/data_dev.db"

    min_sample_size: int = 5

    port: int = 8001

    @property
    def resolved_database_url(self) -> str:
        prefix = "sqlite:///"
        if self.database_url.startswith(prefix) and not self.database_url[len(prefix):].startswith("/"):
            relative_path = self.database_url[len(prefix):]
            return prefix + str((_ML_DIR / relative_path).resolve())
        return self.database_url


settings = Settings()
