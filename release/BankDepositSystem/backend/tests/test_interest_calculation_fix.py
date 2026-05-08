"""Regression tests for annual-interest daily prorating fix (yearly ÷ 365)."""

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


@pytest.fixture(scope="session")
def admin_headers(api_client, base_url):
    login = api_client.post(
        f"{base_url}/api/auth/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )
    if login.status_code != 200:
        pytest.skip(f"Admin login failed: {login.status_code}")
    token = login.json().get("token")
    if not token:
        pytest.skip("No admin token returned")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def calc_deposit(api_client, base_url, admin_headers):
    unique = uuid.uuid4().hex[:8]
    payload = {
        "account_number": f"CALC-ACC-{unique}",
        "deposit_number": f"CALC-DEP-{unique}",
        "amount": 1000000,
        "creation_datetime": "2026-01-01T00:00:00+00:00",
        "maturity_datetime": "2027-01-01T00:00:00+00:00",
        "monthly_interest_rate": 20,
    }
    create = api_client.post(
        f"{base_url}/api/banks/banque-misr/deposits",
        headers=admin_headers,
        json=payload,
    )
    assert create.status_code == 200, create.text
    created = create.json()
    assert created["deposit_number"] == payload["deposit_number"]
    assert created["amount"] == payload["amount"]
    assert created["monthly_interest_rate"] == payload["monthly_interest_rate"]
    return created


# Admin auth sanity coverage for this regression scope
def test_admin_login_success(api_client, base_url):
    response = api_client.post(
        f"{base_url}/api/auth/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data.get("token"), str)
    assert data["user"]["username"] == ADMIN_USERNAME


# Deposit registration coverage with fixed annual-interest semantics
def test_create_deposit_annual_rate_payload(api_client, base_url, admin_headers, calc_deposit):
    fetched = api_client.get(
        f"{base_url}/api/banks/banque-misr/deposits",
        headers=admin_headers,
    )
    assert fetched.status_code == 200
    deposits = fetched.json()
    matched = [item for item in deposits if item["id"] == calc_deposit["id"]]
    assert len(matched) == 1
    assert matched[0]["monthly_interest_rate"] == 20


# Current-year report math: annual = 200000 and January = 30 days * floor(200000/365,2)
def test_current_year_report_matches_requested_math(api_client, base_url, admin_headers, calc_deposit):
    report = api_client.get(
        f"{base_url}/api/banks/banque-misr/reports/current-year",
        headers=admin_headers,
        params={"deposit_id": calc_deposit["id"]},
    )
    assert report.status_code == 200, report.text
    data = report.json()

    assert data["deposit"]["id"] == calc_deposit["id"]
    assert data["monthly_interest_amount"] == 200000

    january = next((row for row in data["rows"] if row["month_number"] == 1), None)
    assert january is not None
    assert january["active_days"] == 30
    assert january["interest_amount"] == 16438.2


# Statement APIs should expose annual-interest values (not legacy monthly formula)
def test_statements_use_annual_interest_not_legacy_monthly(api_client, base_url, admin_headers, calc_deposit):
    detailed = api_client.get(
        f"{base_url}/api/banks/banque-misr/statements/detailed",
        headers=admin_headers,
    )
    assert detailed.status_code == 200
    detailed_rows = detailed.json()["rows"]
    detailed_row = next((row for row in detailed_rows if row["deposit_id"] == calc_deposit["id"]), None)
    assert detailed_row is not None
    assert detailed_row["monthly_interest_amount"] == 200000

    volume = api_client.get(
        f"{base_url}/api/banks/banque-misr/statements/volume",
        headers=admin_headers,
    )
    assert volume.status_code == 200
    volume_rows = volume.json()["rows"]
    volume_row = next((row for row in volume_rows if row["deposit_id"] == calc_deposit["id"]), None)
    assert volume_row is not None
    assert volume_row["monthly_interest_amount"] == 200000
