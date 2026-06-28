"""Global keyboard hotkey on Windows via Win32 ``RegisterHotKey``.

Unlike Wayland, Windows lets an ordinary app claim a system-wide key combo
while another window (the game) is focused, so no portal / IPC-socket dance is
needed — we register the combo with the OS and get a ``WM_HOTKEY`` message when
it fires. Read-only: ``RegisterHotKey`` only tells us *our* combo was pressed,
it never reads raw keyboard input.

Best-effort and isolated: any failure (non-Windows, combo already taken, parse
error) returns None so the caller falls back to the tray trigger.
"""

from __future__ import annotations

import sys
import threading
from collections.abc import Callable

# Win32 modifier flags for RegisterHotKey.
_MOD_ALT = 0x0001
_MOD_CONTROL = 0x0002
_MOD_SHIFT = 0x0004
_MOD_WIN = 0x0008
_MOD_NOREPEAT = 0x4000

_WM_HOTKEY = 0x0312
_WM_QUIT = 0x0012

_MOD_NAMES = {
    "control": _MOD_CONTROL, "primary": _MOD_CONTROL, "ctrl": _MOD_CONTROL,
    "alt": _MOD_ALT, "shift": _MOD_SHIFT, "super": _MOD_WIN, "logo": _MOD_WIN,
    "win": _MOD_WIN, "meta": _MOD_WIN,
}

# Virtual-key codes for non-printable keys we want to allow.
_VK_NAMED = {
    "space": 0x20, "tab": 0x09, "return": 0x0D, "enter": 0x0D, "escape": 0x1B,
    "esc": 0x1B, "insert": 0x2D, "delete": 0x2E, "home": 0x24, "end": 0x23,
    "pageup": 0x21, "pagedown": 0x22, "up": 0x26, "down": 0x28, "left": 0x25,
    "right": 0x27,
}


def parse_accelerator(accel: str) -> tuple[int, int] | None:
    """Convert a GTK accelerator ("<Control><Alt>p") to (modifiers, vk) for
    RegisterHotKey, or None if it can't be parsed."""
    import re

    mods = 0
    for name in re.findall(r"<([^>]+)>", accel):
        flag = _MOD_NAMES.get(name.lower())
        if flag is None:
            return None
        mods |= flag
    key = re.sub(r"<[^>]+>", "", accel).strip()
    if not key:
        return None
    low = key.lower()
    if low in _VK_NAMED:
        vk = _VK_NAMED[low]
    elif len(low) == 2 and low[0] == "f" and low[1:].isdigit():
        vk = 0x70 + int(low[1:]) - 1  # F1..F12 -> 0x70..0x7B
    elif low[0] == "f" and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
        vk = 0x70 + int(key[1:]) - 1
    elif len(key) == 1 and (key.isalnum()):
        vk = ord(key.upper())  # A-Z / 0-9 share their ASCII as the VK code
    else:
        return None
    if mods == 0:
        return None  # a bare key would hijack normal typing — require a modifier
    return mods | _MOD_NOREPEAT, vk


class WinHotkey:
    """Owns a thread running a Win32 message loop that fires ``callback`` when
    the registered combo is pressed."""

    def __init__(self, callback: Callable[[], None], mods: int, vk: int):
        self._callback = callback
        self._mods = mods
        self._vk = vk
        self._thread: threading.Thread | None = None
        self._thread_id = 0
        self._ready = threading.Event()
        self._ok = False

    def start(self, *, timeout_s: float = 4.0) -> bool:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._ready.wait(timeout_s)
        return self._ok

    def stop(self) -> None:
        if self._thread_id:
            import ctypes

            ctypes.windll.user32.PostThreadMessageW(self._thread_id, _WM_QUIT, 0, 0)

    def _run(self) -> None:
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            self._thread_id = kernel32.GetCurrentThreadId()
            # id 1 is arbitrary but unique within this thread.
            if not user32.RegisterHotKey(None, 1, self._mods, self._vk):
                self._ok = False
                self._ready.set()
                return
            self._ok = True
            self._ready.set()

            msg = wintypes.MSG()
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
                if msg.message == _WM_HOTKEY:
                    try:
                        self._callback()
                    except Exception:  # noqa: BLE001 - never kill the loop
                        pass
            user32.UnregisterHotKey(None, 1)
        except Exception:  # noqa: BLE001 - any failure -> caller uses the tray
            self._ok = False
            self._ready.set()


def start_global_hotkey(
    callback: Callable[[], None], *, accelerator: str
) -> WinHotkey | None:
    """Register ``accelerator`` as a system-wide hotkey; returns a handle to keep
    alive, or None if not on Windows / the combo couldn't be claimed."""
    if not sys.platform.startswith("win"):
        return None
    parsed = parse_accelerator(accelerator)
    if parsed is None:
        return None
    try:
        hk = WinHotkey(callback, *parsed)
        return hk if hk.start() else None
    except Exception:  # noqa: BLE001
        return None
