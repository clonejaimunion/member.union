import os
import uuid

import pytest
import requests
from dotenv import dotenv_values


# Organization module targeting + Tax Engine visibility isolation checks.
FRONTEND_ENV = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or FRONTEND_ENV.get("REACT_APP_BACKEND_URL") or "").rstrip("/")

GENERAL_ORG = "general-union"
SOCIAL_ORG = "social-solidarity"


def _headers(token: str | None = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _login(base_url: str, username: str, password: str, organization_id: str):
    return requests.post(
        f"{base_url}/api/auth/login",
        json={"username": username, "password": password, "organization_id": organization_id},
        headers=_headers(),
        timeout=90,
    )


def _get_modules(base_url: str, token: str, organization_id: str):
    return requests.get(
        f"{base_url}/api/admin/organization/modules",
        params={"organization_id": organization_id},
        headers=_headers(token),
        timeout=90,
    )


def _put_modules(base_url: str, token: str, organization_id: str, modules: dict):
    return requests.put(
        f"{base_url}/api/admin/organization/modules",
        params={"organization_id": organization_id},
        json={"modules": modules},
        headers=_headers(token),
        timeout=90,
    )


@pytest.fixture(scope="session")
def base_url():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL is not configured")
    return BASE_URL


@pytest.fixture(scope="session")
def super_admin_login(base_url):
    response = _login(base_url, "admin", "Admin@123", GENERAL_ORG)
    if response.status_code != 200:
        pytest.skip(f"super admin login failed: {response.status_code} {response.text}")
    token = response.json().get("token")
    if not token:
        pytest.skip("super admin token missing")
    return {"token": token, "response": response}


@pytest.fixture(scope="session")
def super_admin_token(super_admin_login):
    return super_admin_login["token"]


@pytest.fixture(scope="session")
def general_admin_token(base_url):
    response = _login(base_url, "admin_union", "Admin@123", GENERAL_ORG)
    if response.status_code != 200:
        pytest.skip(f"general admin login failed: {response.status_code} {response.text}")
    token = response.json().get("token")
    if not token:
        pytest.skip("general admin token missing")
    return token


@pytest.fixture(scope="session")
def social_admin_token(base_url):
    response = _login(base_url, "admin_takaful", "Admin@123", SOCIAL_ORG)
    if response.status_code != 200:
        pytest.skip(f"social admin login failed: {response.status_code} {response.text}")
    token = response.json().get("token")
    if not token:
        pytest.skip("social admin token missing")
    return token


def test_super_admin_get_modules_by_target_organization(base_url, super_admin_token):
    general_resp = _get_modules(base_url, super_admin_token, GENERAL_ORG)
    social_resp = _get_modules(base_url, super_admin_token, SOCIAL_ORG)

    assert general_resp.status_code == 200, general_resp.text
    assert social_resp.status_code == 200, social_resp.text

    general_data = general_resp.json()
    social_data = social_resp.json()

    assert general_data["organization_id"] == GENERAL_ORG
    assert social_data["organization_id"] == SOCIAL_ORG
    assert isinstance(general_data.get("modules"), dict)
    assert isinstance(social_data.get("modules"), dict)


def test_login_sets_httponly_cookie_for_super_admin(super_admin_login):
    set_cookie = (
        super_admin_login["response"].headers.get("set-cookie")
        or super_admin_login["response"].headers.get("Set-Cookie")
        or ""
    )
    assert "HttpOnly" in set_cookie


def test_non_super_admin_cannot_target_other_organization(base_url, social_admin_token):
    response = _get_modules(base_url, social_admin_token, GENERAL_ORG)
    assert response.status_code == 403


def test_current_einvoice_state_general_true_social_false(base_url, super_admin_token):
    general_modules = _get_modules(base_url, super_admin_token, GENERAL_ORG).json()["modules"]
    social_modules = _get_modules(base_url, super_admin_token, SOCIAL_ORG).json()["modules"]

    assert general_modules.get("electronic_invoice") is True
    assert social_modules.get("electronic_invoice") is False


def test_tax_engine_profile_status_matches_org_module_state(base_url, general_admin_token, social_admin_token):
    general_resp = requests.get(
        f"{base_url}/api/tax-engine/profile",
        headers=_headers(general_admin_token),
        timeout=90,
    )
    social_resp = requests.get(
        f"{base_url}/api/tax-engine/profile",
        headers=_headers(social_admin_token),
        timeout=90,
    )

    assert general_resp.status_code == 200, general_resp.text
    assert social_resp.status_code == 404, social_resp.text


def test_updating_one_org_modules_does_not_change_other_org(base_url, super_admin_token):
    general_before_resp = _get_modules(base_url, super_admin_token, GENERAL_ORG)
    social_before_resp = _get_modules(base_url, super_admin_token, SOCIAL_ORG)
    assert general_before_resp.status_code == 200, general_before_resp.text
    assert social_before_resp.status_code == 200, social_before_resp.text

    general_before = general_before_resp.json()["modules"]
    social_before = social_before_resp.json()["modules"]

    target_key = "ledger"
    general_modified = dict(general_before)
    general_modified[target_key] = not bool(general_before.get(target_key, True))

    try:
        update_resp = _put_modules(base_url, super_admin_token, GENERAL_ORG, general_modified)
        assert update_resp.status_code == 200, update_resp.text

        general_after = _get_modules(base_url, super_admin_token, GENERAL_ORG).json()["modules"]
        social_after = _get_modules(base_url, super_admin_token, SOCIAL_ORG).json()["modules"]

        assert general_after.get(target_key) == general_modified[target_key]
        assert social_after == social_before
        assert social_after.get("electronic_invoice") is social_before.get("electronic_invoice")
    finally:
        restore_resp = _put_modules(base_url, super_admin_token, GENERAL_ORG, general_before)
        assert restore_resp.status_code == 200, restore_resp.text


def test_audit_log_contains_organization_modules_updated(base_url, super_admin_token):
    general_before_resp = _get_modules(base_url, super_admin_token, GENERAL_ORG)
    assert general_before_resp.status_code == 200, general_before_resp.text
    general_modules = general_before_resp.json()["modules"]

    update_resp = _put_modules(base_url, super_admin_token, GENERAL_ORG, general_modules)
    assert update_resp.status_code == 200, update_resp.text

    logs_resp = requests.get(
        f"{base_url}/api/admin/security/audit-logs",
        params={"limit": 500},
        headers=_headers(super_admin_token),
        timeout=90,
    )
    assert logs_resp.status_code == 200, logs_resp.text
    logs = logs_resp.json()

    match = [
        item
        for item in logs
        if item.get("action") == "ORGANIZATION_MODULES_UPDATED"
        and item.get("path") == "/admin/organization/modules"
    ]
    assert len(match) > 0


@pytest.fixture
def temporary_org(base_url, super_admin_token):
    org_name = f"TEST_ITER84_ORG_{uuid.uuid4().hex[:8]}"
    create_resp = requests.post(
        f"{base_url}/api/admin/organizations",
        json={"name": org_name, "login_label": org_name},
        headers=_headers(super_admin_token),
        timeout=90,
    )
    assert create_resp.status_code == 200, create_resp.text
    created = create_resp.json()
    org_id = created["id"]

    yield created

    requests.put(
        f"{base_url}/api/admin/organizations/{org_id}",
        json={"is_active": False},
        headers=_headers(super_admin_token),
        timeout=90,
    )


def test_new_organization_default_does_not_auto_enable_einvoice(base_url, super_admin_token, temporary_org):
    org_id = temporary_org["id"]
    modules_resp = _get_modules(base_url, super_admin_token, org_id)
    assert modules_resp.status_code == 200, modules_resp.text
    modules = modules_resp.json()["modules"]
    assert modules.get("electronic_invoice") is False
