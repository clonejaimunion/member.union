"""Iteration 23: Trial balance + module toggle + critical auth guard checks."""

import os
import uuid
from datetime import date

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient


# Modules/features under test: trial balance aggregation, banking-expense auto journal, module toggle, auth guardrails
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


@pytest.fixture(scope="session", autouse=True)
def require_base_url():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL is not configured")


@pytest.fixture(scope="session")
def social_admin_token():
    login = _login("admin_takaful", "Admin@123", "social-solidarity")
    if login.status_code != 200:
        pytest.skip(f"social-solidarity admin login failed: {login.status_code}")
    token = login.json().get("token")
    if not token:
        pytest.skip("No token for social admin")
    return token


@pytest.fixture(scope="session")
def trial_period():
    month = int(uuid.uuid4().int % 12) + 1
    return {"year": 2100, "month": month}


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_data():
    yield
    if not MONGO_URL or not DB_NAME:
        return
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    db.journal_entries.delete_many({"source_type": "banking_expense", "source_id": {"$regex": r"^industrial-development-2100-"}})
    db.banking_manual_charges.delete_many({"bank_id": "industrial-development", "year": 2100})
    db.login_attempts.delete_many({"username": {"$regex": r"^iter23_lock_"}})
    client.close()


class TestTrialBalanceFeature:
    def test_trial_balance_from_banking_expense_is_balanced(self, social_admin_token, trial_period):
        statement_tag = f"TEST ITER23 TB {uuid.uuid4().hex[:6]}"
        amount = 52.5
        count = 2
        total = round(amount * count, 2)
        payload = {
            "bank_id": "industrial-development",
            "year": trial_period["year"],
            "month": trial_period["month"],
            "items": [{"statement": statement_tag, "count": count, "amount": amount}],
        }

        save_response = requests.put(
            f"{BASE_URL}/api/banking-expenses/manual",
            json=payload,
            headers=_headers(social_admin_token),
            timeout=30,
        )
        assert save_response.status_code == 200, save_response.text
        saved = save_response.json()
        assert saved["year"] == trial_period["year"]
        assert saved["month"] == trial_period["month"]
        assert saved["items"][0]["total"] == total

        from_date = date(trial_period["year"], trial_period["month"], 1).isoformat()
        to_date = date(trial_period["year"], trial_period["month"], 28).isoformat()
        trial_response = requests.get(
            f"{BASE_URL}/api/trial-balance",
            params={"from_date": from_date, "to_date": to_date, "non_zero_only": "true"},
            headers=_headers(social_admin_token),
            timeout=30,
        )
        assert trial_response.status_code == 200, trial_response.text
        report = trial_response.json()

        assert report["total_debit"] == total
        assert report["total_credit"] == total
        assert report["is_balanced"] is True

        rows = report.get("rows", [])
        expense_row = next((row for row in rows if row.get("account_name") == "المصروفات البنكية"), None)
        bank_row = next(
            (
                row
                for row in rows
                if float(row.get("total_credit") or 0) == total and float(row.get("total_debit") or 0) == 0
            ),
            None,
        )
        assert expense_row is not None
        assert expense_row["total_debit"] == total
        assert expense_row["total_credit"] == 0
        assert bank_row is not None
        assert bank_row["total_credit"] == total
        assert bank_row["total_debit"] == 0

    def test_trial_balance_account_type_filter_expense_can_be_unbalanced(self, social_admin_token, trial_period):
        from_date = date(trial_period["year"], trial_period["month"], 1).isoformat()
        to_date = date(trial_period["year"], trial_period["month"], 28).isoformat()

        response = requests.get(
            f"{BASE_URL}/api/trial-balance",
            params={
                "from_date": from_date,
                "to_date": to_date,
                "account_type": "expense",
                "non_zero_only": "true",
            },
            headers=_headers(social_admin_token),
            timeout=30,
        )
        assert response.status_code == 200, response.text
        data = response.json()

        rows = data.get("rows", [])
        assert len(rows) >= 1
        observed_types = sorted({str(row.get("account_type")) for row in rows})
        assert all(row.get("account_type") == "expense" for row in rows), f"Observed account types with expense filter: {observed_types}"
        assert data["total_debit"] > 0
        assert data["total_credit"] == 0
        assert data["is_balanced"] is False

    def test_trial_balance_non_zero_only_returns_movement_rows(self, social_admin_token, trial_period):
        from_date = date(trial_period["year"], trial_period["month"], 1).isoformat()
        to_date = date(trial_period["year"], trial_period["month"], 28).isoformat()

        response = requests.get(
            f"{BASE_URL}/api/trial-balance",
            params={"from_date": from_date, "to_date": to_date, "non_zero_only": "true"},
            headers=_headers(social_admin_token),
            timeout=30,
        )
        assert response.status_code == 200
        rows = response.json().get("rows", [])
        assert len(rows) >= 2
        for row in rows:
            assert any(
                [
                    row.get("opening_balance", 0),
                    row.get("total_debit", 0),
                    row.get("total_credit", 0),
                    row.get("balance_debit", 0),
                    row.get("balance_credit", 0),
                ]
            )

    def test_disable_trial_balance_module_and_restore(self, social_admin_token):
        current = requests.get(f"{BASE_URL}/api/admin/organization/modules", headers=_headers(social_admin_token), timeout=30)
        assert current.status_code == 200, current.text
        modules = current.json().get("modules", {})
        original_value = modules.get("trial_balance", True)

        try:
            edited_modules = {**modules, "trial_balance": False}
            update_response = requests.put(
                f"{BASE_URL}/api/admin/organization/modules",
                json={"modules": edited_modules},
                headers=_headers(social_admin_token),
                timeout=30,
            )
            assert update_response.status_code == 200, update_response.text
            assert update_response.json()["modules"]["trial_balance"] is False

            relogin = _login("admin_takaful", "Admin@123", "social-solidarity")
            assert relogin.status_code == 200
            assert relogin.json()["user"]["organization_modules"]["trial_balance"] is False
        finally:
            restore_modules = {**modules, "trial_balance": original_value}
            requests.put(
                f"{BASE_URL}/api/admin/organization/modules",
                json={"modules": restore_modules},
                headers=_headers(social_admin_token),
                timeout=30,
            )


class TestAuthGuardChecks:
    def test_login_sets_httponly_cookie(self):
        response = _login("admin_takaful", "Admin@123", "social-solidarity")
        assert response.status_code == 200
        set_cookie = response.headers.get("set-cookie", "")
        assert "access_token=" in set_cookie
        assert "HttpOnly" in set_cookie

    def test_bruteforce_lockout_after_five_failed_attempts(self):
        username = f"iter23_lock_{uuid.uuid4().hex[:6]}"
        for _ in range(5):
            failed = _login(username, "WrongPass@123", "social-solidarity")
            assert failed.status_code == 401

        locked = _login(username, "WrongPass@123", "social-solidarity")
        assert locked.status_code in (423, 429)

    def test_admin_hash_is_bcrypt_2b_format(self):
        if not MONGO_URL or not DB_NAME:
            pytest.skip("Mongo connection config missing")
        client = MongoClient(MONGO_URL)
        db = client[DB_NAME]
        user = db.users.find_one({"username": "admin_takaful", "organization_id": "social-solidarity"}, {"_id": 0, "password_hash": 1})
        client.close()
        assert user is not None
        password_hash = user.get("password_hash", "")
        assert password_hash.startswith("$2b$")
