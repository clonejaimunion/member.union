import os
import uuid
from datetime import datetime, timezone

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient


FRONTEND_ENV = dotenv_values("/app/frontend/.env")
BACKEND_ENV = dotenv_values("/app/backend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or FRONTEND_ENV.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
MONGO_URL = (BACKEND_ENV.get("MONGO_URL") or "").strip('"')
DB_NAME = (BACKEND_ENV.get("DB_NAME") or "").strip('"')
ORG_ID = "social-solidarity"
BANK_ID = "industrial-development"
ITER_PREFIX = f"TEST-ITER72-{uuid.uuid4().hex[:8]}"
ITER_NUM_PREFIX = f"72{uuid.uuid4().int % 10_000_000:07d}"


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
        json={"username": "admin", "password": "Admin@123", "organization_id": ORG_ID},
        headers=_headers(),
        timeout=60,
    )
    if response.status_code != 200:
        pytest.skip(f"admin login failed: {response.status_code} {response.text}")
    return response.json()["token"]


@pytest.fixture(scope="session", autouse=True)
def cleanup_iter72_data():
    yield
    if not MONGO_URL or not DB_NAME:
        return
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    db.revenues.delete_many({"receipt_number": {"$regex": f"^{ITER_NUM_PREFIX}"}})
    db.expenses.delete_many({"expense_number": {"$regex": f"^{ITER_NUM_PREFIX}"}})
    db.deposits.delete_many({"deposit_number": {"$regex": f"^{ITER_PREFIX}"}})
    db.banking_manual_charges.delete_many({"id": f"{BANK_ID}-2199-4", "organization_id": ORG_ID})
    db.journal_entries.delete_many({"$or": [{"reference": {"$regex": f"^{ITER_PREFIX}"}}, {"reference": {"$regex": f"^{ITER_NUM_PREFIX}"}}, {"source_id": f"{BANK_ID}-2199-4"}]})
    client.close()


def _create_revenue(base_url: str, token: str, receipt_suffix: str, amount: float, method: str, status: str = "collected"):
    payload = {
        "receipt_number": f"{ITER_NUM_PREFIX}{receipt_suffix}",
        "amount": amount,
        "collection_method": method,
        "supplier_name": f"{ITER_PREFIX} مورد" if method == "cash" else None,
        "check_number": f"{ITER_NUM_PREFIX}{receipt_suffix}9" if method == "check" else None,
        "check_clearing_type": "internal" if method == "check" else None,
        "payment_order_number": f"{ITER_NUM_PREFIX}{receipt_suffix}8" if method == "payment_order" else None,
        "bank_id": BANK_ID,
        "dated": "2199-04-10",
        "value": f"{ITER_PREFIX} {method}",
        "issued_at": "2199-04-10",
        "responsible_employee": "يوسف عبدالغني",
        "bank_collection_status": status,
    }
    response = requests.post(f"{base_url}/api/revenues", json=payload, headers=_headers(token), timeout=60)
    assert response.status_code == 200, response.text
    return response.json()


def _create_expense(base_url: str, token: str, suffix: str, amount: float, category: str, status: str = "paid", method: str = "cash"):
    payload = {
        "expense_number": f"{ITER_NUM_PREFIX}{suffix}",
        "organization_scope": "social_solidarity_project",
        "expense_category": category,
        "payment_method": method,
        "payee_name": f"{ITER_PREFIX} مستفيد" if method in {"cash", "check"} else None,
        "check_number": f"{ITER_NUM_PREFIX}{suffix}7" if method == "check" else None,
        "check_clearing_type": "internal" if method == "check" else None,
        "transfer_number": None,
        "transfer_to": None,
        "membership_number": f"{ITER_NUM_PREFIX}{suffix}" if category == "death_benefits" else None,
        "committee": "لجنة اختبار" if category == "death_benefits" else None,
        "governorate": "القاهرة" if category == "death_benefits" else None,
        "bank_id": BANK_ID,
        "gross_amount": amount,
        "gross_statement": f"{ITER_PREFIX} {category}",
        "deductions": [],
        "issued_at": "2199-04-12",
        "responsible_employee": "يوسف عبدالغني",
        "bank_payment_status": status,
    }
    response = requests.post(f"{base_url}/api/expenses", json=payload, headers=_headers(token), timeout=60)
    assert response.status_code == 200, response.text
    return response.json()


def _insert_monthly_interest_deposit():
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    now = datetime.now(timezone.utc).isoformat()
    db.deposits.insert_one({
        "id": str(uuid.uuid4()),
        "organization_id": ORG_ID,
        "bank_id": BANK_ID,
        "account_number": f"ACC-{ITER_PREFIX}",
        "deposit_number": f"{ITER_PREFIX}-AUTO-INTEREST",
        "amount": 36500.0,
        "creation_datetime": "2199-04-01T00:00:00+00:00",
        "accounting_start_datetime": "2199-04-01T00:00:00+00:00",
        "maturity_datetime": "2199-05-01T00:00:00+00:00",
        "monthly_interest_rate": 10.0,
        "is_opening_balance_deposit": False,
        "created_at": now,
        "updated_at": now,
    })
    client.close()


def test_bank_reconciliation_uses_month_opening_plus_receipts_minus_payments(base_url, admin_token):
    _create_revenue(base_url, admin_token, "01", 100.0, "cash")
    _create_revenue(base_url, admin_token, "02", 200.0, "check")
    _create_revenue(base_url, admin_token, "03", 300.0, "payment_order")
    _create_revenue(base_url, admin_token, "04", 40.0, "current_account_interest")
    _create_revenue(base_url, admin_token, "05", 60.0, "deposit_maturity")
    _create_revenue(base_url, admin_token, "06", 999.0, "check", status="under_collection")
    _create_expense(base_url, admin_token, "07", 70.0, "general_expenses")
    _create_expense(base_url, admin_token, "08", 80.0, "death_benefits")
    _create_expense(base_url, admin_token, "09", 90.0, "deposit_link")
    _create_expense(base_url, admin_token, "10", 777.0, "general_expenses", status="not_presented", method="check")
    _insert_monthly_interest_deposit()

    manual_payload = {
        "bank_id": BANK_ID,
        "year": 2199,
        "month": 4,
        "items": [{"statement": f"{ITER_PREFIX} مصروف بنكي", "count": 1, "amount": 25.0}],
    }
    manual_response = requests.put(f"{base_url}/api/banking-expenses/manual", json=manual_payload, headers=_headers(admin_token), timeout=60)
    assert manual_response.status_code == 200, manual_response.text

    response = requests.get(
        f"{base_url}/api/banks/{BANK_ID}/reconciliation-balance",
        params={"year": 2199, "month": 4, "period_label": "أبريل 2199"},
        headers=_headers(admin_token),
        timeout=90,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    opening = round(float(data.get("opening_balance") or 0), 2)
    assert round(float(data.get("monthly_revenues") or 0), 2) == 700.0
    assert round(float(data.get("monthly_deposit_interest") or 0), 2) == 300.0
    assert round(float(data.get("total_receipts") or 0), 2) == 1077.0
    assert round(float(data.get("monthly_expenses") or 0), 2) == 1017.0
    assert round(float(data.get("bank_expenses") or 0), 2) == 25.0
    assert round(float(data.get("total_payments") or 0), 2) == 2041.0
    assert round(float(data.get("checks_under_collection") or 0), 2) == 999.0
    assert round(float(data.get("checks_not_presented") or 0), 2) == 777.0
    expected = round(opening + 300.0 + 777.0 - 25.0 - 1017.0 - 999.0, 2)
    assert round(float(data.get("book_balance") or 0), 2) == expected
    assert round(float(data.get("reconciliation_balance") or 0), 2) == expected