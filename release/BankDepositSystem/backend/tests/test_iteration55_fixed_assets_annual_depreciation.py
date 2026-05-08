"""Iteration 55: annual fixed-asset depreciation automation, idempotency, monthly reversal, and setup EXE validation."""

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient


# Modules/features under test: fixed-assets annual depreciation run, financial-statements auto-run, idempotency, monthly->annual migration, setup download
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or dotenv_values("/app/frontend/.env").get("REACT_APP_BACKEND_URL") or "").rstrip("/")
MONGO_URL = (dotenv_values("/app/backend/.env").get("MONGO_URL") or "").strip('"')
DB_NAME = (dotenv_values("/app/backend/.env").get("DB_NAME") or "").strip('"')

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Admin@123"
ORG_ID = "general-union"
BANK_ID = "industrial-development"
TEST_PREFIX = "TEST_ITER55"


def _headers(token: str | None = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _login(username: str, password: str, organization_id: str = ORG_ID):
    return requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": username, "password": password, "organization_id": organization_id},
        headers=_headers(),
        timeout=40,
    )


def _create_test_asset(token: str, suffix: str = "A", purchase_date: str = "2026-01-01") -> dict:
    payload = {
        "category_code": "151",
        "asset_name": f"{TEST_PREFIX}_خزائن_{suffix}",
        "purchase_date": purchase_date,
        "purchase_cost": 490,
        "bank_id": BANK_ID,
        "invoice_number": f"{TEST_PREFIX}-{uuid.uuid4().hex[:8]}",
        "notes": TEST_PREFIX,
        "is_active": True,
    }
    response = requests.post(f"{BASE_URL}/api/fixed-assets", json=payload, headers=_headers(token), timeout=40)
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture(scope="session", autouse=True)
def require_base_url():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL is not configured")


@pytest.fixture(scope="session")
def admin_token():
    login = _login(ADMIN_USERNAME, ADMIN_PASSWORD, ORG_ID)
    if login.status_code != 200:
        pytest.skip(f"Admin login failed: {login.status_code}")
    token = login.json().get("token")
    if not token:
        pytest.skip("No token returned for admin login")
    return token


@pytest.fixture(scope="session")
def mongo_db():
    if not MONGO_URL or not DB_NAME:
        pytest.skip("Mongo env not available")
    client = MongoClient(MONGO_URL)
    try:
        yield client[DB_NAME]
    finally:
        client.close()


@pytest.fixture(autouse=True)
def cleanup_iter55_records(mongo_db):
    yield
    assets = list(mongo_db.fixed_assets.find({"organization_id": ORG_ID, "asset_name": {"$regex": f"^{TEST_PREFIX}"}}, {"_id": 0, "id": 1}))
    asset_ids = [item["id"] for item in assets]
    dep_ids = []
    if asset_ids:
        dep_ids = [item["id"] for item in mongo_db.fixed_asset_depreciations.find({"organization_id": ORG_ID, "asset_id": {"$in": asset_ids}}, {"_id": 0, "id": 1})]
    mongo_db.journal_entries.delete_many(
        {
            "organization_id": ORG_ID,
            "$or": [
                {"description": {"$regex": TEST_PREFIX}},
                {"reference": {"$regex": TEST_PREFIX}},
                {"source_id": {"$in": asset_ids + dep_ids}},
            ],
        }
    )
    if asset_ids:
        mongo_db.fixed_asset_depreciations.delete_many({"organization_id": ORG_ID, "asset_id": {"$in": asset_ids}})
        mongo_db.fixed_assets.delete_many({"organization_id": ORG_ID, "id": {"$in": asset_ids}})


def test_fixed_asset_490_run_2026_creates_annual_depreciation_and_journal(admin_token, mongo_db):
    asset = _create_test_asset(admin_token, suffix="RUN")
    assert float(asset["annual_depreciation_rate"]) == pytest.approx(5.0)

    run_response = requests.post(
        f"{BASE_URL}/api/fixed-assets/depreciation/run",
        json={"year": 2026, "month": 12},
        headers=_headers(admin_token),
        timeout=40,
    )
    assert run_response.status_code == 200, run_response.text
    records = run_response.json()
    own_record = next((item for item in records if item.get("asset_id") == asset["id"]), None)
    assert own_record is not None
    assert own_record["year"] == 2026
    assert own_record["id"] == f"{asset['id']}-2026-annual"
    assert float(own_record["amount"]) == pytest.approx(24.5)
    assert float(own_record["accumulated_after"]) == pytest.approx(24.5)
    assert float(own_record["net_book_value_after"]) == pytest.approx(465.5)

    assets_response = requests.get(f"{BASE_URL}/api/fixed-assets", headers=_headers(admin_token), timeout=40)
    assert assets_response.status_code == 200, assets_response.text
    refreshed = next((item for item in assets_response.json() if item.get("id") == asset["id"]), None)
    assert refreshed is not None
    assert float(refreshed["accumulated_depreciation"]) == pytest.approx(24.5)
    assert float(refreshed["net_book_value"]) == pytest.approx(465.5)

    journal = mongo_db.journal_entries.find_one(
        {
            "organization_id": ORG_ID,
            "source_type": "asset_depreciation",
            "source_id": own_record["id"],
            "is_reversal": {"$ne": True},
        },
        {"_id": 0},
    )
    assert journal is not None
    debit_line = next((line for line in journal.get("lines", []) if line.get("account_name") == "إهلاك الخزائن"), None)
    credit_line = next((line for line in journal.get("lines", []) if line.get("account_name") == "مجمع إهلاك الخزائن"), None)
    assert debit_line is not None
    assert credit_line is not None
    assert float(debit_line.get("debit") or 0) == pytest.approx(24.5)
    assert float(credit_line.get("credit") or 0) == pytest.approx(24.5)


def test_annual_depreciation_run_is_idempotent_for_same_asset_and_year(admin_token, mongo_db):
    asset = _create_test_asset(admin_token, suffix="IDEMP")

    first = requests.post(
        f"{BASE_URL}/api/fixed-assets/depreciation/run",
        json={"year": 2026, "month": 12},
        headers=_headers(admin_token),
        timeout=40,
    )
    assert first.status_code == 200, first.text

    second = requests.post(
        f"{BASE_URL}/api/fixed-assets/depreciation/run",
        json={"year": 2026, "month": 12},
        headers=_headers(admin_token),
        timeout=40,
    )
    assert second.status_code == 200, second.text

    first_record = next((item for item in first.json() if item.get("asset_id") == asset["id"]), None)
    second_record = next((item for item in second.json() if item.get("asset_id") == asset["id"]), None)
    assert first_record is not None
    assert second_record is not None
    assert first_record["id"] == second_record["id"]

    yearly_records = list(
        mongo_db.fixed_asset_depreciations.find(
            {"organization_id": ORG_ID, "asset_id": asset["id"], "year": 2026},
            {"_id": 0, "id": 1},
        )
    )
    assert len(yearly_records) == 1

    active_journals = list(
        mongo_db.journal_entries.find(
            {
                "organization_id": ORG_ID,
                "source_type": "asset_depreciation",
                "source_id": first_record["id"],
                "is_reversal": {"$ne": True},
            },
            {"_id": 0, "id": 1},
        )
    )
    assert len(active_journals) == 1


def test_financial_statements_auto_run_depreciation_without_duplicate_entries(admin_token, mongo_db):
    asset = _create_test_asset(admin_token, suffix="FS")
    mongo_db.fixed_asset_depreciations.delete_many({"organization_id": ORG_ID, "asset_id": asset["id"], "year": 2026})

    fs1 = requests.get(
        f"{BASE_URL}/api/financial-statements?from_date=2026-01-01&to_date=2026-12-31",
        headers=_headers(admin_token),
        timeout=90,
    )
    assert fs1.status_code == 200, fs1.text

    record = mongo_db.fixed_asset_depreciations.find_one(
        {"organization_id": ORG_ID, "asset_id": asset["id"], "year": 2026, "id": f"{asset['id']}-2026-annual"},
        {"_id": 0},
    )
    assert record is not None
    assert float(record["amount"]) == pytest.approx(24.5)

    fs2 = requests.get(
        f"{BASE_URL}/api/financial-statements?from_date=2026-01-01&to_date=2026-12-31",
        headers=_headers(admin_token),
        timeout=90,
    )
    assert fs2.status_code == 200, fs2.text

    records_after = list(
        mongo_db.fixed_asset_depreciations.find(
            {"organization_id": ORG_ID, "asset_id": asset["id"], "year": 2026},
            {"_id": 0, "id": 1},
        )
    )
    assert len(records_after) == 1

    journals = list(
        mongo_db.journal_entries.find(
            {
                "organization_id": ORG_ID,
                "source_type": "asset_depreciation",
                "source_id": f"{asset['id']}-2026-annual",
                "is_reversal": {"$ne": True},
            },
            {"_id": 0, "id": 1},
        )
    )
    assert len(journals) == 1


def test_monthly_legacy_records_are_reversed_then_replaced_by_annual(admin_token, mongo_db):
    asset = _create_test_asset(admin_token, suffix="LEGACY")
    now_iso = datetime.now(timezone.utc).isoformat()

    month1_id = f"{asset['id']}-2026-01"
    month2_id = f"{asset['id']}-2026-02"
    mongo_db.fixed_asset_depreciations.insert_many(
        [
            {
                "id": month1_id,
                "organization_id": ORG_ID,
                "asset_id": asset["id"],
                "asset_code": asset["asset_code"],
                "asset_name": asset["asset_name"],
                "category_code": "151",
                "category_name": "الخزائن",
                "year": 2026,
                "month": 1,
                "depreciation_date": "2026-01-31",
                "amount": 2.0,
                "accumulated_after": 2.0,
                "net_book_value_after": 488.0,
                "created_at": now_iso,
                "updated_at": now_iso,
            },
            {
                "id": month2_id,
                "organization_id": ORG_ID,
                "asset_id": asset["id"],
                "asset_code": asset["asset_code"],
                "asset_name": asset["asset_name"],
                "category_code": "151",
                "category_name": "الخزائن",
                "year": 2026,
                "month": 2,
                "depreciation_date": "2026-02-28",
                "amount": 2.0,
                "accumulated_after": 4.0,
                "net_book_value_after": 486.0,
                "created_at": now_iso,
                "updated_at": now_iso,
            },
        ]
    )

    j1_id = f"{TEST_PREFIX}-J1-{uuid.uuid4().hex[:6]}"
    j2_id = f"{TEST_PREFIX}-J2-{uuid.uuid4().hex[:6]}"
    mongo_db.journal_entries.insert_many(
        [
            {
                "id": j1_id,
                "organization_id": ORG_ID,
                "entry_number": 990001,
                "entry_date": "2026-01-31",
                "description": f"{TEST_PREFIX} monthly depreciation #1",
                "reference": f"{TEST_PREFIX}-M1",
                "source_type": "asset_depreciation",
                "source_id": month1_id,
                "status": "approved",
                "is_auto": True,
                "lines": [
                    {"account_code": "5104", "account_name": "إهلاك الخزائن", "debit": 2.0, "credit": 0},
                    {"account_code": "1204", "account_name": "مجمع إهلاك الخزائن", "debit": 0, "credit": 2.0},
                ],
                "total_debit": 2.0,
                "total_credit": 2.0,
                "created_at": now_iso,
                "updated_at": now_iso,
            },
            {
                "id": j2_id,
                "organization_id": ORG_ID,
                "entry_number": 990002,
                "entry_date": "2026-02-28",
                "description": f"{TEST_PREFIX} monthly depreciation #2",
                "reference": f"{TEST_PREFIX}-M2",
                "source_type": "asset_depreciation",
                "source_id": month2_id,
                "status": "approved",
                "is_auto": True,
                "lines": [
                    {"account_code": "5104", "account_name": "إهلاك الخزائن", "debit": 2.0, "credit": 0},
                    {"account_code": "1204", "account_name": "مجمع إهلاك الخزائن", "debit": 0, "credit": 2.0},
                ],
                "total_debit": 2.0,
                "total_credit": 2.0,
                "created_at": now_iso,
                "updated_at": now_iso,
            },
        ]
    )

    run_response = requests.post(
        f"{BASE_URL}/api/fixed-assets/depreciation/run",
        json={"year": 2026, "month": 12},
        headers=_headers(admin_token),
        timeout=40,
    )
    assert run_response.status_code == 200, run_response.text

    monthly_remaining = list(
        mongo_db.fixed_asset_depreciations.find(
            {"organization_id": ORG_ID, "asset_id": asset["id"], "year": 2026, "id": {"$in": [month1_id, month2_id]}},
            {"_id": 0, "id": 1},
        )
    )
    assert len(monthly_remaining) == 0

    annual_record = mongo_db.fixed_asset_depreciations.find_one(
        {"organization_id": ORG_ID, "asset_id": asset["id"], "id": f"{asset['id']}-2026-annual"},
        {"_id": 0},
    )
    assert annual_record is not None
    assert float(annual_record["amount"]) == pytest.approx(24.5)

    original_j1 = mongo_db.journal_entries.find_one({"organization_id": ORG_ID, "id": j1_id}, {"_id": 0, "reversal_entry_id": 1})
    original_j2 = mongo_db.journal_entries.find_one({"organization_id": ORG_ID, "id": j2_id}, {"_id": 0, "reversal_entry_id": 1})
    assert original_j1 is not None and original_j1.get("reversal_entry_id")
    assert original_j2 is not None and original_j2.get("reversal_entry_id")

    reversals = list(
        mongo_db.journal_entries.find(
            {"organization_id": ORG_ID, "is_reversal": True, "reversal_of_entry_id": {"$in": [j1_id, j2_id]}},
            {"_id": 0, "id": 1, "reversal_of_entry_id": 1},
        )
    )
    assert len(reversals) == 2


def test_download_setup_exe_is_valid_mz_and_matches_dist_size():
    response = requests.get(f"{BASE_URL}/api/download/setup", timeout=120)
    assert response.status_code == 200, response.text
    assert response.content[:2] == b"MZ"

    local_exe = Path("/app/dist/BankDepositSystemSetup.exe")
    assert local_exe.exists()
    assert len(response.content) == local_exe.stat().st_size
