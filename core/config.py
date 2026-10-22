"""
AirBridge - Configuration & Settings Management
Architected for Cross-Device Local LAN Transfer & Synchronization
Created by Chathunga
"""

import os
import sys
import secrets
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

# Base Application Info
APP_NAME = "AirBridge"
APP_SUBTITLE = "Local AirDrop & Universal Clipboard Hub"
APP_VERSION = "1.1.0"
CREATOR = "Chathunga"
APP_USER_MODEL_ID = "chathunga.airbridge.hub.v2"

# Directories
def find_resource_dir(name: str) -> Path:
    """
    Safely resolve a resource directory across development, PyInstaller onedir,
    PyInstaller onefile, and Windows installed environments.
    """
    candidates = []

    # 1. PyInstaller frozen binary paths
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        # PyInstaller onefile unpacked directory
        if hasattr(sys, "_MEIPASS"):
            candidates.append(Path(sys._MEIPASS) / name)
        # PyInstaller 6+ onedir bundle directory
        candidates.append(exe_dir / "_internal" / name)
        # Direct sibling of executable (e.g. Inno Setup app root)
        candidates.append(exe_dir / name)

    # 2. Source repository root
    src_root = Path(__file__).resolve().parent.parent
    candidates.append(src_root / name)

    # 3. Current working directory
    candidates.append(Path.cwd() / name)

    for cand in candidates:
        try:
            if cand.exists() and cand.is_dir():
                return cand.resolve()
        except Exception:
            pass

    # Fallback to the first candidate and ensure it is created
    target = candidates[0].resolve()
    try:
        target.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return target


if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).resolve().parent
    BASE_DIR = APP_DIR
else:
    BASE_DIR = Path(__file__).resolve().parent.parent
    APP_DIR = BASE_DIR

ASSETS_DIR = find_resource_dir("assets")
MOBILE_UI_DIR = find_resource_dir("mobile_ui")

# Runtime writable directories
try:
    DOWNLOADS_DIR = Path.home() / "Downloads" / "AirBridge"
    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    import tempfile
    DOWNLOADS_DIR = Path(tempfile.gettempdir()) / "AirBridge" / "Downloads"
    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

try:
    CACHE_DIR = Path.home() / ".airbridge" / "cache"
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    import tempfile
    CACHE_DIR = Path(tempfile.gettempdir()) / "AirBridge" / "cache"
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Default Server Settings
HOST = "0.0.0.0"
DEFAULT_PORT = 8000

# High-entropy session token for pairing verification
SESSION_TOKEN = secrets.token_urlsafe(8)


@dataclass
class StreamItem:
    file_id: str
    filename: str
    filepath: str
    filesize: int
    mime_type: str
    duration: Optional[float] = None


@dataclass
class SharedFileItem:
    file_id: str
    filename: str
    filepath: str
    filesize: int
    uploaded_at: str
    is_image: bool
    source: str  # "PC" or "Mobile"
    converted_from_heic: bool = False


class AppSettings:
    """Singleton application state and user preferences."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AppSettings, cls).__new__(cls)
            cls._instance._init_defaults()
        return cls._instance

    def _init_defaults(self):
        self.auto_convert_heic: bool = True
        self.auto_sync_clipboard: bool = True
        try:
            from core.network import find_available_port, get_local_ip
            self.port: int = find_available_port(DEFAULT_PORT)
            self.active_ip: str = get_local_ip()
        except Exception:
            self.port: int = DEFAULT_PORT
            self.active_ip: str = "127.0.0.1"
        self.session_token: str = SESSION_TOKEN
        self.stream_queue: Dict[str, StreamItem] = {}
        self.shared_files: List[SharedFileItem] = []
        self.latest_screenshot_path: Optional[str] = None
        self.connected_devices_count: int = 0
        self.connected_devices_list: List[Dict[str, Any]] = []
        self.last_clipboard_text: str = ""
        self.last_clipboard_source: str = "PC"

    def get_server_url(self) -> str:
        return f"http://{self.active_ip}:{self.port}"

    def get_pairing_url(self) -> str:
        return f"http://{self.active_ip}:{self.port}/?token={self.session_token}"


settings = AppSettings()
