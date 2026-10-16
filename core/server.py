"""
AirBridge - FastAPI High-Performance Backend & Media Streamer
Provides REST APIs, WebSocket Event Bus, and RFC 7233 Range-Request Video Streaming
Created by Chathunga
"""

import os
import mimetypes
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from typing import List, Optional, Dict, Any

from fastapi import (
    FastAPI,
    WebSocket,
    WebSocketDisconnect,
    UploadFile,
    File,
    Header,
    Request,
    Response,
    status,
    HTTPException
)
from fastapi.responses import (
    HTMLResponse,
    FileResponse,
    JSONResponse,
    StreamingResponse
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from core.config import (
    settings,
    APP_NAME,
    APP_VERSION,
    CREATOR,
    ASSETS_DIR,
    MOBILE_UI_DIR,
    DOWNLOADS_DIR,
    CACHE_DIR,
    SharedFileItem,
    StreamItem,
)
from core.network import get_local_ip
from core.websocket_manager import ws_manager
from core.heic_converter import (
    is_heic_extension,
    is_heic_data,
    convert_heic_bytes_to_jpg,
)
from core.clipboard_sync import clipboard_sync
from core.screenshot import capture_primary_screen

logger = logging.getLogger("AirBridge.Server")

# Callbacks for GUI integration
desktop_callbacks: Dict[str, Any] = {
    "on_file_received": None,       # Callable[[Dict[str, Any]], None]
    "on_clipboard_updated": None,   # Callable[[str, str], None]
    "on_device_connected": None,    # Callable[[int], None]
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for FastAPI application."""
    # Detect IP
    settings.active_ip = get_local_ip()
    logger.info(f"AirBridge LAN IP detected: {settings.active_ip}")
    logger.info(f"AirBridge Pairing URL: {settings.get_pairing_url()}")

    # Setup WebSocket manager event loop
    import asyncio
    ws_manager.set_loop(asyncio.get_running_loop())

    # Wire clipboard synchronizer
    def handle_clipboard_change(text: str, source: str):
        # Broadcast to mobile clients
        ws_manager.notify_clipboard(text, source)
        # Notify Desktop GUI if registered
        cb = desktop_callbacks.get("on_clipboard_updated")
        if cb:
            try:
                cb(text, source)
            except Exception as e:
                logger.debug(f"GUI clipboard callback error: {e}")

    clipboard_sync.on_clipboard_changed = handle_clipboard_change
    clipboard_sync.start()

    # Wire device count change
    def handle_device_count(count: int):
        cb = desktop_callbacks.get("on_device_connected")
        if cb:
            try:
                cb(count)
            except Exception as e:
                logger.debug(f"GUI device count callback error: {e}")

    ws_manager.on_device_count_changed = handle_device_count

    yield

    # Clean shutdown
    clipboard_sync.stop()
    logger.info("AirBridge Server stopped gracefully.")


# Initialize FastAPI app
app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None
)

# CORS setup for seamless LAN mobile access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Assets directory
app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")


# ---------------------------------------------------------
# Static & PWA Manifest Routes
# ---------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def serve_mobile_pwa(request: Request):
    """Serve the sleek iOS/Android PWA client."""
    index_file = MOBILE_UI_DIR / "index.html"
    if not index_file.exists():
        return HTMLResponse("<h2>AirBridge Mobile UI is loading...</h2>")
    with open(index_file, "r", encoding="utf-8") as f:
        content = f.read()
    return HTMLResponse(content)


@app.get("/manifest.json")
async def serve_manifest():
    """Serve dynamic PWA manifest for iOS/Android Home Screen installation."""
    manifest_file = MOBILE_UI_DIR / "manifest.json"
    if manifest_file.exists():
        return FileResponse(manifest_file, media_type="application/manifest+json")

    # Fallback dynamic manifest
    dynamic_manifest = {
        "name": "AirBridge",
        "short_name": "AirBridge",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#0f172a",
        "theme_color": "#0f172a",
        "orientation": "portrait-primary",
        "icons": [
            {
                "src": "/assets/AirBridge-Icon.png",
                "sizes": "192x192 512x512",
                "type": "image/png",
                "purpose": "any maskable"
            }
        ]
    }
    return JSONResponse(dynamic_manifest)


# ---------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------

@app.get("/api/info")
async def get_system_info():
    """Return system connection status, server URLs, and settings."""
    return {
        "app_name": APP_NAME,
        "version": APP_VERSION,
        "creator": CREATOR,
        "ip": settings.active_ip,
        "port": settings.port,
        "session_token": settings.session_token,
        "server_url": settings.get_server_url(),
        "pairing_url": settings.get_pairing_url(),
        "auto_convert_heic": settings.auto_convert_heic,
        "auto_sync_clipboard": settings.auto_sync_clipboard,
        "connected_devices": settings.connected_devices_count,
        "downloads_dir": str(DOWNLOADS_DIR),
    }


@app.post("/api/settings/heic")
async def toggle_heic_conversion(request: Request):
    """Toggle the HEIC to JPG auto-conversion setting."""
    data = await request.json()
    enabled = bool(data.get("enabled", True))
    settings.auto_convert_heic = enabled
    return {"auto_convert_heic": settings.auto_convert_heic}


@app.post("/api/settings/clipboard")
async def toggle_clipboard_sync(request: Request):
    """Toggle auto clipboard sync."""
    data = await request.json()
    enabled = bool(data.get("enabled", True))
    settings.auto_sync_clipboard = enabled
    return {"auto_sync_clipboard": settings.auto_sync_clipboard}


@app.post("/api/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    """
    Handle high-speed multi-file uploads from Mobile devices.
    Performs on-the-fly HEIC -> JPG conversion for iPhone photos if enabled.
    Saves directly to PC's Downloads/AirBridge directory.
    """
    uploaded_items = []

    for file in files:
        filename = file.filename or "shared_file"
        file_bytes = await file.read()
        converted_heic = False

        # Smart HEIC detection and conversion
        is_heic = is_heic_extension(filename) or is_heic_data(file_bytes)
        if is_heic and settings.auto_convert_heic:
            file_bytes, filename = convert_heic_bytes_to_jpg(file_bytes, filename)
            converted_heic = True

        # Avoid filename collision
        save_path = DOWNLOADS_DIR / filename
        counter = 1
        stem = save_path.stem
        suffix = save_path.suffix
        while save_path.exists():
            save_path = DOWNLOADS_DIR / f"{stem}_{counter}{suffix}"
            counter += 1

        # Save to disk
        with open(save_path, "wb") as f:
            f.write(file_bytes)

        filesize = len(file_bytes)
        ext = save_path.suffix.lower()
        is_image = ext in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}

        file_item = {
            "id": save_path.name,
            "filename": save_path.name,
            "filepath": str(save_path),
            "filesize": filesize,
            "is_image": is_image,
            "converted_from_heic": converted_heic,
            "source": "Mobile",
            "url": f"/api/download/{save_path.name}",
        }

        # Keep in history
        settings.shared_files.insert(0, SharedFileItem(
            file_id=save_path.name,
            filename=save_path.name,
            filepath=str(save_path),
            filesize=filesize,
            uploaded_at="",
            is_image=is_image,
            source="Mobile",
            converted_from_heic=converted_heic
        ))

        # Notify Desktop GUI
        cb = desktop_callbacks.get("on_file_received")
        if cb:
            try:
                cb(file_item)
            except Exception as e:
                logger.error(f"Error calling on_file_received: {e}")

        # Broadcast to all connected clients
        ws_manager.notify_file_shared(file_item)
        uploaded_items.append(file_item)

    return {"success": True, "count": len(uploaded_items), "files": uploaded_items}


@app.get("/api/files")
async def list_shared_files():
    """List recently shared files for both PC and Mobile."""
    items = []
    for f in settings.shared_files[:50]:
        items.append({
            "id": f.file_id,
            "filename": f.filename,
            "filesize": f.filesize,
            "is_image": f.is_image,
            "source": f.source,
            "converted_from_heic": f.converted_from_heic,
            "url": f"/api/download/{f.filename}",
        })
    return {"files": items}


@app.get("/api/download/{filename}")
async def download_shared_file(filename: str):
    """Download a shared file from Downloads/AirBridge/ to Mobile or browser."""
    target_path = DOWNLOADS_DIR / filename
    if not target_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    mime_type, _ = mimetypes.guess_type(str(target_path))
    return FileResponse(
        path=str(target_path),
        filename=filename,
        media_type=mime_type or "application/octet-stream"
    )


# ---------------------------------------------------------
# Clipboard Endpoints
# ---------------------------------------------------------

@app.get("/api/clipboard")
async def get_clipboard():
    """Retrieve current clipboard text."""
    return {
        "text": clipboard_sync.get_current_text(),
        "source": settings.last_clipboard_source,
    }


@app.post("/api/clipboard")
async def set_clipboard(request: Request):
    """Receive clipboard text from Mobile and inject into Windows OS."""
    data = await request.json()
    text = data.get("text", "")
    success = clipboard_sync.set_remote_text(text)
    if success:
        # Also notify other clients if any
        ws_manager.notify_clipboard(text, source="Mobile")
    return {"success": success, "length": len(text)}


@app.post("/api/clipboard/push")
async def push_pc_clipboard():
    """Manually push current Windows OS clipboard to all connected devices."""
    text = clipboard_sync.push_current_pc_clipboard()
    return {"success": True, "text": text, "length": len(text)}


# ---------------------------------------------------------
# Screenshot Beaming Endpoints
# ---------------------------------------------------------

@app.post("/api/screenshot")
async def beam_screenshot():
    """
    Capture primary Windows monitor and beam to all connected mobile devices.
    Returns preview data URI and download URL.
    """
    try:
        jpeg_bytes, base64_uri, file_path = capture_primary_screen()
        screenshot_url = "/api/screenshot/latest"
        # Broadcast event to mobile clients
        ws_manager.notify_screenshot_beamed(screenshot_url, base64_uri)
        return {
            "success": True,
            "url": screenshot_url,
            "preview": base64_uri,
            "size": len(jpeg_bytes)
        }
    except Exception as e:
        logger.error(f"Screenshot beaming failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/screenshot/latest")
async def get_latest_screenshot():
    """Serve the latest captured screenshot."""
    if not settings.latest_screenshot_path or not os.path.exists(settings.latest_screenshot_path):
        raise HTTPException(status_code=404, detail="No screenshot captured yet")

    return FileResponse(
        path=settings.latest_screenshot_path,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
    )


# ---------------------------------------------------------
# Storage-Free LAN Video/Audio Range-Request Streaming (RFC 7233)
# ---------------------------------------------------------

@app.get("/api/stream/queue")
async def get_stream_queue():
    """List all media items currently available in the stream queue."""
    items = []
    for item in settings.stream_queue.values():
        items.append({
            "id": item.file_id,
            "filename": item.filename,
            "filesize": item.filesize,
            "mime_type": item.mime_type,
            "url": f"/api/stream/{item.file_id}"
        })
    return {"queue": items}


@app.get("/api/stream/{file_id}")
async def stream_media_range(file_id: str, request: Request, range: Optional[str] = Header(None)):
    """
    Full RFC 7233 compliant HTTP Range Request streaming handler.
    Allows iPhone Safari HTML5 video players to seek, scrub, and stream
    large 4K/1080p video files (MKV, MP4, MOV, WebM) and audio directly
    from PC memory/disk with 206 Partial Content without filling iPhone storage.
    """
    item = settings.stream_queue.get(file_id)
    if not item or not os.path.exists(item.filepath):
        # Also check if file exists in Downloads directory by filename
        fallback_path = DOWNLOADS_DIR / file_id
        if fallback_path.exists():
            mime, _ = mimetypes.guess_type(str(fallback_path))
            item = StreamItem(
                file_id=file_id,
                filename=fallback_path.name,
                filepath=str(fallback_path),
                filesize=fallback_path.stat().st_size,
                mime_type=mime or "video/mp4"
            )
        else:
            raise HTTPException(status_code=404, detail="Media file not found in stream queue")

    file_path = Path(item.filepath)
    file_size = item.filesize

    # If no Range header is sent, return the full file stream with Accept-Ranges
    if not range:
        def full_iter():
            with open(file_path, "rb") as f:
                while chunk := f.read(1024 * 512):
                    yield chunk

        return StreamingResponse(
            full_iter(),
            status_code=status.HTTP_200_OK,
            headers={
                "Accept-Ranges": "bytes",
                "Content-Length": str(file_size),
                "Content-Type": item.mime_type,
            }
        )

    # Parse HTTP Range header (format: "bytes=start-end")
    try:
        range_units, range_spec = range.strip().split("=")
        if range_units.lower() != "bytes":
            raise HTTPException(status_code=416, detail="Requested range unit not satisfiable")

        parts = range_spec.split("-")
        start = int(parts[0]) if parts[0] else 0
        end = int(parts[1]) if len(parts) > 1 and parts[1] else file_size - 1

        if start >= file_size or end >= file_size or start > end:
            return Response(
                status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
                headers={"Content-Range": f"bytes */{file_size}"}
            )

        content_length = (end - start) + 1

        def range_iter(start_pos: int, bytes_to_read: int, chunk_size: int = 1024 * 512):
            with open(file_path, "rb") as f:
                f.seek(start_pos)
                remaining = bytes_to_read
                while remaining > 0:
                    read_len = min(remaining, chunk_size)
                    data = f.read(read_len)
                    if not data:
                        break
                    remaining -= len(data)
                    yield data

        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(content_length),
            "Content-Type": item.mime_type,
        }

        return StreamingResponse(
            range_iter(start, content_length),
            status_code=status.HTTP_206_PARTIAL_CONTENT,
            headers=headers
        )

    except Exception as e:
        logger.error(f"Range streaming error: {e}")
        raise HTTPException(status_code=400, detail="Invalid Range request")


# ---------------------------------------------------------
# WebSocket Real-Time Event Bus
# ---------------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Bi-directional WebSocket connection for real-time syncing."""
    user_agent = websocket.headers.get("user-agent", "Unknown Device")
    client_info = {
        "user_agent": user_agent,
        "is_ios": "iPhone" in user_agent or "iPad" in user_agent,
        "is_android": "Android" in user_agent,
    }
    await ws_manager.connect(websocket, client_info)

    try:
        while True:
            text_data = await websocket.receive_text()
            try:
                import json
                msg = json.loads(text_data)
                msg_type = msg.get("type")

                if msg_type == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))

                elif msg_type == "send_clipboard":
                    content = msg.get("text", "")
                    if content:
                        clipboard_sync.set_remote_text(content)
                        # Broadcast to all clients
                        await ws_manager.broadcast({
                            "type": "clipboard_update",
                            "text": content,
                            "source": "Mobile"
                        })

                elif msg_type == "request_screenshot":
                    try:
                        jpeg_bytes, base64_uri, _ = capture_primary_screen()
                        await ws_manager.broadcast({
                            "type": "screenshot_beamed",
                            "url": "/api/screenshot/latest",
                            "preview": base64_uri
                        })
                    except Exception as e:
                        logger.error(f"Failed to capture screenshot on WS request: {e}")

            except Exception as e:
                logger.debug(f"WS message parsing error: {e}")

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.debug(f"WebSocket error: {e}")
        ws_manager.disconnect(websocket)
