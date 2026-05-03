"""Iteration 49: rules-engine journal mapping, ledger sourcing, auth playbook, and setup download checks."""

import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient


# Modules/features under test: deposit journaling, expense-category account mapping, ledger sourcing, auth guards, setup download
ENV_BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
FILE_BASE_URL = dotenv_values("/app/frontend/.env").get("REACT_APP_BACKEND_URL")
BASE_URL = (ENV_BASE_URL or FILE_BASE_URL or "").rstrip("/")

MONGO_URL = dotenv_values("/app/backend/.env").get("MONGO_URL", "").strip('"')
DB_NAME = dotenv_values("/app/backend/.env").get("DB_NAME", "").strip('"')

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
        timeout=30,
    )


def _deposit_payload(prefix: str = "ITER49"):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    maturity = now + timedelta(days=366)
    suffix = uuid.uuid4().hex[:8]
    return {
        "account_number": f"{prefix}-ACC-{suffix}",
        "deposit_number": f"{prefix}-DEP-{suffix}",
        "amount": 1234.56,
        "creation_datetime": now.isoformat(),
        "maturity_datetime": maturity.isoformat(),
        "monthly_interest_rate": 1.5,
    }


def _expense_payload(category: str, prefix: str = "ITER49"):
    suffix = str(uuid.uuid4().int % 100000).zfill(5)
    return {
        "expense_number": suffix,
        "organization_scope": "social_solidarity_project",
        "expense_category": category,
        "payment_method": "cash",
        "payee_name": "TEST ITER49 PAYEE",
        "check_number": None,
        "transfer_number": None,
        "transfer_to": None,
        "membership_number": None,
        "committee": None,
        "governorate": None,
        "bank_id": BANK_ID,
        "gross_amount": 500,
        "gross_statement": f"TEST ITER49 {category}",
        "deductions": [],
        "issued_at": datetime.now(timezone.utc).date().isoformat(),
        "responsible_employee": "يوسف عبدالغني",
        "bank_payment_status": None,
    }


def _find_by_source_id(rows: list[dict], source_id: str):
    return next((row for row in rows if row.get("source_id") == source_id), None)


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


@pytest.fixture()
def created_records(admin_token):
    tracker = {"deposits": [], "expenses": []}
    yield tracker
    for bank_id, deposit_id in tracker["deposits"]:
        requests.delete(f"{BASE_URL}/api/banks/{bank_id}/deposits/{deposit_id}", headers=_headers(admin_token), timeout=30)
    for expense_id in tracker["expenses"]:
        requests.delete(f"{BASE_URL}/api/expenses/{expense_id}", headers=_headers(admin_token), timeout=30)


def test_create_deposit_generates_deposit_and_interest_journals_and_ledger_1250(admin_token, created_records):
    payload = _deposit_payload()
    create = requests.post(f"{BASE_URL}/api/banks/{BANK_ID}/deposits", json=payload, headers=_headers(admin_token), timeout=30)
    assert create.status_code == 200, create.text
    deposit = create.json()
    created_records["deposits"].append((BANK_ID, deposit["id"]))

    deposit_entries = requests.get(f"{BASE_URL}/api/journal-entries", params={"source_type": "deposit"}, headers=_headers(admin_token), timeout=30)
    assert deposit_entries.status_code == 200, deposit_entries.text
    deposit_journal = _find_by_source_id(deposit_entries.json(), deposit["id"])
    assert deposit_journal is not None
    term_line = next((line for line in deposit_journal["lines"] if line.get("account_code") == "1250"), None)
    assert term_line is not None
    assert term_line["debit"] == pytest.approx(1234.56)
    bank_credit_line = next((line for line in deposit_journal["lines"] if str(line.get("account_code") or "").startswith("11") and float(line.get("credit") or 0) > 0), None)
    assert bank_credit_line is not None
    assert bank_credit_line["credit"] == pytest.approx(1234.56)

    interest_entries = requests.get(f"{BASE_URL}/api/journal-entries", params={"source_type": "deposit_interest"}, headers=_headers(admin_token), timeout=30)
    assert interest_entries.status_code == 200, interest_entries.text
    interest_journal = _find_by_source_id(interest_entries.json(), deposit["id"])
    assert interest_journal is not None
    accrued_line = next((line for line in interest_journal["lines"] if line.get("account_code") == "1300"), None)
    assert accrued_line is not None
    assert accrued_line["debit"] == pytest.approx(18.52)

    ledger = requests.get(f"{BASE_URL}/api/ledger", params={"account_code": "1250"}, headers=_headers(admin_token), timeout=30)
    assert ledger.status_code == 200, ledger.text
    ledger_data = ledger.json()
    assert ledger_data["account"]["code"] == "1250"
    matched_row = next((row for row in ledger_data.get("rows", []) if row.get("reference") == deposit["deposit_number"] and row.get("source_type") == "deposit"), None)
    assert matched_row is not None
    assert matched_row["debit"] == pytest.approx(1234.56)


def test_delete_deposit_removes_deposit_and_interest_journals(admin_token):
    payload = _deposit_payload(prefix="ITER49DEL")
    create = requests.post(f"{BASE_URL}/api/banks/{BANK_ID}/deposits", json=payload, headers=_headers(admin_token), timeout=30)
    assert create.status_code == 200, create.text
    deposit = create.json()

    delete_response = requests.delete(f"{BASE_URL}/api/banks/{BANK_ID}/deposits/{deposit['id']}", headers=_headers(admin_token), timeout=30)
    assert delete_response.status_code == 200, delete_response.text

    deposit_entries = requests.get(f"{BASE_URL}/api/journal-entries", params={"source_type": "deposit"}, headers=_headers(admin_token), timeout=30)
    assert deposit_entries.status_code == 200
    assert _find_by_source_id(deposit_entries.json(), deposit["id"]) is None

    interest_entries = requests.get(f"{BASE_URL}/api/journal-entries", params={"source_type": "deposit_interest"}, headers=_headers(admin_token), timeout=30)
    assert interest_entries.status_code == 200
    assert _find_by_source_id(interest_entries.json(), deposit["id"]) is None


@pytest.mark.parametrize(
    "category,expected_code,expected_name",
    [
        ("hajj_umrah", "5104", "حج وعمرة"),
        ("meat_installment", "5105", "قسط لحوم"),
        ("union_committee", "5106", "لجنة نقابية"),
    ],
)
def test_expense_category_maps_to_specific_account_and_ledger(admin_token, created_records, category, expected_code, expected_name):
    create = requests.post(f"{BASE_URL}/api/expenses", json=_expense_payload(category), headers=_headers(admin_token), timeout=30)
    assert create.status_code == 200, create.text
    expense = create.json()
    created_records["expenses"].append(expense["id"])

    entries = requests.get(f"{BASE_URL}/api/journal-entries", params={"source_type": "expense"}, headers=_headers(admin_token), timeout=30)
    assert entries.status_code == 200, entries.text
    expense_journal = _find_by_source_id(entries.json(), expense["id"])
    assert expense_journal is not None

    mapped_line = next((line for line in expense_journal["lines"] if line.get("account_code") == expected_code), None)
    assert mapped_line is not None
    assert mapped_line["account_name"] == expected_name
    assert mapped_line["debit"] == pytest.approx(500)

    general_line = next((line for line in expense_journal["lines"] if line.get("account_code") == "5101"), None)
    assert general_line is None

    ledger = requests.get(f"{BASE_URL}/api/ledger", params={"account_code": expected_code}, headers=_headers(admin_token), timeout=30)
    assert ledger.status_code == 200, ledger.text
    ledger_row = next((row for row in ledger.json().get("rows", []) if row.get("reference") == expense["expense_number"] and row.get("source_type") == "expense"), None)
    assert ledger_row is not None
    assert ledger_row["debit"] == pytest.approx(500)


def test_download_setup_returns_valid_exe_binary():
    response = requests.get(f"{BASE_URL}/api/download/setup", timeout=60)
    assert response.status_code == 200, response.text
    assert response.content[:2] == b"MZ"
    assert len(response.content) > 1_000_000

    local_exe = Path("/app/dist/BankDepositSystemSetup.exe")
    if local_exe.exists():
        assert len(response.content) == local_exe.stat().st_size


def test_auth_login_sets_httponly_cookie_and_no_2fa_for_admin():
    response = _login(ADMIN_USERNAME, ADMIN_PASSWORD, ORG_ID)
    assert response.status_code == 200, response.text
    body = response.json()
    assert bool(body.get("token")) is True
    assert body.get("requires_2fa") is False
    set_cookie = response.headers.get("set-cookie", "")
    assert "access_token=" in set_cookie
    assert "HttpOnly" in set_cookie


def test_auth_cors_allows_credentials_with_explicit_origin():
    response = requests.options(
        f"{BASE_URL}/api/auth/login",
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


def test_auth_lockout_after_five_failed_attempts_requirement():
    username = f"iter49_lock_{uuid.uuid4().hex[:6]}"
    for _ in range(5):
        failed = _login(username, "WrongPass@123", ORG_ID)
        assert failed.status_code == 401

    locked = _login(username, "WrongPass@123", ORG_ID)
    assert locked.status_code in (423, 429)


def test_bcrypt_hash_prefix_and_seed_admin_password_update_guard_present():
    if not MONGO_URL or not DB_NAME:
        pytest.skip("Mongo env not available")

    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    try:
        admin_user = db.users.find_one({"username": "admin", "organization_id": ORG_ID}, {"_id": 0, "password_hash": 1})
        assert admin_user is not None
        assert str(admin_user.get("password_hash", "")).startswith("$2b$")
    finally:
        client.close()

    server_text = Path("/app/backend/server.py").read_text(encoding="utf-8")
    assert "if not verify_password(ADMIN_INITIAL_PASSWORD, existing.get(\"password_hash\", \"\"))" in server_text
    assert 'document["password_hash"] = hash_password(ADMIN_INITIAL_PASSWORD)' in server_text
