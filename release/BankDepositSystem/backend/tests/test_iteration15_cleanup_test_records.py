"""Iteration 15 cleanup: remove temporary TEST users and revenue records created during testing."""

import os

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
        pytest.skip("No admin token returned")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# Module: cleanup temporary users and TEST revenues created by iteration 15 checks
def test_cleanup_iteration15_temp_records(api_client, base_url, admin_headers):
    users_response = api_client.get(f"{base_url}/api/admin/users", headers=admin_headers)
    assert users_response.status_code == 200, users_response.text
    users = users_response.json()

    for user in users:
        username = str(user.get("username", ""))
        if username.startswith("TEST_"):
            delete_response = api_client.delete(
                f"{base_url}/api/admin/users/{user['id']}",
                headers=admin_headers,
            )
            assert delete_response.status_code in [200, 403, 404], delete_response.text

    revenues_response = api_client.get(f"{base_url}/api/revenues", headers=admin_headers)
    assert revenues_response.status_code == 200, revenues_response.text
    revenues = revenues_response.json()

    deleted = 0
    for item in revenues:
        supplier = str(item.get("supplier_name") or "")
        value_text = str(item.get("value") or "")
        receipt = str(item.get("receipt_number") or "")
        should_delete = (
            supplier.upper().startswith("TEST")
            or "TEST" in value_text.upper()
            or "اختبار" in value_text
            or receipt.startswith(("55", "56", "57", "58", "59"))
        )
        if should_delete:
            delete_response = api_client.delete(f"{base_url}/api/revenues/{item['id']}", headers=admin_headers)
            assert delete_response.status_code in [200, 404], delete_response.text
            deleted += 1

    verify_users = api_client.get(f"{base_url}/api/admin/users", headers=admin_headers)
    assert verify_users.status_code == 200
    leftovers_users = [u for u in verify_users.json() if str(u.get("username", "")).startswith("TEST_")]
    assert leftovers_users == []

    verify_revenues = api_client.get(f"{base_url}/api/revenues", headers=admin_headers)
    assert verify_revenues.status_code == 200
    leftovers_revenues = [
        r for r in verify_revenues.json()
        if str(r.get("supplier_name") or "").upper().startswith("TEST")
        or "TEST" in str(r.get("value") or "").upper()
    ]
    assert leftovers_revenues == []

    assert isinstance(deleted, int)
