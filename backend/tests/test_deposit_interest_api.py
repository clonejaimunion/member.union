"""API tests for bank selection, deposit registration, and yearly reports."""

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Admin@123"


@pytest.fixture(scope="session")
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="session")
def base_url():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL is not set")
    return BASE_URL.rstrip("/")


@pytest.fixture(scope="session")
def admin_headers(api_client, base_url):
    login = api_client.post(
        f"{base_url}/api/auth/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )
    if login.status_code != 200:
        pytest.skip("Admin login failed; authenticated API tests skipped")
    token = login.json().get("token")
    if not token:
        pytest.skip("No auth token returned from login")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _new_deposit_payload(prefix: str = "TEST"):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    maturity = now + timedelta(days=370)
    unique = uuid.uuid4().hex[:8]
    return {
        "account_number": f"{prefix}-ACC-{unique}",
        "deposit_number": f"{prefix}-DEP-{unique}",
        "amount": 100000,
        "creation_datetime": now.isoformat(),
        "maturity_datetime": maturity.isoformat(),
        "monthly_interest_rate": 1.25,
    }


# Bank listing and selection coverage
def test_get_banks_shows_three_expected_banks(api_client, base_url, admin_headers):
    response = api_client.get(f"{base_url}/api/banks", headers=admin_headers)
    assert response.status_code == 200

    banks = response.json()
    assert len(banks) == 3
    ids = {bank["id"] for bank in banks}
    assert ids == {"industrial-development", "banque-misr", "agricultural-bank"}


# Deposit registration and persistence coverage
def test_create_deposit_and_verify_latest_for_banque_misr(api_client, base_url, admin_headers):
    payload = _new_deposit_payload("TEST_BM")
    create = api_client.post(f"{base_url}/api/banks/banque-misr/deposits", headers=admin_headers, json=payload)
    assert create.status_code == 200

    created = create.json()
    assert created["bank_id"] == "banque-misr"
    assert created["account_number"] == payload["account_number"]

    latest = api_client.get(f"{base_url}/api/banks/banque-misr/deposits/latest", headers=admin_headers)
    assert latest.status_code == 200
    latest_data = latest.json()
    assert latest_data["id"] == created["id"]
    assert latest_data["deposit_number"] == payload["deposit_number"]


# Bank data isolation coverage
def test_data_isolation_between_banks(api_client, base_url, admin_headers):
    agri_payload = _new_deposit_payload("TEST_AGRI")
    agri_create = api_client.post(f"{base_url}/api/banks/agricultural-bank/deposits", headers=admin_headers, json=agri_payload)
    assert agri_create.status_code == 200
    agri_created_id = agri_create.json()["id"]

    industrial_payload = _new_deposit_payload("TEST_IDB")
    industrial_create = api_client.post(f"{base_url}/api/banks/industrial-development/deposits", headers=admin_headers, json=industrial_payload)
    assert industrial_create.status_code == 200

    misr_deposits = api_client.get(f"{base_url}/api/banks/banque-misr/deposits", headers=admin_headers)
    assert misr_deposits.status_code == 200
    misr_ids = {item["id"] for item in misr_deposits.json()}
    assert agri_created_id not in misr_ids


# Current-year report structure and totals coverage
def test_current_year_report_has_12_rows_and_summary(api_client, base_url, admin_headers):
    latest = api_client.get(f"{base_url}/api/banks/banque-misr/deposits/latest", headers=admin_headers)
    assert latest.status_code == 200
    deposit = latest.json()

    report = api_client.get(
        f"{base_url}/api/banks/banque-misr/reports/current-year",
        headers=admin_headers,
        params={"deposit_id": deposit["id"]},
    )
    assert report.status_code == 200

    data = report.json()
    assert data["report_type"] == "current-year"
    assert data["deposit"]["id"] == deposit["id"]
    assert len(data["rows"]) == 12
    assert isinstance(data["total_interest"], (int, float))


# Previous-year report structure coverage
def test_previous_year_report_has_12_rows_and_summary(api_client, base_url, admin_headers):
    latest = api_client.get(f"{base_url}/api/banks/banque-misr/deposits/latest", headers=admin_headers)
    assert latest.status_code == 200
    deposit = latest.json()

    report = api_client.get(
        f"{base_url}/api/banks/banque-misr/reports/previous-year",
        headers=admin_headers,
        params={"deposit_id": deposit["id"]},
    )
    assert report.status_code == 200

    data = report.json()
    assert data["report_type"] == "previous-year"
    assert len(data["rows"]) == 12
    assert data["deposit"]["id"] == deposit["id"]


# Date validation and user-facing error coverage
def test_rejects_maturity_before_creation_with_arabic_message(api_client, base_url, admin_headers):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    invalid_payload = {
        "account_number": f"TEST-INV-{uuid.uuid4().hex[:6]}",
        "deposit_number": f"TEST-INV-{uuid.uuid4().hex[:6]}",
        "amount": 50000,
        "creation_datetime": now.isoformat(),
        "maturity_datetime": (now - timedelta(days=1)).isoformat(),
        "monthly_interest_rate": 1.1,
    }

    response = api_client.post(f"{base_url}/api/banks/banque-misr/deposits", headers=admin_headers, json=invalid_payload)
    assert response.status_code == 400
    assert "تاريخ الاستحقاق" in response.json().get("detail", "")