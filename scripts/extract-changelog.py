#!/usr/bin/env python3
"""Extract the changelog section for a given version from CHANGELOG.md."""

import re
import sys


def main():
    version = sys.argv[1]
    try:
        with open("CHANGELOG.md") as f:
            content = f.read()
    except FileNotFoundError:
        print("CHANGELOG.md not found", file=sys.stderr)
        sys.exit(1)
    pattern = rf"## \[{re.escape(version)}\].*?(?=## \[|$)"
    match = re.search(pattern, content, re.DOTALL)
    if match:
        section = match.group(0)
        lines = section.strip().split("\n")
        lines[0] = f"# Version {version}"
        print("\n".join(lines))
    else:
        print(f"No changelog section found for version {version}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
