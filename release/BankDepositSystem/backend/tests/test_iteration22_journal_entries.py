"""Iteration 22: Journal entries + module toggle + auth playbook checks on public endpoint."""

import os
import uuid
from datetime import date

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient


# Modules/features under test: journal entries, banking-expenses auto journal, organization module toggle, auth playbook guards
ENV_BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
FILE_BASE_URL = dotenv_values("/app/frontend/.env").get("REACT_APP_BACKEND_URL")
BASE_URL = (ENV_BASE_URL or FILE_BASE_URL or "").rstrip("/")

MONGO_URL = dotenv_values("/app/backend/.env").get("MONGO_URL", "").strip('"')
DB_NAME = dotenv_values("/app/backend/.env").get("DB_NAME", "").strip('"')


def _headers(token: str | None = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _login(username: str, password: str, organization_id: str):
    return requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": username, "password": password, "organization_id": organization_id},
        headers=_headers(),
        timeout=30,
    )


def _create_balanced_manual_journal(token: str, ref: str, amount: float = 100.0):
    payload = {
        "entry_date": date.today().isoformat(),
        "description": f"TEST ITER22 JOURNAL {ref}",
        "reference": ref,
        "lines": [
            {"account_name": "البنك", "debit": amount, "credit": 0},
            {"account_name": "الإيرادات", "debit": 0, "credit": amount},
        ],
    }
    response = requests.post(f"{BASE_URL}/api/journal-entries", json=payload, headers=_headers(token), timeout=30)
    return response


@pytest.fixture(scope="session", autouse=True)
def require_base_url():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL is not configured")


@pytest.fixture(scope="session")
def social_admin_token():
    login = _login("admin_takaful", "Admin@123", "social-solidarity")
    if login.status_code != 200:
        pytest.skip(f"social-solidarity admin login failed: {login.status_code}")
    body = login.json()
    token = body.get("token")
    if not token:
        pytest.skip("No token for social admin")
    return token


@pytest.fixture(scope="session")
def union_admin_token():
    login = _login("admin_union", "Admin@123", "general-union")
    if login.status_code != 200:
        pytest.skip(f"general-union admin login failed: {login.status_code}")
    body = login.json()
    token = body.get("token")
    if not token:
        pytest.skip("No token for union admin")
    return token


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_data():
    yield
    if not MONGO_URL or not DB_NAME:
        return
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    db.journal_entries.delete_many({"reference": {"$regex": r"^TEST-ITER22-"}})
    db.journal_entries.delete_many({"source_id": {"$regex": r"^industrial-development-2098-"}})
    db.banking_manual_charges.delete_many({"bank_id": "industrial-development", "year": 2098})
    db.login_attempts.delete_many({"username": "test_lock_iter22"})
    client.close()


class TestJournalEntriesFeature:
    def test_social_admin_has_journal_module_enabled(self):
        login = _login("admin_takaful", "Admin@123", "social-solidarity")
        assert login.status_code == 200
        user = login.json()["user"]
        assert user["organization_id"] == "social-solidarity"
        assert user["organization_modules"].get("journal_entries") is True

    def test_create_balanced_manual_journal_success(self, social_admin_token):
        ref = f"TEST-ITER22-MANUAL-{uuid.uuid4().hex[:8]}"
        response = _create_balanced_manual_journal(social_admin_token, ref, 125.5)
        assert response.status_code == 200, response.text
        data = response.json()
        assert isinstance(data.get("entry_number"), int)
        assert data["reference"] == ref
        assert data["source_type"] == "manual"
        assert data["status"] == "approved"
        assert data["total_debit"] == 125.5
        assert data["total_credit"] == 125.5

    def test_reject_unbalanced_manual_journal(self, social_admin_token):
        payload = {
            "entry_date": date.today().isoformat(),
            "description": "TEST ITER22 UNBALANCED",
            "reference": f"TEST-ITER22-UNBAL-{uuid.uuid4().hex[:6]}",
            "lines": [
                {"account_name": "المصروفات", "debit": 100, "credit": 0},
                {"account_name": "البنك", "debit": 0, "credit": 50},
            ],
        }
        response = requests.post(f"{BASE_URL}/api/journal-entries", json=payload, headers=_headers(social_admin_token), timeout=30)
        assert response.status_code == 400
        detail = response.json().get("detail", "")
        assert "غير متوازن" in detail

    def test_banking_expense_manual_save_generates_auto_journal(self, social_admin_token):
        month = (int(uuid.uuid4().int % 12) + 1)
        payload = {
            "bank_id": "industrial-development",
            "year": 2098,
            "month": month,
            "items": [
                {"statement": "TEST ITER22 BANK CHARGE", "count": 2, "amount": 37.5},
            ],
        }
        save_response = requests.put(
            f"{BASE_URL}/api/banking-expenses/manual",
            json=payload,
            headers=_headers(social_admin_token),
            timeout=30,
        )
        assert save_response.status_code == 200, save_response.text
        saved = save_response.json()
        assert saved["bank_id"] == "industrial-development"
        assert saved["items"][0]["total"] == 75.0

        source_id = f"industrial-development-2098-{month}"
        list_response = requests.get(
            f"{BASE_URL}/api/journal-entries",
            params={"source_type": "banking_expense"},
            headers=_headers(social_admin_token),
            timeout=30,
        )
        assert list_response.status_code == 200, list_response.text
        rows = list_response.json()
        target = next((entry for entry in rows if entry.get("source_id") == source_id), None)
        assert target is not None
        assert target["is_auto"] is True
        assert target["total_debit"] == 75.0
        assert target["total_credit"] == 75.0
        account_names = {line["account_name"] for line in target["lines"]}
        assert "المصروفات البنكية" in account_names
        assert "البنك" in account_names

    def test_journal_sequence_isolated_between_organizations(self, social_admin_token, union_admin_token):
        social_ref_1 = f"TEST-ITER22-SOC-{uuid.uuid4().hex[:6]}"
        social_ref_2 = f"TEST-ITER22-SOC-{uuid.uuid4().hex[:6]}"
        union_ref_1 = f"TEST-ITER22-UNI-{uuid.uuid4().hex[:6]}"
        union_ref_2 = f"TEST-ITER22-UNI-{uuid.uuid4().hex[:6]}"

        social_one = _create_balanced_manual_journal(social_admin_token, social_ref_1, 91.0)
        assert social_one.status_code == 200, social_one.text
        social_one_number = social_one.json()["entry_number"]

        union_one = _create_balanced_manual_journal(union_admin_token, union_ref_1, 82.0)
        assert union_one.status_code == 200, union_one.text
        union_one_number = union_one.json()["entry_number"]

        social_two = _create_balanced_manual_journal(social_admin_token, social_ref_2, 93.0)
        assert social_two.status_code == 200, social_two.text
        social_two_number = social_two.json()["entry_number"]

        union_two = _create_balanced_manual_journal(union_admin_token, union_ref_2, 84.0)
        assert union_two.status_code == 200, union_two.text
        union_two_number = union_two.json()["entry_number"]

        assert social_two_number == social_one_number + 1
        assert union_two_number == union_one_number + 1

    def test_disable_journal_module_for_social_and_restore(self, social_admin_token):
        current = requests.get(f"{BASE_URL}/api/admin/organization/modules", headers=_headers(social_admin_token), timeout=30)
        assert current.status_code == 200
        modules = current.json().get("modules", {})
        original_value = modules.get("journal_entries", True)

        try:
            edited_modules = {**modules, "journal_entries": False}
            update_response = requests.put(
                f"{BASE_URL}/api/admin/organization/modules",
                json={"modules": edited_modules},
                headers=_headers(social_admin_token),
                timeout=30,
            )
            assert update_response.status_code == 200, update_response.text
            assert update_response.json()["modules"]["journal_entries"] is False

            relogin = _login("admin_takaful", "Admin@123", "social-solidarity")
            assert relogin.status_code == 200
            assert relogin.json()["user"]["organization_modules"]["journal_entries"] is False
        finally:
            restore_modules = {**modules, "journal_entries": original_value}
            requests.put(
                f"{BASE_URL}/api/admin/organization/modules",
                json={"modules": restore_modules},
                headers=_headers(social_admin_token),
                timeout=30,
            )


class TestAuthPlaybookChecks:
    def test_login_sets_httponly_cookie(self):
        response = _login("admin_takaful", "Admin@123", "social-solidarity")
        assert response.status_code == 200
        set_cookie = response.headers.get("set-cookie", "")
        assert "access_token=" in set_cookie
        assert "HttpOnly" in set_cookie

    def test_cors_allows_credentials_with_explicit_origin(self):
        response = requests.options(
            f"{BASE_URL}/api/auth/login",
            headers={
                "Origin": BASE_URL,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,authorization",
            },
            timeout=30,
        )
        assert response.status_code in (200, 204)
        assert response.headers.get("access-control-allow-credentials", "").lower() == "true"
        assert response.headers.get("access-control-allow-origin", "") not in ("", "*")

    def test_bruteforce_lockout_after_five_failed_attempts(self):
        username = "test_lock_iter22"
        for _ in range(5):
            failed = _login(username, "WrongPass@123", "social-solidarity")
            assert failed.status_code == 401

        locked = _login(username, "WrongPass@123", "social-solidarity")
        assert locked.status_code in (423, 429)