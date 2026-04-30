"""Iteration 28: regression for admin fixed-asset rates, fixed-assets reports, custody/advances automation, org isolation, and auth safeguards."""

import os
import uuid

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient


# Modules/features under test: auth/org switch, fixed-asset admin rates + depreciation filters, custody/advance journal automation, chart sync
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


def _pick_bank_id(token: str):
    response = requests.get(f"{BASE_URL}/api/banks", headers=_headers(token), timeout=30)
    assert response.status_code == 200, response.text
    banks = response.json()
    assert len(banks) >= 1
    return banks[0]["id"]


def _asset_categories_admin(token: str):
    response = requests.get(f"{BASE_URL}/api/admin/fixed-assets/categories", headers=_headers(token), timeout=30)
    assert response.status_code == 200, response.text
    return {item["code"]: item for item in response.json()}


def _create_asset(token: str, category_code: str, purchase_cost: float, purchase_date: str):
    category = _asset_categories_admin(token)[category_code]
    payload = {
        "category_code": category_code,
        "asset_name": f"{category['name']}-IT28-{uuid.uuid4().hex[:6]}",
        "purchase_date": purchase_date,
        "purchase_cost": purchase_cost,
        "bank_id": _pick_bank_id(token),
        "invoice_number": f"TEST_IT28_FA_{uuid.uuid4().hex[:8]}",
        "notes": "TEST ITER28",
        "is_active": True,
    }
    response = requests.post(f"{BASE_URL}/api/fixed-assets", json=payload, headers=_headers(token), timeout=30)
    assert response.status_code == 200, response.text
    return response.json()


def _journal_entries(token: str, source_type: str, from_date: str, to_date: str):
    response = requests.get(
        f"{BASE_URL}/api/journal-entries",
        params={"source_type": source_type, "from_date": from_date, "to_date": to_date},
        headers=_headers(token),
        timeout=30,
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture(scope="session", autouse=True)
def require_base_url():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL is not configured")


@pytest.fixture(scope="session")
def social_admin_token():
    response = _login("admin_takaful", "Admin@123", "social-solidarity")
    if response.status_code != 200:
        pytest.skip(f"social-solidarity admin login failed: {response.status_code}")
    return response.json().get("token")


@pytest.fixture(scope="session")
def union_admin_token():
    response = _login("admin_union", "Admin@123", "general-union")
    if response.status_code != 200:
        pytest.skip(f"general-union admin login failed: {response.status_code}")
    return response.json().get("token")


class TestAuthPlaybookAndOrganizationSelection:
    def test_org_login_matrix_and_cookie(self):
        social_ok = _login("admin_takaful", "Admin@123", "social-solidarity")
        social_wrong = _login("admin_takaful", "Admin@123", "general-union")
        union_ok = _login("admin_union", "Admin@123", "general-union")
        union_wrong = _login("admin_union", "Admin@123", "social-solidarity")

        assert social_ok.status_code == 200
        assert union_ok.status_code == 200
        assert social_wrong.status_code == 401
        assert union_wrong.status_code == 401

        social_data = social_ok.json()
        assert social_data["user"]["organization_id"] == "social-solidarity"
        assert social_data["user"]["username"] in ["admin_takaful", "admin"]

        set_cookie = social_ok.headers.get("set-cookie", "")
        assert "access_token=" in set_cookie
        assert "HttpOnly" in set_cookie

    def test_bruteforce_lockout_after_five_failures(self):
        username = f"it28_lock_{uuid.uuid4().hex[:6]}"
        for _ in range(5):
            failed = _login(username, "WrongPass@123", "social-solidarity")
            assert failed.status_code == 401
        locked = _login(username, "WrongPass@123", "social-solidarity")
        assert locked.status_code in (423, 429)

    def test_cors_preflight_credentials_headers(self):
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
        assert response.headers.get("access-control-allow-origin") not in (None, "", "*")

    def test_admin_hash_bcrypt_2b_format(self):
        if not MONGO_URL or not DB_NAME:
            pytest.skip("Mongo connection config missing")
        client = MongoClient(MONGO_URL)
        db = client[DB_NAME]
        user = db.users.find_one({"username": "admin_takaful", "organization_id": "social-solidarity"}, {"_id": 0, "password_hash": 1})
        client.close()
        assert user is not None
        assert (user.get("password_hash") or "").startswith("$2b$")


class TestFixedAssetsRatesAndReports:
    def test_rate_update_affects_new_assets_only_and_keeps_old_data(self, social_admin_token):
        code = "5"
        categories_before = _asset_categories_admin(social_admin_token)
        original_rate = float(categories_before[code]["annual_depreciation_rate"])
        new_rate = 12.0 if original_rate != 12.0 else 13.0

        old_asset = _create_asset(social_admin_token, category_code=code, purchase_cost=12000, purchase_date="2108-01-01")
        assert float(old_asset["annual_depreciation_rate"]) == original_rate

        try:
            update = requests.put(
                f"{BASE_URL}/api/admin/fixed-assets/categories/{code}",
                json={"annual_depreciation_rate": new_rate},
                headers=_headers(social_admin_token),
                timeout=30,
            )
            assert update.status_code == 200, update.text
            assert float(update.json()["annual_depreciation_rate"]) == new_rate

            new_asset = _create_asset(social_admin_token, category_code=code, purchase_cost=12000, purchase_date="2108-01-02")
            assert float(new_asset["annual_depreciation_rate"]) == new_rate
            assert float(new_asset["monthly_depreciation"]) == pytest.approx(round(12000 * new_rate / 100 / 12, 2), abs=0.01)
            assert float(old_asset["annual_depreciation_rate"]) == original_rate

            delete_new = requests.delete(f"{BASE_URL}/api/fixed-assets/{new_asset['id']}", headers=_headers(social_admin_token), timeout=30)
            assert delete_new.status_code == 200, delete_new.text
        finally:
            restore = requests.put(
                f"{BASE_URL}/api/admin/fixed-assets/categories/{code}",
                json={"annual_depreciation_rate": original_rate},
                headers=_headers(social_admin_token),
                timeout=30,
            )
            assert restore.status_code == 200, restore.text

            delete_old = requests.delete(f"{BASE_URL}/api/fixed-assets/{old_asset['id']}", headers=_headers(social_admin_token), timeout=30)
            assert delete_old.status_code == 200, delete_old.text

    def test_rate_isolation_between_organizations(self, social_admin_token, union_admin_token):
        code = "101"
        social_categories = _asset_categories_admin(social_admin_token)
        union_categories_before = _asset_categories_admin(union_admin_token)
        social_original = float(social_categories[code]["annual_depreciation_rate"])
        union_original = float(union_categories_before[code]["annual_depreciation_rate"])
        social_new = 17.0 if social_original != 17.0 else 18.0

        try:
            update_social = requests.put(
                f"{BASE_URL}/api/admin/fixed-assets/categories/{code}",
                json={"annual_depreciation_rate": social_new},
                headers=_headers(social_admin_token),
                timeout=30,
            )
            assert update_social.status_code == 200, update_social.text

            union_categories_after = _asset_categories_admin(union_admin_token)
            assert float(union_categories_after[code]["annual_depreciation_rate"]) == union_original
        finally:
            restore_social = requests.put(
                f"{BASE_URL}/api/admin/fixed-assets/categories/{code}",
                json={"annual_depreciation_rate": social_original},
                headers=_headers(social_admin_token),
                timeout=30,
            )
            assert restore_social.status_code == 200, restore_social.text

    def test_depreciation_report_supports_yearly_and_monthly_filters(self, social_admin_token):
        asset = _create_asset(social_admin_token, category_code="155", purchase_cost=6000, purchase_date="2109-01-01")
        run = requests.post(
            f"{BASE_URL}/api/fixed-assets/depreciation/run",
            json={"year": 2109, "month": 3},
            headers=_headers(social_admin_token),
            timeout=40,
        )
        assert run.status_code == 200, run.text

        yearly = requests.get(
            f"{BASE_URL}/api/fixed-assets/depreciations",
            params={"year": 2109},
            headers=_headers(social_admin_token),
            timeout=30,
        )
        monthly = requests.get(
            f"{BASE_URL}/api/fixed-assets/depreciations",
            params={"year": 2109, "month": 3},
            headers=_headers(social_admin_token),
            timeout=30,
        )
        assert yearly.status_code == 200, yearly.text
        assert monthly.status_code == 200, monthly.text

        yearly_rows = yearly.json()
        monthly_rows = monthly.json()
        assert any(row["asset_id"] == asset["id"] for row in yearly_rows)
        assert any(row["asset_id"] == asset["id"] and int(row["month"]) == 3 for row in monthly_rows)

        delete_asset = requests.delete(f"{BASE_URL}/api/fixed-assets/{asset['id']}", headers=_headers(social_admin_token), timeout=30)
        assert delete_asset.status_code == 200, delete_asset.text


class TestCustodyAdvancesAutomation:
    def test_custody_create_settle_delete_and_journals_balanced(self, social_admin_token):
        payload = {
            "transaction_type": "custody",
            "recipient_name": f"IT28 Recipient {uuid.uuid4().hex[:5]}",
            "issue_date": "2110-01-05",
            "amount": 1500,
            "bank_id": _pick_bank_id(social_admin_token),
            "purpose": "IT28 custody automation test",
            "due_date": None,
            "notes": "IT28",
        }
        create_response = requests.post(f"{BASE_URL}/api/custody-advances", json=payload, headers=_headers(social_admin_token), timeout=30)
        assert create_response.status_code == 200, create_response.text
        created = create_response.json()
        assert created["status"] == "open"
        assert float(created["remaining_amount"]) == 1500

        issue_entries = _journal_entries(social_admin_token, "custody_advance", "2110-01-01", "2110-01-31")
        issue_entry = next((item for item in issue_entries if item.get("source_id") == created["id"]), None)
        assert issue_entry is not None
        assert float(issue_entry["total_debit"]) == 1500
        assert float(issue_entry["total_credit"]) == 1500

        settle_response = requests.post(
            f"{BASE_URL}/api/custody-advances/{created['id']}/settle",
            json={"settlement_date": "2110-01-10", "settlement_amount": 1000, "settlement_type": "expense", "notes": "IT28 settlement"},
            headers=_headers(social_admin_token),
            timeout=30,
        )
        assert settle_response.status_code == 200, settle_response.text
        settled = settle_response.json()
        assert settled["status"] == "partial"
        assert float(settled["settled_amount"]) == 1000
        assert float(settled["remaining_amount"]) == 500

        settlement_entries = _journal_entries(social_admin_token, "custody_advance_settlement", "2110-01-01", "2110-01-31")
        settlement_entry = next((item for item in settlement_entries if item.get("source_id") == created["id"]), None)
        assert settlement_entry is not None
        assert float(settlement_entry["total_debit"]) == 1000
        assert float(settlement_entry["total_credit"]) == 1000

        delete_response = requests.delete(f"{BASE_URL}/api/custody-advances/{created['id']}", headers=_headers(social_admin_token), timeout=30)
        assert delete_response.status_code == 200, delete_response.text

        list_after_delete = requests.get(f"{BASE_URL}/api/custody-advances", headers=_headers(social_admin_token), timeout=30)
        assert list_after_delete.status_code == 200
        assert all(item["id"] != created["id"] for item in list_after_delete.json())

        issue_after = _journal_entries(social_admin_token, "custody_advance", "2110-01-01", "2110-01-31")
        settlement_after = _journal_entries(social_admin_token, "custody_advance_settlement", "2110-01-01", "2110-01-31")
        assert all(item.get("source_id") != created["id"] for item in issue_after)
        assert all(item.get("source_id") != created["id"] for item in settlement_after)

    def test_chart_accounts_include_custody_and_settlement_accounts_after_sync(self, social_admin_token):
        sync = requests.post(f"{BASE_URL}/api/chart-accounts/sync", headers=_headers(social_admin_token), timeout=30)
        assert sync.status_code == 200, sync.text

        listing = requests.get(f"{BASE_URL}/api/chart-accounts", headers=_headers(social_admin_token), timeout=30)
        assert listing.status_code == 200, listing.text
        rows = listing.json()

        custody = next((item for item in rows if item.get("system_key") == "custody_advances"), None)
        settlement = next((item for item in rows if item.get("system_key") == "custody_advance_expense"), None)
        assert custody is not None
        assert settlement is not None

    def test_custody_organization_isolation(self, social_admin_token, union_admin_token):
        payload = {
            "transaction_type": "advance",
            "recipient_name": f"IT28 Isolation {uuid.uuid4().hex[:5]}",
            "issue_date": "2111-02-01",
            "amount": 900,
            "bank_id": _pick_bank_id(social_admin_token),
            "purpose": "isolation check",
            "due_date": None,
            "notes": "IT28",
        }
        created = requests.post(f"{BASE_URL}/api/custody-advances", json=payload, headers=_headers(social_admin_token), timeout=30)
        assert created.status_code == 200, created.text
        document_id = created.json()["id"]

        union_list = requests.get(f"{BASE_URL}/api/custody-advances", headers=_headers(union_admin_token), timeout=30)
        assert union_list.status_code == 200, union_list.text
        assert all(item["id"] != document_id for item in union_list.json())

        union_delete = requests.delete(f"{BASE_URL}/api/custody-advances/{document_id}", headers=_headers(union_admin_token), timeout=30)
        assert union_delete.status_code == 404

        social_delete = requests.delete(f"{BASE_URL}/api/custody-advances/{document_id}", headers=_headers(social_admin_token), timeout=30)
        assert social_delete.status_code == 200
