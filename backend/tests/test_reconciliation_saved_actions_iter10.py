"""Regression API tests for saved reconciliation edit flow, permissions, and setup.exe signature."""

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


# Auth module: admin login for protected reconciliation endpoints
@pytest.fixture(scope="session")
def admin_headers(api_client, base_url):
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
            pytest.skip("Admin account requires 2FA; skipping auth-required tests")
        pytest.skip("No admin token returned")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# Reconciliation module: create/update/get flow with id persistence
def test_put_updates_reconciliation_without_creating_new_record(api_client, base_url, admin_headers):
    period_seed = f"TEST_EDIT_RECON_{uuid.uuid4().hex[:8]}"
    create_payload = {
        "period_label": period_seed,
        "administration": "النقابة العامة للعاملين بالزراعة والري",
        "book_balance": 1000,
        "bank_statement_balance": 950,
        "outstanding_checks": [
            {
                "check_number": f"OUT-{uuid.uuid4().hex[:6]}",
                "amount": 100,
                "check_date": "2026-02-10T00:00:00+00:00",
            }
        ],
        "collection_checks": [
            {
                "check_number": f"COL-{uuid.uuid4().hex[:6]}",
                "amount": 20,
                "check_date": "2026-02-11T00:00:00+00:00",
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
    created_id = created["id"]
    assert created["period_label"] == period_seed

    update_payload = {
        "period_label": f"{period_seed}_UPDATED",
        "administration": "مشروع التكافل الاجتماعي",
        "book_balance": 1500,
        "bank_statement_balance": 1400,
        "outstanding_checks": [
            {
                "check_number": f"OUTU-{uuid.uuid4().hex[:6]}",
                "amount": 80,
                "check_date": "2026-02-12T00:00:00+00:00",
            }
        ],
        "collection_checks": [
            {
                "check_number": f"COLU-{uuid.uuid4().hex[:6]}",
                "amount": 30,
                "check_date": "2026-02-13T00:00:00+00:00",
            }
        ],
    }
    put_resp = api_client.put(
        f"{base_url}/api/banks/industrial-development/reconciliations/{created_id}",
        headers=admin_headers,
        json=update_payload,
    )
    assert put_resp.status_code == 200, put_resp.text
    updated = put_resp.json()
    assert updated["id"] == created_id
    assert updated["period_label"] == update_payload["period_label"]
    assert updated["administration"] == update_payload["administration"]
    assert updated["calculated_balance"] == 1550

    fetch_resp = api_client.get(
        f"{base_url}/api/banks/industrial-development/reconciliations/{created_id}",
        headers=admin_headers,
    )
    assert fetch_resp.status_code == 200, fetch_resp.text
    fetched = fetch_resp.json()
    assert fetched["id"] == created_id
    assert fetched["period_label"] == update_payload["period_label"]
    assert fetched["collection_checks"][0]["amount"] == 30

    list_resp = api_client.get(
        f"{base_url}/api/banks/industrial-development/reconciliations",
        headers=admin_headers,
    )
    assert list_resp.status_code == 200, list_resp.text
    same_id_rows = [item for item in list_resp.json() if item["id"] == created_id]
    assert len(same_id_rows) == 1


# Permissions module: view_reports-only user can view list but cannot create/update
def test_view_reports_user_can_preview_but_cannot_edit(api_client, base_url, admin_headers):
    user_name = f"TEST_view_reports_{uuid.uuid4().hex[:7]}"
    user_password = "UserPass@123"
    create_user_resp = api_client.post(
        f"{base_url}/api/admin/users",
        headers=admin_headers,
        json={
            "username": user_name,
            "password": user_password,
            "permissions": {
                "enter_deposits": False,
                "view_reports": True,
                "edit_deposits": False,
                "manage_users": False,
            },
            "is_active": True,
        },
    )
    assert create_user_resp.status_code == 200, create_user_resp.text

    user_login_resp = api_client.post(
        f"{base_url}/api/auth/login",
        json={"username": user_name, "password": user_password},
    )
    assert user_login_resp.status_code == 200, user_login_resp.text
    user_token = user_login_resp.json().get("token")
    assert isinstance(user_token, str) and user_token
    user_headers = {"Authorization": f"Bearer {user_token}", "Content-Type": "application/json"}

    # Seed reconciliation with admin first, then verify user preview and edit restrictions on same record.
    seed_period = f"TEST_SEED_FOR_VIEW_ONLY_{uuid.uuid4().hex[:6]}"
    seed_resp = api_client.post(
        f"{base_url}/api/banks/banque-misr/reconciliations",
        headers=admin_headers,
        json={
            "period_label": seed_period,
            "administration": "النقابة العامة للعاملين بالزراعة والري",
            "book_balance": 100,
            "bank_statement_balance": 100,
            "outstanding_checks": [],
            "collection_checks": [],
        },
    )
    assert seed_resp.status_code == 200, seed_resp.text
    seed = seed_resp.json()

    list_resp = api_client.get(
        f"{base_url}/api/banks/banque-misr/reconciliations",
        headers=user_headers,
    )
    assert list_resp.status_code == 200, list_resp.text
    listed = [item for item in list_resp.json() if item["id"] == seed["id"]]
    assert len(listed) == 1

    put_resp = api_client.put(
        f"{base_url}/api/banks/banque-misr/reconciliations/{seed['id']}",
        headers=user_headers,
        json={
            "period_label": f"{seed_period}_ILLEGAL_EDIT",
            "administration": "مشروع التكافل الاجتماعي",
            "book_balance": 200,
            "bank_statement_balance": 200,
            "outstanding_checks": [],
            "collection_checks": [],
        },
    )
    assert put_resp.status_code == 403
    assert "detail" in put_resp.json()


# Installer module: setup executable starts with MZ signature from endpoint and local dist file
def test_setup_exe_has_valid_mz_signature(api_client, base_url, admin_headers):
    setup_resp = api_client.get(f"{base_url}/api/download/setup", headers=admin_headers)
    assert setup_resp.status_code == 200, setup_resp.text
    assert setup_resp.content[:2] == b"MZ"

    with open("/app/dist/BankDepositSystemSetup.exe", "rb") as local_file:
        assert local_file.read(2) == b"MZ"
