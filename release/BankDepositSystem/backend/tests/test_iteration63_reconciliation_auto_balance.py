import os
import uuid

import pytest
import requests
from dotenv import dotenv_values


# Modules/features under test: reconciliation auto-balance breakdown, save semantics, and data-flow validity
FRONTEND_ENV = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or FRONTEND_ENV.get("REACT_APP_BACKEND_URL") or "").rstrip("/")


@pytest.fixture(scope="session")
def base_url():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL is not configured")
    return BASE_URL


@pytest.fixture(scope="session")
def session_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


def _login(base_url: str, session_client: requests.Session, username: str, password: str, organization_id: str):
    return session_client.post(
        f"{base_url}/api/auth/login",
        json={"username": username, "password": password, "organization_id": organization_id},
        timeout=40,
    )


@pytest.fixture(scope="session")
def admin_headers(base_url, session_client):
    response = _login(base_url, session_client, "admin", "Admin@123", "social-solidarity")
    if response.status_code != 200:
        pytest.skip(f"super admin login failed: {response.status_code} {response.text}")
    token = response.json().get("token")
    if not token:
        pytest.skip("missing super admin token")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture
def created_reconciliation_ids():
    state = {"ids": []}
    yield state


def _assert_breakdown_formula(breakdown: dict):
    opening_balance = round(float(breakdown.get("opening_balance") or 0), 2)
    monthly_revenues = round(float(breakdown.get("monthly_revenues") or 0), 2)
    deposit_settlements = round(float(breakdown.get("deposit_settlements") or 0), 2)
    checks_under_collection = round(float(breakdown.get("checks_under_collection") or 0), 2)
    gross_total = round(float(breakdown.get("gross_total") or 0), 2)
    book_balance = round(float(breakdown.get("book_balance") or 0), 2)
    monthly_expenses = round(float(breakdown.get("monthly_expenses") or 0), 2)
    checks_not_presented = round(float(breakdown.get("checks_not_presented") or 0), 2)
    bank_expenses = round(float(breakdown.get("bank_expenses") or 0), 2)
    reconciliation_balance = round(float(breakdown.get("reconciliation_balance") or 0), 2)

    expected_gross = round(opening_balance + monthly_revenues + deposit_settlements, 2)
    expected_book = round(expected_gross - monthly_expenses - bank_expenses, 2)
    expected_reconciliation = round(expected_book + checks_not_presented - checks_under_collection, 2)

    assert gross_total == expected_gross
    assert book_balance == expected_book
    assert reconciliation_balance == expected_reconciliation


def test_login_sets_http_only_cookie(base_url, session_client):
    response = _login(base_url, session_client, "admin", "Admin@123", "social-solidarity")
    assert response.status_code == 200, response.text
    set_cookie = response.headers.get("set-cookie", "")
    assert "access_token=" in set_cookie
    assert "HttpOnly" in set_cookie


def test_get_reconciliation_balance_returns_required_breakdown_and_exact_formula(base_url, session_client, admin_headers):
    response = session_client.get(
        f"{base_url}/api/banks/banque-misr/reconciliation-balance",
        headers=admin_headers,
        params={"period_label": "فبراير 2026"},
        timeout=60,
    )
    assert response.status_code == 200, response.text
    data = response.json()

    required_fields = [
        "opening_balance",
        "monthly_revenues",
        "deposit_settlements",
        "checks_under_collection",
        "gross_total",
        "monthly_expenses",
        "checks_not_presented",
        "bank_expenses",
        "reconciliation_balance",
    ]
    for field_name in required_fields:
        assert field_name in data

    _assert_breakdown_formula(data)


def test_create_reconciliation_ignores_payload_book_balance_and_persists_breakdown(
    base_url,
    session_client,
    admin_headers,
    created_reconciliation_ids,
):
    period_label = f"فبراير 2026 TEST ITER63 {uuid.uuid4().hex[:6]}"
    breakdown_response = session_client.get(
        f"{base_url}/api/banks/banque-misr/reconciliation-balance",
        headers=admin_headers,
        params={"period_label": period_label},
        timeout=60,
    )
    assert breakdown_response.status_code == 200, breakdown_response.text
    breakdown = breakdown_response.json()

    payload = {
        "period_label": period_label,
        "administration": "مشروع التكافل الاجتماعي",
        "book_balance": 99999999,
        "bank_statement_balance": float(breakdown["book_balance"]) + 10 - 5,
        "outstanding_checks": [
            {"check_number": "123456", "amount": 10, "check_date": "2026-02-05T00:00:00Z"}
        ],
        "collection_checks": [
            {"check_number": "654321", "amount": 5, "check_date": "2026-02-06T00:00:00Z"}
        ],
    }

    create_response = session_client.post(
        f"{base_url}/api/banks/banque-misr/reconciliations",
        headers=admin_headers,
        json=payload,
        timeout=60,
    )
    assert create_response.status_code == 200, create_response.text
    created = create_response.json()
    created_reconciliation_ids["ids"].append(created["id"])

    assert round(float(created["book_balance"]), 2) == round(float(breakdown["book_balance"]), 2)
    assert round(float(created["calculated_balance"]), 2) == round(float(breakdown["book_balance"]) + 10 - 5, 2)
    assert created.get("balance_breakdown") is not None
    _assert_breakdown_formula(created["balance_breakdown"])

    get_response = session_client.get(
        f"{base_url}/api/banks/banque-misr/reconciliations/{created['id']}",
        headers=admin_headers,
        timeout=60,
    )
    assert get_response.status_code == 200, get_response.text
    persisted = get_response.json()
    assert persisted["id"] == created["id"]
    assert persisted.get("balance_breakdown") is not None
    _assert_breakdown_formula(persisted["balance_breakdown"])


def test_calculated_balance_equals_auto_computed_book_balance_without_double_count(
    base_url,
    session_client,
    admin_headers,
    created_reconciliation_ids,
):
    period_label = f"مارس 2026 TEST ITER63 {uuid.uuid4().hex[:6]}"
    breakdown_response = session_client.get(
        f"{base_url}/api/banks/banque-misr/reconciliation-balance",
        headers=admin_headers,
        params={"period_label": period_label},
        timeout=60,
    )
    assert breakdown_response.status_code == 200, breakdown_response.text
    breakdown = breakdown_response.json()

    outstanding_value = 500
    collection_value = 150
    payload = {
        "period_label": period_label,
        "administration": "مشروع التكافل الاجتماعي",
        "book_balance": 1,
        "bank_statement_balance": float(breakdown["reconciliation_balance"]),
        "outstanding_checks": [
            {"check_number": "777001", "amount": outstanding_value, "check_date": "2026-03-10T00:00:00Z"}
        ],
        "collection_checks": [
            {"check_number": "777002", "amount": collection_value, "check_date": "2026-03-11T00:00:00Z"}
        ],
    }

    create_response = session_client.post(
        f"{base_url}/api/banks/banque-misr/reconciliations",
        headers=admin_headers,
        json=payload,
        timeout=60,
    )
    assert create_response.status_code == 200, create_response.text
    created = create_response.json()
    created_reconciliation_ids["ids"].append(created["id"])

    auto_book_balance = round(float(breakdown["book_balance"]), 2)
    final_formula_value = round(auto_book_balance + outstanding_value - collection_value, 2)

    assert round(float(created["book_balance"]), 2) == auto_book_balance
    assert round(float(created["calculated_balance"]), 2) == final_formula_value


def test_update_reconciliation_keeps_auto_balance_and_breakdown(
    base_url,
    session_client,
    admin_headers,
    created_reconciliation_ids,
):
    period_label = f"أبريل 2026 TEST ITER63 {uuid.uuid4().hex[:6]}"
    breakdown_response = session_client.get(
        f"{base_url}/api/banks/banque-misr/reconciliation-balance",
        headers=admin_headers,
        params={"period_label": period_label},
        timeout=60,
    )
    assert breakdown_response.status_code == 200, breakdown_response.text
    breakdown = breakdown_response.json()

    create_response = session_client.post(
        f"{base_url}/api/banks/banque-misr/reconciliations",
        headers=admin_headers,
        json={
            "period_label": period_label,
            "administration": "مشروع التكافل الاجتماعي",
            "book_balance": 123,
            "bank_statement_balance": float(breakdown["reconciliation_balance"]),
            "outstanding_checks": [],
            "collection_checks": [],
        },
        timeout=60,
    )
    assert create_response.status_code == 200, create_response.text
    created = create_response.json()
    created_reconciliation_ids["ids"].append(created["id"])

    update_response = session_client.put(
        f"{base_url}/api/banks/banque-misr/reconciliations/{created['id']}",
        headers=admin_headers,
        json={
            "period_label": period_label,
            "administration": "مشروع التكافل الاجتماعي",
            "book_balance": 888888,
            "bank_statement_balance": float(breakdown["reconciliation_balance"]),
            "outstanding_checks": [],
            "collection_checks": [],
        },
        timeout=60,
    )
    assert update_response.status_code == 200, update_response.text
    updated = update_response.json()
    assert round(float(updated["book_balance"]), 2) == round(float(breakdown["book_balance"]), 2)
    assert updated.get("balance_breakdown") is not None


def test_admin_data_flow_validation_stays_valid(base_url, session_client, admin_headers):
    response = session_client.get(f"{base_url}/api/admin/data-flow-validation", headers=admin_headers, timeout=80)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload.get("is_valid") is True
    assert isinstance(payload.get("organizations"), list)


def test_cleanup_created_reconciliations(base_url, session_client, admin_headers, created_reconciliation_ids):
    for reconciliation_id in created_reconciliation_ids["ids"]:
        response = session_client.delete(
            f"{base_url}/api/banks/banque-misr/reconciliations/{reconciliation_id}",
            headers=admin_headers,
            timeout=60,
        )
        assert response.status_code in [200, 404], response.text