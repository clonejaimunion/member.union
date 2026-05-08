"""Iteration 42: branding settings, super-admin scope, ETA visibility, and auth playbook checks."""

import os
import uuid
from pathlib import Path
from urllib.parse import urlparse

import pytest
import requests


# Core environment and API helpers
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")


def _backend_url_from_frontend_env() -> str | None:
    env_path = Path("/app/frontend/.env")
    if not env_path.exists():
        return None
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            value = line.split("=", 1)[1].strip()
            return value or None
    return None


def _backend_env_value(key: str) -> str | None:
    env_path = Path("/app/backend/.env")
    if not env_path.exists():
        return None
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{key}="):
            value = line.split("=", 1)[1].strip()
            return value or None
    return None


def _require_base_url() -> str:
    base_url = BASE_URL or _backend_url_from_frontend_env()
    if not base_url:
        pytest.fail("REACT_APP_BACKEND_URL is missing")
    return base_url.rstrip("/")


def _login(username: str, password: str, organization_id: str) -> requests.Response:
    return requests.post(
        f"{_require_base_url()}/api/auth/login",
        json={"username": username, "password": password, "organization_id": organization_id},
        timeout=25,
    )


def _token(username: str, password: str, organization_id: str) -> str:
    response = _login(username, password, organization_id)
    assert response.status_code == 200, response.text
    token = response.json().get("token")
    assert isinstance(token, str) and token
    return token


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# Branding + organizations endpoints
def test_public_app_settings_exposes_organizations_labels():
    response = requests.get(f"{_require_base_url()}/api/app-settings/public", timeout=25)
    assert response.status_code == 200, response.text
    data = response.json()
    assert "organizations" in data and isinstance(data["organizations"], dict)
    assert "general-union" in data["organizations"]
    assert "social-solidarity" in data["organizations"]
    assert data["organizations"]["general-union"].get("name")
    assert data["organizations"]["general-union"].get("login_label")


def test_public_organizations_endpoint_contains_two_core_organizations():
    response = requests.get(f"{_require_base_url()}/api/organizations/public", timeout=25)
    assert response.status_code == 200, response.text
    data = response.json()
    ids = {item.get("id") for item in data}
    assert "general-union" in ids
    assert "social-solidarity" in ids


# Super-admin permissions and settings mutation
def test_admin_union_cannot_update_app_settings_returns_403():
    normal_token = _token("admin_union", "Admin@123", "general-union")
    denied = requests.put(
        f"{_require_base_url()}/api/admin/app-settings",
        headers=_auth_headers(normal_token),
        json={"system_name": "نظام محاسبي متكامل"},
        timeout=25,
    )
    assert denied.status_code == 403


def test_super_admin_update_reflects_on_public_settings_and_organizations_and_restores():
    super_token = _token("admin", "Admin@123", "general-union")

    original_public = requests.get(f"{_require_base_url()}/api/app-settings/public", timeout=25)
    assert original_public.status_code == 200
    original_data = original_public.json()
    original_orgs = original_data.get("organizations", {})

    original_system_name = original_data.get("system_name", "نظام محاسبي متكامل")
    original_general_name = original_orgs.get("general-union", {}).get("name", "النقابة العامة")
    original_general_label = original_orgs.get("general-union", {}).get("login_label", "النقابة العامة")
    original_social_name = original_orgs.get("social-solidarity", {}).get("name", "مشروع التكافل الاجتماعي")
    original_social_label = original_orgs.get("social-solidarity", {}).get("login_label", "مشروع التكافل الاجتماعي")

    temp_system_name = "نظام محاسبي - اختبار iteration42"
    temp_general_name = "النقابة العامة - اختبار"
    temp_general_label = "النقابة - اختبار"
    temp_social_name = "مشروع التكافل - اختبار"
    temp_social_label = "التكافل - اختبار"

    update_payload = {
        "system_name": temp_system_name,
        "organization_name": temp_general_name,
        "organization_login_label": temp_general_label,
        "organization_names": {
            "general-union": temp_general_name,
            "social-solidarity": temp_social_name,
        },
        "organization_login_labels": {
            "general-union": temp_general_label,
            "social-solidarity": temp_social_label,
        },
    }

    try:
        updated = requests.put(
            f"{_require_base_url()}/api/admin/app-settings",
            headers=_auth_headers(super_token),
            json=update_payload,
            timeout=25,
        )
        assert updated.status_code == 200, updated.text

        public_settings = requests.get(f"{_require_base_url()}/api/app-settings/public", timeout=25)
        assert public_settings.status_code == 200, public_settings.text
        public_data = public_settings.json()
        assert public_data.get("system_name") == temp_system_name
        assert public_data["organizations"]["general-union"]["name"] == temp_general_name
        assert public_data["organizations"]["social-solidarity"]["login_label"] == temp_social_label

        public_orgs = requests.get(f"{_require_base_url()}/api/organizations/public", timeout=25)
        assert public_orgs.status_code == 200, public_orgs.text
        org_map = {item["id"]: item for item in public_orgs.json()}
        assert org_map["general-union"]["name"] == temp_general_name
        assert org_map["general-union"]["login_label"] == temp_general_label
        assert org_map["social-solidarity"]["name"] == temp_social_name
        assert org_map["social-solidarity"]["login_label"] == temp_social_label
    finally:
        restore_payload = {
            "system_name": original_system_name,
            "organization_name": original_general_name,
            "organization_login_label": original_general_label,
            "organization_names": {
                "general-union": original_general_name,
                "social-solidarity": original_social_name,
            },
            "organization_login_labels": {
                "general-union": original_general_label,
                "social-solidarity": original_social_label,
            },
        }
        requests.put(
            f"{_require_base_url()}/api/admin/app-settings",
            headers=_auth_headers(super_token),
            json=restore_payload,
            timeout=25,
        )


# ETA integration availability (super-admin only)
def test_eta_integration_visible_to_super_admin_only():
    super_token = _token("admin", "Admin@123", "general-union")
    normal_token = _token("admin_union", "Admin@123", "general-union")

    denied = requests.get(f"{_require_base_url()}/api/admin/eta-integration", headers=_auth_headers(normal_token), timeout=25)
    assert denied.status_code == 403

    allowed = requests.get(f"{_require_base_url()}/api/admin/eta-integration", headers=_auth_headers(super_token), timeout=25)
    assert allowed.status_code == 200, allowed.text
    data = allowed.json()
    assert "environment" in data


# Auth playbook checks
def test_login_sets_http_only_cookie():
    response = _login("admin", "Admin@123", "general-union")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data.get("token")
    assert data.get("user", {}).get("username") == "admin"
    set_cookie = response.headers.get("set-cookie", "")
    assert "access_token=" in set_cookie
    assert "HttpOnly" in set_cookie


def test_cors_preflight_has_explicit_origin_and_credentials():
    parsed = urlparse(_require_base_url())
    origin = f"{parsed.scheme}://{parsed.netloc}"
    response = requests.options(
        f"{_require_base_url()}/api/auth/login",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
        timeout=25,
    )
    assert response.status_code in (200, 204), response.text
    assert response.headers.get("access-control-allow-origin") == origin
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_bcrypt_hash_format_starts_with_2b_for_seeded_admin_users():
    mongo_url = os.environ.get("MONGO_URL") or _backend_env_value("MONGO_URL")
    db_name = os.environ.get("DB_NAME") or _backend_env_value("DB_NAME")
    if not mongo_url or not db_name:
        pytest.skip("MONGO_URL or DB_NAME missing")
    if not (mongo_url.startswith("mongodb://") or mongo_url.startswith("mongodb+srv://")):
        pytest.skip("MONGO_URL is not a valid Mongo URI in this runtime")

    pymongo = pytest.importorskip("pymongo")
    client = pymongo.MongoClient(mongo_url)
    db = client[db_name]
    try:
        users = list(db.users.find({"username": {"$in": ["admin", "admin_union"]}}, {"_id": 0, "username": 1, "password_hash": 1}))
        assert users, "Expected seeded admin users in DB"
        hashes = {item.get("username"): item.get("password_hash", "") for item in users}
        assert hashes.get("admin", "").startswith("$2b$")
        assert hashes.get("admin_union", "").startswith("$2b$")
    finally:
        client.close()


def test_seed_admin_updates_existing_password_logic_exists_in_code_review():
    server_path = Path("/app/backend/server.py")
    content = server_path.read_text(encoding="utf-8")
    assert "if not verify_password(ADMIN_INITIAL_PASSWORD, existing.get(\"password_hash\", \"\"))" in content
    assert "document[\"password_hash\"] = hash_password(ADMIN_INITIAL_PASSWORD)" in content


def test_setup_exe_present_and_non_empty():
    setup_path = Path("/app/dist/BankDepositSystemSetup.exe")
    assert setup_path.exists()
    assert setup_path.stat().st_size > 0


def test_z_bruteforce_lockout_after_five_failures():
    username = f"lockout_probe_iter42_{uuid.uuid4().hex[:8]}"
    organization_id = "general-union"
    for _ in range(5):
        failed = _login(username, "wrong-password", organization_id)
        assert failed.status_code == 401
    locked = _login(username, "wrong-password", organization_id)
    assert locked.status_code == 429
