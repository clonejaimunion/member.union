from fastapi import FastAPI, APIRouter, Depends, File, Form, Header, HTTPException, Query, Request, Response, UploadFile
from dotenv import load_dotenv
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ReturnDocument
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, List, Literal, Optional
import uuid
from datetime import date, datetime, timedelta, timezone
import calendar
import math
import time
import base64
from io import BytesIO
import re
import html
import urllib.request
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table as PdfTable, TableStyle
import json
import hashlib
import secrets
import subprocess
import tempfile
import shlex
import shutil
import urllib.parse
from contextvars import ContextVar
import zipfile
import textwrap
import xml.etree.ElementTree as ET

import bcrypt
import jwt
import pyotp
import qrcode
import arabic_reshaper
from bidi.algorithm import get_display
from PIL import Image, ImageDraw, ImageFont, JpegImagePlugin
from pypdf import PdfReader
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=3000)
db = client[os.environ['DB_NAME']]
JWT_SECRET = os.environ['JWT_SECRET']
JWT_ALGORITHM = "HS256"
LOGIN_LOCKOUT_FAILED_ATTEMPTS = 3
LOGIN_LOCKOUT_MINUTES = 3
ADMIN_USERNAME = os.environ['ADMIN_USERNAME']
ADMIN_INITIAL_PASSWORD = os.environ['ADMIN_INITIAL_PASSWORD']
CORS_ORIGINS = [origin.strip() for origin in os.environ['CORS_ORIGINS'].split(',') if origin.strip()]
APP_ASSETS_DIR = ROOT_DIR.parent / "app_assets"
APP_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
GENERATED_REPORTS_DIR = ROOT_DIR.parent / "generated_reports"
GENERATED_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
APP_ICON_PATH = APP_ASSETS_DIR / "accounting_app_custom.ico"
DEFAULT_SYSTEM_NAME = "نظام محاسبي متكامل"
DEFAULT_ORGANIZATION_ID = "social-solidarity"
CURRENT_ORGANIZATION_ID: ContextVar[Optional[str]] = ContextVar("current_organization_id", default=None)

ORGANIZATIONS = {
    "social-solidarity": {
        "id": "social-solidarity",
        "name": "مشروع التكافل الاجتماعي",
        "login_label": "مشروع التكافل الاجتماعي",
    },
    "general-union": {
        "id": "general-union",
        "name": "النقابة العامة للعاملين بالزراعة والري والصيد واستصلاح الاراضي",
        "login_label": "النقابة العامة",
    },
}

MODULE_DEFINITIONS = {
    "membership": "العضوية",
    "fixed_assets": "الأصول الثابتة",
    "custody_advances": "العهد والسلف",
    "financial_statements": "القوائم المالية",
    "chart_accounts": "شجرة الحسابات",
    "trial_balance": "ميزان المراجعة",
    "deposits": "فوائد الودائع",
    "journal_entries": "القيود اليومية",
    "reconciliations": "التسويات البنكية",
    "revenues": "الإيرادات",
    "expenses": "المصروفات",
    "expenses_analysis": "تحليل المصروفات",
    "banking_expenses": "المصروفات البنكية",
    "ledger": "دفتر الأستاذ",
    "treasury_banks": "الخزينة والبنوك",
    "erp_health_report": "تقرير تقييم النظام",
    "electronic_invoice": "الفاتورة الإلكترونية",
}

FIXED_ASSET_CATEGORIES = [
    {"code": "5", "name": "الأثاث", "annual_depreciation_rate": 10.0, "items": ["موكيت ارضية", "ستائر", "مكتب خشب ووحدة ادارج", "ترابيزة كمبيوتر عدد 2", "ترابيزة زجاج 2 دوور", "ارفف معدنية - 7 وحدات"]},
    {"code": "101", "name": "آلات مكتبية", "annual_depreciation_rate": 20.0, "items": ["عدد 4 جهاز حاسب الي", "عدد 2 ماكينة تصوير مستندات", "طابعة كمبيوتر"]},
    {"code": "151", "name": "الخزائن", "annual_depreciation_rate": 5.0, "items": ["خزينة حديد اوجيدا 44سم"]},
    {"code": "155", "name": "الأجهزة الكهربائية", "annual_depreciation_rate": 20.0, "items": ["مروحة فريش حلزوني", "جهاز تكييف توشيبا 4حصان"]},
]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Background scheduler for deposit maturity notifications (informational only —
# never touches accounting state). Optional: if APScheduler is unavailable the
# notifications still work via manual /scan endpoint and the in-app bell.
try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore  # noqa: E402
    _APSCHEDULER_AVAILABLE = True
except Exception:
    AsyncIOScheduler = None  # type: ignore
    _APSCHEDULER_AVAILABLE = False

from deposit_notifications import attach_router as attach_notifications_router, ensure_indexes as ensure_notification_indexes, schedule_daily_scan  # noqa: E402

deposit_notification_scheduler = AsyncIOScheduler() if _APSCHEDULER_AVAILABLE else None


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
    opening_balance: float = 0
    opening_balance_date: Optional[date] = None


class BankCreate(BaseModel):
    name: str = Field(..., min_length=2)
    code: Optional[str] = None
    swift_code: Optional[str] = None
    logo_url: Optional[str] = None
    color: Optional[str] = "#0f172a"
    opening_balance: float = 0
    opening_balance_date: date


class BankOpeningBalanceUpdate(BaseModel):
    opening_balance: float = 0
    opening_balance_date: date


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
    is_opening_balance_deposit: bool = False
    accounting_start_datetime: Optional[datetime] = None
    renewed_from_deposit_id: Optional[str] = None
    renewal_notes: Optional[str] = None
    use_daily_rounding: bool = True


class DepositCreate(DepositBase):
    pass


class Deposit(DepositBase):
    model_config = ConfigDict(extra="ignore")

    id: str
    bank_id: str
    status: Literal["active", "matured", "renewed", "closed"] = "active"
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
    full_name: str
    role: str
    organization_id: str
    organization_name: str
    organization_modules: Dict[str, bool] = Field(default_factory=dict)
    permissions: UserPermissions
    is_active: bool
    totp_enabled: bool = False
    must_change_password: bool = False
    created_at: datetime
    updated_at: datetime


class LoginRequest(BaseModel):
    username: str
    password: str
    organization_id: str
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
    full_name: str = Field(..., min_length=3, max_length=120)
    password: str = Field(..., min_length=8)
    role: Literal["user", "admin"] = "user"
    organization_id: Optional[str] = None
    permissions: UserPermissions = Field(default_factory=UserPermissions)
    is_active: bool = True


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=3, max_length=120)
    password: Optional[str] = Field(default=None, min_length=8)
    role: Optional[Literal["user", "admin"]] = None
    permissions: Optional[UserPermissions] = None
    is_active: Optional[bool] = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)


class AdminProfileUpdate(BaseModel):
    full_name: str = Field(..., min_length=3, max_length=120)


class AppSettingsResponse(BaseModel):
    system_name: str
    organization_id: Optional[str] = None
    organization_name: Optional[str] = None
    organization_login_label: Optional[str] = None
    organizations: Dict[str, dict] = Field(default_factory=dict)
    login_union_logo_visible: bool = True
    login_union_logo_data_url: Optional[str] = None
    login_authority_logos: List[dict] = Field(default_factory=list)
    backup_enabled: bool = True
    backup_allowed_roles: Dict[str, bool] = Field(default_factory=lambda: {"super_admin": True, "admin": True, "user": False})
    two_factor_role_policy: Dict[str, bool] = Field(default_factory=lambda: {"super_admin": False, "admin": False, "user": False})
    include_tech_stack_in_manual: bool = False
    hide_ai_attribution: bool = True
    intellectual_property_owner: Optional[str] = None
    intellectual_property_national_id: Optional[str] = None
    intellectual_property_fingerprint: Optional[str] = None
    source_lock_password_set: bool = False
    installed_files_lock_enabled: bool = False
    installed_files_password_set: bool = False
    session_timeout_minutes: int = 1
    source_integrity_digest: Optional[str] = None
    shortcut_icon_url: Optional[str] = None
    shortcut_icon_updated_at: Optional[str] = None
    shortcut_update_status: Optional[str] = None
    updated_at: str


class AppSettingsUpdate(BaseModel):
    system_name: str = Field(..., min_length=2, max_length=120)
    organization_name: Optional[str] = Field(default=None, min_length=2, max_length=160)
    organization_login_label: Optional[str] = Field(default=None, min_length=2, max_length=120)
    organization_names: Optional[Dict[str, str]] = None
    organization_login_labels: Optional[Dict[str, str]] = None
    organization_emails: Optional[Dict[str, Optional[str]]] = None
    login_union_logo_visible: Optional[bool] = None
    login_union_logo_data_url: Optional[str] = None
    login_authority_logos: Optional[List[dict]] = None
    backup_enabled: Optional[bool] = None
    backup_allowed_roles: Optional[Dict[str, bool]] = None
    two_factor_role_policy: Optional[Dict[str, bool]] = None
    include_tech_stack_in_manual: Optional[bool] = None
    hide_ai_attribution: Optional[bool] = None
    intellectual_property_owner: Optional[str] = None
    intellectual_property_national_id: Optional[str] = None
    intellectual_property_fingerprint: Optional[str] = None
    installed_files_lock_enabled: Optional[bool] = None
    session_timeout_minutes: Optional[int] = Field(default=None, ge=1, le=240)


class SourceLockPasswordUpdate(BaseModel):
    new_password: str = Field(..., min_length=8, max_length=128)


class InstalledFilesPasswordUpdate(BaseModel):
    new_password: str = Field(..., min_length=8, max_length=128)


class ProgramSecurityResponse(BaseModel):
    intellectual_property_owner: str
    intellectual_property_national_id: Optional[str] = None
    intellectual_property_fingerprint: str
    source_lock_password_set: bool
    installed_files_lock_enabled: bool
    installed_files_password_set: bool
    session_timeout_minutes: int
    source_integrity_digest: str
    encrypted_passwords_summary: Dict[str, str]


class OrganizationResponse(BaseModel):
    id: str
    name: str
    login_label: str
    email: Optional[str] = None
    is_active: bool = True
    modules: Dict[str, bool] = Field(default_factory=dict)


class OrganizationModulesResponse(BaseModel):
    organization_id: str
    organization_name: str
    modules: Dict[str, bool]
    module_labels: Dict[str, str]
    updated_at: str


class OrganizationModulesUpdate(BaseModel):
    modules: Dict[str, bool]


class OrganizationCreate(BaseModel):
    id: Optional[str] = None
    name: str = Field(..., min_length=2, max_length=180)
    login_label: Optional[str] = Field(default=None, min_length=2, max_length=120)
    email: Optional[str] = None
    clone_from: Optional[str] = DEFAULT_ORGANIZATION_ID


class OrganizationUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=180)
    login_label: Optional[str] = Field(default=None, min_length=2, max_length=120)
    email: Optional[str] = None
    is_active: Optional[bool] = None
    modules: Optional[Dict[str, bool]] = None


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
    status: Literal["active", "matured", "renewed", "closed"] = "active"
    renewal_notes: Optional[str] = None
    maturity_date: Optional[str] = None


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
    status: Literal["active", "matured", "renewed", "closed"] = "active"
    renewal_notes: Optional[str] = None
    maturity_date: Optional[str] = None


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


class JournalLine(BaseModel):
    account_id: Optional[str] = None
    account_code: Optional[str] = None
    account_name: str = Field(..., min_length=2)
    account_type: Optional[str] = None
    debit: float = Field(default=0, ge=0)
    credit: float = Field(default=0, ge=0)
    notes: Optional[str] = None


class ChartAccountBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=30)
    name: str = Field(..., min_length=2, max_length=160)
    account_type: Literal["asset", "liability", "equity", "revenue", "expense"]
    nature: Literal["debit", "credit"]
    parent_id: Optional[str] = None
    is_postable: bool = True
    is_active: bool = True
    opening_balance: float = 0


class ChartAccountCreate(ChartAccountBase):
    pass


class ChartAccountUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=160)
    nature: Optional[Literal["debit", "credit"]] = None
    parent_id: Optional[str] = None
    is_postable: Optional[bool] = None
    is_active: Optional[bool] = None
    opening_balance: Optional[float] = None


class ChartAccountResponse(ChartAccountBase):
    id: str
    organization_id: str
    parent_code: Optional[str] = None
    parent_name: Optional[str] = None
    level: int = 1
    system_key: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class GeneralLedgerLine(BaseModel):
    serial: int
    entry_id: str
    entry_number: int
    entry_date: date
    source_type: str
    reference: Optional[str] = None
    account_id: Optional[str] = None
    account_code: Optional[str] = None
    account_name: Optional[str] = None
    description: str
    debit: float
    credit: float
    balance: float


class GeneralLedgerReport(BaseModel):
    account: Optional[ChartAccountResponse] = None
    account_scope: Literal["single", "all"] = "single"
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    opening_balance: float
    total_debit: float
    total_credit: float
    closing_balance: float
    rows: List[GeneralLedgerLine]


class BankBookBalanceResponse(BaseModel):
    bank_id: str
    as_of_date: date
    book_balance: float
    source: str = "journal_entries"


class BankReconciliationBalanceBreakdown(BaseModel):
    bank_id: str
    period_from: date
    period_to: date
    opening_balance: float = 0
    monthly_revenues: float = 0
    monthly_deposit_interest: float = 0
    total_receipts: float = 0
    deposit_settlements: float = 0
    checks_under_collection: float = 0
    gross_total: float = 0
    book_balance: float = 0
    monthly_expenses: float = 0
    checks_not_presented: float = 0
    bank_expenses: float = 0
    total_payments: float = 0
    reconciliation_balance: float = 0
    source: str = "opening_balance_plus_monthly_components"


class TreasuryBanksAccount(BaseModel):
    id: str
    code: Optional[str] = None
    name: str
    account_kind: Literal["bank", "cash"]
    bank_id: Optional[str] = None
    bank_name: Optional[str] = None


class TreasuryBanksTransaction(BaseModel):
    serial: int
    entry_id: Optional[str] = None
    entry_number: int
    entry_date: date
    description: str
    reference: Optional[str] = None
    source_type: str
    movement_type: str
    account_id: str
    account_code: Optional[str] = None
    account_name: str
    account_kind: Literal["bank", "cash"]
    bank_id: Optional[str] = None
    bank_name: Optional[str] = None
    debit: float = 0
    credit: float = 0
    amount: float = 0
    running_balance: float = 0


class TreasuryBanksSummary(BaseModel):
    organization_id: str
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    opening_balance: float = 0
    total_balance: float = 0
    total_revenues: float = 0
    total_expenses: float = 0
    net_movement: float = 0
    transactions_count: int = 0
    source: str = "journal_entries_approved_read_only"


class TreasuryBanksReport(BaseModel):
    summary: TreasuryBanksSummary
    accounts: List[TreasuryBanksAccount]
    transactions: List[TreasuryBanksTransaction]


class BankPrintExternalRow(BaseModel):
    id: str
    section: str
    title: str
    description: Optional[str] = None
    currency: Optional[str] = None
    buy: Optional[str] = None
    sell: Optional[str] = None
    url: Optional[str] = None


class BankPrintExternalData(BaseModel):
    bank_id: str
    bank_name: str
    source_url: str
    fetched_at: datetime
    status: Literal["OK", "NO_DATA"] = "OK"
    checksum: str
    rows: List[BankPrintExternalRow]


class BankPrintManualInput(BaseModel):
    bank_notes: Optional[str] = Field(default=None, max_length=500)
    checks_or_settlements_numbers: Optional[str] = Field(default=None, max_length=220)
    descriptive_adjustments: Optional[str] = Field(default=None, max_length=500)
    period_from: Optional[date] = None
    period_to: Optional[date] = None
    internal_approver_name: Optional[str] = Field(default=None, max_length=120)
    internal_signature: Optional[str] = Field(default=None, max_length=160)
    approval_code: Optional[str] = Field(default=None, max_length=80)


class BankPrintRequestCreate(BaseModel):
    manual_inputs: BankPrintManualInput


class BankPrintRequestStatusUpdate(BaseModel):
    status: Literal["saved_before_print", "printed", "cancelled"]


class BankPrintRequestResponse(BaseModel):
    id: str
    organization_id: str
    bank_id: str
    bank_name: str
    source_url: str
    external_data: BankPrintExternalData
    manual_inputs: BankPrintManualInput
    status: Literal["saved_before_print", "printed", "cancelled"]
    created_by: Optional[str] = None
    created_by_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    printed_at: Optional[datetime] = None


class ErpHealthMetric(BaseModel):
    key: str
    title: str
    score: int
    status: str
    details: str


class ErpHealthReportResponse(BaseModel):
    id: str
    organization_id: str
    generated_at: datetime
    period_from: date
    period_to: date
    overall_score: int
    metrics: List[ErpHealthMetric]
    recommendations: List[str]
    direct_download_url: str
    source: str = "read_only_ledger_trial_reconciliations_audit"


class TrialBalanceRow(BaseModel):
    account_id: Optional[str] = None
    account_code: Optional[str] = None
    account_name: str
    account_type: Optional[str] = None
    nature: Optional[str] = None
    opening_balance: float = 0
    total_debit: float = 0
    total_credit: float = 0
    balance_debit: float = 0
    balance_credit: float = 0


class TrialBalanceReport(BaseModel):
    organization_id: str
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    account_type: Optional[str] = None
    rows: List[TrialBalanceRow]
    total_debit: float
    total_credit: float
    total_balance_debit: float
    total_balance_credit: float
    is_balanced: bool


class FinancialStatementLine(BaseModel):
    code: Optional[str] = None
    name: str
    amount: float = 0
    debit: float = 0
    credit: float = 0
    reference: Optional[str] = None
    entry_number: Optional[int] = None
    entry_date: Optional[date] = None
    details: Optional[str] = None


class FinancialStatementSection(BaseModel):
    title: str
    lines: List[FinancialStatementLine]
    total: float = 0


class AccountingErrorItem(BaseModel):
    severity: Literal["critical", "warning", "info"]
    error_type: str
    location: str
    details: str
    suggested_fix: Optional[str] = None


class JournalRepairItem(BaseModel):
    entry_id: str
    entry_number: Optional[int] = None
    entry_date: Optional[date] = None
    description: Optional[str] = None
    line_index: int
    before_account_name: Optional[str] = None
    before_account_code: Optional[str] = None
    after_account_name: Optional[str] = None
    after_account_code: Optional[str] = None
    after_account_type: Optional[str] = None


class FinancialStatementsReport(BaseModel):
    organization_id: str
    from_date: date
    to_date: date
    balance_sheet: Dict[str, FinancialStatementSection]
    receipts_payments: Dict[str, FinancialStatementSection]
    revenues_expenses: Dict[str, FinancialStatementSection]
    accounting_errors: List[AccountingErrorItem]
    accounting_corrections: List[JournalRepairItem] = Field(default_factory=list)
    is_accounting_valid: bool
    generated_at: datetime


class FixedAssetCategory(BaseModel):
    code: str
    name: str
    annual_depreciation_rate: float
    items: List[str]


class FixedAssetCategoryRateUpdate(BaseModel):
    annual_depreciation_rate: float = Field(..., ge=0, le=100)


class FixedAssetCatalogItem(BaseModel):
    id: str
    category_code: str
    name: str
    is_default: bool = False
    is_custom: bool = False


class FixedAssetCatalogItemCreate(BaseModel):
    category_code: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1, max_length=160)


class FixedAssetBase(BaseModel):
    category_code: str = Field(..., min_length=1)
    asset_name: str = Field(..., min_length=1, max_length=160)
    purchase_date: date
    purchase_cost: float = Field(..., gt=0)
    bank_id: str
    invoice_number: Optional[str] = None
    notes: Optional[str] = None
    is_active: bool = True


class FixedAssetCreate(FixedAssetBase):
    pass


class FixedAssetResponse(FixedAssetBase):
    model_config = ConfigDict(extra="ignore")

    id: str
    organization_id: str
    asset_code: str
    category_name: str
    annual_depreciation_rate: float
    bank_name: str
    monthly_depreciation: float
    accumulated_depreciation: float
    net_book_value: float
    disposal_date: Optional[date] = None
    last_depreciation_period: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class FixedAssetDepreciationRun(BaseModel):
    year: int = Field(..., ge=1900, le=2200)
    month: int = Field(default=12, ge=1, le=12)


class FixedAssetDepreciationResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    organization_id: str
    asset_id: str
    asset_code: str
    asset_name: str
    category_code: str
    category_name: str
    year: int
    month: int
    depreciation_date: date
    amount: float
    accumulated_after: float
    net_book_value_after: float
    created_at: datetime
    updated_at: datetime


class CustodyAdvanceBase(BaseModel):
    transaction_type: Literal["custody", "advance"]
    recipient_name: str = Field(..., min_length=2, max_length=160)
    issue_date: date
    amount: float = Field(..., gt=0)
    bank_id: str
    purpose: str = Field(..., min_length=2, max_length=240)
    due_date: Optional[date] = None
    notes: Optional[str] = None


class CustodyAdvanceCreate(CustodyAdvanceBase):
    pass


class CustodyAdvanceSettle(BaseModel):
    settlement_date: date
    settlement_amount: float = Field(..., gt=0)
    settlement_type: Literal["expense", "bank_return"] = "expense"
    notes: Optional[str] = None


class CustodyAdvanceResponse(CustodyAdvanceBase):
    model_config = ConfigDict(extra="ignore")

    id: str
    organization_id: str
    reference_number: str
    bank_name: str
    settled_amount: float = 0
    remaining_amount: float
    status: Literal["open", "partial", "settled"]
    settlement_date: Optional[date] = None
    settlement_type: Optional[str] = None
    settlement_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


MembershipStatus = Literal["active", "retired", "deceased", "resigned"]


class MembershipBase(BaseModel):
    governorate: str = Field(..., min_length=2, max_length=80)
    union_committee: str = Field(..., min_length=2, max_length=120)
    membership_number: str = Field(..., min_length=1, max_length=40)
    name: str = Field(..., min_length=2, max_length=160)
    national_id: str = Field(..., min_length=14, max_length=14)
    birth_date: date
    address: str = Field(..., min_length=2, max_length=240)
    death_beneficiary: str = Field(..., min_length=2, max_length=160)
    status: MembershipStatus = "active"
    status_effective_date: Optional[date] = None


class MembershipCreate(MembershipBase):
    pass


class MembershipScanAttachment(BaseModel):
    id: str
    file_name: str
    pdf_url: str
    source_type: Literal["scanner", "upload"] = "scanner"
    page_count: int = 1
    ocr_engine: str = "local"
    scanned_at: datetime


class MembershipResponse(MembershipBase):
    model_config = ConfigDict(extra="ignore")

    id: str
    organization_id: str
    retirement_age: int
    retirement_date: date
    retirement_year: int
    retirement_month: int
    status_label: str = "فعال"
    subscription_start_date: date
    subscription_stop_date: Optional[date] = None
    monthly_subscription_amount: float = 3
    current_due: float = 0
    total_collected: float = 0
    remaining_balance: float = 0
    scan_attachment: Optional[MembershipScanAttachment] = None
    created_at: datetime
    updated_at: datetime


class MembershipScannerStatusResponse(BaseModel):
    is_windows: bool
    scanner_available: bool
    tesseract_available: bool
    windows_ocr_available: bool
    message: str


class MembershipScanImportResponse(BaseModel):
    member: MembershipResponse
    extracted_fields: Dict[str, str]
    pdf_url: str
    page_count: int
    ocr_engine: str
    source_type: Literal["scanner", "upload"]


class MembershipCurrentSizeResponse(BaseModel):
    organization_id: str
    as_of_year: int
    as_of_month: int
    total_members: int
    retired_members: int
    current_membership_size: int


class MembershipImportSkippedRow(BaseModel):
    row_number: int
    reason: str


class MembershipImportAcceptedRow(BaseModel):
    row_number: int
    governorate: str
    union_committee: str
    membership_number: str
    name: str
    national_id: str
    birth_date: date
    address: str
    death_beneficiary: str
    status: MembershipStatus = "active"
    status_label: str = "فعال"
    status_effective_date: Optional[date] = None
    retirement_age: int
    retirement_date: date


class MembershipImportPreviewResponse(BaseModel):
    preview_id: str
    accepted_count: int
    skipped_count: int
    total_rows_detected: int
    accepted_rows: List[MembershipImportAcceptedRow]
    skipped_rows: List[MembershipImportSkippedRow]


class MembershipImportCommitRequest(BaseModel):
    preview_id: str


class MembershipImportResponse(BaseModel):
    imported_count: int
    skipped_count: int
    total_rows_detected: int
    imported_members: List[MembershipResponse]
    skipped_rows: List[MembershipImportSkippedRow]


class MembershipAnnualReportRow(BaseModel):
    governorate: str
    union_committee: str
    total_registered: int
    new_members: int
    retired_members: int
    current_membership_size: int
    total_due: float = 0
    total_collected: float = 0
    remaining_balance: float = 0


class MembershipAnnualReportResponse(BaseModel):
    year: int
    rows: List[MembershipAnnualReportRow]
    totals: MembershipAnnualReportRow


class MembershipBatchPaymentCreate(BaseModel):
    governorate: str = Field(..., min_length=2, max_length=80)
    union_committee: str = Field(..., min_length=2, max_length=120)
    bank_id: str
    payment_date: date
    amount: float = Field(..., gt=0)
    receipt_number: Optional[str] = Field(default=None, max_length=80)
    notes: Optional[str] = Field(default=None, max_length=240)


class MembershipPaymentAllocation(BaseModel):
    member_id: str
    membership_number: str
    member_name: str
    period: str
    amount: float


class MembershipBatchPaymentResponse(BaseModel):
    id: str
    organization_id: str
    governorate: str
    union_committee: str
    bank_id: str
    bank_name: str
    payment_date: date
    amount: float
    allocated_amount: float
    unapplied_amount: float
    receipt_number: Optional[str] = None
    notes: Optional[str] = None
    allocations: List[MembershipPaymentAllocation]
    created_at: datetime
    updated_at: datetime


class MembershipCollectionReportRow(BaseModel):
    group_type: Literal["committee", "governorate"]
    group_name: str
    governorate: Optional[str] = None
    union_committee: Optional[str] = None
    members_count: int
    active_members: int
    total_due: float
    total_collected: float
    remaining_balance: float


class MembershipCollectionReportResponse(BaseModel):
    as_of_date: date
    group_by: Literal["committee", "governorate"]
    rows: List[MembershipCollectionReportRow]
    totals: MembershipCollectionReportRow


class JournalEntryCreate(BaseModel):
    entry_date: date
    description: str = Field(..., min_length=2)
    reference: Optional[str] = None
    lines: List[JournalLine] = Field(..., min_length=2)


class InventoryItemCreate(BaseModel):
    item_code: str = Field(..., min_length=1, max_length=60)
    item_name: str = Field(..., min_length=2, max_length=160)
    unit: str = Field(default="وحدة", min_length=1, max_length=40)


class InventoryItemResponse(InventoryItemCreate):
    id: str
    organization_id: str
    quantity_balance: float = 0
    value_balance: float = 0
    average_cost: float = 0
    created_at: datetime
    updated_at: datetime


class InventoryMovementCreate(BaseModel):
    movement_date: date
    item_id: Optional[str] = None
    item_code: Optional[str] = None
    item_name: Optional[str] = None
    unit: str = "وحدة"
    movement_type: Literal["in", "out"]
    quantity: float = Field(..., gt=0)
    unit_cost: Optional[float] = Field(default=None, ge=0)
    description: str = Field(..., min_length=2, max_length=300)
    reference: Optional[str] = Field(default=None, max_length=80)


class InventoryMovementResponse(BaseModel):
    id: str
    organization_id: str
    movement_date: date
    item_id: str
    item_code: str
    item_name: str
    unit: str
    movement_type: Literal["in", "out"]
    quantity: float
    unit_cost: float
    total_value: float
    quantity_balance_after: float
    value_balance_after: float
    journal_entry_id: Optional[str] = None
    description: str
    reference: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class MiscCreditorCreate(BaseModel):
    creditor_code: Optional[str] = Field(default=None, max_length=60)
    creditor_name: str = Field(..., min_length=2, max_length=160)
    notes: Optional[str] = Field(default=None, max_length=300)


class MiscCreditorResponse(MiscCreditorCreate):
    id: str
    organization_id: str
    balance: float = 0
    created_at: datetime
    updated_at: datetime


class MiscCreditorMovementCreate(BaseModel):
    movement_date: date
    creditor_id: Optional[str] = None
    creditor_name: Optional[str] = None
    movement_type: Literal["obligation", "payment"]
    amount: float = Field(..., gt=0)
    bank_id: Optional[str] = None
    description: str = Field(..., min_length=2, max_length=300)
    reference: Optional[str] = Field(default=None, max_length=80)


class MiscCreditorMovementResponse(BaseModel):
    id: str
    organization_id: str
    movement_date: date
    creditor_id: str
    creditor_name: str
    movement_type: Literal["obligation", "payment"]
    amount: float
    balance_after: float
    bank_id: Optional[str] = None
    bank_name: Optional[str] = None
    journal_entry_id: Optional[str] = None
    description: str
    reference: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class JournalEntryResponse(BaseModel):
    id: str
    organization_id: str
    entry_number: int
    entry_date: date
    description: str
    reference: Optional[str] = None
    source_type: Literal["manual", "revenue", "expense", "banking_expense", "deposit", "deposit_interest", "reconciliation", "fixed_asset", "asset_depreciation", "custody_advance", "custody_advance_settlement", "opening_balance", "membership_batch_payment", "inventory", "misc_creditor", "tax_invoice"] = "manual"
    source_id: Optional[str] = None
    status: Literal["approved"] = "approved"
    is_auto: bool = False
    is_reversal: bool = False
    reversal_of_entry_id: Optional[str] = None
    reversal_entry_id: Optional[str] = None
    reversal_reason: Optional[str] = None
    lines: List[JournalLine]
    total_debit: float
    total_credit: float
    created_by: Optional[str] = None
    created_by_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ReconciliationCheck(BaseModel):
    check_number: str = Field(..., min_length=1)
    amount: float = Field(..., ge=0)
    check_date: datetime
    year: Optional[int] = None


class BankReconciliationCreate(BaseModel):
    period_label: Optional[str] = None
    administration: Optional[str] = "النقابة العامة للعاملين بالزراعة والري"
    book_balance: float
    bank_statement_balance: float
    outstanding_checks: List[ReconciliationCheck] = Field(default_factory=list)
    collection_checks: List[ReconciliationCheck] = Field(default_factory=list)
    prior_year_outstanding_checks: List[ReconciliationCheck] = Field(default_factory=list)


class BankReconciliation(BankReconciliationCreate):
    model_config = ConfigDict(extra="ignore")

    id: str
    bank_id: str
    total_outstanding_checks: float
    total_collection_checks: float
    total_prior_year_outstanding_checks: float = 0.0
    calculated_balance: float
    difference: float
    is_matched: bool
    status_text: str
    balance_breakdown: Optional[BankReconciliationBalanceBreakdown] = None
    created_at: datetime
    updated_at: datetime


class RevenueBase(BaseModel):
    receipt_number: str = Field(..., min_length=1)
    amount: float = Field(..., gt=0)
    collection_method: Literal["cash", "check", "payment_order", "current_account_interest", "deposit_maturity"]
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
    expense_category: Literal["general_expenses", "death_benefits", "deposit_link"] = "general_expenses"
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
    items: List[Dict[str, object]] = Field(default_factory=list)


class BankingManualChargesResponse(BankingManualCharges):
    model_config = ConfigDict(extra="ignore")

    id: str
    bank_name: str
    updated_at: datetime


class ElectronicInvoiceSettings(BaseModel):
    organization_name: str = "النقابة العامة للعاملين بالزراعة والري"
    tax_registration_number: Optional[str] = None
    address: Optional[str] = None
    governorate: Optional[str] = None
    activity_code: Optional[str] = None
    default_tax_rate: float = Field(default=0, ge=0, le=100)
    auto_generate_from_collected_revenues: bool = True


class ElectronicInvoiceSettingsResponse(ElectronicInvoiceSettings):
    model_config = ConfigDict(extra="ignore")

    id: str
    updated_at: datetime


class TenantTaxRule(BaseModel):
    id: str = Field(..., min_length=1)
    tax_type: str = Field(..., min_length=1)
    tax_status: Literal["standard", "exempt", "zero", "schedule"] = "standard"
    rate: float = Field(..., ge=0, le=100)
    item_code: str = Field(..., min_length=1)
    activity_code: Optional[str] = None
    effective_from: date
    effective_to: Optional[date] = None
    is_default: bool = False
    description: Optional[str] = None


class TenantTaxProfile(BaseModel):
    tax_registration_id: Optional[str] = None
    taxpayer_name: Optional[str] = None
    country_code: str = "EG"
    currency: str = "EGP"
    eta_environment: Literal["offline_ready", "preprod", "production"] = "offline_ready"
    tax_rules: List[TenantTaxRule] = Field(default_factory=list)
    document_type_codes: Dict[str, str] = Field(default_factory=dict)
    journal_accounts: Dict[str, str] = Field(default_factory=dict)
    eta_payload_schema: Dict[str, object] = Field(default_factory=dict)
    auto_create_journal_on_approval: bool = True
    updated_at: Optional[datetime] = None


class TenantTaxProfileResponse(TenantTaxProfile):
    model_config = ConfigDict(extra="ignore")

    id: str
    organization_id: str
    is_configured: bool = False
    configuration_errors: List[str] = Field(default_factory=list)


class EtaIntegrationSettings(BaseModel):
    environment: Literal["preprod", "production"] = "preprod"
    issuer_tax_number: Optional[str] = None
    issuer_name: Optional[str] = None
    branch_code: Optional[str] = "0"
    activity_code: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    sdk_command_template: Optional[str] = None
    certificate_label: Optional[str] = None
    token_pin: Optional[str] = None
    auto_submit_after_generation: bool = False
    portal_url: Optional[str] = None
    notes: Optional[str] = None


class EtaIntegrationSettingsResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    environment: Literal["preprod", "production"] = "preprod"
    issuer_tax_number: Optional[str] = None
    issuer_name: Optional[str] = None
    branch_code: Optional[str] = None
    activity_code: Optional[str] = None
    client_id: Optional[str] = None
    has_client_secret: bool = False
    sdk_command_template: Optional[str] = None
    certificate_label: Optional[str] = None
    has_token_pin: bool = False
    auto_submit_after_generation: bool = False
    portal_url: Optional[str] = None
    notes: Optional[str] = None
    is_configured: bool = False
    required_items: List[str] = Field(default_factory=list)
    last_connection_status: Optional[str] = None
    last_connection_message: Optional[str] = None
    updated_at: datetime


class EtaConnectionTestResponse(BaseModel):
    status: Literal["configured", "configuration_required", "error"]
    message: str
    environment: str
    required_items: List[str] = Field(default_factory=list)
    token_received: bool = False


class EtaSubmissionResponse(BaseModel):
    status: Literal["submitted", "configuration_required", "sdk_required", "error"]
    message: str
    invoice_id: str
    eta_document_uuid: Optional[str] = None
    eta_submission_id: Optional[str] = None
    eta_portal_url: Optional[str] = None
    response_payload: Optional[dict] = None


class ElectronicCustomerBase(BaseModel):
    name: str = Field(..., min_length=1)
    tax_number: Optional[str] = None
    customer_type: Literal["person", "company", "government", "union"] = "person"
    address: Optional[str] = None
    governorate: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


class ElectronicCustomerCreate(ElectronicCustomerBase):
    pass


class ElectronicCustomer(ElectronicCustomerBase):
    model_config = ConfigDict(extra="ignore")

    id: str
    created_at: datetime
    updated_at: datetime


class ElectronicServiceCodeBase(BaseModel):
    code: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    tax_rate: float = Field(default=0, ge=0, le=100)
    is_default: bool = False


class ElectronicServiceCodeCreate(ElectronicServiceCodeBase):
    pass


class ElectronicServiceCode(ElectronicServiceCodeBase):
    model_config = ConfigDict(extra="ignore")

    id: str
    created_at: datetime
    updated_at: datetime


class ElectronicInvoice(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    revenue_id: Optional[str] = None
    source_document_type: Optional[Literal["revenue", "expense", "manual"]] = "revenue"
    source_document_id: Optional[str] = None
    invoice_type: Optional[Literal["sales", "purchase"]] = "sales"
    invoice_number: str
    issue_date: date
    customer_name: str
    customer_tax_number: Optional[str] = None
    customer_type: Literal["person", "company", "government", "union"] = "person"
    service_code: str
    service_name: str
    description: str
    net_amount: float
    tax_rate: float
    tax_amount: float
    total_amount: float
    payment_method: str
    bank_id: str
    bank_name: str
    status: Literal["draft", "ready", "needs_review", "submitted", "accepted", "rejected"] = "draft"
    validation_notes: List[str] = Field(default_factory=list)
    eta_document_uuid: Optional[str] = None
    eta_submission_id: Optional[str] = None
    eta_portal_url: Optional[str] = None
    eta_last_response: Optional[dict] = None
    journal_entry_id: Optional[str] = None
    tax_invoice_entity_id: Optional[str] = None
    tax_engine_snapshot: Optional[dict] = None
    created_at: datetime
    updated_at: datetime


class ElectronicInvoiceStatusUpdate(BaseModel):
    status: Literal["draft", "ready", "needs_review", "submitted", "accepted", "rejected"]


class TaxInvoiceLineCreate(BaseModel):
    description: str = Field(..., min_length=1)
    quantity: float = Field(default=1, gt=0)
    unit_price: float = Field(..., ge=0)
    item_code: str = Field(..., min_length=1)
    tax_status: Literal["standard", "exempt", "zero", "schedule"] = "standard"
    discount_amount: float = Field(default=0, ge=0)


class TaxEngineInvoiceCreate(BaseModel):
    invoice_type: Literal["sales", "purchase"]
    invoice_number: str = Field(..., min_length=1)
    issue_date: date
    customer_name: str = Field(..., min_length=1)
    customer_tax_number: Optional[str] = None
    customer_type: Literal["person", "company", "government", "union"] = "person"
    payment_method: str = "bank_transfer"
    bank_id: str
    lines: List[TaxInvoiceLineCreate] = Field(..., min_length=1)
    source_document_type: Literal["revenue", "expense", "manual"] = "manual"
    source_document_id: Optional[str] = None


class TaxEngineApprovalResponse(BaseModel):
    invoice: ElectronicInvoice
    journal_entry_id: str
    tax_invoice_entity_id: str
    message: str


class PeriodLockCreate(BaseModel):
    period_type: Literal["monthly", "yearly"]
    year: int = Field(..., ge=2020, le=2200)
    month: Optional[int] = Field(default=None, ge=1, le=12)
    action: Literal["lock", "unlock"]
    reason: Optional[str] = None


class PeriodLockResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    period_type: Literal["monthly", "yearly"]
    year: int
    month: Optional[int] = None
    is_locked: bool
    reason: Optional[str] = None
    locked_by: str
    locked_by_name: str
    created_at: datetime
    updated_at: datetime


class ReportApprovalCreate(BaseModel):
    report_type: str
    report_name: str
    report_reference: Optional[str] = None
    period_label: Optional[str] = None
    status: Literal["unapproved", "approved", "cancelled"] = "approved"
    approver_title: str
    notes: Optional[str] = None


class ReportApprovalResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    approval_number: str
    report_type: str
    report_name: str
    report_reference: Optional[str] = None
    period_label: Optional[str] = None
    status: Literal["unapproved", "approved", "cancelled"]
    approver_name: str
    approver_title: str
    approved_by_user_id: str
    approved_by_username: str
    notes: Optional[str] = None
    approval_phrase: str
    qr_payload: str
    created_at: datetime
    updated_at: datetime


class BackupCreate(BaseModel):
    password: str = Field(..., min_length=6)


class BackupRestoreRequest(BaseModel):
    password: str = Field(..., min_length=6)


class BackupRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    file_name: str
    file_size: int
    encrypted: bool
    created_by: str
    created_by_name: str
    created_at: datetime


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    username: Optional[str] = None
    actor_full_name: Optional[str] = None
    user_id: Optional[str] = None
    method: str
    path: str
    action: str
    arabic_description: Optional[str] = None
    status_code: int
    request_body: Optional[dict] = None
    before_document: Optional[dict] = None
    after_document: Optional[dict] = None
    ip_address: Optional[str] = None
    created_at: datetime


class ProgramPurgeRequest(BaseModel):
    scope: Literal["current_organization", "all_organizations"] = "current_organization"
    confirmation_phrase: str
    include_banks: bool = False
    include_users: bool = False


class ProgramPurgeResponse(BaseModel):
    scope: str
    organization_id: Optional[str] = None
    deleted_counts: Dict[str, int]
    reset_counters: List[str]
    message: str


class AccountingRuleBase(BaseModel):
    event_type: Literal["Income", "Expense", "BankFee", "Deposit", "Interest", "OpeningBalance", "MembershipBatchPayment", "AssetPurchase", "AssetDepreciation", "Loan", "Custody"]
    sub_type: Optional[str] = None
    payment_method: Optional[str] = None
    debit_account: str
    credit_account: str
    priority: int = Field(default=5, ge=1, le=10)
    is_active: bool = True
    notes: Optional[str] = None


class AccountingRuleCreate(AccountingRuleBase):
    pass


class AccountingRuleUpdate(AccountingRuleBase):
    pass


class AccountingRuleResponse(AccountingRuleBase):
    model_config = ConfigDict(extra="ignore")

    id: str
    organization_id: str
    is_system: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class RuleSimulationRequest(BaseModel):
    event_type: Literal["Income", "Expense", "BankFee", "Deposit", "Interest", "OpeningBalance", "MembershipBatchPayment", "AssetPurchase", "AssetDepreciation", "Loan", "Custody"]
    sub_type: Optional[str] = None
    payment_method: Optional[str] = None
    amount: float = Field(..., gt=0)
    bank_id: Optional[str] = None


class RuleSimulationResponse(BaseModel):
    matched_rule: Optional[AccountingRuleResponse] = None
    conflicts: List[AccountingRuleResponse] = Field(default_factory=list)
    preview_lines: List[JournalLine] = Field(default_factory=list)
    is_valid: bool
    errors: List[str] = Field(default_factory=list)
    total_debit: float = 0
    total_credit: float = 0
    simulation_only: bool = True


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
    organization_id = organization_id_or_default()
    deleted_documents = await db.deleted_banks.find(with_organization({}, organization_id), {"_id": 0, "id": 1}).to_list(500)
    deleted_ids = {document["id"] for document in deleted_documents}
    settings_documents = await db.bank_settings.find(with_organization({}, organization_id), {"_id": 0}).to_list(500)
    opening_balances = {document["bank_id"]: float(document.get("opening_balance", 0) or 0) for document in settings_documents}
    opening_balance_dates = {document["bank_id"]: document.get("opening_balance_date") for document in settings_documents if document.get("opening_balance_date")}
    custom_banks = await db.banks.find(with_organization({}, organization_id), {"_id": 0}).sort("created_at", 1).to_list(500)
    merged = list(BANKS.values()) + custom_banks
    seen = set()
    result = []
    for bank in merged:
        if bank["id"] not in seen and bank["id"] not in deleted_ids:
            seen.add(bank["id"])
            clean_bank = dict(bank)
            clean_bank["opening_balance"] = opening_balances.get(bank["id"], float(bank.get("opening_balance", 0) or 0))
            clean_bank["opening_balance_date"] = opening_balance_dates.get(bank["id"], bank.get("opening_balance_date"))
            result.append(clean_bank)
    return result


async def ensure_bank_async(bank_id: str) -> dict:
    organization_id = organization_id_or_default()
    deleted_bank = await db.deleted_banks.find_one(with_organization({"id": bank_id}, organization_id), {"_id": 0})
    if deleted_bank:
        raise HTTPException(status_code=404, detail="البنك محذوف أو غير موجود")
    bank = BANKS.get(bank_id)
    if bank:
        setting = await db.bank_settings.find_one(with_organization({"bank_id": bank_id}, organization_id), {"_id": 0})
        clean_bank = dict(bank)
        clean_bank["opening_balance"] = float(setting.get("opening_balance", 0) or 0) if setting else 0
        clean_bank["opening_balance_date"] = setting.get("opening_balance_date") if setting else None
        return clean_bank
    custom_bank = await db.banks.find_one(with_organization({"id": bank_id}, organization_id), {"_id": 0})
    if not custom_bank:
        raise HTTPException(status_code=404, detail="البنك غير موجود")
    setting = await db.bank_settings.find_one(with_organization({"bank_id": bank_id}, organization_id), {"_id": 0})
    custom_bank["opening_balance"] = float(setting.get("opening_balance", custom_bank.get("opening_balance", 0)) or 0) if setting else float(custom_bank.get("opening_balance", 0) or 0)
    custom_bank["opening_balance_date"] = setting.get("opening_balance_date", custom_bank.get("opening_balance_date")) if setting else custom_bank.get("opening_balance_date")
    return custom_bank


async def ensure_bank_transaction_date_allowed(bank_id: Optional[str], target_date: date):
    if not bank_id or not target_date:
        return
    bank = await ensure_bank_async(bank_id)
    opening_date = parse_date_field(bank.get("opening_balance_date"))
    if opening_date and target_date < opening_date:
        raise HTTPException(status_code=400, detail=f"لا يُسمح بإجراء أي معاملة مالية قبل تاريخ الرصيد الافتتاحي. البنك: {bank.get('name')} | تاريخ العملية: {target_date.isoformat().replace('-', '/')} | تاريخ الرصيد الافتتاحي: {opening_date.isoformat().replace('-', '/')}")


async def bank_transactions_before_date(bank_id: str, opening_date: date) -> List[dict]:
    organization_id = organization_id_or_default()
    date_value = opening_date.isoformat()
    checks = [
        ("الودائع", "deposits", {"bank_id": bank_id, "creation_datetime": {"$lt": f"{date_value}T00:00:00"}, "is_opening_balance_deposit": {"$ne": True}}, "deposit_number", "creation_datetime"),
        ("الإيرادات", "revenues", {"bank_id": bank_id, "issued_at": {"$lt": date_value}}, "receipt_number", "issued_at"),
        ("المصروفات", "expenses", {"bank_id": bank_id, "issued_at": {"$lt": date_value}}, "expense_number", "issued_at"),
        ("الأصول الثابتة", "fixed_assets", {"bank_id": bank_id, "purchase_date": {"$lt": date_value}}, "asset_code", "purchase_date"),
        ("العهد والسلف", "custody_advances", {"bank_id": bank_id, "issue_date": {"$lt": date_value}}, "document_number", "issue_date"),
        ("أذون العضوية الجماعية", "membership_batch_payments", {"bank_id": bank_id, "payment_date": {"$lt": date_value}}, "receipt_number", "payment_date"),
        ("التسويات البنكية", "reconciliations", {"bank_id": bank_id, "created_at": {"$lt": f"{date_value}T00:00:00"}}, "period_label", "created_at"),
    ]
    conflicts = []
    for label, collection_name, query, reference_field, date_field in checks:
        documents = await db[collection_name].find(with_organization(query, organization_id), {"_id": 0, reference_field: 1, date_field: 1}).sort(date_field, 1).limit(3).to_list(3)
        if documents:
            conflicts.append({"collection": label, "count": await db[collection_name].count_documents(with_organization(query, organization_id)), "examples": documents})
    manual_query = with_organization({"bank_id": bank_id, "$or": [{"year": {"$lt": opening_date.year}}, {"year": opening_date.year, "month": {"$lt": opening_date.month}}]}, organization_id)
    manual_count = await db.banking_manual_charges.count_documents(manual_query)
    if manual_count:
        examples = await db.banking_manual_charges.find(manual_query, {"_id": 0, "year": 1, "month": 1}).sort("year", 1).sort("month", 1).limit(3).to_list(3)
        conflicts.append({"collection": "المصروفات البنكية", "count": manual_count, "examples": examples})
    return conflicts


async def ensure_opening_balance_date_not_after_existing_transactions(bank_id: str, opening_date: date):
    conflicts = await bank_transactions_before_date(bank_id, opening_date)
    if conflicts:
        summary = "، ".join(f"{item['collection']} ({item['count']})" for item in conflicts)
        raise HTTPException(status_code=400, detail=f"لا يمكن تعيين تاريخ الرصيد الافتتاحي بعد معاملات مسجلة بالفعل لهذا البنك. اختر تاريخاً يسبق أو يساوي أقدم معاملة. معاملات أقدم من التاريخ المختار: {summary}")


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
    document = await db.banking_tariffs.find_one(with_organization({"bank_id": bank_id, "account_type": "companies"}), {"_id": 0})
    if document:
        return document
    return attach_organization(build_tariff_document(bank, default_tariff_rules(bank_id), notes="القيم الافتراضية الحالية", status="default"))


def normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def serialize_datetime(value: datetime) -> str:
    return normalize_datetime(value).isoformat()


def organization_id_or_default() -> str:
    return CURRENT_ORGANIZATION_ID.get() or DEFAULT_ORGANIZATION_ID


def default_modules_for_organization(organization_id: str) -> Dict[str, bool]:
    modules = {key: True for key in MODULE_DEFINITIONS}
    modules["electronic_invoice"] = False
    if organization_id == "general-union":
        modules["membership"] = False
    return modules


def normalize_modules(organization_id: str, modules: Optional[dict] = None) -> Dict[str, bool]:
    normalized = default_modules_for_organization(organization_id)
    for key, value in (modules or {}).items():
        if key in normalized:
            normalized[key] = bool(value)
    return normalized


def with_organization(query: Optional[dict] = None, organization_id: Optional[str] = None) -> dict:
    next_query = dict(query or {})
    next_query["organization_id"] = organization_id or organization_id_or_default()
    return next_query


def attach_organization(document: dict, organization_id: Optional[str] = None) -> dict:
    document["organization_id"] = organization_id or organization_id_or_default()
    return document


def is_internal_test_organization_id(value: Optional[str]) -> bool:
    text = (value or "").lower()
    return text.startswith(("iter", "test-", "pytest", "accounting-fix-test", "opening-balance-fix-test")) or " iter" in text or "iter" in text


def normalize_arabic_key(value: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower().replace("إ", "ا").replace("أ", "ا").replace("آ", "ا").replace("ة", "ه").replace("ى", "ي"))


async def get_organization_document(organization_id: Optional[str] = None) -> dict:
    org_id = organization_id or organization_id_or_default()
    base = ORGANIZATIONS.get(org_id)
    custom = await db.organizations.find_one({"id": org_id}, {"_id": 0})
    if not base and not custom:
        raise HTTPException(status_code=404, detail="الجهة غير موجودة")
    base = base or {"id": org_id, "name": custom.get("name"), "login_label": custom.get("login_label") or custom.get("name")}
    document = {**base, **(custom or {})}
    document["modules"] = normalize_modules(org_id, document.get("modules"))
    return document


async def list_organization_documents() -> List[dict]:
    result = []
    seen = set()
    for org_id in ORGANIZATIONS:
        result.append(await get_organization_document(org_id))
        seen.add(org_id)
    custom_orgs = await db.organizations.find({"id": {"$nin": list(seen)}, "is_active": {"$ne": False}}, {"_id": 0}).sort("created_at", 1).to_list(1000)
    for custom in custom_orgs:
        if is_internal_test_organization_id(custom.get("id")) or is_internal_test_organization_id(custom.get("login_label")) or is_internal_test_organization_id(custom.get("name")):
            continue
        custom["modules"] = normalize_modules(custom["id"], custom.get("modules"))
        result.append(custom)
    return result


def app_icon_url(updated_at: Optional[str] = None) -> Optional[str]:
    if not updated_at:
        return None
    version = re.sub(r"[^0-9A-Za-z]", "", updated_at)
    return f"/api/app-settings/icon?v={version}"


def official_email_or_none(email: Optional[str]) -> Optional[str]:
    cleaned = (email or "").strip()
    if not cleaned:
        return None
    lowered = cleaned.lower()
    if lowered.endswith("@example.com") or "+iter" in lowered:
        return None
    return cleaned


def source_integrity_digest() -> str:
    hasher = hashlib.sha256()
    for path in [ROOT_DIR / "server.py", ROOT_DIR / "requirements.txt"]:
        if path.exists():
            hasher.update(path.name.encode())
            hasher.update(path.read_bytes())
    font_dir = ROOT_DIR / "assets" / "fonts"
    if font_dir.exists():
        for path in sorted(font_dir.glob("*.ttf")):
            hasher.update(path.name.encode())
            hasher.update(path.read_bytes())
    return hasher.hexdigest()


def intellectual_property_fingerprint(owner: Optional[str], system_name: str, national_id: Optional[str] = None, override: Optional[str] = None) -> str:
    if override:
        return override
    material = f"{owner or 'OWNER-NOT-SET'}|{system_name}|{JWT_SECRET}|BANK-DEPOSIT-SYSTEM".encode()
    if national_id:
        material += f"|{national_id}".encode()
    digest = hashlib.sha256(material).hexdigest().upper()
    return f"IP-EG-{digest[:8]}-{digest[8:16]}-{digest[16:24]}-{digest[24:32]}"


async def get_app_settings_document() -> dict:
    now_iso = serialize_datetime(datetime.now(timezone.utc))
    document = await db.app_settings.find_one({"id": "global"}, {"_id": 0})
    if document:
        document["shortcut_icon_url"] = app_icon_url(document.get("shortcut_icon_updated_at"))
        return document
    document = {
        "id": "global",
        "system_name": DEFAULT_SYSTEM_NAME,
        "login_union_logo_visible": True,
        "login_union_logo_data_url": None,
        "login_authority_logos": [],
        "backup_enabled": True,
        "backup_allowed_roles": {"super_admin": True, "admin": True, "user": False},
        "two_factor_role_policy": {"super_admin": False, "admin": False, "user": False},
        "include_tech_stack_in_manual": False,
        "hide_ai_attribution": True,
        "intellectual_property_owner": None,
        "intellectual_property_national_id": None,
        "intellectual_property_fingerprint": None,
        "source_lock_password_hash": None,
        "installed_files_lock_enabled": False,
        "installed_files_password_hash": None,
        "session_timeout_minutes": 1,
        "shortcut_icon_updated_at": None,
        "shortcut_update_status": "لم يتم رفع أيقونة مخصصة بعد",
        "created_at": now_iso,
        "updated_at": now_iso,
    }
    await db.app_settings.insert_one(document.copy())
    document["shortcut_icon_url"] = app_icon_url(document.get("shortcut_icon_updated_at"))
    return document


def build_organization_modules_response(organization: dict) -> OrganizationModulesResponse:
    return OrganizationModulesResponse(
        organization_id=organization["id"],
        organization_name=organization["name"],
        modules=normalize_modules(organization["id"], organization.get("modules")),
        module_labels=MODULE_DEFINITIONS,
        updated_at=organization.get("updated_at") or serialize_datetime(datetime.now(timezone.utc)),
    )


async def build_app_settings_response(document: dict) -> AppSettingsResponse:
    organization_id = organization_id_or_default()
    organization_name = document.get("organization_name")
    organization_login_label = document.get("organization_login_label")
    organizations = {item["id"]: {"id": item["id"], "name": item["name"], "login_label": item["login_label"], "email": official_email_or_none(item.get("email")), "is_active": item.get("is_active", True), "modules": item.get("modules", {})} for item in await list_organization_documents()}
    return AppSettingsResponse(
        system_name=document.get("system_name") or DEFAULT_SYSTEM_NAME,
        organization_id=organization_id,
        organization_name=organization_name,
        organization_login_label=organization_login_label,
        organizations=organizations,
        login_union_logo_visible=bool(document.get("login_union_logo_visible", True)),
        login_union_logo_data_url=document.get("login_union_logo_data_url"),
        login_authority_logos=document.get("login_authority_logos") or [],
        backup_enabled=bool(document.get("backup_enabled", True)),
        backup_allowed_roles=document.get("backup_allowed_roles") or {"super_admin": True, "admin": True, "user": False},
        two_factor_role_policy=document.get("two_factor_role_policy") or {"super_admin": False, "admin": False, "user": False},
        include_tech_stack_in_manual=bool(document.get("include_tech_stack_in_manual", False)),
        hide_ai_attribution=bool(document.get("hide_ai_attribution", True)),
        intellectual_property_owner=document.get("intellectual_property_owner"),
        intellectual_property_national_id=document.get("intellectual_property_national_id"),
        intellectual_property_fingerprint=intellectual_property_fingerprint(document.get("intellectual_property_owner"), document.get("system_name") or DEFAULT_SYSTEM_NAME, document.get("intellectual_property_national_id"), document.get("intellectual_property_fingerprint")),
        source_lock_password_set=bool(document.get("source_lock_password_hash")),
        installed_files_lock_enabled=bool(document.get("installed_files_lock_enabled", False)),
        installed_files_password_set=bool(document.get("installed_files_password_hash")),
        session_timeout_minutes=int(document.get("session_timeout_minutes") or 1),
        source_integrity_digest=source_integrity_digest(),
        shortcut_icon_url=document.get("shortcut_icon_url") or app_icon_url(document.get("shortcut_icon_updated_at")),
        shortcut_icon_updated_at=document.get("shortcut_icon_updated_at"),
        shortcut_update_status=document.get("shortcut_update_status"),
        updated_at=document.get("updated_at") or serialize_datetime(datetime.now(timezone.utc)),
    )


def convert_uploaded_icon_to_ico(content: bytes, filename: str, content_type: Optional[str]) -> bytes:
    extension = Path(filename or "").suffix.lower()
    normalized_type = (content_type or "").lower()
    if len(content) > 4 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="حجم الأيقونة يجب ألا يتجاوز 4 ميجابايت")
    if extension == ".ico" or normalized_type in {"image/x-icon", "image/vnd.microsoft.icon"}:
        if not content.startswith(b"\x00\x00\x01\x00"):
            raise HTTPException(status_code=400, detail="ملف ICO غير صالح")
        return content
    if extension not in {".png", ".jpg", ".jpeg"} and normalized_type not in {"image/png", "image/jpeg", "image/jpg"}:
        raise HTTPException(status_code=400, detail="ارفع أيقونة بصيغة PNG أو JPG أو ICO فقط")
    try:
        image = Image.open(BytesIO(content)).convert("RGBA")
        icon_buffer = BytesIO()
        image.save(icon_buffer, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
        return icon_buffer.getvalue()
    except Exception:
        raise HTTPException(status_code=400, detail="تعذر تحويل الصورة إلى أيقونة")


def update_windows_shortcut_icon(icon_path: Path) -> str:
    if os.name != "nt":
        return "تم حفظ الأيقونة، وسيتم تحديث اختصارات Windows عند تشغيل النسخة المثبتة محلياً"
    user_profile = Path(os.environ.get("USERPROFILE", ""))
    app_data = Path(os.environ.get("APPDATA", ""))
    shortcut_paths = [
        user_profile / "Desktop" / "Bank Deposit System.lnk",
        app_data / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Bank Deposit Interest System" / "Bank Deposit System.lnk",
    ]
    updated = 0
    for shortcut_path in shortcut_paths:
        if not shortcut_path.exists():
            continue
        safe_shortcut = str(shortcut_path).replace("'", "''")
        safe_icon = str(icon_path).replace("'", "''")
        script = f"$w=New-Object -ComObject WScript.Shell;$s=$w.CreateShortcut('{safe_shortcut}');$s.IconLocation='{safe_icon},0';$s.Save();"
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script], check=False, capture_output=True, text=True, timeout=20)
        updated += 1
    return f"تم حفظ الأيقونة وتحديث {updated} اختصار على Windows" if updated else "تم حفظ الأيقونة، ولم يتم العثور على اختصارات لتحديثها"


async def sync_local_app_icon_cache() -> bool:
    document = await db.app_settings.find_one({"id": "global"}, {"_id": 0, "icon_base64": 1})
    icon_b64 = (document or {}).get("icon_base64")
    if not icon_b64:
        return False
    APP_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    APP_ICON_PATH.write_bytes(base64.b64decode(icon_b64))
    return True


def serialize_date(value: date) -> str:
    return value.isoformat()


def hydrate_deposit(document: dict) -> dict:
    clean = {key: value for key, value in document.items() if key != "_id"}
    clean.setdefault("is_opening_balance_deposit", False)
    clean.setdefault("renewed_from_deposit_id", None)
    clean.setdefault("renewal_notes", None)
    clean.setdefault("use_daily_rounding", True)
    for field_name in ["creation_datetime", "maturity_datetime", "accounting_start_datetime", "created_at", "updated_at"]:
        if isinstance(clean.get(field_name), str):
            clean[field_name] = datetime.fromisoformat(clean[field_name])
    stored_status = clean.get("status")
    if stored_status not in {"renewed", "closed"}:
        maturity_value = normalize_datetime(clean.get("maturity_datetime")) if clean.get("maturity_datetime") else None
        clean["status"] = "matured" if maturity_value and maturity_value <= datetime.now(timezone.utc) else "active"
    return clean


def hydrate_journal_entry(document: dict) -> dict:
    clean = {key: value for key, value in document.items() if key != "_id"}
    if isinstance(clean.get("entry_date"), str):
        clean["entry_date"] = date.fromisoformat(clean["entry_date"])
    for field_name in ["created_at", "updated_at"]:
        if isinstance(clean.get(field_name), str):
            clean[field_name] = datetime.fromisoformat(clean[field_name])
    return clean


def hydrate_chart_account(document: dict) -> dict:
    clean = {key: value for key, value in document.items() if key != "_id"}
    for field_name in ["created_at", "updated_at"]:
        if isinstance(clean.get(field_name), str):
            clean[field_name] = datetime.fromisoformat(clean[field_name])
    return clean


def fixed_asset_category(category_code: str) -> dict:
    category = next((item for item in FIXED_ASSET_CATEGORIES if item["code"] == str(category_code)), None)
    if not category:
        raise HTTPException(status_code=400, detail="تصنيف الأصل الثابت غير صحيح")
    return category


async def fixed_asset_category_with_rate(category_code: str, organization_id: Optional[str] = None) -> dict:
    category = fixed_asset_category(category_code).copy()
    setting = await db.fixed_asset_category_settings.find_one(with_organization({"code": category["code"]}, organization_id or organization_id_or_default()), {"_id": 0})
    if setting and setting.get("annual_depreciation_rate") is not None:
        category["annual_depreciation_rate"] = float(setting["annual_depreciation_rate"])
    return category


async def fixed_asset_categories_with_rates(organization_id: Optional[str] = None) -> List[dict]:
    return [await fixed_asset_category_with_rate(category["code"], organization_id) for category in FIXED_ASSET_CATEGORIES]


def month_end_date(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])


def add_months_safe(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def months_between_inclusive(start_date: date, end_date: date) -> int:
    if end_date < date(start_date.year, start_date.month, 1):
        return 0
    return (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month) + 1


def fixed_asset_monthly_depreciation(purchase_cost: float, annual_rate: float) -> float:
    return round(float(purchase_cost or 0) * float(annual_rate or 0) / 100 / 12, 2)


def fixed_asset_annual_depreciation(purchase_cost: float, annual_rate: float) -> float:
    return round(float(purchase_cost or 0) * float(annual_rate or 0) / 100, 2)


def fixed_asset_disposal_date(purchase_date: date, purchase_cost: float, annual_rate: float) -> Optional[date]:
    monthly_amount = fixed_asset_monthly_depreciation(purchase_cost, annual_rate)
    if monthly_amount <= 0:
        return None
    months_needed = max(math.ceil(float(purchase_cost or 0) / monthly_amount), 1)
    final_month_date = add_months_safe(purchase_date, months_needed - 1)
    return month_end_date(final_month_date.year, final_month_date.month)


def fixed_asset_catalog_default_id(category_code: str, name: str) -> str:
    digest = hashlib.sha1(f"{category_code}:{name}".encode("utf-8")).hexdigest()[:12]
    return f"default-{category_code}-{digest}"


async def list_fixed_asset_catalog_items_for_category(category_code: str, organization_id: Optional[str] = None) -> List[dict]:
    category = fixed_asset_category(category_code)
    org_id = organization_id or organization_id_or_default()
    hidden_documents = await db.fixed_asset_catalog_hidden.find(with_organization({"category_code": category["code"]}, org_id), {"_id": 0, "name": 1}).to_list(1000)
    hidden_names = {item.get("name") for item in hidden_documents}
    items = []
    for name in category["items"]:
        if name in hidden_names:
            continue
        items.append({"id": fixed_asset_catalog_default_id(category["code"], name), "category_code": category["code"], "name": name, "is_default": True, "is_custom": False})
    custom_documents = await db.fixed_asset_catalog_items.find(with_organization({"category_code": category["code"]}, org_id), {"_id": 0}).sort("name", 1).to_list(1000)
    for document in custom_documents:
        items.append({"id": document["id"], "category_code": category["code"], "name": document["name"], "is_default": False, "is_custom": True})
    return items


async def list_fixed_asset_categories_with_catalog(organization_id: Optional[str] = None) -> List[dict]:
    result = []
    for category in await fixed_asset_categories_with_rates(organization_id):
        catalog_items = await list_fixed_asset_catalog_items_for_category(category["code"], organization_id)
        result.append({**category, "items": [item["name"] for item in catalog_items]})
    return result


def retirement_age_for_birth_date(birth_date: date) -> int:
    if birth_date >= date(1975, 7, 1):
        return 65
    if birth_date >= date(1974, 7, 1):
        return 64
    if birth_date >= date(1973, 7, 1):
        return 63
    if birth_date >= date(1972, 7, 1):
        return 62
    if birth_date >= date(1971, 7, 1):
        return 61
    return 60


def add_years_safe(value: date, years: int) -> date:
    try:
        return value.replace(year=value.year + years)
    except ValueError:
        return value.replace(year=value.year + years, day=28)


def membership_retirement_fields(birth_date: date) -> dict:
    retirement_age = retirement_age_for_birth_date(birth_date)
    retirement_date = add_years_safe(birth_date, retirement_age)
    return {"retirement_age": retirement_age, "retirement_date": serialize_date(retirement_date), "retirement_year": retirement_date.year, "retirement_month": retirement_date.month}


def normalize_member_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def require_social_solidarity_membership(current_user: dict):
    if (current_user.get("organization_id") or DEFAULT_ORGANIZATION_ID) != "social-solidarity":
        raise HTTPException(status_code=404, detail="صفحة العضوية متاحة لمشروع التكافل الاجتماعي فقط")


IMPORT_FIELD_LABELS = {
    "membership_number": ["رقم العضوية", "رقم العضويه", "رقم العضو", "عضوية", "العضوية", "member no", "membership no"],
    "name": ["الاسم", "اسم العضو", "اسم المشترك", "اسم", "name", "member name"],
    "national_id": ["الرقم القومي", "رقم قومي", "القومي", "الرقم القومى", "national id", "nid"],
    "birth_date": ["تاريخ الميلاد", "الميلاد", "تاريخ ميلاد", "date of birth", "birth date", "dob"],
    "address": ["العنوان", "عنوان", "محل الاقامة", "محل الإقامة", "address"],
    "death_beneficiary": ["في حالة الوفاة", "مستلم الاعانة", "مستلم الإعانة", "المستفيد", "مستفيد", "يصرف الى", "يصرف إلى", "beneficiary"],
}


def normalize_import_key(value: str) -> str:
    text = normalize_member_text(str(value or "")).lower()
    replacements = {"أ": "ا", "إ": "ا", "آ": "ا", "ة": "ه", "ى": "ي", "ؤ": "و", "ئ": "ي"}
    for source, target in replacements.items():
        text = text.replace(source, target)
    return re.sub(r"[^\w\u0600-\u06FF]+", "", text)


def import_header_field(value: str) -> Optional[str]:
    normalized = normalize_import_key(value)
    if not normalized:
        return None
    for field_name, labels in IMPORT_FIELD_LABELS.items():
        for label in labels:
            label_key = normalize_import_key(label)
            if label_key and (label_key == normalized or label_key in normalized or normalized in label_key):
                return field_name
    return None


def parse_import_date(value: str) -> Optional[date]:
    text = normalize_digit_text(str(value or "")).strip()
    if not text:
        return None
    if re.fullmatch(r"\d+(\.0)?", text):
        serial = int(float(text))
        if 20000 <= serial <= 80000:
            return date(1899, 12, 30) + timedelta(days=serial)
    for pattern in ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d.%m.%Y"]:
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    match = re.search(r"(\d{1,2})[\-/\.](\d{1,2})[\-/\.](\d{4})", text)
    if match:
        day, month, year = [int(item) for item in match.groups()]
        try:
            return date(year, month, day)
        except ValueError:
            return None
    return None


def extract_xlsx_rows(content: bytes) -> List[List[str]]:
    try:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            shared_strings = []
            if "xl/sharedStrings.xml" in archive.namelist():
                shared_root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
                for item in shared_root.iter():
                    if item.tag.endswith("}si"):
                        texts = [node.text or "" for node in item.iter() if node.tag.endswith("}t")]
                        shared_strings.append("".join(texts))
            worksheet_names = sorted([name for name in archive.namelist() if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")])
            rows = []
            for worksheet_name in worksheet_names[:3]:
                root = ET.fromstring(archive.read(worksheet_name))
                for row in root.iter():
                    if not row.tag.endswith("}row"):
                        continue
                    values = []
                    for cell in list(row):
                        if not cell.tag.endswith("}c"):
                            continue
                        cell_type = cell.attrib.get("t")
                        value_node = next((child for child in list(cell) if child.tag.endswith("}v")), None)
                        inline_text = "".join(node.text or "" for node in cell.iter() if node.tag.endswith("}t"))
                        value = value_node.text if value_node is not None else inline_text
                        if cell_type == "s" and value is not None:
                            try:
                                value = shared_strings[int(value)]
                            except (ValueError, IndexError):
                                value = ""
                        values.append(str(value or "").strip())
                    if any(values):
                        rows.append(values)
            return rows
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="ملف Excel غير صالح")


def extract_docx_rows(content: bytes) -> List[List[str]]:
    try:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            if "word/document.xml" not in archive.namelist():
                raise HTTPException(status_code=400, detail="ملف Word غير صالح")
            root = ET.fromstring(archive.read("word/document.xml"))
            rows = []
            for table_row in root.iter():
                if not table_row.tag.endswith("}tr"):
                    continue
                cells = []
                for cell in list(table_row):
                    if cell.tag.endswith("}tc"):
                        text = " ".join(node.text or "" for node in cell.iter() if node.tag.endswith("}t"))
                        cells.append(normalize_member_text(text))
                if any(cells):
                    rows.append(cells)
            if rows:
                return rows
            paragraphs = []
            for paragraph in root.iter():
                if paragraph.tag.endswith("}p"):
                    text = " ".join(node.text or "" for node in paragraph.iter() if node.tag.endswith("}t"))
                    text = normalize_member_text(text)
                    if text:
                        paragraphs.append(split_import_line(text))
            return [row for row in paragraphs if row]
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="ملف Word غير صالح")


def split_import_line(line: str) -> List[str]:
    text = normalize_member_text(line)
    if not text:
        return []
    separators = ["\t", "|", ";", ","]
    for separator in separators:
        if separator in text:
            return [part.strip() for part in text.split(separator) if part.strip()]
    return [part.strip() for part in re.split(r"\s{2,}", text) if part.strip()]


def extract_pdf_rows(content: bytes) -> List[List[str]]:
    reader = PdfReader(BytesIO(content))
    rows = []
    for page in reader.pages:
        text = page.extract_text() or ""
        for line in text.splitlines():
            row = split_import_line(line)
            if row:
                rows.append(row)
    return rows


def extract_membership_import_rows(filename: str, content: bytes) -> List[List[str]]:
    suffix = Path(filename or "").suffix.lower()
    if suffix == ".pdf":
        return extract_pdf_rows(content)
    if suffix == ".docx":
        return extract_docx_rows(content)
    if suffix == ".xlsx":
        return extract_xlsx_rows(content)
    if suffix == ".csv":
        text = content.decode("utf-8-sig")
        return [split_import_line(line) for line in text.splitlines() if split_import_line(line)]
    if suffix in [".doc", ".xls"]:
        raise HTTPException(status_code=400, detail="برجاء حفظ ملف Word بصيغة DOCX أو ملف Excel بصيغة XLSX ثم إعادة الاستيراد")
    raise HTTPException(status_code=400, detail="صيغة الملف غير مدعومة. استخدم PDF أو DOCX أو XLSX")


def build_header_mapping(rows: List[List[str]]) -> tuple[Optional[int], dict]:
    best_index = None
    best_mapping = {}
    for index, row in enumerate(rows[:10]):
        mapping = {}
        for column_index, value in enumerate(row):
            field_name = import_header_field(value)
            if field_name and field_name not in mapping.values():
                mapping[column_index] = field_name
        if len(mapping) > len(best_mapping):
            best_index = index
            best_mapping = mapping
    if len(best_mapping) >= 3:
        return best_index, best_mapping
    return None, {}


def row_to_membership_payload(row: List[str], mapping: dict) -> dict:
    payload = {}
    for index, field_name in mapping.items():
        if index < len(row):
            payload[field_name] = normalize_member_text(row[index])
    return payload


def infer_membership_payload(row: List[str]) -> dict:
    cells = [normalize_member_text(cell) for cell in row if normalize_member_text(cell)]
    payload = {}
    used = set()
    for index, cell in enumerate(cells):
        digits = normalize_digit_text(cell)
        if "national_id" not in payload and re.fullmatch(r"\d{14}", digits):
            payload["national_id"] = digits
            used.add(index)
            continue
        parsed_date = parse_import_date(cell)
        if "birth_date" not in payload and parsed_date:
            payload["birth_date"] = serialize_date(parsed_date)
            used.add(index)
            continue
    for index, cell in enumerate(cells):
        digits = normalize_digit_text(cell)
        if index not in used and "membership_number" not in payload and re.fullmatch(r"\d{1,12}", digits):
            payload["membership_number"] = digits
            used.add(index)
            break
    remaining = [(index, cell) for index, cell in enumerate(cells) if index not in used]
    name_candidates = [(index, cell) for index, cell in remaining if len(cell) >= 5 and not re.search(r"شارع|طريق|محافظة|مركز|قسم|حي|منزل|عمارة", cell)]
    if name_candidates:
        index, cell = name_candidates[0]
        payload["name"] = cell
        used.add(index)
    remaining = [(index, cell) for index, cell in enumerate(cells) if index not in used]
    if remaining:
        address_index, address = max(remaining, key=lambda item: len(item[1]))
        payload["address"] = address
        used.add(address_index)
    remaining = [(index, cell) for index, cell in enumerate(cells) if index not in used]
    if remaining:
        payload["death_beneficiary"] = remaining[0][1]
    return payload


def normalize_import_membership_payload(payload: dict, governorate: str, union_committee: str) -> Optional[dict]:
    birth_value = payload.get("birth_date")
    birth_date_value = parse_import_date(birth_value) if not isinstance(birth_value, date) else birth_value
    national_id = normalize_digit_text(payload.get("national_id") or "")
    membership_number = normalize_digit_text(payload.get("membership_number") or "")
    required_payload = {
        "governorate": governorate,
        "union_committee": union_committee,
        "membership_number": membership_number,
        "name": normalize_member_text(payload.get("name") or ""),
        "national_id": national_id,
        "birth_date": birth_date_value,
        "address": normalize_member_text(payload.get("address") or ""),
        "death_beneficiary": normalize_member_text(payload.get("death_beneficiary") or ""),
    }
    if not all([required_payload["membership_number"], required_payload["name"], required_payload["national_id"], required_payload["birth_date"], required_payload["address"], required_payload["death_beneficiary"]]):
        return None
    if not required_payload["national_id"].isdigit() or len(required_payload["national_id"]) != 14:
        return None
    return required_payload


async def build_membership_import_preview_document(governorate: str, union_committee: str, filename: str, content: bytes, default_status: MembershipStatus = "active", default_status_effective_date: Optional[date] = None) -> dict:
    clean_governorate = normalize_member_text(governorate)
    clean_committee = normalize_member_text(union_committee)
    selected_status = default_status or "active"
    selected_status_effective_date = default_status_effective_date if selected_status in NON_ACTIVE_MEMBERSHIP_STATUSES else None
    if not clean_governorate or not clean_committee:
        raise HTTPException(status_code=400, detail="اختر المحافظة واسم اللجنة قبل الاستيراد")
    if not content:
        raise HTTPException(status_code=400, detail="الملف فارغ")
    if len(content) > 15 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="حجم الملف كبير جداً. الحد الأقصى 15 ميجا")
    rows = extract_membership_import_rows(filename or "", content)
    if not rows:
        raise HTTPException(status_code=400, detail="لم يتم العثور على صفوف قابلة للاستيراد داخل الملف. إذا كان PDF مصوراً برجاء تحويله إلى Excel/Word أو استخدام PDF نصي واضح")
    header_index, mapping = build_header_mapping(rows)
    accepted_rows = []
    accepted_payloads = []
    skipped_rows = []
    total_detected = 0
    seen_membership_numbers = set()
    seen_national_ids = set()
    for index, row in enumerate(rows, start=1):
        if header_index is not None and index - 1 <= header_index:
            continue
        if not any(normalize_member_text(cell) for cell in row):
            continue
        total_detected += 1
        raw_payload = row_to_membership_payload(row, mapping) if mapping else infer_membership_payload(row)
        normalized_payload = normalize_import_membership_payload(raw_payload, clean_governorate, clean_committee)
        if not normalized_payload:
            skipped_rows.append({"row_number": index, "reason": "لم يتم العثور على كل البيانات المطلوبة في الصف"})
            continue
        if normalized_payload["membership_number"] in seen_membership_numbers or normalized_payload["national_id"] in seen_national_ids:
            skipped_rows.append({"row_number": index, "reason": "صف مكرر داخل الملف"})
            continue
        seen_membership_numbers.add(normalized_payload["membership_number"])
        seen_national_ids.add(normalized_payload["national_id"])
        normalized_payload["status"] = selected_status
        normalized_payload["status_effective_date"] = selected_status_effective_date
        try:
            payload = MembershipCreate(**normalized_payload)
            await membership_document_from_payload(payload)
        except HTTPException as exc:
            skipped_rows.append({"row_number": index, "reason": str(exc.detail)})
            continue
        except Exception:
            skipped_rows.append({"row_number": index, "reason": "بيانات الصف غير صالحة"})
            continue
        retirement = membership_retirement_fields(payload.birth_date)
        accepted_rows.append({
            "row_number": index,
            **normalized_payload,
            "birth_date": serialize_date(payload.birth_date),
            "status_label": MEMBERSHIP_STATUS_LABELS.get(selected_status, "فعال"),
            "status_effective_date": serialize_date(selected_status_effective_date) if selected_status_effective_date else None,
            "retirement_age": retirement["retirement_age"],
            "retirement_date": retirement["retirement_date"],
        })
        accepted_payloads.append({"row_number": index, **normalized_payload, "birth_date": serialize_date(payload.birth_date), "status_effective_date": serialize_date(selected_status_effective_date) if selected_status_effective_date else None})
    now_iso = serialize_datetime(datetime.now(timezone.utc))
    return {
        "id": str(uuid.uuid4()),
        "organization_id": organization_id_or_default(),
        "governorate": clean_governorate,
        "union_committee": clean_committee,
        "filename": filename,
        "total_rows_detected": total_detected,
        "accepted_rows": accepted_rows,
        "accepted_payloads": accepted_payloads,
        "skipped_rows": skipped_rows,
        "created_at": now_iso,
        "updated_at": now_iso,
    }


def membership_import_preview_response(document: dict) -> MembershipImportPreviewResponse:
    return MembershipImportPreviewResponse(
        preview_id=document["id"],
        accepted_count=len(document.get("accepted_rows") or []),
        skipped_count=len(document.get("skipped_rows") or []),
        total_rows_detected=int(document.get("total_rows_detected") or 0),
        accepted_rows=[MembershipImportAcceptedRow(**row) for row in document.get("accepted_rows", [])[:200]],
        skipped_rows=[MembershipImportSkippedRow(**row) for row in document.get("skipped_rows", [])[:200]],
    )


MEMBERSHIP_SCAN_DIR = GENERATED_REPORTS_DIR / "membership_scans"
MEMBERSHIP_SCAN_DIR.mkdir(parents=True, exist_ok=True)

SCANNED_FORM_FIELD_LABELS = {
    "governorate": ["المحافظة", "محافظه"],
    "union_committee": ["اللجنة النقابية", "اللجنه النقابيه", "اللجنة", "اللجنه"],
    "membership_number": ["رقم العضوية", "رقم العضويه", "رقم العضو", "عضوية"],
    "name": ["الاسم", "اسم العضو", "اسم المشترك"],
    "national_id": ["الرقم القومي", "الررقم القومي", "رقم البطاقة", "رقم البطاقه", "الرقم القومى"],
    "birth_date": ["تاريخ الميلاد", "الميلاد", "تاريخ ميلاد"],
    "address": ["العنوان", "محل الاقامة والتليفون", "محل الإقامة والتليفون", "محل الاقامة", "محل الإقامة"],
    "death_beneficiary": ["في حالة الوفاة", "مستلم الاعانة", "مستلم الإعانة", "المستفيد"],
}


def scanner_normalized_text(value: str) -> str:
    text = normalize_member_text(value)
    replacements = {"أ": "ا", "إ": "ا", "آ": "ا", "ة": "ه", "ى": "ي", "ؤ": "و", "ئ": "ي", "ـ": ""}
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text


def scanner_pdf_url(membership_id: str) -> str:
    return f"/api/memberships/{membership_id}/scan-pdf"


def scan_line_value(line: str, labels: List[str]) -> Optional[str]:
    raw_line = normalize_member_text(line)
    normalized_line = scanner_normalized_text(raw_line)
    for label in sorted(labels, key=len, reverse=True):
        normalized_label = scanner_normalized_text(label)
        if normalized_label and normalized_label in normalized_line:
            value = raw_line
            for candidate in [label, scanner_normalized_text(label)]:
                value = re.sub(re.escape(candidate), " ", value, flags=re.IGNORECASE)
            value = re.sub(r"^[\s:：\-–—/\\]+", "", value).strip()
            value = re.sub(r"^(بيان|البيان)\s*", "", value).strip()
            return normalize_member_text(value) or None
    return None


def extracted_labeled_value(lines: List[str], field_name: str) -> Optional[str]:
    labels = SCANNED_FORM_FIELD_LABELS[field_name]
    for index, line in enumerate(lines):
        value = scan_line_value(line, labels)
        if value:
            return value
        if any(scanner_normalized_text(label) in scanner_normalized_text(line) for label in labels):
            for next_line in lines[index + 1:index + 4]:
                next_value = normalize_member_text(next_line)
                if next_value and not any(scanner_normalized_text(item) in scanner_normalized_text(next_value) for values in SCANNED_FORM_FIELD_LABELS.values() for item in values):
                    return next_value
    return None


def birth_date_from_national_id(national_id: str) -> Optional[date]:
    digits = normalize_digit_text(national_id)
    if len(digits) != 14 or digits[0] not in {"2", "3"}:
        return None
    year = (1900 if digits[0] == "2" else 2000) + int(digits[1:3])
    month = int(digits[3:5])
    day = int(digits[5:7])
    try:
        return date(year, month, day)
    except ValueError:
        return None


def parse_scanned_membership_text(raw_text: str) -> dict:
    text = normalize_digit_text(raw_text or "")
    lines = [normalize_member_text(line) for line in re.split(r"[\r\n]+", text) if normalize_member_text(line)]
    payload = {field_name: extracted_labeled_value(lines, field_name) for field_name in SCANNED_FORM_FIELD_LABELS}
    national_match = re.search(r"\b\d{14}\b", text)
    if national_match:
        payload["national_id"] = national_match.group(0)
    payload["national_id"] = normalize_digit_text(payload.get("national_id") or "")
    payload["membership_number"] = normalize_digit_text(payload.get("membership_number") or "")
    if not payload.get("birth_date") and payload.get("national_id"):
        inferred_birth = birth_date_from_national_id(payload["national_id"])
        if inferred_birth:
            payload["birth_date"] = serialize_date(inferred_birth)
    birth_value = parse_import_date(payload.get("birth_date") or "")
    required = ["governorate", "union_committee", "membership_number", "name", "national_id", "birth_date", "address"]
    missing = [field for field in required if not payload.get(field)]
    if missing:
        labels = {"governorate": "المحافظة", "union_committee": "اللجنة النقابية", "membership_number": "رقم العضوية", "name": "الاسم", "national_id": "الرقم القومي", "birth_date": "تاريخ الميلاد", "address": "العنوان"}
        raise HTTPException(status_code=400, detail=f"تعذر قراءة الحقول التالية من الاستمارة: {', '.join(labels[item] for item in missing)}")
    return {
        "governorate": normalize_member_text(payload["governorate"]),
        "union_committee": normalize_member_text(payload["union_committee"]),
        "membership_number": payload["membership_number"],
        "name": normalize_member_text(payload["name"]),
        "national_id": payload["national_id"],
        "birth_date": birth_value,
        "address": normalize_member_text(payload["address"]),
        "death_beneficiary": normalize_member_text(payload.get("death_beneficiary") or "غير محدد"),
        "status": "active",
        "status_effective_date": date.today(),
    }


def tesseract_executable_path() -> Optional[str]:
    bundled = ROOT_DIR.parent / "tesseract" / "tesseract.exe"
    if bundled.exists():
        return str(bundled)
    found = shutil.which("tesseract")
    if found:
        return found
    for env_name in ["ProgramFiles", "ProgramFiles(x86)"]:
        base = os.environ.get(env_name)
        if not base:
            continue
        candidate = Path(base) / "Tesseract-OCR" / "tesseract.exe"
        if candidate.exists():
            return str(candidate)
    return None


def run_tesseract_ocr(image_paths: List[Path]) -> Optional[str]:
    executable = tesseract_executable_path()
    if not executable:
        return None
    parts = []
    for image_path in image_paths:
        result = subprocess.run([executable, str(image_path), "stdout", "-l", "ara+eng", "--psm", "6"], capture_output=True, text=True, timeout=90, check=False)
        if result.stdout:
            parts.append(result.stdout)
    return "\n".join(parts).strip() or None


def run_windows_ocr(image_paths: List[Path]) -> Optional[str]:
    if os.name != "nt" or not image_paths:
        return None
    output_path = Path(tempfile.mkdtemp(prefix="membership_ocr_")) / "ocr.txt"
    quoted_images = ",".join([f"'{str(path).replace(chr(39), chr(39) + chr(39))}'" for path in image_paths])
    script = f"""
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType=WindowsRuntime]
$null = [Windows.Globalization.Language, Windows.Foundation, ContentType=WindowsRuntime]
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType=WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType=WindowsRuntime]
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {{ $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' }})[0]
function Await($operation, $type) {{ $asTask = $asTaskGeneric.MakeGenericMethod($type); $task = $asTask.Invoke($null, @($operation)); $task.Wait() | Out-Null; return $task.Result }}
$lang = New-Object Windows.Globalization.Language 'ar'
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($lang)
if ($null -eq $engine) {{ $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages() }}
if ($null -eq $engine) {{ exit 3 }}
$texts = New-Object System.Collections.Generic.List[string]
foreach ($imagePath in @({quoted_images})) {{
  try {{
    $file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($imagePath)) ([Windows.Storage.StorageFile])
    $stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
    $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
    $bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
    $result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
    $texts.Add($result.Text) | Out-Null
    $stream.Dispose()
  }} catch {{ }}
}}
Set-Content -LiteralPath '{str(output_path).replace(chr(39), chr(39) + chr(39))}' -Value ($texts -join "`n") -Encoding UTF8
"""
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script], capture_output=True, text=True, timeout=120, check=False)
    if output_path.exists():
        return output_path.read_text(encoding="utf-8", errors="ignore").strip() or None
    return None


def create_pdf_from_images(image_paths: List[Path], pdf_path: Path) -> None:
    if not image_paths:
        raise HTTPException(status_code=400, detail="لم ينتج الماسح أي صفحات")
    images = []
    for image_path in image_paths:
        images.append(Image.open(image_path).convert("RGB"))
    first, rest = images[0], images[1:]
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    first.save(pdf_path, "PDF", resolution=300.0, save_all=True, append_images=rest)
    for image in images:
        image.close()


def scanned_upload_to_pdf(content: bytes, filename: str, output_dir: Path) -> tuple[Path, List[Path], str]:
    suffix = Path(filename or "").suffix.lower()
    output_dir.mkdir(parents=True, exist_ok=True)
    if suffix == ".pdf":
        pdf_path = output_dir / "membership-form.pdf"
        pdf_path.write_bytes(content)
        return pdf_path, [], "pdf"
    if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}:
        raise HTTPException(status_code=400, detail="ارفع PDF أو صورة للاستمارة فقط")
    image_path = output_dir / f"page-001{suffix}"
    image_path.write_bytes(content)
    pdf_path = output_dir / "membership-form.pdf"
    create_pdf_from_images([image_path], pdf_path)
    return pdf_path, [image_path], "image"


def extract_text_from_pdf_if_possible(pdf_path: Path) -> Optional[str]:
    try:
        reader = PdfReader(str(pdf_path))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        return normalize_member_text(text) or None
    except Exception:
        return None


def run_wia_adf_scan(output_dir: Path, device_index: int, dpi: int, max_pages: int) -> List[Path]:
    if os.name != "nt":
        raise HTTPException(status_code=501, detail="المسح الضوئي المباشر يعمل من نسخة Windows المحلية فقط")
    output_dir.mkdir(parents=True, exist_ok=True)
    script_path = output_dir / "scan-adf.ps1"
    script_path.write_text(r'''
param([int]$DeviceIndex = 1, [string]$OutputPath, [int]$DPI = 300, [int]$MaxPages = 10)
$ErrorActionPreference = "Stop"
$deviceManager = New-Object -ComObject WIA.DeviceManager
if ($deviceManager.DeviceInfos.Count -lt $DeviceIndex) { throw "لم يتم العثور على ماسح ضوئي WIA" }
$deviceInfo = $deviceManager.DeviceInfos.Item($DeviceIndex)
$device = $deviceInfo.Connect()
$FEEDER = 1
$PNG = "{B96B3CAF-0728-11D3-9D7B-0000F81EF32E}"
function SetProp($target, [int]$id, $value) { try { $target.Properties.Item($id).Value = $value } catch {} }
New-Item -ItemType Directory -Force -Path $OutputPath | Out-Null
$count = 0
while ($count -lt $MaxPages) {
  try {
    $item = $device.Items.Item(1)
    SetProp $item 6146 $DPI
    SetProp $item 6147 $DPI
    SetProp $item 4103 24
    SetProp $device 3087 $FEEDER
    $image = $item.Transfer($PNG)
    $count++
    $filePath = Join-Path $OutputPath ("page-{0:D3}.png" -f $count)
    if (Test-Path $filePath) { Remove-Item $filePath -Force }
    $image.SaveFile($filePath)
  } catch {
    if ($count -eq 0) { throw }
    break
  }
}
Write-Output $count
''', encoding="utf-8")
    result = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script_path), "-DeviceIndex", str(device_index), "-OutputPath", str(output_dir), "-DPI", str(dpi), "-MaxPages", str(max_pages)], capture_output=True, text=True, timeout=max(90, max_pages * 45), check=False)
    if result.returncode != 0:
        detail = normalize_member_text(result.stderr or result.stdout or "تعذر تنفيذ أمر الماسح الضوئي")
        raise HTTPException(status_code=500, detail=detail[:500])
    return sorted(output_dir.glob("page-*.png"))


async def create_membership_from_scanned_form(raw_text: str, pdf_path: Path, page_count: int, source_type: str, ocr_engine: str, current_user: dict) -> MembershipScanImportResponse:
    extracted_payload = parse_scanned_membership_text(raw_text)
    payload = MembershipCreate(**extracted_payload)
    document = await membership_document_from_payload(payload)
    membership_id = str(uuid.uuid4())
    now_iso = serialize_datetime(datetime.now(timezone.utc))
    attachment_id = str(uuid.uuid4())
    final_dir = MEMBERSHIP_SCAN_DIR / membership_id
    final_dir.mkdir(parents=True, exist_ok=True)
    final_pdf_path = final_dir / "membership-form.pdf"
    if pdf_path.resolve() != final_pdf_path.resolve():
        shutil.copy2(pdf_path, final_pdf_path)
    document.update({"id": membership_id, "created_at": now_iso, "updated_at": now_iso})
    document["scan_attachment"] = {
        "id": attachment_id,
        "file_name": "membership-form.pdf",
        "pdf_path": str(final_pdf_path),
        "pdf_url": scanner_pdf_url(membership_id),
        "source_type": source_type,
        "page_count": page_count,
        "ocr_engine": ocr_engine,
        "scanned_at": now_iso,
        "extracted_text_preview": (raw_text or "")[:1000],
        "created_by": current_user.get("username"),
    }
    await db.memberships.insert_one(document.copy())
    return MembershipScanImportResponse(
        member=MembershipResponse(**hydrate_membership(document)),
        extracted_fields={key: (serialize_date(value) if isinstance(value, date) else str(value or "")) for key, value in extracted_payload.items()},
        pdf_url=scanner_pdf_url(membership_id),
        page_count=page_count,
        ocr_engine=ocr_engine,
        source_type=source_type,
    )


async def depreciation_total_for_asset(asset_id: str) -> float:
    documents = await db.fixed_asset_depreciations.find(with_organization({"asset_id": asset_id}), {"_id": 0, "amount": 1}).to_list(1000)
    return round(sum(float(item.get("amount") or 0) for item in documents), 2)


async def enrich_fixed_asset(document: dict) -> dict:
    clean = {key: value for key, value in document.items() if key != "_id"}
    if isinstance(clean.get("purchase_date"), str):
        clean["purchase_date"] = date.fromisoformat(clean["purchase_date"])
    for field_name in ["created_at", "updated_at"]:
        if isinstance(clean.get(field_name), str):
            clean[field_name] = datetime.fromisoformat(clean[field_name])
    category = fixed_asset_category(clean.get("category_code"))
    clean["category_name"] = category["name"]
    clean["annual_depreciation_rate"] = float(clean.get("annual_depreciation_rate") or category["annual_depreciation_rate"])
    clean["monthly_depreciation"] = fixed_asset_monthly_depreciation(clean.get("purchase_cost"), clean["annual_depreciation_rate"])
    clean["disposal_date"] = fixed_asset_disposal_date(clean["purchase_date"], clean.get("purchase_cost"), clean["annual_depreciation_rate"])
    clean["accumulated_depreciation"] = await depreciation_total_for_asset(clean["id"])
    clean["net_book_value"] = round(max(float(clean.get("purchase_cost") or 0) - clean["accumulated_depreciation"], 0), 2)
    last_depreciation = await db.fixed_asset_depreciations.find_one(with_organization({"asset_id": clean["id"]}), {"_id": 0}, sort=[("year", -1), ("month", -1)])
    clean["last_depreciation_period"] = f"{last_depreciation.get('month')}/{last_depreciation.get('year')}" if last_depreciation else None
    return clean


def hydrate_fixed_asset_depreciation(document: dict) -> dict:
    clean = {key: value for key, value in document.items() if key != "_id"}
    if isinstance(clean.get("depreciation_date"), str):
        clean["depreciation_date"] = date.fromisoformat(clean["depreciation_date"])
    for field_name in ["created_at", "updated_at"]:
        if isinstance(clean.get(field_name), str):
            clean[field_name] = datetime.fromisoformat(clean[field_name])
    return clean


def hydrate_membership(document: dict) -> dict:
    clean = {key: value for key, value in document.items() if key != "_id"}
    clean.setdefault("status", "active")
    clean["status_label"] = MEMBERSHIP_STATUS_LABELS.get(clean.get("status"), "فعال")
    clean.setdefault("monthly_subscription_amount", MEMBERSHIP_MONTHLY_SUBSCRIPTION)
    clean.setdefault("current_due", 0)
    clean.setdefault("total_collected", 0)
    clean.setdefault("remaining_balance", 0)
    if not clean.get("subscription_start_date"):
        created_value = clean.get("created_at")
        if isinstance(created_value, str):
            try:
                created_value = datetime.fromisoformat(created_value)
            except ValueError:
                created_value = None
        clean["subscription_start_date"] = serialize_date(created_value.date() if isinstance(created_value, datetime) else date.today())
    for field_name in ["birth_date", "retirement_date", "status_effective_date", "subscription_start_date", "subscription_stop_date"]:
        if isinstance(clean.get(field_name), str):
            clean[field_name] = date.fromisoformat(clean[field_name])
    for field_name in ["created_at", "updated_at"]:
        if isinstance(clean.get(field_name), str):
            clean[field_name] = datetime.fromisoformat(clean[field_name])
    return clean


MEMBERSHIP_MONTHLY_SUBSCRIPTION = 3.0
MEMBERSHIP_STATUS_LABELS = {
    "active": "فعال",
    "retired": "معاش",
    "deceased": "متوفي",
    "resigned": "مستقيل",
}
NON_ACTIVE_MEMBERSHIP_STATUSES = {"retired", "deceased", "resigned"}


def first_day_of_month(value: date) -> date:
    return date(value.year, value.month, 1)


def parse_date_field(value, fallback: Optional[date] = None) -> Optional[date]:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str) and value:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return fallback
    return fallback


def iter_month_keys(start_date: date, end_date: date) -> List[str]:
    if end_date < start_date:
        return []
    cursor = first_day_of_month(start_date)
    final = first_day_of_month(end_date)
    keys = []
    while cursor <= final:
        keys.append(f"{cursor.year}-{cursor.month:02d}")
        cursor = date(cursor.year + (1 if cursor.month == 12 else 0), 1 if cursor.month == 12 else cursor.month + 1, 1)
    return keys


def membership_subscription_cutoff(member: dict, as_of_date: date) -> date:
    status = member.get("status") or "active"
    if status in NON_ACTIVE_MEMBERSHIP_STATUSES:
        stop_date = parse_date_field(member.get("subscription_stop_date")) or parse_date_field(member.get("status_effective_date")) or parse_date_field(member.get("updated_at"), as_of_date) or as_of_date
        return min(stop_date, as_of_date)
    return as_of_date


def membership_due_periods(member: dict, as_of_date: date, paid_periods: Optional[dict[str, float]] = None) -> List[dict]:
    paid_periods = paid_periods or {}
    start_date = parse_date_field(member.get("subscription_start_date")) or parse_date_field(member.get("created_at"), as_of_date) or as_of_date
    cutoff = membership_subscription_cutoff(member, as_of_date)
    periods = []
    for period_key in iter_month_keys(start_date, cutoff):
        paid = round(float(paid_periods.get(period_key, 0) or 0), 2)
        remaining = round(max(MEMBERSHIP_MONTHLY_SUBSCRIPTION - paid, 0), 2)
        if remaining > 0:
            periods.append({"period": period_key, "amount": remaining})
    return periods


async def membership_paid_allocations_map(as_of_date: Optional[date] = None) -> dict[str, dict[str, float]]:
    query = with_organization({"is_reversal": {"$ne": True}, "status": "approved"})
    if as_of_date:
        query["payment_date"] = {"$lte": as_of_date.isoformat()}
    documents = await db.membership_batch_payments.find(query, {"_id": 0, "allocations": 1}).to_list(100000)
    paid: dict[str, dict[str, float]] = {}
    for document in documents:
        for allocation in document.get("allocations", []):
            member_id = allocation.get("member_id")
            period = allocation.get("period")
            if not member_id or not period:
                continue
            paid.setdefault(member_id, {})[period] = round(paid.setdefault(member_id, {}).get(period, 0) + float(allocation.get("amount") or 0), 2)
    return paid


async def enrich_membership_financials(document: dict, as_of_date: Optional[date] = None, paid_map: Optional[dict[str, dict[str, float]]] = None) -> dict:
    as_of = as_of_date or date.today()
    paid_map = paid_map if paid_map is not None else await membership_paid_allocations_map(as_of)
    clean = {key: value for key, value in document.items() if key != "_id"}
    member_paid = paid_map.get(clean.get("id"), {})
    periods_due = membership_due_periods(clean, as_of, member_paid)
    total_due = round(len(iter_month_keys(parse_date_field(clean.get("subscription_start_date")) or parse_date_field(clean.get("created_at"), as_of) or as_of, membership_subscription_cutoff(clean, as_of))) * MEMBERSHIP_MONTHLY_SUBSCRIPTION, 2)
    total_collected = round(sum(float(value or 0) for value in member_paid.values()), 2)
    clean["current_due"] = total_due
    clean["total_collected"] = total_collected
    clean["remaining_balance"] = round(sum(item["amount"] for item in periods_due), 2)
    clean["monthly_subscription_amount"] = MEMBERSHIP_MONTHLY_SUBSCRIPTION
    return clean


def hydrate_membership_batch_payment(document: dict) -> dict:
    clean = {key: value for key, value in document.items() if key != "_id"}
    if isinstance(clean.get("payment_date"), str):
        clean["payment_date"] = date.fromisoformat(clean["payment_date"])
    for field_name in ["created_at", "updated_at"]:
        if isinstance(clean.get(field_name), str):
            clean[field_name] = datetime.fromisoformat(clean[field_name])
    return clean


def default_chart_accounts_for_banks(banks: List[dict]) -> List[dict]:
    base_accounts = [
        {"code": "1000", "name": "الأصول", "account_type": "asset", "nature": "debit", "is_postable": False, "system_key": "assets"},
        {"code": "1100", "name": "البنوك", "account_type": "asset", "nature": "debit", "is_postable": False, "parent_code": "1000", "system_key": "banks"},
        {"code": "1150", "name": "الخزينة", "account_type": "asset", "nature": "debit", "is_postable": True, "parent_code": "1000", "system_key": "cash_box"},
        {"code": "1200", "name": "شيكات تحت التحصيل", "account_type": "asset", "nature": "debit", "is_postable": True, "parent_code": "1000", "system_key": "checks_under_collection"},
        {"code": "1250", "name": "ودائع لأجل", "account_type": "asset", "nature": "debit", "is_postable": True, "parent_code": "1000", "system_key": "term_deposits"},
        {"code": "1300", "name": "عوائد ودائع مستحقة", "account_type": "asset", "nature": "debit", "is_postable": True, "parent_code": "1000", "system_key": "accrued_deposit_interest"},
        {"code": "1400", "name": "الأصول الثابتة", "account_type": "asset", "nature": "debit", "is_postable": False, "parent_code": "1000", "system_key": "fixed_assets_parent"},
        {"code": "1490", "name": "مجمع إهلاك الأصول الثابتة", "account_type": "asset", "nature": "credit", "is_postable": False, "parent_code": "1000", "system_key": "accumulated_depreciation_parent"},
        {"code": "1500", "name": "العهد والسلف", "account_type": "asset", "nature": "debit", "is_postable": True, "parent_code": "1000", "system_key": "custody_advances"},
        {"code": "1600", "name": "مديونية اشتراكات العضوية", "account_type": "asset", "nature": "debit", "is_postable": True, "parent_code": "1000", "system_key": "membership_subscription_receivable"},
        {"code": "1700", "name": "المخزون", "account_type": "asset", "nature": "debit", "is_postable": True, "parent_code": "1000", "system_key": "inventory_asset"},
        {"code": "2000", "name": "الالتزامات", "account_type": "liability", "nature": "credit", "is_postable": False, "system_key": "liabilities"},
        {"code": "2100", "name": "شيكات صادرة", "account_type": "liability", "nature": "credit", "is_postable": True, "parent_code": "2000", "system_key": "issued_checks"},
        {"code": "2200", "name": "دائنون متنوعون", "account_type": "liability", "nature": "credit", "is_postable": True, "parent_code": "2000", "system_key": "misc_creditors"},
        {"code": "3000", "name": "حقوق الملكية / الفائض", "account_type": "equity", "nature": "credit", "is_postable": False, "system_key": "equity"},
        {"code": "3100", "name": "رصيد افتتاحي", "account_type": "equity", "nature": "credit", "is_postable": True, "parent_code": "3000", "system_key": "opening_balance_equity"},
        {"code": "4000", "name": "الإيرادات", "account_type": "revenue", "nature": "credit", "is_postable": False, "system_key": "revenues"},
        {"code": "4101", "name": "الإيرادات", "account_type": "revenue", "nature": "credit", "is_postable": True, "parent_code": "4000", "system_key": "revenue_general"},
        {"code": "4102", "name": "إيرادات فوائد ودائع", "account_type": "revenue", "nature": "credit", "is_postable": True, "parent_code": "4000", "system_key": "deposit_interest_revenue"},
        {"code": "4103", "name": "إيرادات اشتراكات العضوية", "account_type": "revenue", "nature": "credit", "is_postable": True, "parent_code": "4000", "system_key": "membership_subscription_revenue"},
        {"code": "4104", "name": "إيرادات فوائد الحساب الجاري", "account_type": "revenue", "nature": "credit", "is_postable": True, "parent_code": "4000", "system_key": "current_account_interest_revenue"},
        {"code": "4105", "name": "إيرادات أوامر الدفع", "account_type": "revenue", "nature": "credit", "is_postable": True, "parent_code": "4000", "system_key": "payment_order_revenue"},
        {"code": "5000", "name": "المصروفات", "account_type": "expense", "nature": "debit", "is_postable": False, "system_key": "expenses"},
        {"code": "5101", "name": "المصروفات", "account_type": "expense", "nature": "debit", "is_postable": True, "parent_code": "5000", "system_key": "expense_general"},
        {"code": "5102", "name": "المصروفات البنكية", "account_type": "expense", "nature": "debit", "is_postable": True, "parent_code": "5000", "system_key": "bank_expenses"},
        {"code": "5103", "name": "تسوية العهد والسلف", "account_type": "expense", "nature": "debit", "is_postable": True, "parent_code": "5000", "system_key": "custody_advance_expense"},
        {"code": "5104", "name": "منصرف مخزون", "account_type": "expense", "nature": "debit", "is_postable": True, "parent_code": "5000", "system_key": "inventory_issue_expense"},
        {"code": "5200", "name": "إهلاك الأصول الثابتة", "account_type": "expense", "nature": "debit", "is_postable": False, "parent_code": "5000", "system_key": "depreciation_expense_parent"},
    ]
    for category in FIXED_ASSET_CATEGORIES:
        base_accounts.append({"code": category["code"], "name": category["name"], "account_type": "asset", "nature": "debit", "is_postable": True, "parent_code": "1400", "system_key": f"fixed_asset:{category['code']}"})
        base_accounts.append({"code": f"{category['code']}-م", "name": f"مجمع إهلاك {category['name']}", "account_type": "asset", "nature": "credit", "is_postable": True, "parent_code": "1490", "system_key": f"accumulated_depreciation:{category['code']}"})
        base_accounts.append({"code": f"52{category['code']}", "name": f"إهلاك {category['name']}", "account_type": "expense", "nature": "debit", "is_postable": True, "parent_code": "5200", "system_key": f"depreciation_expense:{category['code']}"})
    for index, bank in enumerate(banks, start=1):
        base_accounts.append({"code": f"11{index:02d}", "name": bank["name"], "account_type": "asset", "nature": "debit", "is_postable": True, "parent_code": "1100", "system_key": f"bank:{bank['id']}", "bank_id": bank["id"]})
    return base_accounts


async def sync_chart_accounts_for_organization(organization_id: str) -> List[dict]:
    token = CURRENT_ORGANIZATION_ID.set(organization_id)
    try:
        banks = await get_all_banks()
    finally:
        CURRENT_ORGANIZATION_ID.reset(token)
    now_iso = serialize_datetime(datetime.now(timezone.utc))
    existing = await db.chart_accounts.find({"organization_id": organization_id}, {"_id": 0}).to_list(2000)
    by_code = {account["code"]: account for account in existing}
    by_system = {account.get("system_key"): account for account in existing if account.get("system_key")}
    created_or_updated = []
    for account in default_chart_accounts_for_banks(banks):
        parent = by_code.get(account.get("parent_code")) if account.get("parent_code") else None
        system_key = account.get("system_key")
        current = by_system.get(system_key) or by_code.get(account["code"])
        document = {
            "organization_id": organization_id,
            "code": account["code"],
            "name": account["name"],
            "account_type": account["account_type"],
            "nature": account["nature"],
            "parent_id": parent.get("id") if parent else None,
            "parent_code": parent.get("code") if parent else None,
            "parent_name": parent.get("name") if parent else None,
            "level": 2 if parent else 1,
            "is_postable": bool(account.get("is_postable", True)),
            "is_active": True,
            "opening_balance": float(current.get("opening_balance", 0) if current else 0),
            "system_key": system_key,
            "bank_id": account.get("bank_id"),
            "updated_at": now_iso,
        }
        if current:
            await db.chart_accounts.update_one({"id": current["id"], "organization_id": organization_id}, {"$set": document})
            document = {**current, **document}
        else:
            document.update({"id": str(uuid.uuid4()), "created_at": now_iso})
            await db.chart_accounts.insert_one(document.copy())
            by_code[document["code"]] = document
            if system_key:
                by_system[system_key] = document
        created_or_updated.append(document)
    return created_or_updated


async def account_for_system_key(system_key: str, fallback_name: str) -> dict:
    organization_id = organization_id_or_default()
    account = await db.chart_accounts.find_one(with_organization({"system_key": system_key, "is_active": True}, organization_id), {"_id": 0})
    if not account:
        await sync_chart_accounts_for_organization(organization_id)
        account = await db.chart_accounts.find_one(with_organization({"system_key": system_key, "is_active": True}, organization_id), {"_id": 0})
    return account or {"id": None, "code": None, "name": fallback_name, "account_type": None}


async def resolve_journal_account(line: dict) -> dict:
    account_name = str(line.get("account_name") or "").strip()
    bank_id = line.get("bank_id")
    if account_name == "البنك" and not bank_id:
        active_banks = await get_all_banks()
        bank_id = active_banks[0].get("id") if active_banks else None
        if bank_id:
            line["bank_id"] = bank_id
    system_key_map = {
        "البنك": f"bank:{bank_id}" if bank_id else "banks",
        "الإيرادات": "revenue_general",
        "المصروفات": "expense_general",
        "المصروفات البنكية": "bank_expenses",
        "ودائع لأجل": "term_deposits",
        "شيكات تحت التحصيل": "checks_under_collection",
        "شيكات صادرة": "issued_checks",
        "عوائد ودائع مستحقة": "accrued_deposit_interest",
        "إيرادات فوائد ودائع": "deposit_interest_revenue",
        "إيرادات أوامر الدفع": "payment_order_revenue",
        "رصيد افتتاحي": "opening_balance_equity",
        "الخزينة": "cash_box",
        "مديونية اشتراكات العضوية": "membership_subscription_receivable",
        "المخزون": "inventory_asset",
        "دائنون متنوعون": "misc_creditors",
        "منصرف مخزون": "inventory_issue_expense",
        "إيرادات اشتراكات العضوية": "membership_subscription_revenue",
        "إيرادات الاشتراكات": "membership_subscription_revenue",
    }
    system_key = line.get("system_key") or system_key_map.get(account_name)
    account = await account_for_system_key(system_key, account_name) if system_key else await db.chart_accounts.find_one(with_organization({"name": account_name, "is_active": True, "is_postable": True}), {"_id": 0})
    if account:
        line["account_id"] = account.get("id")
        line["account_code"] = account.get("code")
        line["account_name"] = account.get("name") or account_name
        line["account_type"] = account.get("account_type")
    return line


async def repair_journal_account_links_for_organization(organization_id: str, return_details: bool = False):
    entries = await db.journal_entries.find(with_organization({}, organization_id), {"_id": 0}).to_list(100000)
    repaired_count = 0
    repair_details = []
    token = CURRENT_ORGANIZATION_ID.set(organization_id)
    try:
        for entry in entries:
            changed = False
            repaired_lines = []
            for line_index, line in enumerate(entry.get("lines", []), start=1):
                if line.get("account_id") and line.get("account_code") and line.get("account_type"):
                    repaired_lines.append(line)
                    continue
                repaired_line = await resolve_journal_account(line.copy())
                if repaired_line != line:
                    changed = True
                    if return_details:
                        entry_date_value = entry.get("entry_date")
                        try:
                            parsed_entry_date = date.fromisoformat(entry_date_value) if isinstance(entry_date_value, str) else entry_date_value
                        except ValueError:
                            parsed_entry_date = None
                        repair_details.append({
                            "entry_id": entry.get("id"),
                            "entry_number": entry.get("entry_number"),
                            "entry_date": parsed_entry_date,
                            "description": entry.get("description"),
                            "line_index": line_index,
                            "before_account_name": line.get("account_name"),
                            "before_account_code": line.get("account_code"),
                            "after_account_name": repaired_line.get("account_name"),
                            "after_account_code": repaired_line.get("account_code"),
                            "after_account_type": repaired_line.get("account_type"),
                        })
                repaired_lines.append(repaired_line)
            if changed:
                await db.journal_entries.update_one(with_organization({"id": entry["id"]}, organization_id), {"$set": {"lines": repaired_lines, "updated_at": serialize_datetime(datetime.now(timezone.utc))}})
                repaired_count += 1
    finally:
        CURRENT_ORGANIZATION_ID.reset(token)
    if return_details:
        return repair_details
    return repaired_count


async def normalize_journal_lines(lines: List[dict]) -> tuple[List[dict], float, float]:
    normalized = []
    for line in lines:
        account_name = str(line.get("account_name") or "").strip()
        debit = round(float(line.get("debit") or 0), 2)
        credit = round(float(line.get("credit") or 0), 2)
        if not account_name or (debit <= 0 and credit <= 0):
            continue
        if debit > 0 and credit > 0:
            raise HTTPException(status_code=400, detail="كل سطر في القيد يجب أن يكون مدين أو دائن فقط")
        normalized.append(await resolve_journal_account({"account_name": account_name, "bank_id": line.get("bank_id"), "system_key": line.get("system_key"), "debit": debit, "credit": credit, "notes": line.get("notes")}))
    total_debit = round(sum(line["debit"] for line in normalized), 2)
    total_credit = round(sum(line["credit"] for line in normalized), 2)
    if len(normalized) < 2 or total_debit <= 0 or total_debit != total_credit:
        raise HTTPException(status_code=422, detail="تم منع الترحيل: القيد غير متوازن، ولا يسمح النظام بترحيل ناقص.")
    return normalized, total_debit, total_credit


async def next_journal_entry_number(organization_id: str) -> int:
    counter = await db.journal_counters.find_one_and_update(
        {"organization_id": organization_id},
        {"$inc": {"next_number": 1}, "$setOnInsert": {"organization_id": organization_id}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return int(counter.get("next_number", 1))


async def save_journal_entry_document(*, entry_date: date, description: str, lines: List[dict], reference: Optional[str], source_type: str, source_id: Optional[str], is_auto: bool, current_user: Optional[dict] = None, force_new: bool = False) -> dict:
    organization_id = organization_id_or_default()
    for line in lines:
        await ensure_bank_transaction_date_allowed(line.get("bank_id"), entry_date)
    normalized_lines, total_debit, total_credit = await normalize_journal_lines(lines)
    if round(total_debit, 2) != round(total_credit, 2):
        raise HTTPException(status_code=422, detail="تم منع الترحيل: القيد غير متوازن، ولا يسمح النظام بترحيل ناقص.")
    now_iso = serialize_datetime(datetime.now(timezone.utc))
    query = with_organization({"source_type": source_type, "source_id": source_id, "is_reversal": {"$ne": True}, "reversal_entry_id": {"$exists": False}}, organization_id) if source_id and not force_new else None
    existing = await db.journal_entries.find_one(query, {"_id": 0}) if query else None
    entry_number = int(existing["entry_number"]) if existing else await next_journal_entry_number(organization_id)
    document = {
        "id": existing.get("id") if existing else str(uuid.uuid4()),
        "organization_id": organization_id,
        "entry_number": entry_number,
        "entry_date": entry_date.isoformat(),
        "description": description.strip(),
        "reference": reference,
        "source_type": source_type,
        "source_id": source_id,
        "status": "approved",
        "is_auto": is_auto,
        "is_reversal": existing.get("is_reversal", False) if existing else False,
        "lines": normalized_lines,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "created_by": existing.get("created_by") if existing else (current_user or {}).get("id"),
        "created_by_name": existing.get("created_by_name") if existing else (real_name_for_user(current_user or {}) if current_user else None),
        "created_at": existing.get("created_at") if existing else now_iso,
        "updated_at": now_iso,
    }
    await db.journal_entries.update_one(with_organization({"id": document["id"]}, organization_id), {"$set": document}, upsert=True)
    return document


async def create_reverse_journal_entry(original: dict, reason: str = "إلغاء/حذف عملية مرحلة", current_user: Optional[dict] = None) -> Optional[dict]:
    if not original or original.get("is_reversal") or original.get("reversal_entry_id"):
        return None
    reversed_lines = []
    for line in original.get("lines", []):
        reversed_line = line.copy()
        reversed_line["debit"] = round(float(line.get("credit") or 0), 2)
        reversed_line["credit"] = round(float(line.get("debit") or 0), 2)
        reversed_line["notes"] = f"قيد عكسي للقيد رقم {original.get('entry_number')} - {reason}"
        reversed_lines.append(reversed_line)
    document = await save_journal_entry_document(
        entry_date=datetime.now(timezone.utc).date(),
        description=f"قيد عكسي: {original.get('description') or '-'}",
        reference=f"REV-{original.get('entry_number')}",
        source_type=original.get("source_type") or "manual",
        source_id=original.get("source_id") or original.get("id"),
        is_auto=True,
        current_user=current_user,
        lines=reversed_lines,
        force_new=True,
    )
    await db.journal_entries.update_one(with_organization({"id": document["id"]}), {"$set": {"is_reversal": True, "reversal_of_entry_id": original.get("id"), "reversal_reason": reason}})
    await db.journal_entries.update_one(with_organization({"id": original.get("id")}), {"$set": {"reversal_entry_id": document["id"], "reversal_reason": reason, "reversed_at": serialize_datetime(datetime.now(timezone.utc)), "updated_at": serialize_datetime(datetime.now(timezone.utc))}})
    return document


async def reverse_journal_for_source(source_type: str, source_id: str, reason: str = "إلغاء/حذف عملية مرحلة", current_user: Optional[dict] = None):
    # الحذف النهائي (Option C): يُزال القيد الأصلي وأي قيد عكسي سابق لنفس المصدر نهائياً،
    # بدلاً من إنشاء قيد عكسي، لضمان اختفاء العملية المحذوفة من جميع التقارير بشكل صحيح.
    await db.journal_entries.delete_many(with_organization({"source_type": source_type, "source_id": source_id}))


async def delete_journal_for_source(source_type: str, source_id: str):
    await reverse_journal_for_source(source_type, source_id)


REPORT_EXCLUDED_SOURCE_TYPES = ["deposit_interest"]
REVENUE_DIRECT_BANK_METHODS = {"current_account_interest", "deposit_maturity"}
REVENUE_RULE_ACCOUNT_MAP = {
    "payment_order": {"account_name": "إيرادات أوامر الدفع", "system_key": "payment_order_revenue", "analysis_type": "أمر دفع"},
    "deposit_maturity": {"account_name": "إيرادات فوائد ودائع", "system_key": "deposit_interest_revenue", "analysis_type": "استحقاق وديعة"},
    "current_account_interest": {"account_name": "إيرادات فوائد الحساب الجاري", "system_key": "current_account_interest_revenue", "analysis_type": "فوائد الحساب الجاري"},
}
EXPENSE_RULE_ACCOUNT_MAP = {
    "general_expenses": {"account_name": "المصروفات", "system_key": "expense_general", "analysis_type": "مصروفات عمومية"},
    "death_benefits": {"account_name": "المصروفات", "system_key": "expense_general", "analysis_type": "إعانات وفاة"},
    "deposit_link": {"account_name": "ودائع لأجل", "system_key": "term_deposits", "analysis_type": "ربط وديعة"},
}


def default_accounting_rules(organization_id: str) -> List[dict]:
    now_iso = serialize_datetime(datetime.now(timezone.utc))
    defaults = [
        ("rule-income-bank", "Income", "General", "bank_transfer", "البنك", "الإيرادات", "إيراد عادي محصل بالبنك"),
        ("rule-income-payment-order", "Income", "PaymentOrder", "payment_order", "البنك", "إيرادات أوامر الدفع", "تحصيل إيراد مستقل بأمر دفع"),
        ("rule-expense-general", "Expense", "General", "bank_transfer", "المصروفات", "البنك", "مصروف عادي مدفوع من البنك"),
        ("rule-bank-fee", "BankFee", "banking", "bank_transfer", "المصروفات البنكية", "البنك", "عمولة أو مصروف بنكي"),
        ("rule-deposit", "Deposit", "Principal", "bank_transfer", "ودائع لأجل", "البنك", "ربط وديعة لأجل"),
        ("rule-interest-accrued", "Interest", "Accrued", None, "عوائد ودائع مستحقة", "إيرادات فوائد ودائع", "فائدة مستحقة غير محصلة"),
        ("rule-interest-received", "Interest", "Received", "bank_transfer", "البنك", "عوائد ودائع مستحقة", "تحصيل فائدة سبق إثباتها"),
        ("rule-opening-balance", "OpeningBalance", "Bank", None, "البنك", "رصيد افتتاحي", "إثبات الرصيد الافتتاحي للبنك"),
        ("rule-membership-batch-payment", "MembershipBatchPayment", "Committee", "bank_transfer", "البنك", "إيرادات اشتراكات العضوية", "تحصيل اشتراكات عضوية من لجنة نقابية"),
        ("rule-asset-depreciation", "AssetDepreciation", "Annual", None, "إهلاك الأصول الثابتة", "مجمع إهلاك الأصول الثابتة", "إهلاك سنوي تلقائي للأصول"),
        ("rule-loan", "Loan", "Employee Loan", "bank_transfer", "سلف الموظفين", "البنك", "صرف سلفة موظف"),
        ("rule-custody", "Custody", "Employee Custody", "bank_transfer", "عهد الموظفين", "البنك", "صرف عهدة موظف"),
    ]
    return [{
        "id": rule_id,
        "organization_id": organization_id,
        "event_type": event_type,
        "sub_type": sub_type,
        "payment_method": payment_method,
        "debit_account": debit,
        "credit_account": credit,
        "priority": calculate_rule_priority({"event_type": event_type, "sub_type": sub_type, "payment_method": payment_method, "debit_account": debit, "credit_account": credit}),
        "is_active": True,
        "is_system": True,
        "notes": notes,
        "created_at": now_iso,
        "updated_at": now_iso,
    } for rule_id, event_type, sub_type, payment_method, debit, credit, notes in defaults]


def calculate_rule_priority(rule_data: dict) -> int:
    specificity_score = 0
    if rule_data.get("event_type"):
        specificity_score += 1
    if rule_data.get("sub_type"):
        specificity_score += 2
    if rule_data.get("payment_method"):
        specificity_score += 2
    if rule_data.get("debit_account"):
        specificity_score += 1
    if rule_data.get("credit_account"):
        specificity_score += 1
    return max(1, min(10, 10 - specificity_score))


async def list_accounting_rules_for_organization(organization_id: str) -> List[dict]:
    custom_rules = await db.accounting_rules.find(with_organization({}, organization_id), {"_id": 0}).to_list(1000)
    custom_by_id = {item["id"]: item for item in custom_rules}
    merged = []
    for default in default_accounting_rules(organization_id):
        merged.append({**default, **custom_by_id.pop(default["id"], {})})
    merged.extend(custom_by_id.values())
    return sorted(merged, key=lambda item: (int(item.get("priority", 5)), item.get("event_type", ""), item.get("sub_type") or ""))


def rule_matches(rule: dict, payload: RuleSimulationRequest) -> bool:
    if not rule.get("is_active", True):
        return False
    if rule.get("event_type") != payload.event_type:
        return False
    if rule.get("sub_type") and normalize_arabic_key(rule.get("sub_type")) != normalize_arabic_key(payload.sub_type):
        return False
    if rule.get("payment_method") and normalize_arabic_key(rule.get("payment_method")) != normalize_arabic_key(payload.payment_method):
        return False
    return True


async def simulate_accounting_rule(payload: RuleSimulationRequest) -> RuleSimulationResponse:
    organization_id = organization_id_or_default()
    await sync_chart_accounts_for_organization(organization_id)
    rules = await list_accounting_rules_for_organization(organization_id)
    matches = [rule for rule in rules if rule_matches(rule, payload)]
    errors = []
    if not matches:
        return RuleSimulationResponse(is_valid=False, errors=["لا توجد قاعدة مطابقة؛ سيتم منع الترحيل حسب Fail-Safe Layer."])
    selected = sorted(matches, key=lambda item: int(item.get("priority", 5)))[0]
    conflict_rules = [rule for rule in matches if rule.get("id") != selected.get("id") and int(rule.get("priority", 5)) == int(selected.get("priority", 5))]
    raw_lines = [
        {"account_name": selected.get("debit_account"), "bank_id": payload.bank_id, "debit": round(payload.amount, 2), "credit": 0, "notes": "Simulation Mode - لا يوجد ترحيل"},
        {"account_name": selected.get("credit_account"), "bank_id": payload.bank_id, "debit": 0, "credit": round(payload.amount, 2), "notes": "Simulation Mode - لا يوجد ترحيل"},
    ]
    try:
        normalized, total_debit, total_credit = await normalize_journal_lines(raw_lines)
    except HTTPException as exc:
        return RuleSimulationResponse(matched_rule=AccountingRuleResponse(**selected), conflicts=[AccountingRuleResponse(**item) for item in conflict_rules], is_valid=False, errors=[str(exc.detail)], simulation_only=True)
    if round(total_debit, 2) != round(total_credit, 2):
        errors.append("القيد غير متوازن؛ تم منع الترحيل.")
    if conflict_rules:
        errors.append("يوجد تعارض قواعد بنفس الأولوية؛ راجع Conflict detection قبل التفعيل.")
    return RuleSimulationResponse(
        matched_rule=AccountingRuleResponse(**selected),
        conflicts=[AccountingRuleResponse(**item) for item in conflict_rules],
        preview_lines=[JournalLine(**line) for line in normalized],
        is_valid=not errors,
        errors=errors,
        total_debit=total_debit,
        total_credit=total_credit,
        simulation_only=True,
    )


async def journal_for_deposit_principal(deposit: dict, current_user: Optional[dict] = None):
    amount = round(float(deposit.get("amount") or 0), 2)
    if amount <= 0:
        return
    created_value = deposit.get("creation_datetime")
    entry_date = created_value.date() if isinstance(created_value, datetime) else datetime.fromisoformat(str(created_value)).date()
    if deposit.get("is_opening_balance_deposit"):
        accounting_start = deposit.get("accounting_start_datetime")
        entry_date = accounting_start.date() if isinstance(accounting_start, datetime) else datetime.fromisoformat(str(accounting_start)).date()
        lines = [
            {"account_name": "ودائع لأجل", "system_key": "term_deposits", "debit": amount, "credit": 0, "notes": "وديعة قائمة أول الفترة: إثبات أصل وديعة بدون حركة بنك تاريخية"},
            {"account_name": "رصيد افتتاحي", "system_key": "opening_balance_equity", "debit": 0, "credit": amount, "notes": "القيد المقابل لوديعة قائمة عند بداية الفترة"},
        ]
    else:
        lines = [
            {"account_name": "ودائع لأجل", "system_key": "term_deposits", "debit": amount, "credit": 0, "notes": "محرك القواعد: DepositEvent"},
            {"account_name": "البنك", "bank_id": deposit.get("bank_id"), "debit": 0, "credit": amount, "notes": "محرك القواعد: DepositEvent"},
        ]
    await save_journal_entry_document(
        entry_date=entry_date,
        description=f"قيد تلقائي {'لرصيد افتتاحي وديعة قائمة' if deposit.get('is_opening_balance_deposit') else 'لربط وديعة'} رقم {deposit.get('deposit_number')}",
        reference=deposit.get("deposit_number"),
        source_type="deposit",
        source_id=deposit.get("id"),
        is_auto=True,
        current_user=current_user,
        lines=lines,
    )


async def journal_for_revenue(revenue: dict, current_user: Optional[dict] = None):
    amount = round(float(revenue.get("amount") or 0), 2)
    if amount <= 0:
        return
    debit_account = "البنك" if (revenue.get("bank_collection_status") or "under_collection") == "collected" else "شيكات تحت التحصيل"
    revenue_rule = REVENUE_RULE_ACCOUNT_MAP.get(revenue.get("collection_method") or "", {"account_name": "الإيرادات", "system_key": "revenue_general", "analysis_type": "إيراد عام"})
    await save_journal_entry_document(
        entry_date=revenue.get("issued_at") if isinstance(revenue.get("issued_at"), date) else date.fromisoformat(str(revenue.get("issued_at") or revenue.get("dated"))),
        description=f"قيد تلقائي لإيراد رقم {revenue.get('receipt_number')}",
        reference=revenue.get("receipt_number"),
        source_type="revenue",
        source_id=revenue.get("id"),
        is_auto=True,
        current_user=current_user,
        lines=[
            {"account_name": debit_account, "bank_id": revenue.get("bank_id"), "debit": amount, "credit": 0, "notes": f"تحصيل: {revenue_rule['analysis_type']}"},
            {"account_name": revenue_rule["account_name"], "system_key": revenue_rule["system_key"], "debit": 0, "credit": amount, "notes": f"تحليل: {revenue_rule['analysis_type']}"},
        ],
    )


async def reclassify_revenue_journal_lines_for_organization(organization_id: str):
    revenue_methods = list(REVENUE_RULE_ACCOUNT_MAP.keys())
    revenues = await db.revenues.find(with_organization({"collection_method": {"$in": revenue_methods}}, organization_id), {"_id": 0, "id": 1, "collection_method": 1}).to_list(100000)
    if not revenues:
        return
    account_cache = {}
    for rule in REVENUE_RULE_ACCOUNT_MAP.values():
        if rule["system_key"] not in account_cache:
            account_cache[rule["system_key"]] = await db.chart_accounts.find_one(with_organization({"system_key": rule["system_key"], "is_active": True}, organization_id), {"_id": 0})
    for revenue in revenues:
        rule = REVENUE_RULE_ACCOUNT_MAP.get(revenue.get("collection_method"))
        account = account_cache.get(rule["system_key"]) if rule else None
        if not account:
            continue
        entry = await db.journal_entries.find_one(with_organization({"source_type": "revenue", "source_id": revenue.get("id"), "is_reversal": {"$ne": True}}, organization_id), {"_id": 0})
        if not entry:
            continue
        changed = False
        lines = []
        for line in entry.get("lines", []):
            next_line = dict(line)
            if float(next_line.get("credit") or 0) > 0 and next_line.get("account_type") == "revenue" and next_line.get("account_id") != account.get("id"):
                next_line.update({
                    "account_id": account.get("id"),
                    "account_code": account.get("code"),
                    "account_name": account.get("name"),
                    "account_type": account.get("account_type"),
                })
                changed = True
            lines.append(next_line)
        if changed:
            await db.journal_entries.update_one(with_organization({"id": entry.get("id")}, organization_id), {"$set": {"lines": lines, "updated_at": serialize_datetime(datetime.now(timezone.utc))}})


def hydrate_inventory_item(document: dict) -> dict:
    clean = {key: value for key, value in document.items() if key != "_id"}
    for field_name in ["created_at", "updated_at"]:
        if isinstance(clean.get(field_name), str):
            clean[field_name] = datetime.fromisoformat(clean[field_name])
    return clean


def hydrate_inventory_movement(document: dict) -> dict:
    clean = {key: value for key, value in document.items() if key != "_id"}
    for field_name in ["created_at", "updated_at"]:
        if isinstance(clean.get(field_name), str):
            clean[field_name] = datetime.fromisoformat(clean[field_name])
    if isinstance(clean.get("movement_date"), str):
        clean["movement_date"] = date.fromisoformat(clean["movement_date"])
    return clean


def hydrate_misc_creditor(document: dict) -> dict:
    clean = {key: value for key, value in document.items() if key != "_id"}
    for field_name in ["created_at", "updated_at"]:
        if isinstance(clean.get(field_name), str):
            clean[field_name] = datetime.fromisoformat(clean[field_name])
    return clean


def hydrate_misc_creditor_movement(document: dict) -> dict:
    clean = {key: value for key, value in document.items() if key != "_id"}
    for field_name in ["created_at", "updated_at"]:
        if isinstance(clean.get(field_name), str):
            clean[field_name] = datetime.fromisoformat(clean[field_name])
    if isinstance(clean.get("movement_date"), str):
        clean["movement_date"] = date.fromisoformat(clean["movement_date"])
    return clean


async def ensure_inventory_item_from_payload(payload: InventoryMovementCreate) -> dict:
    if payload.item_id:
        item = await db.inventory_items.find_one(with_organization({"id": payload.item_id}), {"_id": 0})
        if not item:
            raise HTTPException(status_code=404, detail="الصنف غير موجود")
        return item
    if not payload.item_name:
        raise HTTPException(status_code=400, detail="يجب اختيار صنف أو إدخال اسم صنف جديد")
    code = (payload.item_code or payload.item_name).strip()
    existing = await db.inventory_items.find_one(with_organization({"item_code": code}), {"_id": 0})
    if existing:
        return existing
    now_iso = serialize_datetime(datetime.now(timezone.utc))
    document = attach_organization({
        "id": str(uuid.uuid4()),
        "item_code": code,
        "item_name": payload.item_name.strip(),
        "unit": (payload.unit or "وحدة").strip(),
        "quantity_balance": 0.0,
        "value_balance": 0.0,
        "average_cost": 0.0,
        "created_at": now_iso,
        "updated_at": now_iso,
    })
    await db.inventory_items.insert_one(document.copy())
    return document


async def journal_for_inventory_movement(movement: dict, current_user: Optional[dict] = None):
    amount = round(float(movement.get("total_value") or 0), 2)
    if amount <= 0:
        return None
    if movement.get("movement_type") == "in":
        lines = [
            {"account_name": "المخزون", "system_key": "inventory_asset", "debit": amount, "credit": 0, "notes": movement.get("item_name")},
            {"account_name": "دائنون متنوعون", "system_key": "misc_creditors", "debit": 0, "credit": amount, "notes": "إثبات وارد مخزون"},
        ]
    else:
        lines = [
            {"account_name": "منصرف مخزون", "system_key": "inventory_issue_expense", "debit": amount, "credit": 0, "notes": movement.get("item_name")},
            {"account_name": "المخزون", "system_key": "inventory_asset", "debit": 0, "credit": amount, "notes": "صرف مخزون"},
        ]
    return await save_journal_entry_document(
        entry_date=movement.get("movement_date") if isinstance(movement.get("movement_date"), date) else date.fromisoformat(str(movement.get("movement_date"))),
        description=f"قيد تلقائي لحركة مخزون: {movement.get('description')}",
        reference=movement.get("reference") or movement.get("id"),
        source_type="inventory",
        source_id=movement.get("id"),
        is_auto=True,
        current_user=current_user,
        lines=lines,
        force_new=True,
    )


async def ensure_misc_creditor_from_payload(payload: MiscCreditorMovementCreate) -> dict:
    if payload.creditor_id:
        creditor = await db.misc_creditors.find_one(with_organization({"id": payload.creditor_id}), {"_id": 0})
        if not creditor:
            raise HTTPException(status_code=404, detail="الدائن غير موجود")
        return creditor
    if not payload.creditor_name:
        raise HTTPException(status_code=400, detail="يجب اختيار دائن أو إدخال اسم دائن جديد")
    existing = await db.misc_creditors.find_one(with_organization({"creditor_name": payload.creditor_name.strip()}), {"_id": 0})
    if existing:
        return existing
    now_iso = serialize_datetime(datetime.now(timezone.utc))
    document = attach_organization({
        "id": str(uuid.uuid4()),
        "creditor_code": None,
        "creditor_name": payload.creditor_name.strip(),
        "notes": None,
        "balance": 0.0,
        "created_at": now_iso,
        "updated_at": now_iso,
    })
    await db.misc_creditors.insert_one(document.copy())
    return document


async def journal_for_misc_creditor_movement(movement: dict, current_user: Optional[dict] = None):
    amount = round(float(movement.get("amount") or 0), 2)
    if movement.get("movement_type") == "obligation":
        lines = [
            {"account_name": "المصروفات", "system_key": "expense_general", "debit": amount, "credit": 0, "notes": movement.get("creditor_name")},
            {"account_name": "دائنون متنوعون", "system_key": "misc_creditors", "debit": 0, "credit": amount, "notes": "إثبات التزام"},
        ]
    else:
        if not movement.get("bank_id"):
            raise HTTPException(status_code=400, detail="يجب اختيار البنك عند سداد دائن")
        lines = [
            {"account_name": "دائنون متنوعون", "system_key": "misc_creditors", "debit": amount, "credit": 0, "notes": movement.get("creditor_name")},
            {"account_name": "البنك", "bank_id": movement.get("bank_id"), "debit": 0, "credit": amount, "notes": "سداد دائن متنوع"},
        ]
    return await save_journal_entry_document(
        entry_date=movement.get("movement_date") if isinstance(movement.get("movement_date"), date) else date.fromisoformat(str(movement.get("movement_date"))),
        description=f"قيد تلقائي لدائن متنوع: {movement.get('description')}",
        reference=movement.get("reference") or movement.get("id"),
        source_type="misc_creditor",
        source_id=movement.get("id"),
        is_auto=True,
        current_user=current_user,
        lines=lines,
        force_new=True,
    )


async def journal_for_expense(expense: dict, current_user: Optional[dict] = None):
    amount = round(float(expense.get("net_amount") or expense.get("total_amount") or 0), 2)
    if amount <= 0:
        return
    credit_account = "البنك" if (expense.get("bank_payment_status") or "not_presented") == "paid" else "شيكات صادرة"
    expense_rule = EXPENSE_RULE_ACCOUNT_MAP.get(expense.get("expense_category") or "general_expenses", EXPENSE_RULE_ACCOUNT_MAP["general_expenses"])
    await save_journal_entry_document(
        entry_date=expense.get("issued_at") if isinstance(expense.get("issued_at"), date) else date.fromisoformat(str(expense.get("issued_at"))),
        description=f"قيد تلقائي لمصروف رقم {expense.get('expense_number')}",
        reference=expense.get("expense_number"),
        source_type="expense",
        source_id=expense.get("id"),
        is_auto=True,
        current_user=current_user,
        lines=[
            {"account_name": expense_rule["account_name"], "system_key": expense_rule["system_key"], "debit": amount, "credit": 0, "notes": f"تحليل: {expense_rule['analysis_type']} | مركز تكلفة: {expense.get('organization_scope') or organization_id_or_default()}"},
            {"account_name": credit_account, "bank_id": expense.get("bank_id"), "debit": 0, "credit": amount, "notes": "محرك القواعد: ExpenseEvent"},
        ],
    )


async def journal_for_banking_expense(document: dict, current_user: Optional[dict] = None):
    total = round(sum(float(item.get("total") if item.get("total") is not None else float(item.get("count") or 1) * float(item.get("amount") or 0)) for item in document.get("items", [])), 2)
    source_id = f"{document.get('bank_id')}-{document.get('year')}-{document.get('month')}"
    if total <= 0:
        await delete_journal_for_source("banking_expense", source_id)
        return
    await save_journal_entry_document(
        entry_date=date(int(document["year"]), int(document["month"]), 1),
        description=f"قيد تلقائي لمصروفات بنكية {document.get('bank_name')} {document.get('month')}/{document.get('year')}",
        reference=f"{document.get('year')}/{str(document.get('month')).zfill(2)}",
        source_type="banking_expense",
        source_id=source_id,
        is_auto=True,
        current_user=current_user,
        lines=[{"account_name": "المصروفات البنكية", "debit": total, "credit": 0}, {"account_name": "البنك", "bank_id": document.get("bank_id"), "debit": 0, "credit": total}],
    )


async def journal_for_deposit_interest(deposit: dict, current_user: Optional[dict] = None):
    if deposit.get("id"):
        await reverse_journal_for_source("deposit_interest", deposit.get("id"), "إيقاف الترحيل الآلي لفوائد الودائع؛ تُسجل فقط عند اختيار استحقاق وديعة", current_user)


async def calculate_bank_book_balance(bank_id: str, as_of_date: Optional[date] = None) -> float:
    organization_id = organization_id_or_default()
    await sync_chart_accounts_for_organization(organization_id)
    account = await db.chart_accounts.find_one(with_organization({"system_key": f"bank:{bank_id}", "is_active": True}, organization_id), {"_id": 0})
    if not account:
        return 0.0
    query = with_organization({"status": "approved"}, organization_id)
    if as_of_date:
        query["entry_date"] = {"$lte": as_of_date.isoformat()}
    query["is_reversal"] = {"$ne": True}
    entries = await db.journal_entries.find(query, {"_id": 0, "lines": 1}).to_list(100000)
    balance = round(float(account.get("opening_balance") or 0), 2)
    for entry in entries:
        for line in entry.get("lines", []):
            if line.get("account_id") != account.get("id") and line.get("account_code") != account.get("code"):
                continue
            balance = round(balance + float(line.get("debit") or 0) - float(line.get("credit") or 0), 2)
    return balance


async def calculate_bank_period_opening_balance(bank_id: str, period_from: date) -> float:
    organization_id = organization_id_or_default()
    bank = await ensure_bank_async(bank_id)
    base = round(float(bank.get("opening_balance") or 0), 2)
    opening_date_value = bank.get("opening_balance_date")
    if isinstance(opening_date_value, datetime):
        opening_date = opening_date_value.date()
    elif isinstance(opening_date_value, date):
        opening_date = opening_date_value
    elif isinstance(opening_date_value, str) and opening_date_value:
        try:
            opening_date = date.fromisoformat(opening_date_value[:10])
        except ValueError:
            opening_date = date.min
    else:
        opening_date = date.min
    if period_from <= opening_date:
        return base
    prior_from = opening_date
    prior_to = period_from - timedelta(days=1)
    date_filter = {"$gte": prior_from.isoformat(), "$lte": prior_to.isoformat()}
    revenue_documents = await db.revenues.find(with_organization({"bank_id": bank_id, "issued_at": date_filter}, organization_id), {"_id": 0, "amount": 1}).to_list(100000)
    prior_revenues = round(sum(float(item.get("amount") or 0) for item in revenue_documents), 2)
    prior_interest = await reconciliation_deposit_interest_for_period(organization_id, prior_from, prior_to, bank_id=bank_id)
    expense_documents = await db.expenses.find(with_organization({"bank_id": bank_id, "issued_at": date_filter}, organization_id), {"_id": 0, "net_amount": 1, "gross_amount": 1}).to_list(100000)
    prior_expenses = round(sum(float(item.get("net_amount") if item.get("net_amount") is not None else item.get("gross_amount") or 0) for item in expense_documents), 2)
    charge_documents = await db.banking_manual_charges.find(with_organization({"bank_id": bank_id}, organization_id), {"_id": 0}).to_list(100000)
    prior_charges = 0.0
    for charge in charge_documents:
        try:
            charge_month = date(int(charge.get("year")), int(charge.get("month")), 1)
        except (TypeError, ValueError):
            continue
        if prior_from <= charge_month <= prior_to:
            prior_charges = round(prior_charges + sum_manual_charge_items(charge), 2)
    return round(base + prior_revenues + prior_interest - prior_expenses - prior_charges, 2)


ARABIC_MONTH_NAME_TO_NUMBER = {
    "يناير": 1,
    "فبراير": 2,
    "مارس": 3,
    "أبريل": 4,
    "ابريل": 4,
    "مايو": 5,
    "يونيو": 6,
    "يوليو": 7,
    "أغسطس": 8,
    "اغسطس": 8,
    "سبتمبر": 9,
    "أكتوبر": 10,
    "اكتوبر": 10,
    "نوفمبر": 11,
    "ديسمبر": 12,
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def month_bounds(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    end = date(year + (1 if month == 12 else 0), 1 if month == 12 else month + 1, 1) - timedelta(days=1)
    return start, end


def reconciliation_period_bounds(period_label: Optional[str] = None, year: Optional[int] = None, month: Optional[int] = None, as_of_date: Optional[date] = None) -> tuple[date, date]:
    if year and month:
        return month_bounds(int(year), int(month))
    label = normalize_digit_text(period_label or "").strip().lower()
    year_match = re.search(r"(19\d{2}|20\d{2}|21\d{2})", label)
    detected_year = int(year_match.group(1)) if year_match else None
    detected_month = None
    numeric_match = re.search(r"(?:^|\D)(1[0-2]|0?[1-9])(?:\D|$)", label)
    if numeric_match:
        detected_month = int(numeric_match.group(1))
    for name, value in ARABIC_MONTH_NAME_TO_NUMBER.items():
        if name in label:
            detected_month = value
            break
    target = as_of_date or date.today()
    return month_bounds(detected_year or target.year, detected_month or target.month)


def sum_manual_charge_items(document: Optional[dict]) -> float:
    if not document:
        return 0.0
    return round(sum(float(item.get("total") if item.get("total") is not None else float(item.get("count") or 1) * float(item.get("amount") or 0)) for item in document.get("items", [])), 2)


async def calculate_bank_reconciliation_balance_breakdown(bank_id: str, period_label: Optional[str] = None, year: Optional[int] = None, month: Optional[int] = None, as_of_date: Optional[date] = None) -> BankReconciliationBalanceBreakdown:
    await ensure_bank_async(bank_id)
    period_from, period_to = reconciliation_period_bounds(period_label, year, month, as_of_date)
    organization_id = organization_id_or_default()
    opening_balance = await calculate_bank_period_opening_balance(bank_id, period_from)
    period_filter = {"$gte": period_from.isoformat(), "$lte": period_to.isoformat()}
    revenue_query = with_organization({"bank_id": bank_id, "issued_at": period_filter}, organization_id)
    revenues = await db.revenues.find(revenue_query, {"_id": 0, "amount": 1}).to_list(100000)
    monthly_revenues = round(sum(float(item.get("amount") or 0) for item in revenues), 2)
    monthly_deposit_interest = await reconciliation_deposit_interest_for_period(organization_id, period_from, period_to, bank_id=bank_id)
    deposit_settlements = monthly_deposit_interest
    collection_query = with_organization({"bank_id": bank_id, "collection_method": "check", "bank_collection_status": "under_collection", "issued_at": {"$gte": period_from.isoformat(), "$lte": period_to.isoformat()}}, organization_id)
    collection_checks = await db.revenues.find(collection_query, {"_id": 0, "amount": 1}).to_list(100000)
    checks_under_collection = round(sum(float(item.get("amount") or 0) for item in collection_checks), 2)
    expense_query = with_organization({"bank_id": bank_id, "issued_at": {"$gte": period_from.isoformat(), "$lte": period_to.isoformat()}}, organization_id)
    expenses = await db.expenses.find(expense_query, {"_id": 0, "net_amount": 1, "gross_amount": 1}).to_list(100000)
    monthly_expenses = round(sum(float(item.get("net_amount") if item.get("net_amount") is not None else item.get("gross_amount") or 0) for item in expenses), 2)
    outstanding_query = with_organization({"bank_id": bank_id, "payment_method": "check", "bank_payment_status": "not_presented", "issued_at": {"$gte": period_from.isoformat(), "$lte": period_to.isoformat()}}, organization_id)
    outstanding_checks = await db.expenses.find(outstanding_query, {"_id": 0, "net_amount": 1, "gross_amount": 1}).to_list(100000)
    checks_not_presented = round(sum(float(item.get("net_amount") if item.get("net_amount") is not None else item.get("gross_amount") or 0) for item in outstanding_checks), 2)
    manual_charges = await db.banking_manual_charges.find_one(with_organization({"bank_id": bank_id, "year": period_from.year, "month": period_from.month}, organization_id), {"_id": 0})
    bank_expenses = sum_manual_charge_items(manual_charges)
    total_receipts = round(monthly_revenues + monthly_deposit_interest, 2)
    total_payments = round(bank_expenses + monthly_expenses, 2)
    gross_total = round(opening_balance + total_receipts, 2)
    book_balance = round(gross_total - total_payments, 2)
    reconciliation_balance = round(book_balance + checks_not_presented - checks_under_collection, 2)
    return BankReconciliationBalanceBreakdown(
        bank_id=bank_id,
        period_from=period_from,
        period_to=period_to,
        opening_balance=opening_balance,
        monthly_revenues=monthly_revenues,
        monthly_deposit_interest=monthly_deposit_interest,
        total_receipts=total_receipts,
        deposit_settlements=deposit_settlements,
        checks_under_collection=checks_under_collection,
        gross_total=gross_total,
        book_balance=book_balance,
        monthly_expenses=monthly_expenses,
        checks_not_presented=checks_not_presented,
        bank_expenses=bank_expenses,
        total_payments=total_payments,
        reconciliation_balance=reconciliation_balance,
    )


BANQUE_MISR_EXTERNAL_SOURCE_URL = "https://www.banquemisr.ae/#tab-2"


def clean_external_html_text(value: Optional[str]) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", value or ""))
    return re.sub(r"\s+", " ", text).strip()


def absolute_external_url(value: Optional[str], base_url: str = BANQUE_MISR_EXTERNAL_SOURCE_URL) -> Optional[str]:
    if not value:
        return None
    return urllib.parse.urljoin(base_url, value)


def fetch_external_html(url: str) -> str:
    last_error = None
    for timeout_seconds in [12, 25]:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 BankDepositSystem/1.0; ReadOnlyBankPrints",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                content_type = response.headers.get("Content-Type", "")
                charset_match = re.search(r"charset=([^;]+)", content_type, re.I)
                charset = charset_match.group(1).strip() if charset_match else "utf-8"
                return response.read().decode(charset, errors="ignore")
        except Exception as exc:
            last_error = exc
    raise HTTPException(status_code=502, detail=f"تعذر جلب بيانات بنك مصر من المصدر الخارجي بعد إعادة المحاولة: {last_error}")


def extract_banque_misr_rows(raw_html: str) -> List[dict]:
    rows: List[dict] = []
    seen = set()
    for match in re.finditer(r'<div class="slick-slide"\s+title="([^"]+)">.*?<h6[^>]*>([^<]+)</h6>.*?<label>BUY</label>\s*<b>([^<]+)</b>.*?<label>SELL</label>\s*<b>([^<]+)</b>', raw_html, re.I | re.S):
        title, currency, buy, sell = [clean_external_html_text(item) for item in match.groups()]
        key = f"fx-{currency}"
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            "id": key.lower(),
            "section": "أسعار العملات",
            "title": title,
            "description": "سعر شراء وبيع لحظي ظاهر في صفحة بنك مصر الخارجية",
            "currency": currency,
            "buy": buy,
            "sell": sell,
            "url": "https://www.banquemisr.ae/personal-banking/remittances/#fx-rates",
        })
    for match in re.finditer(r'<h1[^>]*>(.*?)</h1>\s*<a[^>]+href="([^"]+)"[^>]*>\s*Learn More\s*</a>', raw_html, re.I | re.S):
        title = clean_external_html_text(match.group(1))
        url = absolute_external_url(html.unescape(match.group(2)))
        key = f"product-{normalize_arabic_key(title)}"
        if not title or key in seen:
            continue
        seen.add(key)
        rows.append({
            "id": hashlib.sha256(key.encode("utf-8")).hexdigest()[:16],
            "section": "منتجات وخدمات",
            "title": title,
            "description": "منتج أو خدمة ظاهرة في واجهة بنك مصر الخارجية",
            "currency": None,
            "buy": None,
            "sell": None,
            "url": url,
        })
    for match in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>.*?<span class="font-weight-bold">(.*?)</span>.*?<div class="exeption"[^>]*>\s*<p>(.*?)</p>', raw_html, re.I | re.S):
        url = absolute_external_url(html.unescape(match.group(1)))
        title = clean_external_html_text(match.group(2))
        description = clean_external_html_text(match.group(3))
        key = f"service-{normalize_arabic_key(title)}"
        if not title or key in seen:
            continue
        seen.add(key)
        rows.append({
            "id": hashlib.sha256(key.encode("utf-8")).hexdigest()[:16],
            "section": "خدمات مصرفية",
            "title": title,
            "description": description,
            "currency": None,
            "buy": None,
            "sell": None,
            "url": url,
        })
    return rows


def fetch_banque_misr_external_data() -> BankPrintExternalData:
    raw_html = fetch_external_html(BANQUE_MISR_EXTERNAL_SOURCE_URL)
    rows = extract_banque_misr_rows(raw_html)
    checksum_payload = json.dumps(rows, ensure_ascii=False, sort_keys=True)
    return BankPrintExternalData(
        bank_id="banque-misr",
        bank_name="بنك مصر",
        source_url=BANQUE_MISR_EXTERNAL_SOURCE_URL,
        fetched_at=datetime.now(timezone.utc),
        status="OK" if rows else "NO_DATA",
        checksum=hashlib.sha256(checksum_payload.encode("utf-8")).hexdigest(),
        rows=[BankPrintExternalRow(**row) for row in rows],
    )


def hydrate_bank_print_request(document: dict) -> dict:
    clean = {key: value for key, value in document.items() if key != "_id"}
    for field_name in ["created_at", "updated_at", "printed_at"]:
        if isinstance(clean.get(field_name), str):
            clean[field_name] = datetime.fromisoformat(clean[field_name])
    external_data = clean.get("external_data") or {}
    if isinstance(external_data.get("fetched_at"), str):
        external_data["fetched_at"] = datetime.fromisoformat(external_data["fetched_at"])
    manual_inputs = clean.get("manual_inputs") or {}
    for date_field in ["period_from", "period_to"]:
        if isinstance(manual_inputs.get(date_field), str) and manual_inputs.get(date_field):
            manual_inputs[date_field] = date.fromisoformat(manual_inputs[date_field])
    clean["external_data"] = external_data
    clean["manual_inputs"] = manual_inputs
    return clean


async def journal_for_bank_opening_balance(bank: dict, opening_balance: float, current_user: Optional[dict] = None):
    amount = round(float(opening_balance or 0), 2)
    bank_id = bank.get("id")
    opening_balance_date = parse_date_field(bank.get("opening_balance_date")) or date.today()
    if not bank_id:
        return
    if amount == 0:
        await reverse_journal_for_source("opening_balance", bank_id, "تصفير الرصيد الافتتاحي للبنك", current_user)
        return
    debit_bank = amount > 0
    absolute_amount = abs(amount)
    lines = [
        {"account_name": "البنك", "bank_id": bank_id, "debit": absolute_amount if debit_bank else 0, "credit": 0 if debit_bank else absolute_amount, "notes": "محرك القواعد: رصيد افتتاحي للبنك"},
        {"account_name": "رصيد افتتاحي", "system_key": "opening_balance_equity", "debit": 0 if debit_bank else absolute_amount, "credit": absolute_amount if debit_bank else 0, "notes": "القيد المقابل للرصيد الافتتاحي"},
    ]
    await save_journal_entry_document(
        entry_date=opening_balance_date,
        description=f"قيد تلقائي للرصيد الافتتاحي - {bank.get('name') or bank_id}",
        reference=f"OB-{bank_id}",
        source_type="opening_balance",
        source_id=bank_id,
        is_auto=True,
        current_user=current_user,
        lines=lines,
    )


async def journal_for_reconciliation(document: dict, current_user: Optional[dict] = None):
    difference = round(abs(float(document.get("difference") or 0)), 2)
    if difference <= 0:
        await delete_journal_for_source("reconciliation", document.get("id"))
        return
    lines = [{"account_name": "المصروفات", "debit": difference, "credit": 0}, {"account_name": "البنك", "bank_id": document.get("bank_id"), "debit": 0, "credit": difference}] if float(document.get("difference") or 0) > 0 else [{"account_name": "البنك", "bank_id": document.get("bank_id"), "debit": difference, "credit": 0}, {"account_name": "الإيرادات", "debit": 0, "credit": difference}]
    await save_journal_entry_document(
        entry_date=datetime.fromisoformat(document.get("created_at")).date(),
        description=f"قيد تلقائي لفروق تسوية بنكية {document.get('period_label') or ''}".strip(),
        reference=document.get("period_label") or document.get("id"),
        source_type="reconciliation",
        source_id=document.get("id"),
        is_auto=True,
        current_user=current_user,
        lines=lines,
    )


async def journal_for_membership_batch_payment(document: dict, current_user: Optional[dict] = None):
    amount = round(float(document.get("amount") or 0), 2)
    if amount <= 0:
        return
    payment_value = document.get("payment_date")
    entry_date = payment_value if isinstance(payment_value, date) else date.fromisoformat(str(payment_value))
    await save_journal_entry_document(
        entry_date=entry_date,
        description=f"قيد تلقائي لتحصيل اشتراكات لجنة {document.get('union_committee')}",
        reference=document.get("receipt_number") or document.get("id"),
        source_type="membership_batch_payment",
        source_id=document.get("id"),
        is_auto=True,
        current_user=current_user,
        lines=[
            {"account_name": "البنك", "bank_id": document.get("bank_id"), "debit": amount, "credit": 0, "notes": "محرك القواعد: إذن جماعي للجان"},
            {"account_name": "إيرادات اشتراكات العضوية", "system_key": "membership_subscription_revenue", "debit": 0, "credit": amount, "notes": "تحصيل اشتراكات أعضاء مشروع التكافل"},
        ],
    )


async def journal_for_fixed_asset(asset: dict, current_user: Optional[dict] = None):
    amount = round(float(asset.get("purchase_cost") or 0), 2)
    if amount <= 0:
        return
    category = fixed_asset_category(asset.get("category_code"))
    purchase_value = asset.get("purchase_date")
    entry_date = purchase_value if isinstance(purchase_value, date) else date.fromisoformat(str(purchase_value))
    await save_journal_entry_document(
        entry_date=entry_date,
        description=f"قيد تلقائي لإثبات أصل ثابت: {asset.get('asset_name')}",
        reference=asset.get("asset_code") or asset.get("invoice_number"),
        source_type="fixed_asset",
        source_id=asset.get("id"),
        is_auto=True,
        current_user=current_user,
        lines=[
            {"account_name": category["name"], "system_key": f"fixed_asset:{category['code']}", "debit": amount, "credit": 0},
            {"account_name": "البنك", "bank_id": asset.get("bank_id"), "debit": 0, "credit": amount},
        ],
    )


async def journal_for_asset_depreciation(depreciation: dict, current_user: Optional[dict] = None):
    amount = round(float(depreciation.get("amount") or 0), 2)
    if amount <= 0:
        return
    category = fixed_asset_category(depreciation.get("category_code"))
    depreciation_date_value = depreciation.get("depreciation_date")
    entry_date = depreciation_date_value if isinstance(depreciation_date_value, date) else date.fromisoformat(str(depreciation_date_value))
    await save_journal_entry_document(
        entry_date=entry_date,
        description=f"قيد تلقائي للإهلاك السنوي {depreciation.get('asset_name')} عن سنة {depreciation.get('year')}",
        reference=depreciation.get("asset_code"),
        source_type="asset_depreciation",
        source_id=depreciation.get("id"),
        is_auto=True,
        current_user=current_user,
        lines=[
            {"account_name": f"إهلاك {category['name']}", "system_key": f"depreciation_expense:{category['code']}", "debit": amount, "credit": 0},
            {"account_name": f"مجمع إهلاك {category['name']}", "system_key": f"accumulated_depreciation:{category['code']}", "debit": 0, "credit": amount},
        ],
    )


async def journal_for_custody_advance(document: dict, current_user: Optional[dict] = None):
    amount = round(float(document.get("amount") or 0), 2)
    if amount <= 0:
        return
    issue_date = document.get("issue_date") if isinstance(document.get("issue_date"), date) else date.fromisoformat(str(document.get("issue_date")))
    label = "عهدة" if document.get("transaction_type") == "custody" else "سلفة"
    await save_journal_entry_document(
        entry_date=issue_date,
        description=f"قيد تلقائي لصرف {label}: {document.get('recipient_name')}",
        reference=document.get("reference_number"),
        source_type="custody_advance",
        source_id=document.get("id"),
        is_auto=True,
        current_user=current_user,
        lines=[
            {"account_name": "العهد والسلف", "system_key": "custody_advances", "debit": amount, "credit": 0},
            {"account_name": "البنك", "bank_id": document.get("bank_id"), "debit": 0, "credit": amount},
        ],
    )


async def journal_for_custody_advance_settlement(document: dict, current_user: Optional[dict] = None):
    amount = round(float(document.get("settled_amount") or 0), 2)
    if amount <= 0 or not document.get("settlement_date"):
        await delete_journal_for_source("custody_advance_settlement", document.get("id"))
        return
    settlement_date = document.get("settlement_date") if isinstance(document.get("settlement_date"), date) else date.fromisoformat(str(document.get("settlement_date")))
    debit_line = {"account_name": "تسوية العهد والسلف", "system_key": "custody_advance_expense", "debit": amount, "credit": 0}
    if document.get("settlement_type") == "bank_return":
        debit_line = {"account_name": "البنك", "bank_id": document.get("bank_id"), "debit": amount, "credit": 0}
    await save_journal_entry_document(
        entry_date=settlement_date,
        description=f"قيد تلقائي لتسوية عهدة/سلفة: {document.get('recipient_name')}",
        reference=document.get("reference_number"),
        source_type="custody_advance_settlement",
        source_id=document.get("id"),
        is_auto=True,
        current_user=current_user,
        lines=[
            debit_line,
            {"account_name": "العهد والسلف", "system_key": "custody_advances", "debit": 0, "credit": amount},
        ],
    )


def row_net_amount(row: TrialBalanceRow) -> float:
    return round(float(row.balance_debit or 0) - float(row.balance_credit or 0), 2)


def normal_amount(row: TrialBalanceRow) -> float:
    if row.account_type in ["asset", "expense"]:
        return round(float(row.balance_debit or 0) - float(row.balance_credit or 0), 2)
    return round(float(row.balance_credit or 0) - float(row.balance_debit or 0), 2)


async def calculate_trial_balance_report(
    organization_id: str,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    account_type: Optional[str] = None,
    non_zero_only: bool = False,
) -> TrialBalanceReport:
    await sync_chart_accounts_for_organization(organization_id)
    await reclassify_revenue_journal_lines_for_organization(organization_id)
    show_term_deposit_principal = await should_show_term_deposits_in_trial_balance(organization_id, to_date)
    account_query = with_organization({}, organization_id)
    if account_type:
        account_query["account_type"] = account_type
    accounts = await db.chart_accounts.find(account_query, {"_id": 0}).sort("code", 1).to_list(5000)
    accounts_by_system_key = {account.get("system_key"): account for account in accounts if account.get("system_key")}
    rows_by_key = {}
    for account in accounts:
        key = account.get("id") or account.get("code") or account.get("name")
        rows_by_key[key] = {
            "account_id": account.get("id"),
            "account_code": account.get("code"),
            "account_name": account.get("name"),
            "account_type": account.get("account_type"),
            "nature": account.get("nature"),
            "system_key": account.get("system_key"),
            "opening_balance": round(float(account.get("opening_balance") or 0), 2),
            "total_debit": 0.0,
            "total_credit": 0.0,
            "balance_debit": 0.0,
            "balance_credit": 0.0,
        }
    entry_query = with_organization({"status": "approved", "is_reversal": {"$ne": True}, "source_type": {"$nin": REPORT_EXCLUDED_SOURCE_TYPES}}, organization_id)
    if from_date or to_date:
        entry_query["entry_date"] = {}
        if from_date:
            entry_query["entry_date"]["$gte"] = from_date.isoformat()
        if to_date:
            entry_query["entry_date"]["$lte"] = to_date.isoformat()
    entries = await db.journal_entries.find(entry_query, {"_id": 0, "lines": 1, "source_type": 1}).to_list(100000)
    if not show_term_deposit_principal:
        entries = [entry for entry in entries if not entry_has_term_deposit_principal(entry)]
    account_by_code = {account.get("code"): account for account in accounts if account.get("code")}
    account_by_name = {account.get("name"): account for account in accounts if account.get("name")}
    if from_date:
        prior_entries = await db.journal_entries.find(with_organization({"status": "approved", "is_reversal": {"$ne": True}, "source_type": {"$nin": REPORT_EXCLUDED_SOURCE_TYPES}, "entry_date": {"$lt": from_date.isoformat()}}, organization_id), {"_id": 0, "lines": 1, "source_type": 1}).to_list(100000)
        if not show_term_deposit_principal:
            prior_entries = [entry for entry in prior_entries if not entry_has_term_deposit_principal(entry)]
        for entry in prior_entries:
            for line in entry.get("lines", []):
                account = None
                if line.get("account_id") and line["account_id"] in rows_by_key:
                    key = line["account_id"]
                else:
                    account = account_by_code.get(line.get("account_code")) or account_by_name.get(line.get("account_name"))
                    if account_type and (not account or account.get("account_type") != account_type):
                        continue
                    key = account.get("id") if account else (line.get("account_code") or line.get("account_name"))
                if key not in rows_by_key:
                    continue
                movement_net = round(float(line.get("debit") or 0) - float(line.get("credit") or 0), 2)
                if rows_by_key[key].get("nature") == "credit":
                    rows_by_key[key]["opening_balance"] = round(rows_by_key[key]["opening_balance"] - movement_net, 2)
                else:
                    rows_by_key[key]["opening_balance"] = round(rows_by_key[key]["opening_balance"] + movement_net, 2)
    for entry in entries:
        for line in entry.get("lines", []):
            account = None
            if line.get("account_id") and line["account_id"] in rows_by_key:
                key = line["account_id"]
            else:
                account = account_by_code.get(line.get("account_code")) or account_by_name.get(line.get("account_name"))
                if account_type and (not account or account.get("account_type") != account_type):
                    continue
                key = account.get("id") if account else (line.get("account_code") or line.get("account_name"))
            if key not in rows_by_key:
                if account_type and (account.get("account_type") if account else line.get("account_type")) != account_type:
                    continue
                rows_by_key[key] = {
                    "account_id": account.get("id") if account else line.get("account_id"),
                    "account_code": account.get("code") if account else line.get("account_code"),
                    "account_name": account.get("name") if account else line.get("account_name") or "حساب غير محدد",
                    "account_type": account.get("account_type") if account else line.get("account_type"),
                    "nature": account.get("nature") if account else None,
                    "system_key": account.get("system_key") if account else None,
                    "opening_balance": 0.0,
                    "total_debit": 0.0,
                    "total_credit": 0.0,
                    "balance_debit": 0.0,
                    "balance_credit": 0.0,
                }
            rows_by_key[key]["total_debit"] = round(rows_by_key[key]["total_debit"] + float(line.get("debit") or 0), 2)
            rows_by_key[key]["total_credit"] = round(rows_by_key[key]["total_credit"] + float(line.get("credit") or 0), 2)
    if from_date and to_date:
        deposit_period_interest = await calculate_total_deposit_interest_for_period(organization_id, from_date, to_date)
        if deposit_period_interest > 0:
            for system_key, side in [("accrued_deposit_interest", "debit"), ("deposit_interest_revenue", "credit")]:
                account = accounts_by_system_key.get(system_key)
                if not account or (account_type and account.get("account_type") != account_type):
                    continue
                key = account.get("id") or account.get("code") or account.get("name")
                if key not in rows_by_key:
                    continue
                if side == "debit":
                    rows_by_key[key]["total_debit"] = round(rows_by_key[key]["total_debit"] + deposit_period_interest, 2)
                else:
                    rows_by_key[key]["total_credit"] = round(rows_by_key[key]["total_credit"] + deposit_period_interest, 2)
    rows = []
    for row in rows_by_key.values():
        signed_balance = row["total_debit"] - row["total_credit"]
        if row.get("nature") == "credit":
            signed_balance -= row["opening_balance"]
        else:
            signed_balance += row["opening_balance"]
        if signed_balance >= 0:
            row["balance_debit"] = round(signed_balance, 2)
            row["balance_credit"] = 0.0
        else:
            row["balance_debit"] = 0.0
            row["balance_credit"] = round(abs(signed_balance), 2)
        if row.get("system_key") == "term_deposits" and not show_term_deposit_principal:
            continue
        if non_zero_only and not any([row["opening_balance"], row["total_debit"], row["total_credit"], row["balance_debit"], row["balance_credit"]]):
            continue
        row.pop("system_key", None)
        rows.append(TrialBalanceRow(**row))
    rows.sort(key=lambda item: item.account_code or "999999")
    total_debit = round(sum(row.total_debit for row in rows), 2)
    total_credit = round(sum(row.total_credit for row in rows), 2)
    total_balance_debit = round(sum(row.balance_debit for row in rows), 2)
    total_balance_credit = round(sum(row.balance_credit for row in rows), 2)
    return TrialBalanceReport(
        organization_id=organization_id,
        from_date=from_date,
        to_date=to_date,
        account_type=account_type,
        rows=rows,
        total_debit=total_debit,
        total_credit=total_credit,
        total_balance_debit=total_balance_debit,
        total_balance_credit=total_balance_credit,
        is_balanced=round(total_debit - total_credit, 2) == 0,
    )


def financial_line_from_trial(row: TrialBalanceRow, amount: Optional[float] = None) -> FinancialStatementLine:
    return FinancialStatementLine(code=row.account_code, name=row.account_name, amount=round(amount if amount is not None else normal_amount(row), 2), debit=row.balance_debit, credit=row.balance_credit)


def is_bank_credit_asset_row(row: TrialBalanceRow) -> bool:
    code = str(row.account_code or "")
    name = str(row.account_name or "")
    return row.account_type == "asset" and row.nature == "debit" and row.balance_credit > 0 and (code.startswith("11") or "بنك" in name)


def bank_credit_liability_line(row: TrialBalanceRow) -> FinancialStatementLine:
    return FinancialStatementLine(
        code=row.account_code,
        name=f"رصيد دائن بالبنك - {row.account_name}",
        amount=round(float(row.balance_credit or 0), 2),
        debit=row.balance_debit,
        credit=row.balance_credit,
        details="تم عرض رصيد البنك الدائن ضمن الالتزامات بدلاً من اعتباره خطأ محاسبي.",
    )


async def build_accounting_errors(organization_id: str, balance_report: TrialBalanceReport, income_report: TrialBalanceReport, balance_assets_total: float, balance_liability_equity_total: float) -> List[AccountingErrorItem]:
    errors: List[AccountingErrorItem] = []
    if not balance_report.is_balanced:
        errors.append(AccountingErrorItem(severity="critical", error_type="ميزان غير متوازن", location="ميزان المراجعة", details=f"إجمالي المدين {balance_report.total_debit} لا يساوي إجمالي الدائن {balance_report.total_credit}", suggested_fix="راجع القيود اليومية غير المتوازنة أو الحسابات غير المرتبطة."))
    if round(balance_assets_total - balance_liability_equity_total, 2) != 0:
        errors.append(AccountingErrorItem(severity="critical", error_type="الميزانية غير متوازنة", location="قائمة الميزانية", details=f"إجمالي الأصول {balance_assets_total} لا يساوي إجمالي الالتزامات وحقوق الملكية {balance_liability_equity_total}", suggested_fix="راجع أرصدة الحسابات ونتيجة الفترة والحسابات ذات الطبيعة العكسية."))
    bad_entries = await db.journal_entries.find(with_organization({"status": "approved", "is_reversal": {"$ne": True}}, organization_id), {"_id": 0, "id": 1, "entry_number": 1, "entry_date": 1, "description": 1, "total_debit": 1, "total_credit": 1, "lines": 1}).to_list(100000)
    for entry in bad_entries:
        total_debit = round(float(entry.get("total_debit") or 0), 2)
        total_credit = round(float(entry.get("total_credit") or 0), 2)
        if total_debit != total_credit or total_debit <= 0:
            errors.append(AccountingErrorItem(severity="critical", error_type="قيد غير متوازن", location=f"قيد رقم {entry.get('entry_number')} بتاريخ {entry.get('entry_date')}", details=f"{entry.get('description')} — مدين {total_debit} / دائن {total_credit}", suggested_fix="افتح القيد وعدّل السطور حتى يتساوى المدين والدائن."))
        for index, line in enumerate(entry.get("lines", []), start=1):
            if not line.get("account_id") and not line.get("account_code"):
                errors.append(AccountingErrorItem(severity="critical", error_type="سطر قيد بلا حساب", location=f"قيد رقم {entry.get('entry_number')} - سطر {index}", details=f"السطر باسم {line.get('account_name') or 'غير محدد'} غير مرتبط بحساب في شجرة الحسابات", suggested_fix="اربط السطر بحساب صحيح أو أضف الحساب إلى شجرة الحسابات."))
            if float(line.get("debit") or 0) > 0 and float(line.get("credit") or 0) > 0:
                errors.append(AccountingErrorItem(severity="critical", error_type="سطر مدين ودائن معاً", location=f"قيد رقم {entry.get('entry_number')} - سطر {index}", details="السطر يحتوي قيمة في المدين والدائن معاً", suggested_fix="اجعل السطر مديناً أو دائناً فقط."))
    for row in balance_report.rows:
        if row.nature == "debit" and row.balance_credit > 0:
            if is_bank_credit_asset_row(row):
                continue
            errors.append(AccountingErrorItem(severity="warning", error_type="رصيد عكسي", location=f"حساب {row.account_code or '-'} - {row.account_name}", details=f"الحساب طبيعته مدينة لكن لديه رصيد دائن {row.balance_credit}", suggested_fix="راجع القيود المرتبطة بهذا الحساب."))
        if row.nature == "credit" and row.balance_debit > 0:
            errors.append(AccountingErrorItem(severity="warning", error_type="رصيد عكسي", location=f"حساب {row.account_code or '-'} - {row.account_name}", details=f"الحساب طبيعته دائنة لكن لديه رصيد مدين {row.balance_debit}", suggested_fix="راجع القيود المرتبطة بهذا الحساب."))
    fixed_assets = await db.fixed_assets.find(with_organization({}), {"_id": 0}).to_list(10000)
    for asset in fixed_assets:
        accumulated = await depreciation_total_for_asset(asset["id"])
        cost = round(float(asset.get("purchase_cost") or 0), 2)
        if accumulated > cost:
            errors.append(AccountingErrorItem(severity="critical", error_type="إهلاك أصل أكبر من تكلفته", location=f"الأصل {asset.get('asset_code')} - {asset.get('asset_name')}", details=f"مجمع الإهلاك {accumulated} أكبر من تكلفة الأصل {cost}", suggested_fix="راجع سجلات إهلاك هذا الأصل."))
    return errors


async def calculate_financial_statements_report(organization_id: str, from_date: Optional[date] = None, to_date: Optional[date] = None) -> FinancialStatementsReport:
    repair_details = await repair_journal_account_links_for_organization(organization_id, return_details=True)
    today_value = date.today()
    period_from = from_date or date(today_value.year, 1, 1)
    period_to = to_date or today_value
    await auto_run_annual_depreciation_for_year(organization_id, period_to.year, None)
    balance_report = await calculate_trial_balance_report(organization_id=organization_id, to_date=period_to, non_zero_only=True)
    income_report = await calculate_trial_balance_report(organization_id=organization_id, from_date=period_from, to_date=period_to, non_zero_only=True)
    asset_lines = []
    reclassified_bank_credit_lines = []
    for row in balance_report.rows:
        if row.account_type != "asset" or normal_amount(row) == 0:
            continue
        if is_bank_credit_asset_row(row):
            reclassified_bank_credit_lines.append(bank_credit_liability_line(row))
            continue
        asset_lines.append(financial_line_from_trial(row))
    liability_lines = [financial_line_from_trial(row) for row in balance_report.rows if row.account_type == "liability" and normal_amount(row) != 0] + reclassified_bank_credit_lines
    equity_lines = [financial_line_from_trial(row) for row in balance_report.rows if row.account_type == "equity" and normal_amount(row) != 0]
    revenue_lines = [financial_line_from_trial(row) for row in income_report.rows if row.account_type == "revenue" and normal_amount(row) != 0]
    expense_lines = [financial_line_from_trial(row) for row in income_report.rows if row.account_type == "expense" and normal_amount(row) != 0]
    revenue_total = round(sum(line.amount for line in revenue_lines), 2)
    expense_total = round(sum(line.amount for line in expense_lines), 2)
    period_result = round(revenue_total - expense_total, 2)
    result_line = FinancialStatementLine(code=None, name="فائض / عجز الفترة", amount=period_result, details="محسوب تلقائياً من الإيرادات والمصروفات")
    equity_with_result = equity_lines + [result_line]
    assets_total = round(sum(line.amount for line in asset_lines), 2)
    liabilities_total = round(sum(line.amount for line in liability_lines), 2)
    equity_total = round(sum(line.amount for line in equity_with_result), 2)
    liability_equity_total = round(liabilities_total + equity_total, 2)
    opening_balance_difference = round(assets_total - liability_equity_total, 2)
    if balance_report.is_balanced and opening_balance_difference != 0:
        equity_with_result.append(FinancialStatementLine(
            code=None,
            name="رصيد افتتاحي مرحل / صافي الأصول",
            amount=opening_balance_difference,
            details="تمت إضافته تلقائياً لمعادلة الميزانية عند وجود أرصدة افتتاحية أصول/بنوك بدون حساب حقوق ملكية مقابل.",
        ))
        equity_total = round(sum(line.amount for line in equity_with_result), 2)
        liability_equity_total = round(liabilities_total + equity_total, 2)
    entries = await db.journal_entries.find(with_organization({"status": "approved", "is_reversal": {"$ne": True}, "entry_date": {"$gte": period_from.isoformat(), "$lte": period_to.isoformat()}}, organization_id), {"_id": 0}).sort("entry_date", 1).to_list(100000)
    receipts = []
    payments = []
    for entry in entries:
        for line in entry.get("lines", []):
            account_code = str(line.get("account_code") or "")
            account_name = str(line.get("account_name") or "")
            is_bank_line = account_code.startswith("11") or account_name in ["البنوك", "البنك"] or line.get("bank_id")
            if not is_bank_line:
                continue
            debit = round(float(line.get("debit") or 0), 2)
            credit = round(float(line.get("credit") or 0), 2)
            statement_line = FinancialStatementLine(code=account_code or None, name=entry.get("description") or account_name, debit=debit, credit=credit, amount=debit or credit, reference=entry.get("reference"), entry_number=entry.get("entry_number"), entry_date=date.fromisoformat(entry["entry_date"]), details=account_name)
            if debit > 0:
                receipts.append(statement_line)
            if credit > 0:
                payments.append(statement_line)
    receipts_total = round(sum(line.amount for line in receipts), 2)
    payments_total = round(sum(line.amount for line in payments), 2)
    errors = await build_accounting_errors(organization_id, balance_report, income_report, assets_total, liability_equity_total)
    return FinancialStatementsReport(
        organization_id=organization_id,
        from_date=period_from,
        to_date=period_to,
        balance_sheet={
            "assets": FinancialStatementSection(title="الأصول", lines=asset_lines, total=assets_total),
            "liabilities": FinancialStatementSection(title="الالتزامات", lines=liability_lines, total=liabilities_total),
            "equity": FinancialStatementSection(title="حقوق الملكية والفائض", lines=equity_with_result, total=equity_total),
            "check": FinancialStatementSection(title="اتزان الميزانية", lines=[FinancialStatementLine(name="إجمالي الأصول", amount=assets_total), FinancialStatementLine(name="إجمالي الالتزامات وحقوق الملكية", amount=liability_equity_total), FinancialStatementLine(name="فرق الاتزان", amount=round(assets_total - liability_equity_total, 2))], total=round(assets_total - liability_equity_total, 2)),
        },
        receipts_payments={
            "receipts": FinancialStatementSection(title="المقبوضات", lines=receipts, total=receipts_total),
            "payments": FinancialStatementSection(title="المدفوعات", lines=payments, total=payments_total),
            "net_cash_flow": FinancialStatementSection(title="صافي المقبوضات والمدفوعات", lines=[FinancialStatementLine(name="صافي الحركة النقدية", amount=round(receipts_total - payments_total, 2))], total=round(receipts_total - payments_total, 2)),
        },
        revenues_expenses={
            "revenues": FinancialStatementSection(title="الإيرادات", lines=revenue_lines, total=revenue_total),
            "expenses": FinancialStatementSection(title="المصروفات", lines=expense_lines, total=expense_total),
            "result": FinancialStatementSection(title="نتيجة الفترة", lines=[result_line], total=period_result),
        },
        accounting_errors=errors,
        accounting_corrections=[JournalRepairItem(**item) for item in repair_details],
        is_accounting_valid=not any(error.severity == "critical" for error in errors),
        generated_at=datetime.now(timezone.utc),
    )


async def validate_accounting_data_flow(organization_id: str) -> dict:
    CURRENT_ORGANIZATION_ID.set(organization_id)
    period_from = date(1900, 1, 1)
    period_to = date(2099, 12, 31)
    await sync_chart_accounts_for_organization(organization_id)
    trial = await calculate_trial_balance_report(organization_id, period_from, period_to, non_zero_only=True)
    statements = await calculate_financial_statements_report(organization_id, period_from, period_to)
    accounts = await db.chart_accounts.find(with_organization({}, organization_id), {"_id": 0}).to_list(10000)
    accounts_by_id = {item.get("id"): item for item in accounts if item.get("id")}
    accounts_by_code = {item.get("code"): item for item in accounts if item.get("code")}
    accounts_by_name = {item.get("name"): item for item in accounts if item.get("name")}
    entries = await db.journal_entries.find(with_organization({"status": "approved", "is_reversal": {"$ne": True}, "source_type": {"$nin": REPORT_EXCLUDED_SOURCE_TYPES}, "entry_date": {"$gte": period_from.isoformat(), "$lte": period_to.isoformat()}}, organization_id), {"_id": 0}).to_list(100000)
    show_term_deposit_principal = await should_show_term_deposits_in_trial_balance(organization_id, period_to)
    reversal_count = await db.journal_entries.count_documents(with_organization({"is_reversal": True}, organization_id))
    missing_lines = []
    ledger_totals: dict[str, dict] = {}
    for entry in entries:
        if not show_term_deposit_principal and entry_has_term_deposit_principal(entry):
            continue
        for index, line in enumerate(entry.get("lines", []), 1):
            account = accounts_by_id.get(line.get("account_id")) or accounts_by_code.get(line.get("account_code")) or accounts_by_name.get(line.get("account_name"))
            if not account:
                missing_lines.append({"entry_number": entry.get("entry_number"), "line_index": index, "account_name": line.get("account_name")})
                continue
            key = account.get("id")
            ledger_totals.setdefault(key, {"debit": 0.0, "credit": 0.0, "name": account.get("name")})
            ledger_totals[key]["debit"] = round(ledger_totals[key]["debit"] + float(line.get("debit") or 0), 2)
            ledger_totals[key]["credit"] = round(ledger_totals[key]["credit"] + float(line.get("credit") or 0), 2)
    accounts_by_system_key = {item.get("system_key"): item for item in accounts if item.get("system_key")}
    deposit_period_interest = await calculate_total_deposit_interest_for_period(organization_id, period_from, period_to)
    if deposit_period_interest > 0:
        for system_key, side in [("accrued_deposit_interest", "debit"), ("deposit_interest_revenue", "credit")]:
            account = accounts_by_system_key.get(system_key)
            if not account:
                continue
            key = account.get("id")
            ledger_totals.setdefault(key, {"debit": 0.0, "credit": 0.0, "name": account.get("name")})
            ledger_totals[key][side] = round(ledger_totals[key][side] + deposit_period_interest, 2)
    trial_mismatches = []
    for row in trial.rows:
        if not row.account_id:
            continue
        ledger = ledger_totals.get(row.account_id, {"debit": 0.0, "credit": 0.0, "name": row.account_name})
        if round(float(row.total_debit) - ledger["debit"], 2) != 0 or round(float(row.total_credit) - ledger["credit"], 2) != 0:
            trial_mismatches.append({"account_code": row.account_code, "account_name": row.account_name, "trial_debit": row.total_debit, "ledger_debit": ledger["debit"], "trial_credit": row.total_credit, "ledger_credit": ledger["credit"]})
    balance_check = round(float(statements.balance_sheet["check"].total or 0), 2)
    critical_errors = [error.model_dump(mode="json") for error in statements.accounting_errors if error.severity == "critical"]
    return {
        "organization_id": organization_id,
        "period_from": period_from.isoformat(),
        "period_to": period_to.isoformat(),
        "journal_entries_count": len(entries),
        "hidden_reversal_entries_count": reversal_count,
        "ledger_accounts_checked": len(ledger_totals),
        "trial_balance": {"total_debit": trial.total_debit, "total_credit": trial.total_credit, "is_balanced": trial.is_balanced, "total_balance_debit": trial.total_balance_debit, "total_balance_credit": trial.total_balance_credit},
        "income_statement": {"revenues": statements.revenues_expenses["revenues"].total, "expenses": statements.revenues_expenses["expenses"].total, "result": statements.revenues_expenses["result"].total},
        "cash_in_out": {"receipts": statements.receipts_payments["receipts"].total, "payments": statements.receipts_payments["payments"].total, "net": statements.receipts_payments["net_cash_flow"].total},
        "balance_sheet": {"assets": statements.balance_sheet["assets"].total, "liabilities": statements.balance_sheet["liabilities"].total, "equity": statements.balance_sheet["equity"].total, "check": balance_check},
        "missing_orphan_entries": missing_lines,
        "ledger_trial_mismatches": trial_mismatches,
        "critical_accounting_errors": critical_errors,
        "is_valid": (not missing_lines and not trial_mismatches and trial.is_balanced and balance_check == 0 and not critical_errors),
    }


async def validate_membership_data_flow(organization_id: str) -> dict:
    CURRENT_ORGANIZATION_ID.set(organization_id)
    if organization_id != "social-solidarity":
        return {"organization_id": organization_id, "is_applicable": False, "is_valid": True, "message": "نظام العضوية خاص بمشروع التكافل الاجتماعي"}
    as_of = date.today()
    documents = await db.memberships.find(with_organization({}, organization_id), {"_id": 0}).to_list(10000)
    paid_map = await membership_paid_allocations_map(as_of)
    status_counts = {key: 0 for key in MEMBERSHIP_STATUS_LABELS}
    issues = []
    total_due = total_collected = total_remaining = 0.0
    for document in documents:
        status = document.get("status") or "active"
        status_counts[status] = status_counts.get(status, 0) + 1
        enriched = await enrich_membership_financials(document, as_of, paid_map)
        total_due = round(total_due + float(enriched.get("current_due") or 0), 2)
        total_collected = round(total_collected + float(enriched.get("total_collected") or 0), 2)
        total_remaining = round(total_remaining + float(enriched.get("remaining_balance") or 0), 2)
        if status in NON_ACTIVE_MEMBERSHIP_STATUSES and not document.get("subscription_stop_date"):
            issues.append({"member_id": document.get("id"), "membership_number": document.get("membership_number"), "issue": "عضو غير فعال بدون تاريخ إيقاف اشتراك"})
    batches = await db.membership_batch_payments.find(with_organization({}, organization_id), {"_id": 0}).to_list(10000)
    allocation_total = round(sum(float(allocation.get("amount") or 0) for batch in batches for allocation in batch.get("allocations", [])), 2)
    batch_total = round(sum(float(batch.get("allocated_amount") or 0) for batch in batches), 2)
    if allocation_total != batch_total:
        issues.append({"issue": "إجمالي توزيعات الأذون لا يساوي إجمالي المبالغ الموزعة", "allocation_total": allocation_total, "batch_total": batch_total})
    return {"organization_id": organization_id, "is_applicable": True, "as_of_date": as_of.isoformat(), "members_count": len(documents), "status_counts": status_counts, "total_due": total_due, "total_collected": total_collected, "remaining_balance": total_remaining, "batch_payments_count": len(batches), "allocated_amount": allocation_total, "issues": issues, "is_valid": not issues}


async def latest_created_at_for_collections(organization_id: str, collection_names: list[str]) -> Optional[str]:
    latest_value = None
    for collection_name in collection_names:
        document = await db[collection_name].find_one(with_organization({}, organization_id), {"_id": 0, "created_at": 1, "updated_at": 1}, sort=[("updated_at", -1), ("created_at", -1)])
        value = (document or {}).get("updated_at") or (document or {}).get("created_at")
        if value and (latest_value is None or str(value) > str(latest_value)):
            latest_value = str(value)
    return latest_value


async def flow_monitor_for_organization(organization_id: str, accounting_validation: dict, membership_validation: dict) -> list[dict]:
    input_collections = ["deposits", "revenues", "expenses", "fixed_assets", "custody_advances", "memberships", "membership_batch_payments", "reconciliations"]
    input_count = 0
    for collection_name in input_collections:
        input_count += await db[collection_name].count_documents(with_organization({}, organization_id))
    rules = await list_accounting_rules_for_organization(organization_id)
    active_rules = [rule for rule in rules if rule.get("is_active", True)]
    entries_count = int(accounting_validation.get("journal_entries_count") or 0)
    mismatch_count = len(accounting_validation.get("ledger_trial_mismatches") or [])
    missing_count = len(accounting_validation.get("missing_orphan_entries") or [])
    critical_count = len(accounting_validation.get("critical_accounting_errors") or [])
    balance_error = 0 if float(accounting_validation.get("balance_sheet", {}).get("check") or 0) == 0 else 1
    now_iso = serialize_datetime(datetime.now(timezone.utc))
    return [
        {"stage_key": "input", "stage_name": "إدخال العملية", "status": "مفعلة", "is_active": True, "operations_count": input_count, "last_run": await latest_created_at_for_collections(organization_id, input_collections), "errors_count": 0},
        {"stage_key": "auto_validation", "stage_name": "فحص آلي", "status": "مفعلة", "is_active": True, "operations_count": entries_count + input_count, "last_run": now_iso, "errors_count": missing_count + mismatch_count + critical_count + len(membership_validation.get("issues") or [])},
        {"stage_key": "journal_creation", "stage_name": "إنشاء قيد محاسبي", "status": "مفعلة", "is_active": True, "operations_count": entries_count, "last_run": await latest_created_at_for_collections(organization_id, ["journal_entries"]), "errors_count": missing_count},
        {"stage_key": "journal", "stage_name": "دفتر اليومية", "status": "مفعلة", "is_active": True, "operations_count": entries_count, "last_run": await latest_created_at_for_collections(organization_id, ["journal_entries"]), "errors_count": missing_count},
        {"stage_key": "ledger", "stage_name": "الأستاذ العام", "status": "مفعلة", "is_active": True, "operations_count": int(accounting_validation.get("ledger_accounts_checked") or 0), "last_run": now_iso, "errors_count": mismatch_count},
        {"stage_key": "trial_balance", "stage_name": "ميزان المراجعة", "status": "مفعلة", "is_active": bool(accounting_validation.get("trial_balance", {}).get("is_balanced")), "operations_count": entries_count, "last_run": now_iso, "errors_count": 0 if accounting_validation.get("trial_balance", {}).get("is_balanced") else 1},
        {"stage_key": "financial_statements", "stage_name": "القوائم المالية", "status": "مفعلة", "is_active": accounting_validation.get("is_valid", False), "operations_count": entries_count, "last_run": now_iso, "errors_count": critical_count + balance_error},
        {"stage_key": "rules_engine", "stage_name": "Rules Engine", "status": "مفعلة" if active_rules else "غير مفعلة", "is_active": bool(active_rules), "operations_count": len(active_rules), "last_run": await latest_created_at_for_collections(organization_id, ["accounting_rules"]), "errors_count": 0 if active_rules else 1},
    ]


def validation_tests_from_flow(accounting_validation: dict, membership_validation: dict) -> list[dict]:
    return [
        {"test_key": "journal_balance", "test_name": "فحص اتزان القيود", "status": "ناجح" if not accounting_validation.get("missing_orphan_entries") else "فشل", "errors_count": len(accounting_validation.get("missing_orphan_entries") or [])},
        {"test_key": "ledger", "test_name": "فحص الأستاذ العام", "status": "ناجح" if not accounting_validation.get("ledger_trial_mismatches") else "فشل", "errors_count": len(accounting_validation.get("ledger_trial_mismatches") or [])},
        {"test_key": "trial_balance", "test_name": "فحص ميزان المراجعة", "status": "ناجح" if accounting_validation.get("trial_balance", {}).get("is_balanced") else "فشل", "errors_count": 0 if accounting_validation.get("trial_balance", {}).get("is_balanced") else 1},
        {"test_key": "balance_sheet", "test_name": "فحص الميزانية", "status": "ناجح" if float(accounting_validation.get("balance_sheet", {}).get("check") or 0) == 0 else "فشل", "errors_count": 0 if float(accounting_validation.get("balance_sheet", {}).get("check") or 0) == 0 else 1},
        {"test_key": "membership", "test_name": "فحص العضوية", "status": "ناجح" if membership_validation.get("is_valid") else "فشل", "errors_count": len(membership_validation.get("issues") or [])},
    ]


def health_score(base: int, penalties: List[int]) -> int:
    return max(0, min(100, int(base - sum(penalties))))


def health_status(score: int) -> str:
    if score >= 90:
        return "ممتاز"
    if score >= 80:
        return "جيد جداً"
    if score >= 70:
        return "جيد"
    if score >= 55:
        return "يحتاج متابعة"
    return "حرج"


def pdf_ar(value: object) -> str:
    text = str(value if value is not None else "-")
    return get_display(arabic_reshaper.reshape(text))


def register_erp_pdf_font() -> str:
    font_candidates = [
        str(APP_ASSETS_DIR / "Amiri-Regular.ttf"),
        str(ROOT_DIR.parent / "app_assets" / "Amiri-Regular.ttf"),
        "/usr/share/fonts/opentype/fonts-hosny-amiri/Amiri-Regular.ttf",
        "/usr/share/fonts/truetype/kacst-one/KacstOne.ttf",
        "/usr/share/fonts/truetype/kacst/KacstNaskh.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for font_path in font_candidates:
        if Path(font_path).exists():
            try:
                pdfmetrics.registerFont(TTFont("ArabicReportFont", font_path))
                return "ArabicReportFont"
            except Exception:
                continue
    return "Helvetica"


def public_app_base_url(request: Request) -> str:
    for origin in CORS_ORIGINS:
        if origin.startswith("https://") and "preview" in origin:
            return origin.rstrip("/")
    forwarded_host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    forwarded_proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    if forwarded_host:
        return f"{forwarded_proto}://{forwarded_host}".rstrip("/")
    return str(request.base_url).rstrip("/")


def metric_as_model(key: str, title: str, score: int, details: str) -> ErpHealthMetric:
    return ErpHealthMetric(key=key, title=title, score=score, status=health_status(score), details=details)


async def build_erp_health_report_payload(organization_id: str, direct_download_url: str, report_id: str) -> ErpHealthReportResponse:
    started_at = time.perf_counter()
    generated_at = datetime.now(timezone.utc)
    period_from = date(1900, 1, 1)
    period_to = date(2099, 12, 31)
    query_started_at = time.perf_counter()
    accounts = await db.chart_accounts.find(with_organization({}, organization_id), {"_id": 0}).to_list(100000)
    entries = await db.journal_entries.find(with_organization({"status": "approved", "is_reversal": {"$ne": True}}, organization_id), {"_id": 0}).to_list(100000)
    all_entries_count = await db.journal_entries.count_documents(with_organization({}, organization_id))
    reversal_count = await db.journal_entries.count_documents(with_organization({"is_reversal": True}, organization_id))
    reconciliations = await db.reconciliations.find(with_organization({}, organization_id), {"_id": 0}).to_list(100000)
    audit_count = await db.audit_logs.count_documents(with_organization({}, organization_id))
    electronic_invoice_count = await db.electronic_invoices.count_documents(with_organization({}, organization_id))
    banking_tariff_count = await db.banking_tariffs.count_documents(with_organization({}, organization_id))
    query_ms = round((time.perf_counter() - query_started_at) * 1000, 2)
    accounts_by_id = {item.get("id"): item for item in accounts if item.get("id")}
    accounts_by_code = {item.get("code"): item for item in accounts if item.get("code")}
    accounts_by_name = {item.get("name"): item for item in accounts if item.get("name")}
    unbalanced_entries = []
    invalid_lines = []
    missing_accounts = []
    duplicate_entry_numbers = []
    seen_entry_numbers = set()
    ledger_totals: Dict[str, dict] = {}
    total_debit = 0.0
    total_credit = 0.0
    entries_with_created_at = 0
    entries_with_user = 0
    for entry in entries:
        entry_number = entry.get("entry_number")
        if entry_number in seen_entry_numbers:
            duplicate_entry_numbers.append(entry_number)
        seen_entry_numbers.add(entry_number)
        if entry.get("created_at"):
            entries_with_created_at += 1
        if entry.get("created_by") or entry.get("created_by_name"):
            entries_with_user += 1
        entry_debit = round(sum(float(line.get("debit") or 0) for line in entry.get("lines", [])), 2)
        entry_credit = round(sum(float(line.get("credit") or 0) for line in entry.get("lines", [])), 2)
        total_debit = round(total_debit + entry_debit, 2)
        total_credit = round(total_credit + entry_credit, 2)
        if abs(entry_debit - entry_credit) >= 0.01:
            unbalanced_entries.append(entry_number)
        for index, line in enumerate(entry.get("lines", []), 1):
            debit = float(line.get("debit") or 0)
            credit = float(line.get("credit") or 0)
            if (debit > 0 and credit > 0) or (debit == 0 and credit == 0):
                invalid_lines.append({"entry_number": entry_number, "line_index": index})
            account = accounts_by_id.get(line.get("account_id")) or accounts_by_code.get(line.get("account_code")) or accounts_by_name.get(line.get("account_name"))
            if not account:
                missing_accounts.append({"entry_number": entry_number, "line_index": index, "account_name": line.get("account_name")})
                continue
            account_id = account.get("id")
            ledger_totals.setdefault(account_id, {"debit": 0.0, "credit": 0.0, "name": account.get("name"), "code": account.get("code")})
            ledger_totals[account_id]["debit"] = round(ledger_totals[account_id]["debit"] + debit, 2)
            ledger_totals[account_id]["credit"] = round(ledger_totals[account_id]["credit"] + credit, 2)
    trial_is_balanced = abs(total_debit - total_credit) < 0.01
    reconciliation_differences = [abs(float(item.get("difference") or 0)) for item in reconciliations]
    matched_reconciliations = sum(1 for item in reconciliations if item.get("is_matched") is True or abs(float(item.get("difference") or 0)) < 0.01)
    reconciliation_match_rate = round((matched_reconciliations / len(reconciliations) * 100), 2) if reconciliations else 100.0
    source_collections = ["deposits", "revenues", "expenses", "fixed_assets", "custody_advances", "memberships", "membership_batch_payments", "inventory_movements", "misc_creditor_movements", "reconciliations"]
    source_counts = {name: await db[name].count_documents(with_organization({}, organization_id)) for name in source_collections}
    source_types_in_entries = {entry.get("source_type") for entry in entries if entry.get("source_type")}
    integration_expected = ["deposit", "revenue", "expense", "fixed_asset", "custody_advance", "membership_batch_payment", "inventory", "misc_creditor", "reconciliation"]
    active_expected = [item for item in integration_expected if any(key in item for key in [])]
    active_expected = [item for item in integration_expected if item in source_types_in_entries]
    integration_score_value = round((len(active_expected) / max(1, len(integration_expected))) * 100)
    external_dependency_items = electronic_invoice_count + banking_tariff_count
    total_operation_items = max(1, all_entries_count + sum(source_counts.values()) + len(reconciliations))
    external_dependency_percent = round((external_dependency_items / total_operation_items) * 100, 2)
    accounting_score = health_score(100, [min(40, len(unbalanced_entries) * 10), min(25, len(invalid_lines) * 5), min(25, len(missing_accounts) * 5), min(10, len(duplicate_entry_numbers) * 2)])
    trial_score = health_score(100, [0 if trial_is_balanced else 35, min(30, len(missing_accounts) * 3), min(20, len(duplicate_entry_numbers) * 2)])
    reconciliation_score = health_score(100, [int((100 - reconciliation_match_rate) * 0.7), min(20, sum(1 for value in reconciliation_differences if value >= 0.01) * 3)])
    performance_score = health_score(100, [0 if query_ms <= 800 else 10 if query_ms <= 2000 else 25, 0 if len(entries) <= 50000 else 10])
    integration_score = health_score(100, [max(0, 100 - integration_score_value) // 2, min(15, len(missing_accounts) * 2)])
    external_score = health_score(100, [0 if external_dependency_percent <= 5 else 10 if external_dependency_percent <= 15 else 25])
    stability_score = health_score(100, [min(30, len(duplicate_entry_numbers) * 5), min(30, len(missing_accounts) * 4), 0 if trial_is_balanced else 20])
    audit_ratio = round(((entries_with_created_at + entries_with_user) / max(1, len(entries) * 2)) * 100, 2)
    audit_score = health_score(100, [max(0, 100 - int(audit_ratio)) // 2, 0 if audit_count else 10])
    metrics = [
        metric_as_model("journal_accuracy", "دقة القيود ومعدل الأخطاء المحاسبية", accounting_score, f"تم فحص {len(entries)} قيد مرحل. قيود عكسية محفوظة للتدقيق: {reversal_count}. قيود غير متوازنة: {len(unbalanced_entries)}، سطور غير صحيحة: {len(invalid_lines)}، سطور بلا حساب: {len(missing_accounts)}."),
        metric_as_model("trial_balance_consistency", "توازن الحسابات واتساق ميزان المراجعة", trial_score, f"إجمالي المدين {total_debit} / إجمالي الدائن {total_credit}. حالة الاتزان: {'متوازن' if trial_is_balanced else 'غير متوازن'}."),
        metric_as_model("bank_reconciliation_efficiency", "كفاءة ودقة التسويات البنكية", reconciliation_score, f"عدد التسويات {len(reconciliations)}، المتطابق منها {matched_reconciliations}، معدل التطابق {reconciliation_match_rate}%."),
        metric_as_model("performance_metrics", "سرعة معالجة العمليات", performance_score, f"زمن القراءة والتحليل الأساسي {query_ms} مللي ثانية لعدد {total_operation_items} عنصر تشغيلي تقريباً."),
        metric_as_model("integration_score", "تكامل وربط الموديولات", integration_score, f"مصادر القيود النشطة: {len(source_types_in_entries)}، ومؤشر الربط المحسوب {integration_score_value}%."),
        metric_as_model("external_dependency", "نسبة الاعتماد على البيانات الخارجية", external_score, f"نسبة الاعتماد الخارجي المحسوبة {external_dependency_percent}% بناءً على الفواتير/التعريفات الخارجية مقابل التشغيل الداخلي."),
        metric_as_model("data_stability", "استقرار النظام وعدم وجود تعارضات بيانات", stability_score, f"أرقام قيود مكررة: {len(duplicate_entry_numbers)}، روابط حسابات مفقودة: {len(missing_accounts)}، حالة الميزان: {'مستقر' if trial_is_balanced else 'يحتاج مراجعة'}."),
        metric_as_model("audit_completeness", "جودة تتبع العمليات Audit Completeness", audit_score, f"اكتمال created_at/created_by داخل القيود: {audit_ratio}%. عدد سجلات التدقيق: {audit_count}."),
    ]
    overall_score = round(sum(item.score for item in metrics) / len(metrics)) if metrics else 0
    recommendations = []
    if unbalanced_entries:
        recommendations.append("مراجعة القيود غير المتوازنة فوراً قبل إصدار أي قوائم نهائية.")
    if missing_accounts:
        recommendations.append("استكمال ربط سطور القيود بدليل الحسابات لتقليل مخاطر الترحيل غير المصنف.")
    if not trial_is_balanced:
        recommendations.append("إعادة فحص ميزان المراجعة ومطابقته مع دفتر الأستاذ قبل اعتماد الفترة.")
    if reconciliation_match_rate < 90:
        recommendations.append("زيادة مراجعة التسويات البنكية غير المتطابقة وتوثيق فروق كشف البنك.")
    if query_ms > 2000:
        recommendations.append("تحسين الفهارس أو تقسيم تقارير التشغيل عند زيادة حجم البيانات.")
    if audit_score < 85:
        recommendations.append("رفع اكتمال بيانات التدقيق created_by/created_at وتفعيل مراجعة سجل الحركات دورياً.")
    if external_dependency_percent > 15:
        recommendations.append("تقليل الاعتماد على مصادر خارجية غير حاكمة أو توثيق مصدر كل عملية خارجية داخل التقرير.")
    if not recommendations:
        recommendations.append("النظام مستقر حالياً؛ يوصى باستمرار الفحص الدوري قبل إقفال كل فترة مالية.")
    total_ms = round((time.perf_counter() - started_at) * 1000, 2)
    metrics.append(metric_as_model("analysis_runtime", "زمن إنشاء تقرير التقييم", performance_score, f"إجمالي زمن إنشاء التقرير للعرض فقط: {total_ms} مللي ثانية."))
    return ErpHealthReportResponse(
        id=report_id,
        organization_id=organization_id,
        generated_at=generated_at,
        period_from=period_from,
        period_to=period_to,
        overall_score=overall_score,
        metrics=metrics,
        recommendations=recommendations,
        direct_download_url=direct_download_url,
    )


def write_erp_health_pdf(report: ErpHealthReportResponse, output_path: Path):
    font_name = register_erp_pdf_font()
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("ArabicTitle", parent=styles["Title"], fontName=font_name, fontSize=21, leading=32, alignment=TA_CENTER, wordWrap="RTL")
    score_style = ParagraphStyle("ArabicScore", parent=styles["Heading1"], fontName=font_name, fontSize=18, leading=28, alignment=TA_CENTER, textColor=colors.HexColor("#0f3f5f"), wordWrap="RTL")
    heading_style = ParagraphStyle("ArabicHeading", parent=styles["Heading2"], fontName=font_name, fontSize=15, leading=24, alignment=TA_RIGHT, wordWrap="RTL")
    body_style = ParagraphStyle("ArabicBody", parent=styles["BodyText"], fontName=font_name, fontSize=10.5, leading=17, alignment=TA_RIGHT, wordWrap="RTL")
    small_style = ParagraphStyle("ArabicSmall", parent=body_style, fontSize=9, leading=14)
    document = SimpleDocTemplate(str(output_path), pagesize=A4, rightMargin=1.0 * cm, leftMargin=1.0 * cm, topMargin=1.0 * cm, bottomMargin=1.0 * cm, title="ERP Health Report")
    story = [
        Paragraph(pdf_ar("تقرير تقييم شامل للنظام ERP Health Report"), title_style),
        Paragraph(pdf_ar(f"درجة النظام الإجمالية: {report.overall_score} من 100"), score_style),
        Paragraph(pdf_ar(f"تاريخ الإنشاء: {report.generated_at.isoformat()} | الجهة: {report.organization_id} | الوضع: تحليل فقط Read Only"), body_style),
        Spacer(1, 0.3 * cm),
    ]
    metric_rows = [[pdf_ar("التفاصيل"), pdf_ar("الحالة"), pdf_ar("Score"), pdf_ar("البند")]]
    for metric in report.metrics:
        metric_rows.append([Paragraph(pdf_ar(metric.details), small_style), Paragraph(pdf_ar(metric.status), body_style), pdf_ar(metric.score), Paragraph(pdf_ar(metric.title), body_style)])
    metrics_table = PdfTable(metric_rows, colWidths=[8.4 * cm, 2.3 * cm, 1.8 * cm, 5.1 * cm], repeatRows=1, hAlign="RIGHT")
    metrics_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), font_name),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f3f5f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (2, 1), (2, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
    ]))
    story.extend([metrics_table, Spacer(1, 0.4 * cm), Paragraph(pdf_ar("التوصيات التلقائية"), heading_style)])
    for index, recommendation in enumerate(report.recommendations, 1):
        story.append(Paragraph(pdf_ar(f"{index} ـ {recommendation}"), body_style))
    story.extend([
        Spacer(1, 0.35 * cm),
        Paragraph(pdf_ar("مصادر التحليل: القيود اليومية، دفتر الأستاذ، ميزان المراجعة، القوائم والتقارير الحالية، التسويات البنكية، وسجل الحركات."), body_style),
        Paragraph(pdf_ar("تأكيد: هذا التقرير تم إنشاؤه للقراءة والتحليل فقط، ولا يقوم بأي تعديل على القيود أو التسويات البنكية أو الأرصدة."), body_style),
        Paragraph(pdf_ar("الخط العربي المستخدم مدمج داخل ملف PDF لضمان عرض عربي كامل وواضح على أي جهاز."), small_style),
    ])
    document.build(story)


def hydrate_reconciliation(document: dict) -> dict:
    clean = {key: value for key, value in document.items() if key != "_id"}
    for field_name in ["created_at", "updated_at"]:
        if isinstance(clean.get(field_name), str):
            clean[field_name] = datetime.fromisoformat(clean[field_name])
    for list_name in ["outstanding_checks", "collection_checks", "prior_year_outstanding_checks"]:
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
    if clean.get("collection_method") in REVENUE_DIRECT_BANK_METHODS:
        clean["bank_collection_status"] = "collected"
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
    if clean.get("expense_category") == "deposit_link":
        clean["bank_payment_status"] = "paid"
    if clean.get("payment_method") in {"cash", "check", "bank_transfer"} and not clean.get("bank_payment_status"):
        clean["bank_payment_status"] = "not_presented"
    if clean.get("payment_method") == "check" and not clean.get("check_clearing_type"):
        clean["check_clearing_type"] = "internal"
    if clean.get("total_deductions") is None:
        clean["total_deductions"] = round(sum(float(item.get("amount") or 0) for item in clean.get("deductions") or []), 2)
    if clean.get("net_amount") is None:
        clean["net_amount"] = round(float(clean.get("gross_amount") or 0) - float(clean.get("total_deductions") or 0), 2)
    return clean


def hydrate_banking_manual_charges(document: dict) -> dict:
    clean = {key: value for key, value in document.items() if key != "_id"}
    if not clean.get("items"):
        legacy_labels = {
            "stamp": "دمغة",
            "bank_correspondence": "مراسلات بنكية",
            "correspondence_safekeeping": "حفظ مراسلات",
            "internal_transfer_fee": "رسوم تحويل داخلي",
            "external_transfer_fee": "رسوم تحويل خارجي",
        }
        clean["items"] = [
            {"statement": label, "count": 1, "amount": round(float(clean.get(key) or 0), 2), "total": round(float(clean.get(key) or 0), 2)}
            for key, label in legacy_labels.items()
            if float(clean.get(key) or 0) > 0
        ]
    else:
        clean["items"] = [
            {
                "statement": item.get("statement"),
                "count": round(float(item.get("count") or 1), 2),
                "amount": round(float(item.get("amount") or 0), 2),
                "total": round(float(item.get("total") if item.get("total") is not None else float(item.get("count") or 1) * float(item.get("amount") or 0)), 2),
            }
            for item in clean.get("items", [])
        ]
    if isinstance(clean.get("updated_at"), str):
        clean["updated_at"] = datetime.fromisoformat(clean["updated_at"])
    return clean


def hydrate_einvoice_document(document: dict) -> dict:
    clean = {key: value for key, value in document.items() if key != "_id"}
    for field_name in ["created_at", "updated_at"]:
        if isinstance(clean.get(field_name), str):
            clean[field_name] = datetime.fromisoformat(clean[field_name])
    if isinstance(clean.get("issue_date"), str):
        clean["issue_date"] = date.fromisoformat(clean["issue_date"])
    return clean


async def get_einvoice_settings_document() -> dict:
    document = await db.einvoice_settings.find_one(with_organization({"id": "default"}), {"_id": 0})
    if document:
        return document
    now = datetime.now(timezone.utc)
    return attach_organization({
        "id": "default",
        "organization_name": (await get_organization_document())["name"],
        "tax_registration_number": None,
        "address": None,
        "governorate": None,
        "activity_code": None,
        "default_tax_rate": 0,
        "auto_generate_from_collected_revenues": True,
        "updated_at": serialize_datetime(now),
    })


def validate_tax_profile_document(profile: dict) -> List[str]:
    errors = []
    if not str(profile.get("tax_registration_id") or "").strip():
        errors.append("رقم التسجيل الضريبي المصري غير مسجل")
    if not profile.get("tax_rules"):
        errors.append("لا توجد قواعد ضريبية مفعلة في ملف الجهة")
    document_types = profile.get("document_type_codes") or {}
    for invoice_type in ["sales", "purchase"]:
        if not document_types.get(invoice_type):
            errors.append(f"كود نوع المستند غير محدد لـ {invoice_type}")
    accounts = profile.get("journal_accounts") or {}
    for key in ["sales_debit", "sales_revenue", "sales_output_tax", "purchase_expense", "purchase_input_tax", "purchase_credit"]:
        if not accounts.get(key):
            errors.append(f"حساب القيد الضريبي غير محدد: {key}")
    return errors


def tax_profile_response(document: dict) -> TenantTaxProfileResponse:
    clean = hydrate_einvoice_document(document)
    clean.setdefault("id", "default")
    clean.setdefault("organization_id", organization_id_or_default())
    clean.setdefault("tax_rules", [])
    clean.setdefault("document_type_codes", {})
    clean.setdefault("journal_accounts", {})
    clean.setdefault("eta_payload_schema", {})
    clean.setdefault("auto_create_journal_on_approval", True)
    clean["configuration_errors"] = validate_tax_profile_document(clean)
    clean["is_configured"] = len(clean["configuration_errors"]) == 0
    return TenantTaxProfileResponse(**clean)


async def get_tax_profile_document() -> dict:
    document = await db.tax_profiles.find_one(with_organization({"id": "default"}), {"_id": 0})
    if document:
        return document
    now_iso = serialize_datetime(datetime.now(timezone.utc))
    organization = await get_organization_document()
    settings = await get_einvoice_settings_document()
    return attach_organization({
        "id": "default",
        "tax_registration_id": settings.get("tax_registration_number"),
        "taxpayer_name": settings.get("organization_name") or organization.get("name"),
        "country_code": "EG",
        "currency": "EGP",
        "eta_environment": "offline_ready",
        "tax_rules": [],
        "document_type_codes": {},
        "journal_accounts": {},
        "eta_payload_schema": {},
        "auto_create_journal_on_approval": True,
        "created_at": now_iso,
        "updated_at": now_iso,
    })


async def tax_engine_audit(action: str, description: str, current_user: Optional[dict], before: Optional[dict] = None, after: Optional[dict] = None):
    now_iso = serialize_datetime(datetime.now(timezone.utc))
    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "username": (current_user or {}).get("username") or "system",
        "actor_full_name": real_name_for_user(current_user or {}) if current_user else "Tax Engine",
        "user_id": (current_user or {}).get("id") or "system",
        "organization_id": organization_id_or_default(),
        "method": "SYSTEM",
        "path": "/system/tax-engine",
        "action": action,
        "arabic_description": description,
        "status_code": 200,
        "request_body": None,
        "before_document": before,
        "after_document": after,
        "ip_address": None,
        "created_at": now_iso,
    })


def select_tax_rule(profile: dict, *, invoice_type: str, item_code: str, tax_status: str, issue_date: date) -> dict:
    candidates = []
    for rule in profile.get("tax_rules") or []:
        effective_from = date.fromisoformat(rule["effective_from"]) if isinstance(rule.get("effective_from"), str) else rule.get("effective_from")
        effective_to = date.fromisoformat(rule["effective_to"]) if isinstance(rule.get("effective_to"), str) and rule.get("effective_to") else rule.get("effective_to")
        if effective_from and issue_date < effective_from:
            continue
        if effective_to and issue_date > effective_to:
            continue
        if rule.get("tax_status") != tax_status:
            continue
        if rule.get("item_code") not in {item_code, "*"}:
            continue
        if rule.get("invoice_type") and rule.get("invoice_type") != invoice_type:
            continue
        candidates.append(rule)
    exact = next((rule for rule in candidates if rule.get("item_code") == item_code), None)
    default = next((rule for rule in candidates if rule.get("is_default")), None)
    selected = exact or default or (candidates[0] if candidates else None)
    if not selected:
        raise HTTPException(status_code=400, detail=f"لا توجد قاعدة ضريبية في Tax Profile للكود {item_code} وحالة {tax_status}")
    return selected


def calculate_tax_invoice_from_profile(payload: TaxEngineInvoiceCreate, profile: dict) -> dict:
    errors = validate_tax_profile_document(profile)
    if errors:
        raise HTTPException(status_code=400, detail="ملف الضريبة للجهة غير مكتمل: " + "، ".join(errors))
    lines = []
    net_amount = 0.0
    tax_amount = 0.0
    for index, item in enumerate(payload.lines, 1):
        line_gross = round(float(item.quantity) * float(item.unit_price), 2)
        line_net = round(max(0.0, line_gross - float(item.discount_amount or 0)), 2)
        rule = select_tax_rule(profile, invoice_type=payload.invoice_type, item_code=item.item_code, tax_status=item.tax_status, issue_date=payload.issue_date)
        line_tax = round(line_net * float(rule.get("rate") or 0) / 100, 2)
        net_amount = round(net_amount + line_net, 2)
        tax_amount = round(tax_amount + line_tax, 2)
        lines.append({
            "line_number": index,
            "description": item.description,
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "discount_amount": item.discount_amount,
            "item_code": item.item_code,
            "tax_status": item.tax_status,
            "tax_rule_id": rule.get("id"),
            "tax_type": rule.get("tax_type"),
            "tax_rate": float(rule.get("rate") or 0),
            "line_net_amount": line_net,
            "line_tax_amount": line_tax,
            "line_total_amount": round(line_net + line_tax, 2),
        })
    return {
        "lines": lines,
        "net_amount": net_amount,
        "tax_amount": tax_amount,
        "total_amount": round(net_amount + tax_amount, 2),
        "tax_engine_snapshot": {
            "profile_id": profile.get("id"),
            "tax_registration_id": profile.get("tax_registration_id"),
            "currency": profile.get("currency"),
            "document_type_code": (profile.get("document_type_codes") or {}).get(payload.invoice_type),
            "eta_schema": profile.get("eta_payload_schema") or {},
            "rules_used": sorted({line["tax_rule_id"] for line in lines}),
            "calculation_mode": "config_driven_offline_eta_ready",
        },
    }


async def account_line_from_tax_profile(profile: dict, key: str, debit: float, credit: float, notes: str) -> dict:
    accounts = profile.get("journal_accounts") or {}
    account_ref = accounts.get(key)
    if not account_ref:
        raise HTTPException(status_code=400, detail=f"الحساب غير مضبوط في Tax Profile: {key}")
    query = {"is_active": True, "is_postable": True, "$or": [{"id": account_ref}, {"code": account_ref}, {"system_key": account_ref}, {"name": account_ref}]}
    account = await db.chart_accounts.find_one(with_organization(query), {"_id": 0})
    if not account:
        raise HTTPException(status_code=400, detail=f"حساب Tax Profile غير موجود في دليل الحسابات: {key}")
    return {"account_name": account.get("name"), "account_code": account.get("code"), "account_id": account.get("id"), "system_key": account.get("system_key"), "debit": round(debit, 2), "credit": round(credit, 2), "notes": notes}


async def approve_tax_engine_invoice(invoice: dict, profile: dict, current_user: dict) -> tuple[dict, dict]:
    if invoice.get("journal_entry_id"):
        existing = await db.journal_entries.find_one(with_organization({"id": invoice["journal_entry_id"]}), {"_id": 0})
        tax_entity = await db.tax_invoices.find_one(with_organization({"source_invoice_id": invoice["id"]}), {"_id": 0})
        return existing, tax_entity
    if not profile.get("auto_create_journal_on_approval", True):
        raise HTTPException(status_code=400, detail="إنشاء القيد التلقائي غير مفعل في Tax Profile")
    net_amount = round(float(invoice.get("net_amount") or 0), 2)
    tax_amount = round(float(invoice.get("tax_amount") or 0), 2)
    total_amount = round(float(invoice.get("total_amount") or 0), 2)
    invoice_type = invoice.get("invoice_type") or "sales"
    if invoice_type == "sales":
        lines = [
            await account_line_from_tax_profile(profile, "sales_debit", total_amount, 0, f"فاتورة ضريبية بيع {invoice.get('invoice_number')}") ,
            await account_line_from_tax_profile(profile, "sales_revenue", 0, net_amount, f"صافي فاتورة بيع {invoice.get('invoice_number')}") ,
            await account_line_from_tax_profile(profile, "sales_output_tax", 0, tax_amount, f"ضريبة مخرجات {invoice.get('invoice_number')}") ,
        ]
    else:
        lines = [
            await account_line_from_tax_profile(profile, "purchase_expense", net_amount, 0, f"صافي فاتورة شراء {invoice.get('invoice_number')}") ,
            await account_line_from_tax_profile(profile, "purchase_input_tax", tax_amount, 0, f"ضريبة مدخلات {invoice.get('invoice_number')}") ,
            await account_line_from_tax_profile(profile, "purchase_credit", 0, total_amount, f"فاتورة ضريبية شراء {invoice.get('invoice_number')}") ,
        ]
    journal = await save_journal_entry_document(entry_date=date.fromisoformat(invoice["issue_date"]) if isinstance(invoice.get("issue_date"), str) else invoice.get("issue_date"), description=f"قيد ضريبي تلقائي للفاتورة {invoice.get('invoice_number')}", lines=lines, reference=invoice.get("invoice_number"), source_type="tax_invoice", source_id=invoice.get("id"), is_auto=True, current_user=current_user, force_new=True)
    now_iso = serialize_datetime(datetime.now(timezone.utc))
    tax_entity = attach_organization({
        "id": str(uuid.uuid4()),
        "source_invoice_id": invoice["id"],
        "source_document_type": invoice.get("source_document_type"),
        "source_document_id": invoice.get("source_document_id") or invoice.get("revenue_id"),
        "journal_entry_id": journal.get("id"),
        "invoice_type": invoice_type,
        "eta_status": "offline_ready",
        "eta_payload_preview": build_eta_invoice_payload(invoice, await get_einvoice_settings_document(), await get_eta_integration_document()),
        "created_at": now_iso,
        "updated_at": now_iso,
    })
    await db.tax_invoices.insert_one(tax_entity.copy())
    await db.electronic_invoices.update_one(with_organization({"id": invoice["id"]}), {"$set": {"status": "ready", "journal_entry_id": journal.get("id"), "tax_invoice_entity_id": tax_entity["id"], "updated_at": now_iso}})
    return journal, tax_entity


def eta_urls(environment: str) -> dict:
    if environment == "production":
        return {
            "identity": "https://id.eta.gov.eg",
            "api": "https://api.invoicing.eta.gov.eg",
            "portal": "https://invoicing.eta.gov.eg",
        }
    return {
        "identity": "https://id.preprod.eta.gov.eg",
        "api": "https://api.preprod.invoicing.eta.gov.eg",
        "portal": "https://preprod.invoicing.eta.gov.eg",
    }


def eta_cipher() -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(JWT_SECRET.encode()).digest())
    return Fernet(key)


def eta_encrypt_secret(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return eta_cipher().encrypt(value.encode()).decode()


def eta_decrypt_secret(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        return eta_cipher().decrypt(value.encode()).decode()
    except InvalidToken:
        return None


def eta_required_items(document: dict) -> List[str]:
    required = []
    labels = {
        "issuer_tax_number": "الرقم الضريبي للجهة",
        "issuer_name": "اسم الممول/الجهة",
        "branch_code": "كود الفرع",
        "activity_code": "كود النشاط",
        "client_id": "Client ID من بوابة الضرائب",
        "client_secret_encrypted": "Client Secret من بوابة الضرائب",
        "sdk_command_template": "أمر SDK/أداة التوقيع الرقمي",
    }
    for key, label in labels.items():
        if not str(document.get(key) or "").strip():
            required.append(label)
    return required


def eta_public_response(document: dict) -> EtaIntegrationSettingsResponse:
    now_iso = serialize_datetime(datetime.now(timezone.utc))
    clean = {key: value for key, value in document.items() if key != "_id"}
    clean.setdefault("id", "default")
    clean.setdefault("environment", "preprod")
    clean.setdefault("updated_at", clean.get("created_at") or now_iso)
    clean["client_id"] = clean.get("client_id")
    clean["has_client_secret"] = bool(clean.get("client_secret_encrypted"))
    clean["has_token_pin"] = bool(clean.get("token_pin_encrypted"))
    clean["portal_url"] = clean.get("portal_url") or eta_urls(clean.get("environment", "preprod"))["portal"]
    clean["required_items"] = eta_required_items(clean)
    clean["is_configured"] = len(clean["required_items"]) == 0
    return EtaIntegrationSettingsResponse(**hydrate_einvoice_document(clean))


async def get_eta_integration_document() -> dict:
    document = await db.eta_integration_settings.find_one(with_organization({"id": "default"}), {"_id": 0})
    if document:
        return document
    now = serialize_datetime(datetime.now(timezone.utc))
    settings = await get_einvoice_settings_document()
    return attach_organization({
        "id": "default",
        "environment": "preprod",
        "issuer_tax_number": settings.get("tax_registration_number"),
        "issuer_name": settings.get("organization_name"),
        "branch_code": "0",
        "activity_code": settings.get("activity_code"),
        "client_id": None,
        "client_secret_encrypted": None,
        "sdk_command_template": None,
        "certificate_label": None,
        "token_pin_encrypted": None,
        "auto_submit_after_generation": False,
        "portal_url": eta_urls("preprod")["portal"],
        "notes": None,
        "last_connection_status": None,
        "last_connection_message": None,
        "created_at": now,
        "updated_at": now,
    })


def build_eta_invoice_payload(invoice: dict, settings: dict, config: dict) -> dict:
    uuid_source = f"{invoice.get('id')}|{invoice.get('invoice_number')}|{invoice.get('updated_at')}"
    internal_uuid = hashlib.sha256(uuid_source.encode()).hexdigest()
    snapshot = invoice.get("tax_engine_snapshot") or {}
    snapshot_lines = snapshot.get("lines") or []
    first_line = snapshot_lines[0] if snapshot_lines else {}
    currency = snapshot.get("currency") or "EGP"
    document_type_code = snapshot.get("document_type_code") or ((settings or {}).get("document_type_codes") or {}).get(invoice.get("invoice_type")) or invoice.get("invoice_type") or ""
    taxable_items = []
    if float(invoice.get("tax_amount") or 0) > 0:
        taxable_items.append({
            "taxType": first_line.get("tax_type") or config.get("default_tax_type") or "",
            "amount": float(invoice.get("tax_amount") or 0),
            "subType": first_line.get("tax_status") or "",
            "rate": float(first_line.get("tax_rate") or invoice.get("tax_rate") or 0),
        })
    return {
        "issuer": {
            "type": "B",
            "id": config.get("issuer_tax_number"),
            "name": config.get("issuer_name") or settings.get("organization_name"),
            "address": {"branchID": config.get("branch_code") or "0", "country": "EG", "governate": settings.get("governorate") or "", "regionCity": settings.get("address") or ""},
        },
        "receiver": {"type": "P", "id": invoice.get("customer_tax_number") or "", "name": invoice.get("customer_name")},
        "documentType": document_type_code,
        "documentTypeVersion": str((snapshot.get("eta_schema") or {}).get("documentTypeVersion") or "1.0"),
        "dateTimeIssued": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "taxpayerActivityCode": config.get("activity_code") or settings.get("activity_code") or "",
        "internalID": invoice.get("invoice_number"),
        "uuid": internal_uuid,
        "invoiceLines": [
            {
                "description": invoice.get("description"),
                "itemType": (snapshot.get("eta_schema") or {}).get("itemType") or "",
                "itemCode": first_line.get("item_code") or invoice.get("service_code") or "",
                "unitType": (snapshot.get("eta_schema") or {}).get("unitType") or "",
                "quantity": float(first_line.get("quantity") or 1),
                "unitValue": {"currencySold": currency, "amountEGP": float(first_line.get("unit_price") or invoice.get("net_amount") or 0)},
                "salesTotal": float(invoice.get("net_amount") or 0),
                "total": float(invoice.get("total_amount") or 0),
                "valueDifference": 0,
                "totalTaxableFees": 0,
                "netTotal": float(invoice.get("net_amount") or 0),
                "itemsDiscount": 0,
                "taxableItems": taxable_items,
            }
        ],
        "totalSalesAmount": float(invoice.get("net_amount") or 0),
        "totalDiscountAmount": 0,
        "netAmount": float(invoice.get("net_amount") or 0),
        "taxTotals": [{"taxType": item["taxType"], "amount": item["amount"]} for item in taxable_items],
        "totalAmount": float(invoice.get("total_amount") or 0),
        "extraDiscountAmount": 0,
        "totalItemsDiscountAmount": 0,
    }


def run_eta_sdk_signer(config: dict, payload: dict) -> dict:
    template = (config.get("sdk_command_template") or "").strip()
    if not template:
        raise HTTPException(status_code=400, detail="ضع أمر SDK/أداة التوقيع الرقمي أولاً قبل الإرسال الفعلي")
    with tempfile.TemporaryDirectory() as temp_dir:
        input_path = Path(temp_dir) / "invoice.json"
        output_path = Path(temp_dir) / "signed-invoice.json"
        input_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        command = template.format(input=shlex.quote(str(input_path)), output=shlex.quote(str(output_path)), pin=shlex.quote(eta_decrypt_secret(config.get("token_pin_encrypted")) or ""))
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=90)
        if result.returncode != 0:
            raise HTTPException(status_code=400, detail=f"فشل توقيع الفاتورة عبر SDK: {result.stderr or result.stdout or 'خطأ غير معروف'}")
        if not output_path.exists():
            raise HTTPException(status_code=400, detail="أداة SDK لم تُنشئ ملف الفاتورة الموقعة")
        return json.loads(output_path.read_text(encoding="utf-8"))


def eta_get_access_token(config: dict) -> str:
    client_secret = eta_decrypt_secret(config.get("client_secret_encrypted"))
    if not config.get("client_id") or not client_secret:
        raise HTTPException(status_code=400, detail="Client ID و Client Secret مطلوبان للاتصال بمنظومة الضرائب")
    token_url = eta_urls(config.get("environment", "preprod"))["identity"] + "/connect/token"
    data = urllib.parse.urlencode({"grant_type": "client_credentials", "client_id": config.get("client_id"), "client_secret": client_secret, "scope": "InvoicingAPI"}).encode()
    request = urllib.request.Request(token_url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            payload = json.loads(response.read().decode())
            token = payload.get("access_token")
            if not token:
                raise HTTPException(status_code=400, detail="لم يتم استلام access_token من منظومة الضرائب")
            return token
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"فشل الاتصال بخدمة هوية الضرائب: {exc}")


def eta_submit_signed_document(config: dict, signed_payload: dict) -> dict:
    token = eta_get_access_token(config)
    url = eta_urls(config.get("environment", "preprod"))["api"] + "/api/v1.0/documentsubmissions"
    body = json.dumps({"documents": [signed_payload]}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            return json.loads(response.read().decode())
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"فشل إرسال الفاتورة إلى منظومة الضرائب: {exc}")


async def get_default_service_code(settings: dict) -> dict:
    service = await db.einvoice_service_codes.find_one(with_organization({"is_default": True}), {"_id": 0})
    if service:
        return service
    raise HTTPException(status_code=400, detail="لا يوجد كود خدمة افتراضي مضبوط من إعدادات الجهة")


async def find_or_create_einvoice_customer(name: str) -> dict:
    clean_name = (name or "عميل غير محدد").strip() or "عميل غير محدد"
    customer = await db.einvoice_customers.find_one(with_organization({"name": clean_name}), {"_id": 0})
    if customer:
        return customer
    now = datetime.now(timezone.utc)
    customer = attach_organization({
        "id": str(uuid.uuid4()),
        "name": clean_name,
        "tax_number": None,
        "customer_type": "person",
        "address": None,
        "governorate": None,
        "phone": None,
        "email": None,
        "created_at": serialize_datetime(now),
        "updated_at": serialize_datetime(now),
    })
    await db.einvoice_customers.insert_one(customer.copy())
    return customer


def invoice_status_from_data(settings: dict, customer: dict, service: dict) -> tuple[str, List[str]]:
    notes = []
    if not settings.get("tax_registration_number"):
        notes.append("الرقم الضريبي للجهة غير مسجل")
    if not customer.get("tax_number") and customer.get("customer_type") != "person":
        notes.append("الرقم الضريبي للعميل غير مسجل")
    if not service.get("code"):
        notes.append("كود الخدمة غير مسجل")
    return ("needs_review" if notes else "ready"), notes


def approval_number_for_user(user: dict) -> str:
    username = user.get("username")
    if username == "admin":
        return "0103535"
    if username == "entryuser":
        return "028060"
    existing = user.get("approval_number")
    if existing:
        return str(existing)
    digest = hashlib.sha256((user.get("id") or username or str(uuid.uuid4())).encode()).hexdigest()
    return str(int(digest[:8], 16) % 9000000 + 1000000).zfill(7)


def real_name_for_user(user: dict) -> str:
    return user.get("full_name") or user.get("username") or "مستخدم النظام"


def validate_arabic_full_name(full_name: str) -> str:
    value = re.sub(r"\s+", " ", (full_name or "").strip())
    if len(value) < 3:
        raise HTTPException(status_code=400, detail="الاسم بالكامل باللغة العربية مطلوب")
    if not re.search(r"[\u0600-\u06FF]", value):
        raise HTTPException(status_code=400, detail="يجب إدخال الاسم بالكامل باللغة العربية")
    return value


def default_admin_full_name(username: str, organization_id: str) -> str:
    if username == "admin_union" or organization_id == "general-union":
        return "مدير النقابة العامة"
    return "مدير مشروع التكافل الاجتماعي"


def period_key(period_type: str, year: int, month: Optional[int] = None) -> str:
    return f"{period_type}-{year}-{month or 0}"


async def is_period_locked(target_date: date) -> Optional[dict]:
    year = target_date.year
    month = target_date.month
    yearly = await db.financial_periods.find_one(with_organization({"period_type": "yearly", "year": year, "is_locked": True}), {"_id": 0})
    if yearly:
        return yearly
    monthly = await db.financial_periods.find_one(with_organization({"period_type": "monthly", "year": year, "month": month, "is_locked": True}), {"_id": 0})
    return monthly


async def ensure_period_is_open(target_date: date):
    locked = await is_period_locked(target_date)
    if locked:
        label = f"{locked.get('year')}" if locked.get("period_type") == "yearly" else f"{locked.get('month')}/{locked.get('year')}"
        raise HTTPException(status_code=423, detail=f"الفترة المالية {label} مقفلة ولا يمكن تعديل بياناتها إلا بعد فتحها من المراجعة الأمنية")


def fernet_from_password(password: str, salt: bytes) -> Fernet:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=390000)
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return Fernet(key)


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
    if await db.revenues.find_one(with_organization({"receipt_number": receipt_number, **base_exclusion}), {"_id": 0, "id": 1}):
        raise HTTPException(status_code=400, detail="رقم الإذن موجود بالفعل ولا يمكن تكراره")

    if payload.collection_method == "cash":
        if not payload.supplier_name or not payload.supplier_name.strip():
            raise HTTPException(status_code=400, detail="يجب إدخال اسم الشخص الذي قام بالتوريد عند اختيار نقداً")
    elif payload.collection_method == "check":
        check_number = normalize_digit_text(payload.check_number)
        if not check_number or not check_number.isdigit():
            raise HTTPException(status_code=400, detail="يجب إدخال رقم شيك صحيح عند اختيار شيك")
        if await db.revenues.find_one(with_organization({"check_number": check_number, **base_exclusion}), {"_id": 0, "id": 1}):
            raise HTTPException(status_code=400, detail="رقم الشيك موجود بالفعل ولا يمكن تكراره")
    elif payload.collection_method == "payment_order":
        payment_order_number = normalize_digit_text(payload.payment_order_number)
        if payment_order_number:
            if not payment_order_number.isdigit():
                raise HTTPException(status_code=400, detail="رقم الدفع الإلكتروني يجب أن يكون أرقام فقط")
            if await db.revenues.find_one(with_organization({"payment_order_number": payment_order_number, **base_exclusion}), {"_id": 0, "id": 1}):
                raise HTTPException(status_code=400, detail="رقم الدفع الإلكتروني موجود بالفعل ولا يمكن تكراره")


async def revenue_document_from_payload(payload: RevenueCreate, revenue_id: Optional[str] = None) -> dict:
    bank = await ensure_bank_async(payload.bank_id)
    await ensure_revenue_unique(payload, revenue_id)
    await ensure_period_is_open(payload.issued_at)
    await ensure_bank_transaction_date_allowed(payload.bank_id, payload.issued_at)
    method = payload.collection_method
    return {
        "receipt_number": normalize_digit_text(payload.receipt_number),
        "organization_id": organization_id_or_default(),
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
        "bank_collection_status": "collected" if method in REVENUE_DIRECT_BANK_METHODS else (payload.bank_collection_status if method in ["cash", "check", "payment_order"] else None),
    }


async def ensure_expense_unique(payload: ExpenseCreate, expense_id: Optional[str] = None):
    expense_number = normalize_digit_text(payload.expense_number)
    if not expense_number or not expense_number.isdigit():
        raise HTTPException(status_code=400, detail="رقم الإذن يجب أن يكون أرقام فقط")
    base_exclusion = {"id": {"$ne": expense_id}} if expense_id else {}
    if await db.expenses.find_one(with_organization({"expense_number": expense_number, **base_exclusion}), {"_id": 0, "id": 1}):
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
        if await db.expenses.find_one(with_organization({"check_number": check_number, **base_exclusion}), {"_id": 0, "id": 1}):
            raise HTTPException(status_code=400, detail="رقم الشيك موجود بالفعل داخل المصروفات ولا يمكن تكراره")
    elif payload.payment_method == "bank_transfer":
        transfer_number = normalize_digit_text(payload.transfer_number)
        if not transfer_number or not transfer_number.isdigit():
            raise HTTPException(status_code=400, detail="يجب إدخال رقم عملية التحويل")
        if not payload.transfer_to or not payload.transfer_to.strip():
            raise HTTPException(status_code=400, detail="يجب إدخال اسم الجهة التي تم التحويل إليها")
        if await db.expenses.find_one(with_organization({"transfer_number": transfer_number, **base_exclusion}), {"_id": 0, "id": 1}):
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
    await ensure_period_is_open(payload.issued_at)
    await ensure_bank_transaction_date_allowed(payload.bank_id, payload.issued_at)
    deductions = [
        {"amount": round(float(item.amount), 2), "statement": item.statement.strip()}
        for item in payload.deductions
        if float(item.amount) > 0 or item.statement.strip()
    ]
    if payload.expense_category == "deposit_link":
        deductions = []
    total_deductions = round(sum(item["amount"] for item in deductions), 2)
    gross_amount = round(float(payload.gross_amount), 2)
    net_amount = round(gross_amount - total_deductions, 2)
    return {
        "expense_number": normalize_digit_text(payload.expense_number),
        "organization_id": organization_id_or_default(),
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
        "bank_payment_status": "paid" if payload.expense_category == "deposit_link" else (payload.bank_payment_status if payload.payment_method in ["cash", "check", "bank_transfer"] else None),
    }


async def fixed_asset_document_from_payload(payload: FixedAssetCreate, asset_id: Optional[str] = None) -> dict:
    bank = await ensure_bank_async(payload.bank_id)
    await ensure_period_is_open(payload.purchase_date)
    await ensure_bank_transaction_date_allowed(payload.bank_id, payload.purchase_date)
    organization_id = organization_id_or_default()
    category = await fixed_asset_category_with_rate(payload.category_code, organization_id)
    normalized_name = payload.asset_name.strip()
    if not normalized_name:
        raise HTTPException(status_code=400, detail="اسم الأصل الثابت مطلوب")
    existing_query = with_organization({"category_code": category["code"], "asset_name": normalized_name}, organization_id)
    if asset_id:
        existing_query["id"] = {"$ne": asset_id}
    if await db.fixed_assets.find_one(existing_query, {"_id": 0, "id": 1}):
        raise HTTPException(status_code=400, detail="هذا الأصل مسجل بالفعل داخل نفس التصنيف")
    serial = await db.fixed_assets.count_documents(with_organization({"category_code": category["code"]}, organization_id)) + 1
    asset_code = f"{category['code']}-{serial:03d}"
    if asset_id:
        current = await db.fixed_assets.find_one(with_organization({"id": asset_id}, organization_id), {"_id": 0, "asset_code": 1})
        asset_code = current.get("asset_code") if current else asset_code
    disposal_value = fixed_asset_disposal_date(payload.purchase_date, payload.purchase_cost, category["annual_depreciation_rate"])
    return {
        "organization_id": organization_id,
        "asset_code": asset_code,
        "category_code": category["code"],
        "category_name": category["name"],
        "annual_depreciation_rate": float(category["annual_depreciation_rate"]),
        "asset_name": normalized_name,
        "purchase_date": serialize_date(payload.purchase_date),
        "disposal_date": serialize_date(disposal_value) if disposal_value else None,
        "purchase_cost": round(float(payload.purchase_cost), 2),
        "bank_id": payload.bank_id,
        "bank_name": bank["name"],
        "invoice_number": normalize_digit_text(payload.invoice_number) if payload.invoice_number else None,
        "notes": payload.notes.strip() if payload.notes else None,
        "is_active": bool(payload.is_active),
    }


async def membership_document_from_payload(payload: MembershipCreate, membership_id: Optional[str] = None, existing_document: Optional[dict] = None) -> dict:
    require_social_solidarity_membership({"organization_id": organization_id_or_default()})
    organization_id = organization_id_or_default()
    membership_number = normalize_digit_text(payload.membership_number)
    national_id = normalize_digit_text(payload.national_id)
    if not membership_number:
        raise HTTPException(status_code=400, detail="رقم العضوية مطلوب")
    if not national_id.isdigit() or len(national_id) != 14:
        raise HTTPException(status_code=400, detail="الرقم القومي يجب أن يكون 14 رقم")
    exclusion = {"id": {"$ne": membership_id}} if membership_id else {}
    if await db.memberships.find_one(with_organization({"membership_number": membership_number, **exclusion}, organization_id), {"_id": 0, "id": 1}):
        raise HTTPException(status_code=400, detail="رقم العضوية موجود بالفعل")
    if await db.memberships.find_one(with_organization({"national_id": national_id, **exclusion}, organization_id), {"_id": 0, "id": 1}):
        raise HTTPException(status_code=400, detail="الرقم القومي موجود بالفعل")
    retirement = membership_retirement_fields(payload.birth_date)
    status = payload.status or "active"
    effective_date = payload.status_effective_date or parse_date_field((existing_document or {}).get("status_effective_date")) or date.today()
    existing_status = (existing_document or {}).get("status") or "active"
    subscription_start_date = parse_date_field((existing_document or {}).get("subscription_start_date")) or parse_date_field((existing_document or {}).get("created_at")) or date.today()
    previous_stop_date = parse_date_field((existing_document or {}).get("subscription_stop_date"))
    subscription_stop_date = None
    if status in NON_ACTIVE_MEMBERSHIP_STATUSES:
        subscription_stop_date = previous_stop_date if existing_status == status and previous_stop_date else effective_date
    return {
        "organization_id": organization_id,
        "governorate": normalize_member_text(payload.governorate),
        "union_committee": normalize_member_text(payload.union_committee),
        "membership_number": membership_number,
        "name": normalize_member_text(payload.name),
        "national_id": national_id,
        "birth_date": serialize_date(payload.birth_date),
        "address": normalize_member_text(payload.address),
        "death_beneficiary": normalize_member_text(payload.death_beneficiary),
        "status": status,
        "status_label": MEMBERSHIP_STATUS_LABELS.get(status, "فعال"),
        "status_effective_date": serialize_date(effective_date),
        "subscription_start_date": serialize_date(subscription_start_date),
        "subscription_stop_date": serialize_date(subscription_stop_date) if subscription_stop_date else None,
        "monthly_subscription_amount": MEMBERSHIP_MONTHLY_SUBSCRIPTION,
        **retirement,
    }


async def custody_advance_document_from_payload(payload: CustodyAdvanceCreate, document_id: Optional[str] = None) -> dict:
    bank = await ensure_bank_async(payload.bank_id)
    await ensure_period_is_open(payload.issue_date)
    await ensure_bank_transaction_date_allowed(payload.bank_id, payload.issue_date)
    organization_id = organization_id_or_default()
    if payload.due_date and payload.due_date < payload.issue_date:
        raise HTTPException(status_code=400, detail="تاريخ الاستحقاق لا يمكن أن يسبق تاريخ الصرف")
    serial = await db.custody_advances.count_documents(with_organization({}, organization_id)) + 1
    reference_number = f"AS-{serial:05d}"
    if document_id:
        current = await db.custody_advances.find_one(with_organization({"id": document_id}, organization_id), {"_id": 0, "reference_number": 1})
        reference_number = current.get("reference_number") if current else reference_number
    return {
        "organization_id": organization_id,
        "reference_number": reference_number,
        "transaction_type": payload.transaction_type,
        "recipient_name": normalize_member_text(payload.recipient_name),
        "issue_date": serialize_date(payload.issue_date),
        "amount": round(float(payload.amount), 2),
        "bank_id": payload.bank_id,
        "bank_name": bank["name"],
        "purpose": normalize_member_text(payload.purpose),
        "due_date": serialize_date(payload.due_date) if payload.due_date else None,
        "notes": normalize_member_text(payload.notes) if payload.notes else None,
        "settled_amount": 0,
        "remaining_amount": round(float(payload.amount), 2),
        "status": "open",
        "settlement_date": None,
        "settlement_type": None,
        "settlement_notes": None,
    }


def hydrate_custody_advance(document: dict) -> dict:
    clean = {key: value for key, value in document.items() if key != "_id"}
    for field_name in ["issue_date", "due_date", "settlement_date"]:
        if isinstance(clean.get(field_name), str):
            clean[field_name] = date.fromisoformat(clean[field_name])
    for field_name in ["created_at", "updated_at"]:
        if isinstance(clean.get(field_name), str):
            clean[field_name] = datetime.fromisoformat(clean[field_name])
    clean["settled_amount"] = round(float(clean.get("settled_amount") or 0), 2)
    clean["remaining_amount"] = round(max(float(clean.get("amount") or 0) - clean["settled_amount"], 0), 2)
    clean["status"] = "settled" if clean["remaining_amount"] <= 0 else ("partial" if clean["settled_amount"] > 0 else "open")
    return clean


def calculate_reconciliation(payload: BankReconciliationCreate) -> dict:
    total_prior_year_outstanding = round(sum(item.amount for item in payload.prior_year_outstanding_checks), 2)
    total_outstanding = round(sum(item.amount for item in payload.outstanding_checks) + total_prior_year_outstanding, 2)
    total_collection = round(sum(item.amount for item in payload.collection_checks), 2)
    calculated_balance = round(payload.book_balance + total_outstanding - total_collection, 2)
    difference = round(calculated_balance - payload.bank_statement_balance, 2)
    is_matched = abs(difference) < 0.01
    return {
        "total_outstanding_checks": total_outstanding,
        "total_collection_checks": total_collection,
        "total_prior_year_outstanding_checks": total_prior_year_outstanding,
        "calculated_balance": calculated_balance,
        "difference": difference,
        "is_matched": is_matched,
        "status_text": "الرصيد مطابق" if is_matched else "الرصيد غير مطابق",
    }


def hydrate_user(document: dict) -> dict:
    clean = {key: value for key, value in document.items() if key not in {"_id", "password_hash", "totp_secret", "totp_pending_secret"}}
    clean["full_name"] = clean.get("full_name") or default_admin_full_name(clean.get("username", ""), clean.get("organization_id", DEFAULT_ORGANIZATION_ID)) if clean.get("role") in ["admin", "super_admin"] else clean.get("full_name") or "مستخدم النظام"
    clean["organization_id"] = clean.get("organization_id") or DEFAULT_ORGANIZATION_ID
    clean["organization_name"] = clean.get("organization_name") or ORGANIZATIONS.get(clean["organization_id"], ORGANIZATIONS[DEFAULT_ORGANIZATION_ID])["name"]
    clean["organization_modules"] = normalize_modules(clean["organization_id"], clean.get("organization_modules"))
    for field_name in ["created_at", "updated_at"]:
        if isinstance(clean.get(field_name), str):
            clean[field_name] = datetime.fromisoformat(clean[field_name])
    return clean


def is_super_admin(user: dict) -> bool:
    return user.get("role") == "super_admin" or (user.get("username") == ADMIN_USERNAME and user.get("is_super_admin"))


async def user_query_for_admin(admin_user: dict, base_query: Optional[dict] = None) -> dict:
    query = dict(base_query or {})
    if is_super_admin(admin_user):
        query["role"] = {"$ne": "super_admin"}
        return query
    query.update(with_organization({"role": {"$ne": "super_admin"}}, admin_user.get("organization_id")))
    return query


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
        "organization_id": user.get("organization_id") or DEFAULT_ORGANIZATION_ID,
        "purpose": purpose,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=minutes)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def login_attempt_identifier(username: str, organization_id: str) -> str:
    return f"{organization_id}:{username.strip().lower()}"


async def ensure_login_not_locked(username: str, organization_id: str):
    attempt = await db.login_attempts.find_one({"identifier": login_attempt_identifier(username, organization_id)}, {"_id": 0})
    if not attempt or not attempt.get("locked_until"):
        return
    locked_until = datetime.fromisoformat(attempt["locked_until"])
    if locked_until > datetime.now(timezone.utc):
        raise HTTPException(status_code=429, detail="تم تعطيل الدخول على هذا الجهاز لمدة ٣ دقائق بسبب إدخال كلمة السر خطأ أكثر من ٣ مرات. حاول مرة أخرى بعد انتهاء المدة.")
    await db.login_attempts.delete_one({"identifier": attempt["identifier"]})


async def record_failed_login(username: str, organization_id: str):
    identifier = login_attempt_identifier(username, organization_id)
    now = datetime.now(timezone.utc)
    attempt = await db.login_attempts.find_one({"identifier": identifier}, {"_id": 0}) or {"count": 0}
    count = int(attempt.get("count", 0)) + 1
    update = {"identifier": identifier, "username": username.strip(), "organization_id": organization_id, "count": count, "updated_at": serialize_datetime(now)}
    if count >= LOGIN_LOCKOUT_FAILED_ATTEMPTS:
        update["locked_until"] = serialize_datetime(now + timedelta(minutes=LOGIN_LOCKOUT_MINUTES))
    await db.login_attempts.update_one({"identifier": identifier}, {"$set": update, "$setOnInsert": {"created_at": serialize_datetime(now)}}, upsert=True)


async def clear_failed_login(username: str, organization_id: str):
    await db.login_attempts.delete_one({"identifier": login_attempt_identifier(username, organization_id)})


async def get_login_user(username: str, organization_id: str) -> Optional[dict]:
    if username == ADMIN_USERNAME:
        super_admin = await db.users.find_one(
            {"username": ADMIN_USERNAME, "$or": [{"role": "super_admin"}, {"is_super_admin": True}]},
            {"_id": 0},
        )
        if super_admin:
            return super_admin
    return await db.users.find_one({"username": username, "organization_id": organization_id}, {"_id": 0})


async def disable_two_factor_for_all_users():
    now_iso = serialize_datetime(datetime.now(timezone.utc))
    await db.users.update_many(
        {},
        {
            "$set": {
                "totp_enabled": False,
                "totp_secret": None,
                "totp_pending_secret": None,
                "updated_at": now_iso,
            }
        },
    )


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
    if is_super_admin(user):
        selected_organization_id = payload.get("organization_id") or DEFAULT_ORGANIZATION_ID
        organization = await get_organization_document(selected_organization_id)
        user["organization_id"] = selected_organization_id
        user["organization_name"] = organization["name"]
        user["organization_modules"] = normalize_modules(selected_organization_id, organization.get("modules"))
    else:
        user["organization_id"] = user.get("organization_id") or DEFAULT_ORGANIZATION_ID
    CURRENT_ORGANIZATION_ID.set(user["organization_id"])
    return user


async def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user.get("role") not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="هذه الصفحة للأدمن فقط")
    return current_user


async def require_super_admin(current_user: dict = Depends(get_current_user)) -> dict:
    if not is_super_admin(current_user):
        raise HTTPException(status_code=403, detail="هذه الصفحة متاحة لحساب السوبر أدمن admin فقط")
    return current_user


@api_router.get("/app-settings/public", response_model=AppSettingsResponse)
async def get_public_app_settings():
    document = await get_app_settings_document()
    return await build_app_settings_response(document)


@api_router.get("/organizations/public", response_model=List[OrganizationResponse])
async def list_public_organizations():
    return [OrganizationResponse(**document) for document in await list_organization_documents()]


@api_router.get("/app-settings/icon")
async def get_app_icon():
    document = await db.app_settings.find_one({"id": "global"}, {"_id": 0, "icon_base64": 1})
    icon_b64 = (document or {}).get("icon_base64")
    if not icon_b64:
        raise HTTPException(status_code=404, detail="لا توجد أيقونة مخصصة")
    return Response(content=base64.b64decode(icon_b64), media_type="image/x-icon")


@api_router.get("/admin/app-settings", response_model=AppSettingsResponse)
async def get_admin_app_settings(admin_user: dict = Depends(require_admin)):
    document = await get_app_settings_document()
    organization = await get_organization_document(admin_user.get("organization_id"))
    document["organization_name"] = organization["name"]
    document["organization_login_label"] = organization["login_label"]
    return await build_app_settings_response(document)


@api_router.put("/admin/app-settings", response_model=AppSettingsResponse)
async def update_admin_app_settings(payload: AppSettingsUpdate, admin_user: dict = Depends(require_super_admin)):
    now_iso = serialize_datetime(datetime.now(timezone.utc))
    system_name = payload.system_name.strip()
    if len(system_name) < 2:
        raise HTTPException(status_code=400, detail="اسم النظام مطلوب")
    organization_id = admin_user.get("organization_id") or DEFAULT_ORGANIZATION_ID
    await db.app_settings.update_one(
        {"id": "global"},
        {"$set": {"system_name": system_name, "updated_at": now_iso}, "$setOnInsert": {"id": "global", "created_at": now_iso}},
        upsert=True,
    )
    if payload.organization_name is not None:
        organization_name = payload.organization_name.strip()
        if len(organization_name) < 2:
            raise HTTPException(status_code=400, detail="اسم الجهة مطلوب")
        await db.organizations.update_one(
            {"id": organization_id},
            {"$set": {"name": organization_name, "updated_at": now_iso}, "$setOnInsert": {"id": organization_id, "login_label": ORGANIZATIONS.get(organization_id, {}).get("login_label", organization_name), "created_at": now_iso}},
            upsert=True,
        )
        await db.users.update_many({"organization_id": organization_id}, {"$set": {"organization_name": organization_name, "updated_at": now_iso}})
    if payload.organization_login_label is not None:
        login_label = payload.organization_login_label.strip()
        if len(login_label) < 2:
            raise HTTPException(status_code=400, detail="اسم الجهة المختصر مطلوب")
        await db.organizations.update_one(
            {"id": organization_id},
            {"$set": {"login_label": login_label, "updated_at": now_iso}, "$setOnInsert": {"id": organization_id, "name": ORGANIZATIONS.get(organization_id, {}).get("name", login_label), "created_at": now_iso}},
            upsert=True,
        )
    if payload.organization_names:
        for org_id, org_name_value in payload.organization_names.items():
            org_name = (org_name_value or "").strip()
            if len(org_name) < 2:
                raise HTTPException(status_code=400, detail="اسم الجهة مطلوب")
            await db.organizations.update_one(
                {"id": org_id},
                {"$set": {"name": org_name, "updated_at": now_iso}, "$setOnInsert": {"id": org_id, "login_label": ORGANIZATIONS.get(org_id, {}).get("login_label", org_name), "created_at": now_iso}},
                upsert=True,
            )
            await db.users.update_many({"organization_id": org_id}, {"$set": {"organization_name": org_name, "updated_at": now_iso}})
    if payload.organization_login_labels:
        for org_id, label_value in payload.organization_login_labels.items():
            login_label = (label_value or "").strip()
            if len(login_label) < 2:
                raise HTTPException(status_code=400, detail="اسم الجهة المختصر مطلوب")
            await db.organizations.update_one(
                {"id": org_id},
                {"$set": {"login_label": login_label, "updated_at": now_iso}, "$setOnInsert": {"id": org_id, "name": ORGANIZATIONS.get(org_id, {}).get("name", login_label), "created_at": now_iso}},
                upsert=True,
            )
    if payload.organization_emails:
        for org_id, email_value in payload.organization_emails.items():
            email = (email_value or "").strip() or None
            await db.organizations.update_one({"id": org_id}, {"$set": {"email": email, "updated_at": now_iso}, "$setOnInsert": {"id": org_id, "name": ORGANIZATIONS.get(org_id, {}).get("name", org_id), "login_label": ORGANIZATIONS.get(org_id, {}).get("login_label", org_id), "created_at": now_iso}}, upsert=True)
    app_updates = {}
    if payload.login_union_logo_visible is not None:
        app_updates["login_union_logo_visible"] = payload.login_union_logo_visible
    if payload.login_union_logo_data_url is not None:
        app_updates["login_union_logo_data_url"] = payload.login_union_logo_data_url or None
    if payload.login_authority_logos is not None:
        app_updates["login_authority_logos"] = payload.login_authority_logos
    if payload.backup_enabled is not None:
        app_updates["backup_enabled"] = payload.backup_enabled
    if payload.backup_allowed_roles is not None:
        app_updates["backup_allowed_roles"] = {role: bool(payload.backup_allowed_roles.get(role)) for role in ["super_admin", "admin", "user"]}
    if payload.two_factor_role_policy is not None:
        app_updates["two_factor_role_policy"] = {role: bool(payload.two_factor_role_policy.get(role)) for role in ["super_admin", "admin", "user"]}
    if payload.include_tech_stack_in_manual is not None:
        app_updates["include_tech_stack_in_manual"] = payload.include_tech_stack_in_manual
    if payload.hide_ai_attribution is not None:
        app_updates["hide_ai_attribution"] = payload.hide_ai_attribution
    if payload.intellectual_property_owner is not None:
        app_updates["intellectual_property_owner"] = payload.intellectual_property_owner.strip() or None
    if payload.intellectual_property_national_id is not None:
        app_updates["intellectual_property_national_id"] = payload.intellectual_property_national_id.strip() or None
    if payload.intellectual_property_fingerprint is not None:
        app_updates["intellectual_property_fingerprint"] = payload.intellectual_property_fingerprint.strip() or None
    if payload.installed_files_lock_enabled is not None:
        app_updates["installed_files_lock_enabled"] = payload.installed_files_lock_enabled
    if payload.session_timeout_minutes is not None:
        app_updates["session_timeout_minutes"] = payload.session_timeout_minutes
    if app_updates:
        app_updates["updated_at"] = now_iso
        await db.app_settings.update_one({"id": "global"}, {"$set": app_updates, "$setOnInsert": {"id": "global", "created_at": now_iso}}, upsert=True)
    document = await get_app_settings_document()
    organization = await get_organization_document(organization_id)
    document["organization_name"] = organization["name"]
    document["organization_login_label"] = organization["login_label"]
    return await build_app_settings_response(document)


@api_router.get("/admin/organization/modules", response_model=OrganizationModulesResponse)
async def get_admin_organization_modules(organization_id: Optional[str] = Query(default=None), admin_user: dict = Depends(require_admin)):
    target_organization_id = admin_user.get("organization_id") or DEFAULT_ORGANIZATION_ID
    if organization_id and admin_user.get("role") == "super_admin":
        target_organization_id = organization_id
    elif organization_id and organization_id != target_organization_id:
        raise HTTPException(status_code=403, detail="لا يمكنك تعديل خواص جهة أخرى")
    organization = await get_organization_document(target_organization_id)
    return build_organization_modules_response(organization)


@api_router.put("/admin/organization/modules", response_model=OrganizationModulesResponse)
async def update_admin_organization_modules(payload: OrganizationModulesUpdate, organization_id: Optional[str] = Query(default=None), admin_user: dict = Depends(require_admin)):
    target_organization_id = admin_user.get("organization_id") or DEFAULT_ORGANIZATION_ID
    if organization_id and admin_user.get("role") == "super_admin":
        target_organization_id = organization_id
    elif organization_id and organization_id != target_organization_id:
        raise HTTPException(status_code=403, detail="لا يمكنك تعديل خواص جهة أخرى")
    organization_id = target_organization_id
    organization = await get_organization_document(organization_id)
    before_modules = normalize_modules(organization_id, organization.get("modules"))
    next_modules = normalize_modules(organization_id, payload.modules)
    now_iso = serialize_datetime(datetime.now(timezone.utc))
    await db.organizations.update_one(
        {"id": organization_id},
        {"$set": {"modules": next_modules, "updated_at": now_iso}, "$setOnInsert": {"id": organization_id, "name": organization["name"], "login_label": organization["login_label"], "created_at": now_iso}},
        upsert=True,
    )
    await db.users.update_many({"organization_id": organization_id}, {"$set": {"organization_modules": next_modules, "updated_at": now_iso}})
    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "username": admin_user.get("username"),
        "actor_full_name": real_name_for_user(admin_user),
        "user_id": admin_user.get("id"),
        "organization_id": organization_id,
        "method": "PUT",
        "path": "/admin/organization/modules",
        "action": "ORGANIZATION_MODULES_UPDATED",
        "arabic_description": f"تم تحديث إعدادات خواص الجهة {organization.get('name')} بعزل كامل، ومنها الفاتورة الإلكترونية إن وُجدت.",
        "status_code": 200,
        "request_body": None,
        "before_document": {"modules": before_modules},
        "after_document": {"modules": next_modules},
        "ip_address": None,
        "created_at": now_iso,
    })
    updated = await get_organization_document(organization_id)
    return build_organization_modules_response(updated)


@api_router.post("/admin/organizations", response_model=OrganizationResponse)
async def create_custom_organization(payload: OrganizationCreate, _: dict = Depends(require_super_admin)):
    base_id = re.sub(r"[^a-z0-9-]", "-", (payload.id or payload.login_label or payload.name).strip().lower()).strip("-") or f"org-{uuid.uuid4().hex[:8]}"
    org_id = base_id
    suffix = 2
    while await db.organizations.find_one({"id": org_id}, {"_id": 0}) or org_id in ORGANIZATIONS:
        org_id = f"{base_id}-{suffix}"
        suffix += 1
    clone_source = await get_organization_document(payload.clone_from or DEFAULT_ORGANIZATION_ID)
    now_iso = serialize_datetime(datetime.now(timezone.utc))
    document = {
        "id": org_id,
        "name": payload.name.strip(),
        "login_label": (payload.login_label or payload.name).strip(),
        "email": (payload.email or "").strip() or None,
        "modules": normalize_modules(org_id, clone_source.get("modules")),
        "is_active": True,
        "created_at": now_iso,
        "updated_at": now_iso,
    }
    await db.organizations.insert_one(document.copy())
    return OrganizationResponse(**document)


@api_router.put("/admin/organizations/{organization_id}", response_model=OrganizationResponse)
async def update_custom_organization(organization_id: str, payload: OrganizationUpdate, _: dict = Depends(require_super_admin)):
    organization = await get_organization_document(organization_id)
    updates = {"updated_at": serialize_datetime(datetime.now(timezone.utc))}
    if payload.name is not None:
        updates["name"] = payload.name.strip()
    if payload.login_label is not None:
        updates["login_label"] = payload.login_label.strip()
    if payload.email is not None:
        updates["email"] = (payload.email or "").strip() or None
    if payload.is_active is not None:
        updates["is_active"] = payload.is_active
    if payload.modules is not None:
        updates["modules"] = normalize_modules(organization_id, payload.modules)
    await db.organizations.update_one({"id": organization_id}, {"$set": updates, "$setOnInsert": {"id": organization_id, "name": organization["name"], "login_label": organization["login_label"], "created_at": updates["updated_at"]}}, upsert=True)
    if "name" in updates or "modules" in updates:
        user_updates = {"updated_at": updates["updated_at"]}
        if "name" in updates:
            user_updates["organization_name"] = updates["name"]
        if "modules" in updates:
            user_updates["organization_modules"] = updates["modules"]
        await db.users.update_many({"organization_id": organization_id}, {"$set": user_updates})
    return OrganizationResponse(**await get_organization_document(organization_id))


@api_router.get("/admin/fixed-assets/categories", response_model=List[FixedAssetCategory])
async def admin_list_fixed_asset_categories(_: dict = Depends(require_admin)):
    return [FixedAssetCategory(**category) for category in await list_fixed_asset_categories_with_catalog()]


@api_router.put("/admin/fixed-assets/categories/{category_code}", response_model=FixedAssetCategory)
async def admin_update_fixed_asset_category_rate(category_code: str, payload: FixedAssetCategoryRateUpdate, _: dict = Depends(require_admin)):
    category = fixed_asset_category(category_code)
    organization_id = organization_id_or_default()
    now_iso = serialize_datetime(datetime.now(timezone.utc))
    document = {"id": f"{organization_id}-{category['code']}", "organization_id": organization_id, "code": category["code"], "annual_depreciation_rate": float(payload.annual_depreciation_rate), "updated_at": now_iso}
    await db.fixed_asset_category_settings.update_one(with_organization({"code": category["code"]}, organization_id), {"$set": document, "$setOnInsert": {"created_at": now_iso}}, upsert=True)
    updated = next(item for item in await list_fixed_asset_categories_with_catalog(organization_id) if item["code"] == category["code"])
    return FixedAssetCategory(**updated)


@api_router.post("/admin/app-settings/icon", response_model=AppSettingsResponse)
async def update_admin_app_icon(icon_file: UploadFile = File(...), _: dict = Depends(require_admin)):
    content = await icon_file.read()
    icon_bytes = convert_uploaded_icon_to_ico(content, icon_file.filename or "icon", icon_file.content_type)
    now_iso = serialize_datetime(datetime.now(timezone.utc))
    await db.app_settings.update_one(
        {"id": "global"},
        {
            "$set": {
                "icon_base64": base64.b64encode(icon_bytes).decode("ascii"),
                "shortcut_icon_updated_at": now_iso,
                "updated_at": now_iso,
            },
            "$setOnInsert": {"id": "global", "system_name": DEFAULT_SYSTEM_NAME, "created_at": now_iso},
        },
        upsert=True,
    )
    await sync_local_app_icon_cache()
    shortcut_status = update_windows_shortcut_icon(APP_ICON_PATH)
    await db.app_settings.update_one({"id": "global"}, {"$set": {"shortcut_update_status": shortcut_status, "updated_at": now_iso}})
    document = await get_app_settings_document()
    return await build_app_settings_response(document)


def require_permission(permission_name: str):
    async def checker(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user.get("role") in ["admin", "super_admin"]:
            return current_user
        permissions = current_user.get("permissions", {})
        if not permissions.get(permission_name, False):
            raise HTTPException(status_code=403, detail="ليس لديك صلاحية لتنفيذ هذه العملية")
        return current_user

    return checker


async def require_einvoice_enabled(current_user: dict = Depends(get_current_user)) -> dict:
    organization = await get_organization_document(current_user.get("organization_id"))
    if not normalize_modules(organization["id"], organization.get("modules")).get("electronic_invoice", True):
        raise HTTPException(status_code=404, detail="الفاتورة الإلكترونية غير متاحة لمشروع التكافل الاجتماعي")
    return current_user


async def require_einvoice_admin(current_user: dict = Depends(require_admin)) -> dict:
    organization = await get_organization_document(current_user.get("organization_id"))
    if not normalize_modules(organization["id"], organization.get("modules")).get("electronic_invoice", True):
        raise HTTPException(status_code=404, detail="الفاتورة الإلكترونية غير متاحة لمشروع التكافل الاجتماعي")
    return current_user


def require_einvoice_permission(permission_names: List[str]):
    async def checker(current_user: dict = Depends(require_any_permission(permission_names))) -> dict:
        organization = await get_organization_document(current_user.get("organization_id"))
        if not normalize_modules(organization["id"], organization.get("modules")).get("electronic_invoice", True):
            raise HTTPException(status_code=404, detail="الفاتورة الإلكترونية غير متاحة لمشروع التكافل الاجتماعي")
        return current_user

    return checker


def require_any_permission(permission_names: List[str]):
    async def checker(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user.get("role") in ["admin", "super_admin"]:
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
    # طريقة البنك: دورات شهرية من يوم إنشاء الوديعة لنفس اليوم الشهر التالي (٢١←٢١)،
    # الفائدة اليومية مقرّبة لقرشين، مع إضافة فرق التقريب على قيد إتمام السنة (شهر الإنشاء)
    # حتى يساوي إجمالي كل سنة كاملة العائد السنوي المظبوط.
    creation = normalize_datetime(deposit.creation_datetime).date()
    maturity = normalize_datetime(deposit.maturity_datetime).date()
    annual_interest = deposit.amount * deposit.monthly_interest_rate / 100
    use_rounding = getattr(deposit, "use_daily_rounding", True)
    daily_interest = round(annual_interest / days_in_year(year), 2) if use_rounding else annual_interest / days_in_year(year)
    anniversary_day = creation.day

    def anniversary_on(y: int, m: int) -> date:
        last_day = calendar.monthrange(y, m)[1]
        return date(y, m, min(anniversary_day, last_day))

    rows = []
    total = 0.0
    for month in range(1, 13):
        credit_date = anniversary_on(year, month)
        prev_credit_date = anniversary_on(year - 1, 12) if month == 1 else anniversary_on(year, month - 1)
        period_start = max(prev_credit_date, creation)
        period_end = min(credit_date, maturity)

        if period_end <= period_start:
            active_days = 0
            interest = 0.0
        else:
            active_days = (period_end - period_start).days
            interest = round(daily_interest * active_days, 2)
            # قيد إتمام السنة (شهر إنشاء الوديعة): يأخذ فرق التقريب ليساوي إجمالي السنة العائد السنوي
            # يُطبَّق فقط عند تفعيل التقريب؛ عند إلغاء التقريب نستخدم الرقم الكامل بلا تسوية (زي البنك للشهادات)
            if use_rounding and month == creation.month:
                year_start = anniversary_on(year - 1, creation.month)
                if year_start >= creation and credit_date <= maturity:
                    full_year_days = (credit_date - year_start).days
                    adjustment = round(annual_interest - daily_interest * full_year_days, 2)
                    interest = round(interest + adjustment, 2)

        total += interest
        rows.append(
            InterestRow(
                serial=month,
                month=ARABIC_MONTHS[month - 1],
                month_number=month,
                interest_amount=round(interest, 2),
                active_days=float(active_days),
            )
        )

    return rows, round(annual_interest, 2), round(total, 2)


def calculate_deposit_interest_for_period(deposit: Deposit, period_from: date, period_to: date) -> float:
    start = normalize_datetime(deposit.accounting_start_datetime or deposit.creation_datetime)
    end = normalize_datetime(deposit.maturity_datetime)
    period_start = datetime.combine(period_from, datetime.min.time(), tzinfo=timezone.utc)
    period_end = datetime.combine(period_to + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
    overlap_start = max(start, period_start)
    overlap_end = min(end, period_end)
    if overlap_end <= overlap_start:
        return 0.0
    annual_interest = deposit.amount * deposit.monthly_interest_rate / 100
    daily_base = annual_interest / days_in_year(period_from.year)
    daily_interest = round(daily_base, 2) if getattr(deposit, "use_daily_rounding", True) else daily_base
    active_days = (overlap_end - overlap_start).total_seconds() / 86400
    return round(daily_interest * active_days, 2)


def deposit_principal_start_date(deposit: Deposit) -> date:
    return normalize_datetime(deposit.creation_datetime).date()


def deposit_principal_maturity_date(deposit: Deposit) -> date:
    return normalize_datetime(deposit.maturity_datetime).date()


def deposit_is_active_in_period(deposit: Deposit, period_from: date, period_to: date) -> bool:
    return deposit_principal_start_date(deposit) <= period_to and deposit_principal_maturity_date(deposit) > period_from


def deposit_is_active_as_of(deposit: Deposit, as_of: date) -> bool:
    return deposit_principal_start_date(deposit) <= as_of < deposit_principal_maturity_date(deposit)


async def active_deposit_principal_total(organization_id: str, as_of: Optional[date], bank_id: Optional[str] = None) -> float:
    if not as_of:
        return 0.0
    as_of_start = datetime.combine(as_of, datetime.min.time(), tzinfo=timezone.utc).isoformat()
    as_of_end = datetime.combine(as_of + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc).isoformat()
    query_body = {
        "creation_datetime": {"$lt": as_of_end},
        "maturity_datetime": {"$gt": as_of_start},
        "status": {"$ne": "closed"},
    }
    if bank_id:
        query_body["bank_id"] = bank_id
    documents = await db.deposits.find(with_organization(query_body, organization_id), {"_id": 0, "amount": 1}).to_list(100000)
    return round(sum(float(item.get("amount") or 0) for item in documents), 2)


async def should_show_term_deposits_in_trial_balance(organization_id: str, report_to_date: Optional[date]) -> bool:
    if not report_to_date:
        return False
    day_start = datetime.combine(report_to_date, datetime.min.time(), tzinfo=timezone.utc).isoformat()
    day_end = datetime.combine(report_to_date + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc).isoformat()
    return await db.deposits.count_documents(with_organization({"maturity_datetime": {"$gte": day_start, "$lt": day_end}}, organization_id)) > 0


def entry_has_term_deposit_principal(entry: dict) -> bool:
    if entry.get("source_type") == "deposit":
        return True
    for line in entry.get("lines", []):
        if str(line.get("account_code") or "") == "1250" or str(line.get("account_name") or "") == "ودائع لأجل":
            return True
    return False


async def active_deposits_for_period(bank_id: str, period_from: date, period_to: date) -> List[Deposit]:
    period_start_iso = datetime.combine(period_from, datetime.min.time(), tzinfo=timezone.utc).isoformat()
    period_end_iso = datetime.combine(period_to + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc).isoformat()
    documents = await db.deposits.find(with_organization({
        "bank_id": bank_id,
        "creation_datetime": {"$lt": period_end_iso},
        "maturity_datetime": {"$gt": period_start_iso},
        "status": {"$ne": "closed"},
    }), {"_id": 0}).sort("creation_datetime", 1).to_list(100000)
    return [Deposit(**hydrate_deposit(document)) for document in documents]


async def generate_deposit_renewal_note(previous_deposit: dict, new_deposit: Deposit) -> str:
    return (
        f"تم إعادة ربط الوديعة رقم {previous_deposit.get('deposit_number')} "
        f"بتاريخ {new_deposit.creation_datetime.date().isoformat().replace('-', '/')} "
        f"كوديعة جديدة رقم {new_deposit.deposit_number} بمبلغ {round(float(new_deposit.amount), 2)} "
        f"ومعدل فائدة {round(float(new_deposit.monthly_interest_rate), 4)}%."
    )


async def calculate_total_deposit_interest_for_period(organization_id: str, period_from: Optional[date], period_to: Optional[date], bank_id: Optional[str] = None) -> float:
    if not period_from or not period_to:
        return 0.0
    period_start_iso = datetime.combine(period_from, datetime.min.time(), tzinfo=timezone.utc).isoformat()
    period_end_iso = datetime.combine(period_to + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc).isoformat()
    query_body = {
        "maturity_datetime": {"$gt": period_start_iso},
        "status": {"$ne": "closed"},
        "$or": [
            {"accounting_start_datetime": {"$lt": period_end_iso}},
            {"creation_datetime": {"$lt": period_end_iso}},
        ],
    }
    if bank_id:
        query_body["bank_id"] = bank_id
    query = with_organization(query_body, organization_id)
    documents = await db.deposits.find(query, {"_id": 0}).to_list(100000)
    total = 0.0
    for document in documents:
        total = round(total + calculate_deposit_interest_for_period(Deposit(**hydrate_deposit(document)), period_from, period_to), 2)
    return total


def deposit_interest_report_total(deposit: Deposit, period_from: date, period_to: date) -> float:
    # يطابق "كشف العوائد التفريجي": فائدة كل شهر تُحسب على الدورة الشهرية للوديعة (تاريخ الأساس)
    # وليس على أيام الشهر الميلادي. نجمع فوائد كل شهر يقع ضمن [period_from, period_to].
    creation = normalize_datetime(deposit.creation_datetime).date()
    year, month = period_from.year, period_from.month
    if year < creation.year:
        year, month = creation.year, 1
    rows_by_year: dict[int, list] = {}
    total = 0.0
    while (year < period_to.year) or (year == period_to.year and month <= period_to.month):
        if year not in rows_by_year:
            rows_by_year[year] = calculate_interest_rows(deposit, year)[0]
        for row in rows_by_year[year]:
            if row.month_number == month:
                total = round(total + float(row.interest_amount or 0), 2)
                break
        month += 1
        if month > 12:
            month = 1
            year += 1
    return total


async def reconciliation_deposit_interest_for_period(organization_id: str, period_from: Optional[date], period_to: Optional[date], bank_id: Optional[str] = None) -> float:
    # نسخة مخصّصة للتسوية البنكية تطابق كشف العوائد التفريجي (الدورة الشهرية للوديعة)
    if not period_from or not period_to:
        return 0.0
    period_start_iso = datetime.combine(period_from, datetime.min.time(), tzinfo=timezone.utc).isoformat()
    period_end_iso = datetime.combine(period_to + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc).isoformat()
    query_body = {
        "maturity_datetime": {"$gt": period_start_iso},
        "status": {"$ne": "closed"},
        "$or": [
            {"accounting_start_datetime": {"$lt": period_end_iso}},
            {"creation_datetime": {"$lt": period_end_iso}},
        ],
    }
    if bank_id:
        query_body["bank_id"] = bank_id
    documents = await db.deposits.find(with_organization(query_body, organization_id), {"_id": 0}).to_list(100000)
    total = 0.0
    for document in documents:
        total = round(total + deposit_interest_report_total(Deposit(**hydrate_deposit(document)), period_from, period_to), 2)
    return total



def calculate_daily_interest_amount(deposit: Deposit, year: int) -> tuple[float, float]:
    annual_interest = deposit.amount * deposit.monthly_interest_rate / 100
    daily_base = annual_interest / days_in_year(year)
    daily_interest = round(daily_base, 2) if getattr(deposit, "use_daily_rounding", True) else daily_base
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
    creation_day = normalize_datetime(deposit.accounting_start_datetime or deposit.creation_datetime).date()
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
        "daily_interest_amount": round(daily_interest, 2),
        "last_payment_date": last_payment_day.isoformat(),
        "accrued_until_date": period_end.isoformat(),
        "accrued_days": accrued_days,
        "accrued_interest_amount": accrued_interest,
    }


async def get_deposit_or_latest(bank_id: str, deposit_id: Optional[str] = None) -> Deposit:
    await ensure_bank_async(bank_id)
    query = with_organization({"bank_id": bank_id})
    if deposit_id:
        query["id"] = deposit_id

    cursor = db.deposits.find(query, {"_id": 0}).sort("created_at", -1)
    document = await cursor.to_list(1)
    if not document:
        raise HTTPException(status_code=404, detail="لا توجد وديعة مسجلة لهذا البنك")
    return Deposit(**hydrate_deposit(document[0]))


async def get_bank_deposits(bank_id: str) -> List[Deposit]:
    await ensure_bank_async(bank_id)
    documents = await db.deposits.find(with_organization({"bank_id": bank_id}), {"_id": 0}).sort("created_at", -1).to_list(1000)
    return [Deposit(**hydrate_deposit(document)) for document in documents]


def calculate_year_total(deposit: Deposit, year: int) -> float:
    rows, _, total = calculate_interest_rows(deposit, year)
    return round(sum(row.interest_amount for row in rows), 2) if rows else total


def statement_period_bounds(period_type: str, year: int, month: int) -> tuple[date, date]:
    if period_type == "monthly":
        return month_bounds(year, month)
    return date(year, 1, 1), date(year, 12, 31)


def calculate_previous_years(deposit: Deposit, current_year: int) -> tuple[List[PreviousYearBreakdown], float]:
    start_year = normalize_datetime(deposit.accounting_start_datetime or deposit.creation_datetime).year
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
    try:
        await db.users.drop_index("username_1")
    except Exception:
        pass
    await db.users.update_many({"organization_id": {"$exists": False}}, {"$set": {"organization_id": DEFAULT_ORGANIZATION_ID, "organization_name": ORGANIZATIONS[DEFAULT_ORGANIZATION_ID]["name"]}})
    await db.users.update_many({"role": "admin", "full_name": {"$exists": False}}, {"$set": {"full_name": "مدير النظام"}})
    await db.users.update_many({"role": {"$ne": "admin"}, "full_name": {"$exists": False}}, {"$set": {"full_name": "مستخدم النظام"}})
    await db.users.create_index([("organization_id", 1), ("username", 1)], unique=True)
    await ensure_organization_seed_data()
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
    admin_accounts = [
        (ADMIN_USERNAME, DEFAULT_ORGANIZATION_ID, "super_admin"),
        ("admin_takaful", "social-solidarity", "admin"),
        ("admin_union", "general-union", "admin"),
    ]
    for username, organization_id, role in admin_accounts:
        organization = await get_organization_document(organization_id)
        existing = await db.users.find_one({"username": username, "organization_id": organization_id}, {"_id": 0})
        document = {
            "username": username,
            "full_name": existing.get("full_name") if existing and existing.get("full_name") else default_admin_full_name(username, organization_id),
            "organization_id": organization_id,
            "organization_name": organization["name"],
            "organization_modules": normalize_modules(organization_id, organization.get("modules")),
            "role": role,
            "is_super_admin": role == "super_admin",
            "permissions": admin_permissions,
            "is_active": True,
            "totp_enabled": False,
            "totp_secret": None,
            "totp_pending_secret": None,
            "must_change_password": existing.get("must_change_password", True) if existing else True,
            "updated_at": serialize_datetime(now),
        }
        if existing:
            if not verify_password(ADMIN_INITIAL_PASSWORD, existing.get("password_hash", "")):
                document["password_hash"] = hash_password(ADMIN_INITIAL_PASSWORD)
                document["must_change_password"] = True
            await db.users.update_one({"id": existing["id"]}, {"$set": document})
            continue
        document.update({"id": str(uuid.uuid4()), "password_hash": hash_password(ADMIN_INITIAL_PASSWORD), "created_at": serialize_datetime(now)})
        await db.users.insert_one(document)
    await db.login_attempts.delete_many({"identifier": {"$in": [login_attempt_identifier(ADMIN_USERNAME, org_id) for org_id in ORGANIZATIONS]}})


async def ensure_organization_seed_data():
    now_iso = serialize_datetime(datetime.now(timezone.utc))
    for organization in ORGANIZATIONS.values():
        await db.organizations.update_one(
            {"id": organization["id"]},
            {"$setOnInsert": {**organization, "modules": default_modules_for_organization(organization["id"]), "created_at": now_iso, "updated_at": now_iso}},
            upsert=True,
        )
        existing = await db.organizations.find_one({"id": organization["id"]}, {"_id": 0})
        modules = normalize_modules(organization["id"], existing.get("modules") if existing else None)
        await db.organizations.update_one({"id": organization["id"]}, {"$set": {"modules": modules}})
        await db.users.update_many({"organization_id": organization["id"]}, {"$set": {"organization_modules": modules}})
    tenant_collections = ["banks", "bank_settings", "deleted_banks", "deposits", "revenues", "expenses", "fixed_assets", "fixed_asset_depreciations", "fixed_asset_catalog_items", "fixed_asset_catalog_hidden", "fixed_asset_category_settings", "custody_advances", "memberships", "membership_import_previews", "membership_batch_payments", "reconciliations", "banking_manual_charges", "banking_tariffs", "electronic_invoices", "einvoice_settings", "einvoice_customers", "einvoice_service_codes", "financial_periods", "report_approvals", "audit_logs"]
    for collection_name in tenant_collections:
        await db[collection_name].update_many({"organization_id": {"$exists": False}}, {"$set": {"organization_id": DEFAULT_ORGANIZATION_ID}})
    for organization_id in ORGANIZATIONS:
        await sync_chart_accounts_for_organization(organization_id)


@app.on_event("startup")
async def startup_tasks():
    await ensure_default_admin()
    try:
        await db.revenues.drop_index("receipt_number_1")
    except Exception:
        pass
    await db.revenues.create_index([("organization_id", 1), ("receipt_number", 1)], unique=True)
    await db.revenues.create_index([("organization_id", 1), ("check_number", 1)])
    await db.revenues.create_index([("organization_id", 1), ("payment_order_number", 1)])
    await db.expenses.create_index("expense_number")
    await db.expenses.create_index("check_number")
    await db.expenses.create_index("transfer_number")
    await db.fixed_assets.create_index([("organization_id", 1), ("category_code", 1), ("asset_name", 1)])
    await db.fixed_asset_depreciations.create_index([("organization_id", 1), ("asset_id", 1), ("year", 1), ("month", 1)], unique=True)
    await db.fixed_asset_catalog_items.create_index([("organization_id", 1), ("category_code", 1), ("name", 1)], unique=True)
    await db.fixed_asset_catalog_hidden.create_index([("organization_id", 1), ("category_code", 1), ("name", 1)], unique=True)
    await db.fixed_asset_category_settings.create_index([("organization_id", 1), ("code", 1)], unique=True)
    await db.custody_advances.create_index([("organization_id", 1), ("reference_number", 1)], unique=True)
    await db.memberships.create_index([("organization_id", 1), ("membership_number", 1)], unique=True)
    await db.memberships.create_index([("organization_id", 1), ("national_id", 1)], unique=True)
    await db.memberships.create_index([("organization_id", 1), ("retirement_year", 1), ("retirement_month", 1)])
    await db.membership_import_previews.create_index([("organization_id", 1), ("id", 1)], unique=True)
    await db.membership_batch_payments.create_index([("organization_id", 1), ("payment_date", -1)])
    await db.login_attempts.create_index("identifier", unique=True)
    # Notifications module — strictly informational, never alters accounting state.
    try:
        await ensure_notification_indexes(db)
        if _APSCHEDULER_AVAILABLE and deposit_notification_scheduler is not None:
            schedule_daily_scan(deposit_notification_scheduler, db, run_now=True)
            if not deposit_notification_scheduler.running:
                deposit_notification_scheduler.start()
        else:
            from deposit_notifications import scan_and_create_notifications as _scan_once  # type: ignore
            await _scan_once(db)
    except Exception as notif_error:
        logging.getLogger("deposit_notifications").error("init failed: %s", notif_error)

# Add your routes to the router instead of directly to app
@api_router.get("/health")
async def health_check():
    return {"status": "ok", "service": "bank-deposit-system"}


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
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0", "Pragma": "no-cache", "Expires": "0"},
    )


@api_router.post("/auth/login", response_model=AuthResponse)
async def login(payload: LoginRequest, response: Response):
    organization_id = payload.organization_id.strip()
    try:
        selected_login_org = await get_organization_document(organization_id)
    except HTTPException:
        raise HTTPException(status_code=400, detail="اختر جهة صحيحة قبل تسجيل الدخول")
    await ensure_login_not_locked(payload.username, organization_id)
    username = payload.username.strip()
    user = await get_login_user(username, organization_id)
    if not user or not verify_password(payload.password, user.get("password_hash", "")):
        await record_failed_login(payload.username, organization_id)
        raise HTTPException(status_code=401, detail="اسم المستخدم أو كلمة المرور غير صحيحة")
    if not user.get("is_active", False):
        raise HTTPException(status_code=403, detail="هذا المستخدم غير نشط")

    token_user = user.copy()
    if is_super_admin(token_user):
        organization = selected_login_org
        token_user["organization_id"] = organization_id
        token_user["organization_name"] = organization["name"]
        token_user["organization_modules"] = normalize_modules(organization_id, organization.get("modules"))

    app_settings = await get_app_settings_document()
    two_factor_policy = app_settings.get("two_factor_role_policy") or {"super_admin": False, "admin": False, "user": False}
    if two_factor_policy.get(token_user.get("role")) and user.get("totp_enabled"):
        if not payload.otp_code:
            return AuthResponse(
                requires_2fa=True,
                temp_token=create_access_token(token_user, purpose="2fa", minutes=5),
                message="أدخل كود Google Authenticator لإكمال الدخول",
            )
        secret = user.get("totp_secret")
        if not secret or not pyotp.TOTP(secret).verify(payload.otp_code, valid_window=1):
            await record_failed_login(payload.username, organization_id)
            raise HTTPException(status_code=401, detail="كود المصادقة الثنائية غير صحيح")

    token = create_access_token(token_user)
    await clear_failed_login(payload.username, organization_id)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=480 * 60,
        path="/",
    )
    return AuthResponse(
        token=token,
        user=public_user(token_user),
        requires_2fa_setup=bool(two_factor_policy.get(token_user.get("role"))) and not user.get("totp_enabled", False),
        message="تم تسجيل الدخول بنجاح",
    )


@api_router.get("/auth/me", response_model=UserPublic)
async def get_me(current_user: dict = Depends(get_current_user)):
    return public_user(current_user)


@api_router.get("/admin/users", response_model=List[UserPublic])
async def list_users(admin_user: dict = Depends(require_super_admin)):
    users = await db.users.find(await user_query_for_admin(admin_user), {"_id": 0}).sort("organization_id", 1).sort("created_at", -1).to_list(1000)
    return [public_user(user) for user in users]


@api_router.post("/admin/users", response_model=UserPublic)
async def create_user(payload: UserCreate, admin_user: dict = Depends(require_super_admin)):
    organization_id = payload.organization_id if is_super_admin(admin_user) and payload.organization_id else admin_user.get("organization_id") or DEFAULT_ORGANIZATION_ID
    try:
        organization = await get_organization_document(organization_id)
    except HTTPException:
        raise HTTPException(status_code=400, detail="الجهة غير صحيحة")
    role = payload.role if is_super_admin(admin_user) else "user"
    if role == "admin" and not is_super_admin(admin_user):
        raise HTTPException(status_code=403, detail="إضافة أدمن متاحة للسوبر أدمن فقط")
    existing = await db.users.find_one({"username": payload.username.strip(), "organization_id": organization_id}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail="اسم المستخدم موجود بالفعل")
    now = datetime.now(timezone.utc)
    document = {
        "id": str(uuid.uuid4()),
        "username": payload.username.strip(),
        "full_name": validate_arabic_full_name(payload.full_name),
        "organization_id": organization_id,
        "organization_name": organization["name"],
        "organization_modules": normalize_modules(organization_id, organization.get("modules")),
        "password_hash": hash_password(payload.password),
        "role": role,
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
async def update_user(user_id: str, payload: UserUpdate, admin_user: dict = Depends(require_super_admin)):
    query = {"id": user_id} if is_super_admin(admin_user) else with_organization({"id": user_id}, admin_user.get("organization_id"))
    user = await db.users.find_one(query, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    if is_super_admin(user):
        raise HTTPException(status_code=403, detail="لا يمكن تعديل حساب السوبر أدمن من هنا")
    if user.get("role") == "admin" and user.get("id") != admin_user.get("id"):
        if not is_super_admin(admin_user):
            raise HTTPException(status_code=403, detail="لا يمكن تعديل أدمن آخر")

    updates = {"updated_at": serialize_datetime(datetime.now(timezone.utc))}
    if payload.full_name is not None:
        updates["full_name"] = validate_arabic_full_name(payload.full_name)
    if payload.password:
        updates["password_hash"] = hash_password(payload.password)
        updates["must_change_password"] = False
    if payload.role is not None:
        updates["role"] = payload.role
    if payload.permissions is not None:
        updates["permissions"] = payload.permissions.model_dump()
    if payload.is_active is not None:
        updates["is_active"] = payload.is_active

    await db.users.update_one(query, {"$set": updates})
    updated = await db.users.find_one(query, {"_id": 0})
    return public_user(updated)


@api_router.put("/admin/profile", response_model=UserPublic)
async def update_admin_profile(payload: AdminProfileUpdate, admin_user: dict = Depends(require_admin)):
    updates = {"full_name": validate_arabic_full_name(payload.full_name), "updated_at": serialize_datetime(datetime.now(timezone.utc))}
    query = {"id": admin_user["id"]} if is_super_admin(admin_user) else with_organization({"id": admin_user["id"]}, admin_user.get("organization_id"))
    await db.users.update_one(query, {"$set": updates})
    updated = await db.users.find_one(query, {"_id": 0})
    if not updated:
        raise HTTPException(status_code=404, detail="الحساب غير موجود")
    if is_super_admin(updated):
        selected_organization = await get_organization_document(admin_user.get("organization_id") or DEFAULT_ORGANIZATION_ID)
        updated["organization_id"] = selected_organization["id"]
        updated["organization_name"] = selected_organization["name"]
        updated["organization_modules"] = normalize_modules(selected_organization["id"], selected_organization.get("modules"))
    return public_user(updated)


@api_router.delete("/admin/users/{user_id}")
async def delete_user(user_id: str, admin_user: dict = Depends(require_super_admin)):
    query = {"id": user_id} if is_super_admin(admin_user) else with_organization({"id": user_id}, admin_user.get("organization_id"))
    user = await db.users.find_one(query, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    if is_super_admin(user) or user.get("id") == admin_user.get("id"):
        raise HTTPException(status_code=403, detail="لا يمكن حذف حساب السوبر أدمن")
    if user.get("role") == "admin" and not is_super_admin(admin_user):
        raise HTTPException(status_code=403, detail="حذف الأدمن متاح للسوبر أدمن فقط")
    result = await db.users.delete_one(query)
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
    settings = await get_app_settings_document()
    policy = settings.get("two_factor_role_policy") or {"super_admin": False, "admin": False, "user": False}
    if not policy.get(admin_user.get("role")):
        raise HTTPException(status_code=403, detail="خدمة Google Authenticator غير مفعلة لهذا النوع من الحسابات")
    secret = pyotp.random_base32()
    otpauth_uri = pyotp.TOTP(secret).provisioning_uri(name=admin_user["username"], issuer_name="Bank Deposit Interest System")
    image = qrcode.make(otpauth_uri)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    qr_data_url = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("utf-8")
    await db.users.update_one({"id": admin_user["id"]}, {"$set": {"totp_pending_secret": secret, "updated_at": serialize_datetime(datetime.now(timezone.utc))}})
    return TwoFactorSetupResponse(otpauth_uri=otpauth_uri, qr_data_url=qr_data_url, manual_secret=secret)


@api_router.post("/admin/2fa/verify", response_model=UserPublic)
async def verify_admin_2fa(payload: TwoFactorVerifyRequest, admin_user: dict = Depends(require_admin)):
    secret = admin_user.get("totp_pending_secret") or admin_user.get("totp_secret")
    if not secret:
        raise HTTPException(status_code=400, detail="ابدأ إعداد المصادقة الثنائية أولاً")
    if not pyotp.TOTP(secret).verify(payload.otp_code, valid_window=1):
        raise HTTPException(status_code=400, detail="كود التحقق غير صحيح")
    await db.users.update_one({"id": admin_user["id"]}, {"$set": {"totp_secret": secret, "totp_enabled": True, "totp_pending_secret": None, "updated_at": serialize_datetime(datetime.now(timezone.utc))}})
    updated = await db.users.find_one({"id": admin_user["id"]}, {"_id": 0})
    return public_user(updated)


@api_router.post("/admin/2fa/disable", response_model=UserPublic)
async def disable_current_user_2fa(admin_user: dict = Depends(require_admin)):
    await db.users.update_one({"id": admin_user["id"]}, {"$set": {"totp_secret": None, "totp_pending_secret": None, "totp_enabled": False, "updated_at": serialize_datetime(datetime.now(timezone.utc))}})
    updated = await db.users.find_one({"id": admin_user["id"]}, {"_id": 0})
    return public_user(updated)


@api_router.get("/banks", response_model=List[Bank])
async def get_banks(_: dict = Depends(get_current_user)):
    return await get_all_banks()


@api_router.post("/admin/banks", response_model=Bank)
async def create_bank(payload: BankCreate, current_user: dict = Depends(require_admin)):
    organization_id = organization_id_or_default()
    bank_id_base = slugify_bank_name(payload.name)
    bank_id = bank_id_base
    suffix = 1
    while BANKS.get(bank_id) or await db.banks.find_one(with_organization({"id": bank_id}, organization_id), {"_id": 0}):
        suffix += 1
        bank_id = f"{bank_id_base}-{suffix}"

    now = datetime.now(timezone.utc)
    bank_doc = {
        "id": bank_id,
        "organization_id": organization_id,
        "name": payload.name.strip(),
        "short_name": (payload.code or payload.name[:3]).strip().upper(),
        "code": (payload.code or bank_id.upper()).strip().upper(),
        "swift_code": payload.swift_code.strip().upper() if payload.swift_code else None,
        "logo_url": payload.logo_url.strip() if payload.logo_url else None,
        "color": payload.color or "#0f172a",
        "opening_balance": round(float(payload.opening_balance or 0), 2),
        "opening_balance_date": serialize_date(payload.opening_balance_date),
        "created_at": serialize_datetime(now),
        "updated_at": serialize_datetime(now),
    }
    await db.banks.insert_one(bank_doc)
    default_tariff = build_tariff_document(bank_doc, default_tariff_rules(bank_id), notes="تعريفة افتراضية لبنك جديد لحين رفع ملف التعريفة", status="default")
    default_tariff = attach_organization(default_tariff, organization_id)
    await db.banking_tariffs.update_one(
        with_organization({"bank_id": bank_id, "account_type": "companies"}, organization_id),
        {"$set": default_tariff},
        upsert=True,
    )
    await journal_for_bank_opening_balance(bank_doc, bank_doc["opening_balance"], current_user)
    return Bank(**{key: value for key, value in bank_doc.items() if key not in {"created_at", "updated_at"}})


@api_router.put("/admin/banks/{bank_id}/opening-balance", response_model=Bank)
async def update_bank_opening_balance(bank_id: str, payload: BankOpeningBalanceUpdate, current_user: dict = Depends(require_admin)):
    organization_id = organization_id_or_default()
    bank = await ensure_bank_async(bank_id)
    opening_balance = round(float(payload.opening_balance or 0), 2)
    opening_balance_date = payload.opening_balance_date
    await ensure_opening_balance_date_not_after_existing_transactions(bank_id, opening_balance_date)
    now = datetime.now(timezone.utc)
    await db.bank_settings.update_one(
        with_organization({"bank_id": bank_id}, organization_id),
        {"$set": {"bank_id": bank_id, "organization_id": organization_id, "opening_balance": opening_balance, "opening_balance_date": serialize_date(opening_balance_date), "updated_at": serialize_datetime(now)}},
        upsert=True,
    )
    if await db.banks.find_one(with_organization({"id": bank_id}, organization_id), {"_id": 0}):
        await db.banks.update_one(with_organization({"id": bank_id}, organization_id), {"$set": {"opening_balance": opening_balance, "opening_balance_date": serialize_date(opening_balance_date), "updated_at": serialize_datetime(now)}})
    bank["opening_balance"] = opening_balance
    bank["opening_balance_date"] = serialize_date(opening_balance_date)
    await journal_for_bank_opening_balance(bank, opening_balance, current_user)
    return Bank(**{key: value for key, value in bank.items() if key not in {"created_at", "updated_at"}})


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
        with_organization({"bank_id": bank_id, "account_type": "companies"}),
        {"$set": attach_organization(document)},
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
            with_organization({"bank_id": bank_id, "account_type": "companies"}),
            {"$set": attach_organization(document)},
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
            with_organization({"bank_id": bank_id, "account_type": "companies"}),
            {"$set": attach_organization(document)},
            upsert=True,
        )
        return BankingTariffResponse(**hydrate_banking_manual_charges(document))


@api_router.delete("/admin/banks/{bank_id}")
async def delete_bank(bank_id: str, _: dict = Depends(require_admin)):
    organization_id = organization_id_or_default()
    bank = BANKS.get(bank_id) or await db.banks.find_one(with_organization({"id": bank_id}, organization_id), {"_id": 0})
    if not bank:
        raise HTTPException(status_code=404, detail="البنك غير موجود")

    now = datetime.now(timezone.utc)
    await db.deleted_banks.update_one(
        with_organization({"id": bank_id}, organization_id),
        {"$set": {"id": bank_id, "organization_id": organization_id, "name": bank.get("name"), "deleted_at": serialize_datetime(now)}},
        upsert=True,
    )
    await db.banks.delete_one(with_organization({"id": bank_id}, organization_id))
    await db.banking_tariffs.delete_many(with_organization({"bank_id": bank_id}, organization_id))
    deposits_result = await db.deposits.delete_many(with_organization({"bank_id": bank_id}, organization_id))
    reconciliations_result = await db.reconciliations.delete_many(with_organization({"bank_id": bank_id}, organization_id))
    revenues_result = await db.revenues.delete_many(with_organization({"bank_id": bank_id}, organization_id))
    expenses_result = await db.expenses.delete_many(with_organization({"bank_id": bank_id}, organization_id))
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
    current_user: dict = Depends(require_permission("enter_deposits")),
):
    bank = await ensure_bank_async(bank_id)
    creation_datetime = normalize_datetime(payload.creation_datetime)
    maturity_datetime = normalize_datetime(payload.maturity_datetime)
    opening_date = parse_date_field(bank.get("opening_balance_date"))
    is_opening_balance_deposit = bool(payload.is_opening_balance_deposit)
    accounting_start_datetime = creation_datetime
    if is_opening_balance_deposit:
        if not opening_date:
            raise HTTPException(status_code=400, detail="يجب تحديد تاريخ الرصيد الافتتاحي للبنك قبل تسجيل وديعة قائمة أول الفترة")
        if maturity_datetime.date() <= opening_date:
            raise HTTPException(status_code=400, detail="الوديعة القائمة أول الفترة يجب أن يكون تاريخ استحقاقها بعد تاريخ الرصيد الافتتاحي")
        accounting_start_datetime = datetime.combine(opening_date, datetime.min.time(), tzinfo=timezone.utc)
        await ensure_period_is_open(opening_date)
    else:
        await ensure_period_is_open(creation_datetime.date())
        await ensure_bank_transaction_date_allowed(bank_id, creation_datetime.date())

    if maturity_datetime <= creation_datetime:
        raise HTTPException(status_code=400, detail="تاريخ الاستحقاق يجب أن يكون بعد تاريخ إنشاء الوديعة")

    renewed_from_deposit_id = (payload.renewed_from_deposit_id or "").strip() or None
    previous_deposit = None
    if renewed_from_deposit_id:
        previous_deposit = await db.deposits.find_one(with_organization({"id": renewed_from_deposit_id, "bank_id": bank_id}), {"_id": 0})
        if not previous_deposit:
            raise HTTPException(status_code=404, detail="الوديعة السابقة المختارة للتجديد غير موجودة")
        previous_maturity_value = previous_deposit.get("maturity_datetime")
        if isinstance(previous_maturity_value, str):
            previous_maturity_value = datetime.fromisoformat(previous_maturity_value)
        previous_maturity = normalize_datetime(previous_maturity_value)
        if creation_datetime.date() < previous_maturity.date():
            raise HTTPException(status_code=400, detail="لا يمكن إعادة ربط الوديعة قبل تاريخ استحقاق الوديعة السابقة")

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
        is_opening_balance_deposit=is_opening_balance_deposit,
        accounting_start_datetime=accounting_start_datetime,
        renewed_from_deposit_id=renewed_from_deposit_id,
        renewal_notes=(payload.renewal_notes or "").strip() or None,
        status="active",
        created_at=now,
        updated_at=now,
    )
    if previous_deposit:
        deposit.renewal_notes = deposit.renewal_notes or await generate_deposit_renewal_note(previous_deposit, deposit)
    document = deposit.model_dump()
    attach_organization(document)
    for field_name in ["creation_datetime", "maturity_datetime", "accounting_start_datetime", "created_at", "updated_at"]:
        document[field_name] = serialize_datetime(document[field_name])

    await db.deposits.insert_one(document)
    if previous_deposit:
        await db.deposits.update_one(
            with_organization({"id": previous_deposit.get("id"), "bank_id": bank_id}),
            {"$set": {"status": "renewed", "renewal_notes": deposit.renewal_notes, "updated_at": serialize_datetime(now)}},
        )
    await journal_for_deposit_principal(document, current_user)
    await journal_for_deposit_interest(document, current_user)
    return deposit


@api_router.get("/banks/{bank_id}/deposits", response_model=List[Deposit])
async def list_deposits(bank_id: str, _: dict = Depends(require_permission("view_reports"))):
    await ensure_bank_async(bank_id)
    documents = await db.deposits.find(with_organization({"bank_id": bank_id}), {"_id": 0}).sort("created_at", -1).to_list(500)
    return [Deposit(**hydrate_deposit(document)) for document in documents]


@api_router.get("/banks/{bank_id}/deposits/latest", response_model=Deposit)
async def get_latest_deposit(bank_id: str, _: dict = Depends(require_permission("view_reports"))):
    return await get_deposit_or_latest(bank_id)


@api_router.put("/banks/{bank_id}/deposits/{deposit_id}", response_model=Deposit)
async def update_deposit(
    bank_id: str,
    deposit_id: str,
    payload: DepositCreate,
    current_user: dict = Depends(require_permission("edit_deposits")),
):
    bank = await ensure_bank_async(bank_id)
    creation_datetime = normalize_datetime(payload.creation_datetime)
    maturity_datetime = normalize_datetime(payload.maturity_datetime)
    opening_date = parse_date_field(bank.get("opening_balance_date"))
    is_opening_balance_deposit = bool(payload.is_opening_balance_deposit)
    accounting_start_datetime = creation_datetime
    if is_opening_balance_deposit:
        if not opening_date:
            raise HTTPException(status_code=400, detail="يجب تحديد تاريخ الرصيد الافتتاحي للبنك قبل تسجيل وديعة قائمة أول الفترة")
        if maturity_datetime.date() <= opening_date:
            raise HTTPException(status_code=400, detail="الوديعة القائمة أول الفترة يجب أن يكون تاريخ استحقاقها بعد تاريخ الرصيد الافتتاحي")
        accounting_start_datetime = datetime.combine(opening_date, datetime.min.time(), tzinfo=timezone.utc)
        await ensure_period_is_open(opening_date)
    else:
        await ensure_period_is_open(creation_datetime.date())
        await ensure_bank_transaction_date_allowed(bank_id, creation_datetime.date())
    if maturity_datetime <= creation_datetime:
        raise HTTPException(status_code=400, detail="تاريخ الاستحقاق يجب أن يكون بعد تاريخ إنشاء الوديعة")

    updates = {
        "account_number": payload.account_number.strip(),
        "deposit_number": payload.deposit_number.strip(),
        "amount": payload.amount,
        "creation_datetime": serialize_datetime(creation_datetime),
        "maturity_datetime": serialize_datetime(maturity_datetime),
        "is_opening_balance_deposit": is_opening_balance_deposit,
        "accounting_start_datetime": serialize_datetime(accounting_start_datetime),
        "monthly_interest_rate": payload.monthly_interest_rate,
        "renewed_from_deposit_id": (payload.renewed_from_deposit_id or "").strip() or None,
        "renewal_notes": (payload.renewal_notes or "").strip() or None,
        "updated_at": serialize_datetime(datetime.now(timezone.utc)),
    }
    result = await db.deposits.update_one(with_organization({"id": deposit_id, "bank_id": bank_id}), {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="الوديعة غير موجودة")
    updated = await db.deposits.find_one(with_organization({"id": deposit_id, "bank_id": bank_id}), {"_id": 0})
    await journal_for_deposit_principal(updated, current_user)
    await journal_for_deposit_interest(updated, current_user)
    return Deposit(**hydrate_deposit(updated))


@api_router.delete("/banks/{bank_id}/deposits/{deposit_id}")
async def delete_deposit(
    bank_id: str,
    deposit_id: str,
    _: dict = Depends(require_admin),
):
    await ensure_bank_async(bank_id)
    existing = await db.deposits.find_one(with_organization({"id": deposit_id, "bank_id": bank_id}), {"_id": 0})
    if existing and existing.get("creation_datetime"):
        await ensure_period_is_open(datetime.fromisoformat(existing["creation_datetime"]).date())
    result = await db.deposits.delete_one(with_organization({"id": deposit_id, "bank_id": bank_id}))
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="الوديعة غير موجودة")
    await delete_journal_for_source("deposit", deposit_id)
    await delete_journal_for_source("deposit_interest", deposit_id)
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
async def get_detailed_statement(
    bank_id: str,
    period_type: Literal["yearly", "monthly"] = Query(default="yearly"),
    year: Optional[int] = Query(default=None, ge=2020, le=2200),
    month: Optional[int] = Query(default=None, ge=1, le=12),
    previous_period_type: Literal["yearly", "monthly"] = Query(default="yearly"),
    previous_year: Optional[int] = Query(default=None, ge=2020, le=2200),
    previous_month: Optional[int] = Query(default=None, ge=1, le=12),
    _: dict = Depends(require_permission("view_reports")),
):
    bank = await ensure_bank_async(bank_id)
    current_year = year or datetime.now(timezone.utc).year
    target_month = month or datetime.now(timezone.utc).month
    previous_target_year = previous_year or current_year - 1
    previous_target_month = previous_month or target_month
    current_period_from, current_period_to = statement_period_bounds(period_type, current_year, target_month)
    deposits = await active_deposits_for_period(bank_id, current_period_from, current_period_to)
    rows = []
    total_volume = 0.0
    total_current = 0.0
    total_previous = 0.0

    for index, deposit in enumerate(deposits, start=1):
        interest_rows, annual_interest, yearly_total = calculate_interest_rows(deposit, current_year)
        if period_type == "monthly":
            current_total = next((row.interest_amount for row in interest_rows if row.month_number == target_month), 0.0)
        else:
            current_total = yearly_total

        previous_interest_rows, _, previous_yearly_total = calculate_interest_rows(deposit, previous_target_year)
        if previous_period_type == "monthly":
            previous_total = next((row.interest_amount for row in previous_interest_rows if row.month_number == previous_target_month), 0.0)
        else:
            previous_total = previous_yearly_total
        previous_breakdown = [PreviousYearBreakdown(year=previous_target_year, interest_amount=previous_total)] if previous_total > 0 else []
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
                status=deposit.status,
                renewal_notes=deposit.renewal_notes,
                maturity_date=normalize_datetime(deposit.maturity_datetime).date().isoformat() if deposit.maturity_datetime else None,
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
async def get_volume_statement(
    bank_id: str,
    period_type: Literal["yearly", "monthly"] = Query(default="yearly"),
    year: Optional[int] = Query(default=None, ge=2020, le=2200),
    month: Optional[int] = Query(default=None, ge=1, le=12),
    _: dict = Depends(require_permission("view_reports")),
):
    bank = await ensure_bank_async(bank_id)
    target_year = year or datetime.now(timezone.utc).year
    target_month = month or datetime.now(timezone.utc).month
    period_from, period_to = statement_period_bounds(period_type, target_year, target_month)
    deposits = await active_deposits_for_period(bank_id, period_from, period_to)
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
                status=deposit.status,
                renewal_notes=deposit.renewal_notes,
                maturity_date=normalize_datetime(deposit.maturity_datetime).date().isoformat() if deposit.maturity_datetime else None,
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
    min_year = min([normalize_datetime(deposit.accounting_start_datetime or deposit.creation_datetime).year for deposit in all_deposits], default=current_year)
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
    current_user: dict = Depends(require_any_permission(["enter_deposits", "manage_reconciliations"])),
):
    await ensure_bank_async(bank_id)
    now = datetime.now(timezone.utc)
    await ensure_bank_transaction_date_allowed(bank_id, now.date())
    balance_breakdown = await calculate_bank_reconciliation_balance_breakdown(bank_id, period_label=payload.period_label, as_of_date=now.date())
    payload = payload.model_copy(update={"book_balance": balance_breakdown.book_balance})
    computed = calculate_reconciliation(payload)
    document = payload.model_dump()
    for list_name in ["outstanding_checks", "collection_checks", "prior_year_outstanding_checks"]:
        for item in document[list_name]:
            item["check_date"] = serialize_datetime(item["check_date"])
    document.update(
        {
            "id": str(uuid.uuid4()),
            "bank_id": bank_id,
            "organization_id": organization_id_or_default(),
            **computed,
            "balance_breakdown": balance_breakdown.model_dump(mode="json"),
            "created_at": serialize_datetime(now),
            "updated_at": serialize_datetime(now),
        }
    )
    await db.reconciliations.insert_one(document)
    await journal_for_reconciliation(document, current_user)
    return BankReconciliation(**hydrate_reconciliation(document))


@api_router.get("/banks/{bank_id}/reconciliations", response_model=List[BankReconciliation])
async def list_bank_reconciliations(bank_id: str, _: dict = Depends(require_any_permission(["enter_deposits", "view_reports", "manage_reconciliations"]))):
    await ensure_bank_async(bank_id)
    documents = await db.reconciliations.find(with_organization({"bank_id": bank_id}), {"_id": 0}).sort("created_at", -1).to_list(500)
    return [BankReconciliation(**hydrate_reconciliation(document)) for document in documents]


@api_router.get("/banks/{bank_id}/reconciliations/latest", response_model=BankReconciliation)
async def get_latest_bank_reconciliation(bank_id: str, _: dict = Depends(require_any_permission(["enter_deposits", "view_reports", "manage_reconciliations"]))):
    await ensure_bank_async(bank_id)
    documents = await db.reconciliations.find(with_organization({"bank_id": bank_id}), {"_id": 0}).sort("created_at", -1).to_list(1)
    if not documents:
        raise HTTPException(status_code=404, detail="لا توجد مذكرات تسوية لهذا البنك")
    return BankReconciliation(**hydrate_reconciliation(documents[0]))


@api_router.get("/banks/{bank_id}/book-balance", response_model=BankBookBalanceResponse)
async def get_bank_book_balance(bank_id: str, as_of_date: Optional[date] = Query(default=None), _: dict = Depends(require_any_permission(["enter_deposits", "view_reports", "manage_reconciliations"]))):
    await ensure_bank_async(bank_id)
    target_date = as_of_date or date.today()
    return BankBookBalanceResponse(bank_id=bank_id, as_of_date=target_date, book_balance=await calculate_bank_book_balance(bank_id, target_date))


@api_router.get("/banks/{bank_id}/reconciliation-balance", response_model=BankReconciliationBalanceBreakdown)
async def get_bank_reconciliation_balance(
    bank_id: str,
    period_label: Optional[str] = Query(default=None),
    year: Optional[int] = Query(default=None, ge=1900, le=2200),
    month: Optional[int] = Query(default=None, ge=1, le=12),
    as_of_date: Optional[date] = Query(default=None),
    _: dict = Depends(require_any_permission(["enter_deposits", "view_reports", "manage_reconciliations"])),
):
    return await calculate_bank_reconciliation_balance_breakdown(bank_id, period_label=period_label, year=year, month=month, as_of_date=as_of_date)


@api_router.get("/banks/{bank_id}/reconciliations/{reconciliation_id}", response_model=BankReconciliation)
async def get_bank_reconciliation(bank_id: str, reconciliation_id: str, _: dict = Depends(require_any_permission(["enter_deposits", "view_reports", "manage_reconciliations"]))):
    await ensure_bank_async(bank_id)
    document = await db.reconciliations.find_one(with_organization({"bank_id": bank_id, "id": reconciliation_id}), {"_id": 0})
    if not document:
        raise HTTPException(status_code=404, detail="مذكرة التسوية غير موجودة")
    return BankReconciliation(**hydrate_reconciliation(document))


@api_router.put("/banks/{bank_id}/reconciliations/{reconciliation_id}", response_model=BankReconciliation)
async def update_bank_reconciliation(
    bank_id: str,
    reconciliation_id: str,
    payload: BankReconciliationCreate,
    current_user: dict = Depends(require_any_permission(["enter_deposits", "manage_reconciliations"])),
):
    await ensure_bank_async(bank_id)
    existing = await db.reconciliations.find_one(with_organization({"bank_id": bank_id, "id": reconciliation_id}), {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="مذكرة التسوية غير موجودة")

    now = datetime.now(timezone.utc)
    await ensure_bank_transaction_date_allowed(bank_id, now.date())
    balance_breakdown = await calculate_bank_reconciliation_balance_breakdown(bank_id, period_label=payload.period_label, as_of_date=now.date())
    payload = payload.model_copy(update={"book_balance": balance_breakdown.book_balance})
    computed = calculate_reconciliation(payload)
    updates = payload.model_dump()
    for list_name in ["outstanding_checks", "collection_checks", "prior_year_outstanding_checks"]:
        for item in updates[list_name]:
            item["check_date"] = serialize_datetime(item["check_date"])
    updates.update({**computed, "updated_at": serialize_datetime(datetime.now(timezone.utc))})
    updates["balance_breakdown"] = balance_breakdown.model_dump(mode="json")
    await db.reconciliations.update_one(with_organization({"bank_id": bank_id, "id": reconciliation_id}), {"$set": updates})
    updated = await db.reconciliations.find_one(with_organization({"bank_id": bank_id, "id": reconciliation_id}), {"_id": 0})
    await journal_for_reconciliation(updated, current_user)
    return BankReconciliation(**hydrate_reconciliation(updated))


@api_router.delete("/banks/{bank_id}/reconciliations/{reconciliation_id}")
async def delete_bank_reconciliation(
    bank_id: str,
    reconciliation_id: str,
    _: dict = Depends(require_admin),
):
    await ensure_bank_async(bank_id)
    result = await db.reconciliations.delete_one(with_organization({"bank_id": bank_id, "id": reconciliation_id}))
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="مذكرة التسوية غير موجودة")
    await delete_journal_for_source("reconciliation", reconciliation_id)
    return {"message": "تم حذف مذكرة التسوية", "deleted_reconciliation_id": reconciliation_id}


@api_router.post("/revenues", response_model=Revenue)
async def create_revenue(
    payload: RevenueCreate,
    current_user: dict = Depends(require_any_permission(["enter_deposits", "manage_revenues"])),
):
    now = datetime.now(timezone.utc)
    document = await revenue_document_from_payload(payload)
    document.update({"id": str(uuid.uuid4()), "created_at": serialize_datetime(now), "updated_at": serialize_datetime(now)})
    await db.revenues.insert_one(document)
    await journal_for_revenue(document, current_user)
    return Revenue(**hydrate_revenue(document))


@api_router.get("/revenues", response_model=List[Revenue])
async def list_revenues(
    bank_id: Optional[str] = Query(default=None),
    collection_method: Optional[str] = Query(default=None),
    from_date: Optional[date] = Query(default=None),
    to_date: Optional[date] = Query(default=None),
    _: dict = Depends(require_any_permission(["enter_deposits", "view_reports", "manage_revenues"])),
):
    query = with_organization({"is_reversal": {"$ne": True}})
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
    documents = await db.revenues.find(with_organization({"$or": conditions}), {"_id": 0}).sort("created_at", -1).to_list(50)
    return [Revenue(**hydrate_revenue(document)) for document in documents]


@api_router.get("/revenues/{revenue_id}", response_model=Revenue)
async def get_revenue(
    revenue_id: str,
    _: dict = Depends(require_any_permission(["enter_deposits", "view_reports", "manage_revenues"])),
):
    document = await db.revenues.find_one(with_organization({"id": revenue_id}), {"_id": 0})
    if not document:
        raise HTTPException(status_code=404, detail="الإيراد غير موجود")
    return Revenue(**hydrate_revenue(document))


@api_router.put("/revenues/{revenue_id}", response_model=Revenue)
async def update_revenue(
    revenue_id: str,
    payload: RevenueCreate,
    current_user: dict = Depends(require_any_permission(["enter_deposits", "manage_revenues"])),
):
    existing = await db.revenues.find_one(with_organization({"id": revenue_id}), {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="الإيراد غير موجود")
    await ensure_period_is_open(date.fromisoformat(existing["issued_at"]))
    updates = await revenue_document_from_payload(payload, revenue_id)
    updates["updated_at"] = serialize_datetime(datetime.now(timezone.utc))
    await db.revenues.update_one(with_organization({"id": revenue_id}), {"$set": updates})
    updated = await db.revenues.find_one(with_organization({"id": revenue_id}), {"_id": 0})
    await journal_for_revenue(updated, current_user)
    return Revenue(**hydrate_revenue(updated))


@api_router.patch("/revenues/{revenue_id}/banking-status", response_model=Revenue)
async def update_revenue_banking_status(
    revenue_id: str,
    payload: RevenueBankingStatusUpdate,
    current_user: dict = Depends(require_any_permission(["enter_deposits", "manage_revenues"])),
):
    existing = await db.revenues.find_one(with_organization({"id": revenue_id}), {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="الإيراد غير موجود")
    if existing.get("collection_method") in REVENUE_DIRECT_BANK_METHODS and payload.bank_collection_status != "collected":
        raise HTTPException(status_code=400, detail="فوائد الحساب الجاري واستحقاق الوديعة يتم تحصيلهما فوراً ولا يمكن جعلهما تحت التحصيل")
    await db.revenues.update_one(
        with_organization({"id": revenue_id}),
        {"$set": {"bank_collection_status": payload.bank_collection_status, "updated_at": serialize_datetime(datetime.now(timezone.utc))}},
    )
    updated = await db.revenues.find_one(with_organization({"id": revenue_id}), {"_id": 0})
    await journal_for_revenue(updated, current_user)
    return Revenue(**hydrate_revenue(updated))


@api_router.delete("/revenues/{revenue_id}")
async def delete_revenue(
    revenue_id: str,
    _: dict = Depends(require_any_permission(["enter_deposits", "manage_revenues"])),
):
    existing = await db.revenues.find_one(with_organization({"id": revenue_id}), {"_id": 0})
    if existing and existing.get("issued_at"):
        await ensure_period_is_open(date.fromisoformat(existing["issued_at"]))
    result = await db.revenues.delete_one(with_organization({"id": revenue_id}))
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="الإيراد غير موجود")
    await delete_journal_for_source("revenue", revenue_id)
    return {"message": "تم حذف الإيراد", "deleted_revenue_id": revenue_id}


@api_router.post("/expenses", response_model=Expense)
async def create_expense(
    payload: ExpenseCreate,
    current_user: dict = Depends(require_any_permission(["enter_deposits", "manage_expenses"])),
):
    now = datetime.now(timezone.utc)
    document = await expense_document_from_payload(payload)
    document.update({"id": str(uuid.uuid4()), "created_at": serialize_datetime(now), "updated_at": serialize_datetime(now)})
    await db.expenses.insert_one(document)
    await journal_for_expense(document, current_user)
    return Expense(**hydrate_expense(document))


@api_router.get("/expenses", response_model=List[Expense])
async def list_expenses(
    bank_id: Optional[str] = Query(default=None),
    payment_method: Optional[str] = Query(default=None),
    from_date: Optional[date] = Query(default=None),
    to_date: Optional[date] = Query(default=None),
    _: dict = Depends(require_any_permission(["enter_deposits", "view_reports", "manage_expenses"])),
):
    query = with_organization({"is_reversal": {"$ne": True}})
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
    documents = await db.expenses.find(with_organization({"$or": conditions}), {"_id": 0}).sort("created_at", -1).to_list(50)
    return [Expense(**hydrate_expense(document)) for document in documents]


@api_router.get("/expenses/{expense_id}", response_model=Expense)
async def get_expense(
    expense_id: str,
    _: dict = Depends(require_any_permission(["enter_deposits", "view_reports", "manage_expenses"])),
):
    document = await db.expenses.find_one(with_organization({"id": expense_id}), {"_id": 0})
    if not document:
        raise HTTPException(status_code=404, detail="المصروف غير موجود")
    return Expense(**hydrate_expense(document))


@api_router.put("/expenses/{expense_id}", response_model=Expense)
async def update_expense(
    expense_id: str,
    payload: ExpenseCreate,
    current_user: dict = Depends(require_any_permission(["enter_deposits", "manage_expenses"])),
):
    existing = await db.expenses.find_one(with_organization({"id": expense_id}), {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="المصروف غير موجود")
    await ensure_period_is_open(date.fromisoformat(existing["issued_at"]))
    updates = await expense_document_from_payload(payload, expense_id)
    updates["updated_at"] = serialize_datetime(datetime.now(timezone.utc))
    await db.expenses.update_one(with_organization({"id": expense_id}), {"$set": updates})
    updated = await db.expenses.find_one(with_organization({"id": expense_id}), {"_id": 0})
    await journal_for_expense(updated, current_user)
    return Expense(**hydrate_expense(updated))


@api_router.patch("/expenses/{expense_id}/banking-status", response_model=Expense)
async def update_expense_banking_status(
    expense_id: str,
    payload: ExpenseBankingStatusUpdate,
    current_user: dict = Depends(require_any_permission(["enter_deposits", "manage_expenses"])),
):
    existing = await db.expenses.find_one(with_organization({"id": expense_id}), {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="المصروف غير موجود")
    if existing.get("expense_category") == "deposit_link" and payload.bank_payment_status != "paid":
        raise HTTPException(status_code=400, detail="ربط الوديعة حركة بنك فورية ولا يمكن جعلها تحت التحصيل")
    await db.expenses.update_one(
        with_organization({"id": expense_id}),
        {"$set": {"bank_payment_status": payload.bank_payment_status, "updated_at": serialize_datetime(datetime.now(timezone.utc))}},
    )
    updated = await db.expenses.find_one(with_organization({"id": expense_id}), {"_id": 0})
    await journal_for_expense(updated, current_user)
    return Expense(**hydrate_expense(updated))


@api_router.delete("/expenses/{expense_id}")
async def delete_expense(
    expense_id: str,
    _: dict = Depends(require_any_permission(["enter_deposits", "manage_expenses"])),
):
    existing = await db.expenses.find_one(with_organization({"id": expense_id}), {"_id": 0})
    if existing and existing.get("issued_at"):
        await ensure_period_is_open(date.fromisoformat(existing["issued_at"]))
    result = await db.expenses.delete_one(with_organization({"id": expense_id}))
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="المصروف غير موجود")
    await delete_journal_for_source("expense", expense_id)
    return {"message": "تم حذف المصروف", "deleted_expense_id": expense_id}


@api_router.get("/banking-expenses/manual", response_model=BankingManualChargesResponse)
async def get_banking_manual_charges(
    bank_id: str = Query(...),
    year: int = Query(..., ge=1900, le=2200),
    month: int = Query(..., ge=1, le=12),
    _: dict = Depends(require_any_permission(["enter_deposits", "view_reports", "manage_expenses", "manage_revenues"])),
):
    bank = await ensure_bank_async(bank_id)
    document = await db.banking_manual_charges.find_one(with_organization({"bank_id": bank_id, "year": year, "month": month}), {"_id": 0})
    if not document:
        document = {
            "id": f"{bank_id}-{year}-{month}",
            "organization_id": organization_id_or_default(),
            "bank_id": bank_id,
            "bank_name": bank["name"],
            "year": year,
            "month": month,
            "items": [],
            "updated_at": serialize_datetime(datetime.now(timezone.utc)),
        }
    return BankingManualChargesResponse(**hydrate_banking_manual_charges(document))


@api_router.put("/banking-expenses/manual", response_model=BankingManualChargesResponse)
async def save_banking_manual_charges(
    payload: BankingManualCharges,
    current_user: dict = Depends(require_any_permission(["enter_deposits", "manage_expenses", "manage_revenues"])),
):
    bank = await ensure_bank_async(payload.bank_id)
    now = datetime.now(timezone.utc)
    await ensure_bank_transaction_date_allowed(payload.bank_id, date(int(payload.year), int(payload.month), 1))
    clean_items = []
    for item in payload.items:
      statement = str(item.get("statement") or "").strip()
      count = round(float(item.get("count") or 1), 2)
      amount = round(float(item.get("amount") or 0), 2)
      total = round(count * amount, 2)
      if statement and count > 0 and amount > 0:
          clean_items.append({"statement": statement, "count": count, "amount": amount, "total": total})
    document = {
        "id": f"{payload.bank_id}-{payload.year}-{payload.month}",
        "organization_id": organization_id_or_default(),
        "bank_id": payload.bank_id,
        "bank_name": bank["name"],
        "year": payload.year,
        "month": payload.month,
        "items": clean_items,
        "updated_at": serialize_datetime(now),
    }
    await db.banking_manual_charges.update_one(
        with_organization({"bank_id": payload.bank_id, "year": payload.year, "month": payload.month}),
        {"$set": document},
        upsert=True,
    )
    await journal_for_banking_expense(document, current_user)
    return BankingManualChargesResponse(**hydrate_banking_manual_charges(document))


@api_router.get("/fixed-assets/categories", response_model=List[FixedAssetCategory])
async def list_fixed_asset_categories(_: dict = Depends(require_any_permission(["enter_deposits", "view_reports", "manage_expenses", "manage_revenues"]))):
    categories = await list_fixed_asset_categories_with_catalog()
    return [FixedAssetCategory(**category) for category in categories]


@api_router.get("/fixed-assets/catalog-items", response_model=List[FixedAssetCatalogItem])
async def list_fixed_asset_catalog_items(
    category_code: str = Query(...),
    _: dict = Depends(require_any_permission(["enter_deposits", "view_reports", "manage_expenses", "manage_revenues"])),
):
    return [FixedAssetCatalogItem(**item) for item in await list_fixed_asset_catalog_items_for_category(category_code)]


@api_router.post("/fixed-assets/catalog-items", response_model=FixedAssetCatalogItem)
async def create_fixed_asset_catalog_item(payload: FixedAssetCatalogItemCreate, _: dict = Depends(require_any_permission(["enter_deposits", "manage_expenses"]))):
    category = fixed_asset_category(payload.category_code)
    name = normalize_member_text(payload.name)
    if not name:
        raise HTTPException(status_code=400, detail="اسم الأصل الجديد مطلوب")
    current_items = await list_fixed_asset_catalog_items_for_category(category["code"])
    if any(item["name"] == name for item in current_items):
        raise HTTPException(status_code=400, detail="هذا الأصل موجود بالفعل في القائمة")
    now_iso = serialize_datetime(datetime.now(timezone.utc))
    document = {"id": str(uuid.uuid4()), "organization_id": organization_id_or_default(), "category_code": category["code"], "name": name, "created_at": now_iso, "updated_at": now_iso}
    await db.fixed_asset_catalog_items.insert_one(document.copy())
    return FixedAssetCatalogItem(id=document["id"], category_code=category["code"], name=name, is_default=False, is_custom=True)


@api_router.delete("/fixed-assets/catalog-items/{item_id}")
async def delete_fixed_asset_catalog_item(item_id: str, _: dict = Depends(require_any_permission(["enter_deposits", "manage_expenses"]))):
    custom = await db.fixed_asset_catalog_items.find_one(with_organization({"id": item_id}), {"_id": 0})
    if custom:
        await db.fixed_asset_catalog_items.delete_one(with_organization({"id": item_id}))
        return {"message": "تم حذف الأصل من القائمة", "deleted_item_id": item_id}
    for category in FIXED_ASSET_CATEGORIES:
        for name in category["items"]:
            if fixed_asset_catalog_default_id(category["code"], name) == item_id:
                now_iso = serialize_datetime(datetime.now(timezone.utc))
                document = {"id": item_id, "organization_id": organization_id_or_default(), "category_code": category["code"], "name": name, "created_at": now_iso, "updated_at": now_iso}
                await db.fixed_asset_catalog_hidden.update_one(with_organization({"id": item_id}), {"$set": document}, upsert=True)
                return {"message": "تم إخفاء الأصل من القائمة", "deleted_item_id": item_id}
    raise HTTPException(status_code=404, detail="الأصل غير موجود في القائمة")


@api_router.get("/fixed-assets", response_model=List[FixedAssetResponse])
async def list_fixed_assets(
    category_code: Optional[str] = Query(default=None),
    _: dict = Depends(require_any_permission(["enter_deposits", "view_reports", "manage_expenses", "manage_revenues"])),
):
    query = with_organization({})
    if category_code:
        query["category_code"] = fixed_asset_category(category_code)["code"]
    documents = await db.fixed_assets.find(query, {"_id": 0}).sort("purchase_date", -1).sort("created_at", -1).to_list(2000)
    return [FixedAssetResponse(**(await enrich_fixed_asset(document))) for document in documents]


@api_router.post("/fixed-assets", response_model=FixedAssetResponse)
async def create_fixed_asset(payload: FixedAssetCreate, current_user: dict = Depends(require_any_permission(["enter_deposits", "manage_expenses"]))):
    await sync_chart_accounts_for_organization(organization_id_or_default())
    now_iso = serialize_datetime(datetime.now(timezone.utc))
    document = await fixed_asset_document_from_payload(payload)
    document.update({"id": str(uuid.uuid4()), "created_at": now_iso, "updated_at": now_iso})
    await db.fixed_assets.insert_one(document.copy())
    await journal_for_fixed_asset(document, current_user)
    return FixedAssetResponse(**(await enrich_fixed_asset(document)))


@api_router.put("/fixed-assets/{asset_id}", response_model=FixedAssetResponse)
async def update_fixed_asset(asset_id: str, payload: FixedAssetCreate, current_user: dict = Depends(require_any_permission(["enter_deposits", "manage_expenses"]))):
    existing = await db.fixed_assets.find_one(with_organization({"id": asset_id}), {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="الأصل الثابت غير موجود")
    await ensure_period_is_open(date.fromisoformat(existing["purchase_date"]))
    updates = await fixed_asset_document_from_payload(payload, asset_id)
    updates["updated_at"] = serialize_datetime(datetime.now(timezone.utc))
    await db.fixed_assets.update_one(with_organization({"id": asset_id}), {"$set": updates})
    depreciation_records = await db.fixed_asset_depreciations.find(with_organization({"asset_id": asset_id}), {"_id": 0, "id": 1}).to_list(1000)
    for record in depreciation_records:
        await delete_journal_for_source("asset_depreciation", record["id"])
    await db.fixed_asset_depreciations.delete_many(with_organization({"asset_id": asset_id}))
    updated = await db.fixed_assets.find_one(with_organization({"id": asset_id}), {"_id": 0})
    await journal_for_fixed_asset(updated, current_user)
    return FixedAssetResponse(**(await enrich_fixed_asset(updated)))


@api_router.delete("/fixed-assets/{asset_id}")
async def delete_fixed_asset(asset_id: str, _: dict = Depends(require_admin)):
    existing = await db.fixed_assets.find_one(with_organization({"id": asset_id}), {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="الأصل الثابت غير موجود")
    await ensure_period_is_open(date.fromisoformat(existing["purchase_date"]))
    depreciation_records = await db.fixed_asset_depreciations.find(with_organization({"asset_id": asset_id}), {"_id": 0, "id": 1}).to_list(1000)
    for record in depreciation_records:
        await delete_journal_for_source("asset_depreciation", record["id"])
    await db.fixed_asset_depreciations.delete_many(with_organization({"asset_id": asset_id}))
    await db.fixed_assets.delete_one(with_organization({"id": asset_id}))
    await delete_journal_for_source("fixed_asset", asset_id)
    return {"message": "تم حذف الأصل الثابت وقيوده التلقائية", "deleted_asset_id": asset_id}


async def build_depreciation_record(asset: dict, year: int, month: int, current_user: dict) -> Optional[dict]:
    purchase_date_value = asset.get("purchase_date") if isinstance(asset.get("purchase_date"), date) else date.fromisoformat(str(asset.get("purchase_date")))
    depreciation_date = month_end_date(year, month)
    if depreciation_date < purchase_date_value:
        return None
    category = fixed_asset_category(asset.get("category_code"))
    monthly_amount = fixed_asset_monthly_depreciation(asset.get("purchase_cost"), category["annual_depreciation_rate"])
    if monthly_amount <= 0:
        return None
    record_id = f"{asset['id']}-{year}-{str(month).zfill(2)}"
    previous_records = await db.fixed_asset_depreciations.find(with_organization({"asset_id": asset["id"], "id": {"$ne": record_id}}), {"_id": 0, "amount": 1}).to_list(1000)
    accumulated_before = round(sum(float(item.get("amount") or 0) for item in previous_records), 2)
    remaining = round(float(asset.get("purchase_cost") or 0) - accumulated_before, 2)
    amount = round(min(monthly_amount, remaining), 2)
    if amount <= 0:
        await db.fixed_asset_depreciations.delete_one(with_organization({"id": record_id}))
        await delete_journal_for_source("asset_depreciation", record_id)
        return None
    now_iso = serialize_datetime(datetime.now(timezone.utc))
    existing = await db.fixed_asset_depreciations.find_one(with_organization({"id": record_id}), {"_id": 0})
    document = {
        "id": record_id,
        "organization_id": organization_id_or_default(),
        "asset_id": asset["id"],
        "asset_code": asset.get("asset_code"),
        "asset_name": asset.get("asset_name"),
        "category_code": category["code"],
        "category_name": category["name"],
        "year": year,
        "month": month,
        "depreciation_date": serialize_date(depreciation_date),
        "amount": amount,
        "accumulated_after": round(accumulated_before + amount, 2),
        "net_book_value_after": round(max(float(asset.get("purchase_cost") or 0) - accumulated_before - amount, 0), 2),
        "created_at": existing.get("created_at") if existing else now_iso,
        "updated_at": now_iso,
    }
    await db.fixed_asset_depreciations.update_one(with_organization({"id": record_id}), {"$set": document}, upsert=True)
    await journal_for_asset_depreciation(document, current_user)
    return document


async def build_annual_depreciation_record(asset: dict, year: int, current_user: Optional[dict] = None) -> Optional[dict]:
    purchase_date_value = asset.get("purchase_date") if isinstance(asset.get("purchase_date"), date) else date.fromisoformat(str(asset.get("purchase_date")))
    depreciation_date = date(year, 12, 31)
    if depreciation_date < purchase_date_value:
        return None
    category = fixed_asset_category(asset.get("category_code"))
    annual_rate = float(asset.get("annual_depreciation_rate") if asset.get("annual_depreciation_rate") is not None else category["annual_depreciation_rate"])
    annual_amount = fixed_asset_annual_depreciation(asset.get("purchase_cost"), annual_rate)
    if annual_amount <= 0:
        return None
    record_id = f"{asset['id']}-{year}-annual"
    old_year_records = await db.fixed_asset_depreciations.find(with_organization({"asset_id": asset["id"], "year": year, "id": {"$ne": record_id}}), {"_id": 0}).to_list(1000)
    for old_record in old_year_records:
        await delete_journal_for_source("asset_depreciation", old_record["id"])
        await db.fixed_asset_depreciations.delete_one(with_organization({"id": old_record["id"]}))
    previous_records = await db.fixed_asset_depreciations.find(with_organization({"asset_id": asset["id"], "id": {"$ne": record_id}}), {"_id": 0, "amount": 1}).to_list(1000)
    accumulated_before = round(sum(float(item.get("amount") or 0) for item in previous_records), 2)
    remaining = round(float(asset.get("purchase_cost") or 0) - accumulated_before, 2)
    amount = round(min(annual_amount, remaining), 2)
    if amount <= 0:
        await db.fixed_asset_depreciations.delete_one(with_organization({"id": record_id}))
        await delete_journal_for_source("asset_depreciation", record_id)
        return None
    now_iso = serialize_datetime(datetime.now(timezone.utc))
    existing = await db.fixed_asset_depreciations.find_one(with_organization({"id": record_id}), {"_id": 0})
    document = {
        "id": record_id,
        "organization_id": organization_id_or_default(),
        "asset_id": asset["id"],
        "asset_code": asset.get("asset_code"),
        "asset_name": asset.get("asset_name"),
        "category_code": category["code"],
        "category_name": category["name"],
        "year": year,
        "month": 12,
        "period_type": "annual",
        "depreciation_date": serialize_date(depreciation_date),
        "amount": amount,
        "annual_rate": annual_rate,
        "accumulated_after": round(accumulated_before + amount, 2),
        "net_book_value_after": round(max(float(asset.get("purchase_cost") or 0) - accumulated_before - amount, 0), 2),
        "created_at": existing.get("created_at") if existing else now_iso,
        "updated_at": now_iso,
    }
    await db.fixed_asset_depreciations.update_one(with_organization({"id": record_id}), {"$set": document}, upsert=True)
    await journal_for_asset_depreciation(document, current_user)
    return document


async def auto_run_annual_depreciation_for_year(organization_id: str, year: int, current_user: Optional[dict] = None) -> List[dict]:
    token = CURRENT_ORGANIZATION_ID.set(organization_id)
    try:
        await sync_chart_accounts_for_organization(organization_id)
        assets = await db.fixed_assets.find(with_organization({"is_active": True}, organization_id), {"_id": 0}).sort("asset_code", 1).to_list(5000)
        generated = []
        for asset in assets:
            document = await build_annual_depreciation_record(asset, year, current_user)
            if document:
                generated.append(document)
        return generated
    finally:
        CURRENT_ORGANIZATION_ID.reset(token)


@api_router.post("/fixed-assets/depreciation/run", response_model=List[FixedAssetDepreciationResponse])
async def run_fixed_asset_depreciation(payload: FixedAssetDepreciationRun, current_user: dict = Depends(require_any_permission(["enter_deposits", "manage_expenses"]))):
    await ensure_period_is_open(date(payload.year, 12, 31))
    generated = await auto_run_annual_depreciation_for_year(organization_id_or_default(), payload.year, current_user)
    return [FixedAssetDepreciationResponse(**hydrate_fixed_asset_depreciation(document)) for document in generated]


@api_router.get("/fixed-assets/depreciations", response_model=List[FixedAssetDepreciationResponse])
async def list_fixed_asset_depreciations(
    year: Optional[int] = Query(default=None, ge=1900, le=2200),
    month: Optional[int] = Query(default=None, ge=1, le=12),
    _: dict = Depends(require_any_permission(["enter_deposits", "view_reports", "manage_expenses", "manage_revenues"])),
):
    query = with_organization({})
    if year:
        query["year"] = year
    if month:
        query["month"] = month
    documents = await db.fixed_asset_depreciations.find(query, {"_id": 0}).sort("year", -1).sort("month", -1).sort("asset_code", 1).to_list(5000)
    return [FixedAssetDepreciationResponse(**hydrate_fixed_asset_depreciation(document)) for document in documents]


@api_router.get("/custody-advances", response_model=List[CustodyAdvanceResponse])
async def list_custody_advances(
    status: Optional[str] = Query(default=None),
    transaction_type: Optional[str] = Query(default=None),
    _: dict = Depends(require_any_permission(["enter_deposits", "view_reports", "manage_expenses", "manage_revenues"])),
):
    query = with_organization({})
    if status in ["open", "partial", "settled"]:
        query["status"] = status
    if transaction_type in ["custody", "advance"]:
        query["transaction_type"] = transaction_type
    documents = await db.custody_advances.find(query, {"_id": 0}).sort("issue_date", -1).sort("created_at", -1).to_list(5000)
    return [CustodyAdvanceResponse(**hydrate_custody_advance(document)) for document in documents]


@api_router.post("/custody-advances", response_model=CustodyAdvanceResponse)
async def create_custody_advance(payload: CustodyAdvanceCreate, current_user: dict = Depends(require_any_permission(["enter_deposits", "manage_expenses"]))) :
    await sync_chart_accounts_for_organization(organization_id_or_default())
    document = await custody_advance_document_from_payload(payload)
    now_iso = serialize_datetime(datetime.now(timezone.utc))
    document.update({"id": str(uuid.uuid4()), "created_at": now_iso, "updated_at": now_iso})
    await db.custody_advances.insert_one(document.copy())
    await journal_for_custody_advance(document, current_user)
    return CustodyAdvanceResponse(**hydrate_custody_advance(document))


@api_router.post("/custody-advances/{document_id}/settle", response_model=CustodyAdvanceResponse)
async def settle_custody_advance(document_id: str, payload: CustodyAdvanceSettle, current_user: dict = Depends(require_any_permission(["enter_deposits", "manage_expenses"]))) :
    existing = await db.custody_advances.find_one(with_organization({"id": document_id}), {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="العهدة/السلفة غير موجودة")
    await ensure_period_is_open(payload.settlement_date)
    amount = round(float(existing.get("amount") or 0), 2)
    settlement_amount = round(float(payload.settlement_amount), 2)
    if settlement_amount > amount:
        raise HTTPException(status_code=400, detail="قيمة التسوية لا يمكن أن تتجاوز قيمة العهدة/السلفة")
    updates = {
        "settled_amount": settlement_amount,
        "remaining_amount": round(max(amount - settlement_amount, 0), 2),
        "status": "settled" if settlement_amount >= amount else "partial",
        "settlement_date": serialize_date(payload.settlement_date),
        "settlement_type": payload.settlement_type,
        "settlement_notes": normalize_member_text(payload.notes) if payload.notes else None,
        "updated_at": serialize_datetime(datetime.now(timezone.utc)),
    }
    await db.custody_advances.update_one(with_organization({"id": document_id}), {"$set": updates})
    updated = await db.custody_advances.find_one(with_organization({"id": document_id}), {"_id": 0})
    await journal_for_custody_advance_settlement(updated, current_user)
    return CustodyAdvanceResponse(**hydrate_custody_advance(updated))


@api_router.delete("/custody-advances/{document_id}")
async def delete_custody_advance(document_id: str, _: dict = Depends(require_admin)):
    existing = await db.custody_advances.find_one(with_organization({"id": document_id}), {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="العهدة/السلفة غير موجودة")
    await db.custody_advances.delete_one(with_organization({"id": document_id}))
    await delete_journal_for_source("custody_advance", document_id)
    await delete_journal_for_source("custody_advance_settlement", document_id)
    return {"message": "تم حذف العهدة/السلفة وقيودها التلقائية", "deleted_id": document_id}


@api_router.post("/memberships", response_model=MembershipResponse)
async def create_membership(payload: MembershipCreate, current_user: dict = Depends(require_any_permission(["enter_deposits", "manage_users"]))):
    require_social_solidarity_membership(current_user)
    now_iso = serialize_datetime(datetime.now(timezone.utc))
    document = await membership_document_from_payload(payload)
    document.update({"id": str(uuid.uuid4()), "created_at": now_iso, "updated_at": now_iso})
    await db.memberships.insert_one(document.copy())
    return MembershipResponse(**hydrate_membership(document))


@api_router.put("/memberships/{membership_id}", response_model=MembershipResponse)
async def update_membership(membership_id: str, payload: MembershipCreate, current_user: dict = Depends(require_any_permission(["enter_deposits", "manage_users"]))):
    require_social_solidarity_membership(current_user)
    organization_id = organization_id_or_default()
    existing = await db.memberships.find_one(with_organization({"id": membership_id}, organization_id), {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="العضوية غير موجودة")
    document = await membership_document_from_payload(payload, membership_id=membership_id, existing_document=existing)
    document.update({
        "id": membership_id,
        "created_at": existing.get("created_at") or serialize_datetime(datetime.now(timezone.utc)),
        "updated_at": serialize_datetime(datetime.now(timezone.utc)),
    })
    await db.memberships.update_one(with_organization({"id": membership_id}, organization_id), {"$set": document})
    return MembershipResponse(**hydrate_membership(document))


@api_router.delete("/memberships/{membership_id}")
async def delete_membership(membership_id: str, current_user: dict = Depends(require_any_permission(["enter_deposits", "manage_users"]))):
    require_social_solidarity_membership(current_user)
    organization_id = organization_id_or_default()
    existing = await db.memberships.find_one(with_organization({"id": membership_id}, organization_id), {"_id": 0, "id": 1})
    if not existing:
        raise HTTPException(status_code=404, detail="العضوية غير موجودة")
    await db.memberships.delete_one(with_organization({"id": membership_id}, organization_id))
    return {"message": "تم حذف العضوية وتسجيل العملية في سجل التدقيق", "deleted_id": membership_id}


@api_router.get("/memberships/scanner/status", response_model=MembershipScannerStatusResponse)
async def membership_scanner_status(_: dict = Depends(require_any_permission(["enter_deposits", "manage_users"]))):
    require_social_solidarity_membership(_)
    is_windows = os.name == "nt"
    tesseract_available = bool(tesseract_executable_path())
    windows_ocr_available = is_windows
    scanner_available = is_windows
    message = "جاهز للمسح من نسخة Windows المحلية" if is_windows else "المسح المباشر يعمل فقط من برنامج Windows المثبت محلياً"
    return MembershipScannerStatusResponse(is_windows=is_windows, scanner_available=scanner_available, tesseract_available=tesseract_available, windows_ocr_available=windows_ocr_available, message=message)


@api_router.post("/memberships/scanner/scan-import", response_model=MembershipScanImportResponse)
async def scan_and_import_membership_form(
    device_index: int = Form(1),
    dpi: int = Form(300),
    max_pages: int = Form(10),
    current_user: dict = Depends(require_any_permission(["enter_deposits", "manage_users"])),
):
    require_social_solidarity_membership(current_user)
    safe_dpi = max(150, min(int(dpi or 300), 600))
    safe_pages = max(1, min(int(max_pages or 10), 30))
    work_dir = MEMBERSHIP_SCAN_DIR / "_incoming" / str(uuid.uuid4())
    image_paths = run_wia_adf_scan(work_dir, max(1, int(device_index or 1)), safe_dpi, safe_pages)
    pdf_path = work_dir / "membership-form.pdf"
    create_pdf_from_images(image_paths, pdf_path)
    raw_text = run_tesseract_ocr(image_paths)
    ocr_engine = "tesseract"
    if not raw_text:
        raw_text = run_windows_ocr(image_paths)
        ocr_engine = "windows-ocr"
    if not raw_text:
        raise HTTPException(status_code=400, detail="تم المسح وحفظ PDF، لكن تعذر قراءة النص مجاناً. تأكد من وضوح الاستمارة أو تثبيت حزمة اللغة العربية في Windows OCR أو Tesseract")
    return await create_membership_from_scanned_form(raw_text, pdf_path, len(image_paths), "scanner", ocr_engine, current_user)


@api_router.post("/memberships/scanner/upload-import", response_model=MembershipScanImportResponse)
async def upload_scanned_membership_form(
    file: UploadFile = File(...),
    current_user: dict = Depends(require_any_permission(["enter_deposits", "manage_users"])),
):
    require_social_solidarity_membership(current_user)
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="ملف الاستمارة فارغ")
    if len(content) > 25 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="حجم الاستمارة كبير جداً. الحد الأقصى 25 ميجا")
    work_dir = MEMBERSHIP_SCAN_DIR / "_incoming" / str(uuid.uuid4())
    pdf_path, image_paths, source_kind = scanned_upload_to_pdf(content, file.filename or "membership-form.pdf", work_dir)
    raw_text = extract_text_from_pdf_if_possible(pdf_path) if source_kind == "pdf" else None
    ocr_engine = "pdf-text" if raw_text else "tesseract"
    if not raw_text and image_paths:
        raw_text = run_tesseract_ocr(image_paths)
    if not raw_text and image_paths:
        raw_text = run_windows_ocr(image_paths)
        ocr_engine = "windows-ocr"
    if not raw_text:
        raise HTTPException(status_code=400, detail="تعذر قراءة النص من الاستمارة. استخدم PDF نصي واضح أو امسح الاستمارة من أداة الماسح على Windows")
    page_count = len(image_paths) if image_paths else max(1, len(PdfReader(str(pdf_path)).pages))
    return await create_membership_from_scanned_form(raw_text, pdf_path, page_count, "upload", ocr_engine, current_user)


@api_router.get("/memberships/{membership_id}/scan-pdf")
async def download_membership_scan_pdf(membership_id: str, current_user: dict = Depends(require_any_permission(["enter_deposits", "view_reports", "manage_users"]))):
    require_social_solidarity_membership(current_user)
    document = await db.memberships.find_one(with_organization({"id": membership_id}), {"_id": 0})
    if not document:
        raise HTTPException(status_code=404, detail="العضوية غير موجودة")
    attachment = document.get("scan_attachment") or {}
    pdf_path = Path(attachment.get("pdf_path") or "")
    if not pdf_path.exists() or not pdf_path.is_file():
        raise HTTPException(status_code=404, detail="ملف استمارة العضوية غير موجود")
    return FileResponse(str(pdf_path), media_type="application/pdf", filename=f"membership-{document.get('membership_number')}-form.pdf")


@api_router.post("/memberships/import", response_model=MembershipImportResponse)
async def import_memberships(
    governorate: str = Form(...),
    union_committee: str = Form(...),
    status: MembershipStatus = Form("active"),
    status_effective_date: Optional[date] = Form(default=None),
    file: UploadFile = File(...),
    current_user: dict = Depends(require_any_permission(["enter_deposits", "manage_users"])),
):
    require_social_solidarity_membership(current_user)
    content = await file.read()
    preview = await build_membership_import_preview_document(governorate, union_committee, file.filename or "", content, status, status_effective_date)
    imported_documents = []
    skipped_rows = [MembershipImportSkippedRow(**row) for row in preview.get("skipped_rows", [])]
    for item in preview.get("accepted_payloads", []):
        try:
            payload_data = {key: value for key, value in item.items() if key != "row_number"}
            payload = MembershipCreate(**payload_data)
            document = await membership_document_from_payload(payload)
        except HTTPException as exc:
            skipped_rows.append(MembershipImportSkippedRow(row_number=item.get("row_number", 0), reason=str(exc.detail)))
            continue
        now_iso = serialize_datetime(datetime.now(timezone.utc))
        document.update({"id": str(uuid.uuid4()), "created_at": now_iso, "updated_at": now_iso})
        await db.memberships.insert_one(document.copy())
        imported_documents.append(document)
    return MembershipImportResponse(
        imported_count=len(imported_documents),
        skipped_count=len(skipped_rows),
        total_rows_detected=preview["total_rows_detected"],
        imported_members=[MembershipResponse(**hydrate_membership(document)) for document in imported_documents],
        skipped_rows=skipped_rows[:100],
    )


@api_router.post("/memberships/import/preview", response_model=MembershipImportPreviewResponse)
async def preview_membership_import(
    governorate: str = Form(...),
    union_committee: str = Form(...),
    status: MembershipStatus = Form("active"),
    status_effective_date: Optional[date] = Form(default=None),
    file: UploadFile = File(...),
    current_user: dict = Depends(require_any_permission(["enter_deposits", "manage_users"])),
):
    require_social_solidarity_membership(current_user)
    document = await build_membership_import_preview_document(governorate, union_committee, file.filename or "", await file.read(), status, status_effective_date)
    await db.membership_import_previews.insert_one(document.copy())
    return membership_import_preview_response(document)


@api_router.post("/memberships/import/commit", response_model=MembershipImportResponse)
async def commit_membership_import(payload: MembershipImportCommitRequest, current_user: dict = Depends(require_any_permission(["enter_deposits", "manage_users"]))):
    require_social_solidarity_membership(current_user)
    preview = await db.membership_import_previews.find_one(with_organization({"id": payload.preview_id}), {"_id": 0})
    if not preview:
        raise HTTPException(status_code=404, detail="معاينة الاستيراد غير موجودة أو انتهت")
    imported_documents = []
    skipped_rows = [MembershipImportSkippedRow(**row) for row in preview.get("skipped_rows", [])]
    for item in preview.get("accepted_payloads", []):
        try:
            payload_data = {key: value for key, value in item.items() if key != "row_number"}
            document = await membership_document_from_payload(MembershipCreate(**payload_data))
            now_iso = serialize_datetime(datetime.now(timezone.utc))
            document.update({"id": str(uuid.uuid4()), "created_at": now_iso, "updated_at": now_iso})
            await db.memberships.insert_one(document.copy())
            imported_documents.append(document)
        except HTTPException as exc:
            skipped_rows.append(MembershipImportSkippedRow(row_number=item.get("row_number", 0), reason=str(exc.detail)))
        except Exception:
            skipped_rows.append(MembershipImportSkippedRow(row_number=item.get("row_number", 0), reason="تعذر حفظ الصف أثناء الاعتماد"))
    await db.membership_import_previews.delete_one(with_organization({"id": payload.preview_id}))
    return MembershipImportResponse(imported_count=len(imported_documents), skipped_count=len(skipped_rows), total_rows_detected=preview.get("total_rows_detected", 0), imported_members=[MembershipResponse(**hydrate_membership(document)) for document in imported_documents], skipped_rows=skipped_rows[:100])


@api_router.get("/memberships", response_model=List[MembershipResponse])
async def list_memberships(
    governorate: Optional[str] = Query(default=None),
    union_committee: Optional[str] = Query(default=None),
    _: dict = Depends(require_any_permission(["enter_deposits", "view_reports", "manage_users"])),
):
    require_social_solidarity_membership(_)
    query = with_organization({})
    if governorate:
        query["governorate"] = governorate.strip()
    if union_committee:
        query["union_committee"] = union_committee.strip()
    documents = await db.memberships.find(query, {"_id": 0}).sort("created_at", -1).to_list(5000)
    paid_map = await membership_paid_allocations_map(date.today())
    enriched = [await enrich_membership_financials(document, date.today(), paid_map) for document in documents]
    return [MembershipResponse(**hydrate_membership(document)) for document in enriched]


@api_router.get("/memberships/search", response_model=List[MembershipResponse])
async def search_memberships(name: str = Query(..., min_length=1), _: dict = Depends(require_any_permission(["enter_deposits", "view_reports", "manage_users"]))):
    require_social_solidarity_membership(_)
    cleaned = normalize_member_text(name)
    documents = await db.memberships.find(with_organization({"name": {"$regex": re.escape(cleaned), "$options": "i"}}), {"_id": 0}).sort("name", 1).to_list(50)
    paid_map = await membership_paid_allocations_map(date.today())
    enriched = [await enrich_membership_financials(document, date.today(), paid_map) for document in documents]
    return [MembershipResponse(**hydrate_membership(document)) for document in enriched]


@api_router.get("/memberships/retirement", response_model=List[MembershipResponse])
async def filter_retirement_memberships(
    year: int = Query(..., ge=1900, le=2200),
    month: int = Query(..., ge=1, le=12),
    governorate: Optional[str] = Query(default=None),
    union_committee: Optional[str] = Query(default=None),
    _: dict = Depends(require_any_permission(["enter_deposits", "view_reports", "manage_users"])),
):
    require_social_solidarity_membership(_)
    query = with_organization({"retirement_year": year, "retirement_month": month})
    if governorate:
        query["governorate"] = governorate.strip()
    if union_committee:
        query["union_committee"] = union_committee.strip()
    documents = await db.memberships.find(query, {"_id": 0}).sort("governorate", 1).sort("union_committee", 1).sort("name", 1).to_list(5000)
    paid_map = await membership_paid_allocations_map(date.today())
    enriched = [await enrich_membership_financials(document, date.today(), paid_map) for document in documents]
    return [MembershipResponse(**hydrate_membership(document)) for document in enriched]


@api_router.get("/memberships/current-size", response_model=MembershipCurrentSizeResponse)
async def get_membership_current_size(
    as_of_year: Optional[int] = Query(default=None, ge=1900, le=2200),
    as_of_month: Optional[int] = Query(default=None, ge=1, le=12),
    _: dict = Depends(require_any_permission(["enter_deposits", "view_reports", "manage_users"])),
):
    require_social_solidarity_membership(_)
    today_value = date.today()
    year = as_of_year or today_value.year
    month = as_of_month or today_value.month
    total = await db.memberships.count_documents(with_organization({}))
    retired = await db.memberships.count_documents(with_organization({"$or": [{"status": {"$in": list(NON_ACTIVE_MEMBERSHIP_STATUSES)}}, {"retirement_year": {"$lt": year}}, {"retirement_year": year, "retirement_month": {"$lte": month}}]}))
    return MembershipCurrentSizeResponse(organization_id=organization_id_or_default(), as_of_year=year, as_of_month=month, total_members=total, retired_members=retired, current_membership_size=max(total - retired, 0))


@api_router.post("/memberships/batch-payments", response_model=MembershipBatchPaymentResponse)
async def create_membership_batch_payment(payload: MembershipBatchPaymentCreate, current_user: dict = Depends(require_any_permission(["enter_deposits", "manage_users"]))):
    require_social_solidarity_membership(current_user)
    bank = await ensure_bank_async(payload.bank_id)
    await ensure_bank_transaction_date_allowed(payload.bank_id, payload.payment_date)
    clean_governorate = normalize_member_text(payload.governorate)
    clean_committee = normalize_member_text(payload.union_committee)
    members = await db.memberships.find(with_organization({"governorate": clean_governorate, "union_committee": clean_committee}), {"_id": 0}).sort("membership_number", 1).to_list(10000)
    if not members:
        raise HTTPException(status_code=404, detail="لا توجد عضويات داخل هذه اللجنة")
    paid_map = await membership_paid_allocations_map(payload.payment_date)
    debts = []
    for member in members:
        member_paid = paid_map.get(member.get("id"), {})
        for due in membership_due_periods(member, payload.payment_date, member_paid):
            debts.append({"member": member, "period": due["period"], "amount": due["amount"]})
    debts.sort(key=lambda item: (item["period"], normalize_digit_text(item["member"].get("membership_number") or ""), item["member"].get("name") or ""))
    remaining_amount = round(float(payload.amount), 2)
    allocations = []
    for debt in debts:
        if remaining_amount <= 0:
            break
        allocated = round(min(remaining_amount, float(debt["amount"])), 2)
        if allocated <= 0:
            continue
        member = debt["member"]
        allocations.append({
            "member_id": member.get("id"),
            "membership_number": member.get("membership_number"),
            "member_name": member.get("name"),
            "period": debt["period"],
            "amount": allocated,
        })
        remaining_amount = round(remaining_amount - allocated, 2)
    if not allocations:
        raise HTTPException(status_code=400, detail="لا توجد مديونية قديمة أو حالية قابلة للسداد لهذه اللجنة حتى تاريخ الإذن")
    now_iso = serialize_datetime(datetime.now(timezone.utc))
    document = {
        "id": str(uuid.uuid4()),
        "organization_id": organization_id_or_default(),
        "governorate": clean_governorate,
        "union_committee": clean_committee,
        "bank_id": payload.bank_id,
        "bank_name": bank["name"],
        "payment_date": serialize_date(payload.payment_date),
        "amount": round(float(payload.amount), 2),
        "allocated_amount": round(sum(item["amount"] for item in allocations), 2),
        "unapplied_amount": remaining_amount,
        "receipt_number": normalize_member_text(payload.receipt_number) if payload.receipt_number else None,
        "notes": normalize_member_text(payload.notes) if payload.notes else None,
        "allocations": allocations,
        "created_at": now_iso,
        "updated_at": now_iso,
    }
    await db.membership_batch_payments.insert_one(document.copy())
    await journal_for_membership_batch_payment(document, current_user)
    return MembershipBatchPaymentResponse(**hydrate_membership_batch_payment(document))


@api_router.get("/memberships/batch-payments", response_model=List[MembershipBatchPaymentResponse])
async def list_membership_batch_payments(_: dict = Depends(require_any_permission(["enter_deposits", "view_reports", "manage_users"]))):
    require_social_solidarity_membership(_)
    documents = await db.membership_batch_payments.find(with_organization({}), {"_id": 0}).sort("payment_date", -1).sort("created_at", -1).to_list(500)
    return [MembershipBatchPaymentResponse(**hydrate_membership_batch_payment(document)) for document in documents]


@api_router.get("/memberships/collection-report", response_model=MembershipCollectionReportResponse)
async def get_membership_collection_report(
    as_of_date: Optional[date] = Query(default=None),
    group_by: Literal["committee", "governorate"] = Query(default="committee"),
    _: dict = Depends(require_any_permission(["enter_deposits", "view_reports", "manage_users"])),
):
    require_social_solidarity_membership(_)
    as_of = as_of_date or date.today()
    documents = await db.memberships.find(with_organization({}), {"_id": 0}).to_list(10000)
    paid_map = await membership_paid_allocations_map(as_of)
    groups: dict[str, dict] = {}
    for document in documents:
        enriched = await enrich_membership_financials(document, as_of, paid_map)
        key = enriched.get("governorate") if group_by == "governorate" else f"{enriched.get('governorate') or 'غير محدد'} / {enriched.get('union_committee') or 'غير محدد'}"
        if key not in groups:
            groups[key] = {
                "group_type": group_by,
                "group_name": key,
                "governorate": enriched.get("governorate"),
                "union_committee": None if group_by == "governorate" else enriched.get("union_committee"),
                "members_count": 0,
                "active_members": 0,
                "total_due": 0.0,
                "total_collected": 0.0,
                "remaining_balance": 0.0,
            }
        groups[key]["members_count"] += 1
        if (enriched.get("status") or "active") == "active":
            groups[key]["active_members"] += 1
        groups[key]["total_due"] = round(groups[key]["total_due"] + float(enriched.get("current_due") or 0), 2)
        groups[key]["total_collected"] = round(groups[key]["total_collected"] + float(enriched.get("total_collected") or 0), 2)
        groups[key]["remaining_balance"] = round(groups[key]["remaining_balance"] + float(enriched.get("remaining_balance") or 0), 2)
    rows = [MembershipCollectionReportRow(**value) for value in sorted(groups.values(), key=lambda item: item["group_name"])]
    totals = MembershipCollectionReportRow(
        group_type=group_by,
        group_name="الإجمالي",
        members_count=sum(row.members_count for row in rows),
        active_members=sum(row.active_members for row in rows),
        total_due=round(sum(row.total_due for row in rows), 2),
        total_collected=round(sum(row.total_collected for row in rows), 2),
        remaining_balance=round(sum(row.remaining_balance for row in rows), 2),
    )
    return MembershipCollectionReportResponse(as_of_date=as_of, group_by=group_by, rows=rows, totals=totals)


@api_router.get("/memberships/annual-report", response_model=MembershipAnnualReportResponse)
async def get_membership_annual_report(year: int = Query(..., ge=1900, le=2200), _: dict = Depends(require_any_permission(["enter_deposits", "view_reports", "manage_users"]))):
    require_social_solidarity_membership(_)
    documents = await db.memberships.find(with_organization({}), {"_id": 0}).to_list(10000)
    report_date = date(year, 12, 31)
    paid_map = await membership_paid_allocations_map(report_date)
    groups: dict[tuple[str, str], dict] = {}
    for document in documents:
        financial = await enrich_membership_financials(document, report_date, paid_map)
        governorate = document.get("governorate") or "غير محدد"
        committee = document.get("union_committee") or "غير محدد"
        key = (governorate, committee)
        if key not in groups:
            groups[key] = {"governorate": governorate, "union_committee": committee, "total_registered": 0, "new_members": 0, "retired_members": 0, "current_membership_size": 0, "total_due": 0.0, "total_collected": 0.0, "remaining_balance": 0.0}
        groups[key]["total_registered"] += 1
        created_at = document.get("created_at")
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at)
            except ValueError:
                created_at = None
        if isinstance(created_at, datetime) and created_at.year == year:
            groups[key]["new_members"] += 1
        if int(document.get("retirement_year") or 0) == year or ((document.get("status") or "active") in NON_ACTIVE_MEMBERSHIP_STATUSES and parse_date_field(document.get("status_effective_date"), report_date).year == year):
            groups[key]["retired_members"] += 1
        retired_before_or_during_year = int(document.get("retirement_year") or 9999) <= year or ((document.get("status") or "active") in NON_ACTIVE_MEMBERSHIP_STATUSES and parse_date_field(document.get("status_effective_date"), report_date) <= report_date)
        if not retired_before_or_during_year and (document.get("status") or "active") == "active":
            groups[key]["current_membership_size"] += 1
        groups[key]["total_due"] = round(groups[key]["total_due"] + float(financial.get("current_due") or 0), 2)
        groups[key]["total_collected"] = round(groups[key]["total_collected"] + float(financial.get("total_collected") or 0), 2)
        groups[key]["remaining_balance"] = round(groups[key]["remaining_balance"] + float(financial.get("remaining_balance") or 0), 2)
    rows = [MembershipAnnualReportRow(**value) for value in sorted(groups.values(), key=lambda item: (item["governorate"], item["union_committee"]))]
    totals = MembershipAnnualReportRow(
        governorate="الإجمالي",
        union_committee="كل اللجان",
        total_registered=sum(row.total_registered for row in rows),
        new_members=sum(row.new_members for row in rows),
        retired_members=sum(row.retired_members for row in rows),
        current_membership_size=sum(row.current_membership_size for row in rows),
        total_due=round(sum(row.total_due for row in rows), 2),
        total_collected=round(sum(row.total_collected for row in rows), 2),
        remaining_balance=round(sum(row.remaining_balance for row in rows), 2),
    )
    return MembershipAnnualReportResponse(year=year, rows=rows, totals=totals)


@api_router.get("/journal-entries", response_model=List[JournalEntryResponse])
async def list_journal_entries(
    from_date: Optional[date] = Query(default=None),
    to_date: Optional[date] = Query(default=None),
    source_type: Optional[str] = Query(default=None),
    entry_category: Optional[str] = Query(default=None),
    entry_item: Optional[str] = Query(default=None),
    _: dict = Depends(require_any_permission(["enter_deposits", "view_reports", "manage_expenses", "manage_revenues"])),
):
    query = with_organization({"is_reversal": {"$ne": True}})
    if from_date or to_date:
        query["entry_date"] = {}
        if from_date:
            query["entry_date"]["$gte"] = from_date.isoformat()
        if to_date:
            query["entry_date"]["$lte"] = to_date.isoformat()
    if source_type:
        query["source_type"] = source_type
    category_sources = {
        "fixed_assets": ["fixed_asset", "asset_depreciation"],
        "revenues": ["revenue", "membership_batch_payment"],
        "expenses": ["expense"],
        "deposits": ["deposit", "deposit_interest"],
        "banking_expenses": ["banking_expense"],
        "custody_advances": ["custody_advance", "custody_advance_settlement"],
        "membership": ["membership_batch_payment"],
        "reconciliations": ["reconciliation"],
        "inventory": ["inventory"],
        "misc_creditors": ["misc_creditor"],
        "tax_engine": ["tax_invoice"],
    }
    if entry_category and entry_category != "all" and not source_type:
        query["source_type"] = {"$in": category_sources.get(entry_category, [])}
    if entry_item and entry_item != "all":
        query["$or"] = [
            {"description": {"$regex": entry_item, "$options": "i"}},
            {"reference": {"$regex": entry_item, "$options": "i"}},
            {"lines.account_name": {"$regex": entry_item, "$options": "i"}},
            {"lines.notes": {"$regex": entry_item, "$options": "i"}},
        ]
    documents = await db.journal_entries.find(query, {"_id": 0}).sort("entry_number", -1).to_list(2000)
    return [JournalEntryResponse(**hydrate_journal_entry(document)) for document in documents]


@api_router.get("/journal-entry-classifications")
async def journal_entry_classifications(_: dict = Depends(require_any_permission(["enter_deposits", "view_reports", "manage_expenses", "manage_revenues"]))):
    return {
        "categories": [
            {"key": "all", "label": "كل الأصناف", "items": [{"key": "all", "label": "الكل"}]},
            {"key": "fixed_assets", "label": "الأصول الثابتة", "items": [{"key": "all", "label": "الكل"}, {"key": "خزينة حديد", "label": "خزينة حديد"}, {"key": "أثاث", "label": "أثاث"}, {"key": "أجهزة", "label": "أجهزة"}, {"key": "سيارات", "label": "سيارات"}, {"key": "معدات", "label": "معدات"}]},
            {"key": "revenues", "label": "الإيرادات", "items": [{"key": "all", "label": "الكل"}, {"key": "إيرادات أوامر الدفع", "label": "أوامر الدفع"}, {"key": "إيرادات فوائد الحساب الجاري", "label": "فوائد الحساب الجاري"}, {"key": "إيرادات فوائد ودائع", "label": "فوائد الودائع"}]},
            {"key": "expenses", "label": "المصروفات", "items": [{"key": "all", "label": "الكل"}, {"key": "مصروفات عمومية", "label": "مصروفات عمومية"}, {"key": "إعانات وفاة", "label": "إعانات وفاة"}, {"key": "ربط وديعة", "label": "ربط وديعة"}]},
            {"key": "deposits", "label": "الودائع", "items": [{"key": "all", "label": "الكل"}, {"key": "ودائع لأجل", "label": "أصل الوديعة"}, {"key": "إيرادات فوائد ودائع", "label": "فوائد الودائع"}]},
            {"key": "banking_expenses", "label": "المصروفات البنكية", "items": [{"key": "all", "label": "الكل"}, {"key": "المصروفات البنكية", "label": "المصروفات البنكية"}]},
            {"key": "custody_advances", "label": "العهد والسلف", "items": [{"key": "all", "label": "الكل"}, {"key": "العهد والسلف", "label": "العهد والسلف"}, {"key": "تسوية العهد والسلف", "label": "تسوية العهد والسلف"}]},
            {"key": "membership", "label": "العضوية", "items": [{"key": "all", "label": "الكل"}, {"key": "اشتراكات العضوية", "label": "اشتراكات العضوية"}]},
            {"key": "reconciliations", "label": "التسويات البنكية", "items": [{"key": "all", "label": "الكل"}, {"key": "تسوية", "label": "تسويات بنكية"}]},
            {"key": "inventory", "label": "المخزون", "items": [{"key": "all", "label": "الكل"}, {"key": "وارد", "label": "وارد مخزون"}, {"key": "صرف", "label": "منصرف مخزون"}, {"key": "المخزون", "label": "حساب المخزون"}]},
            {"key": "misc_creditors", "label": "الدائنون المتنوعون", "items": [{"key": "all", "label": "الكل"}, {"key": "إثبات", "label": "إثبات الالتزام"}, {"key": "سداد", "label": "سداد الدائن"}, {"key": "دائنون متنوعون", "label": "حساب الدائنين"}]},
            {"key": "tax_engine", "label": "محرك الضريبة", "items": [{"key": "all", "label": "الكل"}, {"key": "فاتورة ضريبية", "label": "فواتير ضريبية"}]},
        ]
    }


@api_router.get("/treasury-banks", response_model=TreasuryBanksReport)
async def get_treasury_banks_report(
    from_date: Optional[date] = Query(default=None),
    to_date: Optional[date] = Query(default=None),
    account_id: Optional[str] = Query(default=None),
    account_kind: Optional[Literal["all", "bank", "cash"]] = Query(default="all"),
    movement_type: Optional[Literal["all", "revenue", "expense", "opening"]] = Query(default="all"),
    search: Optional[str] = Query(default=None, max_length=120),
    _: dict = Depends(require_any_permission(["enter_deposits", "view_reports", "manage_expenses", "manage_revenues"])),
):
    if from_date and to_date and from_date > to_date:
        raise HTTPException(status_code=400, detail="تاريخ البداية يجب أن يكون قبل تاريخ النهاية")
    organization_id = organization_id_or_default()
    await sync_chart_accounts_for_organization(organization_id)
    banks = await get_all_banks()
    bank_names = {bank.get("id"): bank.get("name") for bank in banks}
    account_documents = await db.chart_accounts.find(
        with_organization({"is_active": True, "is_postable": True, "$or": [{"system_key": "cash_box"}, {"system_key": {"$regex": "^bank:"}}]}, organization_id),
        {"_id": 0},
    ).sort("code", 1).to_list(1000)
    treasury_accounts = []
    for account in account_documents:
        system_key = account.get("system_key") or ""
        kind = "cash" if system_key == "cash_box" else "bank"
        if account_kind in {"bank", "cash"} and kind != account_kind:
            continue
        if account_id and account_id != "all" and account.get("id") != account_id:
            continue
        bank_id = account.get("bank_id") or (system_key.split(":", 1)[1] if system_key.startswith("bank:") else None)
        treasury_accounts.append({
            "id": account.get("id"),
            "code": account.get("code"),
            "name": account.get("name") or (bank_names.get(bank_id) if bank_id else "الخزينة"),
            "account_kind": kind,
            "bank_id": bank_id,
            "bank_name": bank_names.get(bank_id) if bank_id else None,
        })
    selected_ids = {item["id"] for item in treasury_accounts if item.get("id")}
    accounts_by_id = {account.get("id"): account for account in account_documents if account.get("id") in selected_ids}
    accounts_by_code = {account.get("code"): account for account in account_documents if account.get("id") in selected_ids}
    accounts_by_bank_id = {account.get("bank_id") or str(account.get("system_key") or "").split(":", 1)[1]: account for account in account_documents if str(account.get("system_key") or "").startswith("bank:") and account.get("id") in selected_ids}
    cash_account = next((account for account in account_documents if account.get("system_key") == "cash_box" and account.get("id") in selected_ids), None)
    entry_query = {"status": "approved", "is_reversal": {"$ne": True}}
    if to_date:
        entry_query["entry_date"] = {"$lte": to_date.isoformat()}
    entries = await db.journal_entries.find(
        with_organization(entry_query, organization_id),
        {"_id": 0, "id": 1, "entry_number": 1, "entry_date": 1, "description": 1, "reference": 1, "source_type": 1, "lines": 1},
    ).sort("entry_date", 1).sort("entry_number", 1).to_list(100000)

    def resolve_treasury_account(line: dict) -> Optional[dict]:
        account = accounts_by_id.get(line.get("account_id")) or accounts_by_code.get(line.get("account_code"))
        if not account and line.get("bank_id"):
            account = accounts_by_bank_id.get(line.get("bank_id"))
        if not account and normalize_arabic_key(line.get("account_name")) in {"الخزينه", "خزينه"}:
            account = cash_account
        return account if account and account.get("id") in selected_ids else None

    def movement_key_for(entry: dict, debit: float, credit: float) -> str:
        if entry.get("source_type") == "opening_balance":
            return "opening"
        return "revenue" if debit >= credit else "expense"

    movement_labels = {"revenue": "إيراد", "expense": "مصروف", "opening": "رصيد افتتاحي"}
    normalized_search = normalize_arabic_key(search) if search else ""

    # تجميع كل الحركات (قيود اليومية + فوائد الودائع الدورية) في قائمة واحدة ثم ترتيبها زمنياً
    raw_movements: List[dict] = []
    for entry in entries:
        entry_date = date.fromisoformat(str(entry.get("entry_date")))
        for line in entry.get("lines", []):
            account = resolve_treasury_account(line)
            if not account:
                continue
            debit = round(float(line.get("debit") or 0), 2)
            credit = round(float(line.get("credit") or 0), 2)
            delta = round(debit - credit, 2)
            if delta == 0:
                continue
            key = movement_key_for(entry, debit, credit)
            bank_id = account.get("bank_id") or (str(account.get("system_key") or "").split(":", 1)[1] if str(account.get("system_key") or "").startswith("bank:") else line.get("bank_id"))
            account_kind_value = "cash" if account.get("system_key") == "cash_box" else "bank"
            bank_name = bank_names.get(bank_id) if bank_id else None
            searchable_text = normalize_arabic_key(" ".join([str(entry.get("entry_number") or ""), entry.get("description") or "", entry.get("reference") or "", account.get("name") or "", bank_name or "", line.get("notes") or ""]))
            raw_movements.append({
                "entry_date": entry_date,
                "entry_number": int(entry.get("entry_number") or 0),
                "entry_id": entry.get("id"),
                "description": entry.get("description") or line.get("notes") or "-",
                "reference": entry.get("reference"),
                "source_type": entry.get("source_type") or "manual",
                "movement_key": key,
                "account_id": account.get("id"),
                "account_code": account.get("code"),
                "account_name": account.get("name") or "-",
                "account_kind": account_kind_value,
                "bank_id": bank_id,
                "bank_name": bank_name,
                "debit": debit,
                "credit": credit,
                "delta": delta,
                "searchable_text": searchable_text,
                "is_interest": False,
            })

    # فوائد الودائع الدورية: تُحسب من نفس بوابة فوائد الودائع (calculate_interest_rows)
    # وتُرحَّل تلقائياً على البنك في يوم استحقاقها الشهري لتطابق كشف الحساب الفعلي
    if to_date and account_kind != "cash":
        deposit_documents = await db.deposits.find(with_organization({"status": {"$ne": "closed"}}, organization_id), {"_id": 0}).to_list(100000)
        for deposit_document in deposit_documents:
            deposit_bank_id = deposit_document.get("bank_id")
            bank_account = accounts_by_bank_id.get(deposit_bank_id)
            if not bank_account or bank_account.get("id") not in selected_ids:
                continue
            deposit_obj = Deposit(**hydrate_deposit(deposit_document))
            creation_dt = normalize_datetime(deposit_obj.creation_datetime)
            maturity_year = normalize_datetime(deposit_obj.maturity_datetime).year
            anniversary_day = creation_dt.day
            deposit_bank_name = bank_names.get(deposit_bank_id)
            for interest_year in range(creation_dt.year, min(maturity_year, to_date.year) + 1):
                rows_for_year, _, _ = calculate_interest_rows(deposit_obj, interest_year)
                for row in rows_for_year:
                    interest_amount = round(float(row.interest_amount or 0), 2)
                    if interest_amount <= 0:
                        continue
                    last_day = calendar.monthrange(interest_year, row.month_number)[1]
                    credit_date = date(interest_year, row.month_number, min(anniversary_day, last_day))
                    if credit_date > to_date:
                        continue
                    raw_movements.append({
                        "entry_date": credit_date,
                        "entry_number": 0,
                        "entry_id": None,
                        "description": f"فائدة وديعة رقم {deposit_obj.deposit_number} عن {row.month}",
                        "reference": deposit_obj.deposit_number,
                        "source_type": "deposit_interest",
                        "movement_key": "revenue",
                        "account_id": bank_account.get("id"),
                        "account_code": bank_account.get("code"),
                        "account_name": bank_account.get("name") or "-",
                        "account_kind": "bank",
                        "bank_id": deposit_bank_id,
                        "bank_name": deposit_bank_name,
                        "debit": interest_amount,
                        "credit": 0.0,
                        "delta": interest_amount,
                        "searchable_text": normalize_arabic_key(" ".join(["فائدة وديعة", str(deposit_obj.deposit_number or ""), bank_account.get("name") or "", deposit_bank_name or ""])),
                        "is_interest": True,
                    })

    raw_movements.sort(key=lambda item: (item["entry_date"], item["entry_number"], 1 if item["is_interest"] else 0))

    opening_balance = 0.0
    running_by_account = {account_id_value: 0.0 for account_id_value in selected_ids}
    transactions: List[TreasuryBanksTransaction] = []
    total_revenues = 0.0
    total_expenses = 0.0
    serial = 1
    for movement in raw_movements:
        account_id_value = movement["account_id"]
        delta = movement["delta"]
        running_by_account[account_id_value] = round(running_by_account.get(account_id_value, 0.0) + delta, 2)
        if from_date and movement["entry_date"] < from_date:
            opening_balance = round(opening_balance + delta, 2)
            continue
        key = movement["movement_key"]
        if movement_type and movement_type != "all" and key != movement_type:
            continue
        if normalized_search and normalized_search not in movement["searchable_text"]:
            continue
        if key != "opening" and delta > 0:
            total_revenues = round(total_revenues + delta, 2)
        if key != "opening" and delta < 0:
            total_expenses = round(total_expenses + abs(delta), 2)
        transactions.append(TreasuryBanksTransaction(
            serial=serial,
            entry_id=movement["entry_id"],
            entry_number=movement["entry_number"],
            entry_date=movement["entry_date"],
            description=movement["description"],
            reference=movement["reference"],
            source_type=movement["source_type"],
            movement_type=movement_labels.get(key, key),
            account_id=account_id_value,
            account_code=movement["account_code"],
            account_name=movement["account_name"],
            account_kind=movement["account_kind"],
            bank_id=movement["bank_id"],
            bank_name=movement["bank_name"],
            debit=movement["debit"],
            credit=movement["credit"],
            amount=abs(delta),
            running_balance=running_by_account.get(account_id_value, 0.0),
        ))
        serial += 1
    total_balance = round(sum(running_by_account.values()), 2)
    summary = TreasuryBanksSummary(
        organization_id=organization_id,
        from_date=from_date,
        to_date=to_date,
        opening_balance=opening_balance,
        total_balance=total_balance,
        total_revenues=total_revenues,
        total_expenses=total_expenses,
        net_movement=round(total_revenues - total_expenses, 2),
        transactions_count=len(transactions),
    )
    return TreasuryBanksReport(summary=summary, accounts=[TreasuryBanksAccount(**item) for item in treasury_accounts], transactions=transactions)


@api_router.get("/erp-health-report", response_model=ErpHealthReportResponse)
async def generate_erp_health_report(request: Request, _: dict = Depends(require_super_admin)):
    organization_id = organization_id_or_default()
    report_id = str(uuid.uuid4())
    direct_download_url = f"{public_app_base_url(request)}/api/erp-health-report/files/{report_id}"
    report = await build_erp_health_report_payload(organization_id, direct_download_url, report_id)
    write_erp_health_pdf(report, GENERATED_REPORTS_DIR / f"{report_id}.pdf")
    return report


@api_router.get("/erp-health-report/pdf")
async def download_new_erp_health_report_pdf(request: Request, _: dict = Depends(require_super_admin)):
    organization_id = organization_id_or_default()
    report_id = str(uuid.uuid4())
    direct_download_url = f"{public_app_base_url(request)}/api/erp-health-report/files/{report_id}"
    report = await build_erp_health_report_payload(organization_id, direct_download_url, report_id)
    output_path = GENERATED_REPORTS_DIR / f"{report_id}.pdf"
    write_erp_health_pdf(report, output_path)
    return FileResponse(str(output_path), media_type="application/pdf", filename="ERP-Health-Report.pdf")


@api_router.get("/erp-health-report/files/{report_id}")
async def download_generated_erp_health_report(report_id: str, _: dict = Depends(require_super_admin)):
    if not re.fullmatch(r"[a-f0-9\-]{36}", report_id):
        raise HTTPException(status_code=404, detail="التقرير غير موجود")
    output_path = GENERATED_REPORTS_DIR / f"{report_id}.pdf"
    if not output_path.exists():
        raise HTTPException(status_code=404, detail="التقرير غير موجود أو انتهت صلاحيته")
    return FileResponse(str(output_path), media_type="application/pdf", filename="ERP-Health-Report.pdf")


@api_router.get("/bank-prints/{path:path}")
async def disabled_bank_prints_routes(path: str):
    raise HTTPException(status_code=404, detail="تم إلغاء مطبوعات بنكية بناءً على طلب المستخدم")


@api_router.get("/inventory/items", response_model=List[InventoryItemResponse])
async def list_inventory_items(_: dict = Depends(require_any_permission(["enter_deposits", "view_reports", "manage_expenses", "manage_revenues"]))):
    await sync_chart_accounts_for_organization(organization_id_or_default())
    documents = await db.inventory_items.find(with_organization({}), {"_id": 0}).sort("item_name", 1).to_list(5000)
    return [InventoryItemResponse(**hydrate_inventory_item(document)) for document in documents]


@api_router.post("/inventory/items", response_model=InventoryItemResponse)
async def create_inventory_item(payload: InventoryItemCreate, _: dict = Depends(require_any_permission(["enter_deposits", "manage_expenses", "manage_revenues"]))):
    existing = await db.inventory_items.find_one(with_organization({"item_code": payload.item_code.strip()}), {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail="كود الصنف مسجل من قبل")
    now_iso = serialize_datetime(datetime.now(timezone.utc))
    document = attach_organization({
        "id": str(uuid.uuid4()),
        "item_code": payload.item_code.strip(),
        "item_name": payload.item_name.strip(),
        "unit": payload.unit.strip(),
        "quantity_balance": 0.0,
        "value_balance": 0.0,
        "average_cost": 0.0,
        "created_at": now_iso,
        "updated_at": now_iso,
    })
    await db.inventory_items.insert_one(document.copy())
    return InventoryItemResponse(**hydrate_inventory_item(document))


@api_router.get("/inventory/movements", response_model=List[InventoryMovementResponse])
async def list_inventory_movements(
    from_date: Optional[date] = Query(default=None),
    to_date: Optional[date] = Query(default=None),
    item_id: Optional[str] = Query(default=None),
    _: dict = Depends(require_any_permission(["enter_deposits", "view_reports", "manage_expenses", "manage_revenues"])),
):
    query = with_organization({})
    if item_id:
        query["item_id"] = item_id
    if from_date or to_date:
        query["movement_date"] = {}
        if from_date:
            query["movement_date"]["$gte"] = from_date.isoformat()
        if to_date:
            query["movement_date"]["$lte"] = to_date.isoformat()
    documents = await db.inventory_movements.find(query, {"_id": 0}).sort("movement_date", -1).to_list(5000)
    return [InventoryMovementResponse(**hydrate_inventory_movement(document)) for document in documents]


@api_router.post("/inventory/movements", response_model=InventoryMovementResponse)
async def create_inventory_movement(payload: InventoryMovementCreate, current_user: dict = Depends(require_any_permission(["enter_deposits", "manage_expenses", "manage_revenues"]))):
    await sync_chart_accounts_for_organization(organization_id_or_default())
    item = await ensure_inventory_item_from_payload(payload)
    quantity = round(float(payload.quantity), 4)
    current_qty = round(float(item.get("quantity_balance") or 0), 4)
    current_value = round(float(item.get("value_balance") or 0), 2)
    average_cost = round(float(item.get("average_cost") or 0), 4)
    unit_cost = round(float(payload.unit_cost if payload.unit_cost is not None else average_cost), 4)
    if payload.movement_type == "in" and unit_cost <= 0:
        raise HTTPException(status_code=400, detail="يجب إدخال تكلفة الوحدة في حركة الوارد")
    if payload.movement_type == "out":
        if current_qty < quantity:
            raise HTTPException(status_code=400, detail="رصيد الصنف لا يكفي لتنفيذ المنصرف")
        if unit_cost <= 0:
            unit_cost = average_cost
    total_value = round(quantity * unit_cost, 2)
    next_qty = round(current_qty + quantity, 4) if payload.movement_type == "in" else round(current_qty - quantity, 4)
    next_value = round(current_value + total_value, 2) if payload.movement_type == "in" else round(max(0, current_value - total_value), 2)
    next_average = round(next_value / next_qty, 4) if next_qty > 0 else 0.0
    now_iso = serialize_datetime(datetime.now(timezone.utc))
    document = attach_organization({
        "id": str(uuid.uuid4()),
        "movement_date": payload.movement_date.isoformat(),
        "item_id": item["id"],
        "item_code": item.get("item_code"),
        "item_name": item.get("item_name"),
        "unit": item.get("unit") or payload.unit or "وحدة",
        "movement_type": payload.movement_type,
        "quantity": quantity,
        "unit_cost": unit_cost,
        "total_value": total_value,
        "quantity_balance_after": next_qty,
        "value_balance_after": next_value,
        "journal_entry_id": None,
        "description": payload.description.strip(),
        "reference": (payload.reference or "").strip() or None,
        "created_at": now_iso,
        "updated_at": now_iso,
    })
    await db.inventory_movements.insert_one(document.copy())
    journal = await journal_for_inventory_movement({**document, "movement_date": payload.movement_date}, current_user)
    await db.inventory_movements.update_one(with_organization({"id": document["id"]}), {"$set": {"journal_entry_id": journal.get("id") if journal else None}})
    document["journal_entry_id"] = journal.get("id") if journal else None
    await db.inventory_items.update_one(with_organization({"id": item["id"]}), {"$set": {"quantity_balance": next_qty, "value_balance": next_value, "average_cost": next_average, "updated_at": now_iso}})
    return InventoryMovementResponse(**hydrate_inventory_movement(document))


@api_router.get("/misc-creditors", response_model=List[MiscCreditorResponse])
async def list_misc_creditors(_: dict = Depends(require_any_permission(["enter_deposits", "view_reports", "manage_expenses", "manage_revenues"]))):
    documents = await db.misc_creditors.find(with_organization({}), {"_id": 0}).sort("creditor_name", 1).to_list(5000)
    return [MiscCreditorResponse(**hydrate_misc_creditor(document)) for document in documents]


@api_router.post("/misc-creditors", response_model=MiscCreditorResponse)
async def create_misc_creditor(payload: MiscCreditorCreate, _: dict = Depends(require_any_permission(["enter_deposits", "manage_expenses", "manage_revenues"]))):
    now_iso = serialize_datetime(datetime.now(timezone.utc))
    document = attach_organization({
        "id": str(uuid.uuid4()),
        "creditor_code": (payload.creditor_code or "").strip() or None,
        "creditor_name": payload.creditor_name.strip(),
        "notes": (payload.notes or "").strip() or None,
        "balance": 0.0,
        "created_at": now_iso,
        "updated_at": now_iso,
    })
    await db.misc_creditors.insert_one(document.copy())
    return MiscCreditorResponse(**hydrate_misc_creditor(document))


@api_router.get("/misc-creditors/movements", response_model=List[MiscCreditorMovementResponse])
async def list_misc_creditor_movements(
    from_date: Optional[date] = Query(default=None),
    to_date: Optional[date] = Query(default=None),
    creditor_id: Optional[str] = Query(default=None),
    _: dict = Depends(require_any_permission(["enter_deposits", "view_reports", "manage_expenses", "manage_revenues"])),
):
    query = with_organization({})
    if creditor_id:
        query["creditor_id"] = creditor_id
    if from_date or to_date:
        query["movement_date"] = {}
        if from_date:
            query["movement_date"]["$gte"] = from_date.isoformat()
        if to_date:
            query["movement_date"]["$lte"] = to_date.isoformat()
    documents = await db.misc_creditor_movements.find(query, {"_id": 0}).sort("movement_date", -1).to_list(5000)
    return [MiscCreditorMovementResponse(**hydrate_misc_creditor_movement(document)) for document in documents]


@api_router.post("/misc-creditors/movements", response_model=MiscCreditorMovementResponse)
async def create_misc_creditor_movement(payload: MiscCreditorMovementCreate, current_user: dict = Depends(require_any_permission(["enter_deposits", "manage_expenses", "manage_revenues"]))):
    await sync_chart_accounts_for_organization(organization_id_or_default())
    creditor = await ensure_misc_creditor_from_payload(payload)
    amount = round(float(payload.amount), 2)
    current_balance = round(float(creditor.get("balance") or 0), 2)
    if payload.movement_type == "payment" and amount > current_balance:
        raise HTTPException(status_code=400, detail="لا يمكن سداد مبلغ أكبر من رصيد الدائن")
    next_balance = round(current_balance + amount, 2) if payload.movement_type == "obligation" else round(current_balance - amount, 2)
    bank_name = None
    if payload.bank_id:
        bank_name = ensure_bank(payload.bank_id)["name"]
    now_iso = serialize_datetime(datetime.now(timezone.utc))
    document = attach_organization({
        "id": str(uuid.uuid4()),
        "movement_date": payload.movement_date.isoformat(),
        "creditor_id": creditor["id"],
        "creditor_name": creditor.get("creditor_name"),
        "movement_type": payload.movement_type,
        "amount": amount,
        "balance_after": next_balance,
        "bank_id": payload.bank_id,
        "bank_name": bank_name,
        "journal_entry_id": None,
        "description": payload.description.strip(),
        "reference": (payload.reference or "").strip() or None,
        "created_at": now_iso,
        "updated_at": now_iso,
    })
    await db.misc_creditor_movements.insert_one(document.copy())
    journal = await journal_for_misc_creditor_movement({**document, "movement_date": payload.movement_date}, current_user)
    await db.misc_creditor_movements.update_one(with_organization({"id": document["id"]}), {"$set": {"journal_entry_id": journal.get("id") if journal else None}})
    document["journal_entry_id"] = journal.get("id") if journal else None
    await db.misc_creditors.update_one(with_organization({"id": creditor["id"]}), {"$set": {"balance": next_balance, "updated_at": now_iso}})
    return MiscCreditorMovementResponse(**hydrate_misc_creditor_movement(document))


@api_router.post("/journal-entries", response_model=JournalEntryResponse)
async def create_manual_journal_entry(payload: JournalEntryCreate, current_user: dict = Depends(require_admin)):
    document = await save_journal_entry_document(
        entry_date=payload.entry_date,
        description=payload.description,
        reference=payload.reference,
        source_type="manual",
        source_id=None,
        is_auto=False,
        current_user=current_user,
        lines=[line.model_dump() for line in payload.lines],
    )
    return JournalEntryResponse(**hydrate_journal_entry(document))


@api_router.put("/journal-entries/{entry_id}", response_model=JournalEntryResponse)
async def update_journal_entry(entry_id: str, payload: JournalEntryCreate, current_user: dict = Depends(require_admin)):
    existing = await db.journal_entries.find_one(with_organization({"id": entry_id}), {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="القيد غير موجود")
    normalized_lines, total_debit, total_credit = await normalize_journal_lines([line.model_dump() for line in payload.lines])
    updates = {
        "entry_date": payload.entry_date.isoformat(),
        "description": payload.description.strip(),
        "reference": payload.reference,
        "lines": normalized_lines,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "updated_by": current_user.get("id"),
        "updated_by_name": real_name_for_user(current_user),
        "updated_at": serialize_datetime(datetime.now(timezone.utc)),
    }
    await db.journal_entries.update_one(with_organization({"id": entry_id}), {"$set": updates})
    updated = await db.journal_entries.find_one(with_organization({"id": entry_id}), {"_id": 0})
    return JournalEntryResponse(**hydrate_journal_entry(updated))


@api_router.delete("/journal-entries/{entry_id}", response_model=JournalEntryResponse)
async def reverse_manual_journal_entry(entry_id: str, current_user: dict = Depends(require_admin)):
    existing = await db.journal_entries.find_one(with_organization({"id": entry_id}), {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="القيد غير موجود")
    if existing.get("is_reversal"):
        raise HTTPException(status_code=400, detail="لا يمكن حذف قيد عكسي")
    # إلغاء القيود العكسية بالكامل: حذف نهائي للقيد بدل إنشاء قيد عكسي،
    # ليظهر أثر الإلغاء فوراً وبشكل صحيح في جميع التقارير.
    await db.journal_entries.delete_many(with_organization({"id": entry_id}))
    return JournalEntryResponse(**hydrate_journal_entry(existing))


@api_router.post("/maintenance/purge-reversals")
async def purge_reversal_entries(current_user: dict = Depends(require_admin)):
    # تنظيف لمرة واحدة: حذف جميع القيود العكسية القديمة + القيود الأصلية التي سبق عكسها
    # (كانت تمثل عمليات محذوفة/ملغاة) لضبط الأرصدة بعد إلغاء نظام القيود العكسية.
    reversals = await db.journal_entries.delete_many({"is_reversal": True})
    originals = await db.journal_entries.delete_many({"reversal_entry_id": {"$exists": True, "$ne": None}})
    return {
        "deleted_reversals": reversals.deleted_count,
        "deleted_reversed_originals": originals.deleted_count,
        "message": "تم تنظيف القيود العكسية القديمة بنجاح",
    }


DATA_EXPORT_COLLECTIONS = [
    "banks", "bank_settings", "banking_tariffs", "banking_manual_charges", "deleted_banks",
    "deposits", "journal_entries", "journal_counters", "accounting_rules", "chart_accounts",
    "revenues", "expenses", "reconciliations", "financial_periods",
    "memberships", "membership_batch_payments",
    "fixed_assets", "fixed_asset_depreciations", "fixed_asset_category_settings",
    "custody_advances", "misc_creditors", "misc_creditor_movements",
    "inventory_items", "inventory_movements",
    "electronic_invoices", "einvoice_customers",
]


@api_router.get("/maintenance/export-data")
async def export_organization_data(current_user: dict = Depends(require_admin)):
    organization_id = organization_id_or_default()
    payload = {
        "type": "bank-deposit-erp-export",
        "version": 1,
        "organization_id": organization_id,
        "exported_at": serialize_datetime(datetime.now(timezone.utc)),
        "collections": {},
    }
    for collection_name in DATA_EXPORT_COLLECTIONS:
        collection = getattr(db, collection_name)
        documents = await collection.find(with_organization({}, organization_id), {"_id": 0}).to_list(200000)
        payload["collections"][collection_name] = documents
    organization = await db.organizations.find_one({"id": organization_id}, {"_id": 0})
    payload["organization"] = organization
    body = json.dumps(payload, ensure_ascii=False, default=str)
    filename = f"erp-data-{organization_id}-{date.today().isoformat()}.json"
    return Response(
        content=body,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@api_router.post("/maintenance/import-data")
async def import_organization_data(payload: dict, current_user: dict = Depends(require_admin)):
    if payload.get("type") != "bank-deposit-erp-export":
        raise HTTPException(status_code=400, detail="ملف غير صالح: هذا ليس ملف تصدير بيانات صحيح")
    organization_id = organization_id_or_default()
    collections = payload.get("collections") or {}
    summary = {}
    for collection_name in DATA_EXPORT_COLLECTIONS:
        documents = collections.get(collection_name)
        if documents is None:
            continue
        collection = getattr(db, collection_name)
        await collection.delete_many(with_organization({}, organization_id))
        cleaned = []
        for document in documents:
            document.pop("_id", None)
            document["organization_id"] = organization_id
            cleaned.append(document)
        if cleaned:
            await collection.insert_many(cleaned)
        summary[collection_name] = len(cleaned)
    return {"message": "تم استيراد البيانات بنجاح", "organization_id": organization_id, "imported": summary}


class DepositRoundingUpdate(BaseModel):
    use_daily_rounding: bool
    password: str


@api_router.get("/admin/deposits-rounding")
async def list_deposits_rounding(_: dict = Depends(require_super_admin)):
    documents = await db.deposits.find(with_organization({}), {"_id": 0}).sort("created_at", -1).to_list(5000)
    banks_map = {bank["id"]: bank.get("name") for bank in await get_all_banks()}
    items = []
    for document in documents:
        deposit = hydrate_deposit(document)
        items.append({
            "id": deposit.get("id"),
            "bank_id": deposit.get("bank_id"),
            "bank_name": banks_map.get(deposit.get("bank_id"), deposit.get("bank_id")),
            "deposit_number": deposit.get("deposit_number"),
            "account_number": deposit.get("account_number"),
            "amount": deposit.get("amount"),
            "monthly_interest_rate": deposit.get("monthly_interest_rate"),
            "use_daily_rounding": bool(deposit.get("use_daily_rounding", True)),
        })
    return {"deposits": items}


@api_router.patch("/admin/deposits/{deposit_id}/rounding")
async def update_deposit_rounding(deposit_id: str, payload: DepositRoundingUpdate, current_user: dict = Depends(require_super_admin)):
    admin_user = await db.users.find_one({"id": current_user.get("id")}, {"_id": 0})
    if not admin_user or not verify_password(payload.password, admin_user.get("password_hash", "")):
        raise HTTPException(status_code=403, detail="كلمة مرور السوبر أدمن غير صحيحة")
    result = await db.deposits.find_one_and_update(
        with_organization({"id": deposit_id}),
        {"$set": {"use_daily_rounding": bool(payload.use_daily_rounding), "updated_at": serialize_datetime(datetime.now(timezone.utc))}},
        return_document=ReturnDocument.AFTER,
        projection={"_id": 0},
    )
    if not result:
        raise HTTPException(status_code=404, detail="الوديعة غير موجودة")
    state = "تفعيل" if payload.use_daily_rounding else "إلغاء"
    return {
        "message": f"تم {state} تقريب الفائدة اليومية للوديعة {result.get('deposit_number')}",
        "deposit_id": deposit_id,
        "use_daily_rounding": bool(payload.use_daily_rounding),
    }



@api_router.get("/chart-accounts", response_model=List[ChartAccountResponse])
async def list_chart_accounts(_: dict = Depends(require_any_permission(["enter_deposits", "view_reports", "manage_expenses", "manage_revenues"]))):
    await sync_chart_accounts_for_organization(organization_id_or_default())
    documents = await db.chart_accounts.find(with_organization({}), {"_id": 0}).sort("code", 1).to_list(2000)
    return [ChartAccountResponse(**hydrate_chart_account(document)) for document in documents]


@api_router.post("/chart-accounts/sync", response_model=List[ChartAccountResponse])
async def sync_chart_accounts(_: dict = Depends(require_admin)):
    documents = await sync_chart_accounts_for_organization(organization_id_or_default())
    return [ChartAccountResponse(**hydrate_chart_account(document)) for document in documents]


@api_router.get("/ledger", response_model=GeneralLedgerReport)
async def get_general_ledger(
    account_id: Optional[str] = Query(default=None),
    account_code: Optional[str] = Query(default=None),
    from_date: Optional[date] = Query(default=None),
    to_date: Optional[date] = Query(default=None),
    _: dict = Depends(require_any_permission(["enter_deposits", "view_reports", "manage_expenses", "manage_revenues"])),
):
    organization_id = organization_id_or_default()
    await sync_chart_accounts_for_organization(organization_id)
    opening_deposit_documents = await db.deposits.find(with_organization({"is_opening_balance_deposit": True}, organization_id), {"_id": 0, "id": 1}).to_list(100000)
    opening_deposit_source_ids = {item.get("id") for item in opening_deposit_documents if item.get("id")}

    def is_opening_deposit_entry(entry: dict) -> bool:
        return entry.get("source_type") == "deposit" and (entry.get("source_id") in opening_deposit_source_ids or "رصيد افتتاحي وديعة قائمة" in str(entry.get("description") or ""))

    deposit_period_interest = await calculate_total_deposit_interest_for_period(organization_id, from_date, to_date)
    period_entry_query = {"is_reversal": {"$ne": True}, "status": "approved", "source_type": {"$nin": REPORT_EXCLUDED_SOURCE_TYPES}}
    if from_date or to_date:
        date_query = {}
        if from_date:
            date_query["$gte"] = from_date.isoformat()
        if to_date:
            date_query["$lte"] = to_date.isoformat()
        period_entry_query["entry_date"] = date_query
    entries = await db.journal_entries.find(with_organization(period_entry_query, organization_id), {"_id": 0}).sort("entry_date", 1).sort("entry_number", 1).to_list(100000)
    movement_entries = [entry for entry in entries if not is_opening_deposit_entry(entry)]
    opening_entries_inside_period = [entry for entry in entries if is_opening_deposit_entry(entry) and (not to_date or str(entry.get("entry_date") or "") <= to_date.isoformat())]
    if account_id == "all" or account_code == "all":
        accounts = await db.chart_accounts.find(with_organization({"is_postable": True, "is_active": True}, organization_id), {"_id": 0}).to_list(10000)
        accounts_by_id = {account.get("id"): account for account in accounts if account.get("id")}
        accounts_by_code = {account.get("code"): account for account in accounts if account.get("code")}
        accounts_by_system_key = {account.get("system_key"): account for account in accounts if account.get("system_key")}
        period_movement_account_ids = set()
        for entry in movement_entries:
            for line in entry.get("lines", []):
                account = accounts_by_id.get(line.get("account_id")) or accounts_by_code.get(line.get("account_code"))
                if not account:
                    continue
                if round(float(line.get("debit") or 0), 2) != 0 or round(float(line.get("credit") or 0), 2) != 0:
                    period_movement_account_ids.add(account.get("id"))
        accrued_interest_account = accounts_by_system_key.get("accrued_deposit_interest")
        deposit_interest_revenue_account = accounts_by_system_key.get("deposit_interest_revenue")
        if deposit_period_interest > 0:
            if accrued_interest_account:
                period_movement_account_ids.add(accrued_interest_account.get("id"))
            if deposit_interest_revenue_account:
                period_movement_account_ids.add(deposit_interest_revenue_account.get("id"))
        rows = []
        total_debit = 0.0
        total_credit = 0.0
        account_openings = {account_id_value: 0.0 for account_id_value in period_movement_account_ids}
        if from_date:
            for account in accounts:
                if account.get("id") in account_openings:
                    account_openings[account.get("id")] = round(float(account.get("opening_balance") or 0) * (-1 if account.get("nature") == "credit" else 1), 2)
            prior_entries = await db.journal_entries.find(with_organization({"is_reversal": {"$ne": True}, "status": "approved", "source_type": {"$nin": REPORT_EXCLUDED_SOURCE_TYPES}, "entry_date": {"$lt": from_date.isoformat()}}, organization_id), {"_id": 0, "lines": 1}).to_list(100000)
            for entry in prior_entries + opening_entries_inside_period:
                for line in entry.get("lines", []):
                    account = accounts_by_id.get(line.get("account_id")) or accounts_by_code.get(line.get("account_code"))
                    if account and account.get("id") in account_openings:
                        account_openings[account.get("id")] = round(account_openings[account.get("id")] + float(line.get("debit") or 0) - float(line.get("credit") or 0), 2)
        else:
            for account in accounts:
                if account.get("id") in account_openings:
                    account_openings[account.get("id")] = round(float(account.get("opening_balance") or 0) * (-1 if account.get("nature") == "credit" else 1), 2)
        account_running_balances = account_openings.copy()
        opening_balance_total = round(sum(account_openings.values()), 2)
        serial = 1
        for entry in movement_entries:
            entry_date = date.fromisoformat(str(entry.get("entry_date")))
            for line in entry.get("lines", []):
                account = accounts_by_id.get(line.get("account_id")) or accounts_by_code.get(line.get("account_code"))
                if not account or account.get("id") not in period_movement_account_ids:
                    continue
                debit = round(float(line.get("debit") or 0), 2)
                credit = round(float(line.get("credit") or 0), 2)
                account_running_balances[account.get("id")] = round(account_running_balances.get(account.get("id"), 0.0) + debit - credit, 2)
                total_debit = round(total_debit + debit, 2)
                total_credit = round(total_credit + credit, 2)
                rows.append(GeneralLedgerLine(
                    serial=serial,
                    entry_id=entry.get("id"),
                    entry_number=int(entry.get("entry_number") or 0),
                    entry_date=entry_date,
                    source_type=entry.get("source_type") or "manual",
                    reference=entry.get("reference"),
                    account_id=account.get("id"),
                    account_code=account.get("code"),
                    account_name=account.get("name"),
                    description=entry.get("description") or line.get("notes") or "-",
                    debit=debit,
                    credit=credit,
                    balance=account_running_balances[account.get("id")],
                ))
                serial += 1
        synthetic_date = to_date or from_date or date.today()
        synthetic_description = f"إجمالي فوائد الودائع عن الفترة من {from_date.isoformat() if from_date else '-'} إلى {to_date.isoformat() if to_date else '-'}"
        if deposit_period_interest > 0 and accrued_interest_account:
            account_running_balances[accrued_interest_account.get("id")] = round(account_running_balances.get(accrued_interest_account.get("id"), 0.0) + deposit_period_interest, 2)
            total_debit = round(total_debit + deposit_period_interest, 2)
            rows.append(GeneralLedgerLine(serial=serial, entry_id="deposit-interest-period-total", entry_number=0, entry_date=synthetic_date, source_type="deposit_interest", reference="DEPOSIT-INTEREST-PERIOD", account_id=accrued_interest_account.get("id"), account_code=accrued_interest_account.get("code"), account_name=accrued_interest_account.get("name"), description=synthetic_description, debit=deposit_period_interest, credit=0.0, balance=account_running_balances[accrued_interest_account.get("id")]))
            serial += 1
        if deposit_period_interest > 0 and deposit_interest_revenue_account:
            account_running_balances[deposit_interest_revenue_account.get("id")] = round(account_running_balances.get(deposit_interest_revenue_account.get("id"), 0.0) - deposit_period_interest, 2)
            total_credit = round(total_credit + deposit_period_interest, 2)
            rows.append(GeneralLedgerLine(serial=serial, entry_id="deposit-interest-period-total", entry_number=0, entry_date=synthetic_date, source_type="deposit_interest", reference="DEPOSIT-INTEREST-PERIOD", account_id=deposit_interest_revenue_account.get("id"), account_code=deposit_interest_revenue_account.get("code"), account_name=deposit_interest_revenue_account.get("name"), description=synthetic_description, debit=0.0, credit=deposit_period_interest, balance=account_running_balances[deposit_interest_revenue_account.get("id")]))
            serial += 1
        closing_balance = round(sum(account_running_balances.values()), 2)
        return GeneralLedgerReport(account=None, account_scope="all", from_date=from_date, to_date=to_date, opening_balance=opening_balance_total, total_debit=total_debit, total_credit=total_credit, closing_balance=closing_balance, rows=rows)
    account_query = {"id": account_id} if account_id else {"code": account_code} if account_code else {"is_postable": True}
    account = await db.chart_accounts.find_one(with_organization(account_query, organization_id), {"_id": 0})
    if not account:
        raise HTTPException(status_code=404, detail="الحساب غير موجود")
    opening_balance = round(float(account.get("opening_balance") or 0), 2)
    if account.get("system_key") == "term_deposits":
        opening_balance = await active_deposit_principal_total(organization_id, from_date or to_date or date.today())
        for entry in opening_entries_inside_period:
            for line in entry.get("lines", []):
                if line.get("account_id") == account.get("id") or line.get("account_code") == account.get("code"):
                    opening_balance = round(opening_balance + float(line.get("debit") or 0) - float(line.get("credit") or 0), 2)
    elif from_date:
        prior_entries = await db.journal_entries.find(with_organization({"is_reversal": {"$ne": True}, "status": "approved", "source_type": {"$nin": REPORT_EXCLUDED_SOURCE_TYPES}, "entry_date": {"$lt": from_date.isoformat()}}, organization_id), {"_id": 0, "lines": 1}).to_list(100000)
        for entry in prior_entries + opening_entries_inside_period:
            for line in entry.get("lines", []):
                if line.get("account_id") != account.get("id") and line.get("account_code") != account.get("code"):
                    continue
                opening_balance = round(opening_balance + float(line.get("debit") or 0) - float(line.get("credit") or 0), 2)
    running_balance = opening_balance
    rows = []
    total_debit = 0.0
    total_credit = 0.0
    serial = 1
    deposit_cache: dict[str, Optional[Deposit]] = {}
    for entry in movement_entries:
        if account.get("system_key") == "term_deposits" and entry.get("source_type") == "deposit" and (from_date or to_date):
            source_id = entry.get("source_id")
            if source_id not in deposit_cache:
                deposit_document = await db.deposits.find_one(with_organization({"id": source_id}, organization_id), {"_id": 0}) if source_id else None
                deposit_cache[source_id] = Deposit(**hydrate_deposit(deposit_document)) if deposit_document else None
            linked_deposit = deposit_cache.get(source_id)
            if linked_deposit and not deposit_is_active_in_period(linked_deposit, from_date or date.min, to_date or date.max):
                continue
        entry_date = date.fromisoformat(str(entry.get("entry_date")))
        for line in entry.get("lines", []):
            if line.get("account_id") != account.get("id") and line.get("account_code") != account.get("code"):
                continue
            debit = round(float(line.get("debit") or 0), 2)
            credit = round(float(line.get("credit") or 0), 2)
            direction_value = debit - credit if account.get("nature") == "debit" else credit - debit
            running_balance = round(running_balance + direction_value, 2)
            total_debit = round(total_debit + debit, 2)
            total_credit = round(total_credit + credit, 2)
            rows.append(GeneralLedgerLine(
                serial=serial,
                entry_id=entry.get("id"),
                entry_number=int(entry.get("entry_number") or 0),
                entry_date=entry_date,
                source_type=entry.get("source_type") or "manual",
                reference=entry.get("reference"),
                account_id=account.get("id"),
                account_code=account.get("code"),
                account_name=account.get("name"),
                description=entry.get("description") or line.get("notes") or "-",
                debit=debit,
                credit=credit,
                balance=running_balance,
            ))
            serial += 1
    synthetic_date = to_date or from_date or date.today()
    if deposit_period_interest > 0 and account.get("system_key") in {"accrued_deposit_interest", "deposit_interest_revenue"}:
        debit = deposit_period_interest if account.get("system_key") == "accrued_deposit_interest" else 0.0
        credit = deposit_period_interest if account.get("system_key") == "deposit_interest_revenue" else 0.0
        direction_value = debit - credit if account.get("nature") == "debit" else credit - debit
        running_balance = round(running_balance + direction_value, 2)
        total_debit = round(total_debit + debit, 2)
        total_credit = round(total_credit + credit, 2)
        rows.append(GeneralLedgerLine(
            serial=serial,
            entry_id="deposit-interest-period-total",
            entry_number=0,
            entry_date=synthetic_date,
            source_type="deposit_interest",
            reference="DEPOSIT-INTEREST-PERIOD",
            account_id=account.get("id"),
            account_code=account.get("code"),
            account_name=account.get("name"),
            description=f"إجمالي فوائد الودائع عن الفترة من {from_date.isoformat() if from_date else '-'} إلى {to_date.isoformat() if to_date else '-'}",
            debit=debit,
            credit=credit,
            balance=running_balance,
        ))
    return GeneralLedgerReport(
        account=ChartAccountResponse(**hydrate_chart_account(account)),
        account_scope="single",
        from_date=from_date,
        to_date=to_date,
        opening_balance=opening_balance,
        total_debit=total_debit,
        total_credit=total_credit,
        closing_balance=running_balance,
        rows=rows,
    )


@api_router.get("/rules-engine/rules", response_model=List[AccountingRuleResponse])
async def list_rules_engine_rules(_: dict = Depends(require_any_permission(["view_reports", "manage_expenses", "manage_revenues"]))) :
    organization_id = organization_id_or_default()
    rules = await list_accounting_rules_for_organization(organization_id)
    return [AccountingRuleResponse(**rule) for rule in rules]


@api_router.post("/rules-engine/rules", response_model=AccountingRuleResponse)
async def save_rules_engine_rule(payload: AccountingRuleCreate, current_user: dict = Depends(require_admin)):
    organization_id = organization_id_or_default()
    now_iso = serialize_datetime(datetime.now(timezone.utc))
    rule_id = f"rule-{payload.event_type.lower()}-{uuid.uuid4().hex[:8]}"
    payload_data = payload.model_dump()
    payload_data["priority"] = calculate_rule_priority(payload_data)
    document = {
        **payload_data,
        "id": rule_id,
        "organization_id": organization_id,
        "is_system": False,
        "created_by": current_user.get("id"),
        "created_by_name": real_name_for_user(current_user),
        "created_at": now_iso,
        "updated_at": now_iso,
    }
    await db.accounting_rules.insert_one(document.copy())
    return AccountingRuleResponse(**document)


@api_router.put("/rules-engine/rules/{rule_id}", response_model=AccountingRuleResponse)
async def update_rules_engine_rule(rule_id: str, payload: AccountingRuleUpdate, current_user: dict = Depends(require_admin)):
    organization_id = organization_id_or_default()
    rules = await list_accounting_rules_for_organization(organization_id)
    existing = next((rule for rule in rules if rule.get("id") == rule_id), None)
    if not existing:
        raise HTTPException(status_code=404, detail="القاعدة غير موجودة")
    payload_data = payload.model_dump()
    payload_data["priority"] = calculate_rule_priority(payload_data)
    now_iso = serialize_datetime(datetime.now(timezone.utc))
    document = {
        **existing,
        **payload_data,
        "id": rule_id,
        "organization_id": organization_id,
        "is_system": False,
        "updated_by": current_user.get("id"),
        "updated_by_name": real_name_for_user(current_user),
        "updated_at": now_iso,
        "created_at": existing.get("created_at") or now_iso,
    }
    await db.accounting_rules.update_one(with_organization({"id": rule_id}, organization_id), {"$set": document}, upsert=True)
    return AccountingRuleResponse(**document)


@api_router.post("/rules-engine/simulate", response_model=RuleSimulationResponse)
async def simulate_rules_engine(payload: RuleSimulationRequest, _: dict = Depends(require_any_permission(["view_reports", "manage_expenses", "manage_revenues"]))) :
    return await simulate_accounting_rule(payload)


@api_router.post("/chart-accounts", response_model=ChartAccountResponse)
async def create_chart_account(payload: ChartAccountCreate, _: dict = Depends(require_admin)):
    organization_id = organization_id_or_default()
    if await db.chart_accounts.find_one(with_organization({"code": payload.code.strip()}, organization_id), {"_id": 0, "id": 1}):
        raise HTTPException(status_code=400, detail="كود الحساب موجود بالفعل داخل هذه الجهة")
    parent = await db.chart_accounts.find_one(with_organization({"id": payload.parent_id}, organization_id), {"_id": 0}) if payload.parent_id else None
    now_iso = serialize_datetime(datetime.now(timezone.utc))
    document = {
        "id": str(uuid.uuid4()),
        "organization_id": organization_id,
        "code": payload.code.strip(),
        "name": payload.name.strip(),
        "account_type": payload.account_type,
        "nature": payload.nature,
        "parent_id": parent.get("id") if parent else None,
        "parent_code": parent.get("code") if parent else None,
        "parent_name": parent.get("name") if parent else None,
        "level": (int(parent.get("level", 1)) + 1) if parent else 1,
        "is_postable": payload.is_postable,
        "is_active": payload.is_active,
        "opening_balance": round(float(payload.opening_balance or 0), 2),
        "system_key": None,
        "created_at": now_iso,
        "updated_at": now_iso,
    }
    await db.chart_accounts.insert_one(document.copy())
    return ChartAccountResponse(**hydrate_chart_account(document))


@api_router.put("/chart-accounts/{account_id}", response_model=ChartAccountResponse)
async def update_chart_account(account_id: str, payload: ChartAccountUpdate, _: dict = Depends(require_admin)):
    organization_id = organization_id_or_default()
    existing = await db.chart_accounts.find_one(with_organization({"id": account_id}, organization_id), {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="الحساب غير موجود")
    parent = await db.chart_accounts.find_one(with_organization({"id": payload.parent_id}, organization_id), {"_id": 0}) if payload.parent_id else None
    updates = {"updated_at": serialize_datetime(datetime.now(timezone.utc))}
    for field in ["name", "nature", "is_postable", "is_active", "opening_balance"]:
        value = getattr(payload, field)
        if value is not None:
            updates[field] = value.strip() if isinstance(value, str) else value
    if payload.parent_id is not None:
        updates.update({"parent_id": parent.get("id") if parent else None, "parent_code": parent.get("code") if parent else None, "parent_name": parent.get("name") if parent else None, "level": (int(parent.get("level", 1)) + 1) if parent else 1})
    await db.chart_accounts.update_one(with_organization({"id": account_id}, organization_id), {"$set": updates})
    updated = await db.chart_accounts.find_one(with_organization({"id": account_id}, organization_id), {"_id": 0})
    return ChartAccountResponse(**hydrate_chart_account(updated))


@api_router.get("/trial-balance", response_model=TrialBalanceReport)
async def get_trial_balance(
    from_date: Optional[date] = Query(default=None),
    to_date: Optional[date] = Query(default=None),
    account_type: Optional[Literal["asset", "liability", "equity", "revenue", "expense"]] = Query(default=None),
    non_zero_only: bool = Query(default=False),
    _: dict = Depends(require_any_permission(["enter_deposits", "view_reports", "manage_expenses", "manage_revenues"])),
):
    organization_id = organization_id_or_default()
    return await calculate_trial_balance_report(
        organization_id=organization_id,
        from_date=from_date,
        to_date=to_date,
        account_type=account_type,
        non_zero_only=non_zero_only,
    )


@api_router.get("/financial-statements", response_model=FinancialStatementsReport)
async def get_financial_statements(
    from_date: Optional[date] = Query(default=None),
    to_date: Optional[date] = Query(default=None),
    _: dict = Depends(require_any_permission(["enter_deposits", "view_reports", "manage_expenses", "manage_revenues"])),
):
    organization_id = organization_id_or_default()
    return await calculate_financial_statements_report(organization_id=organization_id, from_date=from_date, to_date=to_date)


@api_router.get("/electronic-invoice/settings", response_model=ElectronicInvoiceSettingsResponse)
async def get_electronic_invoice_settings(_: dict = Depends(require_einvoice_enabled)):
    return ElectronicInvoiceSettingsResponse(**hydrate_einvoice_document(await get_einvoice_settings_document()))


@api_router.put("/electronic-invoice/settings", response_model=ElectronicInvoiceSettingsResponse)
async def save_electronic_invoice_settings(payload: ElectronicInvoiceSettings, _: dict = Depends(require_einvoice_admin)):
    now = datetime.now(timezone.utc)
    document = attach_organization({"id": "default", **payload.model_dump(), "updated_at": serialize_datetime(now)})
    await db.einvoice_settings.update_one(with_organization({"id": "default"}), {"$set": document}, upsert=True)
    return ElectronicInvoiceSettingsResponse(**hydrate_einvoice_document(document))


@api_router.get("/tax-engine/profile", response_model=TenantTaxProfileResponse)
async def get_tenant_tax_profile(_: dict = Depends(require_einvoice_enabled)):
    return tax_profile_response(await get_tax_profile_document())


@api_router.put("/tax-engine/profile", response_model=TenantTaxProfileResponse)
async def save_tenant_tax_profile(payload: TenantTaxProfile, current_user: dict = Depends(require_einvoice_admin)):
    existing = await db.tax_profiles.find_one(with_organization({"id": "default"}), {"_id": 0})
    now_iso = serialize_datetime(datetime.now(timezone.utc))
    document = attach_organization({"id": "default", **payload.model_dump(mode="json"), "updated_at": now_iso})
    if not existing:
        document["created_at"] = now_iso
    await db.tax_profiles.update_one(with_organization({"id": "default"}), {"$set": document}, upsert=True)
    await tax_engine_audit("TAX_PROFILE_SAVED", "تم حفظ ملف الضريبة الديناميكي للجهة Tenant Tax Profile.", current_user, before=existing, after=document)
    return tax_profile_response(document)


@api_router.post("/tax-engine/invoices", response_model=ElectronicInvoice)
async def create_tax_engine_invoice(payload: TaxEngineInvoiceCreate, current_user: dict = Depends(require_einvoice_permission(["enter_deposits", "manage_revenues", "manage_expenses"]))):
    profile = await get_tax_profile_document()
    calculation = calculate_tax_invoice_from_profile(payload, profile)
    bank = await ensure_bank_async(payload.bank_id)
    now_iso = serialize_datetime(datetime.now(timezone.utc))
    notes = validate_tax_profile_document(profile)
    if payload.customer_type != "person" and not payload.customer_tax_number:
        notes.append("الرقم الضريبي للطرف المقابل غير مسجل")
    status = "needs_review" if notes else "draft"
    document = attach_organization({
        "id": str(uuid.uuid4()),
        "revenue_id": payload.source_document_id if payload.source_document_type == "revenue" else None,
        "source_document_type": payload.source_document_type,
        "source_document_id": payload.source_document_id,
        "invoice_type": payload.invoice_type,
        "invoice_number": normalize_digit_text(payload.invoice_number),
        "issue_date": serialize_date(payload.issue_date),
        "customer_name": payload.customer_name.strip(),
        "customer_tax_number": payload.customer_tax_number,
        "customer_type": payload.customer_type,
        "service_code": calculation["lines"][0]["item_code"],
        "service_name": calculation["lines"][0]["description"],
        "description": " / ".join([line["description"] for line in calculation["lines"]]),
        "net_amount": calculation["net_amount"],
        "tax_rate": calculation["lines"][0]["tax_rate"],
        "tax_amount": calculation["tax_amount"],
        "total_amount": calculation["total_amount"],
        "payment_method": payload.payment_method,
        "bank_id": payload.bank_id,
        "bank_name": bank["name"],
        "status": status,
        "validation_notes": notes,
        "tax_engine_snapshot": calculation["tax_engine_snapshot"] | {"lines": calculation["lines"]},
        "journal_entry_id": None,
        "tax_invoice_entity_id": None,
        "created_at": now_iso,
        "updated_at": now_iso,
    })
    await db.electronic_invoices.insert_one(document.copy())
    await tax_engine_audit("TAX_INVOICE_CREATED", f"تم إنشاء فاتورة ضريبية {payload.invoice_type} بمحرك ضريبي ديناميكي دون API خارجي.", current_user, after=document)
    return ElectronicInvoice(**hydrate_einvoice_document(document))


@api_router.post("/tax-engine/invoices/{invoice_id}/approve", response_model=TaxEngineApprovalResponse)
async def approve_tax_engine_invoice_endpoint(invoice_id: str, current_user: dict = Depends(require_einvoice_permission(["enter_deposits", "manage_revenues", "manage_expenses"]))):
    invoice = await db.electronic_invoices.find_one(with_organization({"id": invoice_id}), {"_id": 0})
    if not invoice:
        raise HTTPException(status_code=404, detail="الفاتورة الضريبية غير موجودة")
    profile = await get_tax_profile_document()
    before = invoice.copy()
    journal, tax_entity = await approve_tax_engine_invoice(invoice, profile, current_user)
    updated = await db.electronic_invoices.find_one(with_organization({"id": invoice_id}), {"_id": 0})
    await tax_engine_audit("TAX_INVOICE_APPROVED", f"تم اعتماد الفاتورة الضريبية وربطها بالقيد رقم {journal.get('entry_number')} وكيان Tax Invoice مستقل.", current_user, before=before, after={"invoice": updated, "journal_entry_id": journal.get("id"), "tax_invoice_entity_id": tax_entity.get("id") if tax_entity else None})
    return TaxEngineApprovalResponse(invoice=ElectronicInvoice(**hydrate_einvoice_document(updated)), journal_entry_id=journal.get("id"), tax_invoice_entity_id=tax_entity.get("id"), message="تم اعتماد الفاتورة وإنشاء القيد والكيان الضريبي")


@api_router.get("/admin/eta-integration", response_model=EtaIntegrationSettingsResponse)
async def get_eta_integration_settings(_: dict = Depends(require_super_admin)):
    document = await get_eta_integration_document()
    return eta_public_response(document)


@api_router.put("/admin/eta-integration", response_model=EtaIntegrationSettingsResponse)
async def save_eta_integration_settings(payload: EtaIntegrationSettings, _: dict = Depends(require_super_admin)):
    existing = await get_eta_integration_document()
    now_iso = serialize_datetime(datetime.now(timezone.utc))
    updates = {
        "id": "default",
        "environment": payload.environment,
        "issuer_tax_number": (payload.issuer_tax_number or "").strip() or None,
        "issuer_name": (payload.issuer_name or "").strip() or None,
        "branch_code": (payload.branch_code or "0").strip() or "0",
        "activity_code": (payload.activity_code or "").strip() or None,
        "client_id": (payload.client_id or "").strip() or None,
        "sdk_command_template": (payload.sdk_command_template or "").strip() or None,
        "certificate_label": (payload.certificate_label or "").strip() or None,
        "auto_submit_after_generation": bool(payload.auto_submit_after_generation),
        "portal_url": (payload.portal_url or "").strip() or eta_urls(payload.environment)["portal"],
        "notes": (payload.notes or "").strip() or None,
        "updated_at": now_iso,
    }
    updates["client_secret_encrypted"] = existing.get("client_secret_encrypted") if payload.client_secret is None else eta_encrypt_secret(payload.client_secret.strip())
    updates["token_pin_encrypted"] = existing.get("token_pin_encrypted") if payload.token_pin is None else eta_encrypt_secret(payload.token_pin.strip())
    if not existing.get("created_at"):
        updates["created_at"] = now_iso
    updates = attach_organization(updates)
    await db.eta_integration_settings.update_one(with_organization({"id": "default"}), {"$set": updates}, upsert=True)
    document = await db.eta_integration_settings.find_one(with_organization({"id": "default"}), {"_id": 0})
    return eta_public_response(document)


@api_router.post("/admin/eta-integration/test-connection", response_model=EtaConnectionTestResponse)
async def test_eta_integration_connection(_: dict = Depends(require_super_admin)):
    document = await get_eta_integration_document()
    required = eta_required_items(document)
    if required:
        message = "استكمل بيانات الربط أولاً: " + "، ".join(required)
        await db.eta_integration_settings.update_one(with_organization({"id": "default"}), {"$set": {"last_connection_status": "configuration_required", "last_connection_message": message, "updated_at": serialize_datetime(datetime.now(timezone.utc))}}, upsert=True)
        return EtaConnectionTestResponse(status="configuration_required", message=message, environment=document.get("environment", "preprod"), required_items=required)
    try:
        eta_get_access_token(document)
        message = "تم الاتصال بخدمة هوية منظومة الضرائب واستلام رمز وصول بنجاح"
        await db.eta_integration_settings.update_one(with_organization({"id": "default"}), {"$set": {"last_connection_status": "configured", "last_connection_message": message, "updated_at": serialize_datetime(datetime.now(timezone.utc))}}, upsert=True)
        return EtaConnectionTestResponse(status="configured", message=message, environment=document.get("environment", "preprod"), token_received=True)
    except HTTPException as exc:
        message = str(exc.detail)
        await db.eta_integration_settings.update_one(with_organization({"id": "default"}), {"$set": {"last_connection_status": "error", "last_connection_message": message, "updated_at": serialize_datetime(datetime.now(timezone.utc))}}, upsert=True)
        return EtaConnectionTestResponse(status="error", message=message, environment=document.get("environment", "preprod"))


@api_router.get("/electronic-invoice/customers", response_model=List[ElectronicCustomer])
async def list_electronic_customers(_: dict = Depends(require_einvoice_permission(["enter_deposits", "view_reports", "manage_revenues"]))):
    documents = await db.einvoice_customers.find(with_organization({}), {"_id": 0}).sort("name", 1).to_list(1000)
    return [ElectronicCustomer(**hydrate_einvoice_document(document)) for document in documents]


@api_router.post("/electronic-invoice/customers", response_model=ElectronicCustomer)
async def create_electronic_customer(payload: ElectronicCustomerCreate, _: dict = Depends(require_einvoice_permission(["enter_deposits", "manage_revenues"]))):
    now = datetime.now(timezone.utc)
    document = attach_organization({"id": str(uuid.uuid4()), **payload.model_dump(), "created_at": serialize_datetime(now), "updated_at": serialize_datetime(now)})
    await db.einvoice_customers.insert_one(document.copy())
    return ElectronicCustomer(**hydrate_einvoice_document(document))


@api_router.put("/electronic-invoice/customers/{customer_id}", response_model=ElectronicCustomer)
async def update_electronic_customer(customer_id: str, payload: ElectronicCustomerCreate, _: dict = Depends(require_einvoice_permission(["enter_deposits", "manage_revenues"]))):
    existing = await db.einvoice_customers.find_one(with_organization({"id": customer_id}), {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="العميل غير موجود")
    updates = {**payload.model_dump(), "updated_at": serialize_datetime(datetime.now(timezone.utc))}
    await db.einvoice_customers.update_one(with_organization({"id": customer_id}), {"$set": updates})
    updated = await db.einvoice_customers.find_one(with_organization({"id": customer_id}), {"_id": 0})
    return ElectronicCustomer(**hydrate_einvoice_document(updated))


@api_router.get("/electronic-invoice/service-codes", response_model=List[ElectronicServiceCode])
async def list_electronic_service_codes(_: dict = Depends(require_einvoice_permission(["enter_deposits", "view_reports", "manage_revenues"]))):
    documents = await db.einvoice_service_codes.find(with_organization({}), {"_id": 0}).sort("is_default", -1).sort("name", 1).to_list(1000)
    return [ElectronicServiceCode(**hydrate_einvoice_document(document)) for document in documents]


@api_router.post("/electronic-invoice/service-codes", response_model=ElectronicServiceCode)
async def create_electronic_service_code(payload: ElectronicServiceCodeCreate, _: dict = Depends(require_einvoice_permission(["enter_deposits", "manage_revenues"]))):
    now = datetime.now(timezone.utc)
    if payload.is_default:
        await db.einvoice_service_codes.update_many(with_organization({}), {"$set": {"is_default": False}})
    document = attach_organization({"id": str(uuid.uuid4()), **payload.model_dump(), "created_at": serialize_datetime(now), "updated_at": serialize_datetime(now)})
    await db.einvoice_service_codes.insert_one(document.copy())
    return ElectronicServiceCode(**hydrate_einvoice_document(document))


@api_router.get("/electronic-invoices", response_model=List[ElectronicInvoice])
async def list_electronic_invoices(
    status: Optional[str] = Query(default=None),
    from_date: Optional[date] = Query(default=None),
    to_date: Optional[date] = Query(default=None),
    _: dict = Depends(require_einvoice_permission(["enter_deposits", "view_reports", "manage_revenues"])),
):
    query = with_organization({})
    if status and status != "all":
        query["status"] = status
    if from_date or to_date:
        query["issue_date"] = {}
        if from_date:
            query["issue_date"]["$gte"] = serialize_date(from_date)
        if to_date:
            query["issue_date"]["$lte"] = serialize_date(to_date)
    documents = await db.electronic_invoices.find(query, {"_id": 0}).sort("issue_date", -1).sort("created_at", -1).to_list(1000)
    return [ElectronicInvoice(**hydrate_einvoice_document(document)) for document in documents]


@api_router.post("/electronic-invoices/generate-from-revenues", response_model=List[ElectronicInvoice])
async def generate_electronic_invoices_from_revenues(_: dict = Depends(require_einvoice_permission(["enter_deposits", "manage_revenues"]))):
    profile = await get_tax_profile_document()
    rules = profile.get("tax_rules") or []
    default_rule = next((rule for rule in rules if rule.get("is_default")), rules[0] if rules else None)
    if not default_rule:
        raise HTTPException(status_code=400, detail="لا يمكن توليد فواتير من الإيرادات قبل ضبط Tax Profile وقاعدة ضريبية افتراضية")
    revenues = await db.revenues.find(with_organization({"bank_collection_status": "collected"}), {"_id": 0}).sort("issued_at", 1).to_list(1000)
    generated = []
    for revenue in revenues:
        if await db.electronic_invoices.find_one(with_organization({"source_document_type": "revenue", "source_document_id": revenue["id"]}), {"_id": 0, "id": 1}):
            continue
        customer_name = revenue.get("supplier_name") or revenue.get("value") or "عميل غير محدد"
        payload = TaxEngineInvoiceCreate(
            invoice_type="sales",
            invoice_number=f"TAX-{revenue.get('receipt_number')}",
            issue_date=date.fromisoformat(revenue.get("issued_at") or revenue.get("dated")),
            customer_name=customer_name,
            customer_type="person",
            payment_method=revenue.get("collection_method", "cash"),
            bank_id=revenue["bank_id"],
            source_document_type="revenue",
            source_document_id=revenue["id"],
            lines=[TaxInvoiceLineCreate(description=revenue.get("value") or customer_name, quantity=1, unit_price=float(revenue.get("amount", 0) or 0), item_code=default_rule["item_code"], tax_status=default_rule.get("tax_status", "standard"))],
        )
        generated.append(await create_tax_engine_invoice(payload, {"username": "tax-engine", "id": "system", "full_name": "Tax Engine"}))
    return generated


@api_router.post("/tax-engine/invoices/generate-from-operations", response_model=List[ElectronicInvoice])
async def generate_tax_invoices_from_operations(
    invoice_type: Literal["sales", "purchase"] = Query(default="sales"),
    current_user: dict = Depends(require_einvoice_permission(["enter_deposits", "manage_revenues", "manage_expenses"])),
):
    profile = await get_tax_profile_document()
    rules = profile.get("tax_rules") or []
    default_rule = next((rule for rule in rules if rule.get("is_default")), rules[0] if rules else None)
    if not default_rule:
        raise HTTPException(status_code=400, detail="لا يمكن توليد فواتير قبل ضبط Tax Profile وقاعدة ضريبية افتراضية")
    generated = []
    if invoice_type == "sales":
        source_documents = await db.revenues.find(with_organization({"bank_collection_status": "collected"}), {"_id": 0}).sort("issued_at", 1).to_list(1000)
        for revenue in source_documents:
            if await db.electronic_invoices.find_one(with_organization({"source_document_type": "revenue", "source_document_id": revenue["id"]}), {"_id": 0, "id": 1}):
                continue
            generated.append(await create_tax_engine_invoice(TaxEngineInvoiceCreate(
                invoice_type="sales",
                invoice_number=f"TAX-{revenue.get('receipt_number')}",
                issue_date=date.fromisoformat(revenue.get("issued_at") or revenue.get("dated")),
                customer_name=revenue.get("supplier_name") or revenue.get("value") or "عميل غير محدد",
                customer_type="person",
                payment_method=revenue.get("collection_method", "cash"),
                bank_id=revenue["bank_id"],
                source_document_type="revenue",
                source_document_id=revenue["id"],
                lines=[TaxInvoiceLineCreate(description=revenue.get("value") or "فاتورة بيع", quantity=1, unit_price=float(revenue.get("amount", 0) or 0), item_code=default_rule["item_code"], tax_status=default_rule.get("tax_status", "standard"))],
            ), current_user))
    else:
        source_documents = await db.expenses.find(with_organization({}), {"_id": 0}).sort("issued_at", 1).to_list(1000)
        for expense in source_documents:
            if await db.electronic_invoices.find_one(with_organization({"source_document_type": "expense", "source_document_id": expense["id"]}), {"_id": 0, "id": 1}):
                continue
            generated.append(await create_tax_engine_invoice(TaxEngineInvoiceCreate(
                invoice_type="purchase",
                invoice_number=f"TAX-{expense.get('expense_number')}",
                issue_date=date.fromisoformat(expense.get("issued_at")),
                customer_name=expense.get("transfer_to") or expense.get("gross_statement") or "مورد غير محدد",
                customer_type="company",
                payment_method=expense.get("payment_method", "bank_transfer"),
                bank_id=expense.get("bank_id") or (await get_all_banks())[0]["id"],
                source_document_type="expense",
                source_document_id=expense["id"],
                lines=[TaxInvoiceLineCreate(description=expense.get("gross_statement") or "فاتورة شراء", quantity=1, unit_price=float(expense.get("gross_amount", 0) or 0), item_code=default_rule["item_code"], tax_status=default_rule.get("tax_status", "standard"))],
            ), current_user))
    return generated


@api_router.patch("/electronic-invoices/{invoice_id}/status", response_model=ElectronicInvoice)
async def update_electronic_invoice_status(invoice_id: str, payload: ElectronicInvoiceStatusUpdate, _: dict = Depends(require_einvoice_permission(["enter_deposits", "manage_revenues"]))):
    existing = await db.electronic_invoices.find_one(with_organization({"id": invoice_id}), {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="الفاتورة غير موجودة")
    await db.electronic_invoices.update_one(with_organization({"id": invoice_id}), {"$set": {"status": payload.status, "updated_at": serialize_datetime(datetime.now(timezone.utc))}})
    updated = await db.electronic_invoices.find_one(with_organization({"id": invoice_id}), {"_id": 0})
    return ElectronicInvoice(**hydrate_einvoice_document(updated))


@api_router.post("/electronic-invoices/{invoice_id}/submit-eta", response_model=EtaSubmissionResponse)
async def submit_electronic_invoice_to_eta(invoice_id: str, _: dict = Depends(require_super_admin)):
    invoice = await db.electronic_invoices.find_one(with_organization({"id": invoice_id}), {"_id": 0})
    if not invoice:
        raise HTTPException(status_code=404, detail="الفاتورة غير موجودة")
    config = await get_eta_integration_document()
    required = eta_required_items(config)
    if required:
        return EtaSubmissionResponse(status="configuration_required", message="استكمل بيانات الربط أولاً: " + "، ".join(required), invoice_id=invoice_id)
    settings = await get_einvoice_settings_document()
    payload = build_eta_invoice_payload(invoice, settings, config)
    try:
        signed_payload = run_eta_sdk_signer(config, payload)
    except HTTPException as exc:
        return EtaSubmissionResponse(status="sdk_required", message=str(exc.detail), invoice_id=invoice_id)
    response_payload = eta_submit_signed_document(config, signed_payload)
    accepted_documents = response_payload.get("acceptedDocuments") or []
    first_document = accepted_documents[0] if accepted_documents else {}
    eta_document_uuid = first_document.get("uuid") or response_payload.get("uuid")
    eta_submission_id = response_payload.get("submissionId") or response_payload.get("submissionUUID")
    portal_url = f"{config.get('portal_url') or eta_urls(config.get('environment', 'preprod'))['portal']}/documents/{eta_document_uuid}" if eta_document_uuid else config.get("portal_url")
    updates = {
        "status": "submitted",
        "eta_document_uuid": eta_document_uuid,
        "eta_submission_id": eta_submission_id,
        "eta_portal_url": portal_url,
        "eta_last_response": response_payload,
        "updated_at": serialize_datetime(datetime.now(timezone.utc)),
    }
    await db.electronic_invoices.update_one(with_organization({"id": invoice_id}), {"$set": updates})
    return EtaSubmissionResponse(status="submitted", message="تم إرسال الفاتورة إلى منظومة الضرائب المصرية", invoice_id=invoice_id, eta_document_uuid=eta_document_uuid, eta_submission_id=eta_submission_id, eta_portal_url=portal_url, response_payload=response_payload)


@api_router.get("/admin/security/audit-logs", response_model=List[AuditLogResponse])
async def list_audit_logs(
    limit: int = Query(default=200, ge=1, le=1000),
    year: Optional[int] = Query(default=None, ge=2020, le=2200),
    month: Optional[int] = Query(default=None, ge=1, le=12),
    hour: Optional[int] = Query(default=None, ge=0, le=23),
    _: dict = Depends(require_admin),
):
    query = with_organization({})
    if year:
        start_month = month or 1
        start = datetime(year, start_month, 1, hour or 0, tzinfo=timezone.utc)
        if hour is not None:
            end = start + timedelta(hours=1)
        elif month:
            end = datetime(year + (1 if month == 12 else 0), 1 if month == 12 else month + 1, 1, tzinfo=timezone.utc)
        else:
            end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        query["created_at"] = {"$gte": serialize_datetime(start), "$lt": serialize_datetime(end)}
    documents = await db.audit_logs.find(query, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    return [AuditLogResponse(**hydrate_einvoice_document(document)) for document in documents]


@api_router.get("/admin/security/periods", response_model=List[PeriodLockResponse])
async def list_financial_periods(_: dict = Depends(get_current_user)):
    documents = await db.financial_periods.find(with_organization({}), {"_id": 0}).sort("year", -1).sort("month", -1).to_list(1000)
    return [PeriodLockResponse(**hydrate_einvoice_document(document)) for document in documents]


@api_router.post("/admin/security/periods", response_model=PeriodLockResponse)
async def save_financial_period(payload: PeriodLockCreate, current_user: dict = Depends(get_current_user)):
    permissions = current_user.get("permissions", {})
    if payload.action == "lock" and current_user.get("role") != "admin" and not permissions.get("lock_periods") and not permissions.get("manage_users"):
        raise HTTPException(status_code=403, detail="لا تملك صلاحية إقفال الفترات")
    if payload.action == "unlock" and current_user.get("role") != "admin" and not permissions.get("unlock_periods") and not permissions.get("manage_users"):
        raise HTTPException(status_code=403, detail="لا تملك صلاحية فتح الفترات")
    if payload.period_type == "monthly" and not payload.month:
        raise HTTPException(status_code=400, detail="يجب اختيار الشهر عند إقفال فترة شهرية")
    if payload.action == "unlock" and not payload.reason:
        raise HTTPException(status_code=400, detail="يجب كتابة سبب فتح الفترة")
    now = datetime.now(timezone.utc)
    document = {
        "id": f"{organization_id_or_default()}-{period_key(payload.period_type, payload.year, payload.month)}",
        "organization_id": organization_id_or_default(),
        "period_type": payload.period_type,
        "year": payload.year,
        "month": payload.month if payload.period_type == "monthly" else None,
        "is_locked": payload.action == "lock",
        "reason": payload.reason,
        "locked_by": current_user["id"],
        "locked_by_name": real_name_for_user(current_user),
        "created_at": serialize_datetime(now),
        "updated_at": serialize_datetime(now),
    }
    existing = await db.financial_periods.find_one(with_organization({"id": document["id"]}), {"_id": 0})
    if existing:
        document["created_at"] = existing.get("created_at", document["created_at"])
    await db.financial_periods.update_one(with_organization({"id": document["id"]}), {"$set": document}, upsert=True)
    return PeriodLockResponse(**hydrate_einvoice_document(document))


@api_router.get("/admin/security/report-approvals", response_model=List[ReportApprovalResponse])
async def list_report_approvals(_: dict = Depends(require_admin)):
    documents = await db.report_approvals.find(with_organization({}), {"_id": 0}).sort("created_at", -1).to_list(1000)
    return [ReportApprovalResponse(**hydrate_einvoice_document(document)) for document in documents]


@api_router.post("/admin/security/report-approvals", response_model=ReportApprovalResponse)
async def create_report_approval(payload: ReportApprovalCreate, current_user: dict = Depends(require_any_permission(["approve_reports", "manage_users"]))):
    now = datetime.now(timezone.utc)
    approval_number = approval_number_for_user(current_user)
    approver_name = real_name_for_user(current_user)
    document = {
        "id": str(uuid.uuid4()),
        "organization_id": organization_id_or_default(),
        "approval_number": approval_number,
        "report_type": payload.report_type,
        "report_name": payload.report_name,
        "report_reference": payload.report_reference,
        "period_label": payload.period_label,
        "status": payload.status,
        "approver_name": approver_name,
        "approver_title": payload.approver_title,
        "approved_by_user_id": current_user["id"],
        "approved_by_username": current_user["username"],
        "notes": payload.notes,
        "approval_phrase": f"تم اعتماد التقرير بواسطة: {approver_name} بتاريخ: {now.date().isoformat()}",
        "qr_payload": json.dumps({"approval_number": approval_number, "report_reference": payload.report_reference, "report_name": payload.report_name}, ensure_ascii=False),
        "created_at": serialize_datetime(now),
        "updated_at": serialize_datetime(now),
    }
    await db.report_approvals.insert_one(document.copy())
    return ReportApprovalResponse(**hydrate_einvoice_document(document))


BACKUP_COLLECTIONS = ["users", "banks", "bank_settings", "app_settings", "chart_accounts", "journal_entries", "journal_counters", "deposits", "revenues", "expenses", "fixed_assets", "fixed_asset_depreciations", "fixed_asset_catalog_items", "fixed_asset_catalog_hidden", "fixed_asset_category_settings", "custody_advances", "memberships", "membership_import_previews", "membership_batch_payments", "reconciliations", "banking_manual_charges", "banking_tariffs", "electronic_invoices", "tax_profiles", "tax_invoices", "einvoice_settings", "einvoice_customers", "einvoice_service_codes", "eta_integration_settings", "financial_periods", "report_approvals", "audit_logs"]
USER_DATA_PURGE_COLLECTIONS = ["journal_entries", "journal_counters", "deposits", "revenues", "expenses", "fixed_assets", "fixed_asset_depreciations", "custody_advances", "memberships", "membership_import_previews", "membership_batch_payments", "reconciliations", "banking_manual_charges", "electronic_invoices", "tax_profiles", "tax_invoices", "einvoice_customers", "einvoice_service_codes", "financial_periods", "report_approvals"]
TRAINING_DIR = ROOT_DIR.parent / "training_exports"
TRAINING_DIR.mkdir(parents=True, exist_ok=True)


def training_font(size: int):
    for path in [
        str(ROOT_DIR / "assets" / "fonts" / "NotoNaskhArabic-Regular.ttf"),
        str(ROOT_DIR / "assets" / "fonts" / "NotoNaskhArabic-Bold.ttf"),
        "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def latin_training_font(size: int):
    for path in [
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    ]:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def is_arabic_text(text: str) -> bool:
    return any("\u0600" <= char <= "\u06ff" for char in text)


def display_text(text: str) -> str:
    if is_arabic_text(text):
        return get_display(arabic_reshaper.reshape(text))
    return text


def wrap_words(text: str, width: int) -> List[str]:
    words = text.split()
    lines: List[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) > width and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines or [""]


def draw_rtl_text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, font, fill: str, anchor: str = "ra"):
    if is_arabic_text(text):
        draw.text(xy, arabic_reshaper.reshape(text), font=font, fill=fill, anchor=anchor, direction="rtl", language="ar")
    else:
        draw.text(xy, text, font=font, fill=fill, anchor=anchor)


def draw_ltr_text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, font, fill: str, anchor: str = "la"):
    draw.text(xy, text, font=latin_training_font(getattr(font, "size", 24)), fill=fill, anchor=anchor)


def draw_rtl_wrapped_text(draw: ImageDraw.ImageDraw, x: int, y: int, text: str, font, fill: str, width: int, line_gap: int) -> int:
    current_y = y
    for wrapped in wrap_words(text, width):
        draw_rtl_text(draw, (x, current_y), wrapped, font, fill)
        current_y += line_gap
    return current_y


def draw_ltr_wrapped_text(draw: ImageDraw.ImageDraw, x: int, y: int, text: str, font, fill: str, width: int, line_gap: int) -> int:
    current_y = y
    for wrapped in wrap_words(text, width):
        draw_ltr_text(draw, (x, current_y), wrapped, font, fill)
        current_y += line_gap
    return current_y


def english_manual_label(value: Optional[str], fallback: str) -> str:
    text = (value or "").strip()
    if not text:
        return fallback
    known_labels = {
        "يوسف عبد الغني احمد": "Youssef Abdelghany Ahmed",
        "يوسف عبد الغني أحمد": "Youssef Abdelghany Ahmed",
        "مشروع التكافل الاجتماعي": "Social Solidarity Project",
        "النقابة العامة": "General Union",
        "النقابة العامة للعاملين بالزراعة والري": "General Union for Agriculture and Irrigation Workers",
    }
    if text in known_labels:
        return known_labels[text]
    if re.search(r"[\u0600-\u06FF]", text):
        return fallback
    return text


def draw_training_cover(system_name: str, organization_name: str) -> Image.Image:
    image = Image.new("RGB", (1240, 1754), "#f8fafc")
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 0, 1240, 520], fill="#0f172a")
    draw.rectangle([70, 430, 1170, 1620], fill="white", outline="#d1fae5", width=4)
    draw_rtl_text(draw, (1120, 145), "كتيب إرشادات استخدام البرنامج", training_font(58), "#ffffff")
    draw_ltr_text(draw, (120, 225), "User Guide & Training Manual", training_font(38), "#6ee7b7")
    draw_rtl_text(draw, (1120, 620), system_name, training_font(54), "#0f172a")
    draw_rtl_text(draw, (1120, 720), organization_name, training_font(34), "#047857")
    cover_lines = [
        "دليل تدريبي شامل يشرح جميع وظائف وخصائص وأقسام البرنامج خطوة بخطوة.",
        "Comprehensive bilingual manual covering login, daily operations, security, reports, and financial statements.",
        "تم إعداد هذا الدليل تلقائياً حسب اسم البرنامج والجهة المختارة داخل النظام.",
    ]
    y = 870
    for line in cover_lines:
        if is_arabic_text(line):
            draw_rtl_text(draw, (1080, y), line, training_font(30), "#334155")
        else:
            draw_ltr_text(draw, (160, y), line, training_font(26), "#334155")
        y += 82
    draw_rtl_text(draw, (1080, 1505), "الإصدار التدريبي التفصيلي", training_font(30), "#064e3b")
    draw_ltr_text(draw, (160, 1565), datetime.now(timezone.utc).date().isoformat(), training_font(24), "#64748b")
    return image


def draw_training_index(system_name: str, pages: List[dict]) -> Image.Image:
    image = Image.new("RGB", (1240, 1754), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 0, 1240, 170], fill="#0f172a")
    draw_rtl_text(draw, (1120, 65), system_name, training_font(32), "white")
    draw_rtl_text(draw, (1120, 132), "فهرس الاستخدام / Table of Contents", training_font(38), "#6ee7b7")
    y = 245
    for index, page in enumerate(pages, start=3):
        if y > 1580:
            break
        draw_rtl_text(draw, (1080, y), f"{index - 2}. {page['title_ar']}", training_font(27), "#111827")
        draw_ltr_text(draw, (160, y + 34), page["title_en"], training_font(20), "#475569")
        draw_ltr_text(draw, (100, y), str(index), training_font(22), "#047857")
        y += 78
    draw_rtl_text(draw, (620, 1690), "صفحة 2", training_font(22), "#64748b", anchor="mm")
    return image


def draw_training_page(page: dict, page_no: int, system_name: str) -> Image.Image:
    image = Image.new("RGB", (1240, 1754), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 0, 1240, 170], fill="#0f172a")
    draw_rtl_text(draw, (1160, 55), system_name, training_font(30), "white")
    draw_rtl_text(draw, (1160, 125), page["title_ar"], training_font(38), "#6ee7b7")
    draw_ltr_text(draw, (90, 125), page["title_en"], training_font(22), "#cbd5e1")
    y = 225
    draw_rtl_text(draw, (1120, y), "الشرح التفصيلي", training_font(31), "#064e3b")
    y += 58
    for line in page.get("arabic", []):
        for wrapped in wrap_words(line, 68):
            draw_rtl_text(draw, (1120, y), wrapped, training_font(25), "#111827")
            y += 42
        y += 12
    y += 16
    draw_ltr_text(draw, (90, y), "English Guidance", training_font(27), "#0f766e")
    y += 52
    for line in page.get("english", []):
        for wrapped in wrap_words(line, 86):
            draw_ltr_text(draw, (90, y), wrapped, training_font(21), "#334155")
            y += 34
        y += 10
    draw_rtl_text(draw, (620, 1690), f"صفحة {page_no}", training_font(22), "#64748b", anchor="mm")
    return image


def ip_page_seal(page_no: int, fingerprint: Optional[str]) -> str:
    seed = f"{fingerprint or 'IP-NOT-SET'}|PAGE|{page_no}|BANK-DEPOSIT-SYSTEM".encode()
    return hashlib.sha256(seed).hexdigest().upper()[:40]


def draw_manual_cover(language: Literal["ar", "en"], system_name: str, organization_name: str, owner_name: str, fingerprint: str, source_digest: str) -> Image.Image:
    image = Image.new("RGB", (1240, 1754), "#f8fafc")
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 0, 1240, 1754], fill="#f8fafc")
    draw.rectangle([0, 0, 1240, 520], fill="#0f172a")
    draw.polygon([(0, 520), (1240, 360), (1240, 620), (0, 770)], fill="#065f46")
    draw.rectangle([78, 650, 1162, 1580], fill="white", outline="#99f6e4", width=5)
    if language == "ar":
        draw_rtl_text(draw, (1110, 135), "كتيب إرشادات البرنامج", training_font(54), "white")
        draw_rtl_text(draw, (1110, 230), "النسخة العربية", training_font(36), "#6ee7b7")
        y = draw_rtl_wrapped_text(draw, 1085, 760, "برنامج تكامل الحسابات المالية والختامية", training_font(40), "#0f172a", 34, 58)
        y = draw_rtl_wrapped_text(draw, 1085, y + 28, organization_name, training_font(28), "#047857", 48, 42)
        y = draw_rtl_wrapped_text(draw, 1085, max(y + 70, 995), f"اسم المبرمج: {owner_name}", training_font(30), "#111827", 48, 42)
        y = draw_rtl_wrapped_text(draw, 1085, y + 18, "لغة برمجة البرنامج: Python / FastAPI + React", training_font(24), "#334155", 56, 36)
        y = draw_rtl_wrapped_text(draw, 1085, y + 18, "درجة الحماية: مرتفعة - تشفير كلمات السر، قفل محاولات الدخول، نسخ احتياطي مشفر، وبصمة سلامة للملفات", training_font(22), "#334155", 64, 35)
        draw_rtl_wrapped_text(draw, 1085, y + 24, "تم إعداد هذا الكتيب للطباعة على ورق A4، ويشرح البرنامج من شاشة الدخول حتى إصدار الميزانية والقوائم الختامية.", training_font(23), "#475569", 62, 36)
        draw_ltr_text(draw, (155, 1445), f"IP Code: {fingerprint}", latin_training_font(20), "#0f766e")
        draw_ltr_text(draw, (155, 1495), f"Encrypted Page Seal: {ip_page_seal(1, fingerprint)}", latin_training_font(18), "#64748b")
        draw_ltr_text(draw, (155, 1540), f"Source Integrity: {source_digest[:48]}", latin_training_font(17), "#64748b")
    else:
        draw_ltr_text(draw, (120, 135), "Application User Guide", latin_training_font(50), "white")
        draw_ltr_text(draw, (120, 230), "English Edition", latin_training_font(34), "#6ee7b7")
        y = draw_ltr_wrapped_text(draw, 155, 760, "Financial & Final Accounts Integration Program", latin_training_font(35), "#0f172a", 42, 50)
        y = draw_ltr_wrapped_text(draw, 155, y + 28, organization_name, latin_training_font(24), "#047857", 56, 38)
        y = draw_ltr_wrapped_text(draw, 155, max(y + 70, 995), f"Programmer: {owner_name}", latin_training_font(28), "#111827", 56, 40)
        y = draw_ltr_wrapped_text(draw, 155, y + 18, "Programming stack: Python / FastAPI + React", latin_training_font(22), "#334155", 62, 34)
        y = draw_ltr_wrapped_text(draw, 155, y + 18, "Protection level: High - password hashing, login lockout, encrypted backups, and file integrity fingerprinting", latin_training_font(20), "#334155", 78, 32)
        draw_ltr_wrapped_text(draw, 155, y + 24, "Prepared for A4 printing and detailed end-to-end training from login to balance sheet issuance.", latin_training_font(21), "#475569", 78, 34)
        draw_ltr_text(draw, (155, 1445), f"IP Code: {fingerprint}", latin_training_font(20), "#0f766e")
        draw_ltr_text(draw, (155, 1495), f"Encrypted Page Seal: {ip_page_seal(1, fingerprint)}", latin_training_font(18), "#64748b")
        draw_ltr_text(draw, (155, 1540), f"Source Integrity: {source_digest[:48]}", latin_training_font(17), "#64748b")
    return image


def manual_page_footer(draw: ImageDraw.ImageDraw, page_no: int, fingerprint: str, language: Literal["ar", "en"]):
    seal = ip_page_seal(page_no, fingerprint)
    draw.line([80, 1645, 1160, 1645], fill="#d1fae5", width=3)
    if language == "ar":
        draw_rtl_text(draw, (1160, 1685), f"صفحة {page_no} | كود حماية الملكية المشفر: {seal}", training_font(19), "#64748b")
    else:
        draw_ltr_text(draw, (80, 1685), f"Page {page_no} | Encrypted IP protection code: {seal}", latin_training_font(17), "#64748b")


def draw_manual_index(language: Literal["ar", "en"], system_name: str, pages: List[dict], fingerprint: str) -> Image.Image:
    image = Image.new("RGB", (1240, 1754), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 0, 1240, 165], fill="#0f172a")
    if language == "ar":
        draw_rtl_text(draw, (1130, 65), system_name, training_font(31), "white")
        draw_rtl_text(draw, (1130, 128), "فهرس المحتويات التفصيلي", training_font(39), "#6ee7b7")
        y = 230
        for index, page in enumerate(pages, start=3):
            draw_rtl_text(draw, (1090, y), f"{index - 2}. {page['title_ar']}", training_font(25), "#111827")
            draw_rtl_text(draw, (1090, y + 34), "تحتوي على: " + "، ".join(page.get("contents_ar", [])[:4]), training_font(18), "#475569")
            draw_ltr_text(draw, (100, y), str(index), latin_training_font(20), "#047857")
            y += 76
            if y > 1580:
                break
    else:
        draw_ltr_text(draw, (85, 65), system_name, latin_training_font(30), "white")
        draw_ltr_text(draw, (85, 128), "Detailed Table of Contents", latin_training_font(38), "#6ee7b7")
        y = 230
        for index, page in enumerate(pages, start=3):
            draw_ltr_text(draw, (120, y), f"{index - 2}. {page['title_en']}", latin_training_font(24), "#111827")
            draw_ltr_text(draw, (120, y + 34), "Includes: " + ", ".join(page.get("contents_en", [])[:4]), latin_training_font(18), "#475569")
            draw_ltr_text(draw, (1085, y), str(index), latin_training_font(20), "#047857")
            y += 76
            if y > 1580:
                break
    manual_page_footer(draw, 2, fingerprint, language)
    return image


def draw_manual_content_page(language: Literal["ar", "en"], page: dict, page_no: int, system_name: str, fingerprint: str) -> Image.Image:
    image = Image.new("RGB", (1240, 1754), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 0, 1240, 150], fill="#0f172a")
    draw.rectangle([80, 190, 1160, 1585], outline="#ccfbf1", width=3)
    y = 215
    if language == "ar":
        draw_rtl_text(draw, (1130, 58), system_name, training_font(27), "white")
        draw_rtl_text(draw, (1130, 118), page["title_ar"], training_font(36), "#6ee7b7")
        draw_rtl_text(draw, (1110, y), "ما تحتويه هذه الصفحة", training_font(28), "#064e3b")
        y += 52
        for item in page.get("contents_ar", []):
            draw_rtl_text(draw, (1100, y), f"• {item}", training_font(22), "#111827")
            y += 38
        y += 20
        draw_rtl_text(draw, (1110, y), "الشرح وطريقة الاستخدام", training_font(28), "#064e3b")
        y += 52
        for paragraph in page.get("arabic", []):
            for wrapped in wrap_words(paragraph, 74):
                draw_rtl_text(draw, (1100, y), wrapped, training_font(23), "#1f2937")
                y += 39
            y += 12
    else:
        draw_ltr_text(draw, (90, 58), system_name, latin_training_font(27), "white")
        draw_ltr_text(draw, (90, 118), page["title_en"], latin_training_font(33), "#6ee7b7")
        draw_ltr_text(draw, (115, y), "What this page contains", latin_training_font(27), "#064e3b")
        y += 50
        for item in page.get("contents_en", []):
            draw_ltr_text(draw, (130, y), f"• {item}", latin_training_font(21), "#111827")
            y += 36
        y += 20
        draw_ltr_text(draw, (115, y), "Detailed usage instructions", latin_training_font(27), "#064e3b")
        y += 50
        for paragraph in page.get("english", []):
            for wrapped in wrap_words(paragraph, 92):
                draw_ltr_text(draw, (130, y), wrapped, latin_training_font(20), "#1f2937")
                y += 33
            y += 10
    manual_page_footer(draw, page_no, fingerprint, language)
    return image


def enrich_manual_pages(pages: List[dict]) -> List[dict]:
    enriched = []
    for page in pages:
        arabic_extra = [
            "اتبع ترتيب الحقول من أعلى الصفحة إلى أسفلها، ولا تعتمد على الطباعة أو الاعتماد قبل التأكد من صحة التاريخ والجهة والمبلغ والوصف.",
            "أي بيانات يتم إدخالها في هذه الصفحة تظهر لاحقاً في التقارير المرتبطة بها حسب الصلاحيات وحسب الجهة المختارة عند الدخول.",
            "عند وجود زر حفظ أو اعتماد، راجع الرسائل التي تظهر بعد الحفظ للتأكد من نجاح العملية وعدم وجود خطأ في الربط أو البيانات.",
        ]
        english_extra = [
            "Follow the fields from top to bottom and confirm organization, date, amount, and description before saving, printing, or approval.",
            "Data entered on this page flows to related reports according to user permissions and the selected organization.",
            "After saving or approving, read the confirmation or validation message to ensure the transaction is linked correctly.",
        ]
        contents_ar = [page["title_ar"], "الحقول الأساسية", "الأزرار والوظائف", "الأثر على التقارير"]
        contents_en = [page["title_en"], "Main fields", "Buttons and actions", "Reporting impact"]
        enriched.append({**page, "contents_ar": contents_ar, "contents_en": contents_en, "arabic": page.get("arabic", []) + arabic_extra, "english": page.get("english", []) + english_extra})
    return enriched


async def generate_language_manual(current_user: Optional[dict], language: Literal["ar", "en"]) -> Path:
    system_name, organization_name, pages = await training_pages(current_user)
    settings = await get_app_settings_document()
    owner = settings.get("intellectual_property_owner") or "يوسف عبد الغني احمد"
    fingerprint = intellectual_property_fingerprint(settings.get("intellectual_property_owner"), settings.get("system_name") or system_name, settings.get("intellectual_property_national_id"), settings.get("intellectual_property_fingerprint"))
    pages = enrich_manual_pages(pages)
    display_system_name = system_name
    display_organization_name = organization_name
    display_owner = owner
    if language == "en":
        display_system_name = english_manual_label(system_name, "Accounting and Bank Deposit System")
        display_organization_name = english_manual_label(organization_name, "Selected Organization")
        display_owner = english_manual_label(owner, "Youssef Abdelghany Ahmed")
    images = [draw_manual_cover(language, display_system_name, display_organization_name, display_owner, fingerprint, source_integrity_digest()), draw_manual_index(language, display_system_name, pages, fingerprint)]
    images.extend([draw_manual_content_page(language, page, index + 3, display_system_name, fingerprint) for index, page in enumerate(pages)])
    filename = "دليل-استخدام-البرنامج-عربي.pdf" if language == "ar" else "Program-User-Guide-English.pdf"
    path = TRAINING_DIR / filename
    images[0].save(path, "PDF", resolution=150.0, save_all=True, append_images=images[1:])
    return path


@api_router.get("/admin/training/manual-ar.pdf")
async def download_training_manual_ar():
    current_user = {"organization_id": DEFAULT_ORGANIZATION_ID}
    path = await generate_language_manual(current_user, "ar")
    return FileResponse(str(path), filename=path.name, media_type="application/pdf")


@api_router.get("/admin/training/manual-en.pdf")
async def download_training_manual_en():
    current_user = {"organization_id": DEFAULT_ORGANIZATION_ID}
    path = await generate_language_manual(current_user, "en")
    return FileResponse(str(path), filename=path.name, media_type="application/pdf")


async def training_pages(current_user: Optional[dict] = None) -> tuple[str, str, List[dict]]:
    settings = await get_app_settings_document()
    public = await build_app_settings_response(settings)
    system_name = public.system_name
    organization_id = (current_user or {}).get("organization_id") or organization_id_or_default()
    organization = await get_organization_document(organization_id)
    organization_name = organization.get("name") or public.organization_name or "الجهة المستخدمة للبرنامج"
    pages = [
        {"title_ar": "صفحة تسجيل الدخول واختيار الجهة", "title_en": "Login and Organization Selection", "arabic": ["تبدأ الدورة التدريبية من شاشة تسجيل الدخول حيث يختار المستخدم الجهة التي يعمل عليها قبل إدخال اسم المستخدم وكلمة المرور.", "كل جهة لها بياناتها وصلاحياتها ووحداتها، لذلك يجب التأكد من اختيار الجهة الصحيحة قبل الدخول.", "بعد أكثر من ٣ محاولات كلمة مرور خاطئة يتم تعطيل الدخول على الجهاز لمدة ٣ دقائق قبل السماح بالمحاولة مرة أخرى."], "english": ["Start by selecting the correct organization, then enter username and password.", "Each organization has isolated data, modules, and permissions.", "After more than three wrong password attempts, login is locked on the computer for three minutes."]},
        {"title_ar": "تشغيل البرنامج على الشبكة المحلية", "title_en": "Local Network Access", "arabic": ["يتم تثبيت البرنامج على جهاز رئيسي واحد فقط، ثم يتم تشغيله من الاختصار الموجود على هذا الجهاز.", "يعرض ملف التشغيل رابطاً محلياً للجهاز الرئيسي مثل http://localhost:8001 ورابط شبكة مثل http://192.168.1.10:8001.", "على أي جهاز آخر داخل نفس الشبكة المحلية، افتح المتصفح واكتب رابط الشبكة المعروض كما هو بدلاً من localhost.", "لا يلزم تثبيت البرنامج على الأجهزة الأخرى، لأنها تستخدم نفس قاعدة البيانات الموجودة على الجهاز الرئيسي."], "english": ["Install the application on one main computer only, then start it from that computer.", "The launcher shows the local URL and a LAN URL such as http://192.168.1.10:8001.", "On any other computer connected to the same local network, open a browser and use the LAN URL instead of localhost.", "Other computers do not need installation because they use the same database on the main computer."]},
        {"title_ar": "لوحة البرنامج الرئيسية والتنقل", "title_en": "Main Dashboard and Navigation", "arabic": ["بعد الدخول تظهر لوحة البرامج حسب الصلاحيات: البنوك، الودائع، الإيرادات، المصروفات، التسويات، العضوية، الأصول، العهد، الفواتير، التقارير والقوائم المالية.", "الصفحات غير المفعلة للجهة أو غير المصرح بها لا تظهر للمستخدم."], "english": ["The dashboard displays only allowed modules such as banks, deposits, revenues, expenses, reconciliations, memberships, assets, invoices, and reports.", "Unavailable or unauthorized modules are hidden to keep workflows clean."]},
        {"title_ar": "إدارة البنوك والأرصدة الافتتاحية", "title_en": "Banks and Opening Balances", "arabic": ["يتم إضافة البنك باسم واضح ورقم حساب ونوع الحساب والرصيد الافتتاحي.", "تستخدم هذه البيانات لاحقاً في الودائع والتسويات البنكية والتقارير."], "english": ["Create bank records with account details and opening balances.", "These balances support deposit tracking, reconciliations, and reports."]},
        {"title_ar": "إدارة الودائع واحتساب الفوائد", "title_en": "Deposits and Interest Calculation", "arabic": ["من صفحة الودائع يتم إدخال مبلغ الوديعة والبنك وتاريخ البداية والاستحقاق وسعر الفائدة.", "يقوم النظام بحساب الفوائد ومتابعة حالة الوديعة وربطها بالتقارير المالية حسب الجهة."], "english": ["Enter deposit amount, bank, start date, maturity date, and interest rate.", "The system calculates interest and tracks maturity status."]},
        {"title_ar": "الإيرادات والتحصيل", "title_en": "Revenues and Collections", "arabic": ["تسجل الإيرادات بالمبلغ والتاريخ والبنك والبيان ونوع الإيراد.", "ينشئ النظام قيوداً محاسبية تلقائية عند الحاجة، وتظهر الإيرادات في التحليلات والقوائم المالية."], "english": ["Record revenue date, amount, bank, description, and category.", "Accounting entries and financial reports are updated automatically where applicable."]},
        {"title_ar": "المصروفات وأذون الصرف", "title_en": "Expenses and Payment Vouchers", "arabic": ["تسجل المصروفات مع تحديد الجهة والبند والبنك والبيان، ويمكن طباعة إذن صرف يحتوي بيانات الجهة والبريد الإلكتروني إذا تم إدخاله.", "تستخدم هذه البيانات في تحليل المصروفات والقوائم السنوية."], "english": ["Record expenses by organization, category, bank, and description.", "Payment vouchers include organization details and email when configured."]},
        {"title_ar": "تحليل المصروفات", "title_en": "Expense Analysis", "arabic": ["تعرض صفحة تحليل المصروفات إجماليات البنود، التفاصيل الشهرية والسنوية، ونسب كل بند من إجمالي المصروفات.", "يمكن استخدام التصدير والطباعة لمراجعة الاعتمادات والموازنات."], "english": ["Expense analysis shows totals by category, period, and share of total expenses.", "Use exported reports for budget review and approvals."]},
        {"title_ar": "التسوية البنكية", "title_en": "Bank Reconciliation", "arabic": ["يدخل المستخدم رصيد كشف البنك ورصيد الدفتر والشيكات القائمة والشيكات تحت التحصيل.", "يقوم النظام بإظهار فرق التسوية ويساعد على الوصول لرصيد مطابق قابل للطباعة."], "english": ["Enter bank statement balance, book balance, outstanding checks, and deposits in transit.", "The reconciliation calculates differences and prepares a printable statement."]},
        {"title_ar": "شجرة الحسابات والقيود اليومية", "title_en": "Chart of Accounts and Journal Entries", "arabic": ["تستخدم شجرة الحسابات لتنظيم الأصول والخصوم والإيرادات والمصروفات.", "القيود اليومية تربط العمليات المالية بالمحاسبة وتساعد في ميزان المراجعة والقوائم المالية."], "english": ["The chart of accounts organizes assets, liabilities, revenue, and expenses.", "Journal entries connect transactions to trial balance and statements."]},
        {"title_ar": "الأصول الثابتة والإهلاك", "title_en": "Fixed Assets and Depreciation", "arabic": ["يتم تسجيل الأصل بتكلفته وتاريخ الشراء والتصنيف ونسبة الإهلاك.", "يحتسب النظام الإهلاك الدفتري ويحدث صافي القيمة الدفترية للأصل."], "english": ["Register assets with cost, purchase date, category, and depreciation rate.", "The system calculates depreciation and net book value."]},
        {"title_ar": "العهد والسلف", "title_en": "Custody and Advances", "arabic": ["تسجل العهد والسلف باسم الموظف والمبلغ ونوع العملية وحالة التسوية.", "عند التسوية يتم تحديث الحالة وربطها بالأثر المحاسبي."], "english": ["Record custody/advance amount, employee, type, and settlement status.", "Settlement updates status and accounting impact."]},
        {"title_ar": "العضوية والاستيراد", "title_en": "Memberships and Import", "arabic": ["تدار بيانات العضوية من حيث الاسم والرقم القومي والمحافظة واللجنة وتاريخ المعاش.", "يمكن الاستيراد من ملفات ثم مراجعة البيانات قبل اعتمادها داخل النظام."], "english": ["Manage member name, national ID, governorate, committee, and retirement date.", "Import files are reviewed before final save."]},
        {"title_ar": "الفاتورة الإلكترونية", "title_en": "Electronic Invoice", "arabic": ["تجهز الفواتير من بيانات الإيرادات أو الإدخال المباشر مع العميل والبيان والضريبة والإجمالي.", "عند اكتمال إعدادات منظومة الضرائب وSDK التوقيع الرقمي يمكن إرسال الفاتورة للمنظومة وحفظ رقم الاعتماد والرابط."], "english": ["Prepare invoices from revenue data or direct entry with customer, description, tax, and totals.", "When ETA API and signing SDK are configured, invoices can be submitted and tracked."]},
        {"title_ar": "إعدادات منظومة الضرائب المصرية", "title_en": "Egyptian Tax Authority Integration", "arabic": ["تضاف بيانات الممول والرقم الضريبي وكود النشاط والفرع وبيانات API وSDK التوقيع الرقمي.", "لا يتم إرسال أي فاتورة فعلياً قبل اكتمال بيانات الاعتماد والتوقيع."], "english": ["Configure taxpayer information, activity code, branch code, API credentials, and signing SDK command.", "No live submission occurs until required credentials and signature are complete."]},
        {"title_ar": "إدارة المستخدمين والصلاحيات", "title_en": "Users and Permissions", "arabic": ["تتم إضافة المستخدمين وتحديد دورهم وصلاحياتهم والجهة التابعة لهم.", "يمكن تعطيل أو تفعيل الحسابات وتغيير كلمة المرور حسب الصلاحيات الإدارية."], "english": ["Create users, assign roles, organization, and permissions.", "Accounts can be enabled, disabled, or password-reset by authorized managers."]},
        {"title_ar": "إعدادات الجهات والشعارات", "title_en": "Organizations and Branding", "arabic": ["يمكن تعديل اسم البرنامج، أسماء الجهات، البريد الإلكتروني، وشعارات شاشة الدخول.", "عند إخفاء شعار لا يترك النظام مساحة فارغة، وعند تغييره يتم احتواؤه بحجم مناسب."], "english": ["Update program name, organization names, emails, and login branding.", "Hidden logos leave no placeholder; uploaded logos fit the designed frame."]},
        {"title_ar": "النسخ الاحتياطي والاستعادة", "title_en": "Backup and Restore", "arabic": ["ينشئ النظام نسخة احتياطية مشفرة بكلمة مرور تشمل بيانات البرنامج حسب صلاحيات الدور.", "احتفظ بكلمة المرور في مكان آمن لأنها مطلوبة للاستعادة.", "يتم حفظ آخر حقول تم إدخالها محلياً عند انتهاء الجلسة بسبب عدم النشاط، مع استبعاد كلمات المرور والملفات."], "english": ["Create password-protected encrypted backups according to role policy.", "Keep the password safe because it is required for restore.", "When the session times out due to inactivity, the latest entered draft fields are saved locally, excluding passwords and files."]},
        {"title_ar": "إنهاء الجلسة وحماية الحساب", "title_en": "Session Timeout and Account Protection", "arabic": ["لضمان أمان البيانات، يتم تسجيل الخروج تلقائياً بعد دقيقة واحدة من عدم النشاط.", "قبل تسجيل الخروج التلقائي يحفظ النظام آخر البيانات غير الحساسة التي كان المستخدم يكتبها محلياً.", "يمنع النظام كليك يمين داخل الواجهة لتقليل نسخ أو عبث غير مقصود أثناء الاستخدام."], "english": ["For data security, the application logs out automatically after one minute of inactivity.", "Before timeout logout, non-sensitive draft fields are saved locally.", "Right-click is disabled in the interface to reduce accidental copying or tampering."]},
        {"title_ar": "سجل التدقيق والمراجعة الأمنية", "title_en": "Audit Log and Security Review", "arabic": ["يسجل النظام عمليات الإضافة والتعديل والحذف والدخول حسب المستخدم والوقت والمسار.", "يمكن استخدام الفلاتر الشهرية والسنوية لمراجعة النشاط."], "english": ["The audit log records actions, actor, time, route, and status.", "Use filters to review activity by year, month, and hour."]},
        {"title_ar": "ميزان المراجعة", "title_en": "Trial Balance", "arabic": ["يعرض ميزان المراجعة أرصدة الحسابات المدينة والدائنة قبل إعداد القوائم المالية.", "يجب مراجعة أي فروق قبل إصدار الميزانية."], "english": ["Trial balance shows debit and credit balances before financial statements.", "Review differences before issuing the balance sheet."]},
        {"title_ar": "إصدار الميزانية والقوائم المالية", "title_en": "Balance Sheet and Financial Statements", "arabic": ["من صفحة القوائم المالية يتم اختيار السنة ثم استخراج الميزانية وحساب الإيرادات والمصروفات وحساب المقبوضات والمدفوعات.", "يعرض النظام أخطاء الربط المحاسبي إن وجدت، ويجب مراجعتها قبل الطباعة والاعتماد."], "english": ["Select the year to generate balance sheet, revenues/expenses, and receipts/payments statements.", "Review accounting linkage warnings before printing and approval."]},
    ]
    if settings.get("include_tech_stack_in_manual"):
        pages.append({"title_ar": "معلومات تقنية اختيارية", "title_en": "Optional Technical Information", "arabic": ["هذه الصفحة تظهر فقط عند تفعيل خيار إظهار التقنية في كتيب الإرشادات من صفحة أمان البرنامج.", "يعتمد البرنامج على واجهة ويب محلية وخادم محلي وقاعدة بيانات محلية داخل بيئة Windows."], "english": ["This page appears only when the technical stack option is enabled from Program Security.", "The system runs as a local web application with a local server and local database on Windows."]})
    return system_name, organization_name, pages


@api_router.get("/admin/training/manual.pdf")
async def download_training_manual(current_user: dict = Depends(require_admin)):
    system_name, organization_name, pages = await training_pages(current_user)
    images = [draw_training_cover(system_name, organization_name), draw_training_index(system_name, pages)]
    images.extend([draw_training_page(page, index + 3, system_name) for index, page in enumerate(pages)])
    path = TRAINING_DIR / "دليل-استخدام-البرنامج.pdf"
    images[0].save(path, save_all=True, append_images=images[1:])
    return FileResponse(str(path), filename=path.name, media_type="application/pdf")


@api_router.get("/admin/training/screenshots.zip")
async def download_training_screenshots(current_user: dict = Depends(require_admin)):
    system_name, organization_name, pages = await training_pages(current_user)
    zip_path = TRAINING_DIR / "لقطات-صفحات-البرنامج.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        cover = draw_training_cover(system_name, organization_name)
        buffer = BytesIO()
        cover.save(buffer, format="PNG")
        archive.writestr("00-غلاف-الدليل.png", buffer.getvalue())
        for index, page in enumerate(pages, start=1):
            image = draw_training_page(page, index + 2, system_name)
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            archive.writestr(f"{index:02d}-{page['title_ar']}.png", buffer.getvalue())
    return FileResponse(str(zip_path), filename=zip_path.name, media_type="application/zip")


@api_router.get("/admin/training/video-guide.gif")
async def download_training_video(current_user: dict = Depends(require_admin)):
    system_name, organization_name, pages = await training_pages(current_user)
    frames = [draw_training_cover(system_name, organization_name).resize((620, 877))]
    frames.extend([draw_training_page(page, index + 3, system_name).resize((620, 877)) for index, page in enumerate(pages[:10])])
    path = TRAINING_DIR / "فيديو-استرشادي-slideshow.gif"
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=2200, loop=0)
    return FileResponse(str(path), filename=path.name, media_type="image/gif")


@api_router.delete("/admin/security/audit-logs")
async def clear_audit_logs(_: dict = Depends(require_super_admin)):
    result = await db.audit_logs.delete_many({})
    return {"message": "تم مسح محتويات سجل التدقيق", "deleted_count": result.deleted_count}


@api_router.get("/admin/data-flow-validation")
async def get_admin_data_flow_validation(current_user: dict = Depends(require_admin)):
    target_orgs = list(ORGANIZATIONS.keys()) if is_super_admin(current_user) else [current_user.get("organization_id") or DEFAULT_ORGANIZATION_ID]
    organization_results = []
    for organization_id in target_orgs:
        organization_results.append({
            "organization_id": organization_id,
            "organization_name": (await get_organization_document(organization_id))["name"],
            "accounting": await validate_accounting_data_flow(organization_id),
            "membership": await validate_membership_data_flow(organization_id),
        })
    return {
        "generated_at": serialize_datetime(datetime.now(timezone.utc)),
        "organizations": organization_results,
        "is_valid": all(item["accounting"].get("is_valid") and item["membership"].get("is_valid") for item in organization_results),
    }


@api_router.get("/admin/data-flow-rules-manager")
async def get_data_flow_rules_manager(organization_id: Optional[str] = Query(default=None), current_user: dict = Depends(require_super_admin)):
    target_organization_id = organization_id or current_user.get("organization_id") or DEFAULT_ORGANIZATION_ID
    if target_organization_id not in ORGANIZATIONS:
        await get_organization_document(target_organization_id)
    CURRENT_ORGANIZATION_ID.set(target_organization_id)
    accounting_validation = await validate_accounting_data_flow(target_organization_id)
    membership_validation = await validate_membership_data_flow(target_organization_id)
    rules = await list_accounting_rules_for_organization(target_organization_id)
    accounts = await db.chart_accounts.find(with_organization({"is_active": True, "is_postable": True}, target_organization_id), {"_id": 0, "name": 1, "code": 1, "nature": 1}).sort("code", 1).to_list(1000)
    dynamic_accounts = ["البنك", "الإيرادات", "المصروفات", "المصروفات البنكية", "ودائع لأجل", "عوائد ودائع مستحقة", "إيرادات فوائد ودائع", "رصيد افتتاحي", "إيرادات اشتراكات العضوية", "إهلاك الأصول الثابتة", "مجمع إهلاك الأصول الثابتة", "سلف الموظفين", "عهد الموظفين"]
    return {
        "organization_id": target_organization_id,
        "organization_name": (await get_organization_document(target_organization_id))["name"],
        "generated_at": serialize_datetime(datetime.now(timezone.utc)),
        "flow_monitor": await flow_monitor_for_organization(target_organization_id, accounting_validation, membership_validation),
        "rules": [AccountingRuleResponse(**rule).model_dump(mode="json") for rule in rules],
        "available_accounts": [{"name": item, "code": "AUTO", "nature": "auto", "is_dynamic": True} for item in dynamic_accounts] + accounts,
        "validation_tests": validation_tests_from_flow(accounting_validation, membership_validation),
        "accounting_validation": accounting_validation,
        "membership_validation": membership_validation,
    }


@api_router.put("/admin/data-flow-rules-manager/rules/{rule_id}", response_model=AccountingRuleResponse)
async def update_data_flow_rules_manager_rule(rule_id: str, payload: AccountingRuleUpdate, organization_id: Optional[str] = Query(default=None), current_user: dict = Depends(require_super_admin)):
    target_organization_id = organization_id or current_user.get("organization_id") or DEFAULT_ORGANIZATION_ID
    CURRENT_ORGANIZATION_ID.set(target_organization_id)
    rules = await list_accounting_rules_for_organization(target_organization_id)
    existing = next((rule for rule in rules if rule.get("id") == rule_id), None)
    if not existing:
        raise HTTPException(status_code=404, detail="القاعدة غير موجودة")
    payload_data = payload.model_dump()
    payload_data["priority"] = calculate_rule_priority(payload_data)
    now_iso = serialize_datetime(datetime.now(timezone.utc))
    document = {
        **existing,
        **payload_data,
        "id": rule_id,
        "organization_id": target_organization_id,
        "is_system": False,
        "updated_by": current_user.get("id"),
        "updated_by_name": real_name_for_user(current_user),
        "updated_at": now_iso,
        "created_at": existing.get("created_at") or now_iso,
    }
    await db.accounting_rules.update_one(with_organization({"id": rule_id}, target_organization_id), {"$set": document}, upsert=True)
    return AccountingRuleResponse(**document)


@api_router.post("/admin/program-data/purge", response_model=ProgramPurgeResponse)
async def purge_program_user_data(payload: ProgramPurgeRequest, current_user: dict = Depends(require_super_admin)):
    if normalize_member_text(payload.confirmation_phrase) != "تفريغ البيانات نهائيا":
        raise HTTPException(status_code=422, detail="اكتب عبارة التأكيد كما هي: تفريغ البيانات نهائيا")
    target_organization_id = None if payload.scope == "all_organizations" else (current_user.get("organization_id") or DEFAULT_ORGANIZATION_ID)
    collections = list(USER_DATA_PURGE_COLLECTIONS)
    if payload.include_banks:
        collections.extend(["banks", "bank_settings", "deleted_banks", "banking_tariffs"])
    if payload.include_users:
        collections.append("users")
    deleted_counts = {}
    for collection_name in collections:
        query = {} if target_organization_id is None else {"organization_id": target_organization_id}
        if collection_name == "users" and target_organization_id is not None:
            query = {"organization_id": target_organization_id, "role": {"$ne": "super_admin"}}
        if collection_name == "users" and target_organization_id is None:
            query = {"role": {"$ne": "super_admin"}}
        result = await db[collection_name].delete_many(query)
        deleted_counts[collection_name] = int(result.deleted_count)
    if target_organization_id is not None:
        await sync_chart_accounts_for_organization(target_organization_id)
    else:
        for organization_id in ORGANIZATIONS:
            CURRENT_ORGANIZATION_ID.set(organization_id)
            await sync_chart_accounts_for_organization(organization_id)
    return ProgramPurgeResponse(scope=payload.scope, organization_id=target_organization_id, deleted_counts=deleted_counts, reset_counters=["journal_counters"], message="تم تفريغ بيانات المستخدم المطلوبة نهائياً مع الحفاظ على إعدادات تشغيل البرنامج الأساسية")


@api_router.get("/admin/program-security", response_model=ProgramSecurityResponse)
async def get_program_security(_: dict = Depends(require_super_admin)):
    settings = await get_app_settings_document()
    system_name = settings.get("system_name") or DEFAULT_SYSTEM_NAME
    owner = settings.get("intellectual_property_owner") or "غير محدد"
    return ProgramSecurityResponse(
        intellectual_property_owner=owner,
        intellectual_property_national_id=settings.get("intellectual_property_national_id"),
        intellectual_property_fingerprint=intellectual_property_fingerprint(settings.get("intellectual_property_owner"), system_name, settings.get("intellectual_property_national_id"), settings.get("intellectual_property_fingerprint")),
        source_lock_password_set=bool(settings.get("source_lock_password_hash")),
        installed_files_lock_enabled=bool(settings.get("installed_files_lock_enabled", False)),
        installed_files_password_set=bool(settings.get("installed_files_password_hash")),
        session_timeout_minutes=int(settings.get("session_timeout_minutes") or 1),
        source_integrity_digest=source_integrity_digest(),
        encrypted_passwords_summary={
            "user_passwords": "محفوظة كـ bcrypt hash وليست نصاً صريحاً",
            "backup_passwords": "تستخدم لاشتقاق مفتاح تشفير Fernet للنسخ الاحتياطية",
            "eta_api_secrets": "Client Secret و PIN محفوظان مشفرين",
            "source_lock_password": "كلمة سر حماية ملفات البرنامج تحفظ كـ bcrypt hash",
            "installed_files_password": "كلمة سر مجلد التثبيت محفوظة كـ bcrypt hash داخل إعدادات الأمان ولا تُطلب عند تشغيل الاختصار",
        },
    )


@api_router.put("/admin/program-security/source-lock-password", response_model=ProgramSecurityResponse)
async def set_source_lock_password(payload: SourceLockPasswordUpdate, _: dict = Depends(require_super_admin)):
    await db.app_settings.update_one(
        {"id": "global"},
        {"$set": {"source_lock_password_hash": hash_password(payload.new_password), "updated_at": serialize_datetime(datetime.now(timezone.utc))}, "$setOnInsert": {"id": "global", "created_at": serialize_datetime(datetime.now(timezone.utc))}},
        upsert=True,
    )
    return await get_program_security(_)


@api_router.put("/admin/program-security/installed-files-password", response_model=ProgramSecurityResponse)
async def set_installed_files_password(payload: InstalledFilesPasswordUpdate, _: dict = Depends(require_super_admin)):
    now_iso = serialize_datetime(datetime.now(timezone.utc))
    await db.app_settings.update_one(
        {"id": "global"},
        {"$set": {"installed_files_password_hash": hash_password(payload.new_password), "updated_at": now_iso}, "$setOnInsert": {"id": "global", "created_at": now_iso}},
        upsert=True,
    )
    return await get_program_security(_)


async def ensure_backup_allowed(current_user: dict):
    settings = await get_app_settings_document()
    if not settings.get("backup_enabled", True):
        raise HTTPException(status_code=403, detail="خدمة النسخ الاحتياطي معطلة حالياً")
    allowed = settings.get("backup_allowed_roles") or {"super_admin": True, "admin": True, "user": False}
    if not allowed.get(current_user.get("role")):
        raise HTTPException(status_code=403, detail="ليست لديك صلاحية استخدام النسخ الاحتياطي")


@api_router.get("/admin/security/backups", response_model=List[BackupRecord])
async def list_backups(current_user: dict = Depends(require_admin)):
    await ensure_backup_allowed(current_user)
    documents = await db.backup_records.find(with_organization({}), {"_id": 0}).sort("created_at", -1).to_list(500)
    return [BackupRecord(**hydrate_einvoice_document(document)) for document in documents]


@api_router.post("/admin/security/backups", response_model=BackupRecord)
async def create_backup(payload: BackupCreate, current_user: dict = Depends(require_admin)):
    await ensure_backup_allowed(current_user)
    export_data = {}
    for collection_name in BACKUP_COLLECTIONS:
        if collection_name == "app_settings" or is_super_admin(current_user):
            export_data[collection_name] = await db[collection_name].find({}, {"_id": 0}).to_list(100000)
        else:
            export_data[collection_name] = await db[collection_name].find(with_organization({}, current_user.get("organization_id")), {"_id": 0}).to_list(100000)
    raw = json.dumps(export_data, ensure_ascii=False, default=str).encode()
    salt = secrets.token_bytes(16)
    encrypted = fernet_from_password(payload.password, salt).encrypt(raw)
    backup_id = str(uuid.uuid4())
    file_name = f"secure-backup-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.enc"
    path = BACKUP_DIR / file_name
    path.write_bytes(base64.b64encode(salt) + b"\n" + encrypted)
    now = datetime.now(timezone.utc)
    record = {"id": backup_id, "organization_id": current_user.get("organization_id") or DEFAULT_ORGANIZATION_ID, "file_name": file_name, "file_size": path.stat().st_size, "encrypted": True, "created_by": current_user["id"], "created_by_name": real_name_for_user(current_user), "created_at": serialize_datetime(now)}
    await db.backup_records.insert_one(record.copy())
    return BackupRecord(**hydrate_einvoice_document(record))


@api_router.get("/admin/security/backups/{backup_id}/download")
async def download_backup(backup_id: str, current_user: dict = Depends(require_admin)):
    await ensure_backup_allowed(current_user)
    record = await db.backup_records.find_one(with_organization({"id": backup_id}), {"_id": 0})
    if not record:
        raise HTTPException(status_code=404, detail="النسخة الاحتياطية غير موجودة")
    path = BACKUP_DIR / record["file_name"]
    if not path.exists():
        raise HTTPException(status_code=404, detail="ملف النسخة غير موجود")
    return FileResponse(str(path), filename=record["file_name"], media_type="application/octet-stream")


@api_router.post("/admin/security/backups/restore")
async def restore_backup(password: str = Form(...), backup_file: UploadFile = File(...), admin_user: dict = Depends(require_admin)):
    await ensure_backup_allowed(admin_user)
    content = await backup_file.read()
    try:
        salt_line, encrypted = content.split(b"\n", 1)
        salt = base64.b64decode(salt_line)
        raw = fernet_from_password(password, salt).decrypt(encrypted)
        data = json.loads(raw.decode())
    except (ValueError, InvalidToken, json.JSONDecodeError):
        raise HTTPException(status_code=400, detail="كلمة المرور أو ملف النسخة الاحتياطية غير صحيح")
    for collection_name, documents in data.items():
        if collection_name not in BACKUP_COLLECTIONS:
            continue
        if collection_name == "app_settings":
            continue
        await db[collection_name].delete_many(with_organization({}, admin_user.get("organization_id")))
        scoped_documents = [attach_organization(document, admin_user.get("organization_id")) for document in documents]
        if scoped_documents:
            await db[collection_name].insert_many(scoped_documents)
    return {"message": "تمت استعادة النسخة الاحتياطية وتسجيل العملية في سجل التدقيق", "collections": list(data.keys())}

# Include the router in the main app
# Attach notifications routes BEFORE include_router so they are part of api_router.
attach_notifications_router(api_router, db, get_current_user)
app.include_router(api_router)


FRONTEND_BUILD_DIR = ROOT_DIR.parent / "frontend" / "build"
if FRONTEND_BUILD_DIR.exists() and (FRONTEND_BUILD_DIR / "static").exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_BUILD_DIR / "static"), name="static")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_react_app(full_path: str):
        requested_file = FRONTEND_BUILD_DIR / full_path
        if full_path and requested_file.exists() and requested_file.is_file():
            return FileResponse(requested_file)
        return FileResponse(FRONTEND_BUILD_DIR / "index.html")


@app.middleware("http")
async def no_cache_frontend_assets_middleware(request: Request, call_next):
    response = await call_next(request)
    if not request.url.path.startswith("/api"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

BACKUP_DIR = ROOT_DIR.parent / "secure_backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def sanitize_audit_body(value):
    if not isinstance(value, dict):
        return None
    hidden_keys = {"password", "current_password", "new_password", "otp_code", "token", "secret"}
    clean = {}
    for key, item in value.items():
        clean[key] = "***" if key.lower() in hidden_keys else item
    return clean


def arabic_audit_description(method: str, path: str, status_code: int, body: Optional[dict], actor_name: Optional[str]) -> str:
    method_labels = {"GET": "استعرض", "POST": "أضاف أو نفذ", "PUT": "عدّل", "PATCH": "حدّث", "DELETE": "حذف"}
    area_labels = [
        ("/api/admin/users", "إدارة المستخدمين"),
        ("/api/admin/profile", "بيانات الأدمن"),
        ("/api/admin/change-password", "كلمة مرور الأدمن"),
        ("/api/admin/2fa", "المصادقة الثنائية الملغاة"),
        ("/api/admin/security/periods", "إقفال وفتح الفترات"),
        ("/api/admin/security/report-approvals", "اعتماد التقارير"),
        ("/api/admin/security/backups", "النسخ الاحتياطي"),
        ("/api/admin/organization/modules", "إعدادات الخواص"),
        ("/api/admin/app-settings", "الإعدادات العامة"),
        ("/api/admin/banks", "إدارة البنوك"),
        ("/api/memberships", "العضوية"),
        ("/api/fixed-assets", "الأصول الثابتة"),
        ("/api/custody-advances", "العهد والسلف"),
        ("/api/financial-statements", "القوائم المالية"),
        ("/api/banking-expenses", "المصروفات البنكية"),
        ("/api/electronic-invoice", "الفاتورة الإلكترونية"),
        ("/api/electronic-invoices", "الفاتورة الإلكترونية"),
        ("/api/revenues", "الإيرادات"),
        ("/api/expenses", "المصروفات"),
        ("/api/banks", "البنوك والودائع والتقارير"),
        ("/api/auth/login", "تسجيل الدخول"),
        ("/api/auth/me", "بيانات الجلسة"),
    ]
    area = next((label for prefix, label in area_labels if path.startswith(prefix)), "النظام")
    action = method_labels.get(method, "نفذ إجراء")
    result = "بنجاح" if status_code < 400 else "وفشل الإجراء"
    actor = actor_name or "مستخدم غير معروف"
    details = []
    if isinstance(body, dict):
        for key in ["username", "full_name", "system_name", "organization_name", "bank_id", "governorate", "union_committee", "membership_number", "category_code", "asset_name", "year", "month", "report_name", "status", "action"]:
            value = body.get(key)
            if value not in (None, ""):
                details.append(f"{key}: {value}")
        if "modules" in body:
            details.append("تم تعديل إعدادات الخواص")
    detail_text = f"، تفاصيل: {'، '.join(details)}" if details else ""
    return f"قام {actor} بـ{action} داخل {area} على المسار {path}، وكانت النتيجة {result} بكود {status_code}{detail_text}."


AUDIT_SNAPSHOT_ROUTES = {
    "journal-entries": "journal_entries",
    "expenses": "expenses",
    "revenues": "revenues",
    "memberships": "memberships",
    "chart-accounts": "chart_accounts",
    "rules-engine": "accounting_rules",
}


def audit_snapshot_target(path: str) -> tuple[Optional[str], Optional[str]]:
    parts = [part for part in path.split("/") if part]
    if len(parts) < 3 or parts[0] != "api":
        return None, None
    if parts[1] == "rules-engine" and len(parts) >= 4 and parts[2] == "rules":
        return "accounting_rules", parts[3]
    if parts[1] == "admin" and len(parts) >= 5 and parts[2] == "data-flow-rules-manager" and parts[3] == "rules":
        return "accounting_rules", parts[4]
    collection = AUDIT_SNAPSHOT_ROUTES.get(parts[1])
    return collection, parts[2] if collection and len(parts) >= 3 else None


async def audit_document_snapshot(request: Request) -> Optional[dict]:
    collection_name, document_id = audit_snapshot_target(request.url.path)
    if not collection_name or not document_id:
        return None
    collection_names = await db.list_collection_names()
    if collection_name not in collection_names:
        return None
    query_organization_id = request.query_params.get("organization_id")
    organization_id = query_organization_id or DEFAULT_ORGANIZATION_ID
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            payload = jwt.decode(auth_header[7:], JWT_SECRET, algorithms=[JWT_ALGORITHM])
            organization_id = query_organization_id or payload.get("organization_id") or DEFAULT_ORGANIZATION_ID
        except Exception:
            organization_id = DEFAULT_ORGANIZATION_ID
    document = await db[collection_name].find_one(with_organization({"id": document_id}, organization_id), {"_id": 0})
    if not document and collection_name == "accounting_rules":
        document = next((rule for rule in default_accounting_rules(organization_id) if rule.get("id") == document_id), None)
    return sanitize_audit_body(document) if document else None


async def audit_event(request: Request, status_code: int, body: Optional[dict] = None, before_document: Optional[dict] = None, after_document: Optional[dict] = None):
    if request.url.path.startswith("/api/admin/security/audit-logs"):
        return
    user_id = None
    username = None
    actor_full_name = None
    organization_id = DEFAULT_ORGANIZATION_ID
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            payload = jwt.decode(auth_header[7:], JWT_SECRET, algorithms=[JWT_ALGORITHM])
            user_id = payload.get("sub")
            organization_id = payload.get("organization_id") or DEFAULT_ORGANIZATION_ID
            user = await db.users.find_one({"id": user_id}, {"_id": 0, "username": 1, "full_name": 1, "organization_id": 1})
            username = user.get("username") if user else None
            actor_full_name = real_name_for_user(user) if user else None
            organization_id = user.get("organization_id", organization_id) if user else organization_id
        except Exception:
            pass
    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "username": username,
        "actor_full_name": actor_full_name,
        "user_id": user_id,
        "organization_id": organization_id,
        "method": request.method,
        "path": request.url.path,
        "action": f"{request.method} {request.url.path}",
        "arabic_description": arabic_audit_description(request.method, request.url.path, status_code, sanitize_audit_body(body), actor_full_name),
        "status_code": status_code,
        "request_body": sanitize_audit_body(body),
        "before_document": before_document,
        "after_document": after_document,
        "ip_address": request.client.host if request.client else None,
        "created_at": serialize_datetime(datetime.now(timezone.utc)),
    })


@app.middleware("http")
async def audit_log_middleware(request: Request, call_next):
    raw_body = await request.body()
    parsed_body = None
    if raw_body and request.method not in {"GET", "HEAD", "OPTIONS"} and request.url.path.startswith("/api"):
        try:
            parsed_body = json.loads(raw_body.decode())
        except Exception:
            parsed_body = None

    async def receive():
        return {"type": "http.request", "body": raw_body, "more_body": False}

    request = Request(request.scope, receive)
    before_document = None
    if request.url.path.startswith("/api") and request.method in {"PUT", "PATCH", "DELETE"}:
        before_document = await audit_document_snapshot(request)
    response = await call_next(request)
    after_document = None
    if request.url.path.startswith("/api") and request.method in {"PUT", "PATCH"} and response.status_code < 400:
        after_document = await audit_document_snapshot(request)
    if request.url.path.startswith("/api") and request.method not in {"GET", "HEAD", "OPTIONS"}:
        await audit_event(request, response.status_code, parsed_body, before_document, after_document)
    return response


@app.middleware("http")
async def explicit_api_preflight_middleware(request: Request, call_next):
    if request.method == "OPTIONS" and request.url.path.startswith("/api"):
        origin = request.headers.get("origin")
        allowed_origin = origin or (CORS_ORIGINS[0] if CORS_ORIGINS else "")
        return Response(
            status_code=204,
            headers={
                "Access-Control-Allow-Origin": allowed_origin,
                "Access-Control-Allow-Credentials": "true",
                "Access-Control-Allow-Methods": "GET,POST,PUT,PATCH,DELETE,OPTIONS",
                "Access-Control-Allow-Headers": request.headers.get("access-control-request-headers", "authorization,content-type"),
                "Vary": "Origin",
            },
        )
    response = await call_next(request)
    origin = request.headers.get("origin")
    if request.url.path.startswith("/api") and origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Vary"] = "Origin"
    return response

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    try:
        if deposit_notification_scheduler is not None and deposit_notification_scheduler.running:
            deposit_notification_scheduler.shutdown(wait=False)
    except Exception:
        pass
    client.close()