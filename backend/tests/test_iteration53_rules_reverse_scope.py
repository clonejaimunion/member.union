"""Iteration 53: rules-engine edit/priority automation, reverse entries behavior, fail-safe, auth headers, setup download."""

import os
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient


# Modules/features under test: rules-engine create/update auto-priority, journal reverse-on-delete, deposit reverse-on-delete, fail-safe, auth headers, setup binary
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or dotenv_values("/app/frontend/.env").get("REACT_APP_BACKEND_URL") or "").rstrip("/")
LOCAL_API_URL = "http://localhost:8001"

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
    login = _login(ADMIN_USERNAME, ADMIN_PASSWORD, ORG_ID)
    if login.status_code != 200:
        pytest.skip(f"Admin login failed: {login.status_code}")
    token = login.json().get("token")
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


@pytest.fixture()
def cleanup_tracker(mongo_db):
    tracker = {"rule_ids": []}
    yield tracker
    if tracker["rule_ids"]:
        mongo_db.accounting_rules.delete_many({"id": {"$in": tracker["rule_ids"]}, "organization_id": ORG_ID})


def _balanced_manual_entry_payload(prefix: str = "ITER53"):
    return {
        "entry_date": date.today().isoformat(),
        "description": f"{prefix} balanced entry",
        "reference": f"{prefix}-{uuid.uuid4().hex[:8]}",
        "lines": [
            {"account_code": "1110", "account_name": "الخزينة", "debit": 150.0, "credit": 0},
            {"account_code": "4101", "account_name": "إيرادات الاشتراكات", "debit": 0, "credit": 150.0},
        ],
    }


def _deposit_payload(prefix: str = "ITER53"):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    maturity = now + timedelta(days=366)
    suffix = uuid.uuid4().hex[:8]
    return {
        "account_number": f"{prefix}-ACC-{suffix}",
        "deposit_number": f"{prefix}-DEP-{suffix}",
        "amount": 1200.0,
        "creation_datetime": now.isoformat(),
        "maturity_datetime": maturity.isoformat(),
        "monthly_interest_rate": 1.5,
    }


def test_auth_login_sets_httponly_cookie():
    response = _login(ADMIN_USERNAME, ADMIN_PASSWORD, ORG_ID)
    assert response.status_code == 200, response.text
    assert bool(response.json().get("token")) is True
    set_cookie = response.headers.get("set-cookie", "")
    assert "access_token=" in set_cookie
    assert "HttpOnly" in set_cookie


def test_auth_cors_preflight_allows_credentials_with_explicit_origin():
    response = requests.options(
        f"{LOCAL_API_URL}/api/auth/login",
        headers={
            "Origin": BASE_URL,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,authorization",
        },
        timeout=30,
    )
    assert response.status_code in (200, 204)
    assert response.headers.get("access-control-allow-credentials", "").lower() == "true"
    assert response.headers.get("access-control-allow-origin", "") not in ("", "*")


def test_rules_engine_post_then_put_auto_calculates_priority(admin_token, cleanup_tracker):
    create_payload = {
        "event_type": "Expense",
        "sub_type": "hajj_umrah",
        "payment_method": "bank_transfer",
        "debit_account": "المصروفات",
        "credit_account": "البنك",
        "priority": 10,
        "is_active": True,
        "notes": "ITER53 rule create",
    }
    created = requests.post(f"{BASE_URL}/api/rules-engine/rules", json=create_payload, headers=_headers(admin_token), timeout=40)
    assert created.status_code == 200, created.text
    created_body = created.json()
    cleanup_tracker["rule_ids"].append(created_body["id"])
    assert created_body["priority"] == 3

    update_payload = {
        **create_payload,
        "priority": 1,
        "notes": "ITER53 rule updated",
    }
    updated = requests.put(
        f"{BASE_URL}/api/rules-engine/rules/{created_body['id']}",
        json=update_payload,
        headers=_headers(admin_token),
        timeout=40,
    )
    assert updated.status_code == 200, updated.text
    updated_body = updated.json()
    assert updated_body["priority"] == 3
    assert updated_body["notes"] == "ITER53 rule updated"


def test_fail_safe_unbalanced_manual_journal_create_returns_422(admin_token):
    payload = {
        "entry_date": date.today().isoformat(),
        "description": "ITER53 unbalanced create",
        "reference": f"ITER53-UC-{uuid.uuid4().hex[:8]}",
        "lines": [
            {"account_code": "1110", "account_name": "الخزينة", "debit": 120.0, "credit": 0},
            {"account_code": "4101", "account_name": "إيرادات الاشتراكات", "debit": 0, "credit": 100.0},
        ],
    }
    response = requests.post(f"{BASE_URL}/api/journal-entries", json=payload, headers=_headers(admin_token), timeout=40)
    assert response.status_code == 422, response.text


def test_delete_journal_entry_creates_reversal_and_links_original(admin_token, mongo_db):
    create = requests.post(f"{BASE_URL}/api/journal-entries", json=_balanced_manual_entry_payload(), headers=_headers(admin_token), timeout=40)
    assert create.status_code == 200, create.text
    original = create.json()

    delete_response = requests.delete(f"{BASE_URL}/api/journal-entries/{original['id']}", headers=_headers(admin_token), timeout=40)
    assert delete_response.status_code == 200, delete_response.text
    reversal = delete_response.json()

    original_doc = mongo_db.journal_entries.find_one({"id": original["id"], "organization_id": ORG_ID}, {"_id": 0})
    reversal_doc = mongo_db.journal_entries.find_one({"id": reversal["id"], "organization_id": ORG_ID}, {"_id": 0})
    assert original_doc is not None
    assert reversal_doc is not None
    assert original_doc.get("reversal_entry_id") == reversal["id"]
    assert reversal_doc.get("is_reversal") is True
    assert reversal_doc.get("reversal_of_entry_id") == original["id"]

    for idx, line in enumerate(original_doc.get("lines", [])):
        rev_line = reversal_doc.get("lines", [])[idx]
        assert float(rev_line.get("debit") or 0) == pytest.approx(float(line.get("credit") or 0))
        assert float(rev_line.get("credit") or 0) == pytest.approx(float(line.get("debit") or 0))


def test_delete_deposit_creates_reverse_entries_not_hard_delete(admin_token, mongo_db):
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
            {"_id": 0, "id": 1, "source_type": 1, "is_reversal": 1, "reversal_entry_id": 1},
        )
    )
    assert len(before_docs) >= 2

    delete_response = requests.delete(f"{BASE_URL}/api/banks/{BANK_ID}/deposits/{deposit['id']}", headers=_headers(admin_token), timeout=40)
    assert delete_response.status_code == 200, delete_response.text

    after_docs = list(
        mongo_db.journal_entries.find(
            {"organization_id": ORG_ID, "source_id": deposit["id"], "source_type": {"$in": ["deposit", "deposit_interest"]}},
            {"_id": 0, "id": 1, "source_type": 1, "is_reversal": 1, "reversal_entry_id": 1, "reversal_of_entry_id": 1},
        )
    )
    assert len(after_docs) >= 4

    non_reversal_docs = [doc for doc in after_docs if not doc.get("is_reversal")]
    reversal_docs = [doc for doc in after_docs if doc.get("is_reversal")]
    assert len(non_reversal_docs) >= 2
    assert len(reversal_docs) >= 2
    assert all(doc.get("reversal_entry_id") for doc in non_reversal_docs)


def test_download_setup_exe_is_valid_and_matches_dist_size():
    response = requests.get(f"{BASE_URL}/api/download/setup", timeout=120)
    assert response.status_code == 200, response.text
    assert response.content[:2] == b"MZ"

    local_exe = Path("/app/dist/BankDepositSystemSetup.exe")
    assert local_exe.exists()
    assert len(response.content) == local_exe.stat().st_size


def test_bcrypt_hash_prefix_and_seed_admin_password_update_logic_present(mongo_db):
    admin_user = mongo_db.users.find_one({"username": "admin", "organization_id": ORG_ID}, {"_id": 0, "password_hash": 1})
    assert admin_user is not None
    assert str(admin_user.get("password_hash", "")).startswith("$2b$")

    server_text = Path("/app/backend/server.py").read_text(encoding="utf-8")
    assert "if not verify_password(ADMIN_INITIAL_PASSWORD, existing.get(\"password_hash\", \"\"))" in server_text
    assert 'document["password_hash"] = hash_password(ADMIN_INITIAL_PASSWORD)' in server_text
