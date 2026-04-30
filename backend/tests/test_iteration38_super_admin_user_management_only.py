"""Iteration 38: user management is reserved for hidden super admin `admin`."""

import os
import time

import requests


BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001").rstrip("/")


def login(username: str, password: str, organization_id: str) -> str:
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": username, "password": password, "organization_id": organization_id},
        timeout=20,
    )
    assert response.status_code == 200, response.text
    token = response.json().get("token")
    assert token
    return token


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_normal_admin_cannot_list_registered_users():
    token = login("admin_union", "Admin@123", "general-union")
    response = requests.get(f"{BASE_URL}/api/admin/users", headers=auth_header(token), timeout=20)
    assert response.status_code == 403
    assert "السوبر أدمن admin فقط" in response.json()["detail"]


def test_super_admin_can_create_edit_disable_enable_and_delete_user_or_normal_admin():
    super_token = login("admin", "Admin@123", "general-union")
    normal_token = login("admin_union", "Admin@123", "general-union")
    username = f"temp_manage_{int(time.time())}"

    list_response = requests.get(f"{BASE_URL}/api/admin/users", headers=auth_header(super_token), timeout=20)
    assert list_response.status_code == 200
    assert all(item["username"] != "admin" and item["role"] != "super_admin" for item in list_response.json())

    create_response = requests.post(
        f"{BASE_URL}/api/admin/users",
        headers=auth_header(super_token),
        json={
            "username": username,
            "full_name": "مستخدم اختبار الإدارة",
            "password": "TempPass123",
            "role": "user",
            "organization_id": "general-union",
            "permissions": {"enter_deposits": True, "view_reports": True, "edit_deposits": False, "manage_users": False, "manage_reconciliations": True, "manage_revenues": True, "manage_expenses": True},
            "is_active": True,
        },
        timeout=20,
    )
    assert create_response.status_code == 200, create_response.text
    user_id = create_response.json()["id"]

    try:
        normal_delete = requests.delete(f"{BASE_URL}/api/admin/users/{user_id}", headers=auth_header(normal_token), timeout=20)
        assert normal_delete.status_code == 403

        update_response = requests.put(
            f"{BASE_URL}/api/admin/users/{user_id}",
            headers=auth_header(super_token),
            json={"role": "admin", "full_name": "مدير اختبار الإدارة"},
            timeout=20,
        )
        assert update_response.status_code == 200, update_response.text
        assert update_response.json()["role"] == "admin"
        assert update_response.json()["full_name"] == "مدير اختبار الإدارة"

        disable_response = requests.put(f"{BASE_URL}/api/admin/users/{user_id}", headers=auth_header(super_token), json={"is_active": False}, timeout=20)
        assert disable_response.status_code == 200
        assert disable_response.json()["is_active"] is False

        enable_response = requests.put(f"{BASE_URL}/api/admin/users/{user_id}", headers=auth_header(super_token), json={"is_active": True}, timeout=20)
        assert enable_response.status_code == 200
        assert enable_response.json()["is_active"] is True
    finally:
        requests.delete(f"{BASE_URL}/api/admin/users/{user_id}", headers=auth_header(super_token), timeout=20)


def test_super_admin_itself_cannot_be_managed_from_users_endpoint():
    super_token = login("admin", "Admin@123", "general-union")
    me_response = requests.get(f"{BASE_URL}/api/auth/me", headers=auth_header(super_token), timeout=20)
    assert me_response.status_code == 200
    super_id = me_response.json()["id"]

    update_response = requests.put(f"{BASE_URL}/api/admin/users/{super_id}", headers=auth_header(super_token), json={"is_active": False}, timeout=20)
    assert update_response.status_code == 403

    delete_response = requests.delete(f"{BASE_URL}/api/admin/users/{super_id}", headers=auth_header(super_token), timeout=20)
    assert delete_response.status_code == 403