"""Iteration 37: Validate global 2FA removal + auth playbook regression checks."""

import os
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient


# Env and clients for auth + packaging regression tests
frontend_env = dotenv_values("/app/frontend/.env")
backend_env = dotenv_values("/app/backend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL") or backend_env.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME") or backend_env.get("DB_NAME")


@pytest.fixture(scope="module")
def api_session():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL is missing")
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def mongo_db():
    if not MONGO_URL or not DB_NAME:
        pytest.skip("MONGO_URL/DB_NAME is missing")
    client = MongoClient(MONGO_URL)
    try:
        yield client[DB_NAME]
    finally:
        client.close()


def login(api_session, username: str, password: str, organization_id: str, otp_code: str | None = None):
    payload = {"username": username, "password": password, "organization_id": organization_id}
    if otp_code is not None:
        payload["otp_code"] = otp_code
    return api_session.post(f"{BASE_URL}/api/auth/login", json=payload, timeout=25)


# 2FA-disabled login behavior for super_admin across both orgs
@pytest.mark.parametrize("organization_id", ["general-union", "social-solidarity"])
def test_super_admin_login_returns_token_without_2fa(api_session, organization_id):
    response = login(api_session, "admin", "Admin@123", organization_id)
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload.get("token"), str) and payload["token"]
    assert payload.get("requires_2fa") is False
    assert payload.get("requires_2fa_setup") is False
    assert payload.get("user", {}).get("role") == "super_admin"


# OTP payload should be ignored when 2FA is globally disabled
def test_admin_union_login_does_not_require_otp_even_if_sent(api_session):
    response = login(api_session, "admin_union", "Admin@123", "general-union", otp_code="123456")
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload.get("token"), str) and payload["token"]
    assert payload.get("requires_2fa") is False
    assert payload.get("requires_2fa_setup") is False
    assert payload.get("user", {}).get("username") == "admin_union"


# DB migration guarantees all TOTP flags/secrets are cleared
def test_database_has_no_active_totp_fields(mongo_db):
    assert mongo_db.users.count_documents({"totp_enabled": True}) == 0
    assert mongo_db.users.count_documents({"totp_secret": {"$nin": [None, ""]}}) == 0
    assert mongo_db.users.count_documents({"totp_pending_secret": {"$nin": [None, ""]}}) == 0


# Disabled 2FA endpoints must return 410
def test_2fa_endpoints_return_410_with_cancellation_message(api_session):
    login_response = login(api_session, "admin_union", "Admin@123", "general-union")
    assert login_response.status_code == 200
    token = login_response.json().get("token")
    assert isinstance(token, str) and token

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    setup_response = api_session.post(f"{BASE_URL}/api/admin/2fa/setup", headers=headers, timeout=20)
    verify_response = api_session.post(
        f"{BASE_URL}/api/admin/2fa/verify",
        json={"otp_code": "000000"},
        headers=headers,
        timeout=20,
    )

    assert setup_response.status_code == 410
    assert "تم إلغاء المصادقة الثنائية" in setup_response.json().get("detail", "")
    assert verify_response.status_code == 410
    assert "تم إلغاء المصادقة الثنائية" in verify_response.json().get("detail", "")


# Login response should still set httpOnly session cookie
def test_login_sets_httponly_cookie(api_session):
    response = login(api_session, "admin", "Admin@123", "general-union")
    assert response.status_code == 200
    set_cookie = response.headers.get("set-cookie", "")
    assert "access_token=" in set_cookie
    assert "HttpOnly" in set_cookie


# CORS playbook: explicit origin + credentials must be allowed
def test_cors_preflight_allows_credentials_with_explicit_origin(api_session):
    origin = BASE_URL
    response = api_session.options(
        f"{BASE_URL}/api/auth/login",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
        timeout=20,
    )
    assert response.status_code in [200, 204]
    assert response.headers.get("access-control-allow-credentials") == "true"
    allowed_origin = response.headers.get("access-control-allow-origin", "")
    assert allowed_origin and allowed_origin != "*"


# Brute-force lockout after 5 failed attempts
def test_bruteforce_lockout_after_five_failures(api_session, mongo_db):
    username = "admin_union"
    org_id = "general-union"
    identifier = f"{org_id}:{username}"

    mongo_db.login_attempts.delete_many({"identifier": identifier})
    for _ in range(5):
        failed = login(api_session, username, "WrongPass@123", org_id)
        assert failed.status_code == 401

    locked = login(api_session, username, "WrongPass@123", org_id)
    assert locked.status_code == 429
    assert "تم إيقاف تسجيل الدخول" in locked.json().get("detail", "")

    mongo_db.login_attempts.delete_many({"identifier": identifier})


# Packaging artifacts: setup.exe exists and no 2FA reset helper remains
def test_setup_exe_and_release_cleanup_files():
    setup_path = Path("/app/dist/BankDepositSystemSetup.exe")
    assert setup_path.exists()
    assert setup_path.stat().st_size > 0
    assert not Path("/app/release/BankDepositSystem/reset_super_admin_2fa.bat").exists()
    assert not Path("/app/release/BankDepositSystem/backend/reset_super_admin_2fa.py").exists()


# Release bundle must not contain OTP/2FA strings in JS assets
def test_release_js_has_no_otp_or_google_authenticator_strings():
    build_root = Path("/app/release/BankDepositSystem/frontend/build/static/js")
    assert build_root.exists()
    js_files = list(build_root.glob("*.js"))
    assert js_files

    forbidden_strings = [
        "Google Authenticator",
        "otp_code",
        "requires_2fa",
        "requires_2fa_setup",
        "المصادقة الثنائية",
        "رمز التحقق",
    ]

    combined = "\n".join(file.read_text(encoding="utf-8", errors="ignore") for file in js_files)
    for marker in forbidden_strings:
        assert marker not in combined


# Playbook auth hash check: admin passwords should be bcrypt $2b$
def test_seed_admin_accounts_use_bcrypt_2b_prefix(mongo_db):
    for username in ["admin", "admin_union", "admin_takaful"]:
        doc = mongo_db.users.find_one({"username": username}, {"_id": 0, "password_hash": 1})
        assert doc and isinstance(doc.get("password_hash"), str)
        assert doc["password_hash"].startswith("$2b$")
