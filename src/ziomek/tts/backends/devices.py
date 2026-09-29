"""ziomek audio device resolution utilities."""
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import IBackend


def resolve_device(device_spec: str | int | None, backend: "IBackend") -> int | None:
    """Resolve a device specification to an integer index.

    Args:
        device_spec: None, "default", int index, or device name string.
        backend: The backend to query for device names.

    Returns:
        Integer device index, or None for system default.

    Raises:
        ValueError: If a device name is provided but not found.
    """
    if device_spec is None or str(device_spec).lower() == "default":
        return None
    if isinstance(device_spec, int):
        return device_spec
    name = str(device_spec).lower()
    devices = backend.list_devices()
    for dev in devices:
        if dev["name"].lower() == name:
            return dev["id"]
    names = ", ".join(d["name"] for d in devices) if devices else "none"
    raise ValueError(f"Device not found: {str(device_spec)} (available: {names})")
