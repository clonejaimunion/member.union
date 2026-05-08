import os
import uuid

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient


# Deposits renewal regression: independent renewals, statuses/notes sync, and journal isolation.
FRONTEND_ENV = dotenv_values("/app/frontend/.env")
BACKEND_ENV = dotenv_values("/app/backend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or FRONTEND_ENV.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
MONGO_URL = (BACKEND_ENV.get("MONGO_URL") or "").strip('"')
DB_NAME = (BACKEND_ENV.get("DB_NAME") or "").strip('"')
ORG_ID = "social-solidarity"
BANK_ID = "industrial-development"
ITER_PREFIX = f"TEST-ITER74-{uuid.uuid4().hex[:8]}"


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
def cleanup_iter74_data():
    yield
    if not MONGO_URL or not DB_NAME:
        return
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    db.deposits.delete_many({"deposit_number": {"$regex": f"^{ITER_PREFIX}"}})
    db.journal_entries.delete_many({"reference": {"$regex": f"^{ITER_PREFIX}"}})
    client.close()


def _create_deposit(
    base_url: str,
    token: str,
    number: str,
    amount: float,
    start: str,
    maturity: str,
    rate: float,
    renewed_from: str | None = None,
    renewal_notes: str | None = None,
):
    payload = {
        "account_number": f"ACC-{number}",
        "deposit_number": number,
        "amount": amount,
        "creation_datetime": f"{start}T00:00:00Z",
        "maturity_datetime": f"{maturity}T00:00:00Z",
        "monthly_interest_rate": rate,
        "is_opening_balance_deposit": False,
        "renewed_from_deposit_id": renewed_from,
        "renewal_notes": renewal_notes,
    }
    response = requests.post(f"{base_url}/api/banks/{BANK_ID}/deposits", json=payload, headers=_headers(token), timeout=90)
    assert response.status_code == 200, response.text
    return response.json()


def test_renewal_creates_new_deposit_without_mutating_old_core_fields(base_url, admin_token):
    old_number = f"{ITER_PREFIX}-OLD"
    new_number = f"{ITER_PREFIX}-NEW"
    old_deposit = _create_deposit(base_url, admin_token, old_number, 2100.0, "2197-01-01", "2197-02-01", 10.0)
    old_snapshot = {
        "deposit_number": old_deposit["deposit_number"],
        "amount": old_deposit["amount"],
        "creation_datetime": old_deposit["creation_datetime"],
        "maturity_datetime": old_deposit["maturity_datetime"],
    }

    new_deposit = _create_deposit(
        base_url,
        admin_token,
        new_number,
        2300.0,
        "2197-02-01",
        "2197-03-01",
        11.0,
        renewed_from=old_deposit["id"],
        renewal_notes=f"{ITER_PREFIX} linked renewal note",
    )

    deposits_response = requests.get(f"{base_url}/api/banks/{BANK_ID}/deposits", headers=_headers(admin_token), timeout=60)
    assert deposits_response.status_code == 200, deposits_response.text
    deposits = deposits_response.json()

    refreshed_old = next(item for item in deposits if item["id"] == old_deposit["id"])
    refreshed_new = next(item for item in deposits if item["id"] == new_deposit["id"])
    assert refreshed_old["status"] == "renewed"
    assert refreshed_new["status"] == "active"
    assert refreshed_new["renewed_from_deposit_id"] == old_deposit["id"]
    assert refreshed_old["renewal_notes"] == refreshed_new["renewal_notes"]

    assert refreshed_old["deposit_number"] == old_snapshot["deposit_number"]
    assert round(float(refreshed_old["amount"]), 2) == round(float(old_snapshot["amount"]), 2)
    assert refreshed_old["creation_datetime"] == old_snapshot["creation_datetime"]
    assert refreshed_old["maturity_datetime"] == old_snapshot["maturity_datetime"]


def test_renewal_does_not_create_extra_journal_rows_or_copy_renewal_notes_into_journal(base_url, admin_token):
    old_number = f"{ITER_PREFIX}-J-OLD"
    new_number = f"{ITER_PREFIX}-J-NEW"
    old_deposit = _create_deposit(base_url, admin_token, old_number, 1500.0, "2196-01-01", "2196-02-01", 9.5)

    before_response = requests.get(f"{base_url}/api/journal-entries", params={"source_type": "deposit"}, headers=_headers(admin_token), timeout=90)
    assert before_response.status_code == 200, before_response.text
    before_entries = [
        entry for entry in before_response.json()
        if entry.get("reference") in {old_number, new_number}
    ]
    before_count = len(before_entries)

    renewal_note = f"{ITER_PREFIX} renewal journal visibility check"
    _create_deposit(
        base_url,
        admin_token,
        new_number,
        1800.0,
        "2196-02-01",
        "2196-03-01",
        10.5,
        renewed_from=old_deposit["id"],
        renewal_notes=renewal_note,
    )

    after_response = requests.get(f"{base_url}/api/journal-entries", params={"source_type": "deposit"}, headers=_headers(admin_token), timeout=90)
    assert after_response.status_code == 200, after_response.text
    after_entries = [
        entry for entry in after_response.json()
        if entry.get("reference") in {old_number, new_number}
    ]
    assert len(after_entries) == before_count + 1

    journal_blob = "\n".join(
        [
            str(entry.get("description") or "") + " " + str(entry.get("reference") or "") + " " + " ".join(str(line.get("notes") or "") for line in entry.get("lines", []))
            for entry in after_entries
        ]
    )
    assert renewal_note not in journal_blob
