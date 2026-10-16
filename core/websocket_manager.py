"""
AirBridge - Real-Time WebSocket Event Bus & Client Manager
Coordinates live bi-directional notifications across PC and Mobile clients
Created by Chathunga
"""

import json
import asyncio
import logging
from typing import Set, Dict, Any, Optional, Callable, List
from fastapi import WebSocket, WebSocketDisconnect
from core.config import settings

logger = logging.getLogger("AirBridge.WebSocket")


class ConnectionManager:
    """Manages active WebSocket connections and broadcasts real-time events with rich device metadata."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.client_metadata: Dict[WebSocket, Dict[str, Any]] = {}
        # External GUI/System event callbacks
        self.on_device_count_changed: Optional[Callable[[int], None]] = None
        self.on_devices_updated: Optional[Callable[[List[Dict[str, Any]]], None]] = None
        self.on_message_received: Optional[Callable[[Dict[str, Any]], None]] = None
        self.on_quick_note_received: Optional[Callable[[str, str], None]] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    def get_connected_devices_list(self) -> List[Dict[str, Any]]:
        """Return clean list of all connected device objects."""
        return list(self.client_metadata.values())

    async def connect(self, websocket: WebSocket, client_info: Optional[Dict[str, Any]] = None):
        """Accept WebSocket connection, register client and broadcast updated fleet list."""
        await websocket.accept()
        self.active_connections.add(websocket)
        self.client_metadata[websocket] = client_info or {
            "id": f"device_{len(self.active_connections)}",
            "name": "Unknown Device",
            "ip": "Unknown IP",
            "os": "Unknown OS",
            "browser": "Browser",
            "connected_at": "Just now",
            "ping": 10,
        }
        count = len(self.active_connections)
        devices_list = self.get_connected_devices_list()
        settings.connected_devices_count = count
        settings.connected_devices_list = devices_list

        logger.info(f"Client connected: {self.client_metadata[websocket].get('name')}. Active: {count}")

        if self.on_device_count_changed:
            self.on_device_count_changed(count)
        if self.on_devices_updated:
            self.on_devices_updated(devices_list)

        # Notify all devices of updated fleet list
        await self.broadcast({
            "type": "devices_list_updated",
            "connected_count": count,
            "devices": devices_list,
            "message": f"{self.client_metadata[websocket].get('name')} connected",
        })

    def disconnect(self, websocket: WebSocket):
        """Unregister client on disconnect."""
        removed_meta = self.client_metadata.pop(websocket, None)
        self.active_connections.discard(websocket)
        count = len(self.active_connections)
        devices_list = self.get_connected_devices_list()
        settings.connected_devices_count = count
        settings.connected_devices_list = devices_list

        dev_name = removed_meta.get("name") if removed_meta else "A device"
        logger.info(f"Client disconnected: {dev_name}. Active: {count}")

        if self.on_device_count_changed:
            self.on_device_count_changed(count)
        if self.on_devices_updated:
            self.on_devices_updated(devices_list)

        # Broadcast update asynchronously if loop is running
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.broadcast({
                    "type": "devices_list_updated",
                    "connected_count": count,
                    "devices": devices_list,
                    "message": f"{dev_name} disconnected",
                }),
                self._loop
            )

    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast a JSON message to all currently connected clients."""
        if not self.active_connections:
            return

        payload = json.dumps(message)
        dead_connections = []
        for connection in list(self.active_connections):
            try:
                await connection.send_text(payload)
            except Exception as e:
                logger.debug(f"Broadcast failed to client: {e}")
                dead_connections.append(connection)

        for dead in dead_connections:
            self.disconnect(dead)

    def broadcast_threadsafe(self, message: Dict[str, Any]):
        """Safe broadcast callable from any non-async worker or GUI thread."""
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self.broadcast(message), self._loop)
        else:
            logger.debug("Event loop not running, could not broadcast message.")

    def notify_clipboard(self, text: str, source: str = "PC"):
        """Broadcast live clipboard update."""
        self.broadcast_threadsafe({
            "type": "clipboard_update",
            "text": text,
            "source": source,
        })

    def notify_file_shared(self, file_data: Dict[str, Any]):
        """Broadcast file shared from PC or Mobile."""
        self.broadcast_threadsafe({
            "type": "file_shared",
            "file": file_data,
        })

    def notify_screenshot_beamed(self, screenshot_url: str, base64_preview: Optional[str] = None):
        """Broadcast beamed screenshot notification."""
        self.broadcast_threadsafe({
            "type": "screenshot_beamed",
            "url": screenshot_url,
            "preview": base64_preview,
        })

    def notify_stream_queue(self, queue_items: list):
        """Broadcast updated video/audio stream queue."""
        self.broadcast_threadsafe({
            "type": "stream_queue_updated",
            "queue": queue_items,
        })

    def notify_quick_note(self, text: str, sender: str = "PC"):
        """Broadcast instant quick note / link drop."""
        self.broadcast_threadsafe({
            "type": "quick_note",
            "text": text,
            "sender": sender,
        })


ws_manager = ConnectionManager()
