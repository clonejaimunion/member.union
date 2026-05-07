"""Auth playbook regression checks: hash format, cookies, CORS, and lockout."""

import os
import uuid

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient


FRONTEND_ENV = dotenv_values("/app/frontend/.env")
BACKEND_ENV = dotenv_values("/app/backend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or FRONTEND_ENV.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
MONGO_URL = (BACKEND_ENV.get("MONGO_URL") or "").strip('"')
DB_NAME = (BACKEND_ENV.get("DB_NAME") or "").strip('"')


def _headers():
    return {"Content-Type": "application/json"}


@pytest.fixture(scope="session")
def base_url():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL is not configured")
    return BASE_URL


# Modules/features: verify bcrypt hash format for seeded admin users.
def test_seed_admin_password_hash_uses_bcrypt_2b_prefix():
    if not MONGO_URL or not DB_NAME:
        pytest.skip("Mongo env not configured")
    client = MongoClient(MONGO_URL)
    try:
        user = client[DB_NAME].users.find_one(
            {"username": "admin", "$or": [{"role": "super_admin"}, {"is_super_admin": True}]},
            {"_id": 0, "password_hash": 1},
        )
        assert user is not None
        password_hash = str(user.get("password_hash") or "")
        assert password_hash.startswith("$2b$")
    finally:
        client.close()


# Modules/features: verify login sets secure session cookie flags for browser auth flow.
def test_login_sets_http_only_cookie(base_url):
    response = requests.post(
        f"{base_url}/api/auth/login",
        json={"username": "admin", "password": "Admin@123", "organization_id": "social-solidarity"},
        headers=_headers(),
        timeout=60,
    )
    assert response.status_code == 200, response.text
    set_cookie = response.headers.get("set-cookie", "")
    assert "access_token=" in set_cookie
    assert "HttpOnly" in set_cookie


# Modules/features: verify CORS preflight returns explicit origin with credentials.
def test_local_preflight_allows_explicit_origin_and_credentials():
    origin = "https://interest-calculator-12.preview.emergentagent.com"
    response = requests.options(
        "http://localhost:8001/api/auth/login",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,authorization",
        },
        timeout=60,
    )
    assert response.status_code in (200, 204), response.text
    assert response.headers.get("Access-Control-Allow-Origin") == origin
    assert response.headers.get("Access-Control-Allow-Credentials") == "true"


# Modules/features: verify brute-force lockout behavior (configured policy currently 3 failed attempts).
def test_lockout_triggers_after_three_failed_attempts(base_url):
    username = f"TEST_LOCK_{uuid.uuid4().hex[:8]}"
    payload = {"username": username, "password": "WrongPass@123", "organization_id": "social-solidarity"}

    first = requests.post(f"{base_url}/api/auth/login", json=payload, headers=_headers(), timeout=60)
    second = requests.post(f"{base_url}/api/auth/login", json=payload, headers=_headers(), timeout=60)
    third = requests.post(f"{base_url}/api/auth/login", json=payload, headers=_headers(), timeout=60)
    fourth = requests.post(f"{base_url}/api/auth/login", json=payload, headers=_headers(), timeout=60)

    assert first.status_code == 401
    assert second.status_code == 401
    assert third.status_code == 401
    assert fourth.status_code == 429
