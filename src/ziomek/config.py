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
    host: str = "localhost"
    no_vscode: bool = False
    no_browser: bool = False
    stt_engine: str = "faster_whisper"
    stt_model: str = "tiny.en"
    stt_model_dir: str | None = None

    @classmethod
    def load(cls, config_path: str | Path | None = None) -> "Settings":
        """Load Settings from a YAML config file.

        Precedence: explicit path > ziomek_config.yaml > ziomek_server_config.yaml
        in cwd or ~/.ziomek/.
        """
        if config_path:
            result = cls._load_file(Path(config_path))
            if result is not None:
                return result
            return cls()

        # Try new name, then old name for backward compatibility
        for name in ["ziomek_config.yaml", "ziomek_server_config.yaml"]:
            for base in [Path.cwd(), Path.home() / ".ziomek"]:
                path = base / name
                result = cls._load_file(path)
                if result is not None:
                    return result
        return cls()

    @classmethod
    def _load_file(cls, path: Path) -> "Settings | None":
        path = path.resolve()
        allowed = {Path.cwd().resolve(), Path.home().resolve()}
        if not any(path.is_relative_to(a) or path == a for a in allowed):
            return None
        if not path.is_file():
            return None
        try:
            import yaml
        except ImportError:
            return None
        try:
            with open(path) as f:
                data = yaml.safe_load(f) or {}
        except OSError:
            return None
        known = {k: v for k, v in data.items() if k in cls.model_fields}
        return cls(**known)

    @classmethod
    def compose(
        cls,
        file_path: str | Path | None = None,
        env_backend: str | None = None,
        env_device: str | int | None = None,
        env_host: str | None = None,
        cli_backend: str | None = None,
        cli_device: str | int | None = None,
        cli_host: str | None = None,
        *,
        port: int | None = None,
        model_path: str | None = None,
        voice: str | None = None,
        cache_dir: str | None = None,
        host: str | None = None,
        no_browser: bool | None = None,
        no_vscode: bool | None = None,
        stt_engine: str | None = None,
        stt_model: str | None = None,
        stt_model_dir: str | None = None,
    ) -> "Settings":
        """Compose Settings from config sources with precedence: CLI > env > file > defaults."""
        file_settings = cls.load(file_path) if file_path else cls()
        env_backend_val = env_backend or file_settings.audio_backend
        env_device_val = env_device if env_device is not None else file_settings.audio_device
        env_host_val = env_host if env_host is not None else file_settings.host
        cli_backend_val = cli_backend or env_backend_val
        cli_device_val = cli_device if cli_device is not None else env_device_val
        cli_host_val = host if host is not None else (cli_host if cli_host is not None else env_host_val)
        no_browser_val = no_browser if no_browser is not None else file_settings.no_browser
        no_vscode_val = no_vscode if no_vscode is not None else file_settings.no_vscode
        stt_engine_val = stt_engine or file_settings.stt_engine
        stt_model_val = stt_model or file_settings.stt_model
        stt_model_dir_val = stt_model_dir or file_settings.stt_model_dir
        return cls(
            audio_backend=cli_backend_val,
            audio_device=cli_device_val,
            host=cli_host_val,
            port=port if port is not None else file_settings.port,
            model_path=model_path or file_settings.model_path,
            voice=voice or file_settings.voice,
            cache_dir=cache_dir or file_settings.cache_dir,
            no_browser=no_browser_val,
            no_vscode=no_vscode_val,
            stt_engine=stt_engine_val,
            stt_model=stt_model_val,
            stt_model_dir=stt_model_dir_val,
        )

    @classmethod
    def scaffold_config(cls, path: str | Path | None = None) -> Path:
        """Create a default YAML config file at the given path (default: ziomek_config.yaml)."""
        if path is None:
            path = "ziomek_config.yaml"
        content = """# ziomek configuration
# Generate with: ziomek --scaffold-config

# Server settings
# port: 5003
# model_path:
# voice: default
# cache_dir:
# host: localhost

# Audio playback backend (sounddevice, pygame, pyaudio, playsound, noop)
# audio_backend: sounddevice

# Audio device (None/default = system default, or int index, or device name string)
# audio_device:

# Client settings
# no_vscode: false
# no_browser: false

# STT (Speech-to-Text) settings
# stt_engine: faster_whisper
# stt_model: tiny.en
# stt_model_dir:
"""
        p = Path(path).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return p
