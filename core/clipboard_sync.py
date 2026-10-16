"""
AirBridge - Universal Two-Way Clipboard Synchronizer
Seamless real-time synchronization between Windows OS clipboard and mobile devices
Created by Chathunga
"""

import time
import threading
import logging
from typing import Callable, Optional
import pyperclip
from core.config import settings

logger = logging.getLogger("AirBridge.Clipboard")


class ClipboardSynchronizer:
    """
    Manages continuous monitoring and synchronization of the Windows OS clipboard.
    Prevents echo/feedback loops when receiving clipboard updates from mobile clients.
    """

    def __init__(self):
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._last_content: str = ""
        self._ignore_next_change: bool = False
        self.on_clipboard_changed: Optional[Callable[[str, str], None]] = None

    def start(self):
        """Start the background clipboard polling watcher thread."""
        with self._lock:
            if self._running:
                return
            self._running = True
            # Read current clipboard on startup
            try:
                self._last_content = pyperclip.paste() or ""
                settings.last_clipboard_text = self._last_content
            except Exception as e:
                logger.debug(f"Initial clipboard read error: {e}")
                self._last_content = ""

            self._thread = threading.Thread(
                target=self._monitor_loop,
                name="AirBridge-ClipboardWatcher",
                daemon=True
            )
            self._thread.start()
            logger.info("Clipboard watcher thread started.")

    def stop(self):
        """Stop the background watcher."""
        with self._lock:
            self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
            logger.info("Clipboard watcher stopped.")

    def _monitor_loop(self):
        """Poll the OS clipboard periodically for local changes."""
        while self._running:
            try:
                if settings.auto_sync_clipboard:
                    current_text = pyperclip.paste()
                    if current_text and current_text != self._last_content:
                        with self._lock:
                            if self._ignore_next_change:
                                self._ignore_next_change = False
                                self._last_content = current_text
                            else:
                                self._last_content = current_text
                                settings.last_clipboard_text = current_text
                                settings.last_clipboard_source = "PC"
                                logger.info(f"Local clipboard change detected ({len(current_text)} chars)")
                                if self.on_clipboard_changed:
                                    self.on_clipboard_changed(current_text, "PC")
            except Exception as e:
                logger.debug(f"Clipboard poll error: {e}")

            time.sleep(0.5)

    def set_remote_text(self, text: str) -> bool:
        """
        Inject text received from Mobile into the Windows OS clipboard.
        Flags the watcher to ignore this update so it is not bounced back to mobile.
        """
        if not text:
            return False

        with self._lock:
            self._ignore_next_change = True
            self._last_content = text
            settings.last_clipboard_text = text
            settings.last_clipboard_source = "Mobile"

        try:
            pyperclip.copy(text)
            logger.info(f"Remote clipboard injected into Windows OS ({len(text)} chars)")
            if self.on_clipboard_changed:
                self.on_clipboard_changed(text, "Mobile")
            return True
        except Exception as e:
            logger.error(f"Failed to copy remote text to Windows clipboard: {e}")
            return False

    def push_current_pc_clipboard(self) -> str:
        """
        Manually trigger a push of the current Windows OS clipboard to mobile clients.
        Returns the copied text.
        """
        try:
            text = pyperclip.paste() or ""
            with self._lock:
                self._last_content = text
                settings.last_clipboard_text = text
                settings.last_clipboard_source = "PC"

            if self.on_clipboard_changed:
                self.on_clipboard_changed(text, "PC")
            return text
        except Exception as e:
            logger.error(f"Failed to read PC clipboard for manual push: {e}")
            return ""

    def get_current_text(self) -> str:
        """Return the current clipboard text."""
        try:
            return pyperclip.paste() or ""
        except Exception:
            return self._last_content


clipboard_sync = ClipboardSynchronizer()
