"""Orchestration loop: capture -> detect -> OCR -> price -> render.

The per-frame work is split into AppraiserLoop.step() (pure, testable with a
fed frame) and run() (the timed capture loop). Rendering goes through callbacks
so the same loop drives the console now and an overlay later.

A frame-diff gate avoids re-running OCR (and re-rendering) while the panel
content is unchanged, which keeps CPU low at the poll rate.
"""

from __future__ import annotations

import sys
import time
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from aldur_appraiser.pipeline import Appraisal, appraise_roi_rows, rows_to_result
from aldur_appraiser.pricing.client import PriceTable
from aldur_appraiser.pricing.valuation import EvalResult, divine_rate, format_value
from aldur_appraiser.vision import ocr
from aldur_appraiser.vision.detect import PanelDetector

# ROI is downsampled to this many cells per side for the change signature.
_SIG_SIZE = 24
_SIG_EPS = 4.0  # mean abs per-cell delta above which the ROI is "changed"


def _signature(roi: np.ndarray) -> np.ndarray:
    import cv2

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if roi.ndim == 3 else roi
    return cv2.resize(gray, (_SIG_SIZE, _SIG_SIZE), interpolation=cv2.INTER_AREA).astype(np.float32)


def _changed(a: np.ndarray | None, b: np.ndarray) -> bool:
    return a is None or a.shape != b.shape or float(np.abs(a - b).mean()) > _SIG_EPS


@dataclass
class AppraiserLoop:
    prices: PriceTable
    detector: PanelDetector
    engine: ocr.OcrEngine
    # on_result(appraisal): carries the ranked result (corner/console), per-row
    # data (inline overlay), and the anchor mapping ROI pixels to the screen.
    on_result: Callable[[Appraisal], None]
    on_hide: Callable[[], None]
    score_cutoff: int = 80

    _last_sig: np.ndarray | None = None
    _panel_visible: bool = False

    def step(self, frame: np.ndarray) -> EvalResult | None:
        """Process one frame. Returns the result if (re)evaluated, else None."""
        panel = self.detector.find_panel(frame)
        if panel is None:
            if self._panel_visible:
                self._panel_visible = False
                self._last_sig = None
                self.on_hide()
            return None

        rect = panel.reward_roi()
        roi = self.detector.reward_image(frame, panel)
        sig = _signature(roi)
        if not _changed(self._last_sig, sig):
            return None  # panel open but unchanged -> skip OCR

        self._last_sig = sig
        self._panel_visible = True
        rows = appraise_roi_rows(
            roi, self.prices, engine=self.engine, score_cutoff=self.score_cutoff
        )
        result = rows_to_result(rows)
        anchor = (rect.left, rect.top, rect.width, rect.height, frame.shape[1], frame.shape[0])
        self.on_result(Appraisal(result=result, rows=rows, anchor=anchor))
        return result

    def run(self, capture, *, poll_fps: float = 3.0, region=None) -> None:
        """Timed capture loop until interrupted."""
        interval = 1.0 / poll_fps
        while True:
            t0 = time.monotonic()
            frame = capture.grab(region)
            self.step(frame)
            dt = time.monotonic() - t0
            if dt < interval:
                time.sleep(interval - dt)


# --- console rendering -------------------------------------------------------


def _fmt(total: float, base: str, dr: float | None) -> str:
    val, unit = format_value(total, dr, base_unit=base)
    return f"{val:.2f} {unit}"


def render_console(
    result: EvalResult, *, base: str, stale: bool = False, dr: float | None = None
) -> str:
    if not result.items:
        return "Panel open — no reward options recognised."
    lines = [f"Reward ranking (base={base}){' [STALE PRICES]' if stale else ''}:"]
    for v in result.items:
        marker = "  <-- BEST" if v.is_best else ""
        if v.known:
            lines.append(f"  {v.qty}x {v.name:<26} {_fmt(v.total, base, dr):>14}{marker}")
        else:
            lines.append(f"  {v.qty}x {v.name:<26} {'unknown':>14}{marker}")
    if result.incomplete:
        lines.append("  (comparison incomplete: an option has no market price)")
    for v in result.bonus_items:
        val = _fmt(v.total, base, dr) if v.known else "unknown"
        lines.append(f"  + bonus (always paid): {v.qty}x {v.name} — {val}")
    return "\n".join(lines)


@dataclass
class _Setup:
    pc: object
    cached: object
    poll_fps: float
    backend: str


def _prepare(backend: str | None, *, refresh: bool = False) -> _Setup:
    from aldur_appraiser.config import load_config
    from aldur_appraiser.pricing.cache import get_or_fetch
    from aldur_appraiser.vision.capture import default_backend

    cfg = load_config()
    pc = cfg.pricing
    cached = get_or_fetch(
        pc.league,
        pc.base,
        ttl_minutes=0 if refresh else pc.cache_ttl_minutes,
        realm=pc.realm,
        categories=pc.categories,
    )
    poll_fps = float(cfg.raw.get("vision", {}).get("poll_fps", 3))
    return _Setup(pc=pc, cached=cached, poll_fps=poll_fps, backend=backend or default_backend())


def _make_loop(s: _Setup, on_result, on_hide) -> AppraiserLoop:
    return AppraiserLoop(
        prices=s.cached.table,
        detector=PanelDetector(),
        engine=ocr.get_engine(),
        on_result=on_result,
        on_hide=on_hide,
    )


def run_console(*, backend: str | None = None, refresh: bool = False) -> int:
    from aldur_appraiser.vision.capture import open_capture

    s = _prepare(backend, refresh=refresh)
    dr = divine_rate(s.cached.table)

    def _print(appraisal):
        print(render_console(appraisal.result, base=s.pc.base, stale=s.cached.stale, dr=dr) + "\n")

    loop = _make_loop(s, on_result=_print, on_hide=lambda: print("(panel closed)\n"))
    print(f"aldur-appraiser running (backend={s.backend}, league={s.pc.league}, base={s.pc.base}).")
    print("Open a Runeshape Combinations panel in-game. Ctrl+C to stop.\n")
    try:
        with open_capture(backend=s.backend) as cap:
            if hasattr(cap, "assert_capturable"):
                cap.assert_capturable()
            loop.run(cap, poll_fps=s.poll_fps)
    except KeyboardInterrupt:
        print("\nstopped.")
    return 0


def run_overlay(*, backend: str | None = None, style: str = "corner", refresh: bool = False) -> int:
    import os
    import signal
    import threading

    # On Wayland, always-on-top + click-through are honored more reliably under
    # XWayland (xcb) than the native wayland Qt platform; let users override.
    if sys.platform.startswith("linux") and os.environ.get("WAYLAND_DISPLAY"):
        os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

    from PySide6.QtCore import QObject, QTimer, Signal
    from PySide6.QtWidgets import QApplication

    from aldur_appraiser.icons import base_icon_path, currency_icon_paths
    from aldur_appraiser.vision.capture import open_capture
    from aldur_appraiser.vision.overlay import build_inline_overlay, build_overlay

    s = _prepare(backend, refresh=refresh)
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)  # live in the tray, not tied to a window
    stale = s.cached.stale
    dr = divine_rate(s.cached.table)

    tray_icon_path = None
    if style == "inline":
        icons = currency_icon_paths(s.pc.realm, s.pc.league)  # {exalted,divine} best-effort
        tray_icon_path = icons.get("exalted")
        overlay = build_inline_overlay(s.pc.base, icon_paths=icons, divine_rate=dr)
        on_result = lambda a: overlay.post_rows(a.rows, a.anchor)  # noqa: E731
    else:
        tray_icon_path = base_icon_path(s.pc.realm, s.pc.league)
        overlay = build_overlay(s.pc.base)
        on_result = lambda a: overlay.post_result(a.result, stale, a.anchor, dr)  # noqa: E731

    tray = _make_tray(app, s, tray_icon_path)

    # Bridge worker-thread errors to the GUI thread (tray notification).
    class _Bridge(QObject):
        error = Signal(str)

    bridge = _Bridge()
    if tray is not None:
        bridge.error.connect(
            lambda msg: tray.showMessage("Aldur Appraiser", msg, tray.MessageIcon.Critical, 10000)
        )

    def worker() -> None:
        try:
            # Open capture first so the permission dialog appears promptly,
            # before the slower OCR-engine init.
            with open_capture(backend=s.backend) as cap:
                if hasattr(cap, "assert_capturable"):
                    cap.assert_capturable()
                loop = _make_loop(s, on_result=on_result, on_hide=overlay.post_hide)
                loop.run(cap, poll_fps=s.poll_fps)
        except Exception as exc:  # noqa: BLE001 - surface backend errors to the tray
            msg = f"{type(exc).__name__}: {exc}"
            print(f"capture error: {msg}", file=sys.stderr)
            bridge.error.emit(msg)  # keep running so the user sees it and can Quit

    threading.Thread(target=worker, daemon=True).start()

    print(f"aldur-appraiser running in the tray (backend={s.backend}, league={s.pc.league}).")
    print("Open a Runeshape Combinations panel in-game. Right-click the tray icon to quit.")
    # Let Python process SIGINT while the Qt event loop runs.
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    timer = QTimer()
    timer.start(200)
    timer.timeout.connect(lambda: None)
    return app.exec()


def _make_tray(app, setup, icon_path):
    """System-tray icon with a right-click menu (Quit). None if unavailable."""
    from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
    from PySide6.QtWidgets import QMenu, QSystemTrayIcon

    if not QSystemTrayIcon.isSystemTrayAvailable():
        return None

    if icon_path is not None:
        icon = QIcon(str(icon_path))
    else:  # fallback: a simple gold disc
        pm = QPixmap(32, 32)
        pm.fill(QColor(0, 0, 0, 0))
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor("#d9c89a"))
        p.setPen(QColor("#5a4a2a"))
        p.drawEllipse(3, 3, 26, 26)
        p.end()
        icon = QIcon(pm)

    tray = QSystemTrayIcon(icon)
    tray.setToolTip(f"Aldur Appraiser — {setup.pc.league}")
    menu = QMenu()
    title = QAction("Aldur Appraiser")
    title.setEnabled(False)
    menu.addAction(title)
    menu.addSeparator()
    quit_action = QAction("Beenden")
    quit_action.triggered.connect(app.quit)
    menu.addAction(quit_action)
    tray.setContextMenu(menu)
    tray.show()
    return tray


def run_app(
    *, backend: str | None = None, mode: str = "auto", style: str = "corner", refresh: bool = False
) -> int:
    """Entry point for `appraiser run`. mode: auto | overlay | console."""
    if mode == "console":
        return run_console(backend=backend, refresh=refresh)
    try:
        import PySide6  # noqa: F401
    except ImportError:
        if mode == "overlay":
            print("overlay requested but PySide6 is not installed "
                  '(pip install -e ".[overlay]")', file=sys.stderr)
            return 1
        print("overlay unavailable (PySide6 not installed); using console.\n")
        return run_console(backend=backend, refresh=refresh)
    return run_overlay(backend=backend, style=style, refresh=refresh)
