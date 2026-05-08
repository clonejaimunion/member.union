import os
import uuid
from datetime import date

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient


# Modules/features under test: revenue direct bank methods, deposit-link expense posting, period-scoped reports, journal/ledger source filtering, data-flow validity
FRONTEND_ENV = dotenv_values("/app/frontend/.env")
BACKEND_ENV = dotenv_values("/app/backend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or FRONTEND_ENV.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
MONGO_URL = (BACKEND_ENV.get("MONGO_URL") or "").strip('"')
DB_NAME = (BACKEND_ENV.get("DB_NAME") or "").strip('"')

ITER_PREFIX = f"TEST-ITER69-{uuid.uuid4().hex[:8]}"
ITER_NUM_PREFIX = f"69{uuid.uuid4().int % 10_000_000:07d}"


def _headers(token: str | None = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


@pytest.fixture(scope="session")
def base_url():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL is not configured")
    return BASE_URL


@pytest.fixture(scope="session")
def admin_token(base_url):
    response = requests.post(
        f"{base_url}/api/auth/login",
        json={"username": "admin", "password": "Admin@123", "organization_id": "social-solidarity"},
        headers=_headers(),
        timeout=60,
    )
    if response.status_code != 200:
        pytest.skip(f"admin login failed: {response.status_code} {response.text}")
    token = response.json().get("token")
    if not token:
        pytest.skip("admin token missing")
    return token


@pytest.fixture(scope="session", autouse=True)
def cleanup_iter69_data():
    yield
    if not MONGO_URL or not DB_NAME:
        return
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    db.revenues.delete_many({"receipt_number": {"$regex": f"^{ITER_NUM_PREFIX}"}})
    db.expenses.delete_many({"expense_number": {"$regex": f"^{ITER_NUM_PREFIX}"}})
    db.journal_entries.delete_many({"$or": [{"reference": {"$regex": f"^{ITER_PREFIX}"}}, {"reference": {"$regex": f"^{ITER_NUM_PREFIX}"}}]})
    client.close()


@pytest.fixture(scope="session")
def seeded_scope_docs(base_url, admin_token):
    today = date.today().isoformat()
    payloads = {
        "current_interest": {
            "receipt_number": f"{ITER_NUM_PREFIX}01",
            "amount": 1250.5,
            "collection_method": "current_account_interest",
            "supplier_name": None,
            "check_number": None,
            "check_clearing_type": None,
            "payment_order_number": None,
            "bank_id": "industrial-development",
            "dated": today,
            "value": f"{ITER_PREFIX} فوائد حساب جاري",
            "issued_at": today,
            "responsible_employee": "يوسف عبدالغني",
            "bank_collection_status": "under_collection",
        },
        "deposit_maturity": {
            "receipt_number": f"{ITER_NUM_PREFIX}02",
            "amount": 980.25,
            "collection_method": "deposit_maturity",
            "supplier_name": None,
            "check_number": None,
            "check_clearing_type": None,
            "payment_order_number": None,
            "bank_id": "industrial-development",
            "dated": today,
            "value": f"{ITER_PREFIX} استحقاق وديعة",
            "issued_at": today,
            "responsible_employee": "دعاء علي",
            "bank_collection_status": "under_collection",
        },
        "deposit_link_expense": {
            "expense_number": f"{ITER_NUM_PREFIX}03",
            "organization_scope": "social_solidarity_project",
            "expense_category": "deposit_link",
            "payment_method": "cash",
            "payee_name": f"{ITER_PREFIX} مستفيد",
            "check_number": None,
            "check_clearing_type": None,
            "transfer_number": None,
            "transfer_to": None,
            "membership_number": None,
            "committee": None,
            "governorate": None,
            "bank_id": "industrial-development",
            "gross_amount": 1500.0,
            "gross_statement": f"{ITER_PREFIX} ربط وديعة",
            "deductions": [{"amount": 120.0, "statement": "يجب تجاهل هذا الاستقطاع"}],
            "issued_at": today,
            "responsible_employee": "يوسف عبدالغني",
            "bank_payment_status": "not_presented",
        },
    }

    created_current_interest = requests.post(
        f"{base_url}/api/revenues", json=payloads["current_interest"], headers=_headers(admin_token), timeout=60
    )
    assert created_current_interest.status_code == 200, created_current_interest.text

    created_deposit_maturity = requests.post(
        f"{base_url}/api/revenues", json=payloads["deposit_maturity"], headers=_headers(admin_token), timeout=60
    )
    assert created_deposit_maturity.status_code == 200, created_deposit_maturity.text

    created_deposit_link = requests.post(
        f"{base_url}/api/expenses", json=payloads["deposit_link_expense"], headers=_headers(admin_token), timeout=60
    )
    assert created_deposit_link.status_code == 200, created_deposit_link.text

    return {
        "today": today,
        "current_interest": created_current_interest.json(),
        "deposit_maturity": created_deposit_maturity.json(),
        "deposit_link_expense": created_deposit_link.json(),
        "receipt_numbers": {
            payloads["current_interest"]["receipt_number"],
            payloads["deposit_maturity"]["receipt_number"],
        },
        "expense_number": payloads["deposit_link_expense"]["expense_number"],
    }


def _journal_entries_in_period(base_url: str, token: str, period_day: str):
    response = requests.get(
        f"{base_url}/api/journal-entries",
        params={"from_date": period_day, "to_date": period_day},
        headers=_headers(token),
        timeout=60,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _find_bank_line(lines: list[dict], *, side: str):
    for line in lines:
        has_bank_identity = bool(line.get("bank_id")) or str(line.get("account_code") or "").startswith("11") or ("بنك" in str(line.get("account_name") or "")) or line.get("account_name") == "البنك"
        if not has_bank_identity:
            continue
        amount = float(line.get(side) or 0)
        if amount > 0:
            return line
    return None


def test_revenue_current_account_interest_forces_collected_and_posts_bank_debit(base_url, admin_token, seeded_scope_docs):
    revenue = seeded_scope_docs["current_interest"]
    assert revenue["collection_method"] == "current_account_interest"
    assert revenue["bank_collection_status"] == "collected"

    entries = _journal_entries_in_period(base_url, admin_token, seeded_scope_docs["today"])
    target = next((entry for entry in entries if entry.get("reference") == revenue["receipt_number"] and entry.get("source_type") == "revenue"), None)
    assert target is not None

    bank_line = _find_bank_line(target.get("lines", []), side="debit")
    interest_line = next((line for line in target.get("lines", []) if line.get("account_name") == "إيرادات فوائد الحساب الجاري"), None)
    assert bank_line is not None
    assert interest_line is not None
    assert round(float(bank_line.get("debit") or 0), 2) == round(float(revenue["amount"]), 2)
    assert round(float(interest_line.get("credit") or 0), 2) == round(float(revenue["amount"]), 2)


def test_revenue_deposit_maturity_forces_collected_and_posts_deposit_interest_credit(base_url, admin_token, seeded_scope_docs):
    revenue = seeded_scope_docs["deposit_maturity"]
    assert revenue["collection_method"] == "deposit_maturity"
    assert revenue["bank_collection_status"] == "collected"

    entries = _journal_entries_in_period(base_url, admin_token, seeded_scope_docs["today"])
    target = next((entry for entry in entries if entry.get("reference") == revenue["receipt_number"] and entry.get("source_type") == "revenue"), None)
    assert target is not None

    bank_line = _find_bank_line(target.get("lines", []), side="debit")
    interest_line = next((line for line in target.get("lines", []) if line.get("account_name") == "إيرادات فوائد ودائع"), None)
    assert bank_line is not None
    assert interest_line is not None
    assert round(float(bank_line.get("debit") or 0), 2) == round(float(revenue["amount"]), 2)
    assert round(float(interest_line.get("credit") or 0), 2) == round(float(revenue["amount"]), 2)


def test_expense_deposit_link_forces_paid_zeros_deductions_and_posts_term_deposit_debit(base_url, admin_token, seeded_scope_docs):
    expense = seeded_scope_docs["deposit_link_expense"]
    assert expense["expense_category"] == "deposit_link"
    assert expense["bank_payment_status"] == "paid"
    assert round(float(expense.get("total_deductions") or 0), 2) == 0.0
    assert round(float(expense.get("net_amount") or 0), 2) == round(float(expense.get("gross_amount") or 0), 2)

    entries = _journal_entries_in_period(base_url, admin_token, seeded_scope_docs["today"])
    target = next((entry for entry in entries if entry.get("reference") == expense["expense_number"] and entry.get("source_type") == "expense"), None)
    assert target is not None

    deposit_line = next((line for line in target.get("lines", []) if line.get("account_name") == "ودائع لأجل"), None)
    bank_line = _find_bank_line(target.get("lines", []), side="credit")
    assert deposit_line is not None
    assert bank_line is not None
    assert round(float(deposit_line.get("debit") or 0), 2) == round(float(expense.get("net_amount") or 0), 2)
    assert round(float(bank_line.get("credit") or 0), 2) == round(float(expense.get("net_amount") or 0), 2)


def test_financial_statements_period_includes_interest_revenues_and_excludes_deposit_link_from_operating_expenses(base_url, admin_token, seeded_scope_docs):
    period_day = seeded_scope_docs["today"]
    response = requests.get(
        f"{base_url}/api/financial-statements",
        params={"from_date": period_day, "to_date": period_day},
        headers=_headers(admin_token),
        timeout=90,
    )
    assert response.status_code == 200, response.text
    report = response.json()

    revenue_names = {line.get("name") for line in report.get("revenues_expenses", {}).get("revenues", {}).get("lines", [])}
    expense_names = {line.get("name") for line in report.get("revenues_expenses", {}).get("expenses", {}).get("lines", [])}

    assert "إيرادات فوائد الحساب الجاري" in revenue_names
    assert "إيرادات فوائد ودائع" in revenue_names
    assert "ودائع لأجل" not in expense_names


def test_journal_default_filter_excludes_deposit_interest_and_period_rows_are_in_range(base_url, admin_token, seeded_scope_docs):
    entries = _journal_entries_in_period(base_url, admin_token, seeded_scope_docs["today"])
    assert all(entry.get("source_type") != "deposit_interest" for entry in entries)

    target_refs = set(seeded_scope_docs["receipt_numbers"]) | {seeded_scope_docs["expense_number"]}
    target_entries = [entry for entry in entries if entry.get("reference") in target_refs]
    assert len(target_entries) >= 3
    assert all(entry.get("entry_date") == seeded_scope_docs["today"] for entry in target_entries)


def test_ledger_all_period_scope_returns_target_rows_within_period(base_url, admin_token, seeded_scope_docs):
    period_day = seeded_scope_docs["today"]
    response = requests.get(
        f"{base_url}/api/ledger",
        params={"account_id": "all", "from_date": period_day, "to_date": period_day},
        headers=_headers(admin_token),
        timeout=90,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("account_scope") == "all"

    target_refs = set(seeded_scope_docs["receipt_numbers"]) | {seeded_scope_docs["expense_number"]}
    target_rows = [row for row in (body.get("rows") or []) if row.get("reference") in target_refs]
    assert len(target_rows) >= 6
    assert all(period_day <= row.get("entry_date", "") <= period_day for row in target_rows)


def test_data_flow_validation_stays_valid_true(base_url, admin_token):
    response = requests.get(f"{base_url}/api/admin/data-flow-validation", headers=_headers(admin_token), timeout=90)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("is_valid") is True
    assert isinstance(body.get("organizations"), list)
