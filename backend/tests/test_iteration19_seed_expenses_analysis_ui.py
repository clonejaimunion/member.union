"""Iteration 19 UI seed: create temporary expenses for expenses-analysis frontend checks."""

import os
import uuid

import pytest
import requests


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")


@pytest.fixture(scope="module")
def base_url():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL is not set")
    return BASE_URL.rstrip("/")


@pytest.fixture(scope="module")
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def admin_headers(api_client, base_url):
    login = api_client.post(
        f"{base_url}/api/auth/login",
        json={"username": "admin", "password": "Admin@123"},
    )
    if login.status_code != 200:
        pytest.skip(f"Admin login failed: {login.status_code}")
    token = login.json().get("token")
    if not token:
        pytest.skip("No admin token returned")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _payload(expense_number: str, statement: str, amount: float, scope: str):
    return {
        "expense_number": expense_number,
        "organization_scope": scope,
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
        "gross_amount": amount,
        "gross_statement": f"TEST ITER19 {statement}",
        "deductions": [],
        "issued_at": "2031-04-15",
        "responsible_employee": "يوسف عبدالغني",
    }


# Module: /api/expenses seed records for category classification and organization filtering in UI
def test_seed_iteration19_ui_records(api_client, base_url, admin_headers):
    suffix = str(uuid.uuid4().int % 10000).zfill(4)
    data = [
        (f"93{suffix}1", "منحة شهرية", 500.0, "general_union"),
        (f"93{suffix}2", "بدل حضور جلسات مجلس الادارة", 400.0, "general_union"),
        (f"93{suffix}3", "بدل انتقال", 300.0, "general_union"),
        (f"93{suffix}4", "بدل اعباء", 600.0, "general_union"),
        (f"93{suffix}5", "قطع غيار وصيانة", 700.0, "general_union"),
        (f"93{suffix}6", "اتعاب مراجعة ميزانية", 500.0, "general_union"),
        (f"93{suffix}7", "منحة خارج نطاق الجهة", 999.0, "social_solidarity_project"),
    ]

    created = 0
    for expense_number, statement, amount, scope in data:
        response = api_client.post(
            f"{base_url}/api/expenses",
            headers=admin_headers,
            json=_payload(expense_number, statement, amount, scope),
        )
        assert response.status_code == 200, response.text
        assert "id" in response.json()
        created += 1

    assert created == 7
