import os
import uuid
from datetime import date

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient


# Modules/features under test: reversal visibility, accounting data-flow endpoint, purge guardrails, auth security basics
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
MONGO_URL = (dotenv_values("/app/backend/.env").get("MONGO_URL") or "").strip('"')
DB_NAME = (dotenv_values("/app/backend/.env").get("DB_NAME") or "").strip('"')


@pytest.fixture(scope="session")
def base_url():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL is not configured")
    return BASE_URL.rstrip("/")


@pytest.fixture(scope="session")
def session_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _login(base_url: str, session_client: requests.Session, username: str, password: str, organization_id: str):
    return session_client.post(
        f"{base_url}/api/auth/login",
        json={
            "username": username,
            "password": password,
            "organization_id": organization_id,
        },
        timeout=40,
    )


@pytest.fixture(scope="session")
def super_admin_headers(base_url, session_client):
    resp = _login(base_url, session_client, "admin", "Admin@123", "social-solidarity")
    if resp.status_code != 200:
        pytest.skip(f"super admin login failed: {resp.status_code} {resp.text}")
    token = resp.json().get("token")
    if not token:
        pytest.skip("missing super admin token")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def normal_admin_headers(base_url, session_client):
    resp = _login(base_url, session_client, "admin_takaful", "Admin@123", "social-solidarity")
    if resp.status_code != 200:
        pytest.skip(f"normal admin login failed: {resp.status_code} {resp.text}")
    token = resp.json().get("token")
    if not token:
        pytest.skip("missing normal admin token")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def mongo_db():
    if not MONGO_URL or not DB_NAME:
        pytest.skip("Mongo config missing for DB-level reversal verification")
    client = MongoClient(MONGO_URL)
    try:
        yield client[DB_NAME]
    finally:
        client.close()


@pytest.fixture
def created_reversal_pair(base_url, session_client, super_admin_headers):
    suffix = uuid.uuid4().hex[:8]
    payload = {
        "entry_date": date.today().isoformat(),
        "description": f"TEST_ITER60 reversal hidden check {suffix}",
        "reference": f"ITER60-{suffix}",
        "lines": [
            {"account_code": "1110", "account_name": "الخزينة", "debit": 55.0, "credit": 0},
            {"account_code": "4101", "account_name": "إيرادات الاشتراكات", "debit": 0, "credit": 55.0},
        ],
    }
    create_resp = session_client.post(f"{base_url}/api/journal-entries", headers=super_admin_headers, json=payload, timeout=40)
    assert create_resp.status_code == 200, create_resp.text
    original = create_resp.json()

    delete_resp = session_client.delete(f"{base_url}/api/journal-entries/{original['id']}", headers=super_admin_headers, timeout=40)
    assert delete_resp.status_code == 200, delete_resp.text
    reversal = delete_resp.json()

    return {
        "original_id": original["id"],
        "reversal_id": reversal["id"],
        "reference": payload["reference"],
    }


def test_auth_login_sets_http_only_cookie(base_url, session_client):
    resp = _login(base_url, session_client, "admin", "Admin@123", "social-solidarity")
    assert resp.status_code == 200
    set_cookie = resp.headers.get("set-cookie", "")
    assert "httponly" in set_cookie.lower()


def test_admin_password_hash_is_bcrypt_2b_prefix(mongo_db):
    admin_doc = mongo_db.users.find_one({"username": "admin", "role": "super_admin"}, {"_id": 0, "password_hash": 1})
    assert admin_doc is not None
    password_hash = str(admin_doc.get("password_hash") or "")
    assert password_hash.startswith("$2b$")


def test_login_lockout_after_three_failed_attempts(base_url, session_client):
    fake_username = f"iter60_lock_{uuid.uuid4().hex[:6]}"
    for _ in range(3):
        failed = _login(base_url, session_client, fake_username, "wrong-password", "social-solidarity")
        assert failed.status_code == 401
    locked = _login(base_url, session_client, fake_username, "wrong-password", "social-solidarity")
    assert locked.status_code == 429


def test_journal_entries_exclude_is_reversal_rows_but_reversal_persists_in_db(base_url, session_client, super_admin_headers, created_reversal_pair, mongo_db):
    entries_resp = session_client.get(f"{base_url}/api/journal-entries", headers=super_admin_headers, timeout=60)
    assert entries_resp.status_code == 200, entries_resp.text
    entries = entries_resp.json()

    assert all(item.get("is_reversal") is not True for item in entries)
    entry_ids = {item.get("id") for item in entries}
    assert created_reversal_pair["reversal_id"] not in entry_ids

    reversal_doc = mongo_db.journal_entries.find_one({"id": created_reversal_pair["reversal_id"]}, {"_id": 0, "is_reversal": 1})
    assert reversal_doc is not None
    assert reversal_doc.get("is_reversal") is True


def test_ledger_excludes_reversal_entries(base_url, session_client, super_admin_headers, created_reversal_pair):
    entries_resp = session_client.get(f"{base_url}/api/journal-entries", headers=super_admin_headers, timeout=60)
    assert entries_resp.status_code == 200, entries_resp.text
    matching_original = next((item for item in entries_resp.json() if item.get("id") == created_reversal_pair["original_id"]), None)
    if not matching_original:
        pytest.skip("Original manual entry is not visible in journal listing to infer account code")
    inferred_account_code = None
    for line in matching_original.get("lines", []):
        if float(line.get("debit") or 0) > 0:
            inferred_account_code = line.get("account_code")
            break
    if not inferred_account_code:
        inferred_account_code = matching_original.get("lines", [{}])[0].get("account_code")
    if not inferred_account_code:
        pytest.skip("Could not infer account code from created entry lines")

    ledger_resp = session_client.get(
        f"{base_url}/api/ledger",
        headers=super_admin_headers,
        params={"account_code": inferred_account_code, "from_date": "1900-01-01", "to_date": "2099-12-31"},
        timeout=90,
    )
    assert ledger_resp.status_code == 200, ledger_resp.text
    rows = ledger_resp.json().get("rows", [])
    assert all(row.get("entry_id") != created_reversal_pair["reversal_id"] for row in rows)


def test_trial_balance_balanced_and_financial_statements_valid_without_reversal_noise(base_url, session_client, super_admin_headers):
    trial_resp = session_client.get(
        f"{base_url}/api/trial-balance",
        headers=super_admin_headers,
        params={"from_date": "1900-01-01", "to_date": "2099-12-31"},
        timeout=90,
    )
    assert trial_resp.status_code == 200, trial_resp.text
    trial = trial_resp.json()
    assert trial.get("is_balanced") is True
    assert round(float(trial.get("total_debit") or 0), 2) == round(float(trial.get("total_credit") or 0), 2)

    fs_resp = session_client.get(
        f"{base_url}/api/financial-statements",
        headers=super_admin_headers,
        params={"from_date": "1900-01-01", "to_date": "2099-12-31"},
        timeout=120,
    )
    assert fs_resp.status_code == 200, fs_resp.text
    fs_data = fs_resp.json()
    assert fs_data.get("is_accounting_valid") is True
    assert round(float(fs_data.get("balance_sheet", {}).get("check", {}).get("total") or 0), 2) == 0.0


def test_admin_data_flow_validation_returns_accounting_and_membership_sections(base_url, session_client, super_admin_headers):
    resp = session_client.get(f"{base_url}/api/admin/data-flow-validation", headers=super_admin_headers, timeout=120)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data.get("is_valid") is True
    organizations = data.get("organizations") or []
    assert len(organizations) >= 2

    social = next((item for item in organizations if item.get("organization_id") == "social-solidarity"), None)
    assert social is not None
    assert "accounting" in social and "membership" in social
    assert isinstance(social["membership"].get("status_counts"), dict)
    assert "total_due" in social["membership"]
    assert "total_collected" in social["membership"]
    assert "remaining_balance" in social["membership"]
    assert isinstance(social["membership"].get("issues"), list)


def test_program_data_purge_is_super_admin_only(base_url, session_client, normal_admin_headers):
    resp = session_client.post(
        f"{base_url}/api/admin/program-data/purge",
        headers=normal_admin_headers,
        json={"scope": "current_organization", "confirmation_phrase": "تفريغ البيانات نهائيا", "include_banks": False, "include_users": False},
        timeout=40,
    )
    assert resp.status_code == 403


def test_program_data_purge_rejects_wrong_confirmation_phrase(base_url, session_client, super_admin_headers):
    resp = session_client.post(
        f"{base_url}/api/admin/program-data/purge",
        headers=super_admin_headers,
        json={"scope": "current_organization", "confirmation_phrase": "عبارة خاطئة", "include_banks": False, "include_users": False},
        timeout=40,
    )
    assert resp.status_code == 422
