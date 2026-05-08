"""Iteration 18 cleanup: remove TEST ITER18 / TEST_UI expense rows created during API/UI checks."""

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


# Module: cleanup iteration 18 temporary expenses from report/voucher testing
def test_cleanup_iteration18_temp_expenses(api_client, base_url, admin_headers):
    list_response = api_client.get(f"{base_url}/api/expenses", headers=admin_headers)
    assert list_response.status_code == 200, list_response.text
    expenses = list_response.json()

    deleted = 0
    for item in expenses:
        marker_fields = [
            (item.get("gross_statement") or ""),
            (item.get("payee_name") or ""),
            (item.get("transfer_to") or ""),
        ]
        marker_text = " | ".join(marker_fields).upper()
        if "TEST ITER18" in marker_text or "TEST_UI" in marker_text:
            delete_resp = api_client.delete(f"{base_url}/api/expenses/{item['id']}", headers=admin_headers)
            assert delete_resp.status_code in (200, 404), delete_resp.text
            if delete_resp.status_code == 200:
                deleted += 1

    verify_response = api_client.get(f"{base_url}/api/expenses", headers=admin_headers)
    assert verify_response.status_code == 200, verify_response.text
    for item in verify_response.json():
        marker_check = " | ".join(
            [
                (item.get("gross_statement") or ""),
                (item.get("payee_name") or ""),
                (item.get("transfer_to") or ""),
            ]
        ).upper()
        assert "TEST ITER18" not in marker_check
        assert "TEST_UI" not in marker_check

    assert isinstance(deleted, int)
