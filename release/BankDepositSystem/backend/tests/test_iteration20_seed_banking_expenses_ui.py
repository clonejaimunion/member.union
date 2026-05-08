"""Iteration 20 seed/cleanup for banking-expenses UI validation."""

import json
import os
import uuid
from datetime import date

import pytest
import requests


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Admin@123"
BANK_ID = "industrial-development"
SEED_FILE = "/app/test_reports/iter20_banking_ui_seed_ids.json"


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
    token = login_response.json().get("token")
    if not token:
        if login_response.json().get("requires_2fa"):
            pytest.skip("Admin requires 2FA; skipping seed")
        pytest.skip("No admin token returned")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _marker():
    return f"TEST ITER20 UI BANKING {uuid.uuid4().hex[:8]}"


# Module: /api/revenues + /api/expenses - create deterministic rows for banking-expenses status controls
def test_seed_banking_expenses_ui_rows(api_client, base_url, admin_headers):
    marker = _marker()
    suffix = str(uuid.uuid4().int % 100000).zfill(5)
    today = date.today().isoformat()

    revenue_payment_order = {
        "receipt_number": f"85{suffix}",
        "amount": 1500,
        "collection_method": "payment_order",
        "supplier_name": None,
        "check_number": None,
        "payment_order_number": f"75{suffix}",
        "bank_id": BANK_ID,
        "dated": today,
        "value": marker,
        "issued_at": today,
        "responsible_employee": "يوسف عبدالغني",
        "bank_collection_status": "under_collection",
    }
    revenue_check = {
        "receipt_number": f"86{suffix}",
        "amount": 1700,
        "collection_method": "check",
        "supplier_name": None,
        "check_number": f"76{suffix}",
        "payment_order_number": None,
        "bank_id": BANK_ID,
        "dated": today,
        "value": marker,
        "issued_at": today,
        "responsible_employee": "دعاء علي",
        "bank_collection_status": "under_collection",
    }
    expense_check = {
        "expense_number": f"87{suffix}",
        "organization_scope": "general_union",
        "expense_category": "general_expenses",
        "payment_method": "check",
        "payee_name": marker,
        "check_number": f"77{suffix}",
        "transfer_number": None,
        "transfer_to": None,
        "membership_number": None,
        "committee": None,
        "governorate": None,
        "bank_id": BANK_ID,
        "gross_amount": 10000,
        "gross_statement": marker,
        "deductions": [],
        "issued_at": today,
        "responsible_employee": "يوسف عبدالغني",
        "bank_payment_status": "not_presented",
    }

    payment_resp = api_client.post(f"{base_url}/api/revenues", headers=admin_headers, json=revenue_payment_order)
    check_resp = api_client.post(f"{base_url}/api/revenues", headers=admin_headers, json=revenue_check)
    expense_resp = api_client.post(f"{base_url}/api/expenses", headers=admin_headers, json=expense_check)

    assert payment_resp.status_code == 200, payment_resp.text
    assert check_resp.status_code == 200, check_resp.text
    assert expense_resp.status_code == 200, expense_resp.text

    payload = {
        "marker": marker,
        "revenues": [payment_resp.json()["id"], check_resp.json()["id"]],
        "expenses": [expense_resp.json()["id"]],
    }
    with open(SEED_FILE, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)

    list_rev = api_client.get(f"{base_url}/api/revenues", headers=admin_headers)
    assert list_rev.status_code == 200, list_rev.text
    saved_revs = [row for row in list_rev.json() if row.get("id") in payload["revenues"]]
    assert len(saved_revs) == 2

    list_exp = api_client.get(f"{base_url}/api/expenses", headers=admin_headers)
    assert list_exp.status_code == 200, list_exp.text
    saved_exps = [row for row in list_exp.json() if row.get("id") in payload["expenses"]]
    assert len(saved_exps) == 1


# Module: cleanup - remove iteration 20 UI seed rows created for banking-expenses checks
def test_cleanup_banking_expenses_ui_rows(api_client, base_url, admin_headers):
    if not os.path.exists(SEED_FILE):
        pytest.skip("No seed file found for cleanup")

    with open(SEED_FILE, "r", encoding="utf-8") as handle:
        seed_payload = json.load(handle)

    for revenue_id in seed_payload.get("revenues", []):
        response = api_client.delete(f"{base_url}/api/revenues/{revenue_id}", headers=admin_headers)
        assert response.status_code in (200, 404), response.text

    for expense_id in seed_payload.get("expenses", []):
        response = api_client.delete(f"{base_url}/api/expenses/{expense_id}", headers=admin_headers)
        assert response.status_code in (200, 404), response.text

    if os.path.exists(SEED_FILE):
        os.remove(SEED_FILE)
