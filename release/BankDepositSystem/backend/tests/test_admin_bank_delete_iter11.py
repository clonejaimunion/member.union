"""Regression tests for admin-only full bank deletion and cascade cleanup behavior."""

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


def _login(api_client, base_url, username, password):
    return api_client.post(
        f"{base_url}/api/auth/login",
        json={"username": username, "password": password},
    )


# Auth module: admin login for protected bank-delete endpoints
@pytest.fixture(scope="session")
def admin_headers(api_client, base_url):
    login = _login(api_client, base_url, ADMIN_USERNAME, ADMIN_PASSWORD)
    if login.status_code != 200:
        pytest.skip(f"Admin login failed: {login.status_code}")
    data = login.json()
    token = data.get("token")
    if not token:
        if data.get("requires_2fa"):
            pytest.skip("Admin account requires 2FA; skipping admin bank delete tests")
        pytest.skip("No admin token returned")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _create_user_and_headers(api_client, base_url, admin_headers):
    username = f"TEST_bankdelete_user_{uuid.uuid4().hex[:8]}"
    password = "UserPass@123"
    create_user = api_client.post(
        f"{base_url}/api/admin/users",
        headers=admin_headers,
        json={
            "username": username,
            "password": password,
            "permissions": {
                "enter_deposits": True,
                "view_reports": True,
                "edit_deposits": False,
                "manage_users": False,
            },
            "is_active": True,
        },
    )
    assert create_user.status_code == 200, create_user.text

    login = _login(api_client, base_url, username, password)
    assert login.status_code == 200, login.text
    token = login.json().get("token")
    assert isinstance(token, str) and token
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# Permissions module: non-admin must be denied delete-bank endpoint
def test_delete_bank_endpoint_rejects_non_admin(api_client, base_url, admin_headers):
    user_headers = _create_user_and_headers(api_client, base_url, admin_headers)
    response = api_client.delete(
        f"{base_url}/api/admin/banks/banque-misr",
        headers=user_headers,
    )
    assert response.status_code == 403
    assert "detail" in response.json()


# CRUD/Cascade module: deleting TEST bank removes bank, deposits, and reconciliations
def test_admin_delete_bank_cascades_and_hides_bank(api_client, base_url, admin_headers):
    bank_name = f"TEST DELETE BANK ITER11 {uuid.uuid4().hex[:6]}"

    create_bank = api_client.post(
        f"{base_url}/api/admin/banks",
        headers=admin_headers,
        json={"name": bank_name, "code": f"TDB{uuid.uuid4().hex[:3].upper()}"},
    )
    assert create_bank.status_code == 200, create_bank.text
    bank = create_bank.json()
    bank_id = bank["id"]
    assert bank["name"] == bank_name

    creation_dt = datetime.now(timezone.utc)
    maturity_dt = creation_dt + timedelta(days=365)
    create_deposit = api_client.post(
        f"{base_url}/api/banks/{bank_id}/deposits",
        headers=admin_headers,
        json={
            "account_number": f"TEST-ACC-{uuid.uuid4().hex[:6]}",
            "deposit_number": f"TEST-DEP-{uuid.uuid4().hex[:6]}",
            "amount": 100000,
            "creation_datetime": creation_dt.isoformat(),
            "maturity_datetime": maturity_dt.isoformat(),
            "monthly_interest_rate": 12,
        },
    )
    assert create_deposit.status_code == 200, create_deposit.text
    deposit = create_deposit.json()
    assert deposit["bank_id"] == bank_id

    create_recon = api_client.post(
        f"{base_url}/api/banks/{bank_id}/reconciliations",
        headers=admin_headers,
        json={
            "period_label": f"TEST DEL {uuid.uuid4().hex[:4]}",
            "administration": "النقابة العامة للعاملين بالزراعة والري",
            "book_balance": 1000,
            "bank_statement_balance": 1000,
            "outstanding_checks": [],
            "collection_checks": [],
        },
    )
    assert create_recon.status_code == 200, create_recon.text
    recon = create_recon.json()
    assert recon["bank_id"] == bank_id

    delete_bank = api_client.delete(f"{base_url}/api/admin/banks/{bank_id}", headers=admin_headers)
    assert delete_bank.status_code == 200, delete_bank.text
    deleted = delete_bank.json()
    assert deleted["deleted_bank_id"] == bank_id
    assert deleted["deleted_deposits"] >= 1
    assert deleted["deleted_reconciliations"] >= 1

    list_banks = api_client.get(f"{base_url}/api/banks", headers=admin_headers)
    assert list_banks.status_code == 200, list_banks.text
    assert all(item["id"] != bank_id for item in list_banks.json())

    deposits_after = api_client.get(f"{base_url}/api/banks/{bank_id}/deposits", headers=admin_headers)
    assert deposits_after.status_code == 404

    recon_after = api_client.get(f"{base_url}/api/banks/{bank_id}/reconciliations", headers=admin_headers)
    assert recon_after.status_code == 404


# Installer module: setup executable must preserve MZ signature
def test_setup_exe_signature_is_mz(api_client, base_url, admin_headers):
    setup_resp = api_client.get(f"{base_url}/api/download/setup", headers=admin_headers)
    assert setup_resp.status_code == 200, setup_resp.text
    assert setup_resp.content[:2] == b"MZ"

    with open("/app/dist/BankDepositSystemSetup.exe", "rb") as local_file:
        assert local_file.read(2) == b"MZ"
