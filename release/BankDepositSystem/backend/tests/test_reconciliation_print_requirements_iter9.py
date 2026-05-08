"""Regression API tests for reconciliation administration field and setup binary validity."""

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
    payload = login.json()
    token = payload.get("token")
    if not token:
        if payload.get("requires_2fa"):
            pytest.skip("Admin account requires 2FA; skipping auth-required reconciliation API tests")
        pytest.skip("No token returned from admin login")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# Reconciliation module: administration value should persist as sent for union option
def test_reconciliation_create_persists_union_administration(api_client, base_url, admin_headers):
    payload = {
        "period_label": f"TEST ADMIN UNION {uuid.uuid4().hex[:5]}",
        "administration": "النقابة العامة للعاملين بالزراعة والري",
        "book_balance": 1000,
        "bank_statement_balance": 1000,
        "outstanding_checks": [
            {
                "check_number": f"OUT-{uuid.uuid4().hex[:6]}",
                "amount": 10,
                "check_date": "2026-02-15T00:00:00+00:00",
            }
        ],
        "collection_checks": [],
    }
    create_resp = api_client.post(
        f"{base_url}/api/banks/industrial-development/reconciliations",
        headers=admin_headers,
        json=payload,
    )
    assert create_resp.status_code == 200, create_resp.text
    created = create_resp.json()
    assert created["administration"] == payload["administration"]
    assert created["period_label"] == payload["period_label"]
    assert created["total_outstanding_checks"] == 10

    fetch_resp = api_client.get(
        f"{base_url}/api/banks/industrial-development/reconciliations/{created['id']}",
        headers=admin_headers,
    )
    assert fetch_resp.status_code == 200, fetch_resp.text
    fetched = fetch_resp.json()
    assert fetched["administration"] == payload["administration"]
    assert fetched["outstanding_checks"][0]["check_number"] == payload["outstanding_checks"][0]["check_number"]


# Reconciliation module: administration value should persist as sent for social option
def test_reconciliation_create_persists_social_administration(api_client, base_url, admin_headers):
    payload = {
        "period_label": f"TEST ADMIN SOCIAL {uuid.uuid4().hex[:5]}",
        "administration": "مشروع التكافل الاجتماعي",
        "book_balance": 1250,
        "bank_statement_balance": 1250,
        "outstanding_checks": [],
        "collection_checks": [],
    }
    create_resp = api_client.post(
        f"{base_url}/api/banks/banque-misr/reconciliations",
        headers=admin_headers,
        json=payload,
    )
    assert create_resp.status_code == 200, create_resp.text
    created = create_resp.json()
    assert created["administration"] == payload["administration"]
    assert created["total_outstanding_checks"] == 0
    assert created["total_collection_checks"] == 0

    latest_resp = api_client.get(
        f"{base_url}/api/banks/banque-misr/reconciliations/latest",
        headers=admin_headers,
    )
    assert latest_resp.status_code == 200, latest_resp.text
    latest = latest_resp.json()
    assert latest["id"] == created["id"]
    assert latest["administration"] == payload["administration"]


# Reconciliation module: empty checks arrays should remain empty after create -> get
def test_reconciliation_create_with_empty_checks_remains_empty(api_client, base_url, admin_headers):
    payload = {
        "period_label": f"TEST EMPTY TABLES {uuid.uuid4().hex[:5]}",
        "administration": "النقابة العامة للعاملين بالزراعة والري",
        "book_balance": 500,
        "bank_statement_balance": 500,
        "outstanding_checks": [],
        "collection_checks": [],
    }
    create_resp = api_client.post(
        f"{base_url}/api/banks/agricultural-bank/reconciliations",
        headers=admin_headers,
        json=payload,
    )
    assert create_resp.status_code == 200, create_resp.text
    created = create_resp.json()
    assert created["outstanding_checks"] == []
    assert created["collection_checks"] == []

    fetch_resp = api_client.get(
        f"{base_url}/api/banks/agricultural-bank/reconciliations/{created['id']}",
        headers=admin_headers,
    )
    assert fetch_resp.status_code == 200, fetch_resp.text
    fetched = fetch_resp.json()
    assert fetched["outstanding_checks"] == []
    assert fetched["collection_checks"] == []


# Installer module: setup endpoint and local installer should both have MZ signature
def test_setup_exe_mz_signature_endpoint_and_local_file(api_client, base_url, admin_headers):
    endpoint_file = api_client.get(f"{base_url}/api/download/setup", headers=admin_headers)
    assert endpoint_file.status_code == 200
    assert endpoint_file.content[:2] == b"MZ"

    with open("/app/dist/BankDepositSystemSetup.exe", "rb") as setup_file:
        assert setup_file.read(2) == b"MZ"
