"""Iteration 41: super-admin branding settings and login logo cards."""

import os

import requests


BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001").rstrip("/")


def login(username: str, password: str, organization_id: str) -> str:
    response = requests.post(f"{BASE_URL}/api/auth/login", json={"username": username, "password": password, "organization_id": organization_id}, timeout=20)
    assert response.status_code == 200, response.text
    return response.json()["token"]


def headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_only_super_admin_can_update_global_branding_settings():
    super_token = login("admin", "Admin@123", "general-union")
    normal_token = login("admin_union", "Admin@123", "general-union")

    denied = requests.put(
        f"{BASE_URL}/api/admin/app-settings",
        headers=headers(normal_token),
        json={"system_name": "نظام محاسبي متكامل", "organization_name": "النقابة العامة"},
        timeout=20,
    )
    assert denied.status_code == 403

    payload = {
        "system_name": "نظام محاسبي متكامل",
        "organization_name": "النقابة العامة للعاملين بالزراعة والري والصيد واستصلاح الأراضي",
        "organization_login_label": "النقابة العامة",
        "organization_names": {
            "general-union": "النقابة العامة للعاملين بالزراعة والري والصيد واستصلاح الأراضي",
            "social-solidarity": "مشروع التكافل الاجتماعي",
        },
        "organization_login_labels": {"general-union": "النقابة العامة", "social-solidarity": "مشروع التكافل الاجتماعي"},
    }
    response = requests.put(f"{BASE_URL}/api/admin/app-settings", headers=headers(super_token), json=payload, timeout=20)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["system_name"] == payload["system_name"]
    assert data["organizations"]["general-union"]["name"] == payload["organization_names"]["general-union"]
    assert data["organizations"]["social-solidarity"]["login_label"] == "مشروع التكافل الاجتماعي"


def test_public_settings_expose_updated_organization_labels():
    response = requests.get(f"{BASE_URL}/api/app-settings/public", timeout=20)
    assert response.status_code == 200
    data = response.json()
    assert "organizations" in data
    assert data["organizations"]["general-union"]["login_label"] == "النقابة العامة"
    assert data["organizations"]["social-solidarity"]["login_label"] == "مشروع التكافل الاجتماعي"