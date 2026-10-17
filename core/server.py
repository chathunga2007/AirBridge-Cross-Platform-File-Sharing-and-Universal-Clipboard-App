"""
AirBridge - FastAPI High-Performance Backend & Media Streamer
Provides REST APIs, WebSocket Event Bus, and RFC 7233 Range-Request Video Streaming
Turbo LAN Transfer Engine with Multi-Device Fleet Tracking
Created by Chathunga
"""

import os
import time
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
from core.remote_control import remote_control
from core.shell_integration import is_shell_menu_installed, install_shell_menu, uninstall_shell_menu
import zipfile
import tempfile
from urllib.parse import quote

logger = logging.getLogger("AirBridge.Server")

# Callbacks for GUI integration
desktop_callbacks: Dict[str, Any] = {
    "on_file_received": None,       # Callable[[Dict[str, Any]], None]
    "on_clipboard_updated": None,   # Callable[[str, str], None]
    "on_device_connected": None,    # Callable[[int], None]
    "on_devices_updated": None,     # Callable[[List[Dict[str, Any]]], None]
    "on_quick_note_received": None, # Callable[[str, str], None]
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for FastAPI application."""
    # Ensure active IP is set
    if not settings.active_ip or settings.active_ip == "127.0.0.1":
        settings.active_ip = get_local_ip()
    logger.info(f"AirBridge LAN IP detected: {settings.active_ip}")
    logger.info(f"AirBridge Pairing URL: {settings.get_pairing_url()}")

    # Setup WebSocket manager event loop
    import asyncio
    ws_manager.set_loop(asyncio.get_running_loop())

    # Wire clipboard synchronizer
    def handle_clipboard_change(text: str, source: str):
        ws_manager.notify_clipboard(text, source)
        cb = desktop_callbacks.get("on_clipboard_updated")
        if cb:
            try:
                cb(text, source)
            except Exception as e:
                logger.debug(f"GUI clipboard callback error: {e}")

    clipboard_sync.on_clipboard_changed = handle_clipboard_change
    clipboard_sync.start()

    # Wire device count and full device list changes
    def handle_device_count(count: int):
        cb = desktop_callbacks.get("on_device_connected")
        if cb:
            try:
                cb(count)
            except Exception as e:
                logger.debug(f"GUI device count callback error: {e}")

    def handle_devices_updated(devices: List[Dict[str, Any]]):
        cb = desktop_callbacks.get("on_devices_updated")
        if cb:
            try:
                cb(devices)
            except Exception as e:
                logger.debug(f"GUI devices updated callback error: {e}")

    ws_manager.on_device_count_changed = handle_device_count
    ws_manager.on_devices_updated = handle_devices_updated

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

    dynamic_manifest = {
        "name": "AirBridge",
        "short_name": "AirBridge",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#070b14",
        "theme_color": "#070b14",
        "orientation": "portrait-primary",
        "icons": [
            {
                "src": "/assets/icon.png",
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
        "connected_devices_list": settings.connected_devices_list,
        "downloads_dir": str(DOWNLOADS_DIR),
    }


@app.get("/api/devices")
async def get_connected_devices():
    """Return detailed list of all currently connected mobile/desktop devices."""
    devices = ws_manager.get_connected_devices_list()
    return {
        "count": len(devices),
        "devices": devices,
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


# ---------------------------------------------------------
# Turbo LAN High-Speed File Upload Engine (10GB+ Chunk Streaming)
# ---------------------------------------------------------

CHUNK_SIZE = 8 * 1024 * 1024  # 8MB streaming buffer for gigabit Wi-Fi LAN line rate throughput


@app.post("/api/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    """
    Turbo LAN High-Speed Multi-File Upload Engine.
    Handles massive 1GB - 10GB+ files without memory bloat by streaming in 4MB chunks.
    Performs on-the-fly HEIC -> JPG conversion for iPhone photos when enabled.
    """
    uploaded_items = []

    for file in files:
        raw_name = file.filename or "shared_file"
        filename = os.path.basename(raw_name) or "shared_file"
        converted_heic = False

        # Avoid filename collision
        save_path = DOWNLOADS_DIR / filename
        counter = 1
        stem = save_path.stem
        suffix = save_path.suffix
        while save_path.exists():
            save_path = DOWNLOADS_DIR / f"{stem}_{counter}{suffix}"
            counter += 1

        is_heic = is_heic_extension(filename)
        if is_heic and settings.auto_convert_heic:
            # Photos are small enough to read and convert via pillow-heif
            raw_bytes = await file.read()
            jpg_bytes, filename = convert_heic_bytes_to_jpg(raw_bytes, filename)
            save_path = DOWNLOADS_DIR / filename
            counter = 1
            while save_path.exists():
                save_path = DOWNLOADS_DIR / f"{Path(filename).stem}_{counter}.jpg"
                counter += 1
            with open(save_path, "wb") as f:
                f.write(jpg_bytes)
            filesize = len(jpg_bytes)
            converted_heic = True
        else:
            # TURBO STREAMING WRITE for large files (videos, archives, multi-gigabyte files)
            total_size = 0
            with open(save_path, "wb") as out_f:
                while chunk := await file.read(CHUNK_SIZE):
                    out_f.write(chunk)
                    total_size += len(chunk)
            filesize = total_size

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

        # Save in history
        settings.shared_files.insert(0, SharedFileItem(
            file_id=save_path.name,
            filename=save_path.name,
            filepath=str(save_path),
            filesize=filesize,
            uploaded_at=time.strftime("%I:%M %p"),
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
            "uploaded_at": f.uploaded_at,
            "converted_from_heic": f.converted_from_heic,
            "url": f"/api/download/{f.filename}",
        })
    return {"files": items}


@app.get("/api/download/{filename}")
async def download_shared_file(filename: str):
    """
    High-speed Turbo streaming file download from PC to Mobile with 8MB chunk buffer.
    Fully RFC 5987 / RFC 6266 compliant Content-Disposition encoding for Unicode & Sinhala filenames.
    """
    from urllib.parse import quote, unquote

    clean_filename = os.path.basename(unquote(filename))
    target_path = (DOWNLOADS_DIR / clean_filename).resolve()
    if not str(target_path).startswith(str(DOWNLOADS_DIR.resolve())) or not target_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    mime_type, _ = mimetypes.guess_type(str(target_path))
    file_size = target_path.stat().st_size

    def iter_file():
        with open(target_path, "rb") as f:
            while chunk := f.read(CHUNK_SIZE):
                yield chunk

    # Clean ASCII fallback and percent-encoded UTF-8 filename for Unicode compatibility
    safe_ascii = filename.encode("ascii", "ignore").decode("ascii").replace('"', '').strip()
    if not safe_ascii:
        safe_ascii = "downloaded_file"
    encoded_fn = quote(filename)

    headers = {
        "Content-Disposition": f'attachment; filename="{safe_ascii}"; filename*=UTF-8\'\'{encoded_fn}',
        "Content-Length": str(file_size),
        "Accept-Ranges": "bytes",
    }

    return StreamingResponse(
        iter_file(),
        media_type=mime_type or "application/octet-stream",
        headers=headers
    )


# ---------------------------------------------------------
# 1-Tap Batch ZIP Archiver (Download All Session Files)
# ---------------------------------------------------------

@app.get("/api/files/download-zip")
async def download_all_files_zip():
    """
    1-Tap Batch ZIP Archiver:
    Packs all files currently shared/received in AirBridge into a single compressed .zip file.
    Streams directly to the client with low memory overhead.
    """
    files_to_pack = []
    for item in settings.shared_files:
        p = Path(item.filepath)
        if p.exists() and p.is_file():
            files_to_pack.append(p)

    if not files_to_pack:
        for p in DOWNLOADS_DIR.iterdir():
            if p.is_file() and not p.name.startswith("."):
                files_to_pack.append(p)

    if not files_to_pack:
        raise HTTPException(status_code=404, detail="No files available to package into ZIP")

    temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    temp_zip_path = Path(temp_zip.name)
    temp_zip.close()

    try:
        with zipfile.ZipFile(temp_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            added_names = set()
            for file_path in files_to_pack:
                arcname = file_path.name
                counter = 1
                while arcname in added_names:
                    arcname = f"{file_path.stem}_{counter}{file_path.suffix}"
                    counter += 1
                added_names.add(arcname)
                zf.write(file_path, arcname=arcname)

        zip_size = temp_zip_path.stat().st_size

        def iter_zip():
            try:
                with open(temp_zip_path, "rb") as f:
                    while chunk := f.read(CHUNK_SIZE):
                        yield chunk
            finally:
                try:
                    if temp_zip_path.exists():
                        temp_zip_path.unlink()
                except Exception:
                    pass

        timestamp_str = time.strftime("%Y%m%d_%H%M%S")
        zip_filename = f"AirBridge_Archive_{timestamp_str}.zip"
        safe_ascii = zip_filename
        encoded_fn = quote(zip_filename)

        headers = {
            "Content-Disposition": f'attachment; filename="{safe_ascii}"; filename*=UTF-8\'\'{encoded_fn}',
            "Content-Length": str(zip_size),
        }

        return StreamingResponse(
            iter_zip(),
            media_type="application/zip",
            headers=headers
        )
    except Exception as e:
        if temp_zip_path.exists():
            try:
                temp_zip_path.unlink()
            except Exception:
                pass
        logger.error(f"ZIP creation error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate ZIP: {e}")


# ---------------------------------------------------------
# High-Speed LAN Throughput Benchmark (Speedometer)
# ---------------------------------------------------------

@app.get("/api/benchmark/download")
async def benchmark_download(size_mb: int = 15):
    """
    LAN Throughput Benchmark Endpoint (Download Test).
    Streams up to 30MB of fast zero-byte chunks to measure local Wi-Fi speeds.
    """
    clamped_mb = max(1, min(size_mb, 50))
    total_bytes = clamped_mb * 1024 * 1024
    chunk = b"\x00" * (1024 * 1024)  # 1MB chunk

    def iter_benchmark():
        sent = 0
        while sent < total_bytes:
            yield chunk
            sent += len(chunk)

    headers = {
        "Content-Length": str(total_bytes),
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
    }
    return StreamingResponse(iter_benchmark(), media_type="application/octet-stream", headers=headers)


@app.post("/api/benchmark/upload")
async def benchmark_upload(request: Request):
    """
    LAN Throughput Benchmark Endpoint (Upload Test).
    Measures local Wi-Fi upload throughput from mobile to PC.
    """
    from starlette.requests import ClientDisconnect
    start_time = time.perf_counter()
    total_bytes = 0
    try:
        async for chunk in request.stream():
            total_bytes += len(chunk)
    except ClientDisconnect:
        logger.debug("Benchmark upload client disconnected early.")
    elapsed = max(0.001, time.perf_counter() - start_time)
    mbps = (total_bytes * 8) / (elapsed * 1_000_000)
    mb_s = (total_bytes / (1024 * 1024)) / elapsed

    return {
        "status": "success",
        "bytes_received": total_bytes,
        "elapsed_sec": round(elapsed, 3),
        "speed_mbps": round(mbps, 2),
        "speed_mb_s": round(mb_s, 2),
    }


# ---------------------------------------------------------
# Windows Explorer Shell Context Menu Integration
# ---------------------------------------------------------

@app.get("/api/shell/status")
async def get_shell_status():
    """Return whether 'Beam with AirBridge' Explorer context menu is active."""
    return {"installed": is_shell_menu_installed()}


@app.post("/api/shell/toggle")
async def toggle_shell_status(request: Request):
    """Enable or disable 'Beam with AirBridge' Explorer context menu."""
    data = await request.json()
    enable = bool(data.get("enable", True))
    if enable:
        success = install_shell_menu()
    else:
        success = uninstall_shell_menu()
    return {"success": success, "installed": is_shell_menu_installed()}


# ---------------------------------------------------------
# Clipboard & Quick Notes Endpoints
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
        ws_manager.notify_clipboard(text, source="Mobile")
    return {"success": success, "length": len(text)}


@app.post("/api/clipboard/push")
async def push_pc_clipboard():
    """Manually push current Windows OS clipboard to all connected devices."""
    text = clipboard_sync.push_current_pc_clipboard()
    return {"success": True, "text": text, "length": len(text)}


@app.post("/api/note")
async def post_quick_note(request: Request):
    """Broadcast an instant quick note or sticky link across all devices."""
    data = await request.json()
    text = data.get("text", "")
    sender = data.get("sender", "PC")
    ws_manager.notify_quick_note(text, sender)
    cb = desktop_callbacks.get("on_quick_note_received")
    if cb:
        cb(text, sender)
    return {"success": True, "text": text}


# ---------------------------------------------------------
# Screenshot Beaming Endpoints
# ---------------------------------------------------------

@app.post("/api/screenshot")
async def beam_screenshot():
    """Capture primary Windows monitor and beam to all connected mobile devices."""
    try:
        jpeg_bytes, base64_uri, file_path = capture_primary_screen()
        screenshot_url = "/api/screenshot/latest"
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

MEDIA_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".mp3", ".wav", ".m4a", ".flac", ".ogg"}


@app.get("/api/stream/queue")
async def get_stream_queue():
    """
    List all media items currently available in the stream queue.
    Automatically scans DOWNLOADS_DIR for shared video/audio media.
    """
    # 1. Auto-discover any video/audio files present in the AirBridge folder
    if DOWNLOADS_DIR.exists():
        for entry in DOWNLOADS_DIR.iterdir():
            if entry.is_file() and entry.suffix.lower() in MEDIA_EXTENSIONS:
                file_id = f"media_{entry.stem}_{entry.stat().st_size}"
                if file_id not in settings.stream_queue:
                    mime, _ = mimetypes.guess_type(str(entry))
                    settings.stream_queue[file_id] = StreamItem(
                        file_id=file_id,
                        filename=entry.name,
                        filepath=str(entry.resolve()),
                        filesize=entry.stat().st_size,
                        mime_type=mime or "video/mp4"
                    )

    items = []
    for item in settings.stream_queue.values():
        items.append({
            "id": item.file_id,
            "filename": item.filename,
            "filesize": item.filesize,
            "mime_type": item.mime_type,
            "url": f"/api/stream/{item.file_id}"
        })
    return {"queue": items, "count": len(items)}


@app.post("/api/stream/browse")
async def trigger_browse_stream():
    """Trigger the native Windows Open File Dialog on the desktop from mobile."""
    cb = desktop_callbacks.get("on_browse_stream_requested")
    if cb:
        cb()
        return {"success": True, "message": "Windows file picker launched on PC"}
    return {"success": False, "message": "Desktop app window not available"}


@app.get("/api/system/stats")
async def get_system_stats():
    """Return PC storage and AirBridge directory metrics."""
    import shutil
    total, used, free = shutil.disk_usage(DOWNLOADS_DIR)
    files = [f for f in DOWNLOADS_DIR.glob("*") if f.is_file()] if DOWNLOADS_DIR.exists() else []
    total_size = sum(f.stat().st_size for f in files)
    return {
        "disk_total": total,
        "disk_used": used,
        "disk_free": free,
        "disk_percent": round((used / total) * 100, 1),
        "files_count": len(files),
        "airbridge_storage_used": total_size,
        "connected_devices": ws_manager.get_connected_devices_count(),
    }


@app.get("/api/stream/{file_id}")
async def stream_media_range(file_id: str, request: Request, range: Optional[str] = Header(None)):
    """
    Full RFC 7233 compliant HTTP Range Request streaming handler.
    Allows iPhone Safari HTML5 video players to seek, scrub, and stream
    large 4K/1080p video files directly without downloading them to iPhone storage.
    """
    item = settings.stream_queue.get(file_id)
    if not item or not os.path.exists(item.filepath):
        clean_file_id = os.path.basename(file_id)
        fallback_path = (DOWNLOADS_DIR / clean_file_id).resolve()
        if fallback_path.exists() and str(fallback_path).startswith(str(DOWNLOADS_DIR.resolve())):
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

    if not range:
        def full_iter():
            with open(file_path, "rb") as f:
                while chunk := f.read(1024 * 1024):
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

        def range_iter(start_pos: int, bytes_to_read: int, chunk_size: int = 1024 * 1024):
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
# WebSocket Real-Time Event Bus with Rich Device Profiling
# ---------------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Bi-directional WebSocket connection with device parsing & ping benchmarking."""
    user_agent = websocket.headers.get("user-agent", "Unknown Device")
    client_ip = websocket.client.host if websocket.client else "Unknown IP"

    # Precise OS and Browser profiling
    os_name = "Desktop"
    device_name = "Device"
    browser = "Browser"

    if "iPhone" in user_agent:
        os_name = "iOS"
        device_name = "Apple iPhone"
    elif "iPad" in user_agent:
        os_name = "iPadOS"
        device_name = "Apple iPad"
    elif "Android" in user_agent:
        os_name = "Android"
        device_name = "Android Device"
    elif "Windows" in user_agent:
        os_name = "Windows"
        device_name = "Windows Client"
    elif "Macintosh" in user_agent:
        os_name = "macOS"
        device_name = "Mac Client"

    if "Safari" in user_agent and "Chrome" not in user_agent:
        browser = "Safari PWA"
    elif "Chrome" in user_agent:
        browser = "Chrome"
    elif "Firefox" in user_agent:
        browser = "Firefox"
    elif "Edg" in user_agent:
        browser = "Edge"

    dev_id = f"dev_{int(time.time() * 1000) % 1000000}"
    client_info = {
        "id": dev_id,
        "name": f"{device_name} ({browser})",
        "raw_device": device_name,
        "os": os_name,
        "browser": browser,
        "ip": client_ip,
        "connected_at": time.strftime("%I:%M %p"),
        "ping": 10,
        "is_active": True,
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
                    client_ts = msg.get("timestamp", 0)
                    await websocket.send_text(json.dumps({
                        "type": "pong",
                        "client_timestamp": client_ts,
                        "server_timestamp": time.time() * 1000,
                    }))

                elif msg_type == "client_hello":
                    # Device announced a custom nickname
                    custom_name = msg.get("name")
                    if custom_name and websocket in ws_manager.client_metadata:
                        ws_manager.client_metadata[websocket]["name"] = custom_name
                        ws_manager.client_metadata[websocket]["raw_device"] = custom_name
                        devices_list = ws_manager.get_connected_devices_list()
                        settings.connected_devices_list = devices_list
                        if ws_manager.on_devices_updated:
                            ws_manager.on_devices_updated(devices_list)
                        await ws_manager.broadcast({
                            "type": "devices_list_updated",
                            "connected_count": len(ws_manager.active_connections),
                            "devices": devices_list,
                        })

                elif msg_type == "send_clipboard":
                    content = msg.get("text", "")
                    if content:
                        clipboard_sync.set_remote_text(content)
                        await ws_manager.broadcast({
                            "type": "clipboard_update",
                            "text": content,
                            "source": client_info.get("name", "Mobile")
                        })

                elif msg_type == "send_quick_note":
                    note_text = msg.get("text", "")
                    sender_name = msg.get("sender") or client_info.get("name", "Mobile")
                    ws_manager.notify_quick_note(note_text, sender_name)
                    cb = desktop_callbacks.get("on_quick_note_received")
                    if cb:
                        cb(note_text, sender_name)

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

                elif msg_type == "remote_mouse_move":
                    dx = float(msg.get("dx", 0))
                    dy = float(msg.get("dy", 0))
                    sens = float(msg.get("sens", 1.6))
                    remote_control.move_cursor(dx, dy, sens)

                elif msg_type == "remote_mouse_click":
                    button = msg.get("button", "left")
                    remote_control.click(button)

                elif msg_type == "remote_mouse_scroll":
                    delta = int(msg.get("delta", 0))
                    remote_control.scroll(delta)

                elif msg_type == "remote_media_key":
                    action = msg.get("action", "")
                    remote_control.send_media_key(action)

            except Exception as e:
                logger.debug(f"WS message parsing error: {e}")

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.debug(f"WebSocket error: {e}")
        ws_manager.disconnect(websocket)
