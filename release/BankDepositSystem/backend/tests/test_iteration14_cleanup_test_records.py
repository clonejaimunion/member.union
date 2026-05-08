"""Iteration 14 cleanup: remove UI-created TEST_FOCUS_UI reconciliation records."""

import os

import pytest
import requests


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Admin@123"
BANK_IDS = ["industrial-development", "banque-misr", "agricultural-bank"]


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
    payload = login.json()
    token = payload.get("token")
    if not token:
        if payload.get("requires_2fa"):
            pytest.skip("Admin account requires 2FA; skipping cleanup")
        pytest.skip("No auth token from login")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# Module: reconciliation test-data hygiene for UI testing leftovers
def test_cleanup_and_verify_no_test_focus_ui_records(api_client, base_url, admin_headers):
    deleted_ids = []

    for bank_id in BANK_IDS:
        listing = api_client.get(f"{base_url}/api/banks/{bank_id}/reconciliations", headers=admin_headers)
        assert listing.status_code == 200, listing.text
        records = listing.json()

        for item in records:
            if str(item.get("period_label", "")).startswith("TEST_FOCUS_UI"):
                delete = api_client.delete(
                    f"{base_url}/api/banks/{bank_id}/reconciliations/{item['id']}",
                    headers=admin_headers,
                )
                assert delete.status_code == 200, delete.text
                deleted_ids.append(item["id"])

    for bank_id in BANK_IDS:
        recheck = api_client.get(f"{base_url}/api/banks/{bank_id}/reconciliations", headers=admin_headers)
        assert recheck.status_code == 200, recheck.text
        leftover = [
            row
            for row in recheck.json()
            if str(row.get("period_label", "")).startswith("TEST_FOCUS_UI")
        ]
        assert leftover == []
