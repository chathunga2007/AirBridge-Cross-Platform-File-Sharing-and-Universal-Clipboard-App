"""
AirBridge - Main Application Entry Point
Next-Generation Cross-Device Local AirDrop & Universal Clipboard Hub
Created by Chathunga
"""

import os
import sys
import time
import ctypes
import threading
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(name)s) %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger("AirBridge.Main")

# 1. Set Windows AppUserModelID for Windows 11 Taskbar Icon & Toast Integration
try:
    if sys.platform == "win32":
        myappid = "chathunga.airbridge.hub.v2"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        logger.info(f"Windows AppUserModelID set to '{myappid}'")
except Exception as e:
    logger.debug(f"Could not set AppUserModelID: {e}")

# 2. Ensure Assets & Icons Exist (Graceful Fallback Generator)
from core.config import ASSETS_DIR, APP_USER_MODEL_ID, HOST, DEFAULT_PORT


def ensure_icons():
    """Ensure assets directory contains valid icon.ico and icon.png."""
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    ico_path = ASSETS_DIR / "icon.ico"
    png_path = ASSETS_DIR / "icon.png"
    src_icon = ASSETS_DIR / "AirBridge-Icon.png"

    from PIL import Image

    # If source icon exists, create .ico and .png if needed
    if src_icon.exists():
        try:
            with Image.open(src_icon) as img:
                if not ico_path.exists():
                    img.save(ico_path, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
                if not png_path.exists():
                    img.save(png_path, format="PNG")
            return
        except Exception as e:
            logger.warning(f"Error converting AirBridge-Icon.png: {e}")

    # Fallback generator if no icon is placed yet
    if not ico_path.exists() or not png_path.exists():
        try:
            from PIL import ImageDraw
            img = Image.new("RGBA", (256, 256), color=(15, 23, 42, 255))
            draw = ImageDraw.Draw(img)
            # Draw glowing cyan circle and bridge emblem
            draw.ellipse([20, 20, 236, 236], fill=(14, 165, 233, 255), outline=(56, 189, 248, 255), width=6)
            draw.rectangle([80, 110, 176, 146], fill=(255, 255, 255, 255))
            draw.polygon([(128, 60), (70, 130), (186, 130)], fill=(255, 255, 255, 255))

            if not png_path.exists():
                img.save(png_path, format="PNG")
            if not ico_path.exists():
                img.save(ico_path, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
            logger.info("Generated fallback icons in assets directory.")
        except Exception as e:
            logger.error(f"Fallback icon generation failed: {e}")


ensure_icons()


def ensure_shortcuts():
    """Ensure Windows Start Menu & Desktop shortcuts exist with the custom AirBridge icon and AppUserModelID."""
    if sys.platform != "win32":
        return
    try:
        import win32com.client
        import shutil
        shell = win32com.client.Dispatch("WScript.Shell")
        base_dir = Path(__file__).resolve().parent
        ico_path = base_dir / "assets" / "icon.ico"
        main_py = base_dir / "main.py"

        # Resolve pythonw.exe to prevent terminal window popup when clicking shortcut
        py_dir = Path(sys.executable).parent
        pyw_cand = py_dir / "pythonw.exe"
        if not pyw_cand.exists():
            which_pyw = shutil.which("pythonw.exe")
            if which_pyw:
                pyw_cand = Path(which_pyw)
        target_exe = str(pyw_cand.resolve()) if pyw_cand.exists() else sys.executable

        # Start Menu Programs shortcut (forces Windows 11 Taskbar icon resolution)
        try:
            programs_dir = shell.SpecialFolders("Programs")
            if programs_dir and os.path.exists(programs_dir):
                lnk_programs = os.path.join(programs_dir, "AirBridge.lnk")
                s2 = shell.CreateShortcut(lnk_programs)
                s2.TargetPath = target_exe
                s2.Arguments = f'"{main_py}"'
                s2.WorkingDirectory = str(base_dir)
                s2.IconLocation = f"{ico_path.resolve()},0"
                s2.Description = "AirBridge - Cross-Device Local Transfer Hub by Chathunga"
                s2.Save()

                # Bind System.AppUserModel.ID directly into shortcut property store
                try:
                    from win32com.propsys import propsys, pscon
                    store = propsys.SHGetPropertyStoreFromParsingName(lnk_programs, None, 2, propsys.IID_IPropertyStore)
                    propvar = propsys.PROPVARIANTType(APP_USER_MODEL_ID)
                    store.SetValue(pscon.PKEY_AppUserModel_ID, propvar)
                    store.Commit()
                except Exception as ex_prop:
                    logger.debug(f"Shortcut property store setup note: {ex_prop}")

                logger.info("Windows Start Menu shortcut verified with custom icon.")
        except Exception as e:
            logger.debug(f"Start Menu shortcut setup note: {e}")

        # Desktop shortcut
        try:
            desktop_dir = shell.SpecialFolders("Desktop")
            if desktop_dir and os.path.exists(desktop_dir):
                lnk_desktop = os.path.join(desktop_dir, "AirBridge.lnk")
                s = shell.CreateShortcut(lnk_desktop)
                s.TargetPath = target_exe
                s.Arguments = f'"{main_py}"'
                s.WorkingDirectory = str(base_dir)
                s.IconLocation = f"{ico_path.resolve()},0"
                s.Description = "AirBridge - Cross-Device Local Transfer Hub by Chathunga"
                s.Save()

                try:
                    from win32com.propsys import propsys, pscon
                    store_d = propsys.SHGetPropertyStoreFromParsingName(lnk_desktop, None, 2, propsys.IID_IPropertyStore)
                    store_d.SetValue(pscon.PKEY_AppUserModel_ID, propsys.PROPVARIANTType(APP_USER_MODEL_ID))
                    store_d.Commit()
                except Exception:
                    pass

                logger.info("Windows Desktop shortcut verified with custom icon.")
        except Exception as e:
            logger.debug(f"Desktop shortcut setup note: {e}")

    except Exception as e:
        logger.debug(f"Shortcut creation skipped: {e}")


ensure_shortcuts()
class ServerThread(threading.Thread):
    def __init__(self, host: str, port: int):
        super().__init__(name="AirBridge-ServerThread", daemon=True)
        self.host = host
        self.port = port
        self.server = None

    def run(self):
        import uvicorn
        from core.server import app

        config = uvicorn.Config(
            app=app,
            host=self.host,
            port=self.port,
            log_level="warning",
            access_log=False,
            workers=1,
            loop="asyncio"
        )
        self.server = uvicorn.Server(config)
        logger.info(f"Starting AirBridge API Server on {self.host}:{self.port}...")
        self.server.run()

    def stop(self):
        if self.server:
            self.server.should_exit = True


def main():
    # Start FastAPI backend in background thread
    server_thread = ServerThread(host=HOST, port=DEFAULT_PORT)
    server_thread.start()

    # Small pause to allow server initialization
    time.sleep(0.3)

    # Initialize Qt GUI on the main thread
    from gui.qt_compat import QtWidgets, QtGui, QtCore
    from gui.main_window import MainWindow

    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("AirBridge")
    app.setOrganizationName("Chathunga")

    # Set Application Icon (prioritize multi-resolution icon.ico for Windows Taskbar)
    ico_path = ASSETS_DIR / "icon.ico"
    png_path = ASSETS_DIR / "AirBridge-Icon.png"
    if ico_path.exists():
        app.setWindowIcon(QtGui.QIcon(str(ico_path.resolve())))
    elif png_path.exists():
        app.setWindowIcon(QtGui.QIcon(str(png_path.resolve())))

    window = MainWindow()
    window.showMaximized()
    window._apply_windows_native_icon()

    logger.info("AirBridge GUI initialized and running.")
    exit_code = app.exec()

    # Cleanup on exit
    logger.info("Shutting down AirBridge...")
    server_thread.stop()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
