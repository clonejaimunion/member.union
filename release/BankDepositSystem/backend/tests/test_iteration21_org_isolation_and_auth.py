import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from dotenv import dotenv_values


# Organization split + auth hardening checks
ENV_BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
FILE_BASE_URL = dotenv_values("/app/frontend/.env").get("REACT_APP_BACKEND_URL")
BASE_URL = (ENV_BASE_URL or FILE_BASE_URL or "").rstrip("/")


def _headers(token: str | None = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _login(username: str, password: str, organization_id: str):
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={
            "username": username,
            "password": password,
            "organization_id": organization_id,
        },
        headers=_headers(),
        timeout=30,
    )
    return response


@pytest.fixture(scope="session", autouse=True)
def require_base_url():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL is not configured")


class TestOrganizationIsolation:
    def test_public_organizations_has_two_expected_orgs(self):
        response = requests.get(f"{BASE_URL}/api/organizations/public", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        ids = {item.get("id") for item in data}
        assert "social-solidarity" in ids
        assert "general-union" in ids

    def test_admin_takaful_login_matrix(self):
        ok = _login("admin_takaful", "Admin@123", "social-solidarity")
        bad = _login("admin_takaful", "Admin@123", "general-union")

        assert ok.status_code == 200
        ok_data = ok.json()
        assert ok_data["user"]["username"] == "admin_takaful"
        assert ok_data["user"]["organization_id"] == "social-solidarity"

        assert bad.status_code == 401

    def test_admin_union_login_matrix(self):
        ok = _login("admin_union", "Admin@123", "general-union")
        bad = _login("admin_union", "Admin@123", "social-solidarity")

        assert ok.status_code == 200
        ok_data = ok.json()
        assert ok_data["user"]["username"] == "admin_union"
        assert ok_data["user"]["organization_id"] == "general-union"

        assert bad.status_code == 401

    def test_admin_users_are_scoped_per_organization(self):
        social_login = _login("admin_takaful", "Admin@123", "social-solidarity")
        union_login = _login("admin_union", "Admin@123", "general-union")
        assert social_login.status_code == 200
        assert union_login.status_code == 200

        social_token = social_login.json()["token"]
        union_token = union_login.json()["token"]

        social_users_response = requests.get(
            f"{BASE_URL}/api/admin/users", headers=_headers(social_token), timeout=30
        )
        union_users_response = requests.get(
            f"{BASE_URL}/api/admin/users", headers=_headers(union_token), timeout=30
        )
        assert social_users_response.status_code == 200
        assert union_users_response.status_code == 200

        social_users = social_users_response.json()
        union_users = union_users_response.json()

        assert all(item.get("organization_id") == "social-solidarity" for item in social_users)
        assert all(item.get("organization_id") == "general-union" for item in union_users)

        social_usernames = {item.get("username") for item in social_users}
        union_usernames = {item.get("username") for item in union_users}
        assert "admin_union" not in social_usernames
        assert "admin_takaful" not in union_usernames

    def test_social_deposit_not_visible_or_deletable_in_union(self):
        social_login = _login("admin_takaful", "Admin@123", "social-solidarity")
        union_login = _login("admin_union", "Admin@123", "general-union")
        assert social_login.status_code == 200
        assert union_login.status_code == 200

        social_token = social_login.json()["token"]
        union_token = union_login.json()["token"]
        bank_id = "industrial-development"
        now = datetime.now(timezone.utc)

        create_payload = {
            "account_number": f"TEST-ACC-{uuid.uuid4().hex[:8]}",
            "deposit_number": f"TEST-DEP-{uuid.uuid4().hex[:8]}",
            "amount": 12345.67,
            "creation_datetime": now.isoformat(),
            "maturity_datetime": (now + timedelta(days=365)).isoformat(),
            "monthly_interest_rate": 12,
        }

        create_response = requests.post(
            f"{BASE_URL}/api/banks/{bank_id}/deposits",
            json=create_payload,
            headers=_headers(social_token),
            timeout=30,
        )
        assert create_response.status_code == 200
        created = create_response.json()
        deposit_id = created["id"]

        social_list = requests.get(
            f"{BASE_URL}/api/banks/{bank_id}/deposits",
            headers=_headers(social_token),
            timeout=30,
        )
        union_list = requests.get(
            f"{BASE_URL}/api/banks/{bank_id}/deposits",
            headers=_headers(union_token),
            timeout=30,
        )
        assert social_list.status_code == 200
        assert union_list.status_code == 200

        social_ids = {item["id"] for item in social_list.json()}
        union_ids = {item["id"] for item in union_list.json()}
        assert deposit_id in social_ids
        assert deposit_id not in union_ids

        union_delete = requests.delete(
            f"{BASE_URL}/api/banks/{bank_id}/deposits/{deposit_id}",
            headers=_headers(union_token),
            timeout=30,
        )
        assert union_delete.status_code == 404

        social_delete = requests.delete(
            f"{BASE_URL}/api/banks/{bank_id}/deposits/{deposit_id}",
            headers=_headers(social_token),
            timeout=30,
        )
        assert social_delete.status_code == 200


class TestAuthPlaybookChecks:
    def test_login_sets_httponly_cookie(self):
        response = _login("admin_takaful", "Admin@123", "social-solidarity")
        assert response.status_code == 200
        set_cookie = response.headers.get("set-cookie", "")
        assert "HttpOnly" in set_cookie
        assert "__cf_bm=" not in set_cookie

    def test_cors_is_explicit_with_credentials(self):
        headers = {
            "Origin": BASE_URL,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,authorization",
        }
        response = requests.options(f"{BASE_URL}/api/auth/login", headers=headers, timeout=30)
        assert response.status_code in (200, 204)
        allow_credentials = response.headers.get("access-control-allow-credentials", "")
        allow_origin = response.headers.get("access-control-allow-origin", "")
        assert allow_credentials.lower() == "true"
        assert allow_origin != "*"

    def test_bruteforce_lockout_after_five_failures(self):
        for _ in range(5):
            failed = _login("admin_takaful", "WrongPass@123", "social-solidarity")
            assert failed.status_code == 401

        post_fail_valid = _login("admin_takaful", "Admin@123", "social-solidarity")
        assert post_fail_valid.status_code in (401, 423, 429)
