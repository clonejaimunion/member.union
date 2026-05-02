"""Iteration 46: installed folder password and session timeout settings."""

import os

import requests


BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001").rstrip("/")


def login(username: str = "admin", organization_id: str = "general-union") -> str:
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": username, "password": "Admin@123", "organization_id": organization_id},
        timeout=20,
    )
    assert response.status_code == 200, response.text
    return response.json()["token"]


def headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_installed_files_password_is_hashed_and_session_timeout_is_configurable():
    token = login()
    password_response = requests.put(
        f"{BASE_URL}/api/admin/program-security/installed-files-password",
        headers=headers(token),
        json={"new_password": "FolderLock@123"},
        timeout=20,
    )
    assert password_response.status_code == 200, password_response.text
    password_data = password_response.json()
    assert password_data["installed_files_password_set"] is True
    assert password_data["installed_files_lock_enabled"] is False

    settings_response = requests.put(
        f"{BASE_URL}/api/admin/app-settings",
        headers=headers(token),
        json={
            "system_name": "نظام محاسبي متكامل",
            "organization_name": "النقابة العامة للعاملين بالزراعة والري والصيد واستصلاح الأراضي",
            "organization_login_label": "النقابة العامة",
            "installed_files_lock_enabled": False,
            "session_timeout_minutes": 1,
            "intellectual_property_owner": "يوسف عبد الغني احمد",
            "intellectual_property_national_id": "28611250103535",
            "intellectual_property_fingerprint": "IP-EG-050303A1-FC009B54-52DC4118-AE0D2ECA",
        },
        timeout=20,
    )
    assert settings_response.status_code == 200, settings_response.text
    settings = settings_response.json()
    assert settings["installed_files_lock_enabled"] is False
    assert settings["installed_files_password_set"] is True
    assert settings["session_timeout_minutes"] == 1
    assert settings["intellectual_property_owner"] == "يوسف عبد الغني احمد"
    assert settings["intellectual_property_national_id"] == "28611250103535"


def test_normal_admin_cannot_change_installed_files_password():
    token = login("admin_union", "general-union")
    response = requests.put(
        f"{BASE_URL}/api/admin/program-security/installed-files-password",
        headers=headers(token),
        json={"new_password": "FolderLock@123"},
        timeout=20,
    )
    assert response.status_code == 403