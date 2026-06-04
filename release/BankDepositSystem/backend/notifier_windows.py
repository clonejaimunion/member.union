"""Windows background notifier for deposit maturity reminders.

This script runs entirely outside the FastAPI server. It is launched at
Windows startup via Task Scheduler and runs in the background (no console).

Responsibilities:
- Every 6 hours, hit the local backend endpoint /api/notifications/deposits
  and read unread deposit-maturity notifications.
- Pop a sticky Windows toast for each new unread notification using
  the standard winrt API (no third-party AI, no internet calls).
- Each toast has two action buttons:
    * "تم القراءة"      → calls /api/notifications/deposits/{id}/read
    * "فتح الوديعة"     → launches the desktop launcher and deep-links the deposit.
- Sticky behavior: toast scenario "reminder" stays visible until the user
  interacts with it (per Microsoft documentation).
- On any failure, log to %LOCALAPPDATA%/Bank Deposit Interest System/logs/
  and continue silently — never crash the host machine.

Strictly informational. NEVER modifies accounting state — only reads
notifications and posts the read flag.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
import traceback
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

BACKEND_BASE = os.environ.get("BANK_DEPOSIT_BACKEND_URL", "http://127.0.0.1:8001")
POLL_INTERVAL_SECONDS = int(os.environ.get("BANK_DEPOSIT_NOTIFIER_INTERVAL", str(6 * 60 * 60)))
APP_USER_MODEL_ID = "BankDepositInterestSystem.Notifier"
TOAST_APP_NAME = "نظام النقابة العامة"

LOG_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Bank Deposit Interest System" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
SEEN_PATH = LOG_DIR / "notifier_seen.json"
LOG_FILE = LOG_DIR / "notifier.log"

logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
LOGGER = logging.getLogger("notifier")


def load_seen() -> set:
    try:
        if SEEN_PATH.exists():
            return set(json.loads(SEEN_PATH.read_text(encoding="utf-8")))
    except Exception as error:
        LOGGER.warning("seen file unreadable: %s", error)
    return set()


def save_seen(seen: set) -> None:
    try:
        SEEN_PATH.write_text(json.dumps(sorted(seen)), encoding="utf-8")
    except Exception as error:
        LOGGER.warning("seen file write failed: %s", error)


def http_json(method: str, url: str, payload: dict | None = None, headers: dict | None = None, timeout: int = 8) -> dict | None:
    """Tiny urllib wrapper — avoids adding any third-party dependency."""
    try:
        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=data, method=method, headers=headers or {})
        if data is not None:
            request.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except Exception as error:
        LOGGER.warning("http %s %s failed: %s", method, url, error)
        return None


def fetch_unread_notifications(token: str | None) -> list:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    data = http_json("GET", f"{BACKEND_BASE}/api/notifications/deposits?only_unread=true&limit=50", headers=headers)
    if not data:
        return []
    return data.get("items") or []


def mark_read(notification_id: str, token: str | None) -> None:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    http_json("POST", f"{BACKEND_BASE}/api/notifications/deposits/{notification_id}/read", payload={}, headers=headers)


def open_deposit_in_app(notification: dict) -> None:
    """Launch the desktop app and deep-link the deposit registration screen."""
    try:
        launcher = Path(os.environ.get("BANK_DEPOSIT_LAUNCHER", "")) or None
        if not launcher or not launcher.exists():
            program_files = Path(os.environ.get("LOCALAPPDATA", "")) / "Bank Deposit Interest System"
            candidate = program_files / "launch_bank_deposit_system.vbs"
            if candidate.exists():
                launcher = candidate
        if launcher and launcher.exists():
            subprocess.Popen(["wscript.exe", str(launcher)], shell=False)
        # The launcher itself only opens the front page. We additionally
        # write a "pending_deep_link" hint that the frontend can pick up
        # at startup via /api/notifications/deposits and navigate to it.
        hint = LOG_DIR / "pending_open_deposit.json"
        hint.write_text(json.dumps({
            "bank_id": notification.get("bank_id"),
            "deposit_id": notification.get("deposit_id"),
            "deposit_number": notification.get("deposit_number"),
            "ts": datetime.utcnow().isoformat() + "Z",
        }), encoding="utf-8")
    except Exception as error:
        LOGGER.warning("launcher open failed: %s", error)


def show_toast(notification: dict, token: str | None) -> None:
    """Pop a sticky Windows toast using winrt. No-op on non-Windows."""
    try:
        try:
            from windows_toasts import (  # type: ignore
                Toast,
                ToastButton,
                ToastDuration,
                ToastScenario,
                WindowsToaster,
            )
        except ImportError:
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "--no-index", "--find-links", str(Path(__file__).parent / "wheels_win"), "windows-toasts"], timeout=60)
            except Exception:
                LOGGER.warning("windows-toasts not installed; skipping toast for %s", notification.get("id"))
                return
            from windows_toasts import Toast, ToastButton, ToastDuration, ToastScenario, WindowsToaster  # type: ignore

        toaster = WindowsToaster(TOAST_APP_NAME)
        toast = Toast()
        toast.text_fields = [
            notification.get("title") or "تنبيه استحقاق وديعة",
            f"وديعة {notification.get('deposit_number','')} — {notification.get('bank_name','')}",
            f"{notification.get('amount',0):,.0f} جنيه — استحقاق {notification.get('maturity_date','')} (متبقي {notification.get('days_remaining',0)} يوم)",
        ]
        toast.scenario = ToastScenario.Reminder  # sticky until user interacts
        toast.duration = ToastDuration.Long
        toast.AddAction(ToastButton("تم القراءة", arguments=f"read:{notification.get('id')}"))
        toast.AddAction(ToastButton("فتح الوديعة", arguments=f"open:{notification.get('id')}"))

        def on_activated(event):
            try:
                arg = (getattr(event, "arguments", "") or "")
                if arg.startswith("read:"):
                    mark_read(notification.get("id"), token)
                elif arg.startswith("open:"):
                    mark_read(notification.get("id"), token)
                    open_deposit_in_app(notification)
            except Exception as cb_error:
                LOGGER.warning("activation callback error: %s", cb_error)

        def on_dismissed(_event):
            # Sticky reminder dismissed without choosing → stays unread until next scan.
            pass

        toast.on_activated = on_activated
        toast.on_dismissed = on_dismissed
        toaster.show_toast(toast)
        LOGGER.info("toast shown for notification %s", notification.get("id"))
    except Exception as error:
        LOGGER.error("show_toast failed: %s\n%s", error, traceback.format_exc())


def read_token() -> str | None:
    """Read the last logged-in user token from the standard location.

    The frontend stores the JWT in localStorage under `bank_auth_token`.
    The backend writes a parallel mirror to %LOCALAPPDATA%/Bank Deposit
    Interest System/notifier_token.txt to bridge to background service.
    If the file is missing, return None and skip authenticated calls.
    """
    token_file = LOG_DIR.parent / "notifier_token.txt"
    try:
        if token_file.exists():
            return token_file.read_text(encoding="utf-8").strip() or None
    except Exception as error:
        LOGGER.warning("token read failed: %s", error)
    return None


def run_once() -> None:
    seen = load_seen()
    token = read_token()
    notifications = fetch_unread_notifications(token)
    if not notifications:
        return
    new_ids = set()
    for notification in notifications:
        notification_id = notification.get("id")
        if not notification_id or notification_id in seen:
            continue
        show_toast(notification, token)
        new_ids.add(notification_id)
    if new_ids:
        save_seen(seen | new_ids)


def main_loop() -> None:
    LOGGER.info("notifier starting (interval=%ss, backend=%s)", POLL_INTERVAL_SECONDS, BACKEND_BASE)
    while True:
        try:
            run_once()
        except Exception as error:
            LOGGER.error("run_once crashed: %s\n%s", error, traceback.format_exc())
        time.sleep(max(60, POLL_INTERVAL_SECONDS))


if __name__ == "__main__":
    main_loop()
