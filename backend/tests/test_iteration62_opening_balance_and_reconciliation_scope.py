import os
import uuid
from datetime import date, datetime, timedelta

import pytest
import requests
from dotenv import dotenv_values


# Modules/features under test: bank opening_balance_date contract, transaction date guard, and accounting data-flow integrity
FRONTEND_ENV = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or FRONTEND_ENV.get("REACT_APP_BACKEND_URL") or "").rstrip("/")


@pytest.fixture(scope="session")
def base_url():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL is not configured")
    return BASE_URL


@pytest.fixture(scope="session")
def session_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


def _login(base_url: str, session_client: requests.Session, username: str, password: str, organization_id: str):
    return session_client.post(
        f"{base_url}/api/auth/login",
        json={"username": username, "password": password, "organization_id": organization_id},
        timeout=40,
    )


@pytest.fixture(scope="session")
def super_admin_headers(base_url, session_client):
    response = _login(base_url, session_client, "admin", "Admin@123", "social-solidarity")
    if response.status_code != 200:
        pytest.skip(f"super admin login failed: {response.status_code} {response.text}")
    token = response.json().get("token")
    if not token:
        pytest.skip("missing super admin token")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def iteration62_seed_bank(base_url, session_client, super_admin_headers):
    opening_date = date.today().isoformat()
    bank_name = f"TEST_ITER62_BANK_{uuid.uuid4().hex[:8]}"
    create_payload = {
        "name": bank_name,
        "code": f"I62{uuid.uuid4().hex[:4].upper()}",
        "swift_code": "TESTEGCX",
        "logo_url": "",
        "color": "#123456",
        "opening_balance": 1200.0,
        "opening_balance_date": opening_date,
    }
    create_resp = session_client.post(
        f"{base_url}/api/admin/banks",
        headers=super_admin_headers,
        json=create_payload,
        timeout=60,
    )
    if create_resp.status_code != 200:
        pytest.skip(f"failed to create seed bank: {create_resp.status_code} {create_resp.text}")
    created = create_resp.json()

    state = {
        "bank_id": created["id"],
        "bank_name": created["name"],
        "opening_date": opening_date,
        "deposit_id": None,
    }
    yield state

    if state.get("deposit_id"):
        session_client.delete(
            f"{base_url}/api/banks/{state['bank_id']}/deposits/{state['deposit_id']}",
            headers=super_admin_headers,
            timeout=40,
        )
    session_client.delete(
        f"{base_url}/api/admin/banks/{state['bank_id']}",
        headers=super_admin_headers,
        timeout=40,
    )


def test_banks_list_returns_opening_balance_date(base_url, session_client, super_admin_headers, iteration62_seed_bank):
    response = session_client.get(f"{base_url}/api/banks", headers=super_admin_headers, timeout=40)
    assert response.status_code == 200, response.text
    payload = response.json()
    target = next((bank for bank in payload if bank.get("id") == iteration62_seed_bank["bank_id"]), None)
    assert target is not None
    assert target.get("opening_balance_date") == iteration62_seed_bank["opening_date"]


def test_update_opening_balance_requires_opening_balance_date(base_url, session_client, super_admin_headers, iteration62_seed_bank):
    response = session_client.put(
        f"{base_url}/api/admin/banks/{iteration62_seed_bank['bank_id']}/opening-balance",
        headers=super_admin_headers,
        json={"opening_balance": 1300},
        timeout=40,
    )
    assert response.status_code == 422


def test_update_opening_balance_accepts_iso_date_and_updates_bank(base_url, session_client, super_admin_headers, iteration62_seed_bank):
    target_date = (date.today() - timedelta(days=2)).isoformat()
    response = session_client.put(
        f"{base_url}/api/admin/banks/{iteration62_seed_bank['bank_id']}/opening-balance",
        headers=super_admin_headers,
        json={"opening_balance": 1500.75, "opening_balance_date": target_date},
        timeout=50,
    )
    assert response.status_code == 200, response.text
    bank = response.json()
    assert bank["opening_balance_date"] == target_date
    assert round(float(bank["opening_balance"]), 2) == 1500.75
    iteration62_seed_bank["opening_date"] = target_date


def test_create_bank_requires_opening_balance_date(base_url, session_client, super_admin_headers):
    response = session_client.post(
        f"{base_url}/api/admin/banks",
        headers=super_admin_headers,
        json={"name": f"TEST_ITER62_NO_DATE_{uuid.uuid4().hex[:6]}", "opening_balance": 100},
        timeout=40,
    )
    assert response.status_code == 422


def test_opening_balance_creates_journal_at_opening_date(base_url, session_client, super_admin_headers, iteration62_seed_bank):
    opening_date = iteration62_seed_bank["opening_date"]
    response = session_client.get(
        f"{base_url}/api/journal-entries",
        headers=super_admin_headers,
        params={"source_type": "opening_balance", "from_date": opening_date, "to_date": opening_date},
        timeout=80,
    )
    assert response.status_code == 200, response.text
    entries = response.json()
    target = next((entry for entry in entries if entry.get("source_id") == iteration62_seed_bank["bank_id"]), None)
    assert target is not None
    assert target.get("entry_date") == opening_date


def test_financial_transaction_before_opening_date_is_blocked(base_url, session_client, super_admin_headers, iteration62_seed_bank):
    opening_date = date.fromisoformat(iteration62_seed_bank["opening_date"])
    before_date = (opening_date - timedelta(days=1)).isoformat()
    payload = {
        "account_number": f"ACC-{uuid.uuid4().hex[:6]}",
        "deposit_number": f"DEP-{uuid.uuid4().hex[:6]}",
        "amount": 1000,
        "creation_datetime": f"{before_date}T10:00:00Z",
        "maturity_datetime": f"{(opening_date + timedelta(days=30)).isoformat()}T10:00:00Z",
        "monthly_interest_rate": 1.0,
    }
    response = session_client.post(
        f"{base_url}/api/banks/{iteration62_seed_bank['bank_id']}/deposits",
        headers=super_admin_headers,
        json=payload,
        timeout=50,
    )
    assert response.status_code == 400
    detail = response.json().get("detail", "")
    assert "No financial transaction is allowed before the Opening Balance Date" in detail


def test_financial_transaction_on_opening_date_updates_journal_ledger_trial_balance(base_url, session_client, super_admin_headers, iteration62_seed_bank):
    opening_date = iteration62_seed_bank["opening_date"]
    maturity_date = (date.fromisoformat(opening_date) + timedelta(days=40)).isoformat()
    deposit_number = f"DEP-ITER62-{uuid.uuid4().hex[:6]}"
    payload = {
        "account_number": f"ACC-ITER62-{uuid.uuid4().hex[:6]}",
        "deposit_number": deposit_number,
        "amount": 2222.0,
        "creation_datetime": f"{opening_date}T10:30:00Z",
        "maturity_datetime": f"{maturity_date}T10:30:00Z",
        "monthly_interest_rate": 1.5,
    }
    create_resp = session_client.post(
        f"{base_url}/api/banks/{iteration62_seed_bank['bank_id']}/deposits",
        headers=super_admin_headers,
        json=payload,
        timeout=60,
    )
    assert create_resp.status_code == 200, create_resp.text
    deposit = create_resp.json()
    iteration62_seed_bank["deposit_id"] = deposit["id"]
    assert deposit["deposit_number"] == deposit_number

    journal_resp = session_client.get(
        f"{base_url}/api/journal-entries",
        headers=super_admin_headers,
        params={"source_type": "deposit", "from_date": opening_date, "to_date": opening_date},
        timeout=80,
    )
    assert journal_resp.status_code == 200, journal_resp.text
    journal_entries = journal_resp.json()
    deposit_entry = next((item for item in journal_entries if item.get("source_id") == deposit["id"]), None)
    assert deposit_entry is not None
    assert deposit_entry.get("entry_date") == opening_date

    accounts_resp = session_client.get(f"{base_url}/api/chart-accounts", headers=super_admin_headers, timeout=80)
    assert accounts_resp.status_code == 200, accounts_resp.text
    bank_account = next(
        (item for item in accounts_resp.json() if item.get("system_key") == f"bank:{iteration62_seed_bank['bank_id']}"),
        None,
    )
    assert bank_account is not None

    ledger_resp = session_client.get(
        f"{base_url}/api/ledger",
        headers=super_admin_headers,
        params={"account_id": bank_account["id"], "from_date": opening_date, "to_date": opening_date},
        timeout=80,
    )
    assert ledger_resp.status_code == 200, ledger_resp.text
    ledger = ledger_resp.json()
    assert len(ledger.get("rows", [])) >= 1

    trial_resp = session_client.get(
        f"{base_url}/api/trial-balance",
        headers=super_admin_headers,
        params={"from_date": opening_date, "to_date": opening_date},
        timeout=80,
    )
    assert trial_resp.status_code == 200, trial_resp.text
    trial = trial_resp.json()
    trial_row = next((row for row in trial.get("rows", []) if row.get("account_id") == bank_account["id"]), None)
    assert trial_row is not None
    assert (float(trial_row.get("total_debit") or 0) + float(trial_row.get("total_credit") or 0)) > 0


def test_admin_data_flow_validation_is_valid(base_url, session_client, super_admin_headers):
    response = session_client.get(f"{base_url}/api/admin/data-flow-validation", headers=super_admin_headers, timeout=80)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload.get("is_valid") is True
    assert isinstance(payload.get("organizations"), list)
