"""ziomek settings — with config file loading."""
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class Settings(BaseModel):
    """Application settings with optional config file loading."""

    port: int = 5003
    model_path: str | None = None
    voice: str = "default"
    cache_dir: str | None = None
    audio_backend: str = "sounddevice"
    audio_device: str | int | None = None

    @classmethod
    def load(cls, config_path: str | Path) -> "Settings":
        """Load settings from a YAML config file.

        If the file does not exist, returns Settings with defaults.
        """
        path = Path(config_path).resolve()
        allowed = {Path.cwd().resolve(), Path.home().resolve()}
        if not any(path.is_relative_to(a) or path == a for a in allowed):
            return cls()
        if not path.is_file():
            return cls()
        try:
            import yaml
        except ImportError:
            return cls()
        try:
            with open(path) as f:
                data = yaml.safe_load(f) or {}
        except OSError:
            return cls()
        known = {k: v for k, v in data.items() if k in cls.model_fields}
        return cls(**known)

    @classmethod
    def compose(
        cls,
        file_path: str | Path | None = None,
        env_backend: str | None = None,
        env_device: str | int | None = None,
        cli_backend: str | None = None,
        cli_device: str | int | None = None,
    ) -> "Settings":
        """Compose Settings from config sources with precedence: CLI > env > file > defaults."""
        file_settings = cls.load(file_path) if file_path else cls()
        env_backend_val = env_backend or file_settings.audio_backend
        env_device_val = env_device if env_device is not None else file_settings.audio_device
        cli_backend_val = cli_backend or env_backend_val
        cli_device_val = cli_device if cli_device is not None else env_device_val
        return cls(
            audio_backend=cli_backend_val,
            audio_device=cli_device_val,
            port=file_settings.port,
            model_path=file_settings.model_path,
            voice=file_settings.voice,
            cache_dir=file_settings.cache_dir,
        )
