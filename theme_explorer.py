from __future__ import annotations

import os
from typing import Optional

import ida_kernwin
import idaapi

import hub_ui

PLUGIN_NAME = "Theme Explorer"
_ICON_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.png")


def LOG(msg: str) -> None:
    ida_kernwin.msg(f"[ThemeExplorer] {msg}\n")


class OnUpdatedActionsHook(ida_kernwin.UI_Hooks):
    def __init__(self, cb):
        super().__init__()
        self.cb = cb

    def updated_actions(self):
        if self.cb():
            self.unhook()


def install_plugin_menu_icon() -> bool:
    action_name = f"Edit/Plugins/{PLUGIN_NAME}"

    if action_name not in ida_kernwin.get_registered_actions():
        return False

    if not os.path.isfile(_ICON_FILE):
        return False

    try:
        with open(_ICON_FILE, "rb") as f:
            icon_data = f.read()

        icon_id = ida_kernwin.load_custom_icon(data=icon_data, format="png")
        if icon_id < 0:
            return False

        ida_kernwin.update_action_icon(action_name, icon_id)
        LOG(f"updated icon for {action_name} -> {icon_id}")
        return True
    except Exception as e:
        LOG(f"failed to set plugin menu icon: {e}")
        return False


_icon_hook = OnUpdatedActionsHook(install_plugin_menu_icon)
_icon_hook.hook()


class OpenAction(idaapi.action_handler_t):
    NAME = "themeexplorer:open"
    LABEL = "Theme Explorer"

    def __init__(self, plugin: "ThemeExplorerPlugin") -> None:
        super().__init__()
        self._plugin = plugin

    def activate(self, ctx) -> int:
        self._plugin.open_dialog()
        return 1

    def update(self, ctx) -> int:
        return ida_kernwin.AST_ENABLE_ALWAYS


class ThemeExplorerPlugin(idaapi.plugin_t):
    flags = idaapi.PLUGIN_KEEP
    comment = "Browse and install community IDA themes"
    help = "Opens a dialog to discover and manage IDA color themes"
    wanted_name = PLUGIN_NAME
    wanted_hotkey = "Ctrl+Alt+T"

    def __init__(self) -> None:
        super().__init__()
        self._dlg: Optional[hub_ui.ThemeExplorerDialog] = None
        self._icon_id: int = -1

    def open_dialog(self) -> None:
        if self._dlg is not None:
            self._dlg.showNormal()
            self._dlg.raise_()
            self._dlg.activateWindow()
            return

        self._dlg = hub_ui.ThemeExplorerDialog()
        if os.path.isfile(_ICON_FILE):
            from PySide6.QtGui import QIcon
            self._dlg.setWindowIcon(QIcon(_ICON_FILE))
        self._dlg.finished.connect(self._on_closed)
        self._dlg.show()

    def _on_closed(self) -> None:
        self._dlg = None

    def init(self) -> int:
        try:
            LOG("init()")

            self._icon_id = -1
            if os.path.isfile(_ICON_FILE):
                with open(_ICON_FILE, "rb") as f:
                    icon_data = f.read()
                self._icon_id = ida_kernwin.load_custom_icon(
                    data=icon_data, format="png"
                )
                LOG(f"icon id: {self._icon_id}")

            act = OpenAction(self)
            idaapi.register_action(
                idaapi.action_desc_t(
                    OpenAction.NAME,
                    OpenAction.LABEL,
                    act,
                    self.wanted_hotkey,
                    "Browse and install IDA themes",
                    self._icon_id if self._icon_id >= 0 else -1,
                )
            )

            try:
                idaapi.attach_action_to_menu(
                    "Edit/Plugins/",
                    OpenAction.NAME,
                    idaapi.SETMENU_APP,
                )
            except Exception as e:
                LOG(f"menu: {e}")

            LOG("ready (Ctrl+Shift+Alt+T)")
            return idaapi.PLUGIN_KEEP

        except Exception as e:
            LOG(f"init failed: {e}")
            return idaapi.PLUGIN_SKIP

    def run(self, arg: int) -> None:
        self.open_dialog()

    def term(self) -> None:
        try:
            idaapi.unregister_action(OpenAction.NAME)
        except Exception:
            pass

        if self._icon_id >= 0:
            try:
                ida_kernwin.free_custom_icon(self._icon_id)
            except Exception:
                pass
            self._icon_id = -1

        if self._dlg:
            self._dlg.close()
        self._dlg = None


def PLUGIN_ENTRY():
    return ThemeExplorerPlugin()