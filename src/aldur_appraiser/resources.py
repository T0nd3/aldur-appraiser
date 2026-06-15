"""Resolve bundled resources both from source and from a PyInstaller bundle.

When frozen (the Windows .exe), data files live under sys._MEIPASS instead of
the repo tree, so resource lookups must go through here.
"""

from __future__ import annotations

import sys
from pathlib import Path


def resource_path(relative: str) -> Path:
    """Absolute path to a bundled resource (config.toml, assets/…)."""
    base = getattr(sys, "_MEIPASS", None)
    if base:  # running inside a PyInstaller onefile/onedir bundle
        return Path(base) / relative
    # running from source: repo root is two levels above this file
    return Path(__file__).resolve().parents[2] / relative
