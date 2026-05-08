import os
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values


# Modules/features under test: opening-balance deposits before opening date, journals, current-year report start, opening-date update, setup installer, and data-flow validation
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
        timeout=60,
    )


@pytest.fixture(scope="session")
def admin_headers(base_url, session_client):
    response = _login(base_url, session_client, "admin", "Admin@123", "social-solidarity")
    if response.status_code != 200:
        pytest.skip(f"admin login failed: {response.status_code} {response.text}")
    token = response.json().get("token")
    if not token:
        pytest.skip("missing admin token")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture()
def iter65_seed_bank(base_url, session_client, admin_headers):
    opening_date = date.today() + timedelta(days=120)
    bank_name = f"TEST_ITER65_{uuid.uuid4().hex[:8]}"
    payload = {
        "name": bank_name,
        "code": f"I65{uuid.uuid4().hex[:4].upper()}",
        "swift_code": "TESTEGCX",
        "logo_url": "",
        "color": "#0a7c86",
        "opening_balance": 2500.0,
        "opening_balance_date": opening_date.isoformat(),
    }
    create_resp = session_client.post(f"{base_url}/api/admin/banks", headers=admin_headers, json=payload, timeout=60)
    assert create_resp.status_code == 200, create_resp.text
    created = create_resp.json()
    state = {"bank_id": created["id"], "bank_name": created["name"], "opening_date": opening_date, "deposit_ids": []}

    yield state

    for deposit_id in state["deposit_ids"]:
        session_client.delete(f"{base_url}/api/banks/{state['bank_id']}/deposits/{deposit_id}", headers=admin_headers, timeout=40)
    session_client.delete(f"{base_url}/api/admin/banks/{state['bank_id']}", headers=admin_headers, timeout=40)


def _deposit_payload(on_date: date, maturity_date: date, opening_deposit: bool = False):
    return {
        "account_number": f"ACC-I65-{uuid.uuid4().hex[:6]}",
        "deposit_number": f"DEP-I65-{uuid.uuid4().hex[:6]}",
        "amount": 4000.0,
        "creation_datetime": f"{on_date.isoformat()}T09:15:00Z",
        "maturity_datetime": f"{maturity_date.isoformat()}T09:15:00Z",
        "monthly_interest_rate": 1.2,
        "is_opening_balance_deposit": opening_deposit,
    }


def test_opening_balance_deposit_rules_and_reporting(base_url, session_client, admin_headers, iter65_seed_bank):
    bank_id = iter65_seed_bank["bank_id"]
    opening_date = iter65_seed_bank["opening_date"]

    before_opening = opening_date - timedelta(days=10)
    after_opening = opening_date + timedelta(days=45)

    # 1) Normal deposit before opening date should be rejected
    normal_payload = _deposit_payload(before_opening, after_opening, opening_deposit=False)
    normal_resp = session_client.post(f"{base_url}/api/banks/{bank_id}/deposits", headers=admin_headers, json=normal_payload, timeout=60)
    assert normal_resp.status_code == 400, normal_resp.text
    normal_detail = normal_resp.json().get("detail", "")
    assert "قبل تاريخ الرصيد الافتتاحي" in normal_detail

    # 2) Opening-balance deposit before opening date should be accepted
    opening_payload = _deposit_payload(before_opening, after_opening, opening_deposit=True)
    opening_resp = session_client.post(f"{base_url}/api/banks/{bank_id}/deposits", headers=admin_headers, json=opening_payload, timeout=60)
    assert opening_resp.status_code == 200, opening_resp.text
    deposit = opening_resp.json()
    iter65_seed_bank["deposit_ids"].append(deposit["id"])

    # 3) Response contract
    assert deposit.get("is_opening_balance_deposit") is True
    assert str(deposit.get("accounting_start_datetime", "")).startswith(opening_date.isoformat())
    assert str(deposit.get("creation_datetime", "")).startswith(before_opening.isoformat())

    # 4) Journal entry contract for opening-balance deposit
    journal_resp = session_client.get(
        f"{base_url}/api/journal-entries",
        headers=admin_headers,
        params={"source_type": "deposit", "from_date": opening_date.isoformat(), "to_date": opening_date.isoformat()},
        timeout=90,
    )
    assert journal_resp.status_code == 200, journal_resp.text
    deposit_entry = next((entry for entry in journal_resp.json() if entry.get("source_id") == deposit["id"]), None)
    assert deposit_entry is not None
    assert deposit_entry.get("entry_date") == opening_date.isoformat()
    line_names = [line.get("account_name") for line in deposit_entry.get("lines", [])]
    assert "ودائع لأجل" in line_names
    assert "رصيد افتتاحي" in line_names
    assert "البنك" not in line_names

    # 5) Current-year report should start from accounting_start_datetime (opening date), not old creation date
    report_resp = session_client.get(
        f"{base_url}/api/banks/{bank_id}/reports/current-year",
        headers=admin_headers,
        params={"deposit_id": deposit["id"]},
        timeout=90,
    )
    assert report_resp.status_code == 200, report_resp.text
    report = report_resp.json()
    report_deposit = report.get("deposit", {})
    assert report_deposit.get("is_opening_balance_deposit") is True
    assert str(report_deposit.get("accounting_start_datetime", "")).startswith(opening_date.isoformat())

    rows = report.get("rows", [])
    assert isinstance(rows, list) and len(rows) == 12
    months_before_opening = [row for row in rows if int(row.get("month_number", 0)) < opening_date.month]
    assert all(float(row.get("interest_amount") or 0) == 0 for row in months_before_opening)
    positive_months = [int(row.get("month_number")) for row in rows if float(row.get("interest_amount") or 0) > 0]
    assert positive_months, "Expected at least one positive month in current-year report"
    assert min(positive_months) >= opening_date.month

    # 6) Updating opening balance date should not be blocked by opening-balance deposits with old creation date
    updated_opening = opening_date + timedelta(days=5)
    update_resp = session_client.put(
        f"{base_url}/api/admin/banks/{bank_id}/opening-balance",
        headers=admin_headers,
        json={"opening_balance": 2600.0, "opening_balance_date": updated_opening.isoformat()},
        timeout=60,
    )
    assert update_resp.status_code == 200, update_resp.text
    updated_bank = update_resp.json()
    assert updated_bank.get("opening_balance_date") == updated_opening.isoformat()


def test_data_flow_validation_and_installer_presence(base_url, session_client, admin_headers):
    # 7) Data flow validation endpoint should be valid
    validation_resp = session_client.get(f"{base_url}/api/admin/data-flow-validation", headers=admin_headers, timeout=90)
    assert validation_resp.status_code == 200, validation_resp.text
    validation_payload = validation_resp.json()
    assert validation_payload.get("is_valid") is True
    assert isinstance(validation_payload.get("organizations"), list)

    # 8) Installer exists and download endpoint is reachable
    installer_path = Path("/app/dist/BankDepositSystemSetup.exe")
    assert installer_path.exists() is True
    assert installer_path.stat().st_size > 0

    setup_resp = session_client.get(f"{base_url}/api/download/setup", headers=admin_headers, timeout=90)
    assert setup_resp.status_code == 200, setup_resp.text
    content_disposition = setup_resp.headers.get("content-disposition", "")
    assert "BankDepositSystemSetup.exe" in content_disposition
