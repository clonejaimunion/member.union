"""Iteration 15 regression: revenues APIs, permissions, uniqueness, search, and auth-hardening checks."""

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
            pytest.skip("Admin account requires 2FA; skipping revenues tests")
        pytest.skip("No admin token returned")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture()
def created_entities():
    state = {"user_ids": [], "revenue_ids": []}
    yield state


@pytest.fixture(autouse=True)
def cleanup_created_data(api_client, base_url, admin_headers, created_entities):
    yield
    for revenue_id in created_entities["revenue_ids"]:
        api_client.delete(f"{base_url}/api/revenues/{revenue_id}", headers=admin_headers)
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


def _create_revenue(api_client, base_url, headers, payload):
    return api_client.post(f"{base_url}/api/revenues", headers=headers, json=payload)


def _revenue_payload(collection_method="cash"):
    suffix = str(uuid.uuid4().int % 10_000_000).zfill(7)
    supplier_suffix = uuid.uuid4().hex[:6]
    payload = {
        "receipt_number": f"9{suffix}",
        "amount": 1500.75,
        "collection_method": collection_method,
        "supplier_name": f"TEST_SUPPLIER_{supplier_suffix}" if collection_method == "cash" else None,
        "check_number": f"8{suffix}" if collection_method == "check" else None,
        "payment_order_number": f"7{suffix}" if collection_method == "payment_order" else None,
        "bank_id": "industrial-development",
        "dated": date.today().isoformat(),
        "value": f"قيمة اختبار TEST_{suffix} 123",
        "issued_at": date.today().isoformat(),
        "responsible_employee": "يوسف عبدالغني",
    }
    return payload


# Module: /api/revenues create/list/get keeps clean JSON and persisted values
def test_revenues_create_get_list_with_clean_json(api_client, base_url, admin_headers, created_entities):
    payload = _revenue_payload("cash")
    create_response = _create_revenue(api_client, base_url, admin_headers, payload)
    assert create_response.status_code == 200, create_response.text
    created = create_response.json()
    created_entities["revenue_ids"].append(created["id"])

    assert created["receipt_number"] == payload["receipt_number"]
    assert created["supplier_name"] == payload["supplier_name"]
    assert created["collection_method"] == "cash"
    assert "_id" not in created

    get_response = api_client.get(f"{base_url}/api/revenues/{created['id']}", headers=admin_headers)
    assert get_response.status_code == 200, get_response.text
    fetched = get_response.json()
    assert fetched["id"] == created["id"]
    assert fetched["value"] == payload["value"]
    assert "_id" not in fetched

    list_response = api_client.get(f"{base_url}/api/revenues", headers=admin_headers)
    assert list_response.status_code == 200, list_response.text
    items = list_response.json()
    row = next((item for item in items if item.get("id") == created["id"]), None)
    assert row is not None
    assert "_id" not in row


# Module: uniqueness constraints for receipt/check/payment_order numbers
def test_revenues_uniqueness_constraints(api_client, base_url, admin_headers, created_entities):
    cash_payload = _revenue_payload("cash")
    first = _create_revenue(api_client, base_url, admin_headers, cash_payload)
    assert first.status_code == 200, first.text
    created_entities["revenue_ids"].append(first.json()["id"])

    duplicate_receipt_payload = _revenue_payload("cash")
    duplicate_receipt_payload["receipt_number"] = cash_payload["receipt_number"]
    duplicate_receipt = _create_revenue(api_client, base_url, admin_headers, duplicate_receipt_payload)
    assert duplicate_receipt.status_code == 400
    assert "رقم الإذن" in duplicate_receipt.json().get("detail", "")

    check_payload = _revenue_payload("check")
    check_first = _create_revenue(api_client, base_url, admin_headers, check_payload)
    assert check_first.status_code == 200, check_first.text
    created_entities["revenue_ids"].append(check_first.json()["id"])

    duplicate_check_payload = _revenue_payload("check")
    duplicate_check_payload["check_number"] = check_payload["check_number"]
    duplicate_check = _create_revenue(api_client, base_url, admin_headers, duplicate_check_payload)
    assert duplicate_check.status_code == 400
    assert "رقم الشيك" in duplicate_check.json().get("detail", "")

    po_payload = _revenue_payload("payment_order")
    po_first = _create_revenue(api_client, base_url, admin_headers, po_payload)
    assert po_first.status_code == 200, po_first.text
    created_entities["revenue_ids"].append(po_first.json()["id"])

    duplicate_po_payload = _revenue_payload("payment_order")
    duplicate_po_payload["payment_order_number"] = po_payload["payment_order_number"]
    duplicate_po = _create_revenue(api_client, base_url, admin_headers, duplicate_po_payload)
    assert duplicate_po.status_code == 400
    assert "رقم أمر الدفع" in duplicate_po.json().get("detail", "")


# Module: /api/revenues/search supports supplier/check/payment order queries
def test_revenues_search_by_supplier_check_and_payment_order(api_client, base_url, admin_headers, created_entities):
    cash_payload = _revenue_payload("cash")
    check_payload = _revenue_payload("check")
    po_payload = _revenue_payload("payment_order")

    cash_created = _create_revenue(api_client, base_url, admin_headers, cash_payload)
    check_created = _create_revenue(api_client, base_url, admin_headers, check_payload)
    po_created = _create_revenue(api_client, base_url, admin_headers, po_payload)
    assert cash_created.status_code == 200, cash_created.text
    assert check_created.status_code == 200, check_created.text
    assert po_created.status_code == 200, po_created.text
    created_entities["revenue_ids"].extend([
        cash_created.json()["id"],
        check_created.json()["id"],
        po_created.json()["id"],
    ])

    by_supplier = api_client.get(
        f"{base_url}/api/revenues/search",
        headers=admin_headers,
        params={"query": cash_payload["supplier_name"]},
    )
    assert by_supplier.status_code == 200, by_supplier.text
    supplier_result = by_supplier.json()
    assert any(item.get("id") == cash_created.json()["id"] for item in supplier_result)

    by_check = api_client.get(
        f"{base_url}/api/revenues/search",
        headers=admin_headers,
        params={"query": check_payload["check_number"]},
    )
    assert by_check.status_code == 200, by_check.text
    check_result = by_check.json()
    assert any(item.get("id") == check_created.json()["id"] for item in check_result)

    by_po = api_client.get(
        f"{base_url}/api/revenues/search",
        headers=admin_headers,
        params={"query": po_payload["payment_order_number"]},
    )
    assert by_po.status_code == 200, by_po.text
    po_result = by_po.json()
    assert any(item.get("id") == po_created.json()["id"] for item in po_result)


# Module: permissions - view_reports can view/search only, not create
def test_view_reports_user_permissions_on_revenues(api_client, base_url, admin_headers, created_entities):
    view_user = _create_user(
        api_client,
        base_url,
        admin_headers,
        username=f"TEST_view_{uuid.uuid4().hex[:8]}",
        permissions={
            "enter_deposits": False,
            "view_reports": True,
            "edit_deposits": False,
            "manage_users": False,
            "manage_reconciliations": False,
            "manage_revenues": False,
        },
    )
    created_entities["user_ids"].append(view_user["id"])
    login = _login(api_client, base_url, view_user["username"], "UserPass@123")
    assert login.status_code == 200, login.text
    token = login.json().get("token")
    assert isinstance(token, str) and token
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    list_response = api_client.get(f"{base_url}/api/revenues", headers=headers)
    assert list_response.status_code == 200, list_response.text
    assert isinstance(list_response.json(), list)

    search_response = api_client.get(f"{base_url}/api/revenues/search", headers=headers, params={"query": "TEST"})
    assert search_response.status_code == 200, search_response.text
    assert isinstance(search_response.json(), list)

    create_response = _create_revenue(api_client, base_url, headers, _revenue_payload("cash"))
    assert create_response.status_code == 403


# Module: permissions - enter_deposits user can create/update/delete revenues
def test_enter_deposits_user_can_create_update_delete_revenue(api_client, base_url, admin_headers, created_entities):
    entry_user = _create_user(
        api_client,
        base_url,
        admin_headers,
        username=f"TEST_entry_{uuid.uuid4().hex[:8]}",
        permissions={
            "enter_deposits": True,
            "view_reports": True,
            "edit_deposits": False,
            "manage_users": False,
            "manage_reconciliations": False,
            "manage_revenues": False,
        },
    )
    created_entities["user_ids"].append(entry_user["id"])
    login = _login(api_client, base_url, entry_user["username"], "UserPass@123")
    assert login.status_code == 200, login.text
    token = login.json().get("token")
    assert isinstance(token, str) and token
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    create_payload = _revenue_payload("payment_order")
    create_response = _create_revenue(api_client, base_url, headers, create_payload)
    assert create_response.status_code == 200, create_response.text
    created = create_response.json()

    update_payload = dict(create_payload)
    update_payload["amount"] = 1888.25
    update_payload["value"] = "قيمة محدثة TEST"
    update_response = api_client.put(f"{base_url}/api/revenues/{created['id']}", headers=headers, json=update_payload)
    assert update_response.status_code == 200, update_response.text
    updated = update_response.json()
    assert updated["amount"] == 1888.25
    assert updated["value"] == "قيمة محدثة TEST"

    get_response = api_client.get(f"{base_url}/api/revenues/{created['id']}", headers=headers)
    assert get_response.status_code == 200, get_response.text
    fetched = get_response.json()
    assert fetched["amount"] == 1888.25

    delete_response = api_client.delete(f"{base_url}/api/revenues/{created['id']}", headers=headers)
    assert delete_response.status_code == 200, delete_response.text
    verify_deleted = api_client.get(f"{base_url}/api/revenues/{created['id']}", headers=headers)
    assert verify_deleted.status_code == 404


# Module: auth hardening check - failed logins do not lock account after 5 attempts (expected to fail requirement)
def test_bruteforce_lockout_not_enforced_after_five_attempts(api_client, base_url):
    for _ in range(5):
        failed = _login(api_client, base_url, ADMIN_USERNAME, "WrongPass@123")
        assert failed.status_code == 401

    valid = _login(api_client, base_url, ADMIN_USERNAME, ADMIN_PASSWORD)
    assert valid.status_code == 200, "Expected lockout after 5 failures, but valid login still succeeds"


# Module: auth hardening check - login does not issue HttpOnly cookie
def test_login_missing_http_only_cookie(api_client, base_url):
    login = _login(api_client, base_url, ADMIN_USERNAME, ADMIN_PASSWORD)
    assert login.status_code == 200, login.text
    set_cookie = login.headers.get("set-cookie", "")
    assert isinstance(login.json().get("token"), str) and len(login.json()["token"]) > 20
    assert "access_token" not in set_cookie.lower()
    assert "bank_auth_token" not in set_cookie.lower()
    assert "session" not in set_cookie.lower()
