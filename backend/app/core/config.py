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
    neo_recipe_exporter_url: str = ""
    neo_recipe_exporter_timeout_seconds: float = 3600.0
    auto_bake_recipes_after_instance_import: bool = False
    neo_recipe_export_supported_versions: str = "1.21.1"
    # Desktop: %APPDATA%/Recipe Tree Visualizer (задаётся из Tauri при старте)
    rtv_data_dir: str = ""
    # Корень репозитория на хосте (для путей к логам в UI при backend в Docker)
    project_host_path: str = ""

    def neo_recipe_export_supported_list(self) -> frozenset[str]:
        return frozenset(
            part.strip()
            for part in self.neo_recipe_export_supported_versions.split(",")
            if part.strip()
        )
    curseforge_api_key: str = ""
    curseforge_user_agent: str = (
        "Recipe-Tree-Visualizer/1.0 (https://github.com/Kotbuz/Recipe-Tree-Visualizer)"
    )
    mod_dependency_download_timeout_seconds: float = 120.0
    enable_local_folder_picker: bool = True
    cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost,"
        "https://tauri.localhost,http://tauri.localhost,"
        "https://asset.localhost,http://asset.localhost,tauri://localhost"
    )

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

    @property
    def log_dir_path(self) -> Path:
        path = Path(self.log_dir)
        if path.is_absolute():
            return path
        backend_root = Path(__file__).resolve().parents[2]
        return (backend_root / path).resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
