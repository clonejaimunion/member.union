"""Iteration 12 regression: admin user-delete rules, reconciliation permission, and setup.exe signature."""

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


# Auth module: admin token for protected endpoints
@pytest.fixture(scope="session")
def admin_headers(api_client, base_url):
    login = _login(api_client, base_url, ADMIN_USERNAME, ADMIN_PASSWORD)
    if login.status_code != 200:
        pytest.skip(f"Admin login failed: {login.status_code}")
    payload = login.json()
    token = payload.get("token")
    if not token:
        if payload.get("requires_2fa"):
            pytest.skip("Admin account requires 2FA; skipping admin-protected tests")
        pytest.skip("No admin token returned")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture()
def created_user_ids():
    user_ids = []
    yield user_ids


@pytest.fixture(autouse=True)
def cleanup_created_users(api_client, base_url, admin_headers, created_user_ids):
    yield
    for user_id in created_user_ids:
        api_client.delete(f"{base_url}/api/admin/users/{user_id}", headers=admin_headers)


def _create_user(api_client, base_url, admin_headers, username, password, permissions):
    response = api_client.post(
        f"{base_url}/api/admin/users",
        headers=admin_headers,
        json={
            "username": username,
            "password": password,
            "permissions": permissions,
            "is_active": True,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


# Admin-users module: non-admin caller must be rejected for DELETE /api/admin/users/{id}
def test_delete_user_endpoint_rejects_non_admin(api_client, base_url, admin_headers, created_user_ids):
    non_admin = _create_user(
        api_client,
        base_url,
        admin_headers,
        username=f"TEST_nonadmin_delete_{uuid.uuid4().hex[:8]}",
        password="UserPass@123",
        permissions={
            "enter_deposits": True,
            "view_reports": True,
            "edit_deposits": False,
            "manage_users": False,
            "manage_reconciliations": False,
        },
    )
    target = _create_user(
        api_client,
        base_url,
        admin_headers,
        username=f"TEST_target_delete_{uuid.uuid4().hex[:8]}",
        password="UserPass@123",
        permissions={
            "enter_deposits": False,
            "view_reports": True,
            "edit_deposits": False,
            "manage_users": False,
            "manage_reconciliations": False,
        },
    )
    created_user_ids.extend([non_admin["id"], target["id"]])

    login = _login(api_client, base_url, non_admin["username"], "UserPass@123")
    assert login.status_code == 200, login.text
    non_admin_token = login.json().get("token")
    assert isinstance(non_admin_token, str) and non_admin_token

    non_admin_headers = {
        "Authorization": f"Bearer {non_admin_token}",
        "Content-Type": "application/json",
    }
    delete_response = api_client.delete(
        f"{base_url}/api/admin/users/{target['id']}",
        headers=non_admin_headers,
    )
    assert delete_response.status_code == 403
    assert "detail" in delete_response.json()


# Admin-users module: deleting admin account must be rejected
def test_delete_user_endpoint_rejects_admin_target(api_client, base_url, admin_headers):
    users_response = api_client.get(f"{base_url}/api/admin/users", headers=admin_headers)
    assert users_response.status_code == 200, users_response.text
    users = users_response.json()
    admin_user = next((item for item in users if item.get("role") == "admin"), None)
    assert admin_user is not None

    delete_response = api_client.delete(
        f"{base_url}/api/admin/users/{admin_user['id']}",
        headers=admin_headers,
    )
    assert delete_response.status_code == 403
    assert "detail" in delete_response.json()


# Reconciliation-permissions module: manage_reconciliations-only user can create reconciliation memo
def test_manage_reconciliations_only_user_can_create_reconciliation(api_client, base_url, admin_headers, created_user_ids):
    user = _create_user(
        api_client,
        base_url,
        admin_headers,
        username=f"TEST_manage_recon_{uuid.uuid4().hex[:8]}",
        password="UserPass@123",
        permissions={
            "enter_deposits": False,
            "view_reports": False,
            "edit_deposits": False,
            "manage_users": False,
            "manage_reconciliations": True,
        },
    )
    created_user_ids.append(user["id"])

    login = _login(api_client, base_url, user["username"], "UserPass@123")
    assert login.status_code == 200, login.text
    token = login.json().get("token")
    assert isinstance(token, str) and token
    user_headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    create_payload = {
        "period_label": f"TEST_RECON_ONLY_{uuid.uuid4().hex[:6]}",
        "administration": "النقابة العامة للعاملين بالزراعة والري",
        "book_balance": 1500,
        "bank_statement_balance": 1490,
        "outstanding_checks": [
            {
                "check_number": f"OUT-{uuid.uuid4().hex[:5]}",
                "amount": 20,
                "check_date": "2026-02-18T00:00:00+00:00",
            }
        ],
        "collection_checks": [
            {
                "check_number": f"COL-{uuid.uuid4().hex[:5]}",
                "amount": 10,
                "check_date": "2026-02-19T00:00:00+00:00",
            }
        ],
    }
    create_response = api_client.post(
        f"{base_url}/api/banks/industrial-development/reconciliations",
        headers=user_headers,
        json=create_payload,
    )
    assert create_response.status_code == 200, create_response.text
    created = create_response.json()
    assert created["period_label"] == create_payload["period_label"]
    assert created["bank_id"] == "industrial-development"
    assert created["calculated_balance"] == 1510

    get_response = api_client.get(
        f"{base_url}/api/banks/industrial-development/reconciliations/{created['id']}",
        headers=user_headers,
    )
    assert get_response.status_code == 200, get_response.text
    fetched = get_response.json()
    assert fetched["id"] == created["id"]
    assert fetched["period_label"] == create_payload["period_label"]


# Installer module: setup executable must preserve MZ signature (endpoint + local file)
def test_setup_exe_signature_is_mz(api_client, base_url, admin_headers):
    setup_response = api_client.get(f"{base_url}/api/download/setup", headers=admin_headers)
    assert setup_response.status_code == 200, setup_response.text
    assert setup_response.content[:2] == b"MZ"

    with open("/app/dist/BankDepositSystemSetup.exe", "rb") as local_setup:
        assert local_setup.read(2) == b"MZ"