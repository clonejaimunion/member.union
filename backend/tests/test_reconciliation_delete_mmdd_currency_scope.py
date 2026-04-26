"""Reconciliation delete-permission and setup file signature API tests for iteration scope."""

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


def _login(api_client, base_url, username, password):
    return api_client.post(
        f"{base_url}/api/auth/login",
        json={"username": username, "password": password},
    )


@pytest.fixture(scope="session")
def admin_headers(api_client, base_url):
    login = _login(api_client, base_url, ADMIN_USERNAME, ADMIN_PASSWORD)
    if login.status_code != 200:
        pytest.skip(f"Admin login failed: {login.status_code}")

    payload = login.json()
    token = payload.get("token")
    if not token:
        if payload.get("requires_2fa"):
            pytest.skip("Admin account requires 2FA; skipping this suite")
        pytest.skip("Admin token missing")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _create_standard_user_headers(api_client, base_url, admin_headers):
    username = f"TEST_nonadmin_{uuid.uuid4().hex[:8]}"
    password = "UserPass@123"
    user_payload = {
        "username": username,
        "password": password,
        "permissions": {
            "enter_deposits": True,
            "view_reports": True,
            "edit_deposits": False,
            "manage_users": False,
        },
        "is_active": True,
    }
    create_resp = api_client.post(
        f"{base_url}/api/admin/users",
        headers=admin_headers,
        json=user_payload,
    )
    assert create_resp.status_code == 200, create_resp.text

    user_login = _login(api_client, base_url, username, password)
    assert user_login.status_code == 200, user_login.text
    user_token = user_login.json().get("token")
    assert isinstance(user_token, str) and user_token

    return {"Authorization": f"Bearer {user_token}", "Content-Type": "application/json"}


# Module: reconciliation deletion authorization and persistence checks
def test_admin_can_delete_reconciliation_and_get_returns_404(api_client, base_url, admin_headers):
    create_payload = {
        "period_label": f"TEST MMDD DELETE {uuid.uuid4().hex[:4]}",
        "book_balance": 1000,
        "bank_statement_balance": 1000,
        "outstanding_checks": [
            {
                "check_number": f"CHK-{uuid.uuid4().hex[:6]}",
                "amount": 100,
                "check_date": "2026-05-17T00:00:00+00:00",
            }
        ],
        "collection_checks": [],
    }
    create_resp = api_client.post(
        f"{base_url}/api/banks/banque-misr/reconciliations",
        headers=admin_headers,
        json=create_payload,
    )
    assert create_resp.status_code == 200, create_resp.text
    created = create_resp.json()
    reconciliation_id = created["id"]

    assert created["outstanding_checks"][0]["check_number"] == create_payload["outstanding_checks"][0]["check_number"]
    assert "2026-05-17" in created["outstanding_checks"][0]["check_date"]

    delete_resp = api_client.delete(
        f"{base_url}/api/banks/banque-misr/reconciliations/{reconciliation_id}",
        headers=admin_headers,
    )
    assert delete_resp.status_code == 200, delete_resp.text
    delete_body = delete_resp.json()
    assert delete_body.get("deleted_reconciliation_id") == reconciliation_id

    get_deleted = api_client.get(
        f"{base_url}/api/banks/banque-misr/reconciliations/{reconciliation_id}",
        headers=admin_headers,
    )
    assert get_deleted.status_code == 404, get_deleted.text


# Module: non-admin cannot delete reconciliation created by admin
def test_non_admin_cannot_delete_reconciliation(api_client, base_url, admin_headers):
    user_headers = _create_standard_user_headers(api_client, base_url, admin_headers)

    create_payload = {
        "period_label": f"TEST NONADMIN DELETE {uuid.uuid4().hex[:4]}",
        "book_balance": 900,
        "bank_statement_balance": 900,
        "outstanding_checks": [],
        "collection_checks": [
            {
                "check_number": f"COL-{uuid.uuid4().hex[:6]}",
                "amount": 75,
                "check_date": "2026-05-17T00:00:00+00:00",
            }
        ],
    }
    create_resp = api_client.post(
        f"{base_url}/api/banks/industrial-development/reconciliations",
        headers=admin_headers,
        json=create_payload,
    )
    assert create_resp.status_code == 200, create_resp.text
    created = create_resp.json()

    denied_delete = api_client.delete(
        f"{base_url}/api/banks/industrial-development/reconciliations/{created['id']}",
        headers=user_headers,
    )
    assert denied_delete.status_code == 403, denied_delete.text
    denied_body = denied_delete.json()
    assert "detail" in denied_body

    still_exists = api_client.get(
        f"{base_url}/api/banks/industrial-development/reconciliations/{created['id']}",
        headers=admin_headers,
    )
    assert still_exists.status_code == 200, still_exists.text
    assert still_exists.json()["id"] == created["id"]


# Module: setup download endpoint returns executable with MZ signature
def test_setup_download_has_mz_signature(api_client, base_url, admin_headers):
    resp = api_client.get(f"{base_url}/api/download/setup", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    assert resp.headers.get("content-type", "").startswith("application/vnd.microsoft.portable-executable")
    assert resp.content[:2] == b"MZ"
