import os
import uuid

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient


# Modules/features under test: journal date filter, ledger period scope (single/all), trial balance opening logic, and reconciliation formula
FRONTEND_ENV = dotenv_values("/app/frontend/.env")
BACKEND_ENV = dotenv_values("/app/backend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or FRONTEND_ENV.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
MONGO_URL = (BACKEND_ENV.get("MONGO_URL") or "").strip('"')
DB_NAME = (BACKEND_ENV.get("DB_NAME") or "").strip('"')

ITER_PREFIX = f"TEST-ITER67-{uuid.uuid4().hex[:8]}"


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
    token = response.json().get("token")
    if not token:
        pytest.skip("admin token missing")
    return token


@pytest.fixture(scope="session", autouse=True)
def cleanup_iter67_data():
    yield
    if not MONGO_URL or not DB_NAME:
        return
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    db.journal_entries.delete_many({"reference": {"$regex": f"^{ITER_PREFIX}"}})
    db.chart_accounts.delete_many({"code": {"$regex": f"^{ITER_PREFIX}"}})
    client.close()


def _create_chart_account(base_url: str, token: str) -> dict:
    payload = {
        "code": f"{ITER_PREFIX}-A1",
        "name": f"{ITER_PREFIX} أصل اختباري",
        "account_type": "asset",
        "nature": "debit",
        "is_postable": True,
        "is_active": True,
        "opening_balance": 0,
    }
    response = requests.post(f"{base_url}/api/chart-accounts", json=payload, headers=_headers(token), timeout=60)
    assert response.status_code == 200, response.text
    return response.json()


def _create_manual_entry(base_url: str, token: str, *, account_name: str, entry_date: str, amount: float, ref_suffix: str):
    payload = {
        "entry_date": entry_date,
        "description": f"{ITER_PREFIX} {ref_suffix}",
        "reference": f"{ITER_PREFIX}-{ref_suffix}",
        "lines": [
            {"account_name": account_name, "debit": amount, "credit": 0},
            {"account_name": "الإيرادات", "debit": 0, "credit": amount},
        ],
    }
    return requests.post(f"{base_url}/api/journal-entries", json=payload, headers=_headers(token), timeout=60)


@pytest.fixture(scope="session")
def seeded_period_data(base_url, admin_token):
    account = _create_chart_account(base_url, admin_token)
    account_name = account["name"]

    before_entry = _create_manual_entry(base_url, admin_token, account_name=account_name, entry_date="2098-06-30", amount=100.0, ref_suffix="BEFORE")
    inside_1 = _create_manual_entry(base_url, admin_token, account_name=account_name, entry_date="2098-07-10", amount=50.0, ref_suffix="INSIDE-1")
    inside_2 = _create_manual_entry(base_url, admin_token, account_name=account_name, entry_date="2098-07-15", amount=20.0, ref_suffix="INSIDE-2")
    after_entry = _create_manual_entry(base_url, admin_token, account_name=account_name, entry_date="2098-08-01", amount=30.0, ref_suffix="AFTER")

    assert before_entry.status_code == 200, before_entry.text
    assert inside_1.status_code == 200, inside_1.text
    assert inside_2.status_code == 200, inside_2.text
    assert after_entry.status_code == 200, after_entry.text

    return {
        "account": account,
        "from_date": "2098-07-01",
        "to_date": "2098-07-31",
        "opening_expected": 100.0,
        "period_debit_expected": 70.0,
        "inside_refs": {f"{ITER_PREFIX}-INSIDE-1", f"{ITER_PREFIX}-INSIDE-2"},
        "outside_refs": {f"{ITER_PREFIX}-BEFORE", f"{ITER_PREFIX}-AFTER"},
    }


def test_journal_entries_returns_only_period_rows(base_url, admin_token, seeded_period_data):
    response = requests.get(
        f"{base_url}/api/journal-entries",
        params={"from_date": seeded_period_data["from_date"], "to_date": seeded_period_data["to_date"]},
        headers=_headers(admin_token),
        timeout=60,
    )
    assert response.status_code == 200, response.text
    rows = response.json()
    target_rows = [row for row in rows if str(row.get("reference") or "").startswith(ITER_PREFIX)]

    assert len(target_rows) == 2
    assert {row.get("reference") for row in target_rows} == seeded_period_data["inside_refs"]
    assert all(seeded_period_data["from_date"] <= row.get("entry_date", "") <= seeded_period_data["to_date"] for row in target_rows)


def test_ledger_single_period_opening_and_closing_formula(base_url, admin_token, seeded_period_data):
    account_id = seeded_period_data["account"]["id"]
    response = requests.get(
        f"{base_url}/api/ledger",
        params={"account_id": account_id, "from_date": seeded_period_data["from_date"], "to_date": seeded_period_data["to_date"]},
        headers=_headers(admin_token),
        timeout=90,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    rows = body.get("rows") or []
    target_rows = [row for row in rows if str(row.get("reference") or "").startswith(ITER_PREFIX)]

    assert body.get("account_scope") == "single"
    assert round(float(body.get("opening_balance") or 0), 2) == seeded_period_data["opening_expected"]
    assert round(float(body.get("total_debit") or 0), 2) >= seeded_period_data["period_debit_expected"]
    assert all(seeded_period_data["from_date"] <= row.get("entry_date", "") <= seeded_period_data["to_date"] for row in target_rows)
    assert {row.get("reference") for row in target_rows} == seeded_period_data["inside_refs"]

    opening = round(float(body.get("opening_balance") or 0), 2)
    total_debit = round(float(body.get("total_debit") or 0), 2)
    total_credit = round(float(body.get("total_credit") or 0), 2)
    closing = round(float(body.get("closing_balance") or 0), 2)
    assert closing == round(opening + total_debit - total_credit, 2)


def test_ledger_all_returns_period_rows_with_account_columns(base_url, admin_token, seeded_period_data):
    response = requests.get(
        f"{base_url}/api/ledger",
        params={"account_id": "all", "from_date": seeded_period_data["from_date"], "to_date": seeded_period_data["to_date"]},
        headers=_headers(admin_token),
        timeout=90,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    rows = body.get("rows") or []
    target_rows = [row for row in rows if str(row.get("reference") or "").startswith(ITER_PREFIX)]

    assert body.get("account_scope") == "all"
    assert body.get("account") is None
    assert len(target_rows) == 4
    assert all(seeded_period_data["from_date"] <= row.get("entry_date", "") <= seeded_period_data["to_date"] for row in target_rows)
    assert all(isinstance(row.get("account_code"), str) and row.get("account_code") for row in target_rows)
    assert all(isinstance(row.get("account_name"), str) and row.get("account_name") for row in target_rows)

    opening = round(float(body.get("opening_balance") or 0), 2)
    total_debit = round(float(body.get("total_debit") or 0), 2)
    total_credit = round(float(body.get("total_credit") or 0), 2)
    closing = round(float(body.get("closing_balance") or 0), 2)
    assert closing == round(opening + total_debit - total_credit, 2)


def test_trial_balance_opening_includes_prior_period_movement(base_url, admin_token, seeded_period_data):
    response = requests.get(
        f"{base_url}/api/trial-balance",
        params={"from_date": seeded_period_data["from_date"], "to_date": seeded_period_data["to_date"]},
        headers=_headers(admin_token),
        timeout=90,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    rows = body.get("rows") or []
    target = next((row for row in rows if row.get("account_id") == seeded_period_data["account"]["id"]), None)

    assert body.get("is_balanced") is True
    assert target is not None
    assert round(float(target.get("total_debit") or 0), 2) == seeded_period_data["period_debit_expected"]
    assert round(float(target.get("total_credit") or 0), 2) == 0.0
    assert round(float(target.get("opening_balance") or 0), 2) == seeded_period_data["opening_expected"]


def test_reconciliation_balance_formula_matches_breakdown(base_url, admin_token):
    response = requests.get(
        f"{base_url}/api/banks/industrial-development/reconciliation-balance",
        params={"year": 2098, "month": 7, "period_label": "يوليو 2098"},
        headers=_headers(admin_token),
        timeout=90,
    )
    assert response.status_code == 200, response.text
    data = response.json()

    opening = round(float(data.get("opening_balance") or 0), 2)
    monthly_revenues = round(float(data.get("monthly_revenues") or 0), 2)
    deposit_settlements = round(float(data.get("deposit_settlements") or 0), 2)
    monthly_expenses = round(float(data.get("monthly_expenses") or 0), 2)
    bank_expenses = round(float(data.get("bank_expenses") or 0), 2)
    checks_not_presented = round(float(data.get("checks_not_presented") or 0), 2)
    checks_under_collection = round(float(data.get("checks_under_collection") or 0), 2)

    expected_book = round(opening + monthly_revenues + deposit_settlements - monthly_expenses - bank_expenses, 2)
    expected_reconciliation = round(expected_book + checks_not_presented - checks_under_collection, 2)

    assert round(float(data.get("book_balance") or 0), 2) == expected_book
    assert round(float(data.get("reconciliation_balance") or 0), 2) == expected_reconciliation


def test_data_flow_validation_is_valid_true(base_url, admin_token):
    response = requests.get(f"{base_url}/api/admin/data-flow-validation", headers=_headers(admin_token), timeout=90)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("is_valid") is True
    assert isinstance(body.get("organizations"), list)