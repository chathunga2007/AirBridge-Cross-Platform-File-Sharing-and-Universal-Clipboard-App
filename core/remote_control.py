"""
AirBridge - Remote Control Engine for Windows PC
Provides zero-latency wireless trackpad, mouse input, and media controls from mobile devices.
Architected using native Win32 User32 API (zero third-party bloat).
Created by Chathunga
"""

import sys
import time
import logging

logger = logging.getLogger("AirBridge.RemoteControl")

# Win32 Constants
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_WHEEL = 0x0800

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002

VK_LWIN = 0x5B
VK_D = 0x44
VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_STOP = 0xB2
VK_MEDIA_PLAY_PAUSE = 0xCD
VK_LEFT = 0x25
VK_UP = 0x26
VK_RIGHT = 0x27
VK_DOWN = 0x28
VK_SPACE = 0x20
VK_ESCAPE = 0x1B


class RemoteControlEngine:
    """Handles real-time mobile touch-to-mouse translation and media keyboard commands."""

    def __init__(self):
        self.enabled = True
        self._user32 = None
        if sys.platform == "win32":
            try:
                import ctypes
                self._user32 = ctypes.windll.user32
            except Exception as e:
                logger.error(f"Failed to load user32.dll: {e}")

    def move_cursor(self, dx: float, dy: float, sensitivity: float = 1.6):
        """Relative cursor movement from mobile touch gesture."""
        if not self.enabled or not self._user32:
            return
        try:
            # Apply acceleration curve
            int_dx = int(round(dx * sensitivity))
            int_dy = int(round(dy * sensitivity))
            if int_dx != 0 or int_dy != 0:
                self._user32.mouse_event(MOUSEEVENTF_MOVE, int_dx, int_dy, 0, 0)
        except Exception as e:
            logger.debug(f"Cursor move error: {e}")

    def click(self, button: str = "left"):
        """Execute single mouse button click."""
        if not self.enabled or not self._user32:
            return
        try:
            if button == "left":
                self._user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                self._user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            elif button == "right":
                self._user32.mouse_event(MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
                self._user32.mouse_event(MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
            elif button == "double":
                self._user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                self._user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                time.sleep(0.05)
                self._user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                self._user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        except Exception as e:
            logger.debug(f"Click error: {e}")

    def scroll(self, delta_y: int):
        """Scroll mouse wheel (e.g. two-finger swipe)."""
        if not self.enabled or not self._user32:
            return
        try:
            self._user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, int(delta_y * 120), 0)
        except Exception as e:
            logger.debug(f"Scroll error: {e}")

    def send_media_key(self, action: str):
        """Send multimedia keyboard events to Windows OS."""
        if not self.enabled or not self._user32:
            return
        try:
            vk_map = {
                "play_pause": VK_MEDIA_PLAY_PAUSE,
                "vol_up": VK_VOLUME_UP,
                "vol_down": VK_VOLUME_DOWN,
                "mute": VK_VOLUME_MUTE,
                "next": VK_MEDIA_NEXT_TRACK,
                "prev": VK_MEDIA_PREV_TRACK,
                "next_slide": VK_RIGHT,
                "prev_slide": VK_LEFT,
                "space": VK_SPACE,
                "escape": VK_ESCAPE,
            }

            if action == "lock_pc":
                self._user32.LockWorkStation()
                return

            if action == "show_desktop":
                # Win + D
                self._user32.keybd_event(VK_LWIN, 0, 0, 0)
                self._user32.keybd_event(VK_D, 0, 0, 0)
                self._user32.keybd_event(VK_D, 0, KEYEVENTF_KEYUP, 0)
                self._user32.keybd_event(VK_LWIN, 0, KEYEVENTF_KEYUP, 0)
                return

            vk = vk_map.get(action)
            if vk:
                self._user32.keybd_event(vk, 0, KEYEVENTF_EXTENDEDKEY, 0)
                self._user32.keybd_event(vk, 0, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0)

        except Exception as e:
            logger.debug(f"Media key error: {e}")


# Global instance
remote_control = RemoteControlEngine()
