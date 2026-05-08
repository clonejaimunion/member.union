"""Iteration 17: Expense voucher API regression (create/get/delete + method-specific fields)."""

import os
import uuid
from datetime import date

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
    token = login.json().get("token")
    if not token:
        pytest.skip("No admin access token available for expense tests")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture()
def created_expense_ids(api_client, base_url, admin_headers):
    ids = []
    yield ids
    for expense_id in ids:
        api_client.delete(f"{base_url}/api/expenses/{expense_id}", headers=admin_headers)


def _build_expense_payload(payment_method: str) -> dict:
    suffix = str(uuid.uuid4().int % 10_000_000).zfill(7)
    payload = {
        "expense_number": f"7{suffix}",
        "payment_method": payment_method,
        "payee_name": f"TEST_PAYEE_{suffix}" if payment_method in {"cash", "check"} else None,
        "check_number": f"8{suffix}" if payment_method == "check" else None,
        "transfer_number": f"9{suffix}" if payment_method == "bank_transfer" else None,
        "transfer_to": f"TEST_TRANSFER_TO_{suffix}" if payment_method == "bank_transfer" else None,
        "bank_id": "industrial-development",
        "gross_amount": 1234.5,
        "gross_statement": f"بيان TEST_{suffix}",
        "deductions": [
            {"amount": 100.0, "statement": "استقطاع 1"},
            {"amount": 34.5, "statement": "استقطاع 2"},
        ],
        "issued_at": date.today().isoformat(),
        "responsible_employee": "يوسف عبدالغني",
    }
    return payload


# Module: /api/expenses method-specific voucher data correctness
def test_expense_fields_for_cash_check_transfer(api_client, base_url, admin_headers, created_expense_ids):
    for method in ["cash", "check", "bank_transfer"]:
        payload = _build_expense_payload(method)
        create_response = api_client.post(f"{base_url}/api/expenses", headers=admin_headers, json=payload)
        assert create_response.status_code == 200, create_response.text
        created = create_response.json()
        created_expense_ids.append(created["id"])

        assert created["payment_method"] == method
        assert created["expense_number"] == payload["expense_number"]
        assert created["gross_statement"] == payload["gross_statement"]
        assert created["total_deductions"] == 134.5
        assert created["net_amount"] == 1100.0
        assert "_id" not in created

        if method == "cash":
            assert created["payee_name"] == payload["payee_name"]
            assert created["check_number"] is None
            assert created["transfer_number"] is None
            assert created["transfer_to"] is None
        elif method == "check":
            assert created["payee_name"] == payload["payee_name"]
            assert created["check_number"] == payload["check_number"]
            assert created["transfer_number"] is None
            assert created["transfer_to"] is None
        else:
            assert created["payee_name"] is None
            assert created["check_number"] is None
            assert created["transfer_number"] == payload["transfer_number"]
            assert created["transfer_to"] == payload["transfer_to"]


# Module: /api/expenses persistence - create -> get verification
def test_expense_create_then_get_persists_same_values(api_client, base_url, admin_headers, created_expense_ids):
    payload = _build_expense_payload("check")
    create_response = api_client.post(f"{base_url}/api/expenses", headers=admin_headers, json=payload)
    assert create_response.status_code == 200, create_response.text
    created = create_response.json()
    created_expense_ids.append(created["id"])

    get_response = api_client.get(f"{base_url}/api/expenses/{created['id']}", headers=admin_headers)
    assert get_response.status_code == 200, get_response.text
    fetched = get_response.json()

    assert fetched["id"] == created["id"]
    assert fetched["expense_number"] == payload["expense_number"]
    assert fetched["payment_method"] == "check"
    assert fetched["check_number"] == payload["check_number"]
    assert fetched["bank_id"] == "industrial-development"
    assert fetched["issued_at"] == payload["issued_at"]
    assert fetched["responsible_employee"] == payload["responsible_employee"]
    assert "_id" not in fetched


# Module: /api/expenses delete -> get returns 404
def test_expense_delete_then_get_returns_404(api_client, base_url, admin_headers):
    payload = _build_expense_payload("bank_transfer")
    create_response = api_client.post(f"{base_url}/api/expenses", headers=admin_headers, json=payload)
    assert create_response.status_code == 200, create_response.text
    created_id = create_response.json()["id"]

    delete_response = api_client.delete(f"{base_url}/api/expenses/{created_id}", headers=admin_headers)
    assert delete_response.status_code == 200, delete_response.text

    get_response = api_client.get(f"{base_url}/api/expenses/{created_id}", headers=admin_headers)
    assert get_response.status_code == 404
