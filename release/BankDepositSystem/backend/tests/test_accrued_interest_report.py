"""Regression tests for accrued-interest report API, auth guard, and setup download."""

import os
import uuid
from datetime import datetime, timezone

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


@pytest.fixture(scope="session")
def admin_headers(api_client, base_url):
    """Auth module: login and bearer header fixture for protected report APIs."""
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
        pytest.skip("No token returned from login")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def accrued_target_deposit(api_client, base_url, admin_headers):
    """Deposits module: create deterministic deposit for accrued-interest math validation."""
    unique = uuid.uuid4().hex[:8]
    payload = {
        "account_number": f"ACCR-ACC-{unique}",
        "deposit_number": f"ACCR-DEP-{unique}",
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
    assert created["deposit_number"] == payload["deposit_number"]
    assert created["amount"] == payload["amount"]
    return created


# Reports module: auth guard for protected accrued-interest endpoint
def test_accrued_interest_requires_auth(api_client, base_url):
    response = api_client.get(f"{base_url}/api/banks/agricultural-bank/accrued-interest", params={"year": 2024})
    assert response.status_code == 401
    assert "detail" in response.json()


# Reports module: deterministic accrued-interest values for required scenario
def test_accrued_interest_2024_values_match_expected(api_client, base_url, admin_headers, accrued_target_deposit):
    response = api_client.get(
        f"{base_url}/api/banks/agricultural-bank/accrued-interest",
        headers=admin_headers,
        params={"year": 2024},
    )
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["bank"]["id"] == "agricultural-bank"
    assert data["year"] == 2024
    assert isinstance(data["rows"], list)
    assert len(data["rows"]) >= 1

    target = next((row for row in data["rows"] if row["deposit_id"] == accrued_target_deposit["id"]), None)
    assert target is not None
    assert target["deposit_number"] == accrued_target_deposit["deposit_number"]
    assert target["last_payment_date"] == "2024-12-18"
    assert target["accrued_until_date"] == "2024-12-31"
    assert target["accrued_days"] == 13
    assert target["daily_interest_amount"] == 547.94
    assert target["accrued_interest_amount"] == 7123.22


# Reports module: available years should include the current year selector target
def test_accrued_interest_available_years_include_current_year(api_client, base_url, admin_headers):
    response = api_client.get(
        f"{base_url}/api/banks/agricultural-bank/accrued-interest",
        headers=admin_headers,
    )
    assert response.status_code == 200
    data = response.json()
    current_year = datetime.now(timezone.utc).year
    assert current_year in data["available_years"]
    assert max(data["available_years"]) == current_year


# Installer module: setup endpoint should return a valid Windows executable stream
def test_download_setup_returns_exe_mz_signature(api_client, base_url, admin_headers):
    response = api_client.get(f"{base_url}/api/download/setup", headers=admin_headers)
    assert response.status_code == 200
    assert response.content[:2] == b"MZ"
    disposition = response.headers.get("content-disposition", "")
    assert "BankDepositSystemSetup.exe" in disposition
