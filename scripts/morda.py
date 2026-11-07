#!/usr/bin/env python3
"""Package a directory of avatar files into a `.morda` archive."""

import io
import sys
from pathlib import Path
from tarfile import TarFile

from ziomek.avatar.morda import definition_names


def collect_files(source: Path) -> list[Path]:
    """Every file under the skin folder, named by its path inside the archive."""
    return sorted(
        (file for file in source.rglob("*") if file.is_file()),
        key=lambda file: file.relative_to(source).as_posix(),
    )


def package(source: Path, target: Path) -> int:
    """Write the files of a skin folder into an archive, each entry named by its path inside that folder."""
    entries = collect_files(source)
    with TarFile.open(target, "w") as archive:
        for entry in entries:
            data = entry.read_bytes()
            info = archive.tarinfo()
            info.name = entry.relative_to(source).as_posix()
            info.size = len(data)
            info.mtime = int(entry.stat().st_mtime)
            archive.addfile(info, io.BytesIO(data))
    return len(entries)


def main():
    if len(sys.argv) < 2:
        print("usage: morda.py <directory> [output.morda]", file=sys.stderr)
        sys.exit(1)

    source = Path(sys.argv[1])
    if not source.is_dir():
        print(f"{source} is not a directory", file=sys.stderr)
        sys.exit(1)

    target = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(f"{source.name}.morda")

    entries = collect_files(source)
    if not entries:
        print("nothing to package", file=sys.stderr)
        sys.exit(1)
    if not definition_names(entry.relative_to(source).as_posix() for entry in entries):
        print(f"warning: no definition in the folder {source}, so the archive is not a skin", file=sys.stderr)

    written = package(source, target)
    print(f"wrote {target} with {written} entries")


if __name__ == "__main__":
    main()
