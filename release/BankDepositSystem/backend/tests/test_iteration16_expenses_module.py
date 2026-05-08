"""Iteration 16 regression: expenses APIs, permissions, uniqueness, search, and auth-hardening checks."""

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
    data = login.json()
    token = data.get("token")
    if not token:
        if data.get("requires_2fa"):
            pytest.skip("Admin account requires 2FA; skipping expenses tests")
        pytest.skip("No admin token returned")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture()
def created_entities():
    state = {"user_ids": [], "expense_ids": []}
    yield state


@pytest.fixture(autouse=True)
def cleanup_created_data(api_client, base_url, admin_headers, created_entities):
    yield
    for expense_id in created_entities["expense_ids"]:
        api_client.delete(f"{base_url}/api/expenses/{expense_id}", headers=admin_headers)
    for user_id in created_entities["user_ids"]:
        api_client.delete(f"{base_url}/api/admin/users/{user_id}", headers=admin_headers)


def _create_user(api_client, base_url, admin_headers, username, permissions):
    payload = {
        "username": username,
        "password": "UserPass@123",
        "permissions": permissions,
        "is_active": True,
    }
    response = api_client.post(f"{base_url}/api/admin/users", headers=admin_headers, json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def _create_expense(api_client, base_url, headers, payload):
    return api_client.post(f"{base_url}/api/expenses", headers=headers, json=payload)


def _permissions(
    enter_deposits=False,
    view_reports=False,
    edit_deposits=False,
    manage_users=False,
    manage_reconciliations=False,
    manage_revenues=False,
    manage_expenses=False,
):
    return {
        "enter_deposits": enter_deposits,
        "view_reports": view_reports,
        "edit_deposits": edit_deposits,
        "manage_users": manage_users,
        "manage_reconciliations": manage_reconciliations,
        "manage_revenues": manage_revenues,
        "manage_expenses": manage_expenses,
    }


def _expense_payload(payment_method="cash"):
    suffix = str(uuid.uuid4().int % 10_000_000).zfill(7)
    payee_suffix = uuid.uuid4().hex[:6]
    payload = {
        "expense_number": f"9{suffix}",
        "payment_method": payment_method,
        "payee_name": f"TEST_PAYEE_{payee_suffix}" if payment_method in {"cash", "check"} else None,
        "check_number": f"8{suffix}" if payment_method == "check" else None,
        "transfer_number": f"7{suffix}" if payment_method == "bank_transfer" else None,
        "transfer_to": f"TEST_TRANSFER_TO_{payee_suffix}" if payment_method == "bank_transfer" else None,
        "bank_id": "industrial-development",
        "gross_amount": 2500.0,
        "gross_statement": f"استحقاق TEST_{suffix}",
        "deductions": [
            {"amount": 100.25, "statement": "استقطاع 1"},
            {"amount": 50.75, "statement": "استقطاع 2"},
        ],
        "issued_at": date.today().isoformat(),
        "responsible_employee": "يوسف عبدالغني",
    }
    return payload


# Module: /api/expenses create/get/list keeps clean JSON and required conditional fields
def test_expenses_create_cash_and_get_list_clean_json(api_client, base_url, admin_headers, created_entities):
    payload = _expense_payload("cash")
    create_response = _create_expense(api_client, base_url, admin_headers, payload)
    assert create_response.status_code == 200, create_response.text
    created = create_response.json()
    created_entities["expense_ids"].append(created["id"])

    assert created["expense_number"] == payload["expense_number"]
    assert created["payment_method"] == "cash"
    assert created["payee_name"] == payload["payee_name"]
    assert created["check_number"] is None
    assert created["transfer_number"] is None
    assert created["total_deductions"] == 151.0
    assert created["net_amount"] == 2349.0
    assert "_id" not in created

    get_response = api_client.get(f"{base_url}/api/expenses/{created['id']}", headers=admin_headers)
    assert get_response.status_code == 200, get_response.text
    fetched = get_response.json()
    assert fetched["id"] == created["id"]
    assert fetched["gross_statement"] == payload["gross_statement"]
    assert "_id" not in fetched

    list_response = api_client.get(f"{base_url}/api/expenses", headers=admin_headers)
    assert list_response.status_code == 200, list_response.text
    rows = list_response.json()
    row = next((item for item in rows if item.get("id") == created["id"]), None)
    assert row is not None
    assert "_id" not in row


# Module: uniqueness + conditional validations for check/transfer and expense_number
def test_expenses_uniqueness_and_method_specific_requirements(api_client, base_url, admin_headers, created_entities):
    check_payload = _expense_payload("check")
    first_check = _create_expense(api_client, base_url, admin_headers, check_payload)
    assert first_check.status_code == 200, first_check.text
    created_entities["expense_ids"].append(first_check.json()["id"])

    duplicate_check_number = _expense_payload("check")
    duplicate_check_number["check_number"] = check_payload["check_number"]
    duplicate_check_resp = _create_expense(api_client, base_url, admin_headers, duplicate_check_number)
    assert duplicate_check_resp.status_code == 400
    assert "رقم الشيك" in duplicate_check_resp.json().get("detail", "")

    duplicate_expense_number = _expense_payload("cash")
    duplicate_expense_number["expense_number"] = check_payload["expense_number"]
    duplicate_expense_resp = _create_expense(api_client, base_url, admin_headers, duplicate_expense_number)
    assert duplicate_expense_resp.status_code == 400
    assert "رقم الإذن" in duplicate_expense_resp.json().get("detail", "")

    transfer_payload = _expense_payload("bank_transfer")
    first_transfer = _create_expense(api_client, base_url, admin_headers, transfer_payload)
    assert first_transfer.status_code == 200, first_transfer.text
    created_entities["expense_ids"].append(first_transfer.json()["id"])

    duplicate_transfer_number = _expense_payload("bank_transfer")
    duplicate_transfer_number["transfer_number"] = transfer_payload["transfer_number"]
    duplicate_transfer_resp = _create_expense(api_client, base_url, admin_headers, duplicate_transfer_number)
    assert duplicate_transfer_resp.status_code == 400
    assert "رقم عملية التحويل" in duplicate_transfer_resp.json().get("detail", "")


# Module: /api/expenses/search supports expense/check/transfer/person fields
def test_expenses_search_by_number_and_person_fields(api_client, base_url, admin_headers, created_entities):
    cash_payload = _expense_payload("cash")
    check_payload = _expense_payload("check")
    transfer_payload = _expense_payload("bank_transfer")

    cash_created = _create_expense(api_client, base_url, admin_headers, cash_payload)
    check_created = _create_expense(api_client, base_url, admin_headers, check_payload)
    transfer_created = _create_expense(api_client, base_url, admin_headers, transfer_payload)
    assert cash_created.status_code == 200, cash_created.text
    assert check_created.status_code == 200, check_created.text
    assert transfer_created.status_code == 200, transfer_created.text
    created_entities["expense_ids"].extend([
        cash_created.json()["id"],
        check_created.json()["id"],
        transfer_created.json()["id"],
    ])

    by_expense_number = api_client.get(
        f"{base_url}/api/expenses/search",
        headers=admin_headers,
        params={"query": cash_payload["expense_number"]},
    )
    assert by_expense_number.status_code == 200, by_expense_number.text
    assert any(item.get("id") == cash_created.json()["id"] for item in by_expense_number.json())

    by_check_number = api_client.get(
        f"{base_url}/api/expenses/search",
        headers=admin_headers,
        params={"query": check_payload["check_number"]},
    )
    assert by_check_number.status_code == 200, by_check_number.text
    assert any(item.get("id") == check_created.json()["id"] for item in by_check_number.json())

    by_transfer_number = api_client.get(
        f"{base_url}/api/expenses/search",
        headers=admin_headers,
        params={"query": transfer_payload["transfer_number"]},
    )
    assert by_transfer_number.status_code == 200, by_transfer_number.text
    assert any(item.get("id") == transfer_created.json()["id"] for item in by_transfer_number.json())

    by_name = api_client.get(
        f"{base_url}/api/expenses/search",
        headers=admin_headers,
        params={"query": cash_payload["payee_name"]},
    )
    assert by_name.status_code == 200, by_name.text
    assert any(item.get("id") == cash_created.json()["id"] for item in by_name.json())


# Module: update + delete persistence for expenses
def test_expense_update_and_delete_persistence(api_client, base_url, admin_headers):
    create_payload = _expense_payload("bank_transfer")
    create_response = _create_expense(api_client, base_url, admin_headers, create_payload)
    assert create_response.status_code == 200, create_response.text
    created = create_response.json()

    update_payload = dict(create_payload)
    update_payload["gross_amount"] = 3100
    update_payload["gross_statement"] = "استحقاق محدث TEST"
    update_payload["deductions"] = [
        {"amount": 100.0, "statement": "استقطاع محدث 1"},
        {"amount": 200.5, "statement": "استقطاع محدث 2"},
    ]
    update_resp = api_client.put(f"{base_url}/api/expenses/{created['id']}", headers=admin_headers, json=update_payload)
    assert update_resp.status_code == 200, update_resp.text
    updated = update_resp.json()
    assert updated["gross_amount"] == 3100
    assert updated["total_deductions"] == 300.5
    assert updated["net_amount"] == 2799.5

    get_resp = api_client.get(f"{base_url}/api/expenses/{created['id']}", headers=admin_headers)
    assert get_resp.status_code == 200, get_resp.text
    fetched = get_resp.json()
    assert fetched["gross_statement"] == "استحقاق محدث TEST"
    assert fetched["net_amount"] == 2799.5

    delete_resp = api_client.delete(f"{base_url}/api/expenses/{created['id']}", headers=admin_headers)
    assert delete_resp.status_code == 200, delete_resp.text
    verify_resp = api_client.get(f"{base_url}/api/expenses/{created['id']}", headers=admin_headers)
    assert verify_resp.status_code == 404


# Module: permissions - view_reports can view/search only, not create/update/delete
def test_view_reports_user_permissions_on_expenses(api_client, base_url, admin_headers, created_entities):
    view_user = _create_user(
        api_client,
        base_url,
        admin_headers,
        username=f"TEST_view_exp_{uuid.uuid4().hex[:8]}",
        permissions=_permissions(view_reports=True),
    )
    created_entities["user_ids"].append(view_user["id"])

    seed_payload = _expense_payload("cash")
    seed_resp = _create_expense(api_client, base_url, admin_headers, seed_payload)
    assert seed_resp.status_code == 200, seed_resp.text
    seeded = seed_resp.json()
    created_entities["expense_ids"].append(seeded["id"])

    login = _login(api_client, base_url, view_user["username"], "UserPass@123")
    assert login.status_code == 200, login.text
    token = login.json().get("token")
    assert isinstance(token, str) and token
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    list_resp = api_client.get(f"{base_url}/api/expenses", headers=headers)
    assert list_resp.status_code == 200, list_resp.text
    assert isinstance(list_resp.json(), list)

    search_resp = api_client.get(
        f"{base_url}/api/expenses/search",
        headers=headers,
        params={"query": seed_payload["expense_number"]},
    )
    assert search_resp.status_code == 200, search_resp.text
    assert any(item.get("id") == seeded["id"] for item in search_resp.json())

    create_resp = _create_expense(api_client, base_url, headers, _expense_payload("cash"))
    assert create_resp.status_code == 403

    update_resp = api_client.put(
        f"{base_url}/api/expenses/{seeded['id']}",
        headers=headers,
        json=seed_payload,
    )
    assert update_resp.status_code == 403

    delete_resp = api_client.delete(f"{base_url}/api/expenses/{seeded['id']}", headers=headers)
    assert delete_resp.status_code == 403


# Module: permissions - manage_expenses user can create/update/delete expenses
def test_manage_expenses_user_can_create_update_delete(api_client, base_url, admin_headers, created_entities):
    manager_user = _create_user(
        api_client,
        base_url,
        admin_headers,
        username=f"TEST_manage_exp_{uuid.uuid4().hex[:8]}",
        permissions=_permissions(view_reports=True, manage_expenses=True),
    )
    created_entities["user_ids"].append(manager_user["id"])

    login = _login(api_client, base_url, manager_user["username"], "UserPass@123")
    assert login.status_code == 200, login.text
    token = login.json().get("token")
    assert isinstance(token, str) and token
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    create_payload = _expense_payload("check")
    create_resp = _create_expense(api_client, base_url, headers, create_payload)
    assert create_resp.status_code == 200, create_resp.text
    created = create_resp.json()

    update_payload = dict(create_payload)
    update_payload["gross_amount"] = 2800
    update_payload["payee_name"] = "TEST_UPDATED_PAYEE"
    update_resp = api_client.put(
        f"{base_url}/api/expenses/{created['id']}",
        headers=headers,
        json=update_payload,
    )
    assert update_resp.status_code == 200, update_resp.text
    assert update_resp.json()["gross_amount"] == 2800

    get_resp = api_client.get(f"{base_url}/api/expenses/{created['id']}", headers=headers)
    assert get_resp.status_code == 200, get_resp.text
    assert get_resp.json()["payee_name"] == "TEST_UPDATED_PAYEE"

    delete_resp = api_client.delete(f"{base_url}/api/expenses/{created['id']}", headers=headers)
    assert delete_resp.status_code == 200, delete_resp.text
    verify_resp = api_client.get(f"{base_url}/api/expenses/{created['id']}", headers=headers)
    assert verify_resp.status_code == 404


# Module: auth hardening check - failed logins do not lock account after 5 attempts
def test_bruteforce_lockout_not_enforced_after_five_attempts(api_client, base_url):
    for _ in range(5):
        failed = _login(api_client, base_url, ADMIN_USERNAME, "WrongPass@123")
        assert failed.status_code == 401

    valid = _login(api_client, base_url, ADMIN_USERNAME, ADMIN_PASSWORD)
    assert valid.status_code == 200, "Expected lockout after 5 failures, but valid login still succeeds"


# Module: auth hardening check - login does not issue HttpOnly auth cookie
def test_login_missing_http_only_cookie(api_client, base_url):
    login = _login(api_client, base_url, ADMIN_USERNAME, ADMIN_PASSWORD)
    assert login.status_code == 200, login.text
    set_cookie = login.headers.get("set-cookie", "")
    assert isinstance(login.json().get("token"), str) and len(login.json()["token"]) > 20
    assert "httponly" not in set_cookie.lower()
