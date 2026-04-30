"""Regression tests for financial statements automation + auth safety checks."""

import os
from datetime import date

import pytest
import requests


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")

ORG_CREDENTIALS = {
    "general-union": {"username": "admin_union", "password": "Admin@123"},
    "social-solidarity": {"username": "admin_takaful", "password": "Admin@123"},
}

KNOWN_ERROR_TYPES = {
    "ميزان غير متوازن",
    "الميزانية غير متوازنة",
    "قيد غير متوازن",
    "سطر قيد بلا حساب",
    "سطر مدين ودائن معاً",
    "رصيد عكسي",
    "إهلاك أصل أكبر من تكلفته",
}


@pytest.fixture(scope="session")
def base_url():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL is not set")
    return BASE_URL.rstrip("/")


@pytest.fixture
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


def login(session: requests.Session, base_url: str, organization_id: str):
    creds = ORG_CREDENTIALS[organization_id]
    payload = {
        "username": creds["username"],
        "password": creds["password"],
        "organization_id": organization_id,
    }
    response = session.post(f"{base_url}/api/auth/login", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("token")
    assert body["user"]["organization_id"] == organization_id
    return response, body


# Auth playbook checks: httpOnly cookie + brute-force lockout + CORS preflight credentials
def test_auth_login_sets_httponly_cookie(api_client, base_url):
    login_response, _ = login(api_client, base_url, "general-union")
    set_cookie = login_response.headers.get("set-cookie", "")
    assert "access_token=" in set_cookie
    assert "HttpOnly" in set_cookie


def test_auth_bruteforce_lockout_after_five_failures(api_client, base_url):
    payload = {
        "username": "TEST_lockout_probe_user",
        "password": "WrongPass@123",
        "organization_id": "general-union",
    }
    statuses = []
    for _ in range(6):
        response = api_client.post(f"{base_url}/api/auth/login", json=payload)
        statuses.append(response.status_code)
    assert statuses[:5] == [401, 401, 401, 401, 401]
    assert statuses[5] == 429


def test_auth_preflight_has_credentials_headers(base_url):
    response = requests.options(
        f"{base_url}/api/auth/login",
        headers={
            "Origin": base_url,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,authorization",
        },
    )
    assert response.status_code in (200, 204)
    assert response.headers.get("access-control-allow-credentials") == "true"
    assert response.headers.get("access-control-allow-origin") not in (None, "")


# Financial statements coverage: automated extraction of 3 statements + accounting errors
@pytest.mark.parametrize("organization_id", ["general-union", "social-solidarity"])
def test_financial_statements_auto_returns_required_sections(api_client, base_url, organization_id):
    _, auth = login(api_client, base_url, organization_id)
    headers = {"Authorization": f"Bearer {auth['token']}"}

    response = api_client.get(f"{base_url}/api/financial-statements", headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["organization_id"] == organization_id
    assert "balance_sheet" in data
    assert "receipts_payments" in data
    assert "revenues_expenses" in data
    assert "accounting_errors" in data


@pytest.mark.parametrize("organization_id", ["general-union", "social-solidarity"])
def test_financial_statements_default_period_is_current_year(api_client, base_url, organization_id):
    _, auth = login(api_client, base_url, organization_id)
    headers = {"Authorization": f"Bearer {auth['token']}"}

    response = api_client.get(f"{base_url}/api/financial-statements", headers=headers)
    assert response.status_code == 200
    data = response.json()

    today = date.today()
    assert data["from_date"] == f"{today.year}-01-01"
    assert data["to_date"] == today.isoformat()


def test_financial_statements_period_override_works(api_client, base_url):
    _, auth = login(api_client, base_url, "general-union")
    headers = {"Authorization": f"Bearer {auth['token']}"}

    response = api_client.get(
        f"{base_url}/api/financial-statements?from_date=2026-01-01&to_date=2026-12-31",
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["from_date"] == "2026-01-01"
    assert data["to_date"] == "2026-12-31"


def test_balance_sheet_contains_required_totals_and_balance_gap(api_client, base_url):
    _, auth = login(api_client, base_url, "social-solidarity")
    headers = {"Authorization": f"Bearer {auth['token']}"}

    response = api_client.get(f"{base_url}/api/financial-statements", headers=headers)
    assert response.status_code == 200
    data = response.json()

    balance_sheet = data["balance_sheet"]
    for key in ["assets", "liabilities", "equity", "check"]:
        assert key in balance_sheet
        assert isinstance(balance_sheet[key]["lines"], list)
        assert isinstance(balance_sheet[key]["total"], (int, float))

    expected_gap = round(
        float(balance_sheet["assets"]["total"]) - (
            float(balance_sheet["liabilities"]["total"]) + float(balance_sheet["equity"]["total"])
        ),
        2,
    )
    assert round(float(balance_sheet["check"]["total"]), 2) == expected_gap


def test_receipts_and_payments_classification_is_consistent(api_client, base_url):
    _, auth = login(api_client, base_url, "social-solidarity")
    headers = {"Authorization": f"Bearer {auth['token']}"}

    response = api_client.get(f"{base_url}/api/financial-statements", headers=headers)
    assert response.status_code == 200
    data = response.json()

    receipts = data["receipts_payments"]["receipts"]["lines"]
    payments = data["receipts_payments"]["payments"]["lines"]

    for line in receipts:
        assert float(line.get("debit") or 0) > 0
        assert float(line.get("credit") or 0) >= 0
    for line in payments:
        assert float(line.get("credit") or 0) > 0
        assert float(line.get("debit") or 0) >= 0


def test_revenues_expenses_result_equals_revenue_minus_expense(api_client, base_url):
    _, auth = login(api_client, base_url, "general-union")
    headers = {"Authorization": f"Bearer {auth['token']}"}

    response = api_client.get(f"{base_url}/api/financial-statements", headers=headers)
    assert response.status_code == 200
    data = response.json()

    rev_total = float(data["revenues_expenses"]["revenues"]["total"])
    exp_total = float(data["revenues_expenses"]["expenses"]["total"])
    result_total = float(data["revenues_expenses"]["result"]["total"])
    assert round(rev_total - exp_total, 2) == round(result_total, 2)


def test_accounting_errors_payload_shape_and_known_types(api_client, base_url):
    _, auth = login(api_client, base_url, "general-union")
    headers = {"Authorization": f"Bearer {auth['token']}"}

    response = api_client.get(f"{base_url}/api/financial-statements", headers=headers)
    assert response.status_code == 200
    data = response.json()

    assert isinstance(data["accounting_errors"], list)
    for error in data["accounting_errors"]:
        assert error["severity"] in {"critical", "warning", "info"}
        assert isinstance(error["location"], str) and error["location"]
        assert isinstance(error["details"], str) and error["details"]
        assert isinstance(error["error_type"], str) and error["error_type"]
        assert error["error_type"] in KNOWN_ERROR_TYPES
