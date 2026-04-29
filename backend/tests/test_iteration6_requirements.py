"""Regression coverage for leap/year-day math, admin-bank access, and setup binary validity."""

import os
import uuid

import pytest
import requests


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Admin@123"


@pytest.fixture(scope="session")
def base_url():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL is not set")
    return BASE_URL.rstrip("/")


@pytest.fixture(scope="session")
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


# Auth module: admin login and bearer token fixture
@pytest.fixture(scope="session")
def admin_headers(api_client, base_url):
    login = api_client.post(
        f"{base_url}/api/auth/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )
    if login.status_code != 200:
        pytest.skip(f"Admin login failed: {login.status_code}")
    data = login.json()
    token = data.get("token")
    if not token:
        if data.get("requires_2fa"):
            pytest.skip("Admin account currently requires 2FA; skipping auth-required API tests")
        pytest.skip("No token returned from admin login")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _create_data_entry_user(api_client, base_url, admin_headers):
    username = f"TEST_bank_perm_{uuid.uuid4().hex[:8]}"
    payload = {
        "username": username,
        "password": "UserPass@123",
        "permissions": {
            "enter_deposits": True,
            "view_reports": True,
            "edit_deposits": False,
            "manage_users": False,
        },
        "is_active": True,
    }
    create_user = api_client.post(f"{base_url}/api/admin/users", headers=admin_headers, json=payload)
    assert create_user.status_code == 200, create_user.text

    login = api_client.post(
        f"{base_url}/api/auth/login",
        json={"username": username, "password": payload["password"]},
    )
    assert login.status_code == 200, login.text
    token = login.json().get("token")
    assert isinstance(token, str) and token
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# Reports module: current-year report must use real month length (Jan 2026 = 31)
def test_current_year_uses_real_month_days_january_2026(api_client, base_url, admin_headers):
    unique = uuid.uuid4().hex[:8]
    payload = {
        "account_number": f"TEST-DAYS-ACC-{unique}",
        "deposit_number": f"TEST-DAYS-DEP-{unique}",
        "amount": 365000,
        "monthly_interest_rate": 10,
        "creation_datetime": "2026-01-01T00:00:00+00:00",
        "maturity_datetime": "2027-01-01T00:00:00+00:00",
    }
    create = api_client.post(
        f"{base_url}/api/banks/banque-misr/deposits",
        headers=admin_headers,
        json=payload,
    )
    assert create.status_code == 200, create.text
    created = create.json()
    assert created["deposit_number"] == payload["deposit_number"]

    report = api_client.get(
        f"{base_url}/api/banks/banque-misr/reports/current-year",
        headers=admin_headers,
        params={"deposit_id": created["id"]},
    )
    assert report.status_code == 200, report.text
    report_data = report.json()
    assert report_data["year"] == 2026
    january = next((row for row in report_data["rows"] if row["month_number"] == 1), None)
    assert january is not None
    assert january["active_days"] == 31
    assert january["interest_amount"] == 3100


# Accrued module: leap-year daily interest must still divide by fixed 365 days
def test_accrued_2024_daily_interest_uses_fixed_365(api_client, base_url, admin_headers):
    unique = uuid.uuid4().hex[:8]
    payload = {
        "account_number": f"TEST-LEAP-ACC-{unique}",
        "deposit_number": f"TEST-LEAP-DEP-{unique}",
        "amount": 1_000_000,
        "monthly_interest_rate": 20,
        "creation_datetime": "2024-01-18T00:00:00+00:00",
        "maturity_datetime": "2027-01-18T00:00:00+00:00",
    }
    create = api_client.post(
        f"{base_url}/api/banks/agricultural-bank/deposits",
        headers=admin_headers,
        json=payload,
    )
    assert create.status_code == 200, create.text
    created = create.json()

    report = api_client.get(
        f"{base_url}/api/banks/agricultural-bank/accrued-interest",
        headers=admin_headers,
        params={"year": 2024, "deposit_id": created["id"]},
    )
    assert report.status_code == 200, report.text
    data = report.json()
    assert data["year"] == 2024
    assert len(data["rows"]) == 1
    row = data["rows"][0]
    assert row["daily_interest_amount"] == 547.94


# Accrued module: required scenario (18/01 link date) should produce 13 days due until 31/12/2024
def test_accrued_2024_linked_on_18_jan_has_13_days_until_year_end(api_client, base_url, admin_headers):
    unique = uuid.uuid4().hex[:8]
    payload = {
        "account_number": f"TEST-LEAP2-ACC-{unique}",
        "deposit_number": f"TEST-LEAP2-DEP-{unique}",
        "amount": 1_000_000,
        "monthly_interest_rate": 20,
        "creation_datetime": "2024-01-18T00:00:00+00:00",
        "maturity_datetime": "2027-01-18T00:00:00+00:00",
    }
    create = api_client.post(
        f"{base_url}/api/banks/agricultural-bank/deposits",
        headers=admin_headers,
        json=payload,
    )
    assert create.status_code == 200, create.text
    created = create.json()

    report = api_client.get(
        f"{base_url}/api/banks/agricultural-bank/accrued-interest",
        headers=admin_headers,
        params={"year": 2024, "deposit_id": created["id"]},
    )
    assert report.status_code == 200, report.text
    row = report.json()["rows"][0]
    assert row["last_payment_date"] == "2024-12-18"
    assert row["accrued_until_date"] == "2024-12-31"
    assert row["accrued_days"] == 13
    assert row["accrued_interest_amount"] == 7123.22


# Admin module: creating banks must be admin-only
def test_admin_can_create_bank(api_client, base_url, admin_headers):
    unique = uuid.uuid4().hex[:6].upper()
    payload = {
        "name": f"TEST BANK ITER6 {unique}",
        "code": f"TB{unique}",
        "logo_url": "",
        "color": "#0f172a",
    }
    create = api_client.post(f"{base_url}/api/admin/banks", headers=admin_headers, json=payload)
    assert create.status_code == 200, create.text
    bank = create.json()
    assert bank["name"] == payload["name"]
    assert bank["code"] == payload["code"]


# Admin module: non-admin user should be forbidden from creating banks
def test_non_admin_cannot_create_bank(api_client, base_url, admin_headers):
    user_headers = _create_data_entry_user(api_client, base_url, admin_headers)
    payload = {
        "name": f"TEST NONADMIN BANK {uuid.uuid4().hex[:6]}",
        "code": f"NA{uuid.uuid4().hex[:4].upper()}",
        "logo_url": "",
        "color": "#111827",
    }
    create = api_client.post(f"{base_url}/api/admin/banks", headers=user_headers, json=payload)
    assert create.status_code == 403
    assert "detail" in create.json()


# Banks module: newly created admin bank should appear in /api/banks list
def test_created_bank_appears_in_banks_listing(api_client, base_url, admin_headers):
    unique = uuid.uuid4().hex[:6].upper()
    payload = {
        "name": f"TEST BANK VISIBLE {unique}",
        "code": f"TV{unique}",
        "logo_url": "",
        "color": "#1e293b",
    }
    create = api_client.post(f"{base_url}/api/admin/banks", headers=admin_headers, json=payload)
    assert create.status_code == 200, create.text
    created = create.json()
    assert isinstance(created.get("id"), str) and created["id"]

    banks = api_client.get(f"{base_url}/api/banks", headers=admin_headers)
    assert banks.status_code == 200
    bank_list = banks.json()
    matched = [bank for bank in bank_list if bank["id"] == created["id"]]
    assert len(matched) == 1
    assert matched[0]["name"] == payload["name"]


# Installer module: setup endpoint stream and local file must both be valid MZ executable
def test_setup_exe_mz_signature_endpoint_and_local_file(api_client, base_url, admin_headers):
    endpoint_file = api_client.get(f"{base_url}/api/download/setup", headers=admin_headers)
    assert endpoint_file.status_code == 200
    assert endpoint_file.content[:2] == b"MZ"

    with open("/app/dist/BankDepositSystemSetup.exe", "rb") as setup_file:
        assert setup_file.read(2) == b"MZ"
