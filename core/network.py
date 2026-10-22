"""
AirBridge - Network & QR Pairing Module
Accurate Local Wi-Fi / Ethernet IPv4 Detection & Dynamic Pairing QR Generation
Created by Chathunga
"""

import io
import base64
import socket
import logging
from typing import Optional, List, Dict, Any
import psutil
import qrcode
from PIL import Image

logger = logging.getLogger("AirBridge.Network")

# Known virtual/tunnel adapter keywords to ignore
VIRTUAL_ADAPTER_KEYWORDS = [
    "vethernet",
    "wsl",
    "docker",
    "vmware",
    "virtualbox",
    "loopback",
    "bluetooth",
    "teredo",
    "isatap",
    "pseudo",
    "npcap",
    "anyconnect",
    "tap",
    "tun",
    "hyper-v",
    "tailscale",
    "zerotier",
    "wireguard",
    "clash",
    "sing-box",
    "fortinet",
    "cisco",
    "openvpn",
    "hamachi",
    "radmin",
    "host-only",
    "vpn",
]

_adapter_desc_cache: Optional[Dict[str, str]] = None


def get_windows_adapter_descriptions() -> Dict[str, str]:
    """Retrieve Windows network adapter friendly names mapped to their driver descriptions."""
    global _adapter_desc_cache
    if _adapter_desc_cache is not None:
        return _adapter_desc_cache

    _adapter_desc_cache = {}
    import sys
    if sys.platform == "win32":
        try:
            import subprocess
            import json
            cmd = "Get-NetAdapter | Select-Object Name, InterfaceDescription | ConvertTo-Json"
            out = subprocess.check_output(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
                text=True,
                timeout=2,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
            )
            data = json.loads(out)
            if isinstance(data, dict):
                data = [data]
            for item in data:
                name = item.get("Name", "")
                desc = item.get("InterfaceDescription", "")
                if name:
                    _adapter_desc_cache[name.strip().lower()] = desc.strip().lower()
        except Exception as e:
            logger.debug(f"Could not query Get-NetAdapter descriptions: {e}")
    return _adapter_desc_cache


def is_virtual_adapter(name: str, description: str = "") -> bool:
    """Check if network interface name or description belongs to a virtual or tunnel device."""
    lower_name = name.lower()
    lower_desc = description.lower()
    return any(
        keyword in lower_name or keyword in lower_desc
        for keyword in VIRTUAL_ADAPTER_KEYWORDS
    )


def is_port_in_use(port: int, host: str = "0.0.0.0") -> bool:
    """Check if a TCP port is currently occupied."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return False
        except OSError:
            return True


def find_available_port(start_port: int = 8000, max_attempts: int = 30) -> int:
    """Scan and return the first available open TCP port."""
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("0.0.0.0", port))
                return port
            except OSError:
                continue
    return start_port


def is_valid_lan_ip(ip: str) -> bool:
    """Check if IP address is a valid non-loopback, non-link-local IPv4 address."""
    if not ip or ":" in ip:
        return False
    parts = ip.split(".")
    if len(parts) != 4:
        return False
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return False

    # Filter loopback 127.0.0.0/8
    if nums[0] == 127:
        return False
    # Filter APIPA / link-local 169.254.0.0/16
    if nums[0] == 169 and nums[1] == 254:
        return False
    # Filter 0.0.0.0
    if nums[0] == 0:
        return False
    # Filter broadcast / multicast 224.0.0.0+
    if nums[0] >= 224:
        return False

    return True


def get_all_lan_ips() -> List[Dict[str, Any]]:
    """
    Scan all active physical network interfaces and return ranked candidate IPv4s.
    Active Wi-Fi adapters (Wi-Fi, WLAN) receive top priority for cross-device mobile sharing.
    """
    candidates: List[Dict[str, Any]] = []
    descriptions = get_windows_adapter_descriptions()

    try:
        stats = psutil.net_if_stats()
        addrs = psutil.net_if_addrs()

        for iface_name, addr_list in addrs.items():
            desc = descriptions.get(iface_name.strip().lower(), "")
            if is_virtual_adapter(iface_name, desc):
                continue

            stat = stats.get(iface_name)
            if not stat or not stat.isup:
                continue

            lower = iface_name.lower()
            lower_desc = desc.lower()
            is_wifi = any(w in lower or w in lower_desc for w in ["wi-fi", "wifi", "wlan", "wireless", "802.11"])
            is_eth = any(e in lower or e in lower_desc for e in ["ethernet", "eth", "gbe", "gigabit", "realtek", "intel"])

            for addr in addr_list:
                if addr.family == socket.AF_INET and is_valid_lan_ip(addr.address):
                    priority = 100 if is_wifi else (70 if is_eth else 40)
                    type_str = "Wi-Fi" if is_wifi else ("Ethernet" if is_eth else "LAN")
                    candidates.append({
                        "name": iface_name,
                        "ip": addr.address,
                        "priority": priority,
                        "is_wifi": is_wifi,
                        "type": type_str,
                        "label": f"{iface_name} ({addr.address}) [{type_str}]"
                    })

        candidates.sort(key=lambda x: x["priority"], reverse=True)
    except Exception as e:
        logger.debug(f"get_all_lan_ips error: {e}")

    # Fallback if no interface detected
    if not candidates:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.settimeout(0.5)
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
                if is_valid_lan_ip(ip):
                    candidates.append({
                        "name": "Default Network",
                        "ip": ip,
                        "priority": 50,
                        "is_wifi": False,
                        "type": "LAN",
                        "label": f"Default ({ip})"
                    })
        except Exception:
            pass

    return candidates


def get_local_ip() -> str:
    """
    Reliably detect the primary active local Wi-Fi or Ethernet IPv4 address.
    Prioritizes active Wi-Fi adapters so mobile devices on the same Wi-Fi connect seamlessly.
    """
    candidates = get_all_lan_ips()
    if candidates:
        logger.info(f"Primary detected LAN IP: {candidates[0]['ip']} ({candidates[0]['name']})")
        return candidates[0]["ip"]

    # Final fallback
    try:
        host_ip = socket.gethostbyname(socket.gethostname())
        if is_valid_lan_ip(host_ip):
            return host_ip
    except Exception:
        pass

    return "127.0.0.1"


def generate_qr_image(url: str, box_size: int = 8, border: int = 2) -> Image.Image:
    """
    Generate a high-quality QR Code image for the given pairing URL.
    """
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0f172a", back_color="#ffffff").convert("RGBA")
    return img


def generate_qr_base64(url: str, box_size: int = 8, border: int = 2) -> str:
    """
    Generate a base64-encoded PNG data URI of the QR code.
    """
    img = generate_qr_image(url, box_size=box_size, border=border)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    b64_str = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64_str}"
