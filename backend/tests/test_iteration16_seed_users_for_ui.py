"""Iteration 16 setup: ensure stable UI permission users exist."""

import os
import pytest
import requests


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Admin@123"
ENTRY_PASSWORD = "UserPass@123"
VIEW_USER = "TEST_view_exp_ui16"
MANAGE_USER = "TEST_manage_exp_ui16"


def _permissions(
    enter_deposits=False,
    view_reports=False,
    edit_deposits=False,
    manage_users=False,
    manage_reconciliations=False,
    manage_revenues=False,
    manage_expenses=False,
):
    return {
        "enter_deposits": enter_deposits,
        "view_reports": view_reports,
        "edit_deposits": edit_deposits,
        "manage_users": manage_users,
        "manage_reconciliations": manage_reconciliations,
        "manage_revenues": manage_revenues,
        "manage_expenses": manage_expenses,
    }


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


# Module: seed deterministic users for UI permission checks in this iteration
def test_seed_view_and_manage_expense_users(api_client, base_url, admin_headers):
    users_resp = api_client.get(f"{base_url}/api/admin/users", headers=admin_headers)
    assert users_resp.status_code == 200, users_resp.text
    by_username = {user["username"]: user for user in users_resp.json()}

    desired = {
        VIEW_USER: _permissions(view_reports=True),
        MANAGE_USER: _permissions(view_reports=True, manage_expenses=True),
    }

    for username, perms in desired.items():
        existing = by_username.get(username)
        if existing:
            update_resp = api_client.put(
                f"{base_url}/api/admin/users/{existing['id']}",
                headers=admin_headers,
                json={"password": ENTRY_PASSWORD, "permissions": perms, "is_active": True},
            )
            assert update_resp.status_code == 200, update_resp.text
        else:
            create_resp = api_client.post(
                f"{base_url}/api/admin/users",
                headers=admin_headers,
                json={
                    "username": username,
                    "password": ENTRY_PASSWORD,
                    "permissions": perms,
                    "is_active": True,
                },
            )
            assert create_resp.status_code == 200, create_resp.text
