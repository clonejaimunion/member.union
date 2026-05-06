import os
import uuid
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient


# Modules/features under test: ledger all/single account period filtering, totals, account scope, data-flow validity, and setup installer presence
FRONTEND_ENV = dotenv_values("/app/frontend/.env")
BACKEND_ENV = dotenv_values("/app/backend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or FRONTEND_ENV.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
MONGO_URL = (BACKEND_ENV.get("MONGO_URL") or "").strip('"')
DB_NAME = (BACKEND_ENV.get("DB_NAME") or "").strip('"')

ITER_PREFIX = f"TEST-ITER66-{uuid.uuid4().hex[:8]}"


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
    login = requests.post(
        f"{base_url}/api/auth/login",
        json={"username": "admin", "password": "Admin@123", "organization_id": "social-solidarity"},
        headers=_headers(),
        timeout=60,
    )
    if login.status_code != 200:
        pytest.skip(f"admin login failed: {login.status_code} {login.text}")
    token = login.json().get("token")
    if not token:
        pytest.skip("admin token missing")
    return token


@pytest.fixture(scope="session", autouse=True)
def cleanup_iter66_data():
    yield
    if not MONGO_URL or not DB_NAME:
        return
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    db.journal_entries.delete_many({"reference": {"$regex": f"^{ITER_PREFIX}"}})
    client.close()


def _create_manual_entry(base_url: str, token: str, entry_date: str, amount: float, reference_suffix: str):
    payload = {
        "entry_date": entry_date,
        "description": f"{ITER_PREFIX} {reference_suffix}",
        "reference": f"{ITER_PREFIX}-{reference_suffix}",
        "lines": [
            {"account_name": "البنك", "debit": amount, "credit": 0},
            {"account_name": "الإيرادات", "debit": 0, "credit": amount},
        ],
    }
    return requests.post(f"{base_url}/api/journal-entries", json=payload, headers=_headers(token), timeout=60)


def _ledger(base_url: str, token: str, account_id: str, from_date: str, to_date: str):
    return requests.get(
        f"{base_url}/api/ledger",
        params={"account_id": account_id, "from_date": from_date, "to_date": to_date},
        headers=_headers(token),
        timeout=90,
    )


def _extract_debit_account_id(entry_response_json: dict) -> str:
    lines = entry_response_json.get("lines") or []
    debit_line = next((line for line in lines if float(line.get("debit") or 0) > 0), None)
    assert debit_line is not None, "Expected a debit line in created journal entry"
    account_id = debit_line.get("account_id")
    assert isinstance(account_id, str) and account_id
    return account_id


def test_ledger_all_mode_period_scope_and_totals(base_url, admin_token):
    before_resp = _create_manual_entry(base_url, admin_token, "2099-06-30", 999.0, "BEFORE")
    assert before_resp.status_code == 200, before_resp.text

    inside_1_resp = _create_manual_entry(base_url, admin_token, "2099-07-10", 100.0, "INSIDE-1")
    assert inside_1_resp.status_code == 200, inside_1_resp.text

    inside_2_resp = _create_manual_entry(base_url, admin_token, "2099-07-20", 250.0, "INSIDE-2")
    assert inside_2_resp.status_code == 200, inside_2_resp.text

    response = _ledger(base_url, admin_token, "all", "2099-07-01", "2099-07-31")
    assert response.status_code == 200, response.text
    body = response.json()

    assert body.get("account_scope") == "all"
    assert body.get("account") is None
    rows = body.get("rows") or []
    assert len(rows) >= 4
    assert all("2099-07-01" <= row.get("entry_date", "") <= "2099-07-31" for row in rows)

    target_rows = [row for row in rows if (row.get("reference") or "").startswith(ITER_PREFIX)]
    assert len(target_rows) == 4
    assert all(isinstance(row.get("account_code"), str) and row.get("account_code") for row in target_rows)
    assert all(isinstance(row.get("account_name"), str) and row.get("account_name") for row in target_rows)

    expected_total_debit = round(sum(float(row.get("debit") or 0) for row in rows), 2)
    expected_total_credit = round(sum(float(row.get("credit") or 0) for row in rows), 2)
    assert round(float(body.get("total_debit") or 0), 2) == expected_total_debit
    assert round(float(body.get("total_credit") or 0), 2) == expected_total_credit


def test_ledger_single_account_respects_period_without_carrying_previous(base_url, admin_token):
    inside_resp = _create_manual_entry(base_url, admin_token, "2099-07-11", 123.0, "SINGLE-INSIDE")
    assert inside_resp.status_code == 200, inside_resp.text
    bank_account_id = _extract_debit_account_id(inside_resp.json())

    before_outside_resp = _ledger(base_url, admin_token, bank_account_id, "2099-07-01", "2099-07-31")
    assert before_outside_resp.status_code == 200, before_outside_resp.text
    before_outside_payload = before_outside_resp.json()
    before_inside_rows = [row for row in (before_outside_payload.get("rows") or []) if (row.get("reference") or "").endswith("SINGLE-INSIDE")]
    assert len(before_inside_rows) == 1
    inside_balance_before_outside = round(float(before_inside_rows[0].get("balance") or 0), 2)
    period_total_debit_before = round(float(before_outside_payload.get("total_debit") or 0), 2)
    period_total_credit_before = round(float(before_outside_payload.get("total_credit") or 0), 2)

    before_resp = _create_manual_entry(base_url, admin_token, "2099-06-28", 777.0, "SINGLE-BEFORE")
    assert before_resp.status_code == 200, before_resp.text

    result_resp = _ledger(base_url, admin_token, bank_account_id, "2099-07-01", "2099-07-31")
    assert result_resp.status_code == 200, result_resp.text
    result_payload = result_resp.json()

    assert result_payload.get("account_scope") == "single"
    assert isinstance(result_payload.get("account"), dict)
    rows = result_payload.get("rows") or []
    assert all("2099-07-01" <= row.get("entry_date", "") <= "2099-07-31" for row in rows)

    inside_rows = [row for row in rows if (row.get("reference") or "").endswith("SINGLE-INSIDE")]
    before_rows = [row for row in rows if (row.get("reference") or "").endswith("SINGLE-BEFORE")]
    assert len(inside_rows) == 1
    assert len(before_rows) == 0

    first_target_balance = round(float(inside_rows[0].get("balance") or 0), 2)
    assert first_target_balance == inside_balance_before_outside
    assert round(float(result_payload.get("total_debit") or 0), 2) == period_total_debit_before
    assert round(float(result_payload.get("total_credit") or 0), 2) == period_total_credit_before


def test_data_flow_validation_true_and_setup_binary_exists(base_url, admin_token):
    validation_resp = requests.get(f"{base_url}/api/admin/data-flow-validation", headers=_headers(admin_token), timeout=90)
    assert validation_resp.status_code == 200, validation_resp.text
    validation_body = validation_resp.json()
    assert validation_body.get("is_valid") is True
    assert isinstance(validation_body.get("organizations"), list)

    installer_path = Path("/app/dist/BankDepositSystemSetup.exe")
    assert installer_path.exists() is True
    assert installer_path.stat().st_size > 0
