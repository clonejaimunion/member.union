"""Iteration 35: local super-admin 2FA reset recovery tool checks."""

import json
import os
import subprocess
from pathlib import Path

import requests
from dotenv import dotenv_values
from pymongo import MongoClient


BACKEND_ENV = dotenv_values("/app/backend/.env")
MONGO_URL = os.environ.get("MONGO_URL") or BACKEND_ENV.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME") or BACKEND_ENV.get("DB_NAME")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001").rstrip("/")


def test_local_reset_tool_is_packaged_in_release_and_installer_exists():
    assert Path("/app/backend/reset_super_admin_2fa.py").exists()
    assert Path("/app/local_install/reset_super_admin_2fa.bat").exists()
    assert Path("/app/release/BankDepositSystem/backend/reset_super_admin_2fa.py").exists()
    assert Path("/app/release/BankDepositSystem/reset_super_admin_2fa.bat").exists()
    assert Path("/app/dist/BankDepositSystemSetup.exe").stat().st_size > 0


def test_reset_tool_disables_super_admin_2fa_and_login_without_otp_then_restore():
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    user = db.users.find_one(
        {"username": "admin", "$or": [{"role": "super_admin"}, {"is_super_admin": True}]},
        {"_id": 0},
    )
    assert user
    original = {
        "totp_enabled": user.get("totp_enabled", False),
        "totp_secret": user.get("totp_secret"),
        "totp_pending_secret": user.get("totp_pending_secret"),
    }

    try:
        result = subprocess.run(
            ["python", "/app/backend/reset_super_admin_2fa.py"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stderr or result.stdout

        updated = db.users.find_one({"id": user["id"]}, {"_id": 0})
        assert updated.get("totp_enabled") is False
        assert updated.get("totp_secret") is None
        assert updated.get("totp_pending_secret") is None

        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": "admin", "password": "Admin@123", "organization_id": "general-union"},
            timeout=20,
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload.get("requires_2fa") is False
        assert payload.get("user", {}).get("role") == "super_admin"
        assert payload.get("token")
    finally:
        db.users.update_one({"id": user["id"]}, {"$set": original})
        client.close()