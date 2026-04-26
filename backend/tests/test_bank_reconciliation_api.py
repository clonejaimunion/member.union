"""Bank reconciliation API regression tests (calculation fields + permissions)."""

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
    data = login.json()
    token = data.get("token")
    if not token:
        if data.get("requires_2fa"):
            pytest.skip("Admin account requires 2FA; skipping reconciliation API tests")
        pytest.skip("No token returned from admin login")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# Module: user permissions setup for reconciliation-save permission checks
def _create_user_and_headers(api_client, base_url, admin_headers, *, enter_deposits, view_reports):
    username = f"TEST_recon_{uuid.uuid4().hex[:8]}"
    password = "UserPass@123"
    payload = {
        "username": username,
        "password": password,
        "permissions": {
            "enter_deposits": enter_deposits,
            "view_reports": view_reports,
            "edit_deposits": False,
            "manage_users": False,
        },
        "is_active": True,
    }
    create = api_client.post(f"{base_url}/api/admin/users", headers=admin_headers, json=payload)
    assert create.status_code == 200, create.text

    login = _login(api_client, base_url, username, password)
    assert login.status_code == 200, login.text
    token = login.json().get("token")
    assert isinstance(token, str) and token
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# Module: reconciliation formula and response-field validation
def test_create_reconciliation_returns_expected_calculated_fields(api_client, base_url, admin_headers):
    payload = {
        "period_label": f"TEST فبراير {uuid.uuid4().hex[:4]}",
        "book_balance": 100000,
        "bank_statement_balance": 110000,
        "outstanding_checks": [
            {"check_number": f"CHK-{uuid.uuid4().hex[:6]}", "amount": 15000, "check_date": "2025-02-15T00:00:00+00:00"}
        ],
        "collection_checks": [
            {"check_number": f"COL-{uuid.uuid4().hex[:6]}", "amount": 5000, "check_date": "2025-02-16T00:00:00+00:00"}
        ],
    }

    create = api_client.post(
        f"{base_url}/api/banks/banque-misr/reconciliations",
        headers=admin_headers,
        json=payload,
    )
    assert create.status_code == 200, create.text
    data = create.json()

    assert data["bank_id"] == "banque-misr"
    assert data["book_balance"] == payload["book_balance"]
    assert data["bank_statement_balance"] == payload["bank_statement_balance"]
    assert data["total_outstanding_checks"] == 15000
    assert data["total_collection_checks"] == 5000
    assert data["calculated_balance"] == 110000
    assert data["difference"] == 0
    assert data["is_matched"] is True
    assert data["status_text"] == "الرصيد مطابق"

    get_one = api_client.get(
        f"{base_url}/api/banks/banque-misr/reconciliations/{data['id']}",
        headers=admin_headers,
    )
    assert get_one.status_code == 200, get_one.text
    persisted = get_one.json()
    assert persisted["id"] == data["id"]
    assert persisted["calculated_balance"] == 110000
    assert persisted["status_text"] == "الرصيد مطابق"


# Module: unmatched status text and difference integrity
def test_create_reconciliation_unmatched_sets_difference_and_status(api_client, base_url, admin_headers):
    payload = {
        "period_label": f"TEST مارس {uuid.uuid4().hex[:4]}",
        "book_balance": 200000,
        "bank_statement_balance": 220000,
        "outstanding_checks": [
            {"check_number": f"CHK-{uuid.uuid4().hex[:6]}", "amount": 20000, "check_date": "2025-03-10T00:00:00+00:00"}
        ],
        "collection_checks": [
            {"check_number": f"COL-{uuid.uuid4().hex[:6]}", "amount": 10000, "check_date": "2025-03-11T00:00:00+00:00"}
        ],
    }

    create = api_client.post(
        f"{base_url}/api/banks/banque-misr/reconciliations",
        headers=admin_headers,
        json=payload,
    )
    assert create.status_code == 200, create.text
    data = create.json()

    assert data["calculated_balance"] == 210000
    assert data["difference"] == -10000
    assert data["is_matched"] is False
    assert data["status_text"] == "الرصيد غير مطابق"


# Module: reconciliation history listing and selection data source integrity
def test_reconciliation_list_contains_newly_created_record(api_client, base_url, admin_headers):
    payload = {
        "period_label": f"TEST أبريل {uuid.uuid4().hex[:4]}",
        "book_balance": 50000,
        "bank_statement_balance": 50000,
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

    list_resp = api_client.get(
        f"{base_url}/api/banks/industrial-development/reconciliations",
        headers=admin_headers,
    )
    assert list_resp.status_code == 200, list_resp.text
    records = list_resp.json()
    matched = [item for item in records if item["id"] == created["id"]]
    assert len(matched) == 1
    assert matched[0]["period_label"] == payload["period_label"]


# Module: permission checks (user with enter_deposits can save reconciliation)
def test_user_with_enter_deposits_can_save_reconciliation(api_client, base_url, admin_headers):
    user_headers = _create_user_and_headers(
        api_client,
        base_url,
        admin_headers,
        enter_deposits=True,
        view_reports=True,
    )
    payload = {
        "period_label": f"TEST مايو {uuid.uuid4().hex[:4]}",
        "book_balance": 70000,
        "bank_statement_balance": 70000,
        "outstanding_checks": [],
        "collection_checks": [],
    }
    create = api_client.post(
        f"{base_url}/api/banks/agricultural-bank/reconciliations",
        headers=user_headers,
        json=payload,
    )
    assert create.status_code == 200, create.text
    data = create.json()
    assert data["status_text"] == "الرصيد مطابق"
    assert data["is_matched"] is True


# Module: permission checks (user without enter_deposits cannot save reconciliation)
def test_user_without_enter_deposits_cannot_save_reconciliation(api_client, base_url, admin_headers):
    user_headers = _create_user_and_headers(
        api_client,
        base_url,
        admin_headers,
        enter_deposits=False,
        view_reports=True,
    )
    payload = {
        "period_label": f"TEST يونيو {uuid.uuid4().hex[:4]}",
        "book_balance": 70000,
        "bank_statement_balance": 70000,
        "outstanding_checks": [],
        "collection_checks": [],
    }
    create = api_client.post(
        f"{base_url}/api/banks/agricultural-bank/reconciliations",
        headers=user_headers,
        json=payload,
    )
    assert create.status_code == 403
    body = create.json()
    assert "detail" in body
