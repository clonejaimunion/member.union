"""Core smoke regression for requested accounting endpoints."""

import os

import pytest
import requests
from dotenv import dotenv_values


FRONTEND_ENV = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or FRONTEND_ENV.get("REACT_APP_BACKEND_URL") or "").rstrip("/")


def _headers(token: str | None = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


@pytest.fixture(scope="session")
def base_url():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL is not configured")
    return BASE_URL


@pytest.fixture(scope="session")
def admin_token(base_url):
    response = requests.post(
        f"{base_url}/api/auth/login",
        json={"username": "admin", "password": "Admin@123", "organization_id": "social-solidarity"},
        headers=_headers(),
        timeout=60,
    )
    if response.status_code != 200:
        pytest.skip(f"admin login failed: {response.status_code} {response.text}")
    token = response.json().get("token")
    if not token:
        pytest.skip("admin token missing")
    return token


# Modules/features: requested smoke flow coverage for revenues, expenses, ledger, trial-balance, financial-statements, deposits list.
@pytest.mark.parametrize(
    "path,params,expected_type",
    [
        ("/api/revenues", {"bank_id": "industrial-development"}, list),
        ("/api/expenses", {"bank_id": "industrial-development"}, list),
        ("/api/ledger", {"account_id": "all"}, dict),
        ("/api/trial-balance", {"non_zero_only": "true"}, dict),
        ("/api/financial-statements", {}, dict),
        ("/api/banks/industrial-development/deposits", {}, list),
    ],
)
def test_core_smoke_endpoints_return_200_and_valid_shape(base_url, admin_token, path, params, expected_type):
    response = requests.get(
        f"{base_url}{path}",
        params=params,
        headers=_headers(admin_token),
        timeout=90,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert isinstance(body, expected_type)
