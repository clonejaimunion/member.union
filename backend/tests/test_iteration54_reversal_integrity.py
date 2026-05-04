"""Iteration 54: targeted reversal integrity checks for deposit/journal deletes."""

import os
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient


# Modules/features under test: deposit delete reversal integrity and manual journal delete reversal integrity
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or dotenv_values("/app/frontend/.env").get("REACT_APP_BACKEND_URL") or "").rstrip("/")
MONGO_URL = (dotenv_values("/app/backend/.env").get("MONGO_URL") or "").strip('"')
DB_NAME = (dotenv_values("/app/backend/.env").get("DB_NAME") or "").strip('"')

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Admin@123"
ORG_ID = "social-solidarity"
BANK_ID = "industrial-development"


def _headers(token: str | None = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _login(username: str, password: str, organization_id: str = ORG_ID):
    return requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": username, "password": password, "organization_id": organization_id},
        headers=_headers(),
        timeout=40,
    )


@pytest.fixture(scope="session", autouse=True)
def require_base_url():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL is not configured")


@pytest.fixture(scope="session")
def admin_token():
    response = _login(ADMIN_USERNAME, ADMIN_PASSWORD, ORG_ID)
    if response.status_code != 200:
        pytest.skip(f"Admin login failed: {response.status_code}")
    token = response.json().get("token")
    if not token:
        pytest.skip("No token returned for admin login")
    return token


@pytest.fixture(scope="session")
def mongo_db():
    if not MONGO_URL or not DB_NAME:
        pytest.skip("Mongo env not available")
    client = MongoClient(MONGO_URL)
    try:
        yield client[DB_NAME]
    finally:
        client.close()


def _deposit_payload(prefix: str = "ITER54"):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    maturity = now + timedelta(days=400)
    suffix = uuid.uuid4().hex[:8]
    return {
        "account_number": f"{prefix}-ACC-{suffix}",
        "deposit_number": f"{prefix}-DEP-{suffix}",
        "amount": 1750.0,
        "creation_datetime": now.isoformat(),
        "maturity_datetime": maturity.isoformat(),
        "monthly_interest_rate": 1.25,
    }


def _manual_entry_payload(prefix: str = "ITER54"):
    return {
        "entry_date": date.today().isoformat(),
        "description": f"{prefix} manual delete reversal",
        "reference": f"{prefix}-{uuid.uuid4().hex[:8]}",
        "lines": [
            {"account_code": "1110", "account_name": "الخزينة", "debit": 210.0, "credit": 0},
            {"account_code": "4101", "account_name": "إيرادات الاشتراكات", "debit": 0, "credit": 210.0},
        ],
    }


def test_deposit_delete_preserves_originals_and_creates_new_reversal_rows(admin_token, mongo_db):
    create = requests.post(
        f"{BASE_URL}/api/banks/{BANK_ID}/deposits",
        json=_deposit_payload(),
        headers=_headers(admin_token),
        timeout=40,
    )
    assert create.status_code == 200, create.text
    deposit = create.json()

    before_docs = list(
        mongo_db.journal_entries.find(
            {"organization_id": ORG_ID, "source_id": deposit["id"], "source_type": {"$in": ["deposit", "deposit_interest"]}},
            {"_id": 0, "id": 1, "is_reversal": 1, "reversal_entry_id": 1, "reversal_of_entry_id": 1},
        )
    )
    assert len(before_docs) >= 2
    original_ids = {doc["id"] for doc in before_docs}
    assert all(not bool(doc.get("is_reversal")) for doc in before_docs)

    deleted = requests.delete(f"{BASE_URL}/api/banks/{BANK_ID}/deposits/{deposit['id']}", headers=_headers(admin_token), timeout=40)
    assert deleted.status_code == 200, deleted.text

    after_docs = list(
        mongo_db.journal_entries.find(
            {"organization_id": ORG_ID, "source_id": deposit["id"], "source_type": {"$in": ["deposit", "deposit_interest"]}},
            {"_id": 0, "id": 1, "is_reversal": 1, "reversal_entry_id": 1, "reversal_of_entry_id": 1},
        )
    )
    assert len(after_docs) >= 4

    originals_after = [doc for doc in after_docs if doc["id"] in original_ids]
    reversals_after = [doc for doc in after_docs if bool(doc.get("is_reversal"))]

    assert len(originals_after) == len(before_docs)
    assert all(not bool(doc.get("is_reversal")) for doc in originals_after)
    assert all(doc.get("reversal_entry_id") and doc.get("reversal_entry_id") != doc["id"] for doc in originals_after)

    assert len(reversals_after) >= len(before_docs)
    assert all(doc.get("reversal_of_entry_id") in original_ids for doc in reversals_after)
    assert all(doc["id"] not in original_ids for doc in reversals_after)


def test_manual_journal_delete_creates_separate_reversal_linked_to_original(admin_token, mongo_db):
    created = requests.post(
        f"{BASE_URL}/api/journal-entries",
        json=_manual_entry_payload(),
        headers=_headers(admin_token),
        timeout=40,
    )
    assert created.status_code == 200, created.text
    original = created.json()

    deleted = requests.delete(f"{BASE_URL}/api/journal-entries/{original['id']}", headers=_headers(admin_token), timeout=40)
    assert deleted.status_code == 200, deleted.text
    reversal = deleted.json()

    original_doc = mongo_db.journal_entries.find_one({"id": original["id"], "organization_id": ORG_ID}, {"_id": 0})
    reversal_doc = mongo_db.journal_entries.find_one({"id": reversal["id"], "organization_id": ORG_ID}, {"_id": 0})

    assert original_doc is not None
    assert reversal_doc is not None
    assert original_doc.get("is_reversal") is not True
    assert reversal_doc.get("is_reversal") is True
    assert reversal_doc.get("reversal_of_entry_id") == original["id"]
    assert original_doc.get("reversal_entry_id") == reversal["id"]
    assert reversal_doc["id"] != original_doc["id"]
