"""Cross-platform screen capture via mss.

mss works on Windows and on Linux X11/XWayland. PoE2 runs through Proton, i.e.
XWayland, so mss grabs it directly. On a pure-Wayland compositor mss may fail to
see app windows; an xdg-desktop-portal ScreenCast backend is the documented
Linux fallback (future work).

The grab/array conversion is split from the mss call so the geometry and
BGRA->BGR handling stay unit-testable without a live display.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Region:
    left: int
    top: int
    width: int
    height: int

    def to_mss(self) -> dict:
        return {"left": self.left, "top": self.top, "width": self.width, "height": self.height}


class CaptureError(RuntimeError):
    pass


def _to_bgr(raw: np.ndarray) -> np.ndarray:
    """mss yields BGRA; drop alpha to BGR (OpenCV's native order)."""
    if raw.ndim == 3 and raw.shape[2] == 4:
        return np.ascontiguousarray(raw[:, :, :3])
    return raw


class ScreenCapture:
    """Holds a persistent mss instance (re-creating it per frame is costly)."""

    def __init__(self, monitor: int = 1):
        import mss

        self._sct = mss.mss()
        self.monitor = monitor

    @property
    def monitors(self) -> list[dict]:
        # index 0 is the virtual "all monitors" rect; 1..n are physical.
        return self._sct.monitors

    def monitor_region(self, monitor: int | None = None) -> Region:
        mon = self._sct.monitors[monitor if monitor is not None else self.monitor]
        return Region(mon["left"], mon["top"], mon["width"], mon["height"])

    def grab(self, region: Region | None = None) -> np.ndarray:
        """Return a BGR frame of `region`, or the configured monitor if None."""
        box = (region or self.monitor_region()).to_mss()
        shot = self._sct.grab(box)
        return _to_bgr(np.asarray(shot))

    def assert_capturable(self) -> None:
        """Fail fast on a black/empty frame (the classic exclusive-fullscreen trap)."""
        frame = self.grab()
        if frame.size == 0:
            raise CaptureError("capture returned an empty frame")
        if int(frame.max()) == 0:
            raise CaptureError(
                "capture frame is all black — is the game in exclusive fullscreen? "
                "Switch PoE2 to borderless/windowed fullscreen."
            )

    def close(self) -> None:
        self._sct.close()

    def __enter__(self) -> ScreenCapture:
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def default_backend() -> str:
    """'portal' on Linux/Wayland (mss can't read the screen there), else 'mss'."""
    if sys.platform.startswith("linux") and os.environ.get("WAYLAND_DISPLAY"):
        return "portal"
    return "mss"


def open_capture(monitor: int = 1, *, backend: str | None = None):
    """Return a capture backend (use as a context manager).

    Both backends expose grab(region)/assert_capturable()/close() and the
    context-manager protocol, so callers stay backend-agnostic.
    """
    chosen = backend or default_backend()
    if chosen == "portal":
        from aldur_appraiser.vision.portal_capture import PortalScreenCast

        return PortalScreenCast()
    return ScreenCapture(monitor=monitor)
