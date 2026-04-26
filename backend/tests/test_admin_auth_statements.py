"""Critical auth, admin, permissions, and statements API regression tests."""

import os
import uuid
from datetime import datetime, timedelta, timezone

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


def _login(api_client, base_url, username, password, otp_code=None):
    payload = {"username": username, "password": password}
    if otp_code:
        payload["otp_code"] = otp_code
    return api_client.post(f"{base_url}/api/auth/login", json=payload)


@pytest.fixture(scope="session")
def admin_auth(api_client, base_url):
    response = _login(api_client, base_url, ADMIN_USERNAME, ADMIN_PASSWORD)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data.get("requires_2fa") is False
    assert data.get("token")
    assert data["user"]["role"] == "admin"
    return data


@pytest.fixture
def admin_headers(admin_auth):
    return {"Authorization": f"Bearer {admin_auth['token']}", "Content-Type": "application/json"}


def _new_deposit_payload(prefix="TEST"):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    maturity = now + timedelta(days=450)
    unique = uuid.uuid4().hex[:8]
    return {
        "account_number": f"{prefix}-ACC-{unique}",
        "deposit_number": f"{prefix}-DEP-{unique}",
        "amount": 120000,
        "creation_datetime": now.isoformat(),
        "maturity_datetime": maturity.isoformat(),
        "monthly_interest_rate": 1.5,
    }


# Auth flow coverage (admin login without mandatory 2FA)
def test_admin_login_with_default_credentials_without_2fa(api_client, base_url):
    response = _login(api_client, base_url, ADMIN_USERNAME, ADMIN_PASSWORD)
    assert response.status_code == 200
    data = response.json()
    assert data["requires_2fa"] is False
    assert data["user"]["username"] == ADMIN_USERNAME


# Protection coverage (banks endpoint blocked without token)
def test_banks_requires_token(api_client, base_url):
    response = api_client.get(f"{base_url}/api/banks")
    assert response.status_code == 401
    assert "detail" in response.json()


# Protection coverage (banks endpoint works with token)
def test_banks_access_with_admin_token(api_client, base_url, admin_headers):
    response = api_client.get(f"{base_url}/api/banks", headers=admin_headers)
    assert response.status_code == 200
    banks = response.json()
    assert isinstance(banks, list)
    assert any(bank["id"] == "banque-misr" for bank in banks)


# Admin user management coverage
def test_admin_can_create_limited_data_entry_user(api_client, base_url, admin_headers):
    username = f"TEST_enter_{uuid.uuid4().hex[:8]}"
    payload = {
        "username": username,
        "password": "UserPass@123",
        "permissions": {
            "enter_deposits": True,
            "view_reports": False,
            "edit_deposits": False,
            "manage_users": False,
        },
        "is_active": True,
    }
    response = api_client.post(f"{base_url}/api/admin/users", headers=admin_headers, json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == username
    assert data["permissions"]["enter_deposits"] is True
    assert data["permissions"]["view_reports"] is False


# Permission coverage (enter_deposits yes, view_reports no)
def test_limited_user_can_create_deposit_but_cannot_view_statements(api_client, base_url, admin_headers):
    username = f"TEST_perm_{uuid.uuid4().hex[:8]}"
    create_user_payload = {
        "username": username,
        "password": "UserPass@123",
        "permissions": {
            "enter_deposits": True,
            "view_reports": False,
            "edit_deposits": False,
            "manage_users": False,
        },
        "is_active": True,
    }
    create_user = api_client.post(f"{base_url}/api/admin/users", headers=admin_headers, json=create_user_payload)
    assert create_user.status_code == 200

    login = _login(api_client, base_url, username, "UserPass@123")
    assert login.status_code == 200
    user_token = login.json()["token"]
    user_headers = {"Authorization": f"Bearer {user_token}", "Content-Type": "application/json"}

    deposit_payload = _new_deposit_payload("TEST_PERM")
    create_deposit = api_client.post(
        f"{base_url}/api/banks/banque-misr/deposits",
        headers=user_headers,
        json=deposit_payload,
    )
    assert create_deposit.status_code == 200
    created = create_deposit.json()
    assert created["deposit_number"] == deposit_payload["deposit_number"]

    detailed = api_client.get(f"{base_url}/api/banks/banque-misr/statements/detailed", headers=user_headers)
    assert detailed.status_code == 403
    volume = api_client.get(f"{base_url}/api/banks/banque-misr/statements/volume", headers=user_headers)
    assert volume.status_code == 403


# Admin password protection coverage (wrong current password)
def test_admin_change_password_rejects_wrong_current(api_client, base_url, admin_headers):
    response = api_client.post(
        f"{base_url}/api/admin/change-password",
        headers=admin_headers,
        json={"current_password": "WrongPass@123", "new_password": "AdminTemp@123"},
    )
    assert response.status_code == 401
    assert "detail" in response.json()


# Admin password change success coverage (and rollback)
def test_admin_change_password_success_then_rollback(api_client, base_url):
    change = api_client.post(
        f"{base_url}/api/admin/change-password",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {_login(api_client, base_url, ADMIN_USERNAME, ADMIN_PASSWORD).json()['token']}",
        },
        json={"current_password": ADMIN_PASSWORD, "new_password": "AdminTemp@123"},
    )
    assert change.status_code == 200

    login_new = _login(api_client, base_url, ADMIN_USERNAME, "AdminTemp@123")
    assert login_new.status_code == 200
    assert login_new.json()["user"]["username"] == ADMIN_USERNAME

    rollback = api_client.post(
        f"{base_url}/api/admin/change-password",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {login_new.json()['token']}",
        },
        json={"current_password": "AdminTemp@123", "new_password": ADMIN_PASSWORD},
    )
    assert rollback.status_code == 200


# 2FA setup coverage (QR/manual secret without permanent enable)
def test_admin_2fa_setup_returns_qr_and_manual_secret(api_client, base_url, admin_headers):
    response = api_client.post(f"{base_url}/api/admin/2fa/setup", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["qr_data_url"].startswith("data:image/png;base64,")
    assert isinstance(data["manual_secret"], str)
    assert len(data["manual_secret"]) >= 16


# Deposit create by admin + statements data integrity coverage
def test_admin_can_create_deposit_and_fetch_statements(api_client, base_url, admin_headers):
    payload = _new_deposit_payload("TEST_ADMIN")
    created_response = api_client.post(
        f"{base_url}/api/banks/industrial-development/deposits",
        headers=admin_headers,
        json=payload,
    )
    assert created_response.status_code == 200
    created = created_response.json()
    assert created["deposit_number"] == payload["deposit_number"]

    detailed = api_client.get(f"{base_url}/api/banks/industrial-development/statements/detailed", headers=admin_headers)
    assert detailed.status_code == 200
    detailed_data = detailed.json()
    assert detailed_data["bank"]["id"] == "industrial-development"
    assert isinstance(detailed_data["rows"], list)
    assert all("current_year_interest" in row and "previous_years_interest" in row for row in detailed_data["rows"])

    volume = api_client.get(f"{base_url}/api/banks/industrial-development/statements/volume", headers=admin_headers)
    assert volume.status_code == 200
    volume_data = volume.json()
    assert volume_data["bank"]["id"] == "industrial-development"
    assert isinstance(volume_data["rows"], list)
    assert all("deposit_number" in row and "monthly_interest_rate" in row for row in volume_data["rows"])
