"""
AirBridge - Real-Time WebSocket Event Bus & Client Manager
Coordinates live bi-directional notifications across PC and Mobile clients
Created by Chathunga
"""

import json
import asyncio
import logging
from typing import Set, Dict, Any, Optional, Callable
from fastapi import WebSocket, WebSocketDisconnect
from core.config import settings

logger = logging.getLogger("AirBridge.WebSocket")


class ConnectionManager:
    """Manages active WebSocket connections and broadcasts real-time events."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.client_metadata: Dict[WebSocket, Dict[str, Any]] = {}
        # External GUI/System event callbacks
        self.on_device_count_changed: Optional[Callable[[int], None]] = None
        self.on_message_received: Optional[Callable[[Dict[str, Any]], None]] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    async def connect(self, websocket: WebSocket, client_info: Optional[Dict[str, Any]] = None):
        """Accept WebSocket connection and register client."""
        await websocket.accept()
        self.active_connections.add(websocket)
        self.client_metadata[websocket] = client_info or {
            "device": "Unknown",
            "connected_at": asyncio.get_event_loop().time(),
        }
        count = len(self.active_connections)
        settings.connected_devices_count = count
        logger.info(f"Client connected. Active count: {count}")

        if self.on_device_count_changed:
            self.on_device_count_changed(count)

        # Notify all devices of updated peer status
        await self.broadcast({
            "type": "device_status",
            "connected_count": count,
            "message": "New device connected to AirBridge",
        })

    def disconnect(self, websocket: WebSocket):
        """Unregister client on disconnect."""
        self.active_connections.discard(websocket)
        self.client_metadata.pop(websocket, None)
        count = len(self.active_connections)
        settings.connected_devices_count = count
        logger.info(f"Client disconnected. Active count: {count}")

        if self.on_device_count_changed:
            self.on_device_count_changed(count)

        # Broadcast update asynchronously if loop is running
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.broadcast({
                    "type": "device_status",
                    "connected_count": count,
                    "message": "Device disconnected from AirBridge",
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


ws_manager = ConnectionManager()
