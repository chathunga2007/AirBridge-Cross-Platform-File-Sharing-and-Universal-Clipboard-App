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
]


def is_virtual_adapter(name: str) -> bool:
    """Check if network interface name belongs to a virtual or tunnel device."""
    lower_name = name.lower()
    return any(keyword in lower_name for keyword in VIRTUAL_ADAPTER_KEYWORDS)


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
    try:
        stats = psutil.net_if_stats()
        addrs = psutil.net_if_addrs()

        for iface_name, addr_list in addrs.items():
            if is_virtual_adapter(iface_name):
                continue

            stat = stats.get(iface_name)
            if not stat or not stat.isup:
                continue

            lower = iface_name.lower()
            is_wifi = any(w in lower for w in ["wi-fi", "wifi", "wlan", "wireless"])
            is_eth = any(e in lower for e in ["ethernet", "eth", "gbe"])

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
