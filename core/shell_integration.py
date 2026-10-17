"""
AirBridge - Windows Explorer Shell Integration
Allows right-clicking any file in Windows Explorer to "Beam with AirBridge".
Operates purely under HKCU (Current User) requiring zero Administrator permissions.
Created by Chathunga
"""

import os
import sys
import logging
from pathlib import Path

logger = logging.getLogger("AirBridge.ShellIntegration")

REG_SUBKEY = r"Software\Classes\*\shell\AirBridge"


def is_shell_menu_installed() -> bool:
    """Check if 'Beam with AirBridge' context menu is currently registered in HKCU."""
    if sys.platform != "win32":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_SUBKEY, 0, winreg.KEY_READ):
            return True
    except FileNotFoundError:
        return False
    except Exception as e:
        logger.debug(f"Error checking registry: {e}")
        return False


def install_shell_menu() -> bool:
    """Register 'Beam with AirBridge' in Windows Explorer right-click menu."""
    if sys.platform != "win32":
        return False
    try:
        is_frozen = getattr(sys, "frozen", False)
        if is_frozen:
            cmd_str = f'"{sys.executable}" "%1"'
            from core.config import ASSETS_DIR
            ico_path = (ASSETS_DIR / "icon.ico").resolve()
        else:
            base_dir = Path(__file__).resolve().parent.parent
            main_py = (base_dir / "main.py").resolve()
            ico_path = (base_dir / "assets" / "icon.ico").resolve()
            python_exe = sys.executable
            cmd_str = f'"{python_exe}" "{main_py}" "%1"'

        # Create shell\AirBridge key
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_SUBKEY) as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "Beam with AirBridge")
            if ico_path.exists():
                winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, str(ico_path))

        # Create shell\AirBridge\command key
        cmd_subkey = f"{REG_SUBKEY}\\command"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, cmd_subkey) as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, cmd_str)

        logger.info("Successfully registered 'Beam with AirBridge' Windows Explorer context menu.")
        return True
    except Exception as e:
        logger.error(f"Failed to register Windows Explorer context menu: {e}")
        return False


def uninstall_shell_menu() -> bool:
    """Remove 'Beam with AirBridge' context menu from HKCU."""
    if sys.platform != "win32":
        return False
    try:
        import winreg
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, f"{REG_SUBKEY}\\command")
        except FileNotFoundError:
            pass
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, REG_SUBKEY)
        except FileNotFoundError:
            pass
        logger.info("Removed 'Beam with AirBridge' context menu from Windows Explorer.")
        return True
    except Exception as e:
        logger.error(f"Failed to remove context menu: {e}")
        return False
