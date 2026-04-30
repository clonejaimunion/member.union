"""Membership module and auth guard regression tests (iteration 25)."""

import os
import time
import uuid

import pytest
import requests
from pymongo import MongoClient


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")


def _api(path: str) -> str:
    assert BASE_URL, "REACT_APP_BACKEND_URL is required for public-endpoint testing"
    return f"{BASE_URL.rstrip('/')}/api{path}"


def _login(username: str, password: str, organization_id: str):
    session = requests.Session()
    response = session.post(
        _api("/auth/login"),
        json={
            "username": username,
            "password": password,
            "organization_id": organization_id,
        },
        timeout=20,
    )
    return session, response


@pytest.fixture(scope="module")
def social_auth_headers():
    """Auth fixture for social-solidarity admin."""
    _, response = _login("admin_takaful", "Admin@123", "social-solidarity")
    if response.status_code != 200:
        _, response = _login("admin", "Admin@123", "social-solidarity")
    if response.status_code != 200:
        pytest.skip(f"Social admin login failed: {response.status_code} {response.text}")
    payload = response.json()
    return {"Authorization": f"Bearer {payload['token']}"}


@pytest.fixture(scope="module")
def union_auth_headers():
    """Auth fixture for general-union admin."""
    _, response = _login("admin_union", "Admin@123", "general-union")
    if response.status_code != 200:
        pytest.skip(f"Union admin login failed: {response.status_code} {response.text}")
    payload = response.json()
    return {"Authorization": f"Bearer {payload['token']}"}


@pytest.fixture(scope="module")
def created_member(social_auth_headers):
    """Create one membership record for search/filter/current-size checks."""
    suffix = str(uuid.uuid4())[:8]
    payload = {
        "governorate": "القاهرة",
        "union_committee": "لجنة الاختبار",
        "membership_number": f"{int(time.time())}{suffix[:2]}",
        "name": f"TEST_MEMBER_{suffix}",
        "national_id": f"2980101{int(time.time()) % 10000000:07d}",
        "birth_date": "1971-07-01",
        "address": "عنوان اختبار",
        "death_beneficiary": "المستفيد اختبار",
    }
    response = requests.post(_api("/memberships"), json=payload, headers=social_auth_headers, timeout=20)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["name"] == payload["name"]
    return body


# Auth checks requested in playbook
def test_login_sets_httponly_cookie():
    session, response = _login("admin_takaful", "Admin@123", "social-solidarity")
    if response.status_code != 200:
        session, response = _login("admin", "Admin@123", "social-solidarity")
    assert response.status_code == 200, response.text
    set_cookie_header = response.headers.get("set-cookie", "")
    assert "access_token=" in set_cookie_header
    assert "HttpOnly" in set_cookie_header


def test_bruteforce_lockout_after_5_failures():
    username = f"lock_user_{str(uuid.uuid4())[:6]}"
    for _ in range(5):
        response = requests.post(
            _api("/auth/login"),
            json={
                "username": username,
                "password": "wrong-pass",
                "organization_id": "social-solidarity",
            },
            timeout=20,
        )
        assert response.status_code == 401
    locked_response = requests.post(
        _api("/auth/login"),
        json={
            "username": username,
            "password": "wrong-pass",
            "organization_id": "social-solidarity",
        },
        timeout=20,
    )
    assert locked_response.status_code == 429


# Membership API checks
def test_membership_retirement_age_and_date(created_member):
    assert created_member["retirement_age"] == 61
    assert created_member["retirement_date"].startswith("2032-07-01")


def test_membership_invalid_national_id_rejected(social_auth_headers):
    payload = {
        "governorate": "القاهرة",
        "union_committee": "لجنة الاختبار",
        "membership_number": f"{int(time.time())}99",
        "name": "TEST_BAD_NID",
        "national_id": "12345",
        "birth_date": "1970-01-01",
        "address": "عنوان",
        "death_beneficiary": "مستفيد",
    }
    response = requests.post(_api("/memberships"), json=payload, headers=social_auth_headers, timeout=20)
    assert response.status_code in (400, 422)
    assert "14" in response.text or "min_length" in response.text


def test_membership_duplicate_membership_number_rejected(social_auth_headers, created_member):
    payload = {
        "governorate": "القاهرة",
        "union_committee": "لجنة الاختبار",
        "membership_number": created_member["membership_number"],
        "name": "TEST_DUP_NUM",
        "national_id": f"2990101{int(time.time()) % 10000000:07d}",
        "birth_date": "1970-01-01",
        "address": "عنوان",
        "death_beneficiary": "مستفيد",
    }
    response = requests.post(_api("/memberships"), json=payload, headers=social_auth_headers, timeout=20)
    assert response.status_code == 400
    assert "رقم العضوية" in response.text


def test_membership_duplicate_national_id_rejected(social_auth_headers, created_member):
    payload = {
        "governorate": "القاهرة",
        "union_committee": "لجنة الاختبار",
        "membership_number": f"{int(time.time())}88",
        "name": "TEST_DUP_NID",
        "national_id": created_member["national_id"],
        "birth_date": "1970-01-01",
        "address": "عنوان",
        "death_beneficiary": "مستفيد",
    }
    response = requests.post(_api("/memberships"), json=payload, headers=social_auth_headers, timeout=20)
    assert response.status_code == 400
    assert "الرقم القومي" in response.text


def test_membership_search_by_name_returns_created_member(social_auth_headers, created_member):
    response = requests.get(
        _api("/memberships/search"),
        params={"name": created_member["name"]},
        headers=social_auth_headers,
        timeout=20,
    )
    assert response.status_code == 200
    body = response.json()
    assert any(row["id"] == created_member["id"] for row in body)


def test_membership_retirement_filter_returns_created_member(social_auth_headers, created_member):
    response = requests.get(
        _api("/memberships/retirement"),
        params={
            "year": 2032,
            "month": 7,
            "governorate": created_member["governorate"],
            "union_committee": created_member["union_committee"],
        },
        headers=social_auth_headers,
        timeout=20,
    )
    assert response.status_code == 200
    body = response.json()
    assert any(row["id"] == created_member["id"] for row in body)


def test_membership_current_size_formula(social_auth_headers):
    response = requests.get(
        _api("/memberships/current-size"),
        params={"as_of_year": 2032, "as_of_month": 7},
        headers=social_auth_headers,
        timeout=20,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["current_membership_size"] == body["total_members"] - body["retired_members"]


def test_membership_endpoints_blocked_for_general_union(union_auth_headers):
    response = requests.get(_api("/memberships"), headers=union_auth_headers, timeout=20)
    assert response.status_code == 404


def test_modules_settings_contains_membership_key(social_auth_headers):
    response = requests.get(_api("/admin/organization/modules"), headers=social_auth_headers, timeout=20)
    assert response.status_code == 200
    body = response.json()
    assert "membership" in body["modules"]


def test_modules_settings_can_toggle_membership_visibility(social_auth_headers):
    current = requests.get(_api("/admin/organization/modules"), headers=social_auth_headers, timeout=20)
    assert current.status_code == 200
    body = current.json()
    original_modules = body["modules"].copy()

    try:
        toggled = original_modules.copy()
        toggled["membership"] = False
        update_resp = requests.put(
            _api("/admin/organization/modules"),
            headers=social_auth_headers,
            json={"modules": toggled},
            timeout=20,
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["modules"]["membership"] is False
    finally:
        restore_resp = requests.put(
            _api("/admin/organization/modules"),
            headers=social_auth_headers,
            json={"modules": original_modules},
            timeout=20,
        )
        assert restore_resp.status_code == 200


def test_admin_password_hash_uses_bcrypt_prefix():
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not mongo_url or not db_name:
        pytest.skip("MONGO_URL or DB_NAME missing")
    client = MongoClient(mongo_url)
    try:
        admin = client[db_name].users.find_one(
            {"organization_id": "social-solidarity", "username": {"$in": ["admin_takaful", "admin"]}},
            {"password_hash": 1, "_id": 0},
        )
        assert admin and isinstance(admin.get("password_hash"), str)
        assert admin["password_hash"].startswith("$2b$")
    finally:
        client.close()


def test_auth_preflight_has_explicit_origin_and_credentials_header():
    assert BASE_URL, "REACT_APP_BACKEND_URL is required"
    response = requests.options(
        _api("/auth/login"),
        headers={
            "Origin": BASE_URL.rstrip("/"),
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,authorization",
        },
        timeout=20,
    )
    assert response.status_code in (200, 204)
    assert response.headers.get("access-control-allow-origin") == BASE_URL.rstrip("/")
    assert response.headers.get("access-control-allow-credentials") == "true"