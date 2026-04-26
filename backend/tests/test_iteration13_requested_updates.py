"""Iteration 13 regression: auth entry, bank swift fields, reconciliation create/list, setup download."""

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


# Module: admin login with default credentials and 2FA-setup-compatible access response
def test_admin_login_default_credentials_returns_access_or_setup_flag(api_client, base_url):
    response = api_client.post(
        f"{base_url}/api/auth/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )
    assert response.status_code == 200
    data = response.json()
    assert data.get("requires_2fa") is False
    assert isinstance(data.get("message"), str) and data.get("message")
    assert isinstance(data.get("user"), dict)
    assert data["user"]["username"] == ADMIN_USERNAME
    assert data["user"]["role"] == "admin"
    assert isinstance(data.get("requires_2fa_setup"), bool)
    assert isinstance(data.get("token"), str) and len(data.get("token")) > 20


@pytest.fixture
def admin_headers(api_client, base_url):
    login = api_client.post(
        f"{base_url}/api/auth/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )
    assert login.status_code == 200, login.text
    token = login.json().get("token")
    if not token:
        pytest.skip("Admin token unavailable (possibly 2FA required)")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# Module: bank list contains swift code under bank data (selection + bank shell support)
def test_banks_list_includes_swift_code_fields(api_client, base_url, admin_headers):
    response = api_client.get(f"{base_url}/api/banks", headers=admin_headers)
    assert response.status_code == 200
    banks = response.json()
    assert isinstance(banks, list) and len(banks) >= 1
    assert all("swift_code" in bank for bank in banks)

    banque_misr = next((bank for bank in banks if bank.get("id") == "banque-misr"), None)
    assert banque_misr is not None
    assert banque_misr.get("swift_code") == "BMISEGCX"


# Module: reconciliation create/list endpoint sanity for year-filtered history UI source data
def test_reconciliation_create_and_list_data_source(api_client, base_url, admin_headers):
    payload = {
        "period_label": f"TEST يناير 2026 {uuid.uuid4().hex[:6]}",
        "administration": "النقابة العامة للعاملين بالزراعة والري",
        "book_balance": 1000,
        "bank_statement_balance": 1000,
        "outstanding_checks": [],
        "collection_checks": [],
    }
    create = api_client.post(
        f"{base_url}/api/banks/industrial-development/reconciliations",
        headers=admin_headers,
        json=payload,
    )
    assert create.status_code == 200, create.text
    created = create.json()
    assert created["period_label"] == payload["period_label"]
    assert created["status_text"] == "الرصيد مطابق"
    assert created["is_matched"] is True

    listing = api_client.get(
        f"{base_url}/api/banks/industrial-development/reconciliations",
        headers=admin_headers,
    )
    assert listing.status_code == 200
    records = listing.json()
    assert isinstance(records, list)
    one = next((item for item in records if item.get("id") == created["id"]), None)
    assert one is not None
    assert one["period_label"] == payload["period_label"]


# Module: installer download endpoint returns valid EXE magic header and expected size range
def test_download_setup_endpoint_returns_valid_exe(api_client, base_url):
    response = api_client.get(f"{base_url}/api/download/setup")
    assert response.status_code == 200
    assert response.content[:2] == b"MZ"
    assert len(response.content) > 900_000
    assert "application/vnd.microsoft.portable-executable" in response.headers.get("content-type", "")
