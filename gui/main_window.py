"""
AirBridge - Modern Dark Glassmorphism / Fluent Desktop GUI
Architected with Qt6 (PySide6 / PyQt6) for Windows 11
Created by Chathunga
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any

from gui.qt_compat import QtCore, QtGui, QtWidgets, Signal, Slot
from gui.tray_icon import AirBridgeTrayIcon
from core.config import (
    settings,
    APP_NAME,
    APP_SUBTITLE,
    APP_VERSION,
    CREATOR,
    DOWNLOADS_DIR,
    ASSETS_DIR,
    StreamItem,
    SharedFileItem,
)
from core.network import generate_qr_image, get_local_ip, get_all_lan_ips
from core.clipboard_sync import clipboard_sync
from core.screenshot import capture_primary_screen
from core.websocket_manager import ws_manager
import core.server as server_module


class BridgeSignals(QtCore.QObject):
    """Thread-safe event bridge between FastAPI background server and Qt GUI."""
    file_received = Signal(dict)
    clipboard_updated = Signal(str, str)
    device_count_changed = Signal(int)
    devices_updated = Signal(list)
    quick_note_received = Signal(str, str)
    browse_stream_requested = Signal()
    log_message = Signal(str, str)


class DeviceCardWidget(QtWidgets.QFrame):
    """Sleek Glassmorphic Card showing an active connected device."""

    def __init__(self, dev_info: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.dev_info = dev_info
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("""
            QFrame {
                background-color: rgba(15, 23, 42, 0.7);
                border: 1px solid rgba(56, 189, 248, 0.25);
                border-radius: 12px;
            }
            QFrame:hover {
                border-color: rgba(56, 189, 248, 0.55);
                background-color: rgba(30, 41, 59, 0.8);
            }
        """)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)

        # OS Icon
        os_str = self.dev_info.get("os", "").lower()
        if "ios" in os_str:
            icon_str = "📱"
        elif "android" in os_str:
            icon_str = "🤖"
        else:
            icon_str = "💻"

        icon_lbl = QtWidgets.QLabel(icon_str)
        icon_lbl.setStyleSheet("font-size: 20px; background: transparent;")
        layout.addWidget(icon_lbl)

        # Details
        info_layout = QtWidgets.QVBoxLayout()
        info_layout.setSpacing(2)

        name_lbl = QtWidgets.QLabel(self.dev_info.get("name", "Mobile Device"))
        name_lbl.setStyleSheet("color: #f8fafc; font-weight: 700; font-size: 12px; background: transparent;")
        info_layout.addWidget(name_lbl)

        sub_lbl = QtWidgets.QLabel(f"{self.dev_info.get('ip', 'LAN')} • {self.dev_info.get('connected_at', '')}")
        sub_lbl.setStyleSheet("color: #94a3b8; font-size: 10px; font-family: monospace; background: transparent;")
        info_layout.addWidget(sub_lbl)

        layout.addLayout(info_layout, stretch=1)

        # Ping badge
        ping_val = self.dev_info.get("ping", 12)
        ping_lbl = QtWidgets.QLabel(f"{ping_val}ms")
        ping_lbl.setStyleSheet("""
            color: #34d399;
            background-color: rgba(52, 211, 153, 0.15);
            border: 1px solid rgba(52, 211, 153, 0.35);
            border-radius: 6px;
            padding: 3px 6px;
            font-size: 10px;
            font-weight: 700;
            font-family: monospace;
        """)
        layout.addWidget(ping_lbl)


class DropZoneWidget(QtWidgets.QFrame):
    """Modern Drag-and-Drop Card for PC-to-Mobile file sharing."""
    files_dropped = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        self._is_drag_over = False
        self._init_ui()

    def _init_ui(self):
        self.setObjectName("dropZone")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(6)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        # Cloud Icon
        self.icon_label = QtWidgets.QLabel("☁️")
        self.icon_label.setStyleSheet("font-size: 32px; background: transparent;")
        self.icon_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.icon_label)

        # Primary Text
        self.title_label = QtWidgets.QLabel("Drop Files to Beam to Phone")
        self.title_label.setStyleSheet(
            "color: #f1f5f9; font-size: 14px; font-weight: 700; background: transparent;"
        )
        self.title_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)

        # Subtitle Text
        self.sub_label = QtWidgets.QLabel("Turbo LAN Multi-Stream • Supports 10GB+ files • or click to browse")
        self.sub_label.setStyleSheet(
            "color: #94a3b8; font-size: 11px; background: transparent;"
        )
        self.sub_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.sub_label)

        self._update_style()

    def _update_style(self):
        if self._is_drag_over:
            self.setStyleSheet("""
                QFrame#dropZone {
                    background-color: rgba(14, 165, 233, 0.22);
                    border: 2px dashed #38bdf8;
                    border-radius: 16px;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame#dropZone {
                    background-color: rgba(30, 41, 59, 0.45);
                    border: 2px dashed rgba(255, 255, 255, 0.14);
                    border-radius: 16px;
                }
                QFrame#dropZone:hover {
                    background-color: rgba(30, 41, 59, 0.75);
                    border-color: rgba(56, 189, 248, 0.55);
                }
            """)

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent):
        if event.mimeData().hasUrls():
            self._is_drag_over = True
            self._update_style()
            event.acceptProposedAction()

    def dragLeaveEvent(self, event: QtGui.QDragLeaveEvent):
        self._is_drag_over = False
        self._update_style()

    def dropEvent(self, event: QtGui.QDropEvent):
        self._is_drag_over = False
        self._update_style()
        paths = []
        for url in event.mimeData().urls():
            local_path = url.toLocalFile()
            if local_path and os.path.exists(local_path):
                paths.append(local_path)
        if paths:
            self.files_dropped.emit(paths)
        event.acceptProposedAction()

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            files, _ = QtWidgets.QFileDialog.getOpenFileNames(
                self, "Select Files to Share with Mobile", "", "All Files (*.*)"
            )
            if files:
                self.files_dropped.emit(files)


class FileItemRow(QtWidgets.QFrame):
    """Custom Row Widget for Transfer Activity Feed."""

    def __init__(self, file_data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.file_data = file_data
        self.filepath = file_data.get("filepath", "")
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("""
            QFrame {
                background-color: rgba(30, 41, 59, 0.6);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 10px;
                padding: 4px;
            }
            QFrame:hover {
                background-color: rgba(51, 65, 85, 0.7);
                border-color: rgba(56, 189, 248, 0.35);
            }
        """)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)

        # File Icon
        icon_str = "🖼️" if self.file_data.get("is_image") else "📄"
        icon_lbl = QtWidgets.QLabel(icon_str)
        icon_lbl.setStyleSheet("font-size: 18px; background: transparent;")
        layout.addWidget(icon_lbl)

        # File Info Details
        info_layout = QtWidgets.QVBoxLayout()
        info_layout.setSpacing(2)

        name_lbl = QtWidgets.QLabel(self.file_data.get("filename", "Unknown"))
        name_lbl.setStyleSheet("color: #f8fafc; font-weight: 600; font-size: 12px; background: transparent;")
        info_layout.addWidget(name_lbl)

        size_bytes = self.file_data.get("filesize", 0)
        size_str = self._format_size(size_bytes)
        source = self.file_data.get("source", "Mobile")
        heic_tag = " • Converted .JPG" if self.file_data.get("converted_from_heic") else ""
        meta_lbl = QtWidgets.QLabel(f"{size_str} • From {source}{heic_tag}")
        meta_lbl.setStyleSheet("color: #94a3b8; font-size: 10px; background: transparent;")
        info_layout.addWidget(meta_lbl)

        layout.addLayout(info_layout, stretch=1)

        # Action: Open File
        open_btn = QtWidgets.QPushButton("Open")
        open_btn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        open_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(14, 165, 233, 0.15);
                color: #38bdf8;
                border: 1px solid rgba(56, 189, 248, 0.3);
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #0284c7;
                color: #ffffff;
            }
        """)
        open_btn.clicked.connect(self._open_file)
        layout.addWidget(open_btn)

        # Action: Show in Folder
        folder_btn = QtWidgets.QPushButton("Show")
        folder_btn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        folder_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.06);
                color: #cbd5e1;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.15);
                color: #ffffff;
            }
        """)
        folder_btn.clicked.connect(self._show_in_folder)
        layout.addWidget(folder_btn)

    def _open_file(self):
        if self.filepath and os.path.exists(self.filepath):
            try:
                os.startfile(self.filepath)
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Error", f"Could not open file: {e}")

    def _show_in_folder(self):
        if self.filepath and os.path.exists(self.filepath):
            try:
                subprocess.Popen(f'explorer /select,"{os.path.abspath(self.filepath)}"')
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Error", f"Could not locate file: {e}")

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        if size_bytes == 0:
            return "0 B"
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"


class MainWindow(QtWidgets.QMainWindow):
    """Primary Desktop Window with Modern Dark Glassmorphism Styling."""

    def __init__(self):
        super().__init__()
        self.signals = BridgeSignals()
        self._init_window()
        self._init_signals()
        self._init_ui()
        self._init_tray()
        self._load_pairing_qr()

    def _init_window(self):
        self.setWindowTitle(f"{APP_NAME} - Local AirDrop & Universal Clipboard Hub")
        self.resize(1020, 750)
        self.setMinimumSize(880, 650)

        # Set Window Icon (Prioritize multi-res icon.ico for Windows Taskbar and Titlebar)
        ico_path = ASSETS_DIR / "icon.ico"
        png_path = ASSETS_DIR / "AirBridge-Icon.png"
        app_icon = None
        if ico_path.exists():
            app_icon = QtGui.QIcon(str(ico_path.resolve()))
        elif png_path.exists():
            app_icon = QtGui.QIcon(str(png_path.resolve()))

        if app_icon:
            self.setWindowIcon(app_icon)
            QtWidgets.QApplication.setWindowIcon(app_icon)

        # Dark Glassmorphism Palette & Styling
        self.setStyleSheet("""
            QMainWindow {
                background-color: #070b14;
            }
            QWidget {
                color: #f8fafc;
                font-family: 'Segoe UI Variable Display', 'Segoe UI', system-ui, sans-serif;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                border: none;
                background: transparent;
                width: 6px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255, 255, 255, 0.15);
                min-height: 20px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(56, 189, 248, 0.4);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QCheckBox {
                color: #e2e8f0;
                font-size: 12px;
                font-weight: 500;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 5px;
                border: 1px solid rgba(255, 255, 255, 0.2);
                background-color: rgba(30, 41, 59, 0.8);
            }
            QCheckBox::indicator:checked {
                background-color: #0284c7;
                border-color: #38bdf8;
                image: none;
            }
        """)

    def _init_signals(self):
        server_module.desktop_callbacks["on_file_received"] = self._threadsafe_on_file_received
        server_module.desktop_callbacks["on_clipboard_updated"] = self._threadsafe_on_clipboard_updated
        server_module.desktop_callbacks["on_device_connected"] = self._threadsafe_on_device_connected
        server_module.desktop_callbacks["on_devices_updated"] = self._threadsafe_on_devices_updated
        server_module.desktop_callbacks["on_quick_note_received"] = self._threadsafe_on_quick_note_received
        server_module.desktop_callbacks["on_browse_stream_requested"] = self._threadsafe_on_browse_stream_requested

        self.signals.file_received.connect(self._handle_file_received)
        self.signals.clipboard_updated.connect(self._handle_clipboard_updated)
        self.signals.device_count_changed.connect(self._handle_device_count_changed)
        self.signals.devices_updated.connect(self._handle_devices_updated)
        self.signals.quick_note_received.connect(self._handle_quick_note_received)
        self.signals.browse_stream_requested.connect(self._select_stream_video)
        self.signals.log_message.connect(self._handle_log_message)

    def _threadsafe_on_file_received(self, file_data: Dict[str, Any]):
        self.signals.file_received.emit(file_data)

    def _threadsafe_on_clipboard_updated(self, text: str, source: str):
        self.signals.clipboard_updated.emit(text, source)

    def _threadsafe_on_device_connected(self, count: int):
        self.signals.device_count_changed.emit(count)

    def _threadsafe_on_devices_updated(self, devices: List[Dict[str, Any]]):
        self.signals.devices_updated.emit(devices)

    def _threadsafe_on_quick_note_received(self, text: str, sender: str):
        self.signals.quick_note_received.emit(text, sender)

    def _threadsafe_on_browse_stream_requested(self):
        self.signals.browse_stream_requested.emit()

    def showEvent(self, event: QtGui.QShowEvent):
        super().showEvent(event)
        self._apply_windows_native_icon()

    def _apply_windows_native_icon(self):
        """Force Windows Taskbar to display custom icon via Shell Property Store & Win32 API."""
        if sys.platform != "win32":
            return
        try:
            import ctypes
            ico_path = ASSETS_DIR / "icon.ico"
            if not ico_path.exists():
                return

            hwnd = int(self.winId())

            # 1. Bind Windows Shell Property Store for Windows 11 Taskbar Grouping
            try:
                from win32com.propsys import propsys, pscon
                store = propsys.SHGetPropertyStoreForWindow(hwnd, propsys.IID_IPropertyStore)
                store.SetValue(pscon.PKEY_AppUserModel_ID, propsys.PROPVARIANTType(APP_USER_MODEL_ID))
                store.SetValue(pscon.PKEY_AppUserModel_RelaunchIconResource, propsys.PROPVARIANTType(f"{ico_path.resolve()},0"))
                store.SetValue(pscon.PKEY_AppUserModel_RelaunchDisplayNameResource, propsys.PROPVARIANTType("AirBridge"))
                store.Commit()
            except Exception as ex_prop:
                logger.debug(f"Window property store binding note: {ex_prop}")

            # 2. Win32 WM_SETICON for Big (48x48) & Small (16x16) taskbar/titlebar icons
            IMAGE_ICON = 1
            LR_LOADFROMFILE = 0x0010
            h_icon_big = ctypes.windll.user32.LoadImageW(
                None, str(ico_path.resolve()), IMAGE_ICON, 48, 48, LR_LOADFROMFILE
            )
            h_icon_small = ctypes.windll.user32.LoadImageW(
                None, str(ico_path.resolve()), IMAGE_ICON, 16, 16, LR_LOADFROMFILE
            )

            if h_icon_big:
                ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 1, h_icon_big)
            if h_icon_small:
                ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 0, h_icon_small)

            # 3. Stamp window class icon (GCLP_HICON = -14, GCLP_HICONSM = -34)
            try:
                try:
                    SetClassLong = ctypes.windll.user32.SetClassLongPtrW
                except AttributeError:
                    SetClassLong = ctypes.windll.user32.SetClassLongW
                if h_icon_big:
                    SetClassLong(hwnd, -14, h_icon_big)
                if h_icon_small:
                    SetClassLong(hwnd, -34, h_icon_small)
            except Exception:
                pass

        except Exception as e:
            logger.debug(f"Native icon hook note: {e}")

    def _init_ui(self):
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QtWidgets.QVBoxLayout(central_widget)
        main_layout.setContentsMargins(24, 18, 24, 18)
        main_layout.setSpacing(16)

        # -------------------------------------------------------------
        # TOP HEADER: Logo, Brand, Creator Tag, Network Selector, Status Badges
        # -------------------------------------------------------------
        header_layout = QtWidgets.QHBoxLayout()
        header_layout.setSpacing(16)

        logo_icon_path = ASSETS_DIR / "AirBridge-Icon.png"
        logo_lbl = QtWidgets.QLabel()
        if logo_icon_path.exists():
            pix = QtGui.QPixmap(str(logo_icon_path)).scaled(
                44, 44, QtCore.Qt.AspectRatioMode.KeepAspectRatio, QtCore.Qt.TransformationMode.SmoothTransformation
            )
            logo_lbl.setPixmap(pix)
        else:
            logo_lbl.setText("⚡")
            logo_lbl.setStyleSheet("font-size: 32px;")
        header_layout.addWidget(logo_lbl)

        title_layout = QtWidgets.QVBoxLayout()
        title_layout.setSpacing(2)

        app_title = QtWidgets.QLabel(APP_NAME)
        app_title.setStyleSheet("font-size: 22px; font-weight: 800; color: #38bdf8; letter-spacing: -0.5px;")
        title_layout.addWidget(app_title)

        subtitle_lbl = QtWidgets.QLabel(f"{APP_SUBTITLE} • Developed by {CREATOR}")
        subtitle_lbl.setStyleSheet("font-size: 11px; color: #94a3b8; font-weight: 500;")
        title_layout.addWidget(subtitle_lbl)

        header_layout.addLayout(title_layout)
        header_layout.addStretch()

        # LAN URL & Network Interface Selector Card
        self.url_card = QtWidgets.QFrame()
        self.url_card.setStyleSheet("""
            QFrame {
                background-color: rgba(30, 41, 59, 0.7);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 10px;
                padding: 4px 8px;
            }
        """)
        url_layout = QtWidgets.QHBoxLayout(self.url_card)
        url_layout.setContentsMargins(6, 4, 6, 4)
        url_layout.setSpacing(6)

        net_icon = QtWidgets.QLabel("📶")
        net_icon.setStyleSheet("font-size: 13px; background: transparent;")
        url_layout.addWidget(net_icon)

        self.all_lan_ips = get_all_lan_ips()
        self.ip_combo = QtWidgets.QComboBox()
        self.ip_combo.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        self.ip_combo.setStyleSheet("""
            QComboBox {
                background-color: rgba(15, 23, 42, 0.9);
                color: #38bdf8;
                border: 1px solid rgba(56, 189, 248, 0.35);
                border-radius: 6px;
                padding: 3px 8px;
                font-family: 'Consolas', monospace;
                font-size: 11px;
                font-weight: 600;
                min-width: 170px;
            }
            QComboBox::drop-down {
                border: none;
                width: 16px;
            }
            QComboBox QAbstractItemView {
                background-color: #0f172a;
                color: #f1f5f9;
                selection-background-color: #0284c7;
                selection-color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 6px;
                padding: 4px;
            }
        """)

        for iface in self.all_lan_ips:
            self.ip_combo.addItem(f"{iface['label']} :8000", iface['ip'])

        idx = self.ip_combo.findData(settings.active_ip)
        if idx >= 0:
            self.ip_combo.setCurrentIndex(idx)
        self.ip_combo.currentIndexChanged.connect(self._on_ip_combo_changed)
        url_layout.addWidget(self.ip_combo)

        copy_url_btn = QtWidgets.QPushButton("Copy URL")
        copy_url_btn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        copy_url_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(56, 189, 248, 0.15);
                color: #38bdf8;
                border: 1px solid rgba(56, 189, 248, 0.3);
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #0284c7; color: #ffffff; }
        """)
        copy_url_btn.clicked.connect(self._copy_lan_url)
        url_layout.addWidget(copy_url_btn)

        header_layout.addWidget(self.url_card)

        # Device Connected Pill
        self.devices_pill = QtWidgets.QFrame()
        self.devices_pill.setStyleSheet("""
            QFrame {
                background-color: rgba(15, 23, 42, 0.8);
                border: 1px solid rgba(52, 211, 153, 0.3);
                border-radius: 10px;
                padding: 4px 12px;
            }
        """)
        dev_layout = QtWidgets.QHBoxLayout(self.devices_pill)
        dev_layout.setContentsMargins(8, 4, 8, 4)
        dev_layout.setSpacing(6)

        self.dot_lbl = QtWidgets.QLabel("●")
        self.dot_lbl.setStyleSheet("color: #34d399; font-size: 12px;")
        dev_layout.addWidget(self.dot_lbl)

        self.dev_count_lbl = QtWidgets.QLabel("0 Devices Connected")
        self.dev_count_lbl.setStyleSheet("font-size: 11px; font-weight: 600; color: #e2e8f0;")
        dev_layout.addWidget(self.dev_count_lbl)

        header_layout.addWidget(self.devices_pill)
        main_layout.addLayout(header_layout)

        # -------------------------------------------------------------
        # BODY SPLIT: Left Panel (Pairing, Devices Fleet, Actions), Right Panel (Drop Zone, Quick Notes, Transfer Feed)
        # -------------------------------------------------------------
        body_layout = QtWidgets.QHBoxLayout()
        body_layout.setSpacing(18)

        # ================= LEFT COLUMN =================
        left_col = QtWidgets.QVBoxLayout()
        left_col.setSpacing(12)

        # 1. QR Code Pairing Card
        qr_card = QtWidgets.QFrame()
        qr_card.setStyleSheet("""
            QFrame {
                background-color: rgba(15, 23, 42, 0.7);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 16px;
                padding: 10px;
            }
        """)
        qr_layout = QtWidgets.QVBoxLayout(qr_card)
        qr_layout.setContentsMargins(12, 12, 12, 12)
        qr_layout.setSpacing(6)

        qr_title = QtWidgets.QLabel("📱 Scan to Pair iPhone / Android")
        qr_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #f1f5f9;")
        qr_layout.addWidget(qr_title)

        self.qr_label = QtWidgets.QLabel()
        self.qr_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.qr_label.setMinimumSize(170, 170)
        self.qr_label.setStyleSheet("background: #ffffff; border-radius: 12px; padding: 6px;")
        qr_layout.addWidget(self.qr_label, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)

        self.qr_url_label = QtWidgets.QLabel(settings.get_pairing_url())
        self.qr_url_label.setStyleSheet(
            "font-family: 'Consolas', monospace; font-size: 10px; color: #38bdf8; "
            "background: rgba(30, 41, 59, 0.6); padding: 5px 8px; border-radius: 6px; "
            "border: 1px solid rgba(56, 189, 248, 0.2);"
        )
        self.qr_url_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.qr_url_label.setWordWrap(True)
        qr_layout.addWidget(self.qr_url_label)

        qr_tip = QtWidgets.QLabel("⚠️ Ensure phone is connected to SAME Wi-Fi (not 4G/5G data)")
        qr_tip.setStyleSheet("font-size: 10px; color: #f59e0b; font-weight: 600; text-align: center;")
        qr_tip.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        qr_layout.addWidget(qr_tip)

        left_col.addWidget(qr_card)

        # 2. CONNECTED DEVICES FLEET & RADAR PANEL
        fleet_card = QtWidgets.QFrame()
        fleet_card.setStyleSheet("""
            QFrame {
                background-color: rgba(15, 23, 42, 0.7);
                border: 1px solid rgba(56, 189, 248, 0.2);
                border-radius: 16px;
            }
        """)
        fleet_layout = QtWidgets.QVBoxLayout(fleet_card)
        fleet_layout.setContentsMargins(12, 10, 12, 10)
        fleet_layout.setSpacing(6)

        fleet_hdr = QtWidgets.QHBoxLayout()
        fleet_title = QtWidgets.QLabel("📡 Active Devices Radar")
        fleet_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #e2e8f0;")
        fleet_hdr.addWidget(fleet_title)
        fleet_hdr.addStretch()

        self.fleet_badge = QtWidgets.QLabel("0 Active")
        self.fleet_badge.setStyleSheet("font-size: 10px; color: #94a3b8; font-weight: 600;")
        fleet_hdr.addWidget(self.fleet_badge)
        fleet_layout.addLayout(fleet_hdr)

        self.devices_scroll = QtWidgets.QScrollArea()
        self.devices_scroll.setWidgetResizable(True)
        self.devices_scroll.setMaximumHeight(140)
        self.devices_scroll_content = QtWidgets.QWidget()
        self.devices_list_layout = QtWidgets.QVBoxLayout(self.devices_scroll_content)
        self.devices_list_layout.setContentsMargins(0, 0, 0, 0)
        self.devices_list_layout.setSpacing(6)

        self.devices_empty_lbl = QtWidgets.QLabel("Waiting for iPhone or Android on LAN...")
        self.devices_empty_lbl.setStyleSheet("color: #64748b; font-size: 11px; padding: 10px; text-align: center;")
        self.devices_empty_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.devices_list_layout.addWidget(self.devices_empty_lbl)

        self.devices_scroll.setWidget(self.devices_scroll_content)
        fleet_layout.addWidget(self.devices_scroll)

        left_col.addWidget(fleet_card)

        # 3. Settings Toggles Card
        settings_card = QtWidgets.QFrame()
        settings_card.setStyleSheet("""
            QFrame {
                background-color: rgba(30, 41, 59, 0.4);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 14px;
                padding: 10px;
            }
        """)
        set_layout = QtWidgets.QVBoxLayout(settings_card)
        set_layout.setContentsMargins(10, 8, 10, 8)
        set_layout.setSpacing(8)

        self.heic_toggle = QtWidgets.QCheckBox("Auto-Convert iPhone .HEIC to .JPG")
        self.heic_toggle.setChecked(settings.auto_convert_heic)
        self.heic_toggle.stateChanged.connect(self._on_heic_toggle_changed)
        set_layout.addWidget(self.heic_toggle)

        self.clip_toggle = QtWidgets.QCheckBox("Universal Clipboard Live Auto-Sync")
        self.clip_toggle.setChecked(settings.auto_sync_clipboard)
        self.clip_toggle.stateChanged.connect(self._on_clip_toggle_changed)
        set_layout.addWidget(self.clip_toggle)

        left_col.addWidget(settings_card)

        # 4. Action Buttons Grid
        action_grid = QtWidgets.QGridLayout()
        action_grid.setSpacing(8)

        beam_btn = QtWidgets.QPushButton("📸 Beam Screen")
        beam_btn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        beam_btn.setStyleSheet(self._button_style_accent())
        beam_btn.clicked.connect(self._beam_screenshot)
        action_grid.addWidget(beam_btn, 0, 0)

        push_clip_btn = QtWidgets.QPushButton("📋 Push Clipboard")
        push_clip_btn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        push_clip_btn.setStyleSheet(self._button_style_secondary())
        push_clip_btn.clicked.connect(self._push_clipboard)
        action_grid.addWidget(push_clip_btn, 0, 1)

        stream_btn = QtWidgets.QPushButton("🎥 Queue Video")
        stream_btn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        stream_btn.setStyleSheet(self._button_style_secondary())
        stream_btn.clicked.connect(self._select_stream_video)
        action_grid.addWidget(stream_btn, 1, 0)

        open_dl_btn = QtWidgets.QPushButton("📂 Open Downloads")
        open_dl_btn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        open_dl_btn.setStyleSheet(self._button_style_secondary())
        open_dl_btn.clicked.connect(self._open_downloads_folder)
        action_grid.addWidget(open_dl_btn, 1, 1)

        left_col.addLayout(action_grid)
        body_layout.addLayout(left_col, stretch=4)

        # ================= RIGHT COLUMN =================
        right_col = QtWidgets.QVBoxLayout()
        right_col.setSpacing(12)

        # 1. Drag & Drop Zone
        self.drop_zone = DropZoneWidget()
        self.drop_zone.files_dropped.connect(self._handle_files_dropped)
        right_col.addWidget(self.drop_zone)

        # 2. INSTANT NOTE & STICKY LINK BEAM
        note_card = QtWidgets.QFrame()
        note_card.setStyleSheet("""
            QFrame {
                background-color: rgba(30, 41, 59, 0.5);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 14px;
                padding: 8px 12px;
            }
        """)
        note_layout = QtWidgets.QHBoxLayout(note_card)
        note_layout.setContentsMargins(8, 4, 8, 4)
        note_layout.setSpacing(8)

        self.note_input = QtWidgets.QLineEdit()
        self.note_input.setPlaceholderText("💡 Quick Beam: Type a note or paste URL to send to phone instantly...")
        self.note_input.setStyleSheet("""
            QLineEdit {
                background: rgba(15, 23, 42, 0.8);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                padding: 6px 10px;
                color: #f8fafc;
                font-size: 11px;
            }
            QLineEdit:focus {
                border-color: #38bdf8;
            }
        """)
        self.note_input.returnPressed.connect(self._send_quick_note)
        note_layout.addWidget(self.note_input, stretch=1)

        send_note_btn = QtWidgets.QPushButton("Beam Note")
        send_note_btn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        send_note_btn.setStyleSheet("""
            QPushButton {
                background-color: #0284c7;
                color: #ffffff;
                border: 1px solid #38bdf8;
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: 700;
            }
            QPushButton:hover { background-color: #0369a1; }
        """)
        send_note_btn.clicked.connect(self._send_quick_note)
        note_layout.addWidget(send_note_btn)

        right_col.addWidget(note_card)

        # 3. Transfer Activity Feed Card
        feed_card = QtWidgets.QFrame()
        feed_card.setStyleSheet("""
            QFrame#feedCard {
                background-color: rgba(15, 23, 42, 0.7);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 16px;
            }
        """)
        feed_card.setObjectName("feedCard")
        feed_layout = QtWidgets.QVBoxLayout(feed_card)
        feed_layout.setContentsMargins(14, 12, 14, 12)
        feed_layout.setSpacing(8)

        feed_header = QtWidgets.QHBoxLayout()
        feed_title = QtWidgets.QLabel("Transfer Activity & Received Files")
        feed_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #f1f5f9;")
        feed_header.addWidget(feed_title)

        feed_header.addStretch()

        clear_btn = QtWidgets.QPushButton("Clear")
        clear_btn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        clear_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #64748b;
                border: none;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover { color: #38bdf8; }
        """)
        clear_btn.clicked.connect(self._clear_feed)
        feed_header.addWidget(clear_btn)
        feed_layout.addLayout(feed_header)

        self.feed_scroll = QtWidgets.QScrollArea()
        self.feed_scroll.setWidgetResizable(True)
        self.feed_scroll_content = QtWidgets.QWidget()
        self.feed_items_layout = QtWidgets.QVBoxLayout(self.feed_scroll_content)
        self.feed_items_layout.setContentsMargins(0, 0, 0, 0)
        self.feed_items_layout.setSpacing(6)
        self.feed_items_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)

        self.empty_lbl = QtWidgets.QLabel("No recent transfers. Send photos or drop files to begin!")
        self.empty_lbl.setStyleSheet("color: #64748b; font-size: 12px; padding: 20px; text-align: center;")
        self.empty_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.feed_items_layout.addWidget(self.empty_lbl)

        self.feed_scroll.setWidget(self.feed_scroll_content)
        feed_layout.addWidget(self.feed_scroll)

        right_col.addWidget(feed_card, stretch=1)
        body_layout.addLayout(right_col, stretch=6)

        main_layout.addLayout(body_layout)

        # -------------------------------------------------------------
        # BOTTOM STATUS BAR
        # -------------------------------------------------------------
        status_bar = QtWidgets.QHBoxLayout()
        self.status_lbl = QtWidgets.QLabel("⚡ AirBridge Turbo Engine Ready • Waiting for Mobile pairing")
        self.status_lbl.setStyleSheet("font-size: 11px; color: #64748b; font-weight: 500;")
        status_bar.addWidget(self.status_lbl)

        status_bar.addStretch()

        credits_lbl = QtWidgets.QLabel(f"{APP_NAME} v{APP_VERSION} • Developed with ❤️ by {CREATOR}")
        credits_lbl.setStyleSheet("font-size: 11px; color: #475569;")
        status_bar.addWidget(credits_lbl)

        main_layout.addLayout(status_bar)

    def _init_tray(self):
        icon_path = ASSETS_DIR / "icon.ico"
        if not icon_path.exists():
            icon_path = ASSETS_DIR / "icon.png"

        tray_icon = QtGui.QIcon(str(icon_path.resolve())) if icon_path.exists() else QtGui.QIcon()
        self.tray = AirBridgeTrayIcon(
            icon=tray_icon,
            parent=self,
            on_show_window=self._show_and_raise,
            on_beam_screenshot=self._beam_screenshot,
            on_push_clipboard=self._push_clipboard,
            on_quit_app=self._clean_quit
        )
        self.tray.show()

    def _load_pairing_qr(self):
        """Generate and render pairing QR code into the UI."""
        try:
            pairing_url = settings.get_pairing_url()
            qr_pil = generate_qr_image(pairing_url, box_size=5, border=1)
            import io
            buf = io.BytesIO()
            qr_pil.save(buf, format="PNG")
            qimg = QtGui.QImage.fromData(buf.getvalue())
            pix = QtGui.QPixmap.fromImage(qimg).scaled(
                170, 170, QtCore.Qt.AspectRatioMode.KeepAspectRatio, QtCore.Qt.TransformationMode.SmoothTransformation
            )
            self.qr_label.setPixmap(pix)
            if hasattr(self, "qr_url_label"):
                self.qr_url_label.setText(pairing_url)
        except Exception as e:
            self.qr_label.setText(f"QR Error: {e}")

    def _on_ip_combo_changed(self, index: int):
        new_ip = self.ip_combo.itemData(index)
        if new_ip and new_ip != settings.active_ip:
            settings.active_ip = new_ip
            self._load_pairing_qr()
            self.status_lbl.setText(f"📶 Switched to {new_ip} • Pairing QR updated!")

    # -------------------------------------------------------------
    # SLOTS & ACTIONS
    # -------------------------------------------------------------
    @Slot(dict)
    def _handle_file_received(self, file_data: Dict[str, Any]):
        """Slot executed when mobile uploads a file."""
        if self.empty_lbl.isVisible():
            self.empty_lbl.hide()

        row = FileItemRow(file_data)
        self.feed_items_layout.insertWidget(0, row)

        self.status_lbl.setText(f"📥 Received '{file_data.get('filename')}' from {file_data.get('source')}")
        self.tray.show_toast(
            "AirBridge File Received",
            f"Saved '{file_data.get('filename')}' to Downloads/AirBridge"
        )
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except Exception:
            pass

    @Slot(str, str)
    def _handle_clipboard_updated(self, text: str, source: str):
        """Slot executed when clipboard changes."""
        preview = text[:40] + "..." if len(text) > 40 else text
        self.status_lbl.setText(f"📋 Clipboard synced from {source}: '{preview}'")
        if source != "PC":
            self.tray.show_toast("AirBridge Universal Clipboard", f"Pasted from {source}: {preview}")
            try:
                import winsound
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
            except Exception:
                pass

    @Slot(int)
    def _handle_device_count_changed(self, count: int):
        """Slot executed when connected mobile devices count changes."""
        text = f"{count} Device{'s' if count != 1 else ''} Connected"
        self.dev_count_lbl.setText(text)
        self.fleet_badge.setText(f"{count} Active")
        if count > 0:
            self.dot_lbl.setStyleSheet("color: #34d399; font-size: 12px;")
            self.status_lbl.setText(f"🟢 Connected to {count} device{'s' if count > 1 else ''}")
        else:
            self.dot_lbl.setStyleSheet("color: #64748b; font-size: 12px;")
            self.status_lbl.setText("⚡ AirBridge Turbo Engine Ready • Waiting for Mobile pairing")

    @Slot(list)
    def _handle_devices_updated(self, devices: List[Dict[str, Any]]):
        """Slot executed when rich device list changes."""
        # Clear previous device cards
        while self.devices_list_layout.count() > 0:
            item = self.devices_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not devices:
            self.devices_empty_lbl = QtWidgets.QLabel("Waiting for iPhone or Android on LAN...")
            self.devices_empty_lbl.setStyleSheet("color: #64748b; font-size: 11px; padding: 10px; text-align: center;")
            self.devices_empty_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            self.devices_list_layout.addWidget(self.devices_empty_lbl)
        else:
            for dev in devices:
                card = DeviceCardWidget(dev)
                self.devices_list_layout.addWidget(card)

    @Slot(str, str)
    def _handle_quick_note_received(self, text: str, sender: str):
        """Slot executed when quick note is beamed from phone."""
        preview = text[:45] + "..." if len(text) > 45 else text
        self.status_lbl.setText(f"💡 Quick Note from {sender}: {preview}")
        self.tray.show_toast(f"Note from {sender}", preview)

    @Slot(str, str)
    def _handle_log_message(self, message: str, level: str):
        self.status_lbl.setText(message)

    def _send_quick_note(self):
        text = self.note_input.text().strip()
        if not text:
            return
        ws_manager.notify_quick_note(text, "Windows PC")
        self.status_lbl.setText(f"💡 Beamed quick note to connected phones: '{text[:30]}...'")
        self.note_input.clear()

    def _handle_files_dropped(self, paths: List[str]):
        """Handle files dragged and dropped onto the PC window to beam to mobile."""
        copied_items = []
        for p in paths:
            src = Path(p)
            if not src.exists():
                continue
            if src.is_file():
                dest = DOWNLOADS_DIR / src.name
                counter = 1
                while dest.exists():
                    dest = DOWNLOADS_DIR / f"{src.stem}_{counter}{src.suffix}"
                    counter += 1
                shutil.copy2(src, dest)

                filesize = dest.stat().st_size
                ext = dest.suffix.lower()
                is_image = ext in {".jpg", ".jpeg", ".png", ".gif", ".webp"}

                file_dict = {
                    "id": dest.name,
                    "filename": dest.name,
                    "filepath": str(dest),
                    "filesize": filesize,
                    "is_image": is_image,
                    "converted_from_heic": False,
                    "source": "PC",
                    "url": f"/api/download/{dest.name}",
                }

                settings.shared_files.insert(0, SharedFileItem(
                    file_id=dest.name,
                    filename=dest.name,
                    filepath=str(dest),
                    filesize=filesize,
                    uploaded_at="",
                    is_image=is_image,
                    source="PC"
                ))

                ws_manager.notify_file_shared(file_dict)
                self._handle_file_received(file_dict)
                copied_items.append(dest.name)

        if copied_items:
            self.status_lbl.setText(f"🚀 Beamed {len(copied_items)} file(s) to connected phones!")

    def _beam_screenshot(self):
        """Trigger instant screen capture and notify phone."""
        try:
            jpeg_bytes, base64_uri, _ = capture_primary_screen()
            ws_manager.notify_screenshot_beamed("/api/screenshot/latest", base64_uri)
            self.status_lbl.setText(f"📸 Screen captured & beamed to phones! ({len(jpeg_bytes) // 1024} KB)")
            self.tray.show_toast("AirBridge Screenshot", "Windows Screen beamed to connected devices!")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Screenshot Error", f"Failed to capture screen: {e}")

    def _push_clipboard(self):
        """Manually push PC clipboard to phone."""
        text = clipboard_sync.push_current_pc_clipboard()
        if text:
            preview = text[:35] + "..." if len(text) > 35 else text
            self.status_lbl.setText(f"📋 Pushed PC clipboard: '{preview}'")
            self.tray.show_toast("AirBridge Clipboard", f"Pushed to mobile: {preview}")
        else:
            self.status_lbl.setText("Clipboard is currently empty.")

    def _select_stream_video(self):
        """Add a video or audio file to the RFC 7233 Range-Request stream queue."""
        filepath, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select Media to Stream to iPhone/Android",
            "",
            "Video & Audio (*.mp4 *.mkv *.mov *.webm *.mp3 *.m4a *.wav);;All Files (*.*)"
        )
        if filepath and os.path.exists(filepath):
            p = Path(filepath)
            file_id = f"stream_{p.stem}_{p.stat().st_size}"
            import mimetypes
            mime, _ = mimetypes.guess_type(filepath)
            item = StreamItem(
                file_id=file_id,
                filename=p.name,
                filepath=str(p.resolve()),
                filesize=p.stat().st_size,
                mime_type=mime or "video/mp4"
            )
            settings.stream_queue[file_id] = item
            ws_manager.notify_stream_queue(list(settings.stream_queue.values()))
            self.status_lbl.setText(f"🎥 Added '{p.name}' to iPhone Stream Queue (No download required)!")
            self.tray.show_toast("AirBridge Media Streamer", f"'{p.name}' ready for iPhone streaming!")

    def _open_downloads_folder(self):
        try:
            os.startfile(str(DOWNLOADS_DIR.resolve()))
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error", f"Could not open folder: {e}")

    def _copy_lan_url(self):
        try:
            pairing_url = settings.get_pairing_url()
            clipboard_sync.set_remote_text(pairing_url)
            self.status_lbl.setText(f"🔗 Copied '{pairing_url}' to Windows clipboard!")
        except Exception:
            pass

    def _on_heic_toggle_changed(self, state: int):
        settings.auto_convert_heic = bool(state == QtCore.Qt.CheckState.Checked.value or state == 2)
        status_str = "Enabled" if settings.auto_convert_heic else "Disabled"
        self.status_lbl.setText(f"⚙️ Auto-Convert iPhone .HEIC to .JPG: {status_str}")

    def _on_clip_toggle_changed(self, state: int):
        settings.auto_sync_clipboard = bool(state == QtCore.Qt.CheckState.Checked.value or state == 2)
        status_str = "Enabled" if settings.auto_sync_clipboard else "Disabled"
        self.status_lbl.setText(f"⚙️ Universal Clipboard Auto-Sync: {status_str}")

    def _clear_feed(self):
        while self.feed_items_layout.count() > 0:
            item = self.feed_items_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.empty_lbl.show()
        self.feed_items_layout.addWidget(self.empty_lbl)

    def _show_and_raise(self):
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _clean_quit(self):
        QtWidgets.QApplication.quit()

    def closeEvent(self, event: QtGui.QCloseEvent):
        """Minimize to tray instead of quitting when close button is clicked."""
        if self.tray.isVisible():
            self.hide()
            self.tray.show_toast(
                "AirBridge Running in Background",
                "AirBridge is still active in the System Tray. Click the icon to restore."
            )
            event.ignore()
        else:
            event.accept()

    # -------------------------------------------------------------
    # STYLES
    # -------------------------------------------------------------
    @staticmethod
    def _button_style_accent() -> str:
        return """
            QPushButton {
                background-color: #0284c7;
                color: #ffffff;
                border: 1px solid #38bdf8;
                border-radius: 10px;
                padding: 10px 14px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #0369a1;
                border-color: #7dd3fc;
            }
            QPushButton:pressed {
                background-color: #0c4a6e;
            }
        """

    @staticmethod
    def _button_style_secondary() -> str:
        return """
            QPushButton {
                background-color: rgba(30, 41, 59, 0.7);
                color: #e2e8f0;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 10px;
                padding: 10px 14px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: rgba(51, 65, 85, 0.8);
                border-color: rgba(56, 189, 248, 0.4);
                color: #ffffff;
            }
            QPushButton:pressed {
                background-color: rgba(15, 23, 42, 0.9);
            }
        """
