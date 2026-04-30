"""Iteration 34: super-admin login shadowing regression + auth playbook checks."""

# Module: Authentication (super-admin cross-organization login)
# Feature: Shadow-admin regression and security playbook checks

import os
import uuid
from pathlib import Path
from urllib.parse import urlparse

import bcrypt
import jwt
import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient


ENV_BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
FILE_BASE_URL = dotenv_values("/app/frontend/.env").get("REACT_APP_BACKEND_URL")
BASE_URL = (ENV_BASE_URL or FILE_BASE_URL or "").rstrip("/")

BACKEND_ENV = dotenv_values("/app/backend/.env")
MONGO_URL = os.environ.get("MONGO_URL") or BACKEND_ENV.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME") or BACKEND_ENV.get("DB_NAME")
JWT_SECRET = os.environ.get("JWT_SECRET") or BACKEND_ENV.get("JWT_SECRET")
CORS_ORIGINS = [item.strip() for item in (os.environ.get("CORS_ORIGINS") or BACKEND_ENV.get("CORS_ORIGINS") or "").split(",") if item.strip()]


def _json_headers():
    return {"Content-Type": "application/json"}


def _login(username: str, password: str, organization_id: str):
    return requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": username, "password": password, "organization_id": organization_id},
        headers=_json_headers(),
        timeout=30,
    )


def _assert_login_success_or_2fa(response: requests.Response, selected_org: str):
    assert response.status_code == 200
    payload = response.json()
    message = payload.get("message", "")
    assert "اسم المستخدم أو كلمة المرور غير صحيحة" not in message

    if payload.get("requires_2fa") is True:
        assert isinstance(payload.get("temp_token"), str)
        decoded = jwt.decode(payload["temp_token"], JWT_SECRET, algorithms=["HS256"])
        assert decoded.get("role") == "super_admin"
        assert decoded.get("organization_id") == selected_org
    else:
        assert isinstance(payload.get("token"), str)
        assert payload.get("user", {}).get("role") == "super_admin"
        assert payload.get("user", {}).get("organization_id") == selected_org


@pytest.fixture(scope="session", autouse=True)
def _require_envs():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL is not configured")
    if not MONGO_URL or not DB_NAME:
        pytest.skip("MONGO_URL/DB_NAME is not configured")
    if not JWT_SECRET:
        pytest.skip("JWT_SECRET is not configured")


@pytest.fixture
def mongo_db():
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    try:
        yield db
    finally:
        client.close()


def test_super_admin_login_general_union_admin_password_works():
    response = _login("admin", "Admin@123", "general-union")
    _assert_login_success_or_2fa(response, "general-union")


def test_super_admin_login_social_solidarity_admin_password_works():
    response = _login("admin", "Admin@123", "social-solidarity")
    _assert_login_success_or_2fa(response, "social-solidarity")


def test_shadow_admin_regression_admin_login_still_uses_super_admin(mongo_db):
    temp_id = f"test-shadow-{uuid.uuid4().hex[:12]}"
    temp_doc = {
        "id": temp_id,
        "username": "admin",
        "full_name": "TEST_SHADOW_ADMIN",
        "organization_id": "general-union",
        "organization_name": "النقابة العامة",
        "organization_modules": {},
        "password_hash": bcrypt.hashpw("WrongPass@123".encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8"),
        "role": "admin",
        "is_active": True,
        "totp_enabled": False,
        "totp_secret": None,
        "totp_pending_secret": None,
        "must_change_password": False,
        "permissions": {
            "enter_deposits": True,
            "view_reports": True,
            "edit_deposits": False,
            "manage_users": True,
            "manage_reconciliations": True,
            "manage_revenues": True,
            "manage_expenses": True,
        },
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }

    mongo_db.users.delete_many({"full_name": "TEST_SHADOW_ADMIN", "username": "admin", "organization_id": "general-union"})
    mongo_db.users.insert_one(temp_doc)

    try:
        response = _login("admin", "Admin@123", "general-union")
        _assert_login_success_or_2fa(response, "general-union")
    finally:
        mongo_db.users.delete_many({"id": temp_id})


def test_login_sets_http_only_cookie_for_access_token():
    response = _login("admin", "Admin@123", "general-union")
    assert response.status_code == 200

    set_cookie = response.headers.get("set-cookie", "")
    if response.json().get("requires_2fa") is True:
        # If login requires OTP, cookie may not be set yet.
        assert "access_token=" not in set_cookie
    else:
        assert "access_token=" in set_cookie
        assert "HttpOnly" in set_cookie


def test_cors_preflight_allows_credentials_with_explicit_origin():
    origin = CORS_ORIGINS[0] if CORS_ORIGINS else f"{urlparse(BASE_URL).scheme}://{urlparse(BASE_URL).netloc}"
    response = requests.options(
        f"{BASE_URL}/api/auth/login",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
        timeout=30,
    )
    assert response.status_code in (200, 204)
    assert response.headers.get("access-control-allow-credentials") == "true"
    assert response.headers.get("access-control-allow-origin") == origin


def test_lockout_happens_after_five_failed_attempts_and_cleans_up(mongo_db):
    username = "admin_union"
    organization_id = "general-union"

    mongo_db.login_attempts.delete_many({"identifier": f"{organization_id}:{username}"})
    for _ in range(5):
        response = _login(username, "Wrong-Password-For-Lockout", organization_id)
        assert response.status_code == 401

    sixth = _login(username, "Wrong-Password-For-Lockout", organization_id)
    assert sixth.status_code == 429

    mongo_db.login_attempts.delete_many({"identifier": f"{organization_id}:{username}"})


def test_seeded_admin_hashes_use_bcrypt_2b_prefix(mongo_db):
    seeded = list(
        mongo_db.users.find(
            {"username": {"$in": ["admin", "admin_union", "admin_takaful"]}},
            {"_id": 0, "username": 1, "password_hash": 1},
        )
    )
    assert len(seeded) >= 3
    for user in seeded:
        assert user.get("password_hash", "").startswith("$2b$")


def test_setup_exe_exists_non_empty_and_release_server_synced_with_backend():
    backend_server = Path("/app/backend/server.py")
    release_server = Path("/app/release/BankDepositSystem/backend/server.py")
    setup_exe = Path("/app/dist/BankDepositSystemSetup.exe")

    assert backend_server.exists() and release_server.exists()
    assert backend_server.read_bytes() == release_server.read_bytes()
    assert setup_exe.exists() and setup_exe.is_file()
    assert setup_exe.stat().st_size > 0
    assert setup_exe.stat().st_mtime >= release_server.stat().st_mtime
