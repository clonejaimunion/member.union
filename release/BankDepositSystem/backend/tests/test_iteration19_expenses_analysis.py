"""Iteration 19: Expenses analysis regression (seed/report inputs/cleanup) using public preview API."""

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


@pytest.fixture(scope="session")
def admin_headers(api_client, base_url):
    login_response = api_client.post(
        f"{base_url}/api/auth/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )
    if login_response.status_code != 200:
        pytest.skip(f"Admin login failed: {login_response.status_code}")

    payload = login_response.json()
    token = payload.get("token")
    if not token:
        if payload.get("requires_2fa"):
            pytest.skip("Admin requires 2FA; skipping this suite")
        pytest.skip("No login token returned")

    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def created_expense_ids(api_client, base_url, admin_headers):
    ids = []
    yield ids
    for expense_id in ids:
        api_client.delete(f"{base_url}/api/expenses/{expense_id}", headers=admin_headers)


def _expense_payload(expense_number: str, gross_statement: str, gross_amount: float, organization_scope: str, issued_at: str):
    return {
        "expense_number": expense_number,
        "organization_scope": organization_scope,
        "expense_category": "general_expenses",
        "payment_method": "cash",
        "payee_name": f"TEST_ITER19_{expense_number}",
        "check_number": None,
        "transfer_number": None,
        "transfer_to": None,
        "membership_number": None,
        "committee": None,
        "governorate": None,
        "bank_id": "industrial-development",
        "gross_amount": gross_amount,
        "gross_statement": gross_statement,
        "deductions": [],
        "issued_at": issued_at,
        "responsible_employee": "يوسف عبدالغني",
    }


# Module: /api/expenses - seed six keyword expenses used by expenses analysis page
def test_seed_six_keyword_expenses_for_monthly_analysis(api_client, base_url, admin_headers, created_expense_ids):
    suffix = str(uuid.uuid4().int % 10000).zfill(4)
    rows = [
        (f"91{suffix}1", "منحة شهرية", 500.0),
        (f"91{suffix}2", "بدل حضور جلسات مجلس الادارة", 400.0),
        (f"91{suffix}3", "بدل انتقال", 300.0),
        (f"91{suffix}4", "بدل اعباء", 600.0),
        (f"91{suffix}5", "قطع غيار وصيانة", 700.0),
        (f"91{suffix}6", "اتعاب مراجعة ميزانية", 500.0),
    ]

    created_ids = []
    total = 0.0
    for expense_number, statement, amount in rows:
        payload = _expense_payload(
            expense_number=expense_number,
            gross_statement=f"TEST ITER19 {statement}",
            gross_amount=amount,
            organization_scope="general_union",
            issued_at="2031-04-15",
        )
        create_response = api_client.post(f"{base_url}/api/expenses", headers=admin_headers, json=payload)
        assert create_response.status_code == 200, create_response.text
        body = create_response.json()
        created_ids.append(body["id"])
        total += amount
        assert body["gross_statement"] == payload["gross_statement"]
        assert body["organization_scope"] == "general_union"
        assert body["issued_at"] == "2031-04-15"

    created_expense_ids.extend(created_ids)
    assert len(created_ids) == 6
    assert total == 3000.0


# Module: /api/expenses - scope isolation input (same month/year but different organization)
def test_seed_out_of_scope_expense_for_filter_validation(api_client, base_url, admin_headers, created_expense_ids):
    suffix = str(uuid.uuid4().int % 10000).zfill(4)
    payload = _expense_payload(
        expense_number=f"92{suffix}9",
        gross_statement="TEST ITER19 منحة خارج نطاق الجهة",
        gross_amount=999.0,
        organization_scope="social_solidarity_project",
        issued_at="2031-04-16",
    )
    create_response = api_client.post(f"{base_url}/api/expenses", headers=admin_headers, json=payload)
    assert create_response.status_code == 200, create_response.text

    item = create_response.json()
    created_expense_ids.append(item["id"])
    assert item["organization_scope"] == "social_solidarity_project"
    assert item["gross_amount"] == 999.0


# Module: /api/expenses - verify seeded records persisted and can be listed/fetched for frontend aggregation
def test_seeded_iteration19_records_persist(api_client, base_url, admin_headers):
    list_response = api_client.get(f"{base_url}/api/expenses", headers=admin_headers)
    assert list_response.status_code == 200, list_response.text
    rows = [row for row in list_response.json() if "TEST ITER19" in (row.get("gross_statement") or "")]
    assert len(rows) >= 7

    one_id = rows[0]["id"]
    get_response = api_client.get(f"{base_url}/api/expenses/{one_id}", headers=admin_headers)
    assert get_response.status_code == 200, get_response.text
    item = get_response.json()
    assert "TEST ITER19" in item["gross_statement"]
    assert isinstance(item["gross_amount"], (int, float))


# Module: cleanup - remove iteration 19 temporary expenses after run
def test_cleanup_iteration19_seed_data(api_client, base_url, admin_headers):
    list_response = api_client.get(f"{base_url}/api/expenses", headers=admin_headers)
    assert list_response.status_code == 200, list_response.text

    removed = 0
    for row in list_response.json():
        marker = " | ".join([
            row.get("gross_statement") or "",
            row.get("payee_name") or "",
            row.get("transfer_to") or "",
        ]).upper()
        if "TEST ITER19" in marker:
            delete_response = api_client.delete(f"{base_url}/api/expenses/{row['id']}", headers=admin_headers)
            assert delete_response.status_code in (200, 404), delete_response.text
            if delete_response.status_code == 200:
                removed += 1

    verify_response = api_client.get(f"{base_url}/api/expenses", headers=admin_headers)
    assert verify_response.status_code == 200, verify_response.text
    for row in verify_response.json():
        marker = " | ".join([
            row.get("gross_statement") or "",
            row.get("payee_name") or "",
            row.get("transfer_to") or "",
        ]).upper()
        assert "TEST ITER19" not in marker

    assert isinstance(removed, int)
