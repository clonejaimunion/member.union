"""Iteration 18: expenses scope/category regression with death-benefit required fields and year grouping signals."""

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


@pytest.fixture(scope="session")
def admin_headers(api_client, base_url):
    login = api_client.post(
        f"{base_url}/api/auth/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )
    if login.status_code != 200:
        pytest.skip(f"Admin login failed: {login.status_code}")
    token = login.json().get("token")
    if not token:
        if login.json().get("requires_2fa"):
            pytest.skip("Admin requires 2FA; skipping API regression")
        pytest.skip("No admin token returned")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture()
def created_expense_ids(api_client, base_url, admin_headers):
    ids = []
    yield ids
    for expense_id in ids:
        api_client.delete(f"{base_url}/api/expenses/{expense_id}", headers=admin_headers)


def _expense_payload(
    *,
    expense_number: str,
    organization_scope: str,
    expense_category: str,
    payment_method: str = "cash",
    issued_at: str | None = None,
):
    payload = {
        "expense_number": expense_number,
        "organization_scope": organization_scope,
        "expense_category": expense_category,
        "payment_method": payment_method,
        "payee_name": f"TEST_UI_{expense_number}",
        "check_number": None,
        "transfer_number": None,
        "transfer_to": None,
        "membership_number": None,
        "committee": None,
        "governorate": None,
        "bank_id": "industrial-development",
        "gross_amount": 1500.0,
        "gross_statement": f"TEST ITER18 {expense_category} {organization_scope}",
        "deductions": [{"amount": 50.0, "statement": "استقطاع اختبار"}],
        "issued_at": issued_at or date.today().isoformat(),
        "responsible_employee": "يوسف عبدالغني",
    }

    if expense_category == "death_benefits":
        payload.update(
            {
                "membership_number": f"9{expense_number}",
                "committee": "لجنة اختبار",
                "governorate": "القاهرة",
            }
        )
    return payload


# Module: /api/expenses - scope/category persistence + death-benefit fields stored
def test_create_general_and_death_expenses_persist_fields(api_client, base_url, admin_headers, created_expense_ids):
    suffix = str(uuid.uuid4().int % 100000).zfill(5)
    general_payload = _expense_payload(
        expense_number=f"71{suffix}",
        organization_scope="general_union",
        expense_category="general_expenses",
    )
    death_payload = _expense_payload(
        expense_number=f"72{suffix}",
        organization_scope="social_solidarity_project",
        expense_category="death_benefits",
    )

    general_resp = api_client.post(f"{base_url}/api/expenses", headers=admin_headers, json=general_payload)
    death_resp = api_client.post(f"{base_url}/api/expenses", headers=admin_headers, json=death_payload)

    assert general_resp.status_code == 200, general_resp.text
    assert death_resp.status_code == 200, death_resp.text

    general = general_resp.json()
    death = death_resp.json()
    created_expense_ids.extend([general["id"], death["id"]])

    assert general["organization_scope"] == "general_union"
    assert general["expense_category"] == "general_expenses"
    assert general["membership_number"] is None
    assert general["committee"] is None
    assert general["governorate"] is None

    assert death["organization_scope"] == "social_solidarity_project"
    assert death["expense_category"] == "death_benefits"
    assert death["membership_number"] == death_payload["membership_number"]
    assert death["committee"] == death_payload["committee"]
    assert death["governorate"] == death_payload["governorate"]

    general_get = api_client.get(f"{base_url}/api/expenses/{general['id']}", headers=admin_headers)
    death_get = api_client.get(f"{base_url}/api/expenses/{death['id']}", headers=admin_headers)
    assert general_get.status_code == 200, general_get.text
    assert death_get.status_code == 200, death_get.text
    assert general_get.json()["expense_category"] == "general_expenses"
    assert death_get.json()["expense_category"] == "death_benefits"


# Module: /api/expenses - death benefits reject missing membership/committee/governorate
@pytest.mark.parametrize(
    "missing_field, expected_message",
    [
        ("membership_number", "رقم العضوية"),
        ("committee", "اللجنة"),
        ("governorate", "المحافظة"),
    ],
)
def test_death_benefits_require_all_member_fields(
    api_client,
    base_url,
    admin_headers,
    missing_field,
    expected_message,
):
    suffix = str(uuid.uuid4().int % 100000).zfill(5)
    payload = _expense_payload(
        expense_number=f"73{suffix}",
        organization_scope="social_solidarity_project",
        expense_category="death_benefits",
    )
    payload[missing_field] = ""

    response = api_client.post(f"{base_url}/api/expenses", headers=admin_headers, json=payload)
    assert response.status_code == 400, response.text
    assert expected_message in (response.json().get("detail") or "")


# Module: /api/expenses list data supports UI separation by category and year
def test_expenses_list_contains_year_and_category_for_ui_grouping(api_client, base_url, admin_headers, created_expense_ids):
    suffix = str(uuid.uuid4().int % 100000).zfill(5)
    payload_general_2024 = _expense_payload(
        expense_number=f"74{suffix}",
        organization_scope="general_union",
        expense_category="general_expenses",
        issued_at="2024-11-15",
    )
    payload_death_2025 = _expense_payload(
        expense_number=f"75{suffix}",
        organization_scope="social_solidarity_project",
        expense_category="death_benefits",
        issued_at="2025-03-10",
    )

    create_general = api_client.post(f"{base_url}/api/expenses", headers=admin_headers, json=payload_general_2024)
    create_death = api_client.post(f"{base_url}/api/expenses", headers=admin_headers, json=payload_death_2025)
    assert create_general.status_code == 200, create_general.text
    assert create_death.status_code == 200, create_death.text

    general_id = create_general.json()["id"]
    death_id = create_death.json()["id"]
    created_expense_ids.extend([general_id, death_id])

    list_resp = api_client.get(f"{base_url}/api/expenses", headers=admin_headers)
    assert list_resp.status_code == 200, list_resp.text
    rows = list_resp.json()

    general_row = next((row for row in rows if row.get("id") == general_id), None)
    death_row = next((row for row in rows if row.get("id") == death_id), None)
    assert general_row is not None
    assert death_row is not None

    assert general_row["expense_category"] == "general_expenses"
    assert str(general_row["issued_at"]).startswith("2024")
    assert death_row["expense_category"] == "death_benefits"
    assert str(death_row["issued_at"]).startswith("2025")
