"""Configuration management via environment variables and config files.

All settings are prefixed with ``CAD_`` (see AGENTS.md section 8.2).
Environment variables take precedence over a ``.env`` file.
"""

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the CAD system."""

    model_config = SettingsConfigDict(
        env_prefix="CAD_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    runtime: str = Field("analytic", description="CAD kernel: analytic / occ / freecad")
    headless: bool = Field(True, description="Headless mode (no GUI)")
    temp_dir: str = Field("/tmp/cad", description="Temporary file directory")  # noqa: S108
    max_memory: int = Field(4096, description="Max memory in MB")
    log_level: str = Field("INFO", description="Log level")
    log_json: bool = Field(True, description="Emit structured JSON logs")
    config_path: str = Field("~/.cad-cli/config.yaml", description="Config file path")
    mcp_transport: str = Field("stdio", description="MCP transport mode")
    mcp_port: int = Field(8081, description="MCP HTTP/SSE port")
    mcp_host: str = Field("0.0.0.0", description="MCP HTTP host")  # noqa: S104
    auto_approve: str = Field("", description="Comma separated auto-approved tool list")
    safe_mode: bool = Field(False, description="Safe mode disables destructive ops")
    api_key: str = Field("", description="API key for HTTP transport (optional)")
    debug: bool = Field(False, description="Debug mode")

    @property
    def temp_path(self) -> Path:
        """Return ``temp_dir`` as a ``Path``."""
        return Path(self.temp_dir).expanduser()

    def load_yaml_overrides(self, path: str | None = None) -> "Settings":
        """Merge values from a YAML config file into a copy of these settings."""
        config_path = Path(path or self.config_path).expanduser()
        if not config_path.is_file():
            return self
        with config_path.open("r", encoding="utf-8") as handle:
            data: dict[str, Any] = yaml.safe_load(handle) or {}
        if "settings" in data:
            data = data["settings"]
        overrides = {key: value for key, value in data.items() if value is not None}
        return self.model_copy(update=overrides)


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide singleton settings."""
    return Settings().load_yaml_overrides()
