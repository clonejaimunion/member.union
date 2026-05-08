import os
import uuid

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient


FRONTEND_ENV = dotenv_values("/app/frontend/.env")
BACKEND_ENV = dotenv_values("/app/backend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or FRONTEND_ENV.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
MONGO_URL = (BACKEND_ENV.get("MONGO_URL") or "").strip('"')
DB_NAME = (BACKEND_ENV.get("DB_NAME") or "").strip('"')
ITER_PREFIX = f"TEST-ITER70-{uuid.uuid4().hex[:8]}"


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
    return response.json()["token"]


@pytest.fixture(scope="session", autouse=True)
def cleanup_iter70_data():
    yield
    if not MONGO_URL or not DB_NAME:
        return
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    db.journal_entries.delete_many({"reference": {"$regex": f"^{ITER_PREFIX}"}})
    db.chart_accounts.delete_many({"code": {"$regex": f"^{ITER_PREFIX}"}})
    client.close()


def _create_account(base_url: str, token: str, suffix: str, account_type: str, nature: str) -> dict:
    payload = {
        "code": f"{ITER_PREFIX}-{suffix}",
        "name": f"{ITER_PREFIX} {suffix}",
        "account_type": account_type,
        "nature": nature,
        "is_postable": True,
        "is_active": True,
        "opening_balance": 0,
    }
    response = requests.post(f"{base_url}/api/chart-accounts", json=payload, headers=_headers(token), timeout=60)
    assert response.status_code == 200, response.text
    return response.json()


def _create_entry(base_url: str, token: str, entry_date: str, reference: str, debit_account: str, credit_account: str, amount: float):
    payload = {
        "entry_date": entry_date,
        "description": reference,
        "reference": reference,
        "lines": [
            {"account_name": debit_account, "debit": amount, "credit": 0},
            {"account_name": credit_account, "debit": 0, "credit": amount},
        ],
    }
    response = requests.post(f"{base_url}/api/journal-entries", json=payload, headers=_headers(token), timeout=60)
    assert response.status_code == 200, response.text
    return response.json()


def test_ledger_all_shows_only_accounts_with_actual_period_movement(base_url, admin_token):
    active_debit = _create_account(base_url, admin_token, "ACTIVE-D", "asset", "debit")
    active_credit = _create_account(base_url, admin_token, "ACTIVE-C", "liability", "credit")
    dormant_debit = _create_account(base_url, admin_token, "DORMANT-D", "asset", "debit")
    dormant_credit = _create_account(base_url, admin_token, "DORMANT-C", "liability", "credit")

    _create_entry(base_url, admin_token, "2097-06-20", f"{ITER_PREFIX}-ACTIVE-OPENING", active_debit["name"], active_credit["name"], 100)
    _create_entry(base_url, admin_token, "2097-06-21", f"{ITER_PREFIX}-DORMANT-ONLY", dormant_debit["name"], dormant_credit["name"], 777)
    _create_entry(base_url, admin_token, "2097-07-10", f"{ITER_PREFIX}-ACTIVE-PERIOD", active_debit["name"], active_credit["name"], 25)

    response = requests.get(
        f"{base_url}/api/ledger",
        params={"account_id": "all", "from_date": "2097-07-01", "to_date": "2097-07-31"},
        headers=_headers(admin_token),
        timeout=90,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    rows = [row for row in body.get("rows", []) if str(row.get("reference") or "").startswith(ITER_PREFIX)]
    visible_account_ids = {row.get("account_id") for row in rows}

    assert active_debit["id"] in visible_account_ids
    assert active_credit["id"] in visible_account_ids
    assert dormant_debit["id"] not in visible_account_ids
    assert dormant_credit["id"] not in visible_account_ids
    assert all("DORMANT-ONLY" not in str(row.get("reference") or "") for row in rows)
    assert round(float(body.get("opening_balance") or 0), 2) == 0.0
    assert round(float(body.get("total_debit") or 0), 2) >= 25.0
    assert round(float(body.get("closing_balance") or 0), 2) == round(float(body.get("opening_balance") or 0) + float(body.get("total_debit") or 0) - float(body.get("total_credit") or 0), 2)