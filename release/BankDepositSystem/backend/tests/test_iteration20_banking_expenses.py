"""Iteration 20: Banking expenses APIs regression on public preview endpoint."""

import os
import uuid
from datetime import date

import pytest
import requests


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Admin@123"
BANK_ID = "industrial-development"


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
    login_response = api_client.post(
        f"{base_url}/api/auth/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )
    if login_response.status_code != 200:
        pytest.skip(f"Admin login failed: {login_response.status_code}")

    body = login_response.json()
    token = body.get("token")
    if not token:
        if body.get("requires_2fa"):
            pytest.skip("Admin requires 2FA; skipping iteration 20 suite")
        pytest.skip("No auth token returned")

    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture()
def created_ids(api_client, base_url, admin_headers):
    tracker = {"revenues": [], "expenses": []}
    yield tracker
    for revenue_id in tracker["revenues"]:
        api_client.delete(f"{base_url}/api/revenues/{revenue_id}", headers=admin_headers)
    for expense_id in tracker["expenses"]:
        api_client.delete(f"{base_url}/api/expenses/{expense_id}", headers=admin_headers)


@pytest.fixture()
def manual_state_backup(api_client, base_url, admin_headers):
    target_year = date.today().year
    target_month = date.today().month
    get_response = api_client.get(
        f"{base_url}/api/banking-expenses/manual",
        headers=admin_headers,
        params={"bank_id": BANK_ID, "year": target_year, "month": target_month},
    )
    assert get_response.status_code == 200, get_response.text
    original = get_response.json()
    yield original
    restore_payload = {
        "bank_id": BANK_ID,
        "year": target_year,
        "month": target_month,
        "stamp": original.get("stamp", 0),
        "bank_correspondence": original.get("bank_correspondence", 0),
        "correspondence_safekeeping": original.get("correspondence_safekeeping", 0),
        "internal_transfer_fee": original.get("internal_transfer_fee", 0),
        "external_transfer_fee": original.get("external_transfer_fee", 0),
    }
    api_client.put(f"{base_url}/api/banking-expenses/manual", headers=admin_headers, json=restore_payload)


def _revenue_payload(method: str, suffix: str):
    return {
        "receipt_number": f"83{suffix}",
        "amount": 1200,
        "collection_method": method,
        "supplier_name": "TEST_ITER20_SUPPLIER" if method == "cash" else None,
        "check_number": f"62{suffix}" if method == "check" else None,
        "payment_order_number": f"73{suffix}" if method == "payment_order" else None,
        "bank_id": BANK_ID,
        "dated": date.today().isoformat(),
        "value": "TEST ITER20 revenue",
        "issued_at": date.today().isoformat(),
        "responsible_employee": "يوسف عبدالغني",
        "bank_collection_status": None,
    }


def _expense_payload(method: str, suffix: str):
    return {
        "expense_number": f"84{suffix}",
        "organization_scope": "general_union",
        "expense_category": "general_expenses",
        "payment_method": method,
        "payee_name": "TEST_ITER20_PAYEE" if method in ["cash", "check"] else None,
        "check_number": f"64{suffix}" if method == "check" else None,
        "transfer_number": f"95{suffix}" if method == "bank_transfer" else None,
        "transfer_to": "TEST ITER20 BENEFICIARY" if method == "bank_transfer" else None,
        "membership_number": None,
        "committee": None,
        "governorate": None,
        "bank_id": BANK_ID,
        "gross_amount": 1000,
        "gross_statement": "TEST ITER20 expense",
        "deductions": [{"amount": 100, "statement": "خصم اختبار"}],
        "issued_at": date.today().isoformat(),
        "responsible_employee": "يوسف عبدالغني",
        "bank_payment_status": None,
    }


# Module: /api/banking-expenses/manual - save + fetch persistence for manual charges
def test_banking_manual_charges_save_and_get(api_client, base_url, admin_headers, manual_state_backup):
    payload = {
        "bank_id": BANK_ID,
        "year": date.today().year,
        "month": date.today().month,
        "stamp": 11.25,
        "bank_correspondence": 22.5,
        "correspondence_safekeeping": 33.75,
        "internal_transfer_fee": 44,
        "external_transfer_fee": 55,
    }
    save_response = api_client.put(f"{base_url}/api/banking-expenses/manual", headers=admin_headers, json=payload)
    assert save_response.status_code == 200, save_response.text
    saved = save_response.json()
    assert saved["bank_id"] == BANK_ID
    assert saved["stamp"] == 11.25
    assert saved["bank_correspondence"] == 22.5

    get_response = api_client.get(
        f"{base_url}/api/banking-expenses/manual",
        headers=admin_headers,
        params={"bank_id": BANK_ID, "year": date.today().year, "month": date.today().month},
    )
    assert get_response.status_code == 200, get_response.text
    fetched = get_response.json()
    assert fetched["correspondence_safekeeping"] == 33.75
    assert fetched["internal_transfer_fee"] == 44
    assert fetched["external_transfer_fee"] == 55


# Module: /api/revenues + /api/revenues/{id}/banking-status - payment order status update persists
def test_revenue_payment_order_banking_status_update(api_client, base_url, admin_headers, created_ids):
    suffix = str(uuid.uuid4().int % 100000).zfill(5)
    create_response = api_client.post(
        f"{base_url}/api/revenues",
        headers=admin_headers,
        json=_revenue_payload("payment_order", suffix),
    )
    assert create_response.status_code == 200, create_response.text
    created = create_response.json()
    created_ids["revenues"].append(created["id"])
    assert created["collection_method"] == "payment_order"
    assert created["bank_collection_status"] == "under_collection"

    patch_response = api_client.patch(
        f"{base_url}/api/revenues/{created['id']}/banking-status",
        headers=admin_headers,
        json={"bank_collection_status": "collected"},
    )
    assert patch_response.status_code == 200, patch_response.text
    patched = patch_response.json()
    assert patched["bank_collection_status"] == "collected"

    get_response = api_client.get(f"{base_url}/api/revenues/{created['id']}", headers=admin_headers)
    assert get_response.status_code == 200, get_response.text
    assert get_response.json()["bank_collection_status"] == "collected"


# Module: /api/revenues/{id}/banking-status - reject cash revenue for banking status updates
def test_revenue_banking_status_rejects_cash_method(api_client, base_url, admin_headers, created_ids):
    suffix = str(uuid.uuid4().int % 100000).zfill(5)
    create_response = api_client.post(
        f"{base_url}/api/revenues",
        headers=admin_headers,
        json=_revenue_payload("cash", suffix),
    )
    assert create_response.status_code == 200, create_response.text
    created = create_response.json()
    created_ids["revenues"].append(created["id"])
    assert created["collection_method"] == "cash"

    patch_response = api_client.patch(
        f"{base_url}/api/revenues/{created['id']}/banking-status",
        headers=admin_headers,
        json={"bank_collection_status": "collected"},
    )
    assert patch_response.status_code == 400, patch_response.text
    detail = patch_response.json().get("detail") or ""
    assert "للشيكات" in detail or "أوامر الدفع" in detail


# Module: /api/expenses + /api/expenses/{id}/banking-status - check status update persists
def test_expense_check_banking_status_update(api_client, base_url, admin_headers, created_ids):
    suffix = str(uuid.uuid4().int % 100000).zfill(5)
    create_response = api_client.post(
        f"{base_url}/api/expenses",
        headers=admin_headers,
        json=_expense_payload("check", suffix),
    )
    assert create_response.status_code == 200, create_response.text
    created = create_response.json()
    created_ids["expenses"].append(created["id"])
    assert created["payment_method"] == "check"
    assert created["bank_payment_status"] == "not_presented"

    patch_response = api_client.patch(
        f"{base_url}/api/expenses/{created['id']}/banking-status",
        headers=admin_headers,
        json={"bank_payment_status": "paid"},
    )
    assert patch_response.status_code == 200, patch_response.text
    patched = patch_response.json()
    assert patched["bank_payment_status"] == "paid"

    get_response = api_client.get(f"{base_url}/api/expenses/{created['id']}", headers=admin_headers)
    assert get_response.status_code == 200, get_response.text
    assert get_response.json()["bank_payment_status"] == "paid"


# Module: /api/expenses/{id}/banking-status - reject non-check expense updates
def test_expense_banking_status_rejects_cash_method(api_client, base_url, admin_headers, created_ids):
    suffix = str(uuid.uuid4().int % 100000).zfill(5)
    create_response = api_client.post(
        f"{base_url}/api/expenses",
        headers=admin_headers,
        json=_expense_payload("cash", suffix),
    )
    assert create_response.status_code == 200, create_response.text
    created = create_response.json()
    created_ids["expenses"].append(created["id"])
    assert created["payment_method"] == "cash"

    patch_response = api_client.patch(
        f"{base_url}/api/expenses/{created['id']}/banking-status",
        headers=admin_headers,
        json={"bank_payment_status": "paid"},
    )
    assert patch_response.status_code == 400, patch_response.text
    assert "للشيكات" in (patch_response.json().get("detail") or "")
