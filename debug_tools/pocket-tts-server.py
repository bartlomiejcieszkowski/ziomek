"""
Pocket TTS Server — HTTP server wrapping the pocket_tts Python package.
Starts the model once on startup, then serves /generate requests.

Usage (preferred):
  uv run python pocket-tts-server.py --port 5003
  uv run python pocket-tts-server.py --port 5003 --voice "hf://kyutai/tts-voices/alba-mackenna/casual.wav"

Usage (fallback):
  python pocket-tts-server.py --port 5003
"""
# isort: skip_file

import argparse
import base64
import io
import json
import os
import sys
import threading
import time
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional

import numpy as np  # type: ignore[import-untyped]
import scipy.io.wavfile as wavfile  # type: ignore[import-untyped]
import torch  # type: ignore[import-untyped]

try:
    from pocket_tts import TTSModel  # type: ignore[import-untyped]
except ImportError:
    print(
        "ERROR: pocket_tts package not installed. Install with: pip install pocket-tts",
        file=sys.stderr,
    )
    sys.exit(1)

# Global state
tts_model: Optional["TTSModel"] = None  # type: ignore[name-defined]
voice_states: dict = {}  # cache voices by key
server_ready = False
server_port = 5003
_active_streams: list = []  # keep playback streams alive for mixing
_active_play_threads: list[threading.Thread] = []  # track play threads


def load_voice(voice_key: str) -> "dict":  # type: ignore[name-defined]
    """Load or retrieve cached voice state."""
    if voice_key in voice_states:
        return voice_states[voice_key]

    # Check if it's a HuggingFace URL or local file path
    if voice_key.startswith("hf://") or os.path.isfile(voice_key):
        voice_state = tts_model.get_state_for_audio_prompt(voice_key)  # type: ignore[union-attr]
    elif voice_key == "default":
        # Use a named catalog voice as the default
        voice_state = tts_model.get_state_for_audio_prompt("cosette")  # type: ignore[union-attr]
    else:
        # Try the voice_key directly (might be a catalog voice name)
        voice_state = tts_model.get_state_for_audio_prompt(voice_key)  # type: ignore[union-attr]

    voice_states[voice_key] = voice_state
    return voice_state


class PocketTTSHandler(BaseHTTPRequestHandler):
    """HTTP request handler for Pocket TTS."""

    def log_message(self, format, *args):
        """Suppress default logging."""

    def _send_json(self, data: dict, status: int = 200):
        """Send JSON response."""
        response = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def do_GET(self):
        """Handle GET requests."""
        if self.path == "/status":
            self._send_json(
                {
                    "ready": server_ready,
                    "voices": list(voice_states.keys()),
                    "default_voice": "default",
                    "model_loaded": tts_model is not None,
                }
            )
        elif self.path == "/":
            self._send_json(
                {
                    "name": "Pocket TTS Server",
                    "version": "1.0.0",
                    "endpoints": {
                        "generate": "POST /generate",
                        "status": "GET /status",
                    },
                }
            )
        else:
            self._send_json({"error": "Not Found"}, 404)

    def do_POST(self):
        """Handle POST requests."""
        if self.path == "/generate":
            self._handle_generate()
        elif self.path == "/api/tts/speak":
            self._handle_speak()
        else:
            self._send_json({"error": "Not Found"}, 404)

    def _handle_generate(self):
        """Handle /generate endpoint."""
        try:
            content_length = int(self.headers["Content-Length"])
            body = self.rfile.read(content_length)
            data = json.loads(body)

            text = data.get("text")
            if not text:
                self._send_json({"error": 'Missing "text" field'}, 400)
                return

            voice_key = data.get("voice", "default")
            voice_state = load_voice(voice_key)

            # Generate audio
            audio = tts_model.generate_audio(voice_state, text)  # type: ignore[union-attr]

            # Convert to WAV
            if isinstance(audio, torch.Tensor):
                audio_np = audio.detach().cpu().numpy()
            else:
                audio_np = audio

            sample_rate = tts_model.sample_rate  # type: ignore[union-attr]

            # Write WAV to buffer
            wav_buffer = io.BytesIO()
            wavfile.write(wav_buffer, sample_rate, audio_np)
            wav_bytes = wav_buffer.getvalue()

            # Base64 encode
            audio_b64 = base64.b64encode(wav_bytes).decode("utf-8")

            # Calculate duration
            duration = len(audio_np) / sample_rate if isinstance(audio_np, (list, tuple)) or hasattr(audio_np, "__len__") else 0

            self._send_json(
                {
                    "audio_b64": audio_b64,
                    "duration": float(duration),
                    "sample_rate": sample_rate,
                    "channels": 1,
                    "bit_depth": 16,
                    "voice": voice_key,
                }
            )

        except Exception as e:
            print(f"Error generating audio: {e}", file=sys.stderr)
            traceback.print_exc()
            self._send_json({"error": str(e), "traceback": traceback.format_exc()}, 500)

    def _play_wav(self, wav_bytes: bytes, sample_rate: int) -> None:
        """Play WAV audio bytes using sounddevice with mixing support."""
        import sounddevice as sd
        import soundfile as sf
        import gc

        try:
            wav_file = io.BytesIO(wav_bytes)
            audio_data, read_sr = sf.read(wav_file)
            if audio_data.ndim == 2:
                audio_data = audio_data.mean(axis=1)
            # Convert to float32 for sounddevice compatibility
            if audio_data.dtype != np.float32:
                audio_data = audio_data.astype(np.float32)

            # Use sd.play() for non-blocking playback that supports mixing
            sd.play(audio_data, samplerate=read_sr, blocking=False)
            # Keep reference alive until playback completes
            duration_s = len(audio_data) / read_sr if len(audio_data) > 0 else 0
            time.sleep(duration_s + 0.1)
            gc.collect()
        except Exception as e:
            print(f"WARNING: Failed to play audio: {e}", file=sys.stderr)

    def _handle_speak(self):
        """Handle /api/tts/speak — generate audio AND play it locally."""
        try:
            content_length = int(self.headers["Content-Length"])
            body = self.rfile.read(content_length)
            data = json.loads(body)

            text = data.get("text")
            if not text:
                self._send_json({"error": 'Missing "text" field'}, 400)
                return

            voice_key = data.get("voice", "default")
            voice_state = load_voice(voice_key)

            # Generate audio
            voice_state = load_voice(voice_key)
            audio = tts_model.generate_audio(voice_state, text)  # type: ignore[union-attr]

            # Convert to numpy
            if isinstance(audio, torch.Tensor):
                audio_np = audio.detach().cpu().numpy()
            else:
                audio_np = audio

            sample_rate = tts_model.sample_rate  # type: ignore[union-attr]

            # Write WAV to buffer for playback
            wav_buffer = io.BytesIO()
            wavfile.write(wav_buffer, sample_rate, audio_np)
            wav_bytes = wav_buffer.getvalue()

            # Calculate duration
            duration = len(audio_np) / sample_rate if isinstance(audio_np, (list, tuple)) or hasattr(audio_np, "__len__") else 0

            # Play in background thread so we can respond immediately
            play_thread = threading.Thread(
                target=self._play_wav, args=(wav_bytes, sample_rate), daemon=True
            )
            _active_play_threads.append(play_thread)
            play_thread.start()

            self._send_json(
                {
                    "duration": float(duration),
                    "sample_rate": sample_rate,
                    "channels": 1,
                    "bit_depth": 16,
                    "voice": voice_key,
                    "status": "playing",
                }
            )

        except Exception as e:
            print(f"Error generating audio: {e}", file=sys.stderr)
            traceback.print_exc()
            self._send_json({"error": str(e), "traceback": traceback.format_exc()}, 500)


def load_model_and_start_server(model_path: str | None = None, voice: str = "default", port: int = 5003):
    """Load Pocket TTS model and start HTTP server."""
    global tts_model, voice_states, server_ready, server_port

    try:
        print("Loading Pocket TTS model...", file=sys.stderr)
        if model_path and os.path.exists(model_path):
            tts_model = TTSModel.load_from_path(model_path)  # type: ignore[name-defined]
            print(f"Loaded model from: {model_path}", file=sys.stderr)
        else:
            tts_model = TTSModel.load_model()  # type: ignore[name-defined]
            print("Loaded default Pocket TTS model", file=sys.stderr)

        # Load default voice
        print("Loading default voice...", file=sys.stderr)
        load_voice(voice)
        print(f"Voice loaded: {voice}", file=sys.stderr)

        server_ready = True

        print(f"Pocket TTS Server listening on http://localhost:{port}", file=sys.stderr)
        print("Endpoints: POST /generate, POST /api/tts/speak, GET /status", file=sys.stderr)

        # Start server
        server = HTTPServer(("localhost", port), PocketTTSHandler)
        server.serve_forever()

    except KeyboardInterrupt:
        print("\nShutting down Pocket TTS Server...", file=sys.stderr)
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pocket TTS HTTP Server")
    parser.add_argument("--port", type=int, default=5003, help="Server port (default: 5003)")
    parser.add_argument(
        "--voice",
        type=str,
        default="default",
        help='Voice identifier (HF URL, local file, or "default")',
    )
    parser.add_argument("--model-path", type=str, default=None, help="Path to Pocket TTS model")

    args = parser.parse_args()

    load_model_and_start_server(
        model_path=args.model_path,
        voice=args.voice,
        port=args.port,
    )
