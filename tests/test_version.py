import json
from pathlib import Path

from ziomek import __version__

ROOT = Path(__file__).resolve().parent.parent


def test_version():
    """Verify the runtime version matches the VERSION file at the repo root."""
    version_file = ROOT / "VERSION"
    assert __version__ == version_file.read_text(encoding="utf-8").strip()


def test_the_plugin_bundle_carries_the_same_version():
    """The plugin manifest must not claim a version on its own."""
    manifest = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))
    assert manifest["version"] == __version__
