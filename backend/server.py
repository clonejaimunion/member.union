from fastapi import FastAPI, APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile
from dotenv import load_dotenv
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, List, Literal, Optional
import uuid
from datetime import date, datetime, timedelta, timezone
import calendar
import math
import base64
from io import BytesIO
import re
import urllib.request

import bcrypt
import jwt
import pyotp
import qrcode
from pypdf import PdfReader


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]
JWT_SECRET = os.environ['JWT_SECRET']
JWT_ALGORITHM = "HS256"
ADMIN_USERNAME = os.environ['ADMIN_USERNAME']
ADMIN_INITIAL_PASSWORD = os.environ['ADMIN_INITIAL_PASSWORD']

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")


# Static bank master data. Deposits are stored separately per bank_id in MongoDB.
BANKS = {
    "industrial-development": {
        "id": "industrial-development",
        "name": "بنك التنمية الصناعية",
        "short_name": "IDB",
        "code": "IDB-EG",
        "swift_code": "DIBBEGCA",
    },
    "banque-misr": {
        "id": "banque-misr",
        "name": "بنك مصر",
        "short_name": "BM",
        "code": "BM-EG",
        "swift_code": "BMISEGCX",
    },
    "agricultural-bank": {
        "id": "agricultural-bank",
        "name": "البنك الزراعي",
        "short_name": "ABE",
        "code": "ABE-EG",
        "swift_code": "BDACEGCA",
    },
}

ARABIC_MONTHS = [
    "يناير",
    "فبراير",
    "مارس",
    "أبريل",
    "مايو",
    "يونيو",
    "يوليو",
    "أغسطس",
    "سبتمبر",
    "أكتوبر",
    "نوفمبر",
    "ديسمبر",
]


class Bank(BaseModel):
    id: str
    name: str
    short_name: str
    code: str
    swift_code: Optional[str] = None
    logo_url: Optional[str] = None
    color: Optional[str] = None


class BankCreate(BaseModel):
    name: str = Field(..., min_length=2)
    code: Optional[str] = None
    swift_code: Optional[str] = None
    logo_url: Optional[str] = None
    color: Optional[str] = "#0f172a"


class BankingTariffRules(BaseModel):
    monthly_statement_fee: float = Field(default=0, ge=0)
    payment_order_fee: float = Field(default=0, ge=0)
    incoming_check_internal_fee: float = Field(default=0, ge=0)
    incoming_check_external_percent: float = Field(default=0, ge=0)
    incoming_check_external_min: float = Field(default=0, ge=0)
    incoming_check_external_max: float = Field(default=0, ge=0)
    issued_check_internal_fee: float = Field(default=0, ge=0)
    issued_check_external_percent: float = Field(default=0, ge=0)
    issued_check_external_min: float = Field(default=0, ge=0)
    issued_check_external_max: float = Field(default=0, ge=0)
    outgoing_transfer_percent: float = Field(default=0, ge=0)
    outgoing_transfer_min: float = Field(default=0, ge=0)
    outgoing_transfer_max: float = Field(default=0, ge=0)
    cash_deposit_percent: float = Field(default=0, ge=0)
    cash_deposit_min: float = Field(default=0, ge=0)
    deposit_link_fee: float = Field(default=0, ge=0)


class BankingTariffResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    bank_id: str
    bank_name: str
    account_type: Literal["companies"] = "companies"
    source_type: Optional[Literal["default", "link", "file", "manual"]] = "default"
    source_url: Optional[str] = None
    file_name: Optional[str] = None
    source_label: str
    extraction_status: Literal["default", "extracted", "manual", "failed"] = "default"
    extraction_notes: Optional[str] = None
    extracted_text_preview: Optional[str] = None
    rules: BankingTariffRules
    created_at: datetime
    updated_at: datetime


class DepositBase(BaseModel):
    account_number: str = Field(..., min_length=1)
    deposit_number: str = Field(..., min_length=1)
    amount: float = Field(..., gt=0)
    creation_datetime: datetime
    maturity_datetime: datetime
    monthly_interest_rate: float = Field(..., ge=0)


class DepositCreate(DepositBase):
    pass


class Deposit(DepositBase):
    model_config = ConfigDict(extra="ignore")

    id: str
    bank_id: str
    created_at: datetime
    updated_at: datetime


class InterestRow(BaseModel):
    serial: int
    month: str
    month_number: int
    interest_amount: float
    active_days: float


class InterestReport(BaseModel):
    bank: Bank
    deposit: Deposit
    year: int
    report_type: str
    monthly_interest_amount: float
    total_interest: float
    rows: List[InterestRow]


class UserPermissions(BaseModel):
    enter_deposits: bool = True
    view_reports: bool = True
    edit_deposits: bool = False
    manage_users: bool = False
    manage_reconciliations: bool = True
    manage_revenues: bool = True
    manage_expenses: bool = True


class UserPublic(BaseModel):
    id: str
    username: str
    role: str
    permissions: UserPermissions
    is_active: bool
    totp_enabled: bool = False
    must_change_password: bool = False
    created_at: datetime
    updated_at: datetime


class LoginRequest(BaseModel):
    username: str
    password: str
    otp_code: Optional[str] = None


class AuthResponse(BaseModel):
    token: Optional[str] = None
    user: Optional[UserPublic] = None
    requires_2fa: bool = False
    requires_2fa_setup: bool = False
    temp_token: Optional[str] = None
    message: str


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3)
    password: str = Field(..., min_length=8)
    permissions: UserPermissions = Field(default_factory=UserPermissions)
    is_active: bool = True


class UserUpdate(BaseModel):
    password: Optional[str] = Field(default=None, min_length=8)
    permissions: Optional[UserPermissions] = None
    is_active: Optional[bool] = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)


class TwoFactorSetupResponse(BaseModel):
    otpauth_uri: str
    qr_data_url: str
    manual_secret: str


class TwoFactorVerifyRequest(BaseModel):
    otp_code: str = Field(..., min_length=6, max_length=8)


class PreviousYearBreakdown(BaseModel):
    year: int
    interest_amount: float


class DepositStatementRow(BaseModel):
    serial: int
    deposit_id: str
    account_number: str
    deposit_number: str
    amount: float
    monthly_interest_rate: float
    monthly_interest_amount: float
    current_year_interest: float
    previous_years_interest: float
    total_due_interest: float
    previous_years_breakdown: List[PreviousYearBreakdown]


class BankStatement(BaseModel):
    bank: Bank
    current_year: int
    total_deposit_volume: float
    total_current_year_interest: float
    total_previous_years_interest: float
    total_due_interest: float
    deposits_count: int
    rows: List[DepositStatementRow]


class DepositVolumeRow(BaseModel):
    serial: int
    deposit_id: str
    account_number: str
    deposit_number: str
    amount: float
    monthly_interest_rate: float
    monthly_interest_amount: float


class DepositVolumeStatement(BaseModel):
    bank: Bank
    total_deposit_volume: float
    deposits_count: int
    rows: List[DepositVolumeRow]


class AccruedInterestRow(BaseModel):
    serial: int
    deposit_id: str
    account_number: str
    deposit_number: str
    amount: float
    annual_interest_rate: float
    annual_interest_amount: float
    daily_interest_amount: float
    last_payment_date: str
    accrued_until_date: str
    accrued_days: int
    accrued_interest_amount: float


class AccruedInterestReport(BaseModel):
    bank: Bank
    year: int
    available_years: List[int]
    total_accrued_interest: float
    deposits_count: int
    rows: List[AccruedInterestRow]


class ReconciliationCheck(BaseModel):
    check_number: str = Field(..., min_length=1)
    amount: float = Field(..., ge=0)
    check_date: datetime


class BankReconciliationCreate(BaseModel):
    period_label: Optional[str] = None
    administration: Optional[str] = "النقابة العامة للعاملين بالزراعة والري"
    book_balance: float
    bank_statement_balance: float
    outstanding_checks: List[ReconciliationCheck] = Field(default_factory=list)
    collection_checks: List[ReconciliationCheck] = Field(default_factory=list)


class BankReconciliation(BankReconciliationCreate):
    model_config = ConfigDict(extra="ignore")

    id: str
    bank_id: str
    total_outstanding_checks: float
    total_collection_checks: float
    calculated_balance: float
    difference: float
    is_matched: bool
    status_text: str
    created_at: datetime
    updated_at: datetime


class RevenueBase(BaseModel):
    receipt_number: str = Field(..., min_length=1)
    amount: float = Field(..., gt=0)
    collection_method: Literal["cash", "check", "payment_order"]
    supplier_name: Optional[str] = None
    check_number: Optional[str] = None
    check_clearing_type: Optional[Literal["internal", "external"]] = None
    payment_order_number: Optional[str] = None
    bank_id: str
    dated: date
    value: str = Field(..., min_length=1)
    issued_at: date
    responsible_employee: Literal["يوسف عبدالغني", "دعاء علي"]
    bank_collection_status: Optional[Literal["collected", "under_collection"]] = None


class RevenueCreate(RevenueBase):
    pass


class Revenue(RevenueBase):
    model_config = ConfigDict(extra="ignore")

    id: str
    bank_name: str
    created_at: datetime
    updated_at: datetime


class ExpenseDeduction(BaseModel):
    amount: float = Field(..., ge=0)
    statement: str = Field(..., min_length=1)


class ExpenseBase(BaseModel):
    expense_number: str = Field(..., min_length=1)
    organization_scope: Literal["general_union", "social_solidarity_project"] = "social_solidarity_project"
    expense_category: Literal["general_expenses", "death_benefits"] = "general_expenses"
    payment_method: Literal["cash", "check", "bank_transfer"]
    payee_name: Optional[str] = None
    check_number: Optional[str] = None
    check_clearing_type: Optional[Literal["internal", "external"]] = None
    transfer_number: Optional[str] = None
    transfer_to: Optional[str] = None
    membership_number: Optional[str] = None
    committee: Optional[str] = None
    governorate: Optional[str] = None
    bank_id: str
    gross_amount: float = Field(..., gt=0)
    gross_statement: str = Field(..., min_length=1)
    deductions: List[ExpenseDeduction] = Field(default_factory=list)
    issued_at: date
    responsible_employee: Literal["يوسف عبدالغني", "دعاء علي"]
    bank_payment_status: Optional[Literal["paid", "not_presented"]] = None


class RevenueBankingStatusUpdate(BaseModel):
    bank_collection_status: Literal["collected", "under_collection"]


class ExpenseBankingStatusUpdate(BaseModel):
    bank_payment_status: Literal["paid", "not_presented"]


class BankingManualCharges(BaseModel):
    bank_id: str
    year: int = Field(..., ge=1900, le=2200)
    month: int = Field(..., ge=1, le=12)
    stamp: float = Field(default=0, ge=0)
    bank_correspondence: float = Field(default=0, ge=0)
    correspondence_safekeeping: float = Field(default=0, ge=0)
    internal_transfer_fee: float = Field(default=0, ge=0)
    external_transfer_fee: float = Field(default=0, ge=0)


class BankingManualChargesResponse(BankingManualCharges):
    model_config = ConfigDict(extra="ignore")

    id: str
    bank_name: str
    updated_at: datetime


class ExpenseCreate(ExpenseBase):
    pass


class Expense(ExpenseBase):
    model_config = ConfigDict(extra="ignore")

    id: str
    bank_name: str
    total_deductions: float
    net_amount: float
    created_at: datetime
    updated_at: datetime


def ensure_bank(bank_id: str) -> dict:
    bank = BANKS.get(bank_id)
    if not bank:
        raise HTTPException(status_code=404, detail="البنك غير موجود")
    return bank


def slugify_bank_name(name: str) -> str:
    cleaned = "-".join(name.strip().lower().split())
    safe = "".join(char for char in cleaned if char.isascii() and (char.isalnum() or char in {"-", "_"}))
    return safe or str(uuid.uuid4())


async def get_all_banks() -> List[dict]:
    deleted_documents = await db.deleted_banks.find({}, {"_id": 0, "id": 1}).to_list(500)
    deleted_ids = {document["id"] for document in deleted_documents}
    custom_banks = await db.banks.find({}, {"_id": 0}).sort("created_at", 1).to_list(500)
    merged = list(BANKS.values()) + custom_banks
    seen = set()
    result = []
    for bank in merged:
        if bank["id"] not in seen and bank["id"] not in deleted_ids:
            seen.add(bank["id"])
            result.append(bank)
    return result


async def ensure_bank_async(bank_id: str) -> dict:
    deleted_bank = await db.deleted_banks.find_one({"id": bank_id}, {"_id": 0})
    if deleted_bank:
        raise HTTPException(status_code=404, detail="البنك محذوف أو غير موجود")
    bank = BANKS.get(bank_id)
    if bank:
        return bank
    custom_bank = await db.banks.find_one({"id": bank_id}, {"_id": 0})
    if not custom_bank:
        raise HTTPException(status_code=404, detail="البنك غير موجود")
    return custom_bank


def default_tariff_rules(bank_id: str) -> BankingTariffRules:
    if bank_id == "industrial-development":
        return BankingTariffRules(
            monthly_statement_fee=100,
            payment_order_fee=10,
            incoming_check_internal_fee=20,
            incoming_check_external_percent=0.3,
            incoming_check_external_min=50,
            incoming_check_external_max=500,
            issued_check_internal_fee=20,
            issued_check_external_percent=0.3,
            issued_check_external_min=50,
            issued_check_external_max=500,
            outgoing_transfer_percent=0.2,
            outgoing_transfer_min=50,
            outgoing_transfer_max=500,
            cash_deposit_percent=0.2,
            cash_deposit_min=20,
            deposit_link_fee=0,
        )
    return BankingTariffRules()


def normalize_tariff_text(text: str) -> str:
    replacements = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
    normalized = text.translate(replacements)
    normalized = normalized.replace("٪", "%").replace("٫", ".").replace(",", ".")
    return re.sub(r"\s+", " ", normalized)


def numbers_near(text: str, keywords: List[str], window: int = 360) -> List[float]:
    normalized = normalize_tariff_text(text)
    lowered = normalized.lower()
    positions = [lowered.find(keyword.lower()) for keyword in keywords if lowered.find(keyword.lower()) != -1]
    if not positions:
        return []
    start = max(min(positions) - 80, 0)
    end = min(max(positions) + window, len(normalized))
    snippet = normalized[start:end]
    return [float(value) for value in re.findall(r"\d+(?:\.\d+)?", snippet)]


def first_reasonable_amount(values: List[float], fallback: float) -> float:
    for value in values:
        if 1 <= value <= 10000 and value not in {0.2, 0.3, 1000, 2024, 2025, 2026}:
            return value
    return fallback


def first_percent(values: List[float], fallback: float) -> float:
    for value in values:
        if 0 < value <= 5:
            return value
    return fallback


def min_max_from_values(values: List[float], fallback_min: float, fallback_max: float) -> tuple[float, float]:
    candidates = [value for value in values if value >= 10 and value not in {2024, 2025, 2026}]
    if len(candidates) >= 2:
        return min(candidates), max(candidates)
    if len(candidates) == 1:
        return candidates[0], fallback_max
    return fallback_min, fallback_max


def parse_tariff_rules_from_text(text: str, bank_id: str) -> tuple[BankingTariffRules, str]:
    rules = default_tariff_rules(bank_id)
    notes = []
    normalized = normalize_tariff_text(text)

    if bank_id == "industrial-development" or "بنك التنمية الصناعية" in normalized:
        return rules, "تم التعرف على تعريفة بنك التنمية الصناعية وتطبيق القيم المعتمدة لحسابات الشركات تلقائياً"

    statement_values = numbers_near(normalized, ["كشف حساب", "شهري"])
    if statement_values:
        rules.monthly_statement_fee = first_reasonable_amount(statement_values, rules.monthly_statement_fee)
        notes.append("رسوم كشف الحساب الشهري")

    payment_order_values = numbers_near(normalized, ["ACH", "أمر دفع", "اوامر الدفع"])
    if payment_order_values:
        rules.payment_order_fee = first_reasonable_amount(payment_order_values, rules.payment_order_fee)
        notes.append("رسوم أوامر الدفع/ACH")

    internal_check_values = numbers_near(normalized, ["تحصيل شيكات", "داخل", "المقاصة"])
    if internal_check_values:
        rules.incoming_check_internal_fee = first_reasonable_amount(internal_check_values, rules.incoming_check_internal_fee)
        rules.issued_check_internal_fee = rules.incoming_check_internal_fee
        notes.append("رسوم الشيكات الداخلية")

    external_check_values = numbers_near(normalized, ["شيكات", "خارج", "المقاصة"])
    if external_check_values:
        rules.incoming_check_external_percent = first_percent(external_check_values, rules.incoming_check_external_percent)
        rules.incoming_check_external_min, rules.incoming_check_external_max = min_max_from_values(
            external_check_values,
            rules.incoming_check_external_min,
            rules.incoming_check_external_max,
        )
        rules.issued_check_external_percent = rules.incoming_check_external_percent
        rules.issued_check_external_min = rules.incoming_check_external_min
        rules.issued_check_external_max = rules.incoming_check_external_max
        notes.append("رسوم الشيكات الخارجية")

    transfer_values = numbers_near(normalized, ["تحويل", "مستفيد", "داخلي"])
    if transfer_values:
        rules.outgoing_transfer_percent = first_percent(transfer_values, rules.outgoing_transfer_percent)
        rules.outgoing_transfer_min, rules.outgoing_transfer_max = min_max_from_values(
            transfer_values,
            rules.outgoing_transfer_min,
            rules.outgoing_transfer_max,
        )
        notes.append("رسوم التحويل البنكي")

    cash_values = numbers_near(normalized, ["إيداع نقدي", "ايداع نقدي", "إيداع"])
    if cash_values:
        rules.cash_deposit_percent = first_percent(cash_values, rules.cash_deposit_percent)
        rules.cash_deposit_min = first_reasonable_amount(cash_values, rules.cash_deposit_min)
        notes.append("عمولة الإيداع النقدي")

    return rules, "تم استخراج: " + "، ".join(notes) if notes else "تم حفظ الملف/الرابط مع استخدام القيم الافتراضية لحين مراجعة الأدمن"


def extract_pdf_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def build_tariff_document(bank: dict, rules: BankingTariffRules, source_type: str = "default", source_url: Optional[str] = None, file_name: Optional[str] = None, notes: Optional[str] = None, preview: Optional[str] = None, status: str = "default") -> dict:
    now = datetime.now(timezone.utc)
    return {
        "id": f"{bank['id']}-companies",
        "bank_id": bank["id"],
        "bank_name": bank["name"],
        "account_type": "companies",
        "source_type": source_type,
        "source_url": source_url,
        "file_name": file_name,
        "source_label": f"تعريفة خدمات {bank['name']} - حسابات الشركات",
        "extraction_status": status,
        "extraction_notes": notes,
        "extracted_text_preview": preview[:2000] if preview else None,
        "rules": rules.model_dump(),
        "created_at": serialize_datetime(now),
        "updated_at": serialize_datetime(now),
    }


async def get_tariff_document(bank_id: str) -> dict:
    bank = await ensure_bank_async(bank_id)
    document = await db.banking_tariffs.find_one({"bank_id": bank_id, "account_type": "companies"}, {"_id": 0})
    if document:
        return document
    return build_tariff_document(bank, default_tariff_rules(bank_id), notes="القيم الافتراضية الحالية", status="default")


def normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def serialize_datetime(value: datetime) -> str:
    return normalize_datetime(value).isoformat()


def serialize_date(value: date) -> str:
    return value.isoformat()


def hydrate_deposit(document: dict) -> dict:
    clean = {key: value for key, value in document.items() if key != "_id"}
    for field_name in ["creation_datetime", "maturity_datetime", "created_at", "updated_at"]:
        if isinstance(clean.get(field_name), str):
            clean[field_name] = datetime.fromisoformat(clean[field_name])
    return clean


def hydrate_reconciliation(document: dict) -> dict:
    clean = {key: value for key, value in document.items() if key != "_id"}
    for field_name in ["created_at", "updated_at"]:
        if isinstance(clean.get(field_name), str):
            clean[field_name] = datetime.fromisoformat(clean[field_name])
    for list_name in ["outstanding_checks", "collection_checks"]:
        for item in clean.get(list_name, []):
            if isinstance(item.get("check_date"), str):
                item["check_date"] = datetime.fromisoformat(item["check_date"])
    return clean


def hydrate_revenue(document: dict) -> dict:
    clean = {key: value for key, value in document.items() if key != "_id"}
    for field_name in ["dated", "issued_at"]:
        if isinstance(clean.get(field_name), str):
            clean[field_name] = date.fromisoformat(clean[field_name])
    for field_name in ["created_at", "updated_at"]:
        if isinstance(clean.get(field_name), str):
            clean[field_name] = datetime.fromisoformat(clean[field_name])
    if clean.get("collection_method") in {"cash", "check", "payment_order"} and not clean.get("bank_collection_status"):
        clean["bank_collection_status"] = "under_collection"
    if clean.get("collection_method") == "check" and not clean.get("check_clearing_type"):
        clean["check_clearing_type"] = "internal"
    return clean


def hydrate_expense(document: dict) -> dict:
    clean = {key: value for key, value in document.items() if key != "_id"}
    if isinstance(clean.get("issued_at"), str):
        clean["issued_at"] = date.fromisoformat(clean["issued_at"])
    for field_name in ["created_at", "updated_at"]:
        if isinstance(clean.get(field_name), str):
            clean[field_name] = datetime.fromisoformat(clean[field_name])
    if clean.get("payment_method") in {"cash", "check", "bank_transfer"} and not clean.get("bank_payment_status"):
        clean["bank_payment_status"] = "not_presented"
    if clean.get("payment_method") == "check" and not clean.get("check_clearing_type"):
        clean["check_clearing_type"] = "internal"
    return clean


def hydrate_banking_manual_charges(document: dict) -> dict:
    clean = {key: value for key, value in document.items() if key != "_id"}
    if isinstance(clean.get("updated_at"), str):
        clean["updated_at"] = datetime.fromisoformat(clean["updated_at"])
    return clean


WESTERN_DIGIT_MAP = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def normalize_digit_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return value.strip().translate(WESTERN_DIGIT_MAP)


async def ensure_revenue_unique(payload: RevenueCreate, revenue_id: Optional[str] = None):
    receipt_number = normalize_digit_text(payload.receipt_number)
    if not receipt_number or not receipt_number.isdigit():
        raise HTTPException(status_code=400, detail="رقم الإذن يجب أن يكون أرقام فقط")
    base_exclusion = {"id": {"$ne": revenue_id}} if revenue_id else {}
    if await db.revenues.find_one({"receipt_number": receipt_number, **base_exclusion}, {"_id": 0, "id": 1}):
        raise HTTPException(status_code=400, detail="رقم الإذن موجود بالفعل ولا يمكن تكراره")

    if payload.collection_method == "cash":
        if not payload.supplier_name or not payload.supplier_name.strip():
            raise HTTPException(status_code=400, detail="يجب إدخال اسم الشخص الذي قام بالتوريد عند اختيار نقداً")
    elif payload.collection_method == "check":
        check_number = normalize_digit_text(payload.check_number)
        if not check_number or not check_number.isdigit():
            raise HTTPException(status_code=400, detail="يجب إدخال رقم شيك صحيح عند اختيار شيك")
        if await db.revenues.find_one({"check_number": check_number, **base_exclusion}, {"_id": 0, "id": 1}):
            raise HTTPException(status_code=400, detail="رقم الشيك موجود بالفعل ولا يمكن تكراره")
    elif payload.collection_method == "payment_order":
        payment_order_number = normalize_digit_text(payload.payment_order_number)
        if not payment_order_number or not payment_order_number.isdigit():
            raise HTTPException(status_code=400, detail="يجب إدخال رقم أمر الدفع عند اختيار أمر دفع")
        if await db.revenues.find_one({"payment_order_number": payment_order_number, **base_exclusion}, {"_id": 0, "id": 1}):
            raise HTTPException(status_code=400, detail="رقم أمر الدفع موجود بالفعل ولا يمكن تكراره")


async def revenue_document_from_payload(payload: RevenueCreate, revenue_id: Optional[str] = None) -> dict:
    bank = await ensure_bank_async(payload.bank_id)
    await ensure_revenue_unique(payload, revenue_id)
    method = payload.collection_method
    return {
        "receipt_number": normalize_digit_text(payload.receipt_number),
        "amount": round(float(payload.amount), 2),
        "collection_method": method,
        "supplier_name": payload.supplier_name.strip() if method == "cash" and payload.supplier_name else None,
        "check_number": normalize_digit_text(payload.check_number) if method == "check" else None,
        "check_clearing_type": payload.check_clearing_type if method == "check" else None,
        "payment_order_number": normalize_digit_text(payload.payment_order_number) if method == "payment_order" else None,
        "bank_id": payload.bank_id,
        "bank_name": bank["name"],
        "dated": serialize_date(payload.dated),
        "value": payload.value.strip(),
        "issued_at": serialize_date(payload.issued_at),
        "responsible_employee": payload.responsible_employee,
        "bank_collection_status": payload.bank_collection_status if method in ["cash", "check", "payment_order"] else None,
    }


async def ensure_expense_unique(payload: ExpenseCreate, expense_id: Optional[str] = None):
    expense_number = normalize_digit_text(payload.expense_number)
    if not expense_number or not expense_number.isdigit():
        raise HTTPException(status_code=400, detail="رقم الإذن يجب أن يكون أرقام فقط")
    base_exclusion = {"id": {"$ne": expense_id}} if expense_id else {}
    if await db.expenses.find_one({"expense_number": expense_number, **base_exclusion}, {"_id": 0, "id": 1}):
        raise HTTPException(status_code=400, detail="رقم الإذن موجود بالفعل داخل المصروفات ولا يمكن تكراره")

    if payload.payment_method == "cash":
        if not payload.payee_name or not payload.payee_name.strip():
            raise HTTPException(status_code=400, detail="يجب إدخال اسم الشخص الذي قام بالصرف له")
    elif payload.payment_method == "check":
        check_number = normalize_digit_text(payload.check_number)
        if not check_number or not check_number.isdigit():
            raise HTTPException(status_code=400, detail="يجب إدخال رقم شيك صحيح")
        if not payload.payee_name or not payload.payee_name.strip():
            raise HTTPException(status_code=400, detail="يجب إدخال اسم يصرف للسيد")
        if await db.expenses.find_one({"check_number": check_number, **base_exclusion}, {"_id": 0, "id": 1}):
            raise HTTPException(status_code=400, detail="رقم الشيك موجود بالفعل داخل المصروفات ولا يمكن تكراره")
    elif payload.payment_method == "bank_transfer":
        transfer_number = normalize_digit_text(payload.transfer_number)
        if not transfer_number or not transfer_number.isdigit():
            raise HTTPException(status_code=400, detail="يجب إدخال رقم عملية التحويل")
        if not payload.transfer_to or not payload.transfer_to.strip():
            raise HTTPException(status_code=400, detail="يجب إدخال اسم الجهة التي تم التحويل إليها")
        if await db.expenses.find_one({"transfer_number": transfer_number, **base_exclusion}, {"_id": 0, "id": 1}):
            raise HTTPException(status_code=400, detail="رقم عملية التحويل موجود بالفعل داخل المصروفات ولا يمكن تكراره")

    if payload.expense_category == "death_benefits":
        if not payload.membership_number or not payload.membership_number.strip():
            raise HTTPException(status_code=400, detail="يجب إدخال رقم العضوية عند اختيار إعانات وفاة")
        if not payload.committee or not payload.committee.strip():
            raise HTTPException(status_code=400, detail="يجب إدخال اللجنة عند اختيار إعانات وفاة")
        if not payload.governorate or not payload.governorate.strip():
            raise HTTPException(status_code=400, detail="يجب إدخال المحافظة عند اختيار إعانات وفاة")


async def expense_document_from_payload(payload: ExpenseCreate, expense_id: Optional[str] = None) -> dict:
    bank = await ensure_bank_async(payload.bank_id)
    await ensure_expense_unique(payload, expense_id)
    deductions = [
        {"amount": round(float(item.amount), 2), "statement": item.statement.strip()}
        for item in payload.deductions
        if float(item.amount) > 0 or item.statement.strip()
    ]
    total_deductions = round(sum(item["amount"] for item in deductions), 2)
    gross_amount = round(float(payload.gross_amount), 2)
    net_amount = round(gross_amount - total_deductions, 2)
    return {
        "expense_number": normalize_digit_text(payload.expense_number),
        "organization_scope": payload.organization_scope,
        "expense_category": payload.expense_category,
        "payment_method": payload.payment_method,
        "payee_name": payload.payee_name.strip() if payload.payment_method in ["cash", "check"] and payload.payee_name else None,
        "check_number": normalize_digit_text(payload.check_number) if payload.payment_method == "check" else None,
        "check_clearing_type": payload.check_clearing_type if payload.payment_method == "check" else None,
        "transfer_number": normalize_digit_text(payload.transfer_number) if payload.payment_method == "bank_transfer" else None,
        "transfer_to": payload.transfer_to.strip() if payload.payment_method == "bank_transfer" and payload.transfer_to else None,
        "membership_number": normalize_digit_text(payload.membership_number) if payload.expense_category == "death_benefits" and payload.membership_number else None,
        "committee": payload.committee.strip() if payload.expense_category == "death_benefits" and payload.committee else None,
        "governorate": payload.governorate.strip() if payload.expense_category == "death_benefits" and payload.governorate else None,
        "bank_id": payload.bank_id,
        "bank_name": bank["name"],
        "gross_amount": gross_amount,
        "gross_statement": payload.gross_statement.strip(),
        "deductions": deductions,
        "total_deductions": total_deductions,
        "net_amount": net_amount,
        "issued_at": serialize_date(payload.issued_at),
        "responsible_employee": payload.responsible_employee,
        "bank_payment_status": payload.bank_payment_status if payload.payment_method in ["cash", "check", "bank_transfer"] else None,
    }


def calculate_reconciliation(payload: BankReconciliationCreate) -> dict:
    total_outstanding = round(sum(item.amount for item in payload.outstanding_checks), 2)
    total_collection = round(sum(item.amount for item in payload.collection_checks), 2)
    calculated_balance = round(payload.book_balance + total_outstanding - total_collection, 2)
    difference = round(calculated_balance - payload.bank_statement_balance, 2)
    is_matched = abs(difference) < 0.01
    return {
        "total_outstanding_checks": total_outstanding,
        "total_collection_checks": total_collection,
        "calculated_balance": calculated_balance,
        "difference": difference,
        "is_matched": is_matched,
        "status_text": "الرصيد مطابق" if is_matched else "الرصيد غير مطابق",
    }


def hydrate_user(document: dict) -> dict:
    clean = {key: value for key, value in document.items() if key not in {"_id", "password_hash", "totp_secret", "totp_pending_secret"}}
    for field_name in ["created_at", "updated_at"]:
        if isinstance(clean.get(field_name), str):
            clean[field_name] = datetime.fromisoformat(clean[field_name])
    return clean


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user: dict, purpose: str = "access", minutes: int = 480) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user["id"],
        "username": user["username"],
        "role": user["role"],
        "purpose": purpose,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=minutes)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def get_current_user(authorization: Optional[str] = Header(default=None, alias="Authorization")) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="يجب تسجيل الدخول أولاً")

    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="جلسة الدخول غير صالحة")

    if payload.get("purpose") != "access":
        raise HTTPException(status_code=401, detail="نوع الجلسة غير صالح")

    user = await db.users.find_one({"id": payload.get("sub")}, {"_id": 0})
    if not user or not user.get("is_active", False):
        raise HTTPException(status_code=401, detail="المستخدم غير نشط أو غير موجود")
    return user


async def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="هذه الصفحة للأدمن فقط")
    return current_user


def require_permission(permission_name: str):
    async def checker(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user.get("role") == "admin":
            return current_user
        permissions = current_user.get("permissions", {})
        if not permissions.get(permission_name, False):
            raise HTTPException(status_code=403, detail="ليس لديك صلاحية لتنفيذ هذه العملية")
        return current_user

    return checker


def require_any_permission(permission_names: List[str]):
    async def checker(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user.get("role") == "admin":
            return current_user
        permissions = current_user.get("permissions", {})
        if not any(permissions.get(permission_name, False) for permission_name in permission_names):
            raise HTTPException(status_code=403, detail="ليس لديك صلاحية لتنفيذ هذه العملية")
        return current_user

    return checker


def public_user(user_document: dict) -> UserPublic:
    return UserPublic(**hydrate_user(user_document))


def days_in_year(year: int) -> int:
    return 365


def calculate_interest_rows(deposit: Deposit, year: int) -> tuple[List[InterestRow], float, float]:
    start = normalize_datetime(deposit.creation_datetime)
    end = normalize_datetime(deposit.maturity_datetime)
    annual_interest = deposit.amount * deposit.monthly_interest_rate / 100
    daily_interest = math.floor((annual_interest / days_in_year(year)) * 100) / 100
    rows = []
    total = 0.0

    for month in range(1, 13):
        month_start = datetime(year, month, 1, tzinfo=timezone.utc)
        next_month = datetime(year + (1 if month == 12 else 0), 1 if month == 12 else month + 1, 1, tzinfo=timezone.utc)

        overlap_start = max(start, month_start)
        overlap_end = min(end, next_month)

        if overlap_end <= overlap_start:
            active_days = 0.0
            interest = 0.0
        else:
            active_days = (overlap_end - overlap_start).total_seconds() / 86400
            interest = daily_interest * active_days

        rounded_interest = round(interest, 2)
        total += rounded_interest
        rows.append(
            InterestRow(
                serial=month,
                month=ARABIC_MONTHS[month - 1],
                month_number=month,
                interest_amount=rounded_interest,
                active_days=round(active_days, 2),
            )
        )

    return rows, round(annual_interest, 2), round(total, 2)


def calculate_daily_interest_amount(deposit: Deposit, year: int) -> tuple[float, float]:
    annual_interest = deposit.amount * deposit.monthly_interest_rate / 100
    daily_interest = math.floor((annual_interest / days_in_year(year)) * 100) / 100
    return round(annual_interest, 2), daily_interest


def payment_date_for_month(year: int, month: int, payment_day: int) -> date:
    month_last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(payment_day, month_last_day))


def latest_payment_date_on_or_before(target_day: date, creation_day: date) -> date:
    payment_day = creation_day.day
    cursor_year = target_day.year
    cursor_month = target_day.month

    for _ in range(36):
        candidate = payment_date_for_month(cursor_year, cursor_month, payment_day)
        if creation_day <= candidate <= target_day:
            return candidate
        cursor_month -= 1
        if cursor_month == 0:
            cursor_month = 12
            cursor_year -= 1

    return creation_day


def calculate_accrued_interest_for_year(deposit: Deposit, year: int) -> dict:
    creation_day = normalize_datetime(deposit.creation_datetime).date()
    maturity_day = normalize_datetime(deposit.maturity_datetime).date()
    today = datetime.now(timezone.utc).date()
    current_year = today.year

    period_start = max(date(year, 1, 1), creation_day)
    nominal_year_end = date(year, 12, 31)
    period_end = min(nominal_year_end, maturity_day)
    if year == current_year:
        period_end = min(period_end, today)

    annual_interest, daily_interest = calculate_daily_interest_amount(deposit, year)

    if year < creation_day.year or year > current_year or period_end <= period_start:
        last_payment_day = period_start
        accrued_days = 0
    else:
        last_payment_day = latest_payment_date_on_or_before(period_end, creation_day)
        last_payment_day = max(last_payment_day, period_start)
        accrued_days = max((period_end - last_payment_day).days, 0)

    accrued_interest = round(daily_interest * accrued_days, 2)
    return {
        "annual_interest_amount": annual_interest,
        "daily_interest_amount": daily_interest,
        "last_payment_date": last_payment_day.isoformat(),
        "accrued_until_date": period_end.isoformat(),
        "accrued_days": accrued_days,
        "accrued_interest_amount": accrued_interest,
    }


async def get_deposit_or_latest(bank_id: str, deposit_id: Optional[str] = None) -> Deposit:
    await ensure_bank_async(bank_id)
    query = {"bank_id": bank_id}
    if deposit_id:
        query["id"] = deposit_id

    cursor = db.deposits.find(query, {"_id": 0}).sort("created_at", -1)
    document = await cursor.to_list(1)
    if not document:
        raise HTTPException(status_code=404, detail="لا توجد وديعة مسجلة لهذا البنك")
    return Deposit(**hydrate_deposit(document[0]))


async def get_bank_deposits(bank_id: str) -> List[Deposit]:
    await ensure_bank_async(bank_id)
    documents = await db.deposits.find({"bank_id": bank_id}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return [Deposit(**hydrate_deposit(document)) for document in documents]


def calculate_year_total(deposit: Deposit, year: int) -> float:
    rows, _, total = calculate_interest_rows(deposit, year)
    return round(sum(row.interest_amount for row in rows), 2) if rows else total


def calculate_previous_years(deposit: Deposit, current_year: int) -> tuple[List[PreviousYearBreakdown], float]:
    start_year = normalize_datetime(deposit.creation_datetime).year
    end_year = min(normalize_datetime(deposit.maturity_datetime).year, current_year - 1)
    breakdown = []
    total = 0.0

    if end_year < start_year:
        return breakdown, 0.0

    for year in range(start_year, end_year + 1):
        year_total = calculate_year_total(deposit, year)
        if year_total > 0:
            breakdown.append(PreviousYearBreakdown(year=year, interest_amount=year_total))
            total += year_total

    return breakdown, round(total, 2)


async def ensure_default_admin():
    await db.users.create_index("username", unique=True)
    existing_admin = await db.users.find_one({"role": "admin"}, {"_id": 0})
    if existing_admin:
        return

    now = datetime.now(timezone.utc)
    admin_permissions = UserPermissions(
        enter_deposits=True,
        view_reports=True,
        edit_deposits=True,
        manage_users=True,
        manage_reconciliations=True,
        manage_revenues=True,
        manage_expenses=True,
    ).model_dump()
    await db.users.insert_one(
        {
            "id": str(uuid.uuid4()),
            "username": ADMIN_USERNAME,
            "password_hash": hash_password(ADMIN_INITIAL_PASSWORD),
            "role": "admin",
            "permissions": admin_permissions,
            "is_active": True,
            "totp_enabled": False,
            "totp_secret": None,
            "totp_pending_secret": None,
            "must_change_password": True,
            "created_at": serialize_datetime(now),
            "updated_at": serialize_datetime(now),
        }
    )


@app.on_event("startup")
async def startup_tasks():
    await ensure_default_admin()
    await db.revenues.create_index("receipt_number", unique=True)
    await db.revenues.create_index("check_number")
    await db.revenues.create_index("payment_order_number")
    await db.expenses.create_index("expense_number")
    await db.expenses.create_index("check_number")
    await db.expenses.create_index("transfer_number")

# Add your routes to the router instead of directly to app
@api_router.get("/")
async def root():
    return {"message": "Bank deposit interest system is running"}


@api_router.get("/download/setup")
async def download_setup_file():
    setup_path = ROOT_DIR.parent / "dist" / "BankDepositSystemSetup.exe"
    if not setup_path.exists():
        raise HTTPException(status_code=404, detail="ملف التثبيت غير موجود حالياً")
    return FileResponse(
        setup_path,
        media_type="application/vnd.microsoft.portable-executable",
        filename="BankDepositSystemSetup.exe",
    )


@api_router.post("/auth/login", response_model=AuthResponse)
async def login(payload: LoginRequest):
    user = await db.users.find_one({"username": payload.username.strip()}, {"_id": 0})
    if not user or not verify_password(payload.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="اسم المستخدم أو كلمة المرور غير صحيحة")
    if not user.get("is_active", False):
        raise HTTPException(status_code=403, detail="هذا المستخدم غير نشط")

    if user.get("role") == "admin" and user.get("totp_enabled"):
        if not payload.otp_code:
            return AuthResponse(
                requires_2fa=True,
                temp_token=create_access_token(user, purpose="2fa", minutes=5),
                message="أدخل كود Google Authenticator لإكمال الدخول",
            )
        totp = pyotp.TOTP(user.get("totp_secret"))
        if not totp.verify(payload.otp_code, valid_window=1):
            raise HTTPException(status_code=401, detail="كود المصادقة الثنائية غير صحيح")

    token = create_access_token(user)
    return AuthResponse(
        token=token,
        user=public_user(user),
        requires_2fa_setup=user.get("role") == "admin" and not user.get("totp_enabled", False),
        message="تم تسجيل الدخول بنجاح",
    )


@api_router.get("/auth/me", response_model=UserPublic)
async def get_me(current_user: dict = Depends(get_current_user)):
    return public_user(current_user)


@api_router.get("/admin/users", response_model=List[UserPublic])
async def list_users(_: dict = Depends(require_admin)):
    users = await db.users.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return [public_user(user) for user in users]


@api_router.post("/admin/users", response_model=UserPublic)
async def create_user(payload: UserCreate, _: dict = Depends(require_admin)):
    existing = await db.users.find_one({"username": payload.username.strip()}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail="اسم المستخدم موجود بالفعل")
    now = datetime.now(timezone.utc)
    document = {
        "id": str(uuid.uuid4()),
        "username": payload.username.strip(),
        "password_hash": hash_password(payload.password),
        "role": "user",
        "permissions": payload.permissions.model_dump(),
        "is_active": payload.is_active,
        "totp_enabled": False,
        "totp_secret": None,
        "totp_pending_secret": None,
        "must_change_password": False,
        "created_at": serialize_datetime(now),
        "updated_at": serialize_datetime(now),
    }
    await db.users.insert_one(document)
    return public_user(document)


@api_router.put("/admin/users/{user_id}", response_model=UserPublic)
async def update_user(user_id: str, payload: UserUpdate, admin_user: dict = Depends(require_admin)):
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    if user.get("role") == "admin" and user.get("id") != admin_user.get("id"):
        raise HTTPException(status_code=403, detail="لا يمكن تعديل أدمن آخر")

    updates = {"updated_at": serialize_datetime(datetime.now(timezone.utc))}
    if payload.password:
        updates["password_hash"] = hash_password(payload.password)
        updates["must_change_password"] = False
    if payload.permissions is not None and user.get("role") != "admin":
        updates["permissions"] = payload.permissions.model_dump()
    if payload.is_active is not None and user.get("role") != "admin":
        updates["is_active"] = payload.is_active

    await db.users.update_one({"id": user_id}, {"$set": updates})
    updated = await db.users.find_one({"id": user_id}, {"_id": 0})
    return public_user(updated)


@api_router.delete("/admin/users/{user_id}")
async def delete_user(user_id: str, admin_user: dict = Depends(require_admin)):
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    if user.get("role") == "admin" or user.get("id") == admin_user.get("id"):
        raise HTTPException(status_code=403, detail="لا يمكن حذف حساب الأدمن")
    result = await db.users.delete_one({"id": user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    return {"message": "تم حذف المستخدم", "deleted_user_id": user_id}


@api_router.post("/admin/change-password", response_model=UserPublic)
async def change_admin_password(payload: ChangePasswordRequest, admin_user: dict = Depends(require_admin)):
    if not verify_password(payload.current_password, admin_user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="كلمة المرور الحالية غير صحيحة")
    updates = {
        "password_hash": hash_password(payload.new_password),
        "must_change_password": False,
        "updated_at": serialize_datetime(datetime.now(timezone.utc)),
    }
    await db.users.update_one({"id": admin_user["id"]}, {"$set": updates})
    updated = await db.users.find_one({"id": admin_user["id"]}, {"_id": 0})
    return public_user(updated)


@api_router.post("/admin/2fa/setup", response_model=TwoFactorSetupResponse)
async def setup_admin_2fa(admin_user: dict = Depends(require_admin)):
    secret = pyotp.random_base32()
    otpauth_uri = pyotp.TOTP(secret).provisioning_uri(
        name=admin_user["username"],
        issuer_name="Bank Deposit Interest System",
    )
    image = qrcode.make(otpauth_uri)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    qr_data_url = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("utf-8")
    await db.users.update_one(
        {"id": admin_user["id"]},
        {"$set": {"totp_pending_secret": secret, "updated_at": serialize_datetime(datetime.now(timezone.utc))}},
    )
    return TwoFactorSetupResponse(otpauth_uri=otpauth_uri, qr_data_url=qr_data_url, manual_secret=secret)


@api_router.post("/admin/2fa/verify", response_model=UserPublic)
async def verify_admin_2fa(payload: TwoFactorVerifyRequest, admin_user: dict = Depends(require_admin)):
    secret = admin_user.get("totp_pending_secret") or admin_user.get("totp_secret")
    if not secret:
        raise HTTPException(status_code=400, detail="ابدأ إعداد المصادقة الثنائية أولاً")
    if not pyotp.TOTP(secret).verify(payload.otp_code, valid_window=1):
        raise HTTPException(status_code=400, detail="كود التحقق غير صحيح")
    await db.users.update_one(
        {"id": admin_user["id"]},
        {
            "$set": {
                "totp_secret": secret,
                "totp_enabled": True,
                "totp_pending_secret": None,
                "updated_at": serialize_datetime(datetime.now(timezone.utc)),
            }
        },
    )
    updated = await db.users.find_one({"id": admin_user["id"]}, {"_id": 0})
    return public_user(updated)


@api_router.get("/banks", response_model=List[Bank])
async def get_banks(_: dict = Depends(get_current_user)):
    return await get_all_banks()


@api_router.post("/admin/banks", response_model=Bank)
async def create_bank(payload: BankCreate, _: dict = Depends(require_admin)):
    bank_id_base = slugify_bank_name(payload.name)
    bank_id = bank_id_base
    suffix = 1
    while BANKS.get(bank_id) or await db.banks.find_one({"id": bank_id}, {"_id": 0}):
        suffix += 1
        bank_id = f"{bank_id_base}-{suffix}"

    now = datetime.now(timezone.utc)
    bank_doc = {
        "id": bank_id,
        "name": payload.name.strip(),
        "short_name": (payload.code or payload.name[:3]).strip().upper(),
        "code": (payload.code or bank_id.upper()).strip().upper(),
        "swift_code": payload.swift_code.strip().upper() if payload.swift_code else None,
        "logo_url": payload.logo_url.strip() if payload.logo_url else None,
        "color": payload.color or "#0f172a",
        "created_at": serialize_datetime(now),
        "updated_at": serialize_datetime(now),
    }
    await db.banks.insert_one(bank_doc)
    default_tariff = build_tariff_document(bank_doc, default_tariff_rules(bank_id), notes="تعريفة افتراضية لبنك جديد لحين رفع ملف التعريفة", status="default")
    await db.banking_tariffs.update_one(
        {"bank_id": bank_id, "account_type": "companies"},
        {"$set": default_tariff},
        upsert=True,
    )
    return Bank(**{key: value for key, value in bank_doc.items() if key not in {"created_at", "updated_at"}})


@api_router.get("/banking-tariffs/{bank_id}", response_model=BankingTariffResponse)
async def get_banking_tariff(bank_id: str, _: dict = Depends(get_current_user)):
    document = await get_tariff_document(bank_id)
    return BankingTariffResponse(**hydrate_banking_manual_charges(document))


@api_router.get("/admin/banking-tariffs", response_model=List[BankingTariffResponse])
async def list_admin_banking_tariffs(_: dict = Depends(require_admin)):
    banks = await get_all_banks()
    documents = []
    for bank in banks:
        document = await get_tariff_document(bank["id"])
        documents.append(BankingTariffResponse(**hydrate_banking_manual_charges(document)))
    return documents


@api_router.put("/admin/banking-tariffs/{bank_id}", response_model=BankingTariffResponse)
async def save_admin_banking_tariff(bank_id: str, rules: BankingTariffRules, _: dict = Depends(require_admin)):
    bank = await ensure_bank_async(bank_id)
    existing = await get_tariff_document(bank_id)
    document = build_tariff_document(
        bank,
        rules,
        source_type="manual",
        source_url=existing.get("source_url"),
        file_name=existing.get("file_name"),
        notes="تم اعتماد القيم يدوياً من الأدمن",
        preview=existing.get("extracted_text_preview"),
        status="manual",
    )
    document["created_at"] = existing.get("created_at") or document["created_at"]
    await db.banking_tariffs.update_one(
        {"bank_id": bank_id, "account_type": "companies"},
        {"$set": document},
        upsert=True,
    )
    return BankingTariffResponse(**hydrate_banking_manual_charges(document))


@api_router.post("/admin/banking-tariffs/{bank_id}/extract", response_model=BankingTariffResponse)
async def extract_admin_banking_tariff(
    bank_id: str,
    source_url: Optional[str] = Form(default=None),
    tariff_file: Optional[UploadFile] = File(default=None),
    _: dict = Depends(require_admin),
):
    bank = await ensure_bank_async(bank_id)
    source_type = "link" if source_url else "file"
    file_name = tariff_file.filename if tariff_file else None
    try:
        if tariff_file:
            pdf_bytes = await tariff_file.read()
            if not tariff_file.filename.lower().endswith(".pdf"):
                raise HTTPException(status_code=400, detail="يجب رفع ملف PDF فقط")
        elif source_url:
            request = urllib.request.Request(source_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(request, timeout=45) as response:
                pdf_bytes = response.read()
            if not source_url.lower().split("?")[0].endswith(".pdf"):
                file_name = source_url.rsplit("/", 1)[-1] or "tariff.pdf"
        else:
            raise HTTPException(status_code=400, detail="ارفع ملف PDF أو أدخل رابط التعريفة")

        extracted_text = extract_pdf_text(pdf_bytes)
        if not extracted_text.strip():
            raise HTTPException(status_code=400, detail="تعذر قراءة نص ملف التعريفة")
        rules, notes = parse_tariff_rules_from_text(extracted_text, bank_id)
        document = build_tariff_document(
            bank,
            rules,
            source_type=source_type,
            source_url=source_url,
            file_name=file_name,
            notes=notes,
            preview=normalize_tariff_text(extracted_text),
            status="extracted",
        )
        await db.banking_tariffs.update_one(
            {"bank_id": bank_id, "account_type": "companies"},
            {"$set": document},
            upsert=True,
        )
        return BankingTariffResponse(**hydrate_banking_manual_charges(document))
    except HTTPException:
        raise
    except Exception as exc:
        rules = default_tariff_rules(bank_id)
        document = build_tariff_document(
            bank,
            rules,
            source_type=source_type,
            source_url=source_url,
            file_name=file_name,
            notes=f"فشل استخراج التعريفة تلقائياً: {str(exc)}",
            status="failed",
        )
        await db.banking_tariffs.update_one(
            {"bank_id": bank_id, "account_type": "companies"},
            {"$set": document},
            upsert=True,
        )
        return BankingTariffResponse(**hydrate_banking_manual_charges(document))


@api_router.delete("/admin/banks/{bank_id}")
async def delete_bank(bank_id: str, _: dict = Depends(require_admin)):
    bank = BANKS.get(bank_id) or await db.banks.find_one({"id": bank_id}, {"_id": 0})
    if not bank:
        raise HTTPException(status_code=404, detail="البنك غير موجود")

    now = datetime.now(timezone.utc)
    await db.deleted_banks.update_one(
        {"id": bank_id},
        {"$set": {"id": bank_id, "name": bank.get("name"), "deleted_at": serialize_datetime(now)}},
        upsert=True,
    )
    await db.banks.delete_one({"id": bank_id})
    await db.banking_tariffs.delete_many({"bank_id": bank_id})
    deposits_result = await db.deposits.delete_many({"bank_id": bank_id})
    reconciliations_result = await db.reconciliations.delete_many({"bank_id": bank_id})
    revenues_result = await db.revenues.delete_many({"bank_id": bank_id})
    expenses_result = await db.expenses.delete_many({"bank_id": bank_id})
    return {
        "message": "تم حذف البنك وكل بياناته بالكامل",
        "deleted_bank_id": bank_id,
        "deleted_deposits": deposits_result.deleted_count,
        "deleted_reconciliations": reconciliations_result.deleted_count,
        "deleted_revenues": revenues_result.deleted_count,
        "deleted_expenses": expenses_result.deleted_count,
    }


@api_router.post("/banks/{bank_id}/deposits", response_model=Deposit)
async def create_deposit(
    bank_id: str,
    payload: DepositCreate,
    _: dict = Depends(require_permission("enter_deposits")),
):
    await ensure_bank_async(bank_id)
    creation_datetime = normalize_datetime(payload.creation_datetime)
    maturity_datetime = normalize_datetime(payload.maturity_datetime)

    if maturity_datetime <= creation_datetime:
        raise HTTPException(status_code=400, detail="تاريخ الاستحقاق يجب أن يكون بعد تاريخ إنشاء الوديعة")

    now = datetime.now(timezone.utc)
    deposit = Deposit(
        id=str(uuid.uuid4()),
        bank_id=bank_id,
        account_number=payload.account_number.strip(),
        deposit_number=payload.deposit_number.strip(),
        amount=payload.amount,
        creation_datetime=creation_datetime,
        maturity_datetime=maturity_datetime,
        monthly_interest_rate=payload.monthly_interest_rate,
        created_at=now,
        updated_at=now,
    )
    document = deposit.model_dump()
    for field_name in ["creation_datetime", "maturity_datetime", "created_at", "updated_at"]:
        document[field_name] = serialize_datetime(document[field_name])

    await db.deposits.insert_one(document)
    return deposit


@api_router.get("/banks/{bank_id}/deposits", response_model=List[Deposit])
async def list_deposits(bank_id: str, _: dict = Depends(require_permission("view_reports"))):
    await ensure_bank_async(bank_id)
    documents = await db.deposits.find({"bank_id": bank_id}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return [Deposit(**hydrate_deposit(document)) for document in documents]


@api_router.get("/banks/{bank_id}/deposits/latest", response_model=Deposit)
async def get_latest_deposit(bank_id: str, _: dict = Depends(require_permission("view_reports"))):
    return await get_deposit_or_latest(bank_id)


@api_router.put("/banks/{bank_id}/deposits/{deposit_id}", response_model=Deposit)
async def update_deposit(
    bank_id: str,
    deposit_id: str,
    payload: DepositCreate,
    _: dict = Depends(require_permission("edit_deposits")),
):
    await ensure_bank_async(bank_id)
    creation_datetime = normalize_datetime(payload.creation_datetime)
    maturity_datetime = normalize_datetime(payload.maturity_datetime)
    if maturity_datetime <= creation_datetime:
        raise HTTPException(status_code=400, detail="تاريخ الاستحقاق يجب أن يكون بعد تاريخ إنشاء الوديعة")

    updates = {
        "account_number": payload.account_number.strip(),
        "deposit_number": payload.deposit_number.strip(),
        "amount": payload.amount,
        "creation_datetime": serialize_datetime(creation_datetime),
        "maturity_datetime": serialize_datetime(maturity_datetime),
        "monthly_interest_rate": payload.monthly_interest_rate,
        "updated_at": serialize_datetime(datetime.now(timezone.utc)),
    }
    result = await db.deposits.update_one({"id": deposit_id, "bank_id": bank_id}, {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="الوديعة غير موجودة")
    updated = await db.deposits.find_one({"id": deposit_id, "bank_id": bank_id}, {"_id": 0})
    return Deposit(**hydrate_deposit(updated))


@api_router.delete("/banks/{bank_id}/deposits/{deposit_id}")
async def delete_deposit(
    bank_id: str,
    deposit_id: str,
    _: dict = Depends(require_admin),
):
    await ensure_bank_async(bank_id)
    result = await db.deposits.delete_one({"id": deposit_id, "bank_id": bank_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="الوديعة غير موجودة")
    return {"message": "تم حذف الوديعة بالكامل", "deleted_deposit_id": deposit_id}


@api_router.get("/banks/{bank_id}/reports/{report_type}", response_model=InterestReport)
async def get_interest_report(
    bank_id: str,
    report_type: str,
    deposit_id: Optional[str] = Query(default=None),
    _: dict = Depends(require_permission("view_reports")),
):
    bank = await ensure_bank_async(bank_id)
    if report_type not in {"current-year", "previous-year"}:
        raise HTTPException(status_code=404, detail="نوع التقرير غير صحيح")

    target_year = datetime.now(timezone.utc).year
    if report_type == "previous-year":
        target_year -= 1

    deposit = await get_deposit_or_latest(bank_id, deposit_id)
    rows, monthly_interest, total = calculate_interest_rows(deposit, target_year)

    return InterestReport(
        bank=Bank(**bank),
        deposit=deposit,
        year=target_year,
        report_type=report_type,
        monthly_interest_amount=monthly_interest,
        total_interest=total,
        rows=rows,
    )


@api_router.get("/banks/{bank_id}/statements/detailed", response_model=BankStatement)
async def get_detailed_statement(bank_id: str, _: dict = Depends(require_permission("view_reports"))):
    bank = await ensure_bank_async(bank_id)
    current_year = datetime.now(timezone.utc).year
    deposits = await get_bank_deposits(bank_id)
    rows = []
    total_volume = 0.0
    total_current = 0.0
    total_previous = 0.0

    for index, deposit in enumerate(deposits, start=1):
        _, annual_interest, current_total = calculate_interest_rows(deposit, current_year)
        previous_breakdown, previous_total = calculate_previous_years(deposit, current_year)
        total_volume += deposit.amount
        total_current += current_total
        total_previous += previous_total
        rows.append(
            DepositStatementRow(
                serial=index,
                deposit_id=deposit.id,
                account_number=deposit.account_number,
                deposit_number=deposit.deposit_number,
                amount=deposit.amount,
                monthly_interest_rate=deposit.monthly_interest_rate,
                monthly_interest_amount=annual_interest,
                current_year_interest=current_total,
                previous_years_interest=previous_total,
                total_due_interest=round(current_total + previous_total, 2),
                previous_years_breakdown=previous_breakdown,
            )
        )

    return BankStatement(
        bank=Bank(**bank),
        current_year=current_year,
        total_deposit_volume=round(total_volume, 2),
        total_current_year_interest=round(total_current, 2),
        total_previous_years_interest=round(total_previous, 2),
        total_due_interest=round(total_current + total_previous, 2),
        deposits_count=len(rows),
        rows=rows,
    )


@api_router.get("/banks/{bank_id}/statements/volume", response_model=DepositVolumeStatement)
async def get_volume_statement(bank_id: str, _: dict = Depends(require_permission("view_reports"))):
    bank = await ensure_bank_async(bank_id)
    deposits = await get_bank_deposits(bank_id)
    rows = []
    total_volume = 0.0

    for index, deposit in enumerate(deposits, start=1):
        annual_interest = round(deposit.amount * deposit.monthly_interest_rate / 100, 2)
        total_volume += deposit.amount
        rows.append(
            DepositVolumeRow(
                serial=index,
                deposit_id=deposit.id,
                account_number=deposit.account_number,
                deposit_number=deposit.deposit_number,
                amount=deposit.amount,
                monthly_interest_rate=deposit.monthly_interest_rate,
                monthly_interest_amount=annual_interest,
            )
        )

    return DepositVolumeStatement(
        bank=Bank(**bank),
        total_deposit_volume=round(total_volume, 2),
        deposits_count=len(rows),
        rows=rows,
    )


@api_router.get("/banks/{bank_id}/accrued-interest", response_model=AccruedInterestReport)
async def get_accrued_interest_report(
    bank_id: str,
    year: Optional[int] = Query(default=None),
    deposit_id: Optional[str] = Query(default=None),
    _: dict = Depends(require_permission("view_reports")),
):
    bank = await ensure_bank_async(bank_id)
    all_deposits = await get_bank_deposits(bank_id)
    deposits = [deposit for deposit in all_deposits if not deposit_id or deposit.id == deposit_id]
    if deposit_id and not deposits:
        raise HTTPException(status_code=404, detail="الوديعة غير موجودة")
    current_year = datetime.now(timezone.utc).year
    min_year = min([normalize_datetime(deposit.creation_datetime).year for deposit in all_deposits], default=current_year)
    available_years = list(range(min_year, current_year + 1))
    target_year = year or current_year

    if target_year < min_year or target_year > current_year:
        raise HTTPException(status_code=400, detail="السنة المختارة خارج نطاق سنوات الودائع")

    rows = []
    total = 0.0
    for index, deposit in enumerate(deposits, start=1):
        accrued = calculate_accrued_interest_for_year(deposit, target_year)
        total += accrued["accrued_interest_amount"]
        rows.append(
            AccruedInterestRow(
                serial=index,
                deposit_id=deposit.id,
                account_number=deposit.account_number,
                deposit_number=deposit.deposit_number,
                amount=deposit.amount,
                annual_interest_rate=deposit.monthly_interest_rate,
                annual_interest_amount=accrued["annual_interest_amount"],
                daily_interest_amount=accrued["daily_interest_amount"],
                last_payment_date=accrued["last_payment_date"],
                accrued_until_date=accrued["accrued_until_date"],
                accrued_days=accrued["accrued_days"],
                accrued_interest_amount=accrued["accrued_interest_amount"],
            )
        )

    return AccruedInterestReport(
        bank=Bank(**bank),
        year=target_year,
        available_years=available_years,
        total_accrued_interest=round(total, 2),
        deposits_count=len(rows),
        rows=rows,
    )


@api_router.post("/banks/{bank_id}/reconciliations", response_model=BankReconciliation)
async def create_bank_reconciliation(
    bank_id: str,
    payload: BankReconciliationCreate,
    _: dict = Depends(require_any_permission(["enter_deposits", "manage_reconciliations"])),
):
    await ensure_bank_async(bank_id)
    now = datetime.now(timezone.utc)
    computed = calculate_reconciliation(payload)
    document = payload.model_dump()
    for list_name in ["outstanding_checks", "collection_checks"]:
        for item in document[list_name]:
            item["check_date"] = serialize_datetime(item["check_date"])
    document.update(
        {
            "id": str(uuid.uuid4()),
            "bank_id": bank_id,
            **computed,
            "created_at": serialize_datetime(now),
            "updated_at": serialize_datetime(now),
        }
    )
    await db.reconciliations.insert_one(document)
    return BankReconciliation(**hydrate_reconciliation(document))


@api_router.get("/banks/{bank_id}/reconciliations", response_model=List[BankReconciliation])
async def list_bank_reconciliations(bank_id: str, _: dict = Depends(require_any_permission(["enter_deposits", "view_reports", "manage_reconciliations"]))):
    await ensure_bank_async(bank_id)
    documents = await db.reconciliations.find({"bank_id": bank_id}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return [BankReconciliation(**hydrate_reconciliation(document)) for document in documents]


@api_router.get("/banks/{bank_id}/reconciliations/latest", response_model=BankReconciliation)
async def get_latest_bank_reconciliation(bank_id: str, _: dict = Depends(require_any_permission(["enter_deposits", "view_reports", "manage_reconciliations"]))):
    await ensure_bank_async(bank_id)
    documents = await db.reconciliations.find({"bank_id": bank_id}, {"_id": 0}).sort("created_at", -1).to_list(1)
    if not documents:
        raise HTTPException(status_code=404, detail="لا توجد مذكرات تسوية لهذا البنك")
    return BankReconciliation(**hydrate_reconciliation(documents[0]))


@api_router.get("/banks/{bank_id}/reconciliations/{reconciliation_id}", response_model=BankReconciliation)
async def get_bank_reconciliation(bank_id: str, reconciliation_id: str, _: dict = Depends(require_any_permission(["enter_deposits", "view_reports", "manage_reconciliations"]))):
    await ensure_bank_async(bank_id)
    document = await db.reconciliations.find_one({"bank_id": bank_id, "id": reconciliation_id}, {"_id": 0})
    if not document:
        raise HTTPException(status_code=404, detail="مذكرة التسوية غير موجودة")
    return BankReconciliation(**hydrate_reconciliation(document))


@api_router.put("/banks/{bank_id}/reconciliations/{reconciliation_id}", response_model=BankReconciliation)
async def update_bank_reconciliation(
    bank_id: str,
    reconciliation_id: str,
    payload: BankReconciliationCreate,
    _: dict = Depends(require_any_permission(["enter_deposits", "manage_reconciliations"])),
):
    await ensure_bank_async(bank_id)
    existing = await db.reconciliations.find_one({"bank_id": bank_id, "id": reconciliation_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="مذكرة التسوية غير موجودة")

    computed = calculate_reconciliation(payload)
    updates = payload.model_dump()
    for list_name in ["outstanding_checks", "collection_checks"]:
        for item in updates[list_name]:
            item["check_date"] = serialize_datetime(item["check_date"])
    updates.update({**computed, "updated_at": serialize_datetime(datetime.now(timezone.utc))})
    await db.reconciliations.update_one({"bank_id": bank_id, "id": reconciliation_id}, {"$set": updates})
    updated = await db.reconciliations.find_one({"bank_id": bank_id, "id": reconciliation_id}, {"_id": 0})
    return BankReconciliation(**hydrate_reconciliation(updated))


@api_router.delete("/banks/{bank_id}/reconciliations/{reconciliation_id}")
async def delete_bank_reconciliation(
    bank_id: str,
    reconciliation_id: str,
    _: dict = Depends(require_admin),
):
    await ensure_bank_async(bank_id)
    result = await db.reconciliations.delete_one({"bank_id": bank_id, "id": reconciliation_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="مذكرة التسوية غير موجودة")
    return {"message": "تم حذف مذكرة التسوية", "deleted_reconciliation_id": reconciliation_id}


@api_router.post("/revenues", response_model=Revenue)
async def create_revenue(
    payload: RevenueCreate,
    _: dict = Depends(require_any_permission(["enter_deposits", "manage_revenues"])),
):
    now = datetime.now(timezone.utc)
    document = await revenue_document_from_payload(payload)
    document.update({"id": str(uuid.uuid4()), "created_at": serialize_datetime(now), "updated_at": serialize_datetime(now)})
    await db.revenues.insert_one(document)
    return Revenue(**hydrate_revenue(document))


@api_router.get("/revenues", response_model=List[Revenue])
async def list_revenues(
    bank_id: Optional[str] = Query(default=None),
    collection_method: Optional[str] = Query(default=None),
    from_date: Optional[date] = Query(default=None),
    to_date: Optional[date] = Query(default=None),
    _: dict = Depends(require_any_permission(["enter_deposits", "view_reports", "manage_revenues"])),
):
    query = {}
    if bank_id:
        await ensure_bank_async(bank_id)
        query["bank_id"] = bank_id
    if collection_method:
        query["collection_method"] = collection_method
    if from_date or to_date:
        query["dated"] = {}
        if from_date:
            query["dated"]["$gte"] = serialize_date(from_date)
        if to_date:
            query["dated"]["$lte"] = serialize_date(to_date)
    documents = await db.revenues.find(query, {"_id": 0}).sort("dated", -1).sort("created_at", -1).to_list(1000)
    return [Revenue(**hydrate_revenue(document)) for document in documents]


@api_router.get("/revenues/search", response_model=List[Revenue])
async def search_revenues(
    query: str = Query(..., min_length=1),
    _: dict = Depends(require_any_permission(["enter_deposits", "view_reports", "manage_revenues"])),
):
    cleaned = query.strip()
    digit_query = normalize_digit_text(cleaned)
    conditions = [
        {"supplier_name": {"$regex": cleaned, "$options": "i"}},
        {"check_number": digit_query},
        {"payment_order_number": digit_query},
    ]
    documents = await db.revenues.find({"$or": conditions}, {"_id": 0}).sort("created_at", -1).to_list(50)
    return [Revenue(**hydrate_revenue(document)) for document in documents]


@api_router.get("/revenues/{revenue_id}", response_model=Revenue)
async def get_revenue(
    revenue_id: str,
    _: dict = Depends(require_any_permission(["enter_deposits", "view_reports", "manage_revenues"])),
):
    document = await db.revenues.find_one({"id": revenue_id}, {"_id": 0})
    if not document:
        raise HTTPException(status_code=404, detail="الإيراد غير موجود")
    return Revenue(**hydrate_revenue(document))


@api_router.put("/revenues/{revenue_id}", response_model=Revenue)
async def update_revenue(
    revenue_id: str,
    payload: RevenueCreate,
    _: dict = Depends(require_any_permission(["enter_deposits", "manage_revenues"])),
):
    existing = await db.revenues.find_one({"id": revenue_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="الإيراد غير موجود")
    updates = await revenue_document_from_payload(payload, revenue_id)
    updates["updated_at"] = serialize_datetime(datetime.now(timezone.utc))
    await db.revenues.update_one({"id": revenue_id}, {"$set": updates})
    updated = await db.revenues.find_one({"id": revenue_id}, {"_id": 0})
    return Revenue(**hydrate_revenue(updated))


@api_router.patch("/revenues/{revenue_id}/banking-status", response_model=Revenue)
async def update_revenue_banking_status(
    revenue_id: str,
    payload: RevenueBankingStatusUpdate,
    _: dict = Depends(require_any_permission(["enter_deposits", "manage_revenues"])),
):
    existing = await db.revenues.find_one({"id": revenue_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="الإيراد غير موجود")
    await db.revenues.update_one(
        {"id": revenue_id},
        {"$set": {"bank_collection_status": payload.bank_collection_status, "updated_at": serialize_datetime(datetime.now(timezone.utc))}},
    )
    updated = await db.revenues.find_one({"id": revenue_id}, {"_id": 0})
    return Revenue(**hydrate_revenue(updated))


@api_router.delete("/revenues/{revenue_id}")
async def delete_revenue(
    revenue_id: str,
    _: dict = Depends(require_any_permission(["enter_deposits", "manage_revenues"])),
):
    result = await db.revenues.delete_one({"id": revenue_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="الإيراد غير موجود")
    return {"message": "تم حذف الإيراد", "deleted_revenue_id": revenue_id}


@api_router.post("/expenses", response_model=Expense)
async def create_expense(
    payload: ExpenseCreate,
    _: dict = Depends(require_any_permission(["enter_deposits", "manage_expenses"])),
):
    now = datetime.now(timezone.utc)
    document = await expense_document_from_payload(payload)
    document.update({"id": str(uuid.uuid4()), "created_at": serialize_datetime(now), "updated_at": serialize_datetime(now)})
    await db.expenses.insert_one(document)
    return Expense(**hydrate_expense(document))


@api_router.get("/expenses", response_model=List[Expense])
async def list_expenses(
    bank_id: Optional[str] = Query(default=None),
    payment_method: Optional[str] = Query(default=None),
    from_date: Optional[date] = Query(default=None),
    to_date: Optional[date] = Query(default=None),
    _: dict = Depends(require_any_permission(["enter_deposits", "view_reports", "manage_expenses"])),
):
    query = {}
    if bank_id:
        await ensure_bank_async(bank_id)
        query["bank_id"] = bank_id
    if payment_method:
        query["payment_method"] = payment_method
    if from_date or to_date:
        query["issued_at"] = {}
        if from_date:
            query["issued_at"]["$gte"] = serialize_date(from_date)
        if to_date:
            query["issued_at"]["$lte"] = serialize_date(to_date)
    documents = await db.expenses.find(query, {"_id": 0}).sort("issued_at", -1).sort("created_at", -1).to_list(1000)
    return [Expense(**hydrate_expense(document)) for document in documents]


@api_router.get("/expenses/search", response_model=List[Expense])
async def search_expenses(
    query: str = Query(..., min_length=1),
    _: dict = Depends(require_any_permission(["enter_deposits", "view_reports", "manage_expenses"])),
):
    cleaned = query.strip()
    digit_query = normalize_digit_text(cleaned)
    conditions = [
        {"expense_number": digit_query},
        {"check_number": digit_query},
        {"transfer_number": digit_query},
        {"payee_name": {"$regex": cleaned, "$options": "i"}},
        {"transfer_to": {"$regex": cleaned, "$options": "i"}},
    ]
    documents = await db.expenses.find({"$or": conditions}, {"_id": 0}).sort("created_at", -1).to_list(50)
    return [Expense(**hydrate_expense(document)) for document in documents]


@api_router.get("/expenses/{expense_id}", response_model=Expense)
async def get_expense(
    expense_id: str,
    _: dict = Depends(require_any_permission(["enter_deposits", "view_reports", "manage_expenses"])),
):
    document = await db.expenses.find_one({"id": expense_id}, {"_id": 0})
    if not document:
        raise HTTPException(status_code=404, detail="المصروف غير موجود")
    return Expense(**hydrate_expense(document))


@api_router.put("/expenses/{expense_id}", response_model=Expense)
async def update_expense(
    expense_id: str,
    payload: ExpenseCreate,
    _: dict = Depends(require_any_permission(["enter_deposits", "manage_expenses"])),
):
    existing = await db.expenses.find_one({"id": expense_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="المصروف غير موجود")
    updates = await expense_document_from_payload(payload, expense_id)
    updates["updated_at"] = serialize_datetime(datetime.now(timezone.utc))
    await db.expenses.update_one({"id": expense_id}, {"$set": updates})
    updated = await db.expenses.find_one({"id": expense_id}, {"_id": 0})
    return Expense(**hydrate_expense(updated))


@api_router.patch("/expenses/{expense_id}/banking-status", response_model=Expense)
async def update_expense_banking_status(
    expense_id: str,
    payload: ExpenseBankingStatusUpdate,
    _: dict = Depends(require_any_permission(["enter_deposits", "manage_expenses"])),
):
    existing = await db.expenses.find_one({"id": expense_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="المصروف غير موجود")
    await db.expenses.update_one(
        {"id": expense_id},
        {"$set": {"bank_payment_status": payload.bank_payment_status, "updated_at": serialize_datetime(datetime.now(timezone.utc))}},
    )
    updated = await db.expenses.find_one({"id": expense_id}, {"_id": 0})
    return Expense(**hydrate_expense(updated))


@api_router.delete("/expenses/{expense_id}")
async def delete_expense(
    expense_id: str,
    _: dict = Depends(require_any_permission(["enter_deposits", "manage_expenses"])),
):
    result = await db.expenses.delete_one({"id": expense_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="المصروف غير موجود")
    return {"message": "تم حذف المصروف", "deleted_expense_id": expense_id}


@api_router.get("/banking-expenses/manual", response_model=BankingManualChargesResponse)
async def get_banking_manual_charges(
    bank_id: str = Query(...),
    year: int = Query(..., ge=1900, le=2200),
    month: int = Query(..., ge=1, le=12),
    _: dict = Depends(require_any_permission(["enter_deposits", "view_reports", "manage_expenses", "manage_revenues"])),
):
    bank = await ensure_bank_async(bank_id)
    document = await db.banking_manual_charges.find_one({"bank_id": bank_id, "year": year, "month": month}, {"_id": 0})
    if not document:
        document = {
            "id": f"{bank_id}-{year}-{month}",
            "bank_id": bank_id,
            "bank_name": bank["name"],
            "year": year,
            "month": month,
            "stamp": 0,
            "bank_correspondence": 0,
            "correspondence_safekeeping": 0,
            "internal_transfer_fee": 0,
            "external_transfer_fee": 0,
            "updated_at": serialize_datetime(datetime.now(timezone.utc)),
        }
    return BankingManualChargesResponse(**hydrate_banking_manual_charges(document))


@api_router.put("/banking-expenses/manual", response_model=BankingManualChargesResponse)
async def save_banking_manual_charges(
    payload: BankingManualCharges,
    _: dict = Depends(require_any_permission(["enter_deposits", "manage_expenses", "manage_revenues"])),
):
    bank = await ensure_bank_async(payload.bank_id)
    now = datetime.now(timezone.utc)
    document = {
        "id": f"{payload.bank_id}-{payload.year}-{payload.month}",
        "bank_id": payload.bank_id,
        "bank_name": bank["name"],
        "year": payload.year,
        "month": payload.month,
        "stamp": round(float(payload.stamp or 0), 2),
        "bank_correspondence": round(float(payload.bank_correspondence or 0), 2),
        "correspondence_safekeeping": round(float(payload.correspondence_safekeeping or 0), 2),
        "internal_transfer_fee": round(float(payload.internal_transfer_fee or 0), 2),
        "external_transfer_fee": round(float(payload.external_transfer_fee or 0), 2),
        "updated_at": serialize_datetime(now),
    }
    await db.banking_manual_charges.update_one(
        {"bank_id": payload.bank_id, "year": payload.year, "month": payload.month},
        {"$set": document},
        upsert=True,
    )
    return BankingManualChargesResponse(**hydrate_banking_manual_charges(document))

# Include the router in the main app
app.include_router(api_router)


FRONTEND_BUILD_DIR = ROOT_DIR.parent / "frontend" / "build"
if FRONTEND_BUILD_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_BUILD_DIR / "static"), name="static")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_react_app(full_path: str):
        requested_file = FRONTEND_BUILD_DIR / full_path
        if full_path and requested_file.exists() and requested_file.is_file():
            return FileResponse(requested_file)
        return FileResponse(FRONTEND_BUILD_DIR / "index.html")

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()