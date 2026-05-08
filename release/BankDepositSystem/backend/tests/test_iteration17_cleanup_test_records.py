"""Iteration 17 cleanup: remove temporary expense records created during UI checks."""

import os

import pytest
import requests


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Admin@123"


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
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )
    if login.status_code != 200:
        pytest.skip(f"Admin login failed: {login.status_code}")
    token = login.json().get("token")
    if not token:
        pytest.skip("No admin token returned")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# Module: cleanup temporary expense rows with TEST markers used in iteration 17
def test_cleanup_iteration17_test_expenses(api_client, base_url, admin_headers):
    expenses_response = api_client.get(f"{base_url}/api/expenses", headers=admin_headers)
    assert expenses_response.status_code == 200, expenses_response.text
    expenses = expenses_response.json()

    deleted_count = 0
    for expense in expenses:
        markers = [
            (expense.get("gross_statement", "") or ""),
            (expense.get("payee_name", "") or ""),
            (expense.get("transfer_to", "") or ""),
        ]
        marker_text = " | ".join(markers).upper()
        if "TEST ITER17" in marker_text or "TEST UI" in marker_text:
            delete_resp = api_client.delete(f"{base_url}/api/expenses/{expense['id']}", headers=admin_headers)
            assert delete_resp.status_code in (200, 404), delete_resp.text
            if delete_resp.status_code == 200:
                deleted_count += 1

    verify_response = api_client.get(f"{base_url}/api/expenses", headers=admin_headers)
    assert verify_response.status_code == 200, verify_response.text
    assert all(
        "TEST ITER17" not in ((item.get("gross_statement", "") or "").upper())
        and "TEST UI" not in ((item.get("gross_statement", "") or "").upper())
        and "TEST UI" not in ((item.get("payee_name", "") or "").upper())
        and "TEST UI" not in ((item.get("transfer_to", "") or "").upper())
        for item in verify_response.json()
    )

    assert isinstance(deleted_count, int)
