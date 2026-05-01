"""Iteration 44: super-admin controls, training exports, backup/2FA policy, and auth playbook checks."""

# Modules covered: app-settings, organizations, training exports, backup policy, 2FA policy, auth hardening

import os
import time
import uuid

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient


def _load_base_url() -> str:
    env_base = os.environ.get("REACT_APP_BACKEND_URL")
    if env_base:
        return env_base.rstrip("/")
    front_env = dotenv_values("/app/frontend/.env")
    front_base = front_env.get("REACT_APP_BACKEND_URL")
    if front_base:
        return str(front_base).rstrip("/")
    pytest.fail("REACT_APP_BACKEND_URL is missing (env and /app/frontend/.env)")


BASE_URL = _load_base_url()


def _mongo_client():
    env_url = os.environ.get("MONGO_URL")
    if not env_url:
        back_env = dotenv_values("/app/backend/.env")
        env_url = back_env.get("MONGO_URL")
    if not env_url:
        pytest.skip("MONGO_URL is missing")
    back_env = dotenv_values("/app/backend/.env")
    db_name = os.environ.get("DB_NAME") or back_env.get("DB_NAME")
    if not db_name:
        pytest.skip("DB_NAME is missing")
    return MongoClient(str(env_url).strip('"'))[str(db_name).strip('"')]


def login(username: str, password: str, organization_id: str):
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": username, "password": password, "organization_id": organization_id},
        timeout=30,
    )
    assert response.status_code == 200, response.text
    token = response.json().get("token")
    assert isinstance(token, str) and token
    return token, response


def headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def super_admin_token():
    token, _ = login("admin", "Admin@123", "general-union")
    return token


@pytest.fixture(scope="module")
def admin_union_token():
    token, _ = login("admin_union", "Admin@123", "general-union")
    return token


@pytest.fixture(scope="module", autouse=True)
def restore_global_settings(super_admin_token):
    before = requests.get(f"{BASE_URL}/api/admin/app-settings", headers=headers(super_admin_token), timeout=30)
    assert before.status_code == 200, before.text
    snapshot = before.json()
    yield
    payload = {
        "system_name": snapshot.get("system_name") or "نظام محاسبي متكامل",
        "organization_name": snapshot.get("organization_name") or "",
        "organization_login_label": snapshot.get("organization_login_label") or "",
        "organization_names": {k: v.get("name") for k, v in (snapshot.get("organizations") or {}).items()},
        "organization_login_labels": {k: v.get("login_label") for k, v in (snapshot.get("organizations") or {}).items()},
        "organization_emails": {k: v.get("email") for k, v in (snapshot.get("organizations") or {}).items()},
        "login_union_logo_visible": snapshot.get("login_union_logo_visible", True),
        "login_union_logo_data_url": snapshot.get("login_union_logo_data_url"),
        "login_authority_logos": snapshot.get("login_authority_logos") or [],
        "backup_enabled": snapshot.get("backup_enabled", True),
        "backup_allowed_roles": snapshot.get("backup_allowed_roles") or {"super_admin": True, "admin": True, "user": False},
        "two_factor_role_policy": snapshot.get("two_factor_role_policy") or {"super_admin": False, "admin": False, "user": False},
    }
    requests.put(f"{BASE_URL}/api/admin/app-settings", headers=headers(super_admin_token), json=payload, timeout=30)


def test_auth_playbook_bcrypt_hash_prefix_for_admin():
    db = _mongo_client()
    admin = db.users.find_one({"username": "admin"}, {"_id": 0, "password_hash": 1})
    assert admin is not None
    password_hash = admin.get("password_hash") or ""
    assert isinstance(password_hash, str)
    assert password_hash.startswith("$2b$")


def test_auth_playbook_login_sets_httponly_cookie():
    _, response = login("admin", "Admin@123", "general-union")
    set_cookie = response.headers.get("set-cookie", "")
    assert "access_token=" in set_cookie
    assert "HttpOnly" in set_cookie


def test_auth_playbook_cors_preflight_explicit_origin_and_credentials():
    origin = BASE_URL
    response = requests.options(
        f"{BASE_URL}/api/auth/login",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,authorization",
        },
        timeout=30,
    )
    assert response.status_code in [200, 204]
    assert response.headers.get("access-control-allow-origin") == origin
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_auth_playbook_bruteforce_lockout_after_5_fails():
    random_user = f"lockout_{uuid.uuid4().hex[:8]}"
    for _ in range(5):
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": random_user, "password": "wrong-pass", "organization_id": "general-union"},
            timeout=30,
        )
        assert response.status_code == 401
    blocked = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": random_user, "password": "wrong-pass", "organization_id": "general-union"},
        timeout=30,
    )
    assert blocked.status_code == 429, blocked.text


def test_super_admin_can_save_logo_email_backup_and_2fa_policies(super_admin_token):
    payload = {
        "system_name": "نظام محاسبي متكامل",
        "organization_name": "النقابة العامة للعاملين بالزراعة والري والصيد واستصلاح الأراضي",
        "organization_login_label": "النقابة العامة",
        "organization_names": {
            "general-union": "النقابة العامة للعاملين بالزراعة والري والصيد واستصلاح الأراضي",
            "social-solidarity": "مشروع التكافل الاجتماعي",
        },
        "organization_login_labels": {
            "general-union": "النقابة العامة",
            "social-solidarity": "مشروع التكافل الاجتماعي",
        },
        "organization_emails": {
            "general-union": "union+iter44@example.com",
            "social-solidarity": "solidarity+iter44@example.com",
        },
        "login_union_logo_visible": False,
        "login_authority_logos": [
            {"name": "مصلحة الضرائب المصرية", "enabled": True, "src": "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 10 10'><circle cx='5' cy='5' r='4' fill='green'/></svg>"},
            {"name": "مصلحة الخزانة العامة", "enabled": True, "src": "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 10 10'><rect x='1' y='1' width='8' height='8' fill='blue'/></svg>"},
            {"name": "وزارة المالية", "enabled": True, "src": "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 10 10'><path d='M1 9 L5 1 L9 9Z' fill='red'/></svg>"},
            {"name": "وزارة العمل المصرية", "enabled": True, "src": "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 10 10'><line x1='1' y1='1' x2='9' y2='9' stroke='black' /></svg>"},
            {"name": "وزارة الاتصالات وتكنولوجيا المعلومات", "enabled": True, "src": "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 10 10'><ellipse cx='5' cy='5' rx='4' ry='2' fill='purple'/></svg>"},
        ],
        "backup_enabled": True,
        "backup_allowed_roles": {"super_admin": True, "admin": True, "user": False},
        "two_factor_role_policy": {"super_admin": True, "admin": False, "user": False},
    }
    response = requests.put(f"{BASE_URL}/api/admin/app-settings", json=payload, headers=headers(super_admin_token), timeout=30)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["login_union_logo_visible"] is False
    assert len(data.get("login_authority_logos") or []) == 5
    assert data["organizations"]["general-union"]["email"] == "union+iter44@example.com"
    assert data["two_factor_role_policy"]["admin"] is False


def test_public_settings_returns_organizations_emails_and_logo_list():
    response = requests.get(f"{BASE_URL}/api/app-settings/public", timeout=30)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["organizations"]["general-union"]["email"] == "union+iter44@example.com"
    assert data["organizations"]["social-solidarity"]["email"] == "solidarity+iter44@example.com"
    assert len(data.get("login_authority_logos") or []) == 5


def test_super_admin_can_add_org_with_clone_and_disable(super_admin_token):
    suffix = int(time.time())
    create = requests.post(
        f"{BASE_URL}/api/admin/organizations",
        headers=headers(super_admin_token),
        json={
            "name": f"جهة اختبار iter44 {suffix}",
            "login_label": f"اختبار iter44 {suffix}",
            "email": "iter44@example.com",
            "clone_from": "social-solidarity",
        },
        timeout=30,
    )
    assert create.status_code == 200, create.text
    body = create.json()
    assert isinstance(body.get("modules"), dict)
    assert len(body["modules"]) > 0
    org_id = body["id"]

    disable = requests.put(
        f"{BASE_URL}/api/admin/organizations/{org_id}",
        headers=headers(super_admin_token),
        json={"is_active": False},
        timeout=30,
    )
    assert disable.status_code == 200, disable.text
    assert disable.json()["is_active"] is False


def test_admin_union_cannot_create_org_clear_audit_or_save_global_settings(admin_union_token):
    create = requests.post(
        f"{BASE_URL}/api/admin/organizations",
        headers=headers(admin_union_token),
        json={"name": "blocked-org"},
        timeout=30,
    )
    assert create.status_code == 403

    clear = requests.delete(f"{BASE_URL}/api/admin/security/audit-logs", headers=headers(admin_union_token), timeout=30)
    assert clear.status_code == 403

    update = requests.put(
        f"{BASE_URL}/api/admin/app-settings",
        headers=headers(admin_union_token),
        json={"system_name": "منع", "organization_name": "منع", "organization_login_label": "منع"},
        timeout=30,
    )
    assert update.status_code == 403


def test_training_exports_non_empty_and_no_super_admin_word(super_admin_token):
    for path, expected_type in [
        ("/api/admin/training/manual.pdf", "application/pdf"),
        ("/api/admin/training/screenshots.zip", "application/zip"),
        ("/api/admin/training/video-guide.gif", "image/gif"),
    ]:
        response = requests.get(f"{BASE_URL}{path}", headers=headers(super_admin_token), timeout=60)
        assert response.status_code == 200, response.text
        assert expected_type in response.headers.get("content-type", "")
        assert len(response.content) > 1000
        assert b"super_admin" not in response.content


def test_backup_policy_blocks_service_when_disabled_and_role_not_allowed(super_admin_token, admin_union_token):
    disable_backup_payload = {
        "system_name": "نظام محاسبي متكامل",
        "organization_name": "النقابة العامة",
        "organization_login_label": "النقابة العامة",
        "backup_enabled": False,
        "backup_allowed_roles": {"super_admin": True, "admin": True, "user": False},
        "two_factor_role_policy": {"super_admin": True, "admin": False, "user": False},
    }
    disable = requests.put(
        f"{BASE_URL}/api/admin/app-settings",
        headers=headers(super_admin_token),
        json=disable_backup_payload,
        timeout=30,
    )
    assert disable.status_code == 200, disable.text

    blocked_by_service = requests.post(
        f"{BASE_URL}/api/admin/security/backups",
        headers=headers(super_admin_token),
        json={"password": "Secret123"},
        timeout=30,
    )
    assert blocked_by_service.status_code == 403

    enable_limited_payload = {
        "system_name": "نظام محاسبي متكامل",
        "organization_name": "النقابة العامة",
        "organization_login_label": "النقابة العامة",
        "backup_enabled": True,
        "backup_allowed_roles": {"super_admin": True, "admin": False, "user": False},
        "two_factor_role_policy": {"super_admin": True, "admin": False, "user": False},
    }
    limited = requests.put(
        f"{BASE_URL}/api/admin/app-settings",
        headers=headers(super_admin_token),
        json=enable_limited_payload,
        timeout=30,
    )
    assert limited.status_code == 200, limited.text

    blocked_by_role = requests.post(
        f"{BASE_URL}/api/admin/security/backups",
        headers=headers(admin_union_token),
        json={"password": "Secret123"},
        timeout=30,
    )
    assert blocked_by_role.status_code == 403


def test_two_factor_policy_blocks_and_allows_setup_by_role(super_admin_token, admin_union_token):
    block_admin_payload = {
        "system_name": "نظام محاسبي متكامل",
        "organization_name": "النقابة العامة",
        "organization_login_label": "النقابة العامة",
        "backup_enabled": True,
        "backup_allowed_roles": {"super_admin": True, "admin": True, "user": False},
        "two_factor_role_policy": {"super_admin": True, "admin": False, "user": False},
    }
    block_update = requests.put(
        f"{BASE_URL}/api/admin/app-settings",
        headers=headers(super_admin_token),
        json=block_admin_payload,
        timeout=30,
    )
    assert block_update.status_code == 200, block_update.text

    blocked = requests.post(f"{BASE_URL}/api/admin/2fa/setup", headers=headers(admin_union_token), timeout=30)
    assert blocked.status_code == 403

    allow_admin_payload = {
        "system_name": "نظام محاسبي متكامل",
        "organization_name": "النقابة العامة",
        "organization_login_label": "النقابة العامة",
        "backup_enabled": True,
        "backup_allowed_roles": {"super_admin": True, "admin": True, "user": False},
        "two_factor_role_policy": {"super_admin": True, "admin": True, "user": False},
    }
    allow_update = requests.put(
        f"{BASE_URL}/api/admin/app-settings",
        headers=headers(super_admin_token),
        json=allow_admin_payload,
        timeout=30,
    )
    assert allow_update.status_code == 200, allow_update.text

    allowed = requests.post(f"{BASE_URL}/api/admin/2fa/setup", headers=headers(admin_union_token), timeout=30)
    assert allowed.status_code == 200, allowed.text
    data = allowed.json()
    assert isinstance(data.get("qr_data_url"), str) and data["qr_data_url"].startswith("data:image/png;base64,")
    assert isinstance(data.get("manual_secret"), str) and len(data["manual_secret"]) >= 16
