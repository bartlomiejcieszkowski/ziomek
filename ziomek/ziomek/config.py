"""ziomek settings."""
from pydantic import BaseModel


class Settings(BaseModel):
    port: int = 5003
    model_path: str | None = None
    voice: str = "default"
    cache_dir: str | None = None
