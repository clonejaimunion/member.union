"""Regression tests for financial statements repair on legacy journal entry #5."""

import os

import pytest
import requests


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")

# Module scope: auth + financial statements + journal lines mapping for legacy entry repair.
ORG_CREDENTIALS = {
    "social-solidarity": {"username": "admin_takaful", "password": "Admin@123"},
    "general-union": {"username": "admin_union", "password": "Admin@123"},
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
    response = session.post(
        f"{base_url}/api/auth/login",
        json={
            "username": creds["username"],
            "password": creds["password"],
            "organization_id": organization_id,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert isinstance(body.get("token"), str) and body["token"]
    assert body["user"]["organization_id"] == organization_id
    return body["token"]


def test_social_2026_financial_statements_has_no_entry5_accounting_error(api_client, base_url):
    token = login(api_client, base_url, "social-solidarity")
    response = api_client.get(
        f"{base_url}/api/financial-statements?from_date=2026-01-01&to_date=2026-12-31",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    data = response.json()

    errors = data.get("accounting_errors", [])
    assert isinstance(errors, list)
    assert not any("قيد رقم 5" in (item.get("location") or "") for item in errors)


def test_social_2026_financial_statements_are_valid_and_balanced(api_client, base_url):
    token = login(api_client, base_url, "social-solidarity")
    response = api_client.get(
        f"{base_url}/api/financial-statements?from_date=2026-01-01&to_date=2026-12-31",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()

    assert data["is_accounting_valid"] is True
    assert len(data.get("accounting_errors", [])) == 0
    assert round(float(data["balance_sheet"]["check"]["total"]), 2) == 0.0


def test_social_journal_entry_5_legacy_lines_are_linked_to_expected_accounts(api_client, base_url):
    token = login(api_client, base_url, "social-solidarity")
    response = api_client.get(
        f"{base_url}/api/journal-entries?from_date=2026-01-01&to_date=2026-12-31",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    entries = response.json()
    assert isinstance(entries, list)

    entry_five = next((entry for entry in entries if int(entry.get("entry_number") or 0) == 5), None)
    assert entry_five is not None

    lines = entry_five.get("lines", [])
    bank_line = next((line for line in lines if line.get("account_name") == "بنك التنمية الصناعية"), None)
    revenue_line = next((line for line in lines if line.get("account_name") == "الإيرادات"), None)

    assert bank_line is not None
    assert bank_line.get("account_code") == "1101"
    assert bank_line.get("account_type") == "asset"

    assert revenue_line is not None
    assert revenue_line.get("account_code") == "4101"
    assert revenue_line.get("account_type") == "revenue"


def test_general_union_financial_statements_still_work_for_2026(api_client, base_url):
    token = login(api_client, base_url, "general-union")
    response = api_client.get(
        f"{base_url}/api/financial-statements?from_date=2026-01-01&to_date=2026-12-31",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["organization_id"] == "general-union"
    assert isinstance(data.get("balance_sheet", {}), dict)
    assert isinstance(data.get("accounting_errors", []), list)
