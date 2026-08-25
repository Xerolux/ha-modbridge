#!/usr/bin/env python3
"""Sync the integration version with the upstream ModBridge project.

Reads version.txt from a local modbridge checkout (default: sibling directory)
and updates every place that must stay in sync with the original version:

  - custom_components/modbridge/manifest.json  -> version
  - README.md                                  -> version badge & text
  - hacs.json                                  -> unchanged (informational)

Usage:
    python scripts/sync_version.py [path/to/modbridge]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "custom_components" / "modbridge" / "manifest.json"
README = ROOT / "README.md"


def get_upstream_version() -> str:
    """Read the version from the local modbridge checkout."""
    if len(sys.argv) > 1:
        version_file = Path(sys.argv[1]) / "version.txt"
    else:
        version_file = ROOT.parent / "modbridge" / "version.txt"

    if not version_file.is_file():
        print(f"ERROR: {version_file} not found")
        print("Pass the modbridge path as argument: python scripts/sync_version.py ../modbridge")
        sys.exit(1)

    version = version_file.read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"\d+(\.\d+)*", version):
        print(f"ERROR: invalid version in {version_file}: {version!r}")
        sys.exit(1)
    return version


def current_version() -> str | None:
    """Return the currently stored integration version."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return manifest.get("version")


def update_manifest(version: str) -> None:
    """Write the new version into the manifest."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest["version"] = version
    MANIFEST.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"manifest.json -> {version}")


def update_readme(version: str) -> None:
    """Update version mentions in README.md."""
    if not README.is_file():
        return
    text = README.read_text(encoding="utf-8")
    text = re.sub(
        r"(?<=/Xerolux/ha-modbridge/blob/)[^/]+(?=/README\.md)",
        f"v{version}",
        text,
    )
    text = re.sub(
        r"(?<=badge/version-)[^-]+(?=-blue)",
        f"v{version}",
        text,
    )
    text = re.sub(
        r"(?<=\*\*Version:\*\* )[^\s|]+",
        f"v{version}",
        text,
    )
    README.write_text(text, encoding="utf-8")
    print(f"README.md -> v{version}")


def main() -> None:
    """Run the sync."""
    version = get_upstream_version()
    if version == current_version():
        print(f"Already in sync: {version}")
        return
    update_manifest(version)
    update_readme(version)
    print(f"Synced to ModBridge v{version}")


if __name__ == "__main__":
    main()
