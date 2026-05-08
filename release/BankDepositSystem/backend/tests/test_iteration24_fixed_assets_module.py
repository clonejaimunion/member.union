"""Iteration 24: fixed assets end-to-end API coverage + auth hardening checks."""

import os
import uuid

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient


# Modules/features under test: fixed assets categories/create/depreciation/delete, auto journals, org isolation, module toggle, auth guards
ENV_BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
FILE_BASE_URL = dotenv_values("/app/frontend/.env").get("REACT_APP_BACKEND_URL")
BASE_URL = (ENV_BASE_URL or FILE_BASE_URL or "").rstrip("/")

MONGO_URL = dotenv_values("/app/backend/.env").get("MONGO_URL", "").strip('"')
DB_NAME = dotenv_values("/app/backend/.env").get("DB_NAME", "").strip('"')

TEST_INVOICE_PREFIX = "TEST_ITER24_FA_"


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


def _category_map(token: str):
    response = requests.get(f"{BASE_URL}/api/fixed-assets/categories", headers=_headers(token), timeout=30)
    assert response.status_code == 200, response.text
    return {item["code"]: item for item in response.json()}


def _create_asset(token: str, category_code: str, purchase_cost: float, purchase_date: str):
    categories = _category_map(token)
    category = categories[category_code]
    bank_id = _pick_bank_id(token)
    payload = {
        "category_code": category_code,
        "asset_name": f"{category['items'][0]} - {uuid.uuid4().hex[:6]}",
        "purchase_date": purchase_date,
        "purchase_cost": purchase_cost,
        "bank_id": bank_id,
        "invoice_number": f"{TEST_INVOICE_PREFIX}{uuid.uuid4().hex[:8]}",
        "notes": "TEST ITER24",
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
    login = _login("admin_takaful", "Admin@123", "social-solidarity")
    if login.status_code != 200:
        pytest.skip(f"social-solidarity admin login failed: {login.status_code}")
    token = login.json().get("token")
    if not token:
        pytest.skip("No token for social admin")
    return token


@pytest.fixture(scope="session")
def union_admin_token():
    login = _login("admin_union", "Admin@123", "general-union")
    if login.status_code != 200:
        pytest.skip(f"general-union admin login failed: {login.status_code}")
    token = login.json().get("token")
    if not token:
        pytest.skip("No token for union admin")
    return token


@pytest.fixture(scope="session", autouse=True)
def cleanup_iter24_test_data():
    yield
    if not MONGO_URL or not DB_NAME:
        return
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    assets = list(db.fixed_assets.find({"invoice_number": {"$regex": f"^{TEST_INVOICE_PREFIX}"}}, {"_id": 0, "id": 1}))
    asset_ids = [item["id"] for item in assets]
    depreciation_ids = [item["id"] for item in db.fixed_asset_depreciations.find({"asset_id": {"$in": asset_ids}}, {"_id": 0, "id": 1})]

    if asset_ids:
        db.fixed_assets.delete_many({"id": {"$in": asset_ids}})
        db.fixed_asset_depreciations.delete_many({"asset_id": {"$in": asset_ids}})
        db.journal_entries.delete_many({"source_type": "fixed_asset", "source_id": {"$in": asset_ids}})
    if depreciation_ids:
        db.journal_entries.delete_many({"source_type": "asset_depreciation", "source_id": {"$in": depreciation_ids}})

    db.login_attempts.delete_many({"username": {"$regex": r"^iter24_lock_"}})
    client.close()


class TestFixedAssetsCoreFlows:
    def test_fixed_asset_categories_have_required_codes_rates_and_items(self, social_admin_token):
        categories = _category_map(social_admin_token)

        assert set(["5", "101", "151", "155"]).issubset(set(categories.keys()))
        assert categories["5"]["annual_depreciation_rate"] == 10.0
        assert categories["101"]["annual_depreciation_rate"] == 20.0
        assert categories["151"]["annual_depreciation_rate"] == 5.0
        assert categories["155"]["annual_depreciation_rate"] == 20.0
        assert "موكيت ارضية" in categories["5"]["items"]
        assert "عدد 4 جهاز حاسب الي" in categories["101"]["items"]
        assert "خزينة حديد اوجيدا 44سم" in categories["151"]["items"]
        assert "جهاز تكييف توشيبا 4حصان" in categories["155"]["items"]

    def test_create_asset_stores_org_and_creates_balanced_purchase_journal(self, social_admin_token):
        asset = _create_asset(
            social_admin_token,
            category_code="5",
            purchase_cost=12000,
            purchase_date="2101-01-10",
        )

        assert asset["organization_id"] == "social-solidarity"
        assert asset["category_code"] == "5"
        assert asset["annual_depreciation_rate"] == 10.0
        assert asset["monthly_depreciation"] == 100.0

        journal_entries = _journal_entries(social_admin_token, "fixed_asset", "2101-01-01", "2101-01-31")
        purchase_entry = next((item for item in journal_entries if item.get("source_id") == asset["id"]), None)
        assert purchase_entry is not None
        assert purchase_entry["total_debit"] == 12000
        assert purchase_entry["total_credit"] == 12000

    def test_organization_isolation_between_union_and_social_solidarity(self, social_admin_token, union_admin_token):
        union_asset = _create_asset(
            union_admin_token,
            category_code="101",
            purchase_cost=6000,
            purchase_date="2101-02-01",
        )

        social_assets_response = requests.get(f"{BASE_URL}/api/fixed-assets", headers=_headers(social_admin_token), timeout=30)
        assert social_assets_response.status_code == 200, social_assets_response.text
        social_asset_ids = {item["id"] for item in social_assets_response.json()}
        assert union_asset["id"] not in social_asset_ids

        cross_delete = requests.delete(
            f"{BASE_URL}/api/fixed-assets/{union_asset['id']}",
            headers=_headers(social_admin_token),
            timeout=30,
        )
        assert cross_delete.status_code == 404

    def test_run_monthly_depreciation_uses_rate_divided_by_12_and_creates_journal(self, social_admin_token):
        asset = _create_asset(
            social_admin_token,
            category_code="5",
            purchase_cost=12000,
            purchase_date="2102-01-01",
        )

        run_response = requests.post(
            f"{BASE_URL}/api/fixed-assets/depreciation/run",
            json={"year": 2102, "month": 4},
            headers=_headers(social_admin_token),
            timeout=40,
        )
        assert run_response.status_code == 200, run_response.text
        records = run_response.json()

        depreciation_record = next((item for item in records if item.get("asset_id") == asset["id"]), None)
        assert depreciation_record is not None
        assert depreciation_record["amount"] == 100.0
        assert depreciation_record["amount"] <= asset["purchase_cost"]

        dep_entries = _journal_entries(social_admin_token, "asset_depreciation", "2102-04-01", "2102-04-30")
        dep_journal = next((item for item in dep_entries if item.get("source_id") == depreciation_record["id"]), None)
        assert dep_journal is not None
        assert dep_journal["total_debit"] == 100.0
        assert dep_journal["total_credit"] == 100.0

    def test_chart_of_accounts_contains_fixed_assets_and_depreciation_accounts(self, social_admin_token):
        response = requests.get(f"{BASE_URL}/api/chart-accounts", headers=_headers(social_admin_token), timeout=30)
        assert response.status_code == 200, response.text
        by_code = {item["code"]: item for item in response.json()}

        assert "1400" in by_code
        assert "1490" in by_code
        assert "5200" in by_code
        for code in ["5", "101", "151", "155"]:
            assert code in by_code
            assert f"{code}-م" in by_code
            assert f"52{code}" in by_code

    def test_trial_balance_reflects_fixed_asset_and_depreciation_entries(self, social_admin_token):
        asset = _create_asset(
            social_admin_token,
            category_code="155",
            purchase_cost=6000,
            purchase_date="2111-02-01",
        )

        run_response = requests.post(
            f"{BASE_URL}/api/fixed-assets/depreciation/run",
            json={"year": 2111, "month": 2},
            headers=_headers(social_admin_token),
            timeout=40,
        )
        assert run_response.status_code == 200, run_response.text
        depreciation_record = next((item for item in run_response.json() if item.get("asset_id") == asset["id"]), None)
        assert depreciation_record is not None

        trial_response = requests.get(
            f"{BASE_URL}/api/trial-balance",
            params={"from_date": "2111-02-01", "to_date": "2111-02-28", "non_zero_only": "true"},
            headers=_headers(social_admin_token),
            timeout=30,
        )
        assert trial_response.status_code == 200, trial_response.text
        report = trial_response.json()
        rows = report.get("rows", [])

        asset_row = next((row for row in rows if row.get("account_code") == "155"), None)
        depreciation_expense_row = next((row for row in rows if row.get("account_code") == "52155"), None)
        accumulated_dep_row = next((row for row in rows if row.get("account_code") == "155-م"), None)

        assert asset_row is not None
        assert depreciation_expense_row is not None
        assert accumulated_dep_row is not None
        assert float(asset_row.get("total_debit") or 0) >= 6000
        assert float(depreciation_expense_row.get("total_debit") or 0) >= depreciation_record["amount"]
        assert float(accumulated_dep_row.get("total_credit") or 0) >= depreciation_record["amount"]

    def test_delete_asset_removes_depreciations_and_auto_journals(self, social_admin_token):
        asset = _create_asset(
            social_admin_token,
            category_code="101",
            purchase_cost=2400,
            purchase_date="2112-03-01",
        )

        run_response = requests.post(
            f"{BASE_URL}/api/fixed-assets/depreciation/run",
            json={"year": 2112, "month": 3},
            headers=_headers(social_admin_token),
            timeout=40,
        )
        assert run_response.status_code == 200, run_response.text
        depreciation_record = next((item for item in run_response.json() if item.get("asset_id") == asset["id"]), None)
        assert depreciation_record is not None

        delete_response = requests.delete(
            f"{BASE_URL}/api/fixed-assets/{asset['id']}",
            headers=_headers(social_admin_token),
            timeout=30,
        )
        assert delete_response.status_code == 200, delete_response.text

        assets_response = requests.get(f"{BASE_URL}/api/fixed-assets", headers=_headers(social_admin_token), timeout=30)
        assert assets_response.status_code == 200
        assert all(item["id"] != asset["id"] for item in assets_response.json())

        dep_list_response = requests.get(
            f"{BASE_URL}/api/fixed-assets/depreciations",
            params={"year": 2112, "month": 3},
            headers=_headers(social_admin_token),
            timeout=30,
        )
        assert dep_list_response.status_code == 200
        assert all(item.get("asset_id") != asset["id"] for item in dep_list_response.json())

        fixed_entries = _journal_entries(social_admin_token, "fixed_asset", "2112-03-01", "2112-03-31")
        dep_entries = _journal_entries(social_admin_token, "asset_depreciation", "2112-03-01", "2112-03-31")
        assert all(item.get("source_id") != asset["id"] for item in fixed_entries)
        assert all(item.get("source_id") != depreciation_record["id"] for item in dep_entries)

    def test_toggle_fixed_assets_module_and_restore(self, social_admin_token):
        current = requests.get(f"{BASE_URL}/api/admin/organization/modules", headers=_headers(social_admin_token), timeout=30)
        assert current.status_code == 200, current.text
        modules = current.json().get("modules", {})
        original_value = modules.get("fixed_assets", True)

        try:
            disabled_modules = {**modules, "fixed_assets": False}
            update = requests.put(
                f"{BASE_URL}/api/admin/organization/modules",
                json={"modules": disabled_modules},
                headers=_headers(social_admin_token),
                timeout=30,
            )
            assert update.status_code == 200, update.text
            assert update.json()["modules"]["fixed_assets"] is False

            relogin = _login("admin_takaful", "Admin@123", "social-solidarity")
            assert relogin.status_code == 200
            assert relogin.json()["user"]["organization_modules"]["fixed_assets"] is False
        finally:
            restore_modules = {**modules, "fixed_assets": original_value}
            requests.put(
                f"{BASE_URL}/api/admin/organization/modules",
                json={"modules": restore_modules},
                headers=_headers(social_admin_token),
                timeout=30,
            )


class TestAuthPlaybookChecks:
    def test_login_sets_httponly_cookie(self):
        response = _login("admin_takaful", "Admin@123", "social-solidarity")
        assert response.status_code == 200, response.text
        set_cookie = response.headers.get("set-cookie", "")
        assert "access_token=" in set_cookie
        assert "HttpOnly" in set_cookie

    def test_bruteforce_lockout_after_five_failed_attempts(self):
        username = f"iter24_lock_{uuid.uuid4().hex[:6]}"
        for _ in range(5):
            failed = _login(username, "WrongPass@123", "social-solidarity")
            assert failed.status_code == 401

        locked = _login(username, "WrongPass@123", "social-solidarity")
        assert locked.status_code in (423, 429)

    def test_cors_preflight_credentials_headers_are_explicit(self):
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
        assert response.headers.get("access-control-allow-credentials") == "true"
        assert response.headers.get("access-control-allow-origin") not in (None, "", "*")

    def test_admin_hash_is_bcrypt_2b_format(self):
        if not MONGO_URL or not DB_NAME:
            pytest.skip("Mongo connection config missing")
        client = MongoClient(MONGO_URL)
        db = client[DB_NAME]
        user = db.users.find_one(
            {"username": "admin_takaful", "organization_id": "social-solidarity"},
            {"_id": 0, "password_hash": 1},
        )
        client.close()
        assert user is not None
        password_hash = user.get("password_hash", "")
        assert password_hash.startswith("$2b$")