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
import sys

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
        rows.append("<div style='color:#caa45a;font-size:13px'>comparison incomplete</div>")
    for v in result.bonus_items:
        val = f"{v.total:.1f} {base}" if v.known else "?"
        bname = html.escape(v.name)
        rows.append(
            "<div style='color:#8a8a8a;font-size:13px'>"
            f"+ bonus: {v.qty}x {bname} &mdash; {val}</div>"
        )
    if stale:
        rows.append("<div style='color:#caa45a;font-size:13px'>&#9888; stale prices</div>")
    return "".join(rows)


def build_inline_overlay(base: str, *, icon_path=None):
    """Full-monitor, transparent, click-through overlay that paints a value chip
    at the end of each reward row (positions mapped from the OCR boxes).

    Receives per-row appraisals (with OCR boxes in ROI pixels) plus the anchor
    (ROI rect + frame size) and maps each row to monitor-local coordinates. If
    icon_path is given, the value is shown as "<n> [base-icon]".
    """
    from PySide6.QtCore import QRectF, Qt, Signal, Slot
    from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
    from PySide6.QtWidgets import QApplication, QWidget

    BEST = QColor("#7CFC8A")
    KNOWN = QColor("#e8e8e8")
    DIM = QColor("#9a9a9a")
    ICON_H = 20

    class InlineOverlay(QWidget):
        _show = Signal(object, object)
        _hide = Signal()

        def __init__(self):
            super().__init__()
            self.base = base
            # (text, x, y, color, show_icon)
            self._chips: list[tuple[str, float, float, QColor, bool]] = []
            self._icon = None
            if icon_path is not None:
                pm = QPixmap(str(icon_path))
                if not pm.isNull():
                    self._icon = pm.scaledToHeight(
                        ICON_H, Qt.SmoothTransformation
                    )
            flags = Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
            if sys.platform.startswith("linux"):
                flags |= Qt.X11BypassWindowManagerHint
            self.setWindowFlags(flags)
            self.setAttribute(Qt.WA_TranslucentBackground, True)
            self.setAttribute(Qt.WA_ShowWithoutActivating, True)
            self.setWindowFlag(Qt.WindowTransparentForInput, True)
            self._font = QFont("DejaVu Sans")
            self._font.setPixelSize(18)
            self._font.setBold(True)
            self._show.connect(self._apply_show)
            self._hide.connect(self._apply_hide)

        def post_rows(self, rows, anchor) -> None:
            self._show.emit(rows, anchor)

        def post_hide(self) -> None:
            self._hide.emit()

        def _screen_for_frame(self, fw: int, fh: int):
            for s in QApplication.screens():
                g = s.geometry()
                if g.width() == fw and g.height() == fh:
                    return s
            return QApplication.primaryScreen()

        @Slot(object, object)
        def _apply_show(self, rows, anchor) -> None:
            rl, rt, rw, rh, fw, fh = anchor
            self.setGeometry(self._screen_for_frame(fw, fh).geometry())
            has_icon = self._icon is not None
            chips = []
            for r in rows:
                v = r.valuation
                if r.box is None:
                    continue
                x = rl + r.box[2] + 10            # just right of the row text
                y = rt + (r.box[1] + r.box[3]) / 2
                if v.known:
                    num = f"{v.total:.1f}"
                    label = (f"+{num}" if v.is_bonus else num) if has_icon else (
                        f"+{num} {self.base}" if v.is_bonus else f"{num} {self.base}"
                    )
                    color = DIM if v.is_bonus else (BEST if v.is_best else KNOWN)
                    show_icon = has_icon
                else:
                    label, color, show_icon = "?", DIM, False
                chips.append((label, float(x), float(y), color, show_icon))
            self._chips = chips
            self.update()
            self.show()
            self.raise_()

        @Slot()
        def _apply_hide(self) -> None:
            self._chips = []
            self.hide()

        def paintEvent(self, _event) -> None:
            if not self._chips:
                return
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing)
            p.setFont(self._font)
            fm = p.fontMetrics()
            pad, gap = 9, 5
            iw = (self._icon.width() if self._icon is not None else 0)
            h = max(fm.height(), ICON_H) + 8
            for label, x, y, color, show_icon in self._chips:
                tw = fm.horizontalAdvance(label)
                w = pad + tw + (gap + iw if show_icon else 0) + pad
                top = y - h / 2
                p.setBrush(QColor(20, 18, 14, 225))
                p.setPen(QColor(90, 74, 42))
                p.drawRoundedRect(QRectF(x, top, w, h), 7, 7)
                p.setPen(color)
                p.drawText(QRectF(x + pad, top, tw, h), Qt.AlignVCenter | Qt.AlignLeft, label)
                if show_icon and self._icon is not None:
                    iy = y - self._icon.height() / 2
                    p.drawPixmap(int(x + pad + tw + gap), int(iy), self._icon)
            p.end()

    return InlineOverlay()


def build_overlay(base: str, *, position: str = "top-right", opacity: float = 0.92):
    """Construct the overlay widget (imports PySide6 lazily). Returns the widget.

    The widget exposes thread-safe post_result(result)/post_hide() that emit Qt
    signals delivered on the GUI thread.
    """
    from PySide6.QtCore import Qt, Signal, Slot
    from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

    class CornerOverlay(QWidget):
        _show = Signal(object, bool, object)
        _hide = Signal()

        def __init__(self):
            super().__init__()
            self.base = base
            self.position = position
            flags = Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
            if sys.platform.startswith("linux"):
                # override-redirect: stay above a fullscreen game without a
                # focus change (alt-tab), like a classic X11 HUD overlay.
                flags |= Qt.X11BypassWindowManagerHint
            self.setWindowFlags(flags)
            self.setAttribute(Qt.WA_TranslucentBackground, True)
            self.setAttribute(Qt.WA_ShowWithoutActivating, True)
            # passive HUD: never intercept mouse/keyboard
            self.setWindowFlag(Qt.WindowTransparentForInput, True)

            self._label = QLabel(self)
            self._label.setTextFormat(Qt.RichText)
            self._label.setMinimumWidth(320)
            self._label.setStyleSheet(
                "QLabel{"
                f"background:rgba(20,18,14,{int(opacity * 255)});"
                "color:#e8e8e8;border:2px solid #5a4a2a;border-radius:10px;"
                "padding:12px 16px;font-family:'DejaVu Sans',sans-serif;font-size:17px;}"
            )
            lay = QVBoxLayout(self)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.addWidget(self._label)

            self._show.connect(self._apply_show)
            self._hide.connect(self._apply_hide)

        # thread-safe entry points (called from the capture worker thread)
        def post_result(self, result: EvalResult, stale: bool = False, anchor=None) -> None:
            self._show.emit(result, stale, anchor)

        def post_hide(self) -> None:
            self._hide.emit()

        @Slot(object, bool, object)
        def _apply_show(self, result: EvalResult, stale: bool, anchor) -> None:
            self._label.setText(result_to_html(result, self.base, stale=stale))
            self.adjustSize()
            self._reposition(anchor)
            self.show()
            self.raise_()

        @Slot()
        def _apply_hide(self) -> None:
            self.hide()

        def _screen_for_frame(self, fw: int, fh: int):
            for s in QApplication.screens():
                g = s.geometry()
                if g.width() == fw and g.height() == fh:
                    return s
            return QApplication.primaryScreen()

        def _reposition(self, anchor=None) -> None:
            if anchor is not None:
                self._anchor_near_panel(anchor)
            else:
                self._anchor_corner(QApplication.primaryScreen().geometry())

        def _anchor_near_panel(self, anchor) -> None:
            rl, rt, rw, rh, fw, fh = anchor
            g = self._screen_for_frame(fw, fh).geometry()
            margin = 12
            # to the right of the reward column, aligned with its top
            x = g.left() + rl + rw + margin
            y = g.top() + rt
            if x + self.width() > g.right():  # no room right -> left of the panel
                x = g.left() + rl - self.width() - margin
            x = max(g.left() + margin, x)
            y = min(y, g.bottom() - self.height() - margin)
            self.move(x, y)

        def _anchor_corner(self, screen) -> None:
            margin = 16
            x = screen.left() + margin
            y = screen.top() + margin
            if "right" in self.position:
                x = screen.right() - self.width() - margin
            if "bottom" in self.position:
                y = screen.bottom() - self.height() - margin
            self.move(x, y)

    return CornerOverlay()
