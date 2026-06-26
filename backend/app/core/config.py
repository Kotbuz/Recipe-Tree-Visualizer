from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"
    log_dir: str = "logs"
    mods_auto_load_on_startup: bool = True
    mod_upload_max_bytes: int = 256 * 1024 * 1024
    minecraft_default_version: str = "26.2"
    version_catalog_cache_ttl_seconds: int = 86_400
    minecraft_versions_dir: str = "../MinecraftVersions"
    renderer_url: str = "http://localhost:3001"
    renderer_minecraft_root: str = "/data/minecraft"
    minecraft_render_version: str = "1.21.4"
    renderer_icon_size: int = 128
    renderer_batch_size: int = 25
    renderer_timeout_seconds: float = 600.0
    vanilla_icon_render_on_startup: bool = True
    recipe_exporter_url: str = ""
    recipe_exporter_mode: str = "auto"
    recipe_exporter_timeout_seconds: float = 1800.0
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def minecraft_versions_path(self) -> Path:
        path = Path(self.minecraft_versions_dir)
        if path.is_absolute():
            return path
        backend_root = Path(__file__).resolve().parents[2]
        return (backend_root / path).resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
