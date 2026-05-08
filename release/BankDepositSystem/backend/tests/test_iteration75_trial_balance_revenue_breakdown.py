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
ITER_PREFIX = f"TEST-ITER75-{uuid.uuid4().hex[:8]}"
ITER_NUM_PREFIX = f"75{uuid.uuid4().int % 10_000_000:07d}"


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
def cleanup_iter75_data():
    yield
    if not MONGO_URL or not DB_NAME:
        return
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    db.revenues.delete_many({"receipt_number": {"$regex": f"^{ITER_NUM_PREFIX}"}})
    db.deposits.delete_many({"deposit_number": {"$regex": f"^{ITER_PREFIX}"}})
    db.journal_entries.delete_many({"reference": {"$regex": f"^{ITER_NUM_PREFIX}"}})
    client.close()


def _create_revenue(base_url: str, token: str, suffix: str, amount: float, method: str, status: str = "collected"):
    payload = {
        "receipt_number": f"{ITER_NUM_PREFIX}{suffix}",
        "amount": amount,
        "collection_method": method,
        "supplier_name": None,
        "check_number": f"{ITER_NUM_PREFIX}{suffix}9" if method == "check" else None,
        "check_clearing_type": "internal" if method == "check" else None,
        "payment_order_number": f"{ITER_NUM_PREFIX}{suffix}8" if method == "payment_order" else None,
        "bank_id": BANK_ID,
        "dated": "2199-06-10",
        "value": f"{ITER_PREFIX} {method}",
        "issued_at": "2199-06-10",
        "responsible_employee": "يوسف عبدالغني",
        "bank_collection_status": status,
    }
    response = requests.post(f"{base_url}/api/revenues", json=payload, headers=_headers(token), timeout=60)
    assert response.status_code == 200, response.text
    return response.json()


def _insert_interest_deposit():
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    now = datetime.now(timezone.utc).isoformat()
    db.deposits.insert_one({
        "id": str(uuid.uuid4()),
        "organization_id": ORG_ID,
        "bank_id": BANK_ID,
        "account_number": f"ACC-{ITER_PREFIX}",
        "deposit_number": f"{ITER_PREFIX}-INT",
        "amount": 36500.0,
        "creation_datetime": "2199-06-01T00:00:00+00:00",
        "accounting_start_datetime": "2199-06-01T00:00:00+00:00",
        "maturity_datetime": "2199-07-01T00:00:00+00:00",
        "monthly_interest_rate": 10.0,
        "is_opening_balance_deposit": False,
        "status": "active",
        "created_at": now,
        "updated_at": now,
    })
    client.close()


def _row(rows: list[dict], account_name: str) -> dict:
    found = next((item for item in rows if item.get("account_name") == account_name), None)
    assert found is not None, f"missing account row: {account_name}; rows={[(r.get('account_code'), r.get('account_name')) for r in rows]}"
    return found


def test_trial_balance_separates_checks_payment_orders_and_deposit_interest(base_url, admin_token):
    _create_revenue(base_url, admin_token, "01", 340.0, "payment_order", status="collected")
    _create_revenue(base_url, admin_token, "02", 120.0, "check", status="under_collection")
    _insert_interest_deposit()

    response = requests.get(
        f"{base_url}/api/trial-balance",
        params={"from_date": "2199-06-01", "to_date": "2199-06-30"},
        headers=_headers(admin_token),
        timeout=90,
    )
    assert response.status_code == 200, response.text
    rows = response.json().get("rows", [])

    checks_row = _row(rows, "شيكات تحت التحصيل")
    payment_order_row = _row(rows, "إيرادات أوامر الدفع")
    deposit_interest_asset_row = _row(rows, "عوائد ودائع مستحقة")
    deposit_interest_revenue_row = _row(rows, "إيرادات فوائد ودائع")

    assert round(float(checks_row.get("total_debit") or 0), 2) == 120.0
    assert checks_row.get("account_type") == "asset"
    assert round(float(payment_order_row.get("total_credit") or 0), 2) == 340.0
    assert payment_order_row.get("account_type") == "revenue"
    assert round(float(deposit_interest_asset_row.get("total_debit") or 0), 2) == 300.0
    assert round(float(deposit_interest_revenue_row.get("total_credit") or 0), 2) == 300.0
    assert deposit_interest_revenue_row.get("account_type") == "revenue"