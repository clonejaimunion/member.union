"""Deposit maturity notifications module.

Generates non-intrusive reminders for deposits that are about to mature.
This module is strictly informational: it does NOT touch any accounting
state (journal entries, ledgers, trial balance, financial statements,
or bank reconciliations). It only reads from the `deposits` collection
and writes to a dedicated `deposit_notifications` collection.

Key responsibilities:
1) Scan active deposits daily and create one notification per (deposit, date).
2) Mark/track read state per user.
3) Provide endpoints to list unread/all notifications and act on them.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, time, timedelta, timezone
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, ConfigDict, Field


LOGGER = logging.getLogger("deposit_notifications")
DEFAULT_THRESHOLD_DAYS = 365  # show all active deposits maturing within a year
URGENT_THRESHOLD_DAYS = 7


router = APIRouter(prefix="/notifications", tags=["notifications"])


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def today_iso() -> str:
    return now_utc().date().isoformat()


def days_until(maturity_dt: datetime) -> int:
    today = now_utc().date()
    return (maturity_dt.date() - today).days


class MaturityNotification(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    organization_id: str
    bank_id: str
    bank_name: str
    deposit_id: str
    deposit_number: str
    account_number: str
    amount: float
    creation_date: str
    maturity_date: str
    days_remaining: int
    notification_date: str
    title: str = Field(default="تنبيه استحقاق وديعة")
    message: str
    urgency: Literal["urgent", "upcoming"] = "upcoming"
    status: Literal["unread", "read"] = "unread"
    created_at: datetime
    sent_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    read_by: Optional[str] = None
    delivery_channels: List[str] = Field(default_factory=list)


class NotificationReadResponse(BaseModel):
    success: bool
    notification: MaturityNotification


class NotificationListResponse(BaseModel):
    items: List[MaturityNotification]
    unread_count: int
    total_count: int


class ScanSummary(BaseModel):
    scanned_at: datetime
    threshold_days: int
    candidates_checked: int
    notifications_created: int
    notifications_skipped_duplicate: int
    errors: List[str] = Field(default_factory=list)


def build_message(amount: float, bank_name: str, deposit_number: str, creation_date: str, maturity_date: str, days_remaining: int) -> str:
    """Build the Arabic notification body — exactly as specified in the requirement."""
    formatted_amount = f"{amount:,.0f}"
    return (
        f"رقم الوديعة: {deposit_number}\n"
        f"قيمة الوديعة: {formatted_amount} جنيه\n"
        f"البنك: {bank_name}\n"
        f"تاريخ الربط: {creation_date}\n"
        f"تاريخ الاستحقاق: {maturity_date}\n\n"
        f"متبقي {days_remaining} {'أيام' if days_remaining != 1 else 'يوم'} على موعد الاستحقاق.\n"
        "يرجى مراجعة الوديعة واتخاذ القرار المناسب."
    )


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    """Idempotent index creation."""
    await db.deposit_notifications.create_index(
        [("organization_id", 1), ("deposit_id", 1), ("notification_date", 1)],
        unique=True,
        name="uniq_org_deposit_date",
    )
    await db.deposit_notifications.create_index([("organization_id", 1), ("status", 1)])
    await db.deposit_notifications.create_index("created_at")


async def scan_and_create_notifications(db: AsyncIOMotorDatabase, threshold_days: int = DEFAULT_THRESHOLD_DAYS) -> ScanSummary:
    """Scan active deposits and create notifications for those within `threshold_days` of maturity.

    - Strictly read-only on `deposits` (no status changes here).
    - Idempotent per (deposit, calendar day) via unique index — duplicates are silently skipped.
    """
    summary = ScanSummary(
        scanned_at=now_utc(),
        threshold_days=threshold_days,
        candidates_checked=0,
        notifications_created=0,
        notifications_skipped_duplicate=0,
    )
    today_str = today_iso()
    today_dt = now_utc().date()
    cutoff = today_dt + timedelta(days=threshold_days)
    try:
        cursor = db.deposits.find({"status": "active"}, {"_id": 0})
        async for deposit in cursor:
            summary.candidates_checked += 1
            try:
                maturity = deposit.get("maturity_datetime")
                if not isinstance(maturity, datetime):
                    continue
                maturity_date = maturity.date()
                if maturity_date < today_dt:
                    continue
                if maturity_date > cutoff:
                    continue
                remaining = (maturity_date - today_dt).days
                bank = await db.banks.find_one({"id": deposit.get("bank_id")}, {"_id": 0, "name": 1})
                bank_name = (bank or {}).get("name") or "—"
                creation_str = deposit.get("creation_datetime").date().isoformat() if isinstance(deposit.get("creation_datetime"), datetime) else "—"
                maturity_str = maturity_date.isoformat()
                deposit_number = deposit.get("deposit_number") or ""
                account_number = deposit.get("account_number") or ""
                amount = float(deposit.get("amount") or 0)
                organization_id = deposit.get("organization_id") or ""
                document = MaturityNotification(
                    id=str(uuid.uuid4()),
                    organization_id=organization_id,
                    bank_id=deposit.get("bank_id") or "",
                    bank_name=bank_name,
                    deposit_id=deposit.get("id") or "",
                    deposit_number=deposit_number,
                    account_number=account_number,
                    amount=amount,
                    creation_date=creation_str,
                    maturity_date=maturity_str,
                    days_remaining=remaining,
                    notification_date=today_str,
                    message=build_message(amount, bank_name, deposit_number, creation_str, maturity_str, remaining),
                    urgency="urgent" if remaining <= URGENT_THRESHOLD_DAYS else "upcoming",
                    status="unread",
                    created_at=now_utc(),
                    sent_at=None,
                    read_at=None,
                    read_by=None,
                    delivery_channels=["in_app"],
                ).model_dump(mode="json")
                try:
                    await db.deposit_notifications.insert_one(document)
                    summary.notifications_created += 1
                except Exception as insert_error:  # duplicate key or transient failure
                    error_text = str(insert_error)
                    if "duplicate key" in error_text.lower() or "E11000" in error_text:
                        summary.notifications_skipped_duplicate += 1
                    else:
                        summary.errors.append(error_text[:200])
                        LOGGER.error("insert error: %s", insert_error)
            except Exception as per_row_error:
                summary.errors.append(str(per_row_error)[:200])
                LOGGER.error("row error: %s", per_row_error)
    except Exception as outer_error:
        summary.errors.append(str(outer_error)[:300])
        LOGGER.error("scan error: %s", outer_error)
    try:
        await db.notification_scan_log.insert_one(summary.model_dump(mode="json"))
    except Exception as log_error:
        LOGGER.error("scan log write failed: %s", log_error)
    return summary


def schedule_daily_scan(scheduler, db: AsyncIOMotorDatabase, run_now: bool = True) -> None:
    """Register a daily APScheduler job that runs the scan every morning at 08:00 server time.

    Also runs an immediate scan on startup so a freshly-installed system shows
    notifications without waiting for the next morning.
    """
    from apscheduler.triggers.cron import CronTrigger

    async def _job():
        try:
            await scan_and_create_notifications(db)
        except Exception as job_error:
            LOGGER.error("scheduled scan failed: %s", job_error)

    scheduler.add_job(
        _job,
        trigger=CronTrigger(hour=8, minute=0),
        id="deposit_maturity_scan_daily",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    if run_now:
        async def _initial():
            try:
                await scan_and_create_notifications(db)
            except Exception as init_error:
                LOGGER.error("initial scan failed: %s", init_error)
        scheduler.add_job(_initial, id="deposit_maturity_scan_initial", replace_existing=True)


def attach_router(api_router: APIRouter, db: AsyncIOMotorDatabase, require_user_dep) -> None:
    """Mount the notifications endpoints under the main api_router."""

    @router.get("/deposits", response_model=NotificationListResponse)
    async def list_deposit_notifications(
        only_unread: bool = False,
        limit: int = 100,
        auto_scan: bool = True,
        include_all_orgs: bool = True,
        current_user: dict = Depends(require_user_dep),
    ):
        organization_id = current_user.get("organization_id")
        # On-demand scan so new deposits show their notification immediately
        # (without waiting for the daily 08:00 cron). Cheap & idempotent.
        if auto_scan:
            try:
                await scan_and_create_notifications(db)
            except Exception as scan_error:
                LOGGER.warning("on-demand scan failed: %s", scan_error)
        # Admin / super-admin can also see notifications across orgs to avoid
        # losing reminders due to organization_id mismatches in mixed datasets.
        is_admin = (current_user.get("role") or "").lower() in {"admin", "super_admin", "superadmin"}
        query: dict = {}
        if not (is_admin and include_all_orgs):
            query["organization_id"] = organization_id or "__none__"
        if only_unread:
            query["status"] = "unread"
        cursor = db.deposit_notifications.find(query, {"_id": 0}).sort([("days_remaining", 1), ("created_at", -1)]).limit(max(1, min(limit, 500)))
        items = await cursor.to_list(length=500)
        unread_filter = {"status": "unread"}
        total_filter: dict = {}
        if not (is_admin and include_all_orgs):
            unread_filter["organization_id"] = organization_id or "__none__"
            total_filter["organization_id"] = organization_id or "__none__"
        unread_count = await db.deposit_notifications.count_documents(unread_filter)
        total_count = await db.deposit_notifications.count_documents(total_filter)
        return NotificationListResponse(items=items, unread_count=unread_count, total_count=total_count)

    @router.post("/deposits/{notification_id}/read", response_model=NotificationReadResponse)
    async def mark_deposit_notification_read(
        notification_id: str,
        current_user: dict = Depends(require_user_dep),
    ):
        organization_id = current_user.get("organization_id")
        is_admin = (current_user.get("role") or "").lower() in {"admin", "super_admin", "superadmin"}
        query: dict = {"id": notification_id}
        if not is_admin:
            query["organization_id"] = organization_id
        existing = await db.deposit_notifications.find_one(query, {"_id": 0})
        if not existing:
            raise HTTPException(status_code=404, detail="التنبيه غير موجود")
        if existing.get("status") == "unread":
            now = now_utc()
            await db.deposit_notifications.update_one(
                {"id": notification_id},
                {"$set": {"status": "read", "read_at": now, "read_by": current_user.get("username") or current_user.get("id")}},
            )
            existing["status"] = "read"
            existing["read_at"] = now
            existing["read_by"] = current_user.get("username") or current_user.get("id")
        return NotificationReadResponse(success=True, notification=existing)

    @router.post("/deposits/scan", response_model=ScanSummary)
    async def trigger_scan(
        threshold_days: int = DEFAULT_THRESHOLD_DAYS,
        current_user: dict = Depends(require_user_dep),
    ):
        """Manual trigger — useful for testing or when the user clicks 'Refresh'."""
        return await scan_and_create_notifications(db, threshold_days=max(1, min(int(threshold_days), 90)))

    api_router.include_router(router)
