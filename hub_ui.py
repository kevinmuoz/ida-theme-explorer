from __future__ import annotations

import platform
import threading
from typing import List, Optional

import ida_kernwin

from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QLabel,
    QLineEdit,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QFrame,
)

import hub_core

_BG        = "#0d0d0d"
_SURFACE   = "#161616"
_CARD      = "#1c1c1c"
_BORDER    = "#2a2a2a"
_ACCENT    = "#6c8cbf"
_GREEN     = "#5cb985"
_RED       = "#d9534f"
_TEXT      = "#d4d4d4"
_TEXT_DIM  = "#707070"
_TEXT_MUTE = "#4a4a4a"

_HERO_COLORS = [
    "#1a1a2e", "#162028", "#1e1a16", "#161e1a",
    "#1e161e", "#1a1e2e", "#2e1a1a", "#1a2e2e",
]


def _hero_bg(name: str) -> str:
    h = sum(ord(c) for c in name) if name else 0
    return _HERO_COLORS[h % len(_HERO_COLORS)]


def _initials(name: str) -> str:
    parts = name.split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    return name[:2].upper() if name else "?"


_IS_MAC = platform.system() == "Darwin"


def _hero_placeholder() -> str:
    """Emoji on macOS, plain text fallback elsewhere."""
    return "🎨" if _IS_MAC else "#"

class _Bridge(QObject):
    result = Signal(bool, str)
    registry_ready = Signal(list)


_DIALOG_SS = f"""
QDialog {{
    background: {_BG};
    color: {_TEXT};
}}
"""

_LIST_SS = f"""
QListWidget {{
    background: {_SURFACE};
    border: 1px solid {_BORDER};
    border-radius: 6px;
    padding: 4px;
    color: {_TEXT};
    font-size: 13px;
    outline: none;
}}
QListWidget::item {{
    padding: 7px 10px;
    border-radius: 4px;
    margin: 1px 0;
}}
QListWidget::item:selected {{
    background: {_ACCENT}22;
    color: {_TEXT};
}}
QListWidget::item:hover {{
    background: {_BORDER};
}}
"""

_SEARCH_SS = f"""
QLineEdit {{
    background: {_SURFACE};
    border: 1px solid {_BORDER};
    border-radius: 6px;
    padding: 6px 10px;
    color: {_TEXT};
    font-size: 13px;
    selection-background-color: {_ACCENT}44;
}}
QLineEdit:focus {{
    border-color: {_ACCENT};
}}
"""

_BTN_PRIMARY_SS = f"""
QPushButton {{
    background: {_ACCENT};
    color: #fff;
    border: none;
    border-radius: 6px;
    padding: 7px 22px;
    font-size: 13px;
    font-weight: 600;
}}
QPushButton:hover {{
    background: {_ACCENT}cc;
}}
QPushButton:disabled {{
    background: {_BORDER};
    color: {_TEXT_MUTE};
}}
"""

_BTN_DANGER_SS = f"""
QPushButton {{
    background: transparent;
    color: {_RED};
    border: 1px solid {_RED}66;
    border-radius: 6px;
    padding: 7px 18px;
    font-size: 13px;
}}
QPushButton:hover {{
    background: {_RED}18;
}}
QPushButton:disabled {{
    border-color: {_BORDER};
    color: {_TEXT_MUTE};
}}
"""

_BTN_GHOST_SS = f"""
QPushButton {{
    background: {_SURFACE};
    color: {_TEXT_DIM};
    border: 1px solid {_BORDER};
    border-radius: 6px;
    padding: 5px 10px;
    font-size: 13px;
}}
QPushButton:hover {{
    background: {_BORDER};
    color: {_TEXT};
}}
"""

_STATUS_SS = f"""
QLabel {{
    color: {_TEXT_DIM};
    font-size: 11px;
    padding: 2px 0;
}}
"""

class ThemeExplorerDialog(QDialog):

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("IDA Theme Explorer")
        self.setMinimumSize(740, 500)
        self.resize(780, 530)
        self.setStyleSheet(_DIALOG_SS)

        self._themes: List[dict] = []
        self._installed = hub_core.load_installed()
        self._bridge = _Bridge()
        self._bridge.result.connect(self._on_result)
        self._bridge.registry_ready.connect(self._on_registry)
        self._build()
        self._refresh()

    # build
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 8)
        root.setSpacing(8)

        # header
        hdr = QHBoxLayout()
        title = QLabel("Theme Explorer")
        title.setStyleSheet(f"font-size:16px; font-weight:700; color:{_TEXT};")
        hdr.addWidget(title)
        hdr.addStretch()
        self._btn_refresh = QPushButton("↻  Refresh")
        self._btn_refresh.setStyleSheet(_BTN_GHOST_SS)
        self._btn_refresh.clicked.connect(self._refresh)
        hdr.addWidget(self._btn_refresh)
        root.addLayout(hdr)

        # search
        self._search = QLineEdit()
        self._search.setPlaceholderText("  Search themes...")
        self._search.setStyleSheet(_SEARCH_SS)
        self._search.textChanged.connect(self._filter)
        root.addWidget(self._search)

        # splitter
        sp = QSplitter(Qt.Horizontal)
        sp.setHandleWidth(1)
        sp.setStyleSheet(f"QSplitter::handle {{ background: {_BORDER}; }}")

        # left: list
        self._list = QListWidget()
        self._list.setStyleSheet(_LIST_SS)
        self._list.currentRowChanged.connect(self._on_select)
        sp.addWidget(self._list)

        # right: deatil card
        card = QFrame()
        card.setStyleSheet(
            f"QFrame {{ background: {_CARD}; border: 1px solid {_BORDER};"
            f"border-radius: 8px; }}"
        )
        cl = QVBoxLayout(card)
        cl.setContentsMargins(16, 16, 16, 16)
        cl.setSpacing(0)

        # hero block
        self._hero = QLabel()
        self._hero.setFixedHeight(100)
        self._hero.setAlignment(Qt.AlignCenter)
        self._hero.setStyleSheet(
            f"font-size:36px; font-weight:800; color:{_TEXT_MUTE};"
            f"background:{_HERO_COLORS[0]}; border:none;"
            f"border-radius:6px; letter-spacing:4px;"
        )
        self._hero.setText(_hero_placeholder())
        cl.addWidget(self._hero)
        cl.addSpacing(14)

        # name
        self._lbl_name = QLabel()
        self._lbl_name.setStyleSheet(
            f"font-size:20px; font-weight:700; color:{_TEXT}; border:none;"
        )
        cl.addWidget(self._lbl_name)
        cl.addSpacing(2)

        # author
        self._lbl_author = QLabel()
        self._lbl_author.setStyleSheet(
            f"font-size:12px; color:{_TEXT_DIM}; border:none;"
        )
        cl.addWidget(self._lbl_author)
        cl.addSpacing(10)

        # description
        self._lbl_desc = QLabel()
        self._lbl_desc.setWordWrap(True)
        self._lbl_desc.setStyleSheet(
            f"font-size:13px; color:{_TEXT}; border:none; line-height:1.4;"
        )
        cl.addWidget(self._lbl_desc)
        cl.addSpacing(12)

        # separator
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{_BORDER}; border:none;")
        cl.addWidget(sep)
        cl.addSpacing(10)

        # meta grid
        self._lbl_meta = QLabel()
        self._lbl_meta.setWordWrap(True)
        self._lbl_meta.setOpenExternalLinks(True)
        self._lbl_meta.setStyleSheet(
            f"font-size:12px; color:{_TEXT_DIM}; border:none; line-height:1.6;"
        )
        cl.addWidget(self._lbl_meta)

        cl.addStretch()

        # action buttons
        btns = QHBoxLayout()
        btns.setSpacing(8)
        self._btn_install = QPushButton("Install Theme")
        self._btn_install.setStyleSheet(_BTN_PRIMARY_SS)
        self._btn_install.clicked.connect(self._on_install)
        self._btn_uninstall = QPushButton("Uninstall")
        self._btn_uninstall.setStyleSheet(_BTN_DANGER_SS)
        self._btn_uninstall.clicked.connect(self._on_uninstall)
        btn_colors = QPushButton("Open Colors...")
        btn_colors.setStyleSheet(_BTN_GHOST_SS)
        btn_colors.setToolTip("Open IDA's color/theme selector")
        btn_colors.clicked.connect(self._open_colors)
        btns.addWidget(self._btn_install)
        btns.addWidget(self._btn_uninstall)
        btns.addStretch()
        btns.addWidget(btn_colors)
        cl.addLayout(btns)

        sp.addWidget(card)
        sp.setStretchFactor(0, 2)
        sp.setStretchFactor(1, 3)
        root.addWidget(sp, 1)

        # status bar
        self._status = QLabel("")
        self._status.setStyleSheet(_STATUS_SS)
        root.addWidget(self._status)

        # initial state
        self._btn_install.setEnabled(False)
        self._btn_uninstall.setEnabled(False)
        self._clear_detail()

    def _clear_detail(self) -> None:
        self._hero.setText(_hero_placeholder())
        self._hero.setStyleSheet(
            f"font-size:36px; font-weight:800; color:{_TEXT_MUTE};"
            f"background:{_HERO_COLORS[0]}; border:none;"
            f"border-radius:6px; letter-spacing:4px;"
        )
        self._lbl_name.setText("Select a theme")
        self._lbl_author.setText("")
        self._lbl_desc.setText("Choose a theme from the list to see details.")
        self._lbl_meta.setText("")

    def _log(self, msg: str, error: bool = False) -> None:
        c = _RED if error else _TEXT_DIM
        self._status.setText(f'<span style="color:{c}">{msg}</span>')
        ida_kernwin.msg(f"[ThemeExplorer] {msg}\n")

    def _refresh(self) -> None:
        self._log("Fetching registry...")
        self._btn_refresh.setEnabled(False)

        def w():
            try:
                t = hub_core.fetch_registry()
            except Exception:
                t = hub_core.fetch_registry_bundled()
            self._bridge.registry_ready.emit(t)

        threading.Thread(target=w, daemon=True).start()

    def _on_registry(self, themes: list) -> None:
        self._themes = themes
        self._installed = hub_core.load_installed()
        self._filter()
        self._btn_refresh.setEnabled(True)
        self._log(f"{len(themes)} themes available")

    # filter
    def _filter(self) -> None:
        q = self._search.text().strip().lower()
        self._list.clear()

        for t in self._themes:
            if q and q not in (
                t.get("name", "") + t.get("author", "") +
                t.get("description", "")
            ).lower():
                continue

            tid = t.get("id", "")
            name = t.get("name", tid)
            inst = tid in self._installed

            item = QListWidgetItem()
            label = f"  {'✓ ' if inst else ''}{name}"
            item.setText(label)
            item.setData(Qt.UserRole, t)
            if inst:
                item.setForeground(QColor(_GREEN))
            self._list.addItem(item)

    # selection
    def _sel(self) -> Optional[dict]:
        it = self._list.currentItem()
        return it.data(Qt.UserRole) if it else None

    def _on_select(self, row: int) -> None:
        t = self._sel()
        if not t:
            self._clear_detail()
            return

        tid = t.get("id", "")
        name = t.get("name", tid)
        inst = tid in self._installed
        repo = t.get("repo", "")

        # hero with initials and bg colro
        ini = _initials(name)
        bg = _hero_bg(name)
        self._hero.setText(ini)
        self._hero.setStyleSheet(
            f"font-size:32px; font-weight:800; color:{_ACCENT};"
            f"background:{bg}; border:none;"
            f"border-radius:6px; letter-spacing:6px;"
        )

        self._lbl_name.setText(name)
        self._lbl_author.setText(f"by {t.get('author', '—')}")
        self._lbl_desc.setText(t.get("description", ""))

        # meta block
        status_color = _GREEN if inst else _TEXT_MUTE
        status_text = "Installed" if inst else "Not installed"
        status_dot = "●" if inst else "○"

        meta_lines = [
            f'<span style="color:{status_color}">{status_dot} {status_text}</span>',
        ]
        if repo:
            meta_lines.append(
                f'<b style="color:{_TEXT_DIM}">Repository</b> '
                f'<a href="https://github.com/{repo}" '
                f'style="color:{_ACCENT}; text-decoration:none;">{repo}</a>'
            )
        if inst:
            import os
            dest = os.path.join(hub_core.themes_dir(), tid)
            meta_lines.append(
                f'<b style="color:{_TEXT_DIM}">Path</b> '
                f'<span style="color:{_TEXT_DIM}">{dest}</span>'
            )
        meta_lines.append(
            f'<b style="color:{_TEXT_DIM}">Theme ID</b> '
            f'<span style="color:{_TEXT_DIM}">{tid}</span>'
        )

        self._lbl_meta.setText("<br>".join(meta_lines))

        self._btn_install.setEnabled(not inst)
        self._btn_uninstall.setEnabled(inst)

    # actions
    @staticmethod
    def _open_colors() -> None:
        """Open IDA's Options > Colors dialog."""
        ida_kernwin.process_ui_action("SetColors")

    def _on_install(self) -> None:
        t = self._sel()
        if not t:
            return
        self._log(f"Installing '{t.get('name')}'...")
        self._busy(True)

        def w():
            ok, msg = hub_core.install_theme(t)
            self._bridge.result.emit(ok, msg)

        threading.Thread(target=w, daemon=True).start()

    def _on_uninstall(self) -> None:
        t = self._sel()
        if not t:
            return
        tid = t.get("id", "")
        if tid not in self._installed:
            return
        if QMessageBox.question(
            self, "Uninstall",
            f"Remove theme '{t.get('name')}'?",
            QMessageBox.Yes | QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        self._log(f"Removing '{t.get('name')}'...")
        self._busy(True)

        def w():
            ok, msg = hub_core.uninstall_theme(tid)
            self._bridge.result.emit(ok, msg)

        threading.Thread(target=w, daemon=True).start()

    # result
    def _on_result(self, ok: bool, msg: str) -> None:
        self._busy(False)
        self._installed = hub_core.load_installed()
        self._filter()
        row = self._list.currentRow()
        if row >= 0:
            self._on_select(row)

        if ok:
            self._log(msg.split("\n")[0])
            QMessageBox.information(self, "Theme Explorer", msg)
        else:
            self._log(msg.split("\n")[0], error=True)
            QMessageBox.warning(self, "Theme Explorer", msg)

    def _busy(self, b: bool) -> None:
        e = not b
        self._btn_install.setEnabled(e)
        self._btn_uninstall.setEnabled(e)
        self._btn_refresh.setEnabled(e)