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
ORG_ID = "social-solidarity"
BANK_ID = "industrial-development"
ITER_PREFIX = f"TEST-ITER73-{uuid.uuid4().hex[:8]}"


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
def cleanup_iter73_data():
    yield
    if not MONGO_URL or not DB_NAME:
        return
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    db.deposits.delete_many({"deposit_number": {"$regex": f"^{ITER_PREFIX}"}})
    db.journal_entries.delete_many({"reference": {"$regex": f"^{ITER_PREFIX}"}})
    client.close()


def _create_deposit(base_url: str, token: str, number: str, amount: float, start: str, maturity: str, rate: float, renewed_from: str | None = None):
    payload = {
        "account_number": f"ACC-{number}",
        "deposit_number": number,
        "amount": amount,
        "creation_datetime": f"{start}T00:00:00Z",
        "maturity_datetime": f"{maturity}T00:00:00Z",
        "monthly_interest_rate": rate,
        "is_opening_balance_deposit": False,
        "renewed_from_deposit_id": renewed_from,
        "renewal_notes": None,
    }
    response = requests.post(f"{base_url}/api/banks/{BANK_ID}/deposits", json=payload, headers=_headers(token), timeout=90)
    assert response.status_code == 200, response.text
    return response.json()


def _term_deposit_balance(rows):
    row = next((item for item in rows if item.get("account_name") == "ودائع لأجل" or item.get("account_code") == "1250"), None)
    if row is None:
        return 0.0
    return round(float(row.get("balance_debit") or 0) - float(row.get("balance_credit") or 0), 2)


def test_renewed_deposit_is_independent_and_active_asset_is_period_scoped(base_url, admin_token):
    old_deposit = _create_deposit(base_url, admin_token, f"{ITER_PREFIX}-OLD", 1000.0, "2198-01-01", "2198-02-01", 12.0)
    new_deposit = _create_deposit(base_url, admin_token, f"{ITER_PREFIX}-NEW", 1300.0, "2198-02-01", "2198-03-01", 15.0, renewed_from=old_deposit["id"])

    deposits_response = requests.get(f"{base_url}/api/banks/{BANK_ID}/deposits", headers=_headers(admin_token), timeout=60)
    assert deposits_response.status_code == 200, deposits_response.text
    deposits = deposits_response.json()
    refreshed_old = next(item for item in deposits if item["id"] == old_deposit["id"])
    refreshed_new = next(item for item in deposits if item["id"] == new_deposit["id"])
    assert refreshed_old["status"] == "renewed"
    assert refreshed_new["status"] == "active"
    assert refreshed_new["renewed_from_deposit_id"] == old_deposit["id"]
    assert "تم إعادة ربط الوديعة" in refreshed_old["renewal_notes"]
    assert refreshed_old["renewal_notes"] == refreshed_new["renewal_notes"]

    jan_statement = requests.get(
        f"{base_url}/api/banks/{BANK_ID}/statements/detailed",
        params={"period_type": "monthly", "year": 2198, "month": 1, "previous_period_type": "monthly", "previous_year": 2197, "previous_month": 1},
        headers=_headers(admin_token),
        timeout=90,
    )
    assert jan_statement.status_code == 200, jan_statement.text
    jan_numbers = {row["deposit_number"] for row in jan_statement.json().get("rows", [])}
    assert f"{ITER_PREFIX}-OLD" in jan_numbers
    assert f"{ITER_PREFIX}-NEW" not in jan_numbers

    feb_statement = requests.get(
        f"{base_url}/api/banks/{BANK_ID}/statements/detailed",
        params={"period_type": "monthly", "year": 2198, "month": 2, "previous_period_type": "monthly", "previous_year": 2197, "previous_month": 2},
        headers=_headers(admin_token),
        timeout=90,
    )
    assert feb_statement.status_code == 200, feb_statement.text
    feb_rows = feb_statement.json().get("rows", [])
    feb_numbers = {row["deposit_number"] for row in feb_rows}
    assert f"{ITER_PREFIX}-OLD" not in feb_numbers
    assert f"{ITER_PREFIX}-NEW" in feb_numbers
    assert next(row for row in feb_rows if row["deposit_number"] == f"{ITER_PREFIX}-NEW")["renewal_notes"] == refreshed_new["renewal_notes"]

    jan_trial = requests.get(
        f"{base_url}/api/trial-balance",
        params={"from_date": "2198-01-01", "to_date": "2198-01-31"},
        headers=_headers(admin_token),
        timeout=90,
    )
    assert jan_trial.status_code == 200, jan_trial.text
    assert _term_deposit_balance(jan_trial.json().get("rows", [])) == 0.0

    feb_trial = requests.get(
        f"{base_url}/api/trial-balance",
        params={"from_date": "2198-02-01", "to_date": "2198-02-28"},
        headers=_headers(admin_token),
        timeout=90,
    )
    assert feb_trial.status_code == 200, feb_trial.text
    assert _term_deposit_balance(feb_trial.json().get("rows", [])) == 0.0

    april_trial = requests.get(
        f"{base_url}/api/trial-balance",
        params={"from_date": "2198-04-01", "to_date": "2198-04-30"},
        headers=_headers(admin_token),
        timeout=90,
    )
    assert april_trial.status_code == 200, april_trial.text
    assert _term_deposit_balance(april_trial.json().get("rows", [])) == 0.0