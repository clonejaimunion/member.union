"""Iteration 36: two-factor authentication is permanently disabled."""

import os
from pathlib import Path

import requests
from dotenv import dotenv_values
from pymongo import MongoClient


BACKEND_ENV = dotenv_values("/app/backend/.env")
MONGO_URL = os.environ.get("MONGO_URL") or BACKEND_ENV.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME") or BACKEND_ENV.get("DB_NAME")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001").rstrip("/")


def test_all_users_have_two_factor_fields_disabled():
    client = MongoClient(MONGO_URL)
    try:
        db = client[DB_NAME]
        assert db.users.count_documents({"totp_enabled": True}) == 0
        assert db.users.count_documents({"totp_secret": {"$nin": [None, ""]}}) == 0
        assert db.users.count_documents({"totp_pending_secret": {"$nin": [None, ""]}}) == 0
    finally:
        client.close()


def test_super_admin_login_never_requires_otp_for_either_organization():
    for organization_id in ["general-union", "social-solidarity"]:
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": "admin", "password": "Admin@123", "organization_id": organization_id},
            timeout=20,
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["requires_2fa"] is False
        assert payload["requires_2fa_setup"] is False
        assert payload["user"]["role"] == "super_admin"
        assert payload["token"]


def test_two_factor_endpoints_are_permanently_disabled():
    login = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": "admin_union", "password": "Admin@123", "organization_id": "general-union"},
        timeout=20,
    )
    assert login.status_code == 200
    token = login.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    for path in ["/api/admin/2fa/setup", "/api/admin/2fa/verify"]:
        response = requests.post(f"{BASE_URL}{path}", json={"otp_code": "000000"}, headers=headers, timeout=20)
        assert response.status_code == 410
        assert "تم إلغاء المصادقة الثنائية" in response.json()["detail"]


def test_packaged_release_has_no_two_factor_reset_tool():
    assert Path("/app/dist/BankDepositSystemSetup.exe").stat().st_size > 0
    assert not Path("/app/release/BankDepositSystem/reset_super_admin_2fa.bat").exists()
    assert not Path("/app/release/BankDepositSystem/backend/reset_super_admin_2fa.py").exists()