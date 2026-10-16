"""
AirBridge - Windows System Tray Integration
Allows background execution, quick screenshot beaming, and folder access
Created by Chathunga
"""

import os
import subprocess
from pathlib import Path
from typing import Callable, Optional

from gui.qt_compat import QtWidgets, QtGui, QtCore
from core.config import settings, APP_NAME, CREATOR, DOWNLOADS_DIR, ASSETS_DIR


class AirBridgeTrayIcon(QtWidgets.QSystemTrayIcon):
    """System Tray Icon for AirBridge with quick actions and notification bubbles."""

    def __init__(
        self,
        icon: QtGui.QIcon,
        parent: Optional[QtWidgets.QWidget] = None,
        on_show_window: Optional[Callable[[], None]] = None,
        on_beam_screenshot: Optional[Callable[[], None]] = None,
        on_push_clipboard: Optional[Callable[[], None]] = None,
        on_quit_app: Optional[Callable[[], None]] = None,
    ):
        super().__init__(icon, parent)
        self.on_show_window = on_show_window
        self.on_beam_screenshot = on_beam_screenshot
        self.on_push_clipboard = on_push_clipboard
        self.on_quit_app = on_quit_app

        self.setToolTip(f"{APP_NAME} - Created by {CREATOR}")
        self._init_menu()

        # Connect double-click or single-click activation
        self.activated.connect(self._on_tray_activated)

    def _init_menu(self):
        menu = QtWidgets.QMenu()
        menu.setStyleSheet("""
            QMenu {
                background-color: #0f172a;
                color: #f8fafc;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 8px;
                padding: 6px;
                font-family: 'Segoe UI', system-ui, sans-serif;
                font-size: 13px;
            }
            QMenu::item {
                padding: 7px 24px 7px 12px;
                border-radius: 6px;
            }
            QMenu::item:selected {
                background-color: #0284c7;
                color: #ffffff;
            }
            QMenu::separator {
                height: 1px;
                background-color: rgba(255, 255, 255, 0.08);
                margin: 4px 6px;
            }
        """)

        # Title Item
        title_action = QtGui.QAction(f"⚡ {APP_NAME} Hub", self)
        title_action.setEnabled(False)
        menu.addAction(title_action)

        credit_action = QtGui.QAction(f"   Created by {CREATOR}", self)
        credit_action.setEnabled(False)
        menu.addAction(credit_action)

        menu.addSeparator()

        # Open Window
        open_action = QtGui.QAction("🖥️ Open AirBridge", self)
        if self.on_show_window:
            open_action.triggered.connect(self.on_show_window)
        menu.addAction(open_action)

        # Beam Screenshot
        beam_action = QtGui.QAction("📸 Beam Screenshot Now", self)
        if self.on_beam_screenshot:
            beam_action.triggered.connect(self.on_beam_screenshot)
        menu.addAction(beam_action)

        # Push Clipboard
        clip_action = QtGui.QAction("📋 Push Clipboard to Mobile", self)
        if self.on_push_clipboard:
            clip_action.triggered.connect(self.on_push_clipboard)
        menu.addAction(clip_action)

        # Open Downloads Folder
        folder_action = QtGui.QAction("📂 Open Downloads Folder", self)
        folder_action.triggered.connect(self._open_downloads_folder)
        menu.addAction(folder_action)

        menu.addSeparator()

        # Quit
        quit_action = QtGui.QAction("❌ Quit AirBridge", self)
        if self.on_quit_app:
            quit_action.triggered.connect(self.on_quit_app)
        else:
            quit_action.triggered.connect(QtWidgets.QApplication.quit)
        menu.addAction(quit_action)

        self.setContextMenu(menu)

    def _open_downloads_folder(self):
        """Open the AirBridge downloads directory in Windows File Explorer."""
        try:
            path_str = str(DOWNLOADS_DIR.resolve())
            if hasattr(os, "startfile"):
                os.startfile(path_str)
            else:
                subprocess.Popen(["explorer", path_str])
        except Exception as e:
            self.show_toast("AirBridge", f"Could not open folder: {e}", is_error=True)

    def _on_tray_activated(self, reason: QtWidgets.QSystemTrayIcon.ActivationReason):
        if reason in (
            QtWidgets.QSystemTrayIcon.ActivationReason.Trigger,
            QtWidgets.QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            if self.on_show_window:
                self.on_show_window()

    def show_toast(self, title: str, message: str, is_error: bool = False):
        """Display a Windows native notification balloon/toast."""
        icon_type = (
            QtWidgets.QSystemTrayIcon.MessageIcon.Warning
            if is_error
            else QtWidgets.QSystemTrayIcon.MessageIcon.Information
        )
        self.showMessage(title, message, icon_type, 3000)
