import os
import uuid

import pytest
import requests
from dotenv import dotenv_values


# Super-admin cross-organization permissions and user-management controls
ENV_BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
FILE_BASE_URL = dotenv_values("/app/frontend/.env").get("REACT_APP_BACKEND_URL")
BASE_URL = (ENV_BASE_URL or FILE_BASE_URL or "").rstrip("/")


def _headers(token: str | None = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _login(username: str, password: str, organization_id: str):
    return requests.post(
        f"{BASE_URL}/api/auth/login",
        json={
            "username": username,
            "password": password,
            "organization_id": organization_id,
        },
        headers=_headers(),
        timeout=30,
    )


def _admin_users(token: str):
    return requests.get(f"{BASE_URL}/api/admin/users", headers=_headers(token), timeout=30)


@pytest.fixture(scope="session", autouse=True)
def require_base_url():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL is not configured")


@pytest.fixture
def super_admin_sessions():
    social_login = _login("admin", "Admin@123", "social-solidarity")
    union_login = _login("admin", "Admin@123", "general-union")
    assert social_login.status_code == 200
    assert union_login.status_code == 200
    return {
        "social": social_login.json(),
        "union": union_login.json(),
    }


@pytest.fixture
def created_user_ids():
    ids: list[str] = []
    yield ids
    cleanup_login = _login("admin", "Admin@123", "social-solidarity")
    if cleanup_login.status_code != 200:
        return
    token = cleanup_login.json().get("token")
    for user_id in ids:
        requests.delete(f"{BASE_URL}/api/admin/users/{user_id}", headers=_headers(token), timeout=30)


class TestSuperAdminCrossOrgAndControls:
    def test_super_admin_login_role_and_selected_organization(self, super_admin_sessions):
        social_user = super_admin_sessions["social"]["user"]
        union_user = super_admin_sessions["union"]["user"]

        assert social_user["role"] == "super_admin"
        assert social_user["organization_id"] == "social-solidarity"
        assert union_user["role"] == "super_admin"
        assert union_user["organization_id"] == "general-union"

    def test_super_admin_admin_users_lists_all_orgs_without_admin_account(self, super_admin_sessions):
        token = super_admin_sessions["social"]["token"]
        response = _admin_users(token)
        assert response.status_code == 200

        users = response.json()
        usernames = {item["username"] for item in users}
        orgs = {item["organization_id"] for item in users}

        assert "admin" not in usernames
        assert "social-solidarity" in orgs
        assert "general-union" in orgs

    def test_admin_users_for_regular_admin_never_shows_admin_super_account(self):
        union_login = _login("admin_union", "Admin@123", "general-union")
        social_login = _login("admin_takaful", "Admin@123", "social-solidarity")
        assert union_login.status_code == 200
        assert social_login.status_code == 200

        union_users = _admin_users(union_login.json()["token"])
        social_users = _admin_users(social_login.json()["token"])
        assert union_users.status_code == 200
        assert social_users.status_code == 200

        union_usernames = {item["username"] for item in union_users.json()}
        social_usernames = {item["username"] for item in social_users.json()}
        assert "admin" not in union_usernames
        assert "admin" not in social_usernames

    def test_regular_admins_are_org_scoped_and_cannot_see_other_org_users(self):
        union_login = _login("admin_union", "Admin@123", "general-union")
        social_login = _login("admin_takaful", "Admin@123", "social-solidarity")
        assert union_login.status_code == 200
        assert social_login.status_code == 200

        union_users = _admin_users(union_login.json()["token"]).json()
        social_users = _admin_users(social_login.json()["token"]).json()

        assert all(item["organization_id"] == "general-union" for item in union_users)
        assert all(item["organization_id"] == "social-solidarity" for item in social_users)

    def test_super_admin_can_create_admin_in_target_organization(self, super_admin_sessions, created_user_ids):
        token = super_admin_sessions["social"]["token"]
        username = f"TEST_admin_iter32_{uuid.uuid4().hex[:8]}"
        payload = {
            "username": username,
            "full_name": "اختبار سوبر أدمن",
            "password": "Admin@123",
            "role": "admin",
            "organization_id": "social-solidarity",
            "permissions": {
                "enter_deposits": True,
                "view_reports": True,
                "edit_deposits": True,
                "manage_users": True,
                "manage_reconciliations": True,
                "manage_revenues": True,
                "manage_expenses": True,
            },
            "is_active": True,
        }
        create_response = requests.post(
            f"{BASE_URL}/api/admin/users",
            json=payload,
            headers=_headers(token),
            timeout=30,
        )
        assert create_response.status_code == 200
        created = create_response.json()
        created_user_ids.append(created["id"])

        assert created["role"] == "admin"
        assert created["organization_id"] == "social-solidarity"
        assert created["username"] == username

    def test_super_admin_can_toggle_user_active_status(self, super_admin_sessions, created_user_ids):
        token = super_admin_sessions["social"]["token"]
        username = f"TEST_user_iter32_{uuid.uuid4().hex[:8]}"
        create_payload = {
            "username": username,
            "full_name": "اختبار تعطيل مستخدم",
            "password": "Admin@123",
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
        }
        create_response = requests.post(f"{BASE_URL}/api/admin/users", json=create_payload, headers=_headers(token), timeout=30)
        assert create_response.status_code == 200
        user = create_response.json()
        created_user_ids.append(user["id"])

        disable_response = requests.put(
            f"{BASE_URL}/api/admin/users/{user['id']}",
            json={"is_active": False},
            headers=_headers(token),
            timeout=30,
        )
        assert disable_response.status_code == 200
        assert disable_response.json()["is_active"] is False

        enable_response = requests.put(
            f"{BASE_URL}/api/admin/users/{user['id']}",
            json={"is_active": True},
            headers=_headers(token),
            timeout=30,
        )
        assert enable_response.status_code == 200
        assert enable_response.json()["is_active"] is True

    def test_super_admin_can_delete_normal_user_and_cannot_delete_self(self, super_admin_sessions, created_user_ids):
        token = super_admin_sessions["social"]["token"]
        super_admin_user = super_admin_sessions["social"]["user"]
        username = f"TEST_delete_iter32_{uuid.uuid4().hex[:8]}"
        create_payload = {
            "username": username,
            "full_name": "اختبار حذف مستخدم",
            "password": "Admin@123",
            "role": "user",
            "organization_id": "social-solidarity",
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
        }
        create_response = requests.post(f"{BASE_URL}/api/admin/users", json=create_payload, headers=_headers(token), timeout=30)
        assert create_response.status_code == 200
        user = create_response.json()

        delete_response = requests.delete(f"{BASE_URL}/api/admin/users/{user['id']}", headers=_headers(token), timeout=30)
        assert delete_response.status_code == 200

        # Do not attempt cleanup for already-deleted user
        self_delete = requests.delete(
            f"{BASE_URL}/api/admin/users/{super_admin_user['id']}",
            headers=_headers(token),
            timeout=30,
        )
        assert self_delete.status_code == 403

    def test_super_admin_cannot_update_self_from_admin_users_endpoint(self, super_admin_sessions):
        token = super_admin_sessions["social"]["token"]
        super_admin_user = super_admin_sessions["social"]["user"]
        update_response = requests.put(
            f"{BASE_URL}/api/admin/users/{super_admin_user['id']}",
            json={"is_active": False},
            headers=_headers(token),
            timeout=30,
        )
        assert update_response.status_code == 403

    def test_regular_admin_cannot_modify_or_delete_another_admin(self):
        union_login = _login("admin_union", "Admin@123", "general-union")
        social_login = _login("admin_takaful", "Admin@123", "social-solidarity")
        assert union_login.status_code == 200
        assert social_login.status_code == 200

        union_token = union_login.json()["token"]
        social_admin_id = social_login.json()["user"]["id"]

        update_response = requests.put(
            f"{BASE_URL}/api/admin/users/{social_admin_id}",
            json={"is_active": False},
            headers=_headers(union_token),
            timeout=30,
        )
        delete_response = requests.delete(
            f"{BASE_URL}/api/admin/users/{social_admin_id}",
            headers=_headers(union_token),
            timeout=30,
        )

        assert update_response.status_code in (403, 404)
        assert delete_response.status_code in (403, 404)
