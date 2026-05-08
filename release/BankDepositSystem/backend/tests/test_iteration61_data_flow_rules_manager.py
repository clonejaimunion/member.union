import os
import uuid

import pytest
import requests
from dotenv import dotenv_values


# Modules/features under test: Data Flow & Rules Manager APIs, super-admin access guard, rule update audit trail, journal immutability
FRONTEND_ENV = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or FRONTEND_ENV.get("REACT_APP_BACKEND_URL") or "").rstrip("/")


@pytest.fixture(scope="session")
def base_url():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL is not configured")
    return BASE_URL


@pytest.fixture(scope="session")
def session_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _login(base_url: str, session_client: requests.Session, username: str, password: str, organization_id: str):
    return session_client.post(
        f"{base_url}/api/auth/login",
        json={
            "username": username,
            "password": password,
            "organization_id": organization_id,
        },
        timeout=40,
    )


@pytest.fixture(scope="session")
def super_admin_headers(base_url, session_client):
    response = _login(base_url, session_client, "admin", "Admin@123", "social-solidarity")
    if response.status_code != 200:
        pytest.skip(f"super admin login failed: {response.status_code} {response.text}")
    token = response.json().get("token")
    if not token:
        pytest.skip("missing super admin token")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def normal_admin_headers(base_url, session_client):
    response = _login(base_url, session_client, "admin_takaful", "Admin@123", "social-solidarity")
    if response.status_code != 200:
        pytest.skip(f"normal admin login failed: {response.status_code} {response.text}")
    token = response.json().get("token")
    if not token:
        pytest.skip("missing normal admin token")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _fetch_manager_data(base_url: str, session_client: requests.Session, headers: dict, organization_id: str = "social-solidarity"):
    response = session_client.get(
        f"{base_url}/api/admin/data-flow-rules-manager",
        headers=headers,
        params={"organization_id": organization_id},
        timeout=80,
    )
    return response


def test_login_sets_http_only_cookie(base_url, session_client):
    response = _login(base_url, session_client, "admin", "Admin@123", "social-solidarity")
    assert response.status_code == 200
    assert "httponly" in (response.headers.get("set-cookie", "").lower())


def test_data_flow_rules_manager_super_admin_only(base_url, session_client, normal_admin_headers):
    response = _fetch_manager_data(base_url, session_client, normal_admin_headers)
    assert response.status_code == 403


def test_get_data_flow_rules_manager_payload_shape(base_url, session_client, super_admin_headers):
    response = _fetch_manager_data(base_url, session_client, super_admin_headers)
    assert response.status_code == 200, response.text
    payload = response.json()

    assert isinstance(payload.get("flow_monitor"), list)
    assert isinstance(payload.get("rules"), list)
    assert isinstance(payload.get("validation_tests"), list)

    expected_stage_keys = {
        "input",
        "auto_validation",
        "journal_creation",
        "journal",
        "ledger",
        "trial_balance",
        "financial_statements",
    }
    actual_stage_keys = {stage.get("stage_key") for stage in payload.get("flow_monitor", [])}
    assert expected_stage_keys.issubset(actual_stage_keys)

    for stage in payload.get("flow_monitor", []):
        assert "status" in stage
        assert "operations_count" in stage
        assert "last_run" in stage
        assert "errors_count" in stage

    first_rule = (payload.get("rules") or [None])[0]
    assert first_rule is not None
    assert "event_type" in first_rule
    assert "debit_account" in first_rule
    assert "credit_account" in first_rule
    assert "is_active" in first_rule


def test_validation_tests_all_success_for_current_data(base_url, session_client, super_admin_headers):
    response = _fetch_manager_data(base_url, session_client, super_admin_headers)
    assert response.status_code == 200, response.text
    validation_tests = response.json().get("validation_tests") or []

    expected_keys = {"journal_balance", "ledger", "trial_balance", "balance_sheet", "membership"}
    actual_keys = {item.get("test_key") for item in validation_tests}
    assert expected_keys.issubset(actual_keys)
    assert all(item.get("status") == "ناجح" for item in validation_tests if item.get("test_key") in expected_keys)


def test_put_rule_updates_rule_only_and_writes_audit_before_after(base_url, session_client, super_admin_headers):
    before_manager_resp = _fetch_manager_data(base_url, session_client, super_admin_headers)
    assert before_manager_resp.status_code == 200, before_manager_resp.text
    before_manager = before_manager_resp.json()

    target_rule = (before_manager.get("rules") or [None])[0]
    assert target_rule is not None
    rule_id = target_rule["id"]

    entries_before_resp = session_client.get(f"{base_url}/api/journal-entries", headers=super_admin_headers, timeout=80)
    assert entries_before_resp.status_code == 200, entries_before_resp.text
    entries_before_count = len(entries_before_resp.json())

    marker = f"TEST_ITER61_{uuid.uuid4().hex[:6]}"
    updated_payload = {
        "event_type": target_rule["event_type"],
        "sub_type": target_rule.get("sub_type"),
        "payment_method": target_rule.get("payment_method"),
        "debit_account": target_rule["debit_account"],
        "credit_account": target_rule["credit_account"],
        "priority": int(target_rule.get("priority", 5)),
        "is_active": bool(target_rule.get("is_active", True)),
        "notes": marker,
    }
    update_resp = session_client.put(
        f"{base_url}/api/admin/data-flow-rules-manager/rules/{rule_id}",
        headers=super_admin_headers,
        params={"organization_id": "social-solidarity"},
        json=updated_payload,
        timeout=80,
    )
    assert update_resp.status_code == 200, update_resp.text
    updated_rule = update_resp.json()
    assert updated_rule.get("notes") == marker

    # Restore the original value immediately to keep test non-destructive.
    restore_payload = {
        "event_type": target_rule["event_type"],
        "sub_type": target_rule.get("sub_type"),
        "payment_method": target_rule.get("payment_method"),
        "debit_account": target_rule["debit_account"],
        "credit_account": target_rule["credit_account"],
        "priority": int(target_rule.get("priority", 5)),
        "is_active": bool(target_rule.get("is_active", True)),
        "notes": target_rule.get("notes"),
    }
    restore_resp = session_client.put(
        f"{base_url}/api/admin/data-flow-rules-manager/rules/{rule_id}",
        headers=super_admin_headers,
        params={"organization_id": "social-solidarity"},
        json=restore_payload,
        timeout=80,
    )
    assert restore_resp.status_code == 200, restore_resp.text

    entries_after_resp = session_client.get(f"{base_url}/api/journal-entries", headers=super_admin_headers, timeout=80)
    assert entries_after_resp.status_code == 200, entries_after_resp.text
    entries_after_count = len(entries_after_resp.json())
    assert entries_before_count == entries_after_count

    audit_resp = session_client.get(
        f"{base_url}/api/admin/security/audit-logs",
        headers=super_admin_headers,
        params={"limit": 250},
        timeout=80,
    )
    assert audit_resp.status_code == 200, audit_resp.text
    logs = audit_resp.json()
    path_suffix = f"/api/admin/data-flow-rules-manager/rules/{rule_id}"
    matched = [
        item
        for item in logs
        if item.get("method") == "PUT"
        and item.get("path") == path_suffix
        and item.get("before_document")
        and item.get("after_document")
    ]
    assert len(matched) >= 1