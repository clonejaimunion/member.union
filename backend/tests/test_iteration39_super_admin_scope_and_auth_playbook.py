"""Iteration 39: super-admin-only user management + auth playbook regression checks."""

import os
import time
import uuid

import pytest
import requests
from pymongo import MongoClient


BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")


@pytest.fixture(scope="session")
def api_base_url():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL is missing")
    return BASE_URL


@pytest.fixture(scope="session")
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


def login(api_client: requests.Session, api_base_url: str, username: str, password: str, organization_id: str) -> str:
    response = api_client.post(
        f"{api_base_url}/api/auth/login",
        json={"username": username, "password": password, "organization_id": organization_id},
        timeout=20,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    token = payload.get("token")
    assert isinstance(token, str) and token
    assert payload.get("user", {}).get("username") == username
    return token


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# --- Super admin user-management scope checks ---
def test_admin_union_get_post_put_delete_admin_users_return_403_with_required_message(api_client, api_base_url):
    super_token = login(api_client, api_base_url, "admin", "Admin@123", "general-union")
    normal_token = login(api_client, api_base_url, "admin_union", "Admin@123", "general-union")

    create_response = api_client.post(
        f"{api_base_url}/api/admin/users",
        headers=auth_header(super_token),
        json={
            "username": f"temp_scope_{uuid.uuid4().hex[:8]}",
            "full_name": "مستخدم اختبار الصلاحيات",
            "password": "TempPass123",
            "role": "user",
            "organization_id": "general-union",
            "permissions": {
                "enter_deposits": True,
                "view_reports": True,
                "edit_deposits": False,
                "manage_users": False,
                "manage_reconciliations": True,
                "manage_revenues": True,
                "manage_expenses": True,
            },
            "is_active": True,
        },
        timeout=20,
    )
    assert create_response.status_code == 200, create_response.text
    created_user = create_response.json()
    user_id = created_user["id"]

    try:
        get_response = api_client.get(f"{api_base_url}/api/admin/users", headers=auth_header(normal_token), timeout=20)
        assert get_response.status_code == 403
        assert "السوبر أدمن admin فقط" in get_response.json().get("detail", "")

        post_response = api_client.post(
            f"{api_base_url}/api/admin/users",
            headers=auth_header(normal_token),
            json={
                "username": f"temp_forbidden_{uuid.uuid4().hex[:8]}",
                "full_name": "مستخدم ممنوع",
                "password": "TempPass123",
                "role": "user",
                "organization_id": "general-union",
                "permissions": {
                    "enter_deposits": True,
                    "view_reports": True,
                    "edit_deposits": False,
                    "manage_users": False,
                    "manage_reconciliations": True,
                    "manage_revenues": True,
                    "manage_expenses": True,
                },
                "is_active": True,
            },
            timeout=20,
        )
        assert post_response.status_code == 403
        assert "السوبر أدمن admin فقط" in post_response.json().get("detail", "")

        put_response = api_client.put(
            f"{api_base_url}/api/admin/users/{user_id}",
            headers=auth_header(normal_token),
            json={"full_name": "تحديث غير مسموح"},
            timeout=20,
        )
        assert put_response.status_code == 403
        assert "السوبر أدمن admin فقط" in put_response.json().get("detail", "")

        delete_response = api_client.delete(
            f"{api_base_url}/api/admin/users/{user_id}",
            headers=auth_header(normal_token),
            timeout=20,
        )
        assert delete_response.status_code == 403
        assert "السوبر أدمن admin فقط" in delete_response.json().get("detail", "")
    finally:
        api_client.delete(f"{api_base_url}/api/admin/users/{user_id}", headers=auth_header(super_token), timeout=20)


def test_super_admin_not_listed_and_cannot_be_updated_or_deleted(api_client, api_base_url):
    super_token = login(api_client, api_base_url, "admin", "Admin@123", "general-union")

    list_response = api_client.get(f"{api_base_url}/api/admin/users", headers=auth_header(super_token), timeout=20)
    assert list_response.status_code == 200
    users = list_response.json()
    assert all(user.get("username") != "admin" for user in users)
    assert all(user.get("role") != "super_admin" for user in users)

    me_response = api_client.get(f"{api_base_url}/api/auth/me", headers=auth_header(super_token), timeout=20)
    assert me_response.status_code == 200
    super_admin_id = me_response.json()["id"]

    update_response = api_client.put(
        f"{api_base_url}/api/admin/users/{super_admin_id}",
        headers=auth_header(super_token),
        json={"is_active": False},
        timeout=20,
    )
    assert update_response.status_code == 403

    delete_response = api_client.delete(
        f"{api_base_url}/api/admin/users/{super_admin_id}",
        headers=auth_header(super_token),
        timeout=20,
    )
    assert delete_response.status_code == 403


# --- Auth playbook checks requested in instructions ---
def test_login_sets_httponly_cookie(api_client, api_base_url):
    response = api_client.post(
        f"{api_base_url}/api/auth/login",
        json={"username": "admin", "password": "Admin@123", "organization_id": "general-union"},
        timeout=20,
    )
    assert response.status_code == 200, response.text
    set_cookie = response.headers.get("set-cookie", "")
    assert "access_token=" in set_cookie
    assert "HttpOnly" in set_cookie


def test_cors_preflight_returns_explicit_origin_and_allow_credentials(api_base_url):
    origin = "https://interest-calculator-12.preview.emergentagent.com"
    response = requests.options(
        f"{api_base_url}/api/auth/login",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,authorization",
        },
        timeout=20,
    )
    assert response.status_code in [200, 204]
    assert response.headers.get("Access-Control-Allow-Origin") == origin
    assert response.headers.get("Access-Control-Allow-Credentials") == "true"


def test_bruteforce_lockout_after_five_failed_attempts(api_client, api_base_url):
    username = f"lock_{uuid.uuid4().hex[:10]}"
    payload = {"username": username, "password": "WrongPass123!", "organization_id": "general-union"}

    statuses = []
    for _ in range(6):
        response = api_client.post(f"{api_base_url}/api/auth/login", json=payload, timeout=20)
        statuses.append(response.status_code)
        time.sleep(0.15)

    assert statuses[:5] == [401, 401, 401, 401, 401]
    assert statuses[5] == 429


def test_seeded_admin_password_hash_uses_bcrypt_2b_prefix():
    if not MONGO_URL or not DB_NAME:
        pytest.skip("MONGO_URL or DB_NAME missing")

    client = MongoClient(MONGO_URL)
    try:
        document = client[DB_NAME].users.find_one({"username": "admin", "role": "super_admin"}, {"password_hash": 1, "_id": 0})
        assert document is not None
        password_hash = document.get("password_hash", "")
        assert isinstance(password_hash, str) and password_hash.startswith("$2b$")
    finally:
        client.close()
