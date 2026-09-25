"""ziomek HTTP server — FastAPI application."""
import uvicorn
from fastapi import FastAPI
from ziomek.config import Settings
import sys


def create_app(settings=None) -> FastAPI:
    if settings is None:
        settings = Settings()
    app = FastAPI(title="ziomek", version="0.1.0")
    return app


def run_server(port=5003, model_path=None, voice="default", cache_dir=None):
    settings = Settings(port=port, model_path=model_path, voice=voice, cache_dir=cache_dir)
    app = create_app(settings)
    print(f"ziomek server listening on http://localhost:{port}", file=sys.stderr)
    uvicorn.run(app, host="localhost", port=port)
