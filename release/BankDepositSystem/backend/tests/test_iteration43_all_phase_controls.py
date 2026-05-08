"""Iteration 43: super-admin training, logos, organizations, backup policy, and 2FA policy."""

import os
import time

import requests


BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001").rstrip("/")


def login(username: str, password: str, organization_id: str) -> str:
    response = requests.post(f"{BASE_URL}/api/auth/login", json={"username": username, "password": password, "organization_id": organization_id}, timeout=20)
    assert response.status_code == 200, response.text
    return response.json()["token"]


def headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_super_admin_can_save_logo_email_backup_and_2fa_policies():
    token = login("admin", "Admin@123", "general-union")
    payload = {
        "system_name": "نظام محاسبي متكامل",
        "organization_name": "النقابة العامة للعاملين بالزراعة والري والصيد واستصلاح الأراضي",
        "organization_login_label": "النقابة العامة",
        "organization_names": {"general-union": "النقابة العامة للعاملين بالزراعة والري والصيد واستصلاح الأراضي", "social-solidarity": "مشروع التكافل الاجتماعي"},
        "organization_login_labels": {"general-union": "النقابة العامة", "social-solidarity": "مشروع التكافل الاجتماعي"},
        "organization_emails": {"general-union": "union@example.com", "social-solidarity": "solidarity@example.com"},
        "login_union_logo_visible": False,
        "login_authority_logos": [{"name": "مصلحة الضرائب المصرية", "enabled": True, "src": ""}],
        "backup_enabled": True,
        "backup_allowed_roles": {"super_admin": True, "admin": True, "user": False},
        "two_factor_role_policy": {"super_admin": False, "admin": False, "user": False},
    }
    response = requests.put(f"{BASE_URL}/api/admin/app-settings", json=payload, headers=headers(token), timeout=20)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["login_union_logo_visible"] is False
    assert data["organizations"]["general-union"]["email"] is None
    assert data["backup_allowed_roles"]["admin"] is True
    assert data["two_factor_role_policy"]["admin"] is False


def test_training_exports_are_generated_and_do_not_mention_super_admin():
    token = login("admin", "Admin@123", "general-union")
    for path, content_type in [
        ("/api/admin/training/manual.pdf", "application/pdf"),
        ("/api/admin/training/screenshots.zip", "application/zip"),
        ("/api/admin/training/video-guide.gif", "image/gif"),
    ]:
        response = requests.get(f"{BASE_URL}{path}", headers=headers(token), timeout=30)
        assert response.status_code == 200, response.text
        assert content_type in response.headers.get("content-type", "")
        assert len(response.content) > 1000
        assert b"super_admin" not in response.content


def test_super_admin_can_add_and_disable_custom_organization():
    token = login("admin", "Admin@123", "general-union")
    suffix = int(time.time())
    response = requests.post(
        f"{BASE_URL}/api/admin/organizations",
        headers=headers(token),
        json={"name": f"جهة اختبار {suffix}", "login_label": f"اختبار {suffix}", "email": "test@example.com", "clone_from": "social-solidarity"},
        timeout=20,
    )
    assert response.status_code == 200, response.text
    org_id = response.json()["id"]
    assert response.json()["modules"]

    disable = requests.put(f"{BASE_URL}/api/admin/organizations/{org_id}", headers=headers(token), json={"is_active": False}, timeout=20)
    assert disable.status_code == 200
    assert disable.json()["is_active"] is False


def test_normal_admin_cannot_clear_audit_logs_or_create_organization():
    token = login("admin_union", "Admin@123", "general-union")
    assert requests.delete(f"{BASE_URL}/api/admin/security/audit-logs", headers=headers(token), timeout=20).status_code == 403
    assert requests.post(f"{BASE_URL}/api/admin/organizations", headers=headers(token), json={"name": "x"}, timeout=20).status_code == 403