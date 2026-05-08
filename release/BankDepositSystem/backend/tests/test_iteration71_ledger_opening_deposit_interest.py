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
ITER_PREFIX = f"TEST-ITER71-{uuid.uuid4().hex[:8]}"


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


@pytest.fixture(scope="session")
def db_client():
    if not MONGO_URL or not DB_NAME:
        pytest.skip("MongoDB env is not configured")
    client = MongoClient(MONGO_URL)
    yield client[DB_NAME]
    client.close()


@pytest.fixture(scope="session", autouse=True)
def cleanup_iter71_data():
    yield
    if not MONGO_URL or not DB_NAME:
        return
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    db.deposits.delete_many({"deposit_number": {"$regex": f"^{ITER_PREFIX}"}})
    db.journal_entries.delete_many({"reference": {"$regex": f"^{ITER_PREFIX}"}})
    client.close()


def _account_by_system_key(base_url: str, token: str, system_key: str) -> dict:
    response = requests.get(f"{base_url}/api/chart-accounts", headers=_headers(token), timeout=60)
    assert response.status_code == 200, response.text
    account = next((item for item in response.json() if item.get("system_key") == system_key), None)
    assert account is not None, system_key
    return account


def _iso(value: str) -> str:
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc).isoformat()


def _insert_deposit(db, *, deposit_id: str, number: str, amount: float, start: str, maturity: str, rate: float, opening: bool = False):
    now = datetime.now(timezone.utc).isoformat()
    db.deposits.insert_one({
        "id": deposit_id,
        "organization_id": ORG_ID,
        "bank_id": "industrial-development",
        "account_number": f"ACC-{number}",
        "deposit_number": number,
        "amount": amount,
        "creation_datetime": _iso(start),
        "maturity_datetime": _iso(maturity),
        "monthly_interest_rate": rate,
        "is_opening_balance_deposit": opening,
        "accounting_start_datetime": _iso(start),
        "created_at": now,
        "updated_at": now,
    })


def _insert_opening_deposit_entry(db, term_account: dict, opening_equity: dict, deposit_id: str, amount: float):
    now = datetime.now(timezone.utc).isoformat()
    db.journal_entries.insert_one({
        "id": str(uuid.uuid4()),
        "organization_id": ORG_ID,
        "entry_number": 907100,
        "entry_date": "2096-01-05",
        "description": f"قيد تلقائي لرصيد افتتاحي وديعة قائمة رقم {ITER_PREFIX}-OPEN",
        "reference": f"{ITER_PREFIX}-OPEN",
        "source_type": "deposit",
        "source_id": deposit_id,
        "status": "approved",
        "is_auto": True,
        "is_reversal": False,
        "lines": [
            {"account_id": term_account["id"], "account_code": term_account["code"], "account_name": term_account["name"], "account_type": term_account["account_type"], "debit": amount, "credit": 0.0, "notes": "وديعة قائمة أول الفترة"},
            {"account_id": opening_equity["id"], "account_code": opening_equity["code"], "account_name": opening_equity["name"], "account_type": opening_equity["account_type"], "debit": 0.0, "credit": amount, "notes": "القيد المقابل"},
        ],
        "total_debit": amount,
        "total_credit": amount,
        "created_at": now,
        "updated_at": now,
    })


def test_opening_deposit_entry_moves_to_opening_balance_not_january_rows(base_url, admin_token, db_client):
    term_account = _account_by_system_key(base_url, admin_token, "term_deposits")
    opening_equity = _account_by_system_key(base_url, admin_token, "opening_balance_equity")
    deposit_id = str(uuid.uuid4())
    _insert_deposit(db_client, deposit_id=deposit_id, number=f"{ITER_PREFIX}-OPEN", amount=5000, start="2096-01-05T00:00:00", maturity="2096-12-31T00:00:00", rate=0, opening=True)
    _insert_opening_deposit_entry(db_client, term_account, opening_equity, deposit_id, 5000)

    response = requests.get(
        f"{base_url}/api/ledger",
        params={"account_id": term_account["id"], "from_date": "2096-01-01", "to_date": "2096-01-31"},
        headers=_headers(admin_token),
        timeout=90,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert round(float(body.get("opening_balance") or 0), 2) >= 5000.0
    assert all(row.get("reference") != f"{ITER_PREFIX}-OPEN" for row in body.get("rows", []))


def test_ledger_january_shows_aggregated_deposit_interest_only_for_period(base_url, admin_token, db_client):
    _insert_deposit(db_client, deposit_id=str(uuid.uuid4()), number=f"{ITER_PREFIX}-INT-1", amount=36500, start="2096-01-01T00:00:00", maturity="2096-03-01T00:00:00", rate=10)
    _insert_deposit(db_client, deposit_id=str(uuid.uuid4()), number=f"{ITER_PREFIX}-INT-2", amount=73000, start="2096-01-01T00:00:00", maturity="2096-03-01T00:00:00", rate=10)

    response = requests.get(
        f"{base_url}/api/ledger",
        params={"account_id": "all", "from_date": "2096-01-01", "to_date": "2096-01-31"},
        headers=_headers(admin_token),
        timeout=90,
    )
    assert response.status_code == 200, response.text
    rows = response.json().get("rows", [])
    interest_rows = [row for row in rows if row.get("reference") == "DEPOSIT-INTEREST-PERIOD" and row.get("account_name") == "إيرادات فوائد ودائع"]
    assert len(interest_rows) == 1
    assert round(float(interest_rows[0].get("credit") or 0), 2) == 930.0
    assert all(row.get("reference") != f"{ITER_PREFIX}-OPEN" for row in rows)