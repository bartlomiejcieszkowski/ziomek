from pathlib import Path

from ziomek import __version__


def test_version():
    """Verify the runtime version matches the VERSION file at the repo root."""
    version_file = Path(__file__).resolve().parent.parent / "VERSION"
    assert __version__ == version_file.read_text(encoding="utf-8").strip()
