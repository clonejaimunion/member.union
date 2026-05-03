"""Iteration 46 regression: manuals, memberships, audit logs, annual report, and financial statements."""

import os
import time
import uuid
from datetime import datetime, timezone

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient


FRONTEND_ENV = dotenv_values("/app/frontend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL") or FRONTEND_ENV.get("REACT_APP_BACKEND_URL")


def _base_url() -> str:
    assert BASE_URL, "REACT_APP_BACKEND_URL is required for public-endpoint testing"
    return BASE_URL.rstrip("/")


def _api(path: str) -> str:
    return f"{_base_url()}/api{path}"


# Auth helper coverage for requested admin credentials and organization scope.
def login(username: str, password: str, organization_id: str):
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    response = session.post(
        _api("/auth/login"),
        json={
            "username": username,
            "password": password,
            "organization_id": organization_id,
        },
        timeout=25,
    )
    return session, response


@pytest.fixture(scope="module")
def auth_context():
    session, response = login("admin", "Admin@123", "social-solidarity")
    if response.status_code != 200:
        pytest.skip(f"Admin login failed for social-solidarity: {response.status_code} {response.text}")
    body = response.json()
    token = body.get("token")
    assert isinstance(token, str) and token
    assert body.get("user", {}).get("organization_id") == "social-solidarity"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    return {"session": session, "response": response, "token": token, "headers": headers}


# Membership CRUD + persistence coverage and cleanup.
@pytest.fixture
def created_membership_id(auth_context):
    suffix = str(uuid.uuid4().int)[:8]
    payload = {
        "governorate": "القاهرة",
        "union_committee": "لجنة اختبار تكامل",
        "membership_number": f"46{int(time.time())}{suffix[:2]}",
        "name": f"TEST_ITER46_MEMBER_{suffix}",
        "national_id": f"29{suffix}123456"[:14],
        "birth_date": "1976-02-14",
        "address": "عنوان اختبار تكامل",
        "death_beneficiary": "مستفيد اختبار",
    }
    create_response = requests.post(_api("/memberships"), json=payload, headers=auth_context["headers"], timeout=25)
    assert create_response.status_code == 200, create_response.text
    created = create_response.json()
    assert created["name"] == payload["name"]
    assert created["membership_number"] == payload["membership_number"]
    assert created["organization_id"] == "social-solidarity"

    membership_id = created["id"]
    try:
        yield membership_id, payload
    finally:
        requests.delete(_api(f"/memberships/{membership_id}"), headers=auth_context["headers"], timeout=25)


def test_training_manual_ar_public_pdf_without_auth():
    response = requests.get(_api("/admin/training/manual-ar.pdf"), timeout=30)
    assert response.status_code == 200, response.text
    assert "application/pdf" in response.headers.get("content-type", "")
    assert len(response.content) > 1000


def test_training_manual_en_public_pdf_without_auth():
    response = requests.get(_api("/admin/training/manual-en.pdf"), timeout=30)
    assert response.status_code == 200, response.text
    assert "application/pdf" in response.headers.get("content-type", "")
    assert len(response.content) > 1000


def test_login_admin_social_solidarity_and_cookie(auth_context):
    response = auth_context["response"]
    set_cookie = response.headers.get("set-cookie", "")
    assert response.status_code == 200
    assert "HttpOnly" in set_cookie
    assert "access_token=" in set_cookie


def test_membership_create_then_list_persistence(created_membership_id, auth_context):
    membership_id, payload = created_membership_id
    list_response = requests.get(_api("/memberships"), headers=auth_context["headers"], timeout=25)
    assert list_response.status_code == 200, list_response.text
    rows = list_response.json()
    hit = next((row for row in rows if row.get("id") == membership_id), None)
    assert hit is not None
    assert hit["name"] == payload["name"]


def test_membership_update_then_search_persistence(created_membership_id, auth_context):
    membership_id, payload = created_membership_id
    updated_payload = {
        **payload,
        "name": f"{payload['name']}_UPDATED",
        "address": "عنوان محدث لاختبار التعديل",
    }
    update_response = requests.put(
        _api(f"/memberships/{membership_id}"),
        json=updated_payload,
        headers=auth_context["headers"],
        timeout=25,
    )
    assert update_response.status_code == 200, update_response.text
    body = update_response.json()
    assert body["name"] == updated_payload["name"]
    assert body["address"] == updated_payload["address"]

    search_response = requests.get(
        _api("/memberships/search"),
        params={"name": updated_payload["name"]},
        headers=auth_context["headers"],
        timeout=25,
    )
    assert search_response.status_code == 200, search_response.text
    rows = search_response.json()
    hit = next((row for row in rows if row.get("id") == membership_id), None)
    assert hit is not None
    assert hit["name"] == updated_payload["name"]


def test_membership_delete_then_not_in_list(auth_context):
    suffix = str(uuid.uuid4().int)[:8]
    payload = {
        "governorate": "الجيزة",
        "union_committee": "لجنة حذف اختبار",
        "membership_number": f"46{int(time.time())}{suffix[:2]}",
        "name": f"TEST_ITER46_DELETE_{suffix}",
        "national_id": f"28{suffix}654321"[:14],
        "birth_date": "1975-05-20",
        "address": "عنوان حذف",
        "death_beneficiary": "مستفيد حذف",
    }
    create_response = requests.post(_api("/memberships"), json=payload, headers=auth_context["headers"], timeout=25)
    assert create_response.status_code == 200, create_response.text
    membership_id = create_response.json()["id"]

    delete_response = requests.delete(_api(f"/memberships/{membership_id}"), headers=auth_context["headers"], timeout=25)
    assert delete_response.status_code == 200, delete_response.text
    delete_body = delete_response.json()
    assert delete_body.get("deleted_id") == membership_id

    list_response = requests.get(_api("/memberships"), headers=auth_context["headers"], timeout=25)
    assert list_response.status_code == 200, list_response.text
    rows = list_response.json()
    assert all(row.get("id") != membership_id for row in rows)


def test_audit_log_has_membership_update_and_delete_entries(created_membership_id, auth_context):
    membership_id, payload = created_membership_id
    update_payload = {
        **payload,
        "name": f"{payload['name']}_AUDIT",
    }
    update_response = requests.put(
        _api(f"/memberships/{membership_id}"),
        json=update_payload,
        headers=auth_context["headers"],
        timeout=25,
    )
    assert update_response.status_code == 200, update_response.text

    delete_response = requests.delete(_api(f"/memberships/{membership_id}"), headers=auth_context["headers"], timeout=25)
    assert delete_response.status_code == 200, delete_response.text

    logs_response = requests.get(_api("/admin/security/audit-logs"), params={"limit": 300}, headers=auth_context["headers"], timeout=25)
    assert logs_response.status_code == 200, logs_response.text
    logs = logs_response.json()

    update_log = next(
        (
            item
            for item in logs
            if item.get("method") == "PUT"
            and item.get("path") == f"/api/memberships/{membership_id}"
            and item.get("status_code") < 400
        ),
        None,
    )
    delete_log = next(
        (
            item
            for item in logs
            if item.get("method") == "DELETE"
            and item.get("path") == f"/api/memberships/{membership_id}"
            and item.get("status_code") < 400
        ),
        None,
    )

    assert update_log is not None
    assert delete_log is not None
    assert isinstance(update_log.get("arabic_description"), str) and update_log.get("arabic_description")
    assert isinstance(delete_log.get("arabic_description"), str) and delete_log.get("arabic_description")


def test_memberships_annual_report_works(auth_context):
    year = datetime.now(timezone.utc).year
    response = requests.get(_api("/memberships/annual-report"), params={"year": year}, headers=auth_context["headers"], timeout=25)
    assert response.status_code == 200, response.text
    data = response.json()
    assert isinstance(data.get("rows"), list)
    assert isinstance(data.get("totals"), dict)
    assert "current_membership_size" in data["totals"]


def test_financial_statements_contains_accounting_corrections(auth_context):
    year = datetime.now(timezone.utc).year
    response = requests.get(
        _api("/financial-statements"),
        params={"from_date": f"{year}-01-01", "to_date": f"{year}-12-31"},
        headers=auth_context["headers"],
        timeout=30,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert "accounting_corrections" in data
    assert isinstance(data["accounting_corrections"], list)


# Playbook auth checks: bcrypt/hash format, CORS credentials, brute-force lockout and seed-admin update path.
def test_bcrypt_hash_format_starts_with_2b_in_db():
    env_values = dotenv_values("/app/backend/.env")
    mongo_url = os.environ.get("MONGO_URL") or env_values.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME") or env_values.get("DB_NAME")
    if not mongo_url or not db_name:
        pytest.skip("MONGO_URL or DB_NAME missing")

    client = MongoClient(str(mongo_url).strip())
    try:
        user = client[str(db_name).strip()].users.find_one({"username": "admin"}, {"_id": 0, "password_hash": 1})
        assert user and isinstance(user.get("password_hash"), str)
        assert user["password_hash"].startswith("$2b$")
    finally:
        client.close()


def test_auth_cors_preflight_has_credentials_header():
    origin = _base_url()
    response = requests.options(
        _api("/auth/login"),
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,authorization",
        },
        timeout=25,
    )
    assert response.status_code in (200, 204)
    assert response.headers.get("access-control-allow-credentials") == "true"
    assert response.headers.get("access-control-allow-origin") == origin


def test_lockout_happens_after_3_failed_attempts_per_user_policy():
    username = f"TEST_iter46_lockout_{str(uuid.uuid4())[:8]}"
    payload = {
        "username": username,
        "password": "wrong-password",
        "organization_id": "social-solidarity",
    }
    statuses = []
    for _ in range(4):
        response = requests.post(_api("/auth/login"), json=payload, timeout=25)
        statuses.append(response.status_code)
    assert statuses[:3] == [401, 401, 401]
    assert statuses[3] == 429


def test_seed_admin_update_logic_present():
    with open("/app/backend/server.py", "r", encoding="utf-8") as handle:
        content = handle.read()
    assert "ensure_default_admin" in content
    assert "if not verify_password(ADMIN_INITIAL_PASSWORD, existing.get(\"password_hash\", \"\"))" in content
    assert "document[\"password_hash\"] = hash_password(ADMIN_INITIAL_PASSWORD)" in content
