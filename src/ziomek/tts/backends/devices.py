"""Answer what a device ask names, for the devices a path can see."""

from typing import TYPE_CHECKING

from .device_type import read_type_from_name

if TYPE_CHECKING:
    from .base import IBackend


def which_devices_carry(name: str, backend: "IBackend") -> list[int]:
    """The devices whose names carry the part asked for, in the order they are reported.

    The order is the one written in docs/internal/tests.md: the table is asked first (that part is added
    by the settings task), then a name is read for the side it words, then a part of a name is matched
    against the whole names.

    Args:
        name: The name as it was asked for.
        backend: The path whose devices are looked at.

    Returns:
        Every device that carries the name, so more than one can be said instead of one being picked.
    """
    devices = backend.list_devices()
    wanted = str(name).lower()
    side = read_type_from_name(wanted)
    if side:
        return [dev["id"] for dev in devices if dev.get("type") == side or read_type_from_name(dev["name"]) == side]
    return [dev["id"] for dev in devices if wanted in dev["name"].lower()]


def resolve_devices(device_spec: str | int | None, backend: "IBackend") -> list[int]:
    """Which devices the ask names. An empty answer means nothing was named or nothing carries it.

    An empty answer is not the system default: the caller chooses the system default when it asks for it,
    so nothing-found and the default stay apart.

    Args:
        device_spec: None, "default", an index, or a device name.
        backend: The path whose devices are looked at.

    Returns:
        The devices the ask names. Nothing is picked when more than one could be meant.
    """
    if device_spec is None or str(device_spec).lower() == "default":
        return []
    if isinstance(device_spec, int):
        return [device_spec]
    return which_devices_carry(str(device_spec), backend)
