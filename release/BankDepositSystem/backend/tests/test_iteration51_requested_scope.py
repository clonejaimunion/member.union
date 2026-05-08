"""Iteration 51: requested scope regression for organizations, rules engine, fail-safe, audit trail, and setup download."""

import os
import uuid
from datetime import date
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values


# Modules/features under test: public org visibility, rules-engine simulation, fail-safe journaling, audit before/after, setup binary
ENV_BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
FILE_BASE_URL = dotenv_values("/app/frontend/.env").get("REACT_APP_BACKEND_URL")
BASE_URL = (ENV_BASE_URL or FILE_BASE_URL or "").rstrip("/")
LOCAL_API_URL = "http://localhost:8001"

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Admin@123"
ORG_ID = "social-solidarity"


def _headers(token: str | None = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _login(username: str, password: str, organization_id: str = ORG_ID):
    return requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": username, "password": password, "organization_id": organization_id},
        headers=_headers(),
        timeout=40,
    )


@pytest.fixture(scope="session", autouse=True)
def require_base_url():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL is not configured")


@pytest.fixture(scope="session")
def admin_token():
    login = _login(ADMIN_USERNAME, ADMIN_PASSWORD, ORG_ID)
    if login.status_code != 200:
        pytest.skip(f"Admin login failed: {login.status_code}")
    token = login.json().get("token")
    if not token:
        pytest.skip("No token returned for admin login")
    return token


def _create_balanced_manual_entry(token: str, ref_prefix: str = "ITER51") -> dict:
    payload = {
        "entry_date": date.today().isoformat(),
        "description": f"{ref_prefix} balanced entry",
        "reference": f"{ref_prefix}-{uuid.uuid4().hex[:8]}",
        "lines": [
            {"account_code": "1110", "account_name": "الخزينة", "debit": 100.0, "credit": 0},
            {"account_code": "4101", "account_name": "إيرادات الاشتراكات", "debit": 0, "credit": 100.0},
        ],
    }
    response = requests.post(f"{BASE_URL}/api/journal-entries", json=payload, headers=_headers(token), timeout=40)
    assert response.status_code == 200, response.text
    return response.json()


def test_public_organizations_only_official_entities():
    response = requests.get(f"{BASE_URL}/api/organizations/public", timeout=30)
    assert response.status_code == 200, response.text
    organizations = response.json()
    org_ids = [item["id"] for item in organizations]
    assert "social-solidarity" in org_ids
    assert "general-union" in org_ids
    assert all("iter" not in item.lower() for item in org_ids)
    assert all(not item.lower().startswith("test") for item in org_ids)


def test_auth_login_sets_httponly_cookie(admin_token):
    response = _login(ADMIN_USERNAME, ADMIN_PASSWORD, ORG_ID)
    assert response.status_code == 200, response.text
    body = response.json()
    assert bool(body.get("token")) is True
    set_cookie = response.headers.get("set-cookie", "")
    assert "access_token=" in set_cookie
    assert "HttpOnly" in set_cookie


def test_auth_cors_preflight_allows_credentials_explicit_origin_localhost():
    response = requests.options(
        f"{LOCAL_API_URL}/api/auth/login",
        headers={
            "Origin": BASE_URL,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,authorization",
        },
        timeout=30,
    )
    assert response.status_code in (200, 204)
    assert response.headers.get("access-control-allow-credentials", "").lower() == "true"
    assert response.headers.get("access-control-allow-origin", "") not in ("", "*")


def test_rules_engine_rules_list_and_simulate_returns_preview_without_posting(admin_token):
    rules_response = requests.get(f"{BASE_URL}/api/rules-engine/rules", headers=_headers(admin_token), timeout=40)
    assert rules_response.status_code == 200, rules_response.text
    assert isinstance(rules_response.json(), list)

    before_entries = requests.get(f"{BASE_URL}/api/journal-entries", headers=_headers(admin_token), timeout=40)
    assert before_entries.status_code == 200, before_entries.text
    before_max = max([int(item.get("entry_number", 0) or 0) for item in before_entries.json()] or [0])

    simulate_payload = {
        "event_type": "BankFee",
        "sub_type": "StatementFee",
        "payment_method": "bank",
        "amount": 250,
        "bank_id": "industrial-development",
    }
    simulation = requests.post(f"{BASE_URL}/api/rules-engine/simulate", json=simulate_payload, headers=_headers(admin_token), timeout=40)
    assert simulation.status_code == 200, simulation.text
    simulation_body = simulation.json()
    assert simulation_body.get("simulation_only") is True
    assert isinstance(simulation_body.get("preview_lines"), list)

    after_entries = requests.get(f"{BASE_URL}/api/journal-entries", headers=_headers(admin_token), timeout=40)
    assert after_entries.status_code == 200, after_entries.text
    after_max = max([int(item.get("entry_number", 0) or 0) for item in after_entries.json()] or [0])
    assert after_max == before_max


def test_download_setup_exe_is_valid_and_matches_dist_size():
    response = requests.get(f"{BASE_URL}/api/download/setup", timeout=120)
    assert response.status_code == 200, response.text
    assert response.content[:2] == b"MZ"

    local_exe = Path("/app/dist/BankDepositSystemSetup.exe")
    assert local_exe.exists()
    assert len(response.content) == local_exe.stat().st_size


def test_fail_safe_unbalanced_manual_journal_create_returns_422(admin_token):
    payload = {
        "entry_date": date.today().isoformat(),
        "description": "ITER51 unbalanced create",
        "reference": f"ITER51-UC-{uuid.uuid4().hex[:8]}",
        "lines": [
            {"account_code": "1110", "account_name": "الخزينة", "debit": 120.0, "credit": 0},
            {"account_code": "4101", "account_name": "إيرادات الاشتراكات", "debit": 0, "credit": 100.0},
        ],
    }
    response = requests.post(f"{BASE_URL}/api/journal-entries", json=payload, headers=_headers(admin_token), timeout=40)
    assert response.status_code == 422, response.text


def test_fail_safe_unbalanced_manual_journal_update_returns_422(admin_token):
    created = _create_balanced_manual_entry(admin_token, ref_prefix="ITER51-UPD")
    payload = {
        "entry_date": created["entry_date"],
        "description": "ITER51 unbalanced update",
        "reference": created.get("reference"),
        "lines": [
            {"account_code": "1110", "account_name": "الخزينة", "debit": 300.0, "credit": 0},
            {"account_code": "4101", "account_name": "إيرادات الاشتراكات", "debit": 0, "credit": 100.0},
        ],
    }
    response = requests.put(f"{BASE_URL}/api/journal-entries/{created['id']}", json=payload, headers=_headers(admin_token), timeout=40)
    assert response.status_code == 422, response.text


def test_audit_log_contains_before_after_for_chart_account_put(admin_token):
    accounts_response = requests.get(f"{BASE_URL}/api/chart-accounts", headers=_headers(admin_token), timeout=40)
    assert accounts_response.status_code == 200, accounts_response.text
    accounts = accounts_response.json()
    target = next((item for item in accounts if item.get("code") == "5104"), accounts[0] if accounts else None)
    assert target is not None

    new_name = f"{target['name']} ITER51"
    update_response = requests.put(
        f"{BASE_URL}/api/chart-accounts/{target['id']}",
        json={"name": new_name},
        headers=_headers(admin_token),
        timeout=40,
    )
    assert update_response.status_code == 200, update_response.text
    updated_body = update_response.json()
    assert updated_body.get("name") == new_name

    logs_response = requests.get(f"{BASE_URL}/api/admin/security/audit-logs?limit=80", headers=_headers(admin_token), timeout=40)
    assert logs_response.status_code == 200, logs_response.text
    logs = logs_response.json()
    hit = next(
        (
            item
            for item in logs
            if item.get("method") == "PUT"
            and str(item.get("path", "")).endswith(f"/api/chart-accounts/{target['id']}")
        ),
        None,
    )
    assert hit is not None
    assert isinstance(hit.get("before_document"), dict)
    assert isinstance(hit.get("after_document"), dict)


def test_audit_log_contains_before_after_for_journal_entry_put(admin_token):
    created = _create_balanced_manual_entry(admin_token, ref_prefix="ITER51-AUD")
    update_payload = {
        "entry_date": created["entry_date"],
        "description": "ITER51 audit update",
        "reference": created.get("reference"),
        "lines": created["lines"],
    }
    update_response = requests.put(
        f"{BASE_URL}/api/journal-entries/{created['id']}",
        json=update_payload,
        headers=_headers(admin_token),
        timeout=40,
    )
    assert update_response.status_code == 200, update_response.text
    assert update_response.json().get("description") == "ITER51 audit update"

    logs_response = requests.get(f"{BASE_URL}/api/admin/security/audit-logs?limit=80", headers=_headers(admin_token), timeout=40)
    assert logs_response.status_code == 200, logs_response.text
    logs = logs_response.json()
    hit = next(
        (
            item
            for item in logs
            if item.get("method") == "PUT"
            and str(item.get("path", "")).endswith(f"/api/journal-entries/{created['id']}")
        ),
        None,
    )
    assert hit is not None
    assert isinstance(hit.get("before_document"), dict)
    assert isinstance(hit.get("after_document"), dict)