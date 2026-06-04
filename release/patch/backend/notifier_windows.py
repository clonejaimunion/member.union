"""Standalone Windows notifier for deposit maturity reminders.

Runs every hour via Task Scheduler. Works completely independently:
- Reads deposits directly from MongoDB (no HTTP backend dependency).
- Triggers notifications via PowerShell + Windows.UI.Notifications API.
- Works whether the main app is open or closed.
- NO third-party dependencies beyond pymongo (already bundled).

Strictly informational — never touches accounting state.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
import traceback
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ----- configuration -----
DEFAULT_THRESHOLD_DAYS = 30
URGENT_THRESHOLD_DAYS = 7
APP_USER_MODEL_ID = "BankDepositInterestSystem"
TOAST_APP_NAME = "نظام النقابة العامة"

INSTALL_DIR = Path(__file__).resolve().parent.parent  # backend/ → install root
LOG_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Bank Deposit Interest System" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "notifier.log"
SEEN_PATH = LOG_DIR / "notifier_seen.json"
SHOW_TOAST_PS1 = INSTALL_DIR / "show_toast.ps1"
LAUNCHER_VBS = INSTALL_DIR / "launch_bank_deposit_system.vbs"

logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
LOGGER = logging.getLogger("notifier")


def load_seen() -> dict:
    """Return a dict {notification_id: read_status_str}."""
    try:
        if SEEN_PATH.exists():
            data = json.loads(SEEN_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
            if isinstance(data, list):  # legacy format
                return {item: "shown" for item in data}
    except Exception as error:
        LOGGER.warning("seen file unreadable: %s", error)
    return {}


def save_seen(seen: dict) -> None:
    try:
        SEEN_PATH.write_text(json.dumps(seen, ensure_ascii=False), encoding="utf-8")
    except Exception as error:
        LOGGER.warning("seen file write failed: %s", error)


def read_env_file(env_path: Path) -> dict:
    values: dict[str, str] = {}
    try:
        if not env_path.exists():
            return values
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip().strip('"').strip("'")
    except Exception as error:
        LOGGER.warning("env file read failed: %s", error)
    return values


def open_mongo_client():
    """Connect to the local MongoDB instance bundled with the app."""
    try:
        from pymongo import MongoClient  # type: ignore
    except Exception as import_error:
        LOGGER.error("pymongo not available: %s", import_error)
        return None, None
    env = read_env_file(INSTALL_DIR / "backend" / ".env")
    mongo_url = env.get("MONGO_URL") or "mongodb://localhost:27017"
    db_name = env.get("DB_NAME") or "bank_deposit_system"
    try:
        client = MongoClient(mongo_url, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
        return client, client[db_name]
    except Exception as conn_error:
        LOGGER.error("mongo connect failed (%s): %s", mongo_url, conn_error)
        return None, None


def show_powershell_toast(notification: dict) -> bool:
    """Invoke the bundled PowerShell script — works on any Windows 10/11."""
    try:
        title = notification.get("title") or "تنبيه استحقاق وديعة"
        deposit_number = notification.get("deposit_number") or ""
        bank_name = notification.get("bank_name") or "—"
        amount = f"{float(notification.get('amount') or 0):,.0f}"
        maturity = notification.get("maturity_date") or ""
        days = int(notification.get("days_remaining") or 0)
        nid = notification.get("id") or str(uuid.uuid4())

        line1 = f"وديعة {deposit_number} — {bank_name}"
        line2 = f"المبلغ: {amount} جنيه"
        line3 = f"تاريخ الاستحقاق: {maturity} — متبقي {days} يوم"

        if not SHOW_TOAST_PS1.exists():
            LOGGER.error("powershell script not found: %s", SHOW_TOAST_PS1)
            return False

        command = [
            "powershell.exe",
            "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-File", str(SHOW_TOAST_PS1),
            "-Title", title,
            "-Line1", line1,
            "-Line2", line2,
            "-Line3", line3,
            "-LauncherPath", str(LAUNCHER_VBS),
            "-NotificationId", nid,
        ]
        creationflags = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW
        result = subprocess.run(command, capture_output=True, text=True, timeout=60, creationflags=creationflags)
        if result.returncode != 0:
            LOGGER.warning("powershell toast returned %s: %s", result.returncode, result.stderr[:200])
            return False
        return True
    except Exception as error:
        LOGGER.error("show_powershell_toast failed: %s\n%s", error, traceback.format_exc())
        return False


def build_message(amount: float, bank_name: str, deposit_number: str, creation_date: str, maturity_date: str, days_remaining: int) -> str:
    formatted_amount = f"{amount:,.0f}"
    word = "أيام" if days_remaining != 1 else "يوم"
    return (
        f"رقم الوديعة: {deposit_number}\n"
        f"قيمة الوديعة: {formatted_amount} جنيه\n"
        f"البنك: {bank_name}\n"
        f"تاريخ الربط: {creation_date}\n"
        f"تاريخ الاستحقاق: {maturity_date}\n\n"
        f"متبقي {days_remaining} {word} على موعد الاستحقاق.\n"
        "يرجى مراجعة الوديعة واتخاذ القرار المناسب."
    )


def scan_and_collect(db) -> list:
    """Find all active deposits maturing within DEFAULT_THRESHOLD_DAYS.

    Strictly read-only: NEVER writes to deposits, journal_entries, etc.
    """
    today = datetime.now(timezone.utc).date()
    cutoff = today + timedelta(days=DEFAULT_THRESHOLD_DAYS)
    results: list[dict] = []
    try:
        cursor = db.deposits.find({"status": "active"}, {"_id": 0})
        for deposit in cursor:
            try:
                maturity = deposit.get("maturity_datetime")
                if not isinstance(maturity, datetime):
                    continue
                maturity_date = maturity.date()
                if maturity_date < today or maturity_date > cutoff:
                    continue
                remaining = (maturity_date - today).days
                bank = db.banks.find_one({"id": deposit.get("bank_id")}, {"_id": 0, "name": 1})
                bank_name = (bank or {}).get("name") or "—"
                creation = deposit.get("creation_datetime")
                creation_str = creation.date().isoformat() if isinstance(creation, datetime) else "—"
                maturity_str = maturity_date.isoformat()
                notification_id = f"{deposit.get('id')}::{today.isoformat()}"
                results.append({
                    "id": notification_id,
                    "deposit_id": deposit.get("id"),
                    "deposit_number": deposit.get("deposit_number") or "",
                    "bank_id": deposit.get("bank_id"),
                    "bank_name": bank_name,
                    "amount": float(deposit.get("amount") or 0),
                    "creation_date": creation_str,
                    "maturity_date": maturity_str,
                    "days_remaining": remaining,
                    "urgency": "urgent" if remaining <= URGENT_THRESHOLD_DAYS else "upcoming",
                    "title": "تنبيه استحقاق وديعة" if remaining > URGENT_THRESHOLD_DAYS else "⚠️ استحقاق عاجل",
                    "organization_id": deposit.get("organization_id") or "",
                    "message": build_message(
                        float(deposit.get("amount") or 0),
                        bank_name,
                        deposit.get("deposit_number") or "",
                        creation_str,
                        maturity_str,
                        remaining,
                    ),
                })
            except Exception as row_error:
                LOGGER.warning("row processing error: %s", row_error)
    except Exception as outer_error:
        LOGGER.error("scan failure: %s", outer_error)
    return results


def persist_to_db(db, notification: dict) -> None:
    """Mirror the notification into the database so the in-app bell can show it."""
    try:
        document = {
            "id": str(uuid.uuid4()),
            "organization_id": notification.get("organization_id") or "",
            "bank_id": notification.get("bank_id") or "",
            "bank_name": notification.get("bank_name") or "—",
            "deposit_id": notification.get("deposit_id") or "",
            "deposit_number": notification.get("deposit_number") or "",
            "account_number": "",
            "amount": float(notification.get("amount") or 0),
            "creation_date": notification.get("creation_date") or "",
            "maturity_date": notification.get("maturity_date") or "",
            "days_remaining": int(notification.get("days_remaining") or 0),
            "notification_date": datetime.now(timezone.utc).date().isoformat(),
            "title": notification.get("title") or "تنبيه استحقاق وديعة",
            "message": notification.get("message") or "",
            "urgency": notification.get("urgency") or "upcoming",
            "status": "unread",
            "created_at": datetime.now(timezone.utc),
            "sent_at": datetime.now(timezone.utc),
            "read_at": None,
            "read_by": None,
            "delivery_channels": ["windows_toast", "in_app"],
        }
        # Unique by (org, deposit, day) — duplicates silently ignored.
        db.deposit_notifications.update_one(
            {
                "organization_id": document["organization_id"],
                "deposit_id": document["deposit_id"],
                "notification_date": document["notification_date"],
            },
            {"$setOnInsert": document},
            upsert=True,
        )
    except Exception as error:
        LOGGER.warning("db mirror failed: %s", error)


def run_once() -> None:
    client, db = open_mongo_client()
    if db is None:
        LOGGER.info("mongo unavailable — skipping this run")
        return
    try:
        notifications = scan_and_collect(db)
        if not notifications:
            LOGGER.info("no deposits within threshold")
            return
        seen = load_seen()
        today_iso = datetime.now(timezone.utc).date().isoformat()
        new_count = 0
        for notification in notifications:
            persist_to_db(db, notification)
            seen_key = notification["id"]
            if seen.get(seen_key):
                continue
            shown = show_powershell_toast(notification)
            if shown:
                seen[seen_key] = today_iso
                new_count += 1
        if new_count:
            save_seen(seen)
        LOGGER.info("scan complete: %d candidates, %d new toasts", len(notifications), new_count)
    finally:
        try:
            client.close()
        except Exception:
            pass


def main_loop() -> None:
    """Long-running mode (kept for compatibility). One-shot is preferred via Task Scheduler."""
    LOGGER.info("notifier started (long-run mode)")
    while True:
        try:
            run_once()
        except Exception as error:
            LOGGER.error("run_once crashed: %s\n%s", error, traceback.format_exc())
        time.sleep(3600)  # 1 hour


if __name__ == "__main__":
    # One-shot if --once, else long-running.
    if "--once" in sys.argv:
        run_once()
    else:
        run_once()
        if "--loop" in sys.argv:
            main_loop()
