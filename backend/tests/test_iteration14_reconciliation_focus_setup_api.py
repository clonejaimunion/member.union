"""Iteration 14 regression: reconciliation save/delete flow + setup installer download validity."""

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
    body = login.json()
    token = body.get("token")
    if not token:
        if body.get("requires_2fa"):
            pytest.skip("Admin account requires 2FA; skipping authenticated API tests")
        pytest.skip("No token returned from admin login")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# Module: setup installer endpoint validation (magic bytes + expected size band)
def test_download_setup_returns_valid_exe_binary(api_client, base_url):
    response = api_client.get(f"{base_url}/api/download/setup")
    assert response.status_code == 200, response.text
    assert response.content[:2] == b"MZ"
    assert len(response.content) > 900_000
    assert abs(len(response.content) - 944_131) < 20_000


# Module: reconciliation create -> get -> delete -> get(404) persistence lifecycle
def test_reconciliation_create_and_cleanup(api_client, base_url, admin_headers):
    suffix = uuid.uuid4().hex[:8]
    payload = {
        "period_label": f"TEST_FOCUS_FIX_{suffix}",
        "administration": "النقابة العامة للعاملين بالزراعة والري",
        "book_balance": 2000,
        "bank_statement_balance": 3250.25,
        "outstanding_checks": [
            {
                "check_number": "12345",
                "amount": 1500.75,
                "check_date": "2026-04-26T00:00:00+00:00",
            }
        ],
        "collection_checks": [
            {
                "check_number": "98765",
                "amount": 250.50,
                "check_date": "2026-04-05T00:00:00+00:00",
            }
        ],
    }

    create = api_client.post(
        f"{base_url}/api/banks/industrial-development/reconciliations",
        headers=admin_headers,
        json=payload,
    )
    assert create.status_code == 200, create.text
    created = create.json()
    assert created["period_label"] == payload["period_label"]
    assert created["total_outstanding_checks"] == 1500.75
    assert created["total_collection_checks"] == 250.5

    get_one = api_client.get(
        f"{base_url}/api/banks/industrial-development/reconciliations/{created['id']}",
        headers=admin_headers,
    )
    assert get_one.status_code == 200, get_one.text
    persisted = get_one.json()
    assert persisted["id"] == created["id"]
    assert persisted["outstanding_checks"][0]["check_number"] == "12345"
    assert persisted["collection_checks"][0]["check_number"] == "98765"

    delete = api_client.delete(
        f"{base_url}/api/banks/industrial-development/reconciliations/{created['id']}",
        headers=admin_headers,
    )
    assert delete.status_code == 200, delete.text
    delete_body = delete.json()
    assert delete_body["deleted_reconciliation_id"] == created["id"]

    missing = api_client.get(
        f"{base_url}/api/banks/industrial-development/reconciliations/{created['id']}",
        headers=admin_headers,
    )
    assert missing.status_code == 404
