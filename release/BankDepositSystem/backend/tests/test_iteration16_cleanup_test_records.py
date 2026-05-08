"""Iteration 16 cleanup: remove temporary TEST_* expenses and TEST_* users."""

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


# Module: cleanup temporary expense and user data for this and prior TEST runs
def test_cleanup_test_users_and_expenses(api_client, base_url, admin_headers):
    users_response = api_client.get(f"{base_url}/api/admin/users", headers=admin_headers)
    assert users_response.status_code == 200, users_response.text
    users = users_response.json()

    deleted_users = 0
    for user in users:
        username = user.get("username", "")
        role = user.get("role")
        if role == "admin":
            continue
        if username.startswith("TEST_") or username.startswith("ui_") or username.startswith("entryuser"):
            delete_resp = api_client.delete(f"{base_url}/api/admin/users/{user['id']}", headers=admin_headers)
            assert delete_resp.status_code in (200, 404), delete_resp.text
            if delete_resp.status_code == 200:
                deleted_users += 1

    expenses_response = api_client.get(f"{base_url}/api/expenses", headers=admin_headers)
    assert expenses_response.status_code == 200, expenses_response.text
    expenses = expenses_response.json()

    deleted_expenses = 0
    for expense in expenses:
        markers = [
            expense.get("gross_statement", ""),
            expense.get("payee_name", "") or "",
            expense.get("transfer_to", "") or "",
        ]
        if any("TEST_" in marker for marker in markers):
            delete_resp = api_client.delete(f"{base_url}/api/expenses/{expense['id']}", headers=admin_headers)
            assert delete_resp.status_code in (200, 404), delete_resp.text
            if delete_resp.status_code == 200:
                deleted_expenses += 1

    verify_users = api_client.get(f"{base_url}/api/admin/users", headers=admin_headers)
    assert verify_users.status_code == 200, verify_users.text
    assert all(
        user.get("role") == "admin"
        or not (
            user.get("username", "").startswith("TEST_")
            or user.get("username", "").startswith("ui_")
            or user.get("username", "").startswith("entryuser")
        )
        for user in verify_users.json()
    )

    verify_expenses = api_client.get(f"{base_url}/api/expenses", headers=admin_headers)
    assert verify_expenses.status_code == 200, verify_expenses.text
    assert all(
        "TEST_" not in (expense.get("gross_statement", ""))
        and "TEST_" not in (expense.get("payee_name", "") or "")
        and "TEST_" not in (expense.get("transfer_to", "") or "")
        for expense in verify_expenses.json()
    )

    assert isinstance(deleted_users, int)
    assert isinstance(deleted_expenses, int)
