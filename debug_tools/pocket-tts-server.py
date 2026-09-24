"""
Pocket TTS Server — HTTP server wrapping the pocket_tts Python package.
Starts the model once on startup, then serves /generate requests.

Usage (preferred):
  uv run python pocket-tts-server.py --port 5003
  uv run python pocket-tts-server.py --port 5003 --voice "alba"

Usage (fallback):
  python pocket-tts-server.py --port 5003
"""
# isort: skip_file

import argparse
import base64
import io
import json
import os
import re
import shutil
import sys
import threading
import traceback
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional

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
model_state: dict = {}  # streaming cache state (shared across requests)
voice_states: dict = {}  # voice-specific state updates (cached in memory & on disk)
voice_dir: str | None = None  # local cache directory for voices & voice states
server_ready = False  # flag for the thread-safe status check
_server_ready = False  # flag for the thread-safe status check
_active_streams: list = []  # keep playback streams alive
server_ready = False
server_port = 5003


def _build_model_state(tts_model: "TTSModel") -> dict:  # type: ignore[name-defined]
    """Initialize the streaming cache for all stateful modules.

    Must be called on flow_lm and mimi separately (not on the parent TTSModel)
    because the StatefulModules have their absolute names set relative to their
    parent (e.g. 'transformer.layers.0.self_attn' not 'flow_lm.transformer...').
    """
    from pocket_tts.modules.stateful_module import StatefulModule

    result: dict = {}
    # Initialize state separately for flow_lm and mimi so keys match the
    # modules' _module_absolute_name (which was set at registration time).
    for top_module in (tts_model.flow_lm, tts_model.mimi):
        for module_name, module in top_module.named_modules():
            if isinstance(module, StatefulModule):
                result[module_name] = module.init_state(
                    batch_size=1, sequence_length=4000
                )
    return result


def _hf_to_local_path(voice_key: str) -> Path | None:
    """Convert an HF voice URL to a local cache path. Returns None if not an HF URL."""
    if not voice_key.startswith("hf://"):
        return None
    # hf://repo/file.wav -> repo__file.wav
    local_name = voice_key[len("hf://"):].replace("/", "__")
    # Sanitize: keep only safe characters
    safe_name = re.sub(r'[^a-zA-Z0-9_.\-]', '_', local_name)
    return Path(voice_dir) / safe_name if voice_dir else None


def _download_voice_from_hf(voice_key: str, dest: Path) -> str | None:
    """Download a voice file from HuggingFace Hub. Returns local path on success, None on failure."""
    print(f"Downloading voice from HF: {voice_key} -> {dest}", file=sys.stderr)
    try:
        from huggingface_hub import hf_hub_download  # type: ignore[import-untyped]
    except ImportError:
        print(
            "WARNING: huggingface_hub not installed. Cannot auto-download voice. "
            "Install with: pip install huggingface_hub",
            file=sys.stderr,
        )
        return None

    # Parse repo_id and filename from hf:// repo/file.wav
    hf_path = voice_key[len("hf://"):]
    parts = hf_path.split("/", 1)
    if len(parts) != 2:
        print(f"WARNING: Invalid HF voice URL: {voice_key}", file=sys.stderr)
        return None

    repo_id, rel_path = parts
    dest.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Download the specific file (not the whole snapshot)
        cached_path = hf_hub_download(
            repo_id=repo_id,
            filename=rel_path,
            cache_dir=str(dest.parent),
        )
        # Copy to our voice cache (single file, not a directory)
        shutil.copy2(cached_path, str(dest))
        print(f"Voice downloaded: {dest} ({dest.stat().st_size} bytes)", file=sys.stderr)
        return str(dest)
    except Exception as e:
        print(f"WARNING: Failed to download voice {voice_key}: {e}", file=sys.stderr)
        return None


def _voice_state_path(voice_key: str) -> Path:
    """Get the path where a voice state should be cached on disk."""
    if voice_dir is None:
        return Path("")
    safe = re.sub(r'[^a-zA-Z0-9_.\-]', '_', voice_key)
    return Path(voice_dir) / f"{safe}.safetensors"


def _save_voice_state(voice_key: str, state: dict) -> None:
    """Persist a voice state to disk so it survives server restarts."""
    path = _voice_state_path(voice_key)
    if not path:
        return  # no cache dir configured
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import safetensors.torch as st
        flat: dict = {}
        for module_name, module_state in state.items():
            for key, tensor in module_state.items():
                flat[f"{module_name}/{key}"] = tensor
        st.save_file(flat, str(path))
        print(f"Cached voice state: {path} ({os.path.getsize(path):,} bytes)", file=sys.stderr)
    except Exception as e:
        import traceback
        print(f"WARNING: Failed to save voice state {voice_key}: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)


def _load_voice_state(voice_key: str) -> dict | None:
    """Load a previously cached voice state from disk. Returns None if not found."""
    path = _voice_state_path(voice_key)
    if not path or not path.exists():
        return None
    try:
        import safetensors
        result: dict = {}
        with safetensors.safe_open(path, framework="pt") as f:
            for key in f.keys():  # noqa  # safe_open handle, not dict
                module_name, tensor_key = key.split("/", 1)
                result.setdefault(module_name, {})
                if tensor_key == "current_end":
                    tensor = f.get_tensor(key)
                    result[module_name]["offset"] = torch.full(
                        (1,), fill_value=tensor.shape[0], dtype=torch.long, device=tensor.device
                    )
                else:
                    result[module_name][tensor_key] = f.get_tensor(key)
        print(f"Loaded cached voice state: {path}", file=sys.stderr)
        return result
    except Exception as e:
        print(f"WARNING: Failed to load cached voice state: {e}", file=sys.stderr)
        return None


def load_voice(voice_key: str) -> dict:  # type: ignore[name-defined]
    """Load or retrieve cached voice state (memory → disk → generate)."""
    # Handle "default" as a special alias for the first loaded voice
    if voice_key == "default":
        if voice_states:
            return list(voice_states.values())[0]
        voice_key = "alba"  # fallback

    # 1️⃣  In-memory cache (fastest — survives within a single server run)
    if voice_key in voice_states:
        return voice_states[voice_key]

    # 2️⃣  Disk cache (survives restarts)
    cached = _load_voice_state(voice_key)
    if cached is not None:
        voice_states[voice_key] = cached
        return cached

    # 3️⃣  HuggingFace URL — try local audio cache, then download
    if voice_key.startswith("hf://"):
        local_path = _hf_to_local_path(voice_key)
        if local_path and local_path.exists():
            print(f"Loading cached voice audio: {local_path}", file=sys.stderr)
            with Path(local_path).open("rb") as f:
                audio_bytes = f.read()
            audio_tensor = (
                torch.frombuffer(audio_bytes, dtype=torch.uint8).float().div_(127.5)
            )
            state = tts_model.get_state_for_audio_prompt(audio_tensor)  # type: ignore[union-attr]
        elif voice_dir:
            downloaded = _download_voice_from_hf(voice_key, local_path)  # type: ignore[arg-type]
            if downloaded and os.path.exists(downloaded):
                print(f"Loaded downloaded voice: {downloaded}", file=sys.stderr)
                with Path(downloaded).open("rb") as f:
                    audio_bytes = f.read()
                audio_tensor = (
                    torch.frombuffer(audio_bytes, dtype=torch.uint8).float().div_(127.5)
                )
                state = tts_model.get_state_for_audio_prompt(audio_tensor)  # type: ignore[union-attr]
            else:
                print(f"Falling back to HF load for: {voice_key}", file=sys.stderr)
                state = tts_model.get_state_for_audio_prompt(voice_key)  # type: ignore[union-attr]
        else:
            print(f"Falling back to HF load for: {voice_key}", file=sys.stderr)
            state = tts_model.get_state_for_audio_prompt(voice_key)  # type: ignore[union-attr]

    # 4️⃣  Local file path
    elif os.path.isfile(voice_key):
        with Path(voice_key).open("rb") as f:
            audio_bytes = f.read()
        audio_tensor = (
            torch.frombuffer(audio_bytes, dtype=torch.uint8).float().div_(127.5)
        )
        state = tts_model.get_state_for_audio_prompt(audio_tensor)  # type: ignore[union-attr]

    # 5️⃣  Catalog voice (alba, cosette, javert, etc.)
    else:
        print(f"Loading catalog voice: {voice_key}", file=sys.stderr)
        state = tts_model.get_state_for_audio_prompt(voice_key)  # type: ignore[union-attr]

    # Cache in memory AND on disk
    voice_states[voice_key] = state
    _save_voice_state(voice_key, state)
    return state


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
        if self.path == "/api/tts/status":
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
                        "generate": "POST /api/tts/generate",
                        "status": "GET /api/tts/status",
                    },
                }
            )
        else:
            self._send_json({"error": "Not Found"}, 404)

    def do_POST(self):
        """Handle POST requests."""
        if self.path == "/api/tts/generate":
            self._handle_generate()
        elif self.path == "/api/tts/speak":
            self._handle_speak()
        else:
            self._send_json({"error": "Not Found"}, 404)

    # Background threads that keep audio playing (prevents GC from killing them)
    _active_play_threads: list[threading.Thread] = []

    def _play_wav(self, wav_bytes: bytes, sample_rate: int) -> None:
        """Play WAV audio bytes via ctypes waveOut API (Windows mixing) or sounddevice (cross-platform)."""
        import soundfile as sf
        import gc
        import struct
        import ctypes
        import ctypes.wintypes
        import sys
        import tempfile

        WAVE_FORMAT_PCM = 1
        WAVE_MAPPER = -1
        MMERR_NOERROR = 0

        # Function pointers returned by waveOutOpen
        CALLBACK_NULL = 0

        class WAVEHDR(ctypes.Structure):
            _fields_ = [
                ("lpData", ctypes.c_char_p),
                ("dwBufferLength", ctypes.c_ulong),
                ("dwBytesRecorded", ctypes.c_ulong),
                ("dwUser", ctypes.c_ulong),
                ("dwFlags", ctypes.c_ulong),
                ("dwLoops", ctypes.c_ulong),
                ("lpNext", ctypes.c_void_p),
                ("reserved", ctypes.c_ulong),
            ]

        def _play_mme():
            """Use Windows MME waveOut API for true mixing."""
            winmm = ctypes.windll.winmm
            try:
                # Parse WAV header to get data offset
                import io as io_mod
                f = io_mod.BytesIO(wav_bytes)
                # Skip RIFF chunk
                chunk_id = f.read(4)
                chunk_size = struct.unpack('<I', f.read(4))[0]
                # Skip WAVE
                format_id = f.read(4)
                # Read fmt chunk
                fmt_id = f.read(4)
                fmt_size = struct.unpack('<I', f.read(4))[0]
                audio_format = struct.unpack('<H', f.read(2))[0]
                num_channels = struct.unpack('<H', f.read(2))[0]
                sample_rate_val = struct.unpack('<I', f.read(4))[0]
                byte_rate = struct.unpack('<I', f.read(4))[0]
                block_align = struct.unpack('<H', f.read(2))[0]
                bits_per_sample = struct.unpack('<H', f.read(2))[0]
                # Skip to data chunk
                data_id = f.read(4)
                data_size = struct.unpack('<I', f.read(4))[0]
                data_offset = f.tell()

                # Prepare wave header (fmt chunk)
                fmt_header = struct.pack('<IHHHHHH', 16, WAVE_FORMAT_PCM, num_channels, sample_rate_val, byte_rate, block_align, bits_per_sample)
                wav_header = b'RIFF' + struct.pack('<I', 36 + data_size) + b'WAVEfmt ' + fmt_header + b'data' + struct.pack('<I', data_size)

                # Copy wav_bytes to a pinned buffer
                wav_pinned = (ctypes.c_ubyte * len(wav_bytes))()
                wav_pinned[:] = wav_bytes

                # Prepare WAVEHDR
                hdr = WAVEHDR()
                hdr.lpData = ctypes.cast(wav_pinned, ctypes.c_char_p)
                hdr.dwBufferLength = len(wav_header) + data_size

                # Write WAV header + data
                wav_data = bytes(wav_header) + bytes(wav_pinned[data_offset:data_offset + data_size])
                hdr.lpData = ctypes.create_string_buffer(wav_data)
                hdr.dwBufferLength = len(wav_data)
                hdr.dwFlags = 0  # WHDR_BEGINLOOP

                hwo = ctypes.c_void_p()
                rc = winmm.waveOutOpen(
                    ctypes.byref(hwo),
                    WAVE_MAPPER,
                    ctypes.byref(fmt_header),
                    0, 0,
                    CALLBACK_NULL | 0x10000  # CALLBACK_FUNCTION | WAVE_ALLOCSYNCBUFFER
                )
                if rc != MMERR_NOERROR:
                    raise OSError(f"waveOutOpen failed with error {rc}")

                rc = winmm.waveOutWrite(hwo, ctypes.byref(hdr), ctypes.sizeof(WAVEHDR))
                if rc != MMERR_NOERROR:
                    winmm.waveOutClose(hwo)
                    raise OSError(f"waveOutWrite failed with error {rc}")

                # Keep handle alive until playback completes
                while True:
                    hdr2 = WAVEHDR()
                    rc = winmm.waveOutUnprepareHeader(hwo, ctypes.byref(hdr2), ctypes.sizeof(WAVEHDR))
                    if rc != MMERR_NOERROR:
                        break
                    import time
                    time.sleep(0.05)
                    break

                winmm.waveOutClose(hwo)
                gc.collect()

            except Exception as e:
                print(f"WARNING: MME playback failed, trying fallback: {e}", file=sys.stderr)
                _play_fallback()

        def _play_fallback():
            """Fallback: write to temp WAV and play with subprocess."""
            import subprocess
            try:
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False, mode='wb') as tmp:
                    tmp.write(wav_bytes)
                    tmp_path = tmp.name
                subprocess.Popen([
                    'powershell', '-Command',
                    f'([Audio.PlayState]::Play)' + '; $w = New-Object System.Media.SoundPlayer "' + tmp_path + '"; $w.PlayAsync()'
                ], creationflags=subprocess.CREATE_NO_WINDOW)
            except Exception as e2:
                print(f"WARNING: Fallback playback failed: {e2}", file=sys.stderr)

        if sys.platform == 'win32':
            _play_mme()
            return

        # Fallback for non-Windows
        try:
            wav_file = io.BytesIO(wav_bytes)
            audio_data, read_sr = sf.read(wav_file)
            if audio_data.ndim == 2:
                audio_data = audio_data.mean(axis=1)
            import sounddevice as sd
            stream = sd.OutputStream(
                samplerate=read_sr,
                channels=1,
                dtype=audio_data.dtype,
            )
            stream.start()
            stream.write(audio_data)
            stream.stop()
            stream.close()
            gc.collect()
        except Exception as e:
            print(f"WARNING: Playback failed: {e}", file=sys.stderr)

        # Start playback in a background thread
        threading.Thread(target=_play_wav._play_wrapper_, args=(wav_bytes, sample_rate), daemon=True).start()

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

            merged_state = {**model_state, **voice_state}
            audio = tts_model.generate_audio(merged_state, text)  # type: ignore[union-attr]

            if isinstance(audio, torch.Tensor):
                audio_np = audio.detach().cpu().numpy()
            else:
                audio_np = audio

            sample_rate = tts_model.sample_rate  # type: ignore[union-attr]

            wav_buffer = io.BytesIO()
            wavfile.write(wav_buffer, sample_rate, audio_np)
            wav_bytes = wav_buffer.getvalue()

            duration = (
                len(audio_np) / sample_rate
                if isinstance(audio_np, (list, tuple)) or hasattr(audio_np, "__len__")
                else 0
            )

            duration = (
                len(audio_np) / sample_rate
                if isinstance(audio_np, (list, tuple)) or hasattr(audio_np, "__len__")
                else 0
            )

            # Play in background thread so we can respond immediately
            play_thread = threading.Thread(
                target=self._play_wav, args=(wav_bytes, sample_rate), daemon=True
            )
            self._active_play_threads.append(play_thread)
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
            print(f"Error speaking: {e}", file=sys.stderr)
            traceback.print_exc()
            self._send_json(
                {"error": str(e), "traceback": traceback.format_exc()}, 500
            )

    def _handle_generate(self):
        """Handle /api/tts/generate — returns audio only."""
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

            # Merge voice state into base model state (voice_state is a partial update)
            merged_state = {**model_state, **voice_state}

            # Generate audio
            audio = tts_model.generate_audio(merged_state, text)  # type: ignore[union-attr]

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
            duration = (
                len(audio_np) / sample_rate
                if isinstance(audio_np, (list, tuple)) or hasattr(audio_np, "__len__")
                else 0
            )

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
            self._send_json(
                {"error": str(e), "traceback": traceback.format_exc()}, 500
            )


def load_model_and_start_server(
    model_path: str | None = None,
    voice: str = "default",
    port: int = 5003,
    voice_dir_path: str | None = None,
):
    """Load Pocket TTS model and start HTTP server."""
    global tts_model, model_state, voice_states, voice_dir, server_ready, server_port
    voice_dir = voice_dir_path  # type: ignore[assignment]

    try:
        print("Loading Pocket TTS model...", file=sys.stderr)
        if model_path and os.path.exists(model_path):
            tts_model = TTSModel.load_from_path(model_path)  # type: ignore[name-defined]
            print(f"Loaded model from: {model_path}", file=sys.stderr)
        else:
            tts_model = TTSModel.load_model()  # type: ignore[name-defined]
            print("Loaded default Pocket TTS model", file=sys.stderr)

        # Build the base streaming cache state (shared across requests)
        model_state = _build_model_state(tts_model)  # type: ignore[arg-type]
        print(f"Initialized model state with {len(model_state)} modules", file=sys.stderr)

        # Load default voice
        print("Loading default voice...", file=sys.stderr)
        load_voice(voice)
        print(f"Voice loaded: {voice}", file=sys.stderr)

        server_ready = True
        server_port = port

        print(
            f"Pocket TTS Server listening on http://localhost:{port}", file=sys.stderr
        )
        print("Endpoints: POST /api/tts/speak, POST /api/tts/generate, GET /api/tts/status", file=sys.stderr)

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
    parser.add_argument(
        "--port", type=int, default=5003, help="Server port (default: 5003)"
    )
    parser.add_argument(
        "--voice",
        type=str,
        default="default",
        help='Voice identifier (HF URL, local file, or catalog name like "alba")',
    )
    parser.add_argument("--model-path", type=str, default=None, help="Path to Pocket TTS model")
    parser.add_argument(
        "--voice-dir",
        type=str,
        default=None,
        help="Local directory to cache downloaded voice files AND voice states",
    )

    args = parser.parse_args()

    load_model_and_start_server(
        model_path=args.model_path,
        voice=args.voice,
        port=args.port,
        voice_dir_path=args.voice_dir,
    )
