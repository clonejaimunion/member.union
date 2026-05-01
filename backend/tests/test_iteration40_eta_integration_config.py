"""Iteration 40: Egyptian Tax Authority integration settings are super-admin only."""

import os

import requests


BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001").rstrip("/")


def login(username: str, password: str, organization_id: str) -> str:
    response = requests.post(f"{BASE_URL}/api/auth/login", json={"username": username, "password": password, "organization_id": organization_id}, timeout=20)
    assert response.status_code == 200, response.text
    return response.json()["token"]


def headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_eta_integration_is_super_admin_only_and_redacts_secrets():
    super_token = login("admin", "Admin@123", "general-union")
    normal_token = login("admin_union", "Admin@123", "general-union")

    denied = requests.get(f"{BASE_URL}/api/admin/eta-integration", headers=headers(normal_token), timeout=20)
    assert denied.status_code == 403

    payload = {
        "environment": "preprod",
        "issuer_tax_number": "123456789",
        "issuer_name": "النقابة العامة للعاملين بالزراعة والري",
        "branch_code": "0",
        "activity_code": "9499",
        "client_id": "demo-client",
        "client_secret": "demo-secret",
        "sdk_command_template": "",
        "certificate_label": "USB Token",
        "token_pin": "123456",
        "auto_submit_after_generation": False,
        "portal_url": "https://preprod.invoicing.eta.gov.eg",
        "notes": "اختبار إعدادات الربط",
    }
    saved = requests.put(f"{BASE_URL}/api/admin/eta-integration", json=payload, headers=headers(super_token), timeout=20)
    assert saved.status_code == 200, saved.text
    data = saved.json()
    assert data["has_client_secret"] is True
    assert data["has_token_pin"] is True
    assert "client_secret" not in data
    assert data["is_configured"] is False
    assert "أمر SDK/أداة التوقيع الرقمي" in data["required_items"]


def test_eta_connection_test_requires_sdk_configuration_not_mocked():
    super_token = login("admin", "Admin@123", "general-union")
    response = requests.post(f"{BASE_URL}/api/admin/eta-integration/test-connection", headers=headers(super_token), timeout=20)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "configuration_required"
    assert "SDK" in data["message"]