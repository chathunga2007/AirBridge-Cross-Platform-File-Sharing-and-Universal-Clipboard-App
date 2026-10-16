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
from typing import List, Dict, Optional

# Base Application Info
APP_NAME = "AirBridge"
APP_SUBTITLE = "Local AirDrop & Universal Clipboard Hub"
APP_VERSION = "1.0.0"
CREATOR = "Chathunga"
APP_USER_MODEL_ID = "chathunga.airbridge.hub.v2"

# Directories
BASE_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = BASE_DIR / "assets"
MOBILE_UI_DIR = BASE_DIR / "mobile_ui"
DOWNLOADS_DIR = Path.home() / "Downloads" / "AirBridge"
CACHE_DIR = BASE_DIR / ".cache"

# Ensure runtime directories exist
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

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
        self.port: int = DEFAULT_PORT
        try:
            from core.network import get_local_ip
            self.active_ip: str = get_local_ip()
        except Exception:
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
