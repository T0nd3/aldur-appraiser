"""Corner-HUD overlay using Qt (PySide6).

A frameless, always-on-top, translucent, click-through window in a screen
corner. Qt is a pip wheel (no system dependency, unlike tkinter on atomic
distros) and handles these window traits well on Wayland/XWayland.

Updates arrive from the capture worker thread via Qt signals, which Qt delivers
to the GUI thread with a queued connection — the thread-safe way to touch
widgets. Heavy import (PySide6) is done lazily by the caller.
"""

from __future__ import annotations

import html

from aldur_appraiser.pricing.valuation import EvalResult


def result_to_html(result: EvalResult, base: str, *, stale: bool = False) -> str:
    """Render an EvalResult as the HUD's HTML body."""
    rows = ["<div style='font-weight:bold;color:#d9c89a'>Aldur Appraiser</div>"]
    if not result.items:
        rows.append("<div style='color:#aaa'>no reward options recognised</div>")
        return "".join(rows)

    for v in result.items:
        name = html.escape(v.name)
        if v.known:
            val = f"{v.total:.1f} {base}"
            if v.is_best:
                rows.append(
                    f"<div style='color:#7CFC8A;font-weight:bold'>&#9656; {v.qty}x {name} "
                    f"&mdash; {val}</div>"
                )
            else:
                rows.append(f"<div style='color:#e8e8e8'>{v.qty}x {name} &mdash; {val}</div>")
        else:
            rows.append(f"<div style='color:#888'>{v.qty}x {name} &mdash; ?</div>")

    if result.incomplete:
        rows.append("<div style='color:#caa45a;font-size:11px'>comparison incomplete</div>")
    if stale:
        rows.append("<div style='color:#caa45a;font-size:11px'>&#9888; stale prices</div>")
    return "".join(rows)


def build_overlay(base: str, *, position: str = "top-right", opacity: float = 0.92):
    """Construct the overlay widget (imports PySide6 lazily). Returns the widget.

    The widget exposes thread-safe post_result(result)/post_hide() that emit Qt
    signals delivered on the GUI thread.
    """
    from PySide6.QtCore import Qt, Signal, Slot
    from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

    class CornerOverlay(QWidget):
        _show = Signal(object, bool)
        _hide = Signal()

        def __init__(self):
            super().__init__()
            self.base = base
            self.position = position
            self.setWindowFlags(
                Qt.FramelessWindowHint
                | Qt.WindowStaysOnTopHint
                | Qt.Tool  # keep out of taskbar / alt-tab
            )
            self.setAttribute(Qt.WA_TranslucentBackground, True)
            self.setAttribute(Qt.WA_ShowWithoutActivating, True)
            # passive HUD: never intercept mouse/keyboard
            self.setWindowFlag(Qt.WindowTransparentForInput, True)

            self._label = QLabel(self)
            self._label.setTextFormat(Qt.RichText)
            self._label.setStyleSheet(
                "QLabel{"
                f"background:rgba(20,18,14,{int(opacity * 255)});"
                "color:#e8e8e8;border:1px solid #5a4a2a;border-radius:8px;"
                "padding:8px 12px;font-family:'DejaVu Sans',sans-serif;font-size:13px;}"
            )
            lay = QVBoxLayout(self)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.addWidget(self._label)

            self._show.connect(self._apply_show)
            self._hide.connect(self._apply_hide)

        # thread-safe entry points (called from the capture worker thread)
        def post_result(self, result: EvalResult, stale: bool = False) -> None:
            self._show.emit(result, stale)

        def post_hide(self) -> None:
            self._hide.emit()

        @Slot(object, bool)
        def _apply_show(self, result: EvalResult, stale: bool) -> None:
            self._label.setText(result_to_html(result, self.base, stale=stale))
            self.adjustSize()
            self._reposition()
            self.show()
            self.raise_()

        @Slot()
        def _apply_hide(self) -> None:
            self.hide()

        def _reposition(self) -> None:
            screen = QApplication.primaryScreen().geometry()
            margin = 16
            w = self.width()
            x = screen.left() + margin
            y = screen.top() + margin
            if "right" in self.position:
                x = screen.right() - w - margin
            if "bottom" in self.position:
                y = screen.bottom() - self.height() - margin
            self.move(x, y)

    return CornerOverlay()
