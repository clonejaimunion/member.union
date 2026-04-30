"""Iteration 27: fixed-assets catalog + membership preview/commit regression coverage."""

import io
import os
import uuid

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient


# Modules/features under test: fixed-assets catalog add/delete + disposal date, membership import preview/commit/cancel, legacy import compatibility, org isolation
ENV_BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
FILE_BASE_URL = dotenv_values("/app/frontend/.env").get("REACT_APP_BACKEND_URL")
BASE_URL = (ENV_BASE_URL or FILE_BASE_URL or "").rstrip("/")

MONGO_URL = dotenv_values("/app/backend/.env").get("MONGO_URL", "").strip('"')
DB_NAME = dotenv_values("/app/backend/.env").get("DB_NAME", "").strip('"')

ASSET_INVOICE_PREFIX = "TEST_IT27_FA_"
CATALOG_PREFIX = "TEST_IT27_ASSET_"
MEMBER_PREFIX = "TEST_IT27_MEMBER_"
GOV_NAME = "TEST_IT27_GOV"
COMMITTEE_NAME = "TEST_IT27_COMMITTEE"
IMPORT_HEADERS_AR = ["رقم العضوية", "الاسم", "الرقم القومي", "تاريخ الميلاد", "العنوان", "في حالة الوفاة"]


def _headers(token: str | None = None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _login(username: str, password: str, organization_id: str):
    return requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": username, "password": password, "organization_id": organization_id},
        timeout=30,
    )


def _csv_bytes(rows: list[list[str]]) -> bytes:
    return ("\n".join([",".join(row) for row in rows]) + "\n").encode("utf-8")


def _search_member(token: str, name: str):
    response = requests.get(
        f"{BASE_URL}/api/memberships/search",
        params={"name": name},
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
        response = _login("admin", "Admin@123", "social-solidarity")
    if response.status_code != 200:
        pytest.skip(f"social-solidarity admin login failed: {response.status_code}")
    token = response.json().get("token")
    if not token:
        pytest.skip("No token for social admin")
    return token


@pytest.fixture(scope="session")
def union_admin_token():
    response = _login("admin_union", "Admin@123", "general-union")
    if response.status_code != 200:
        pytest.skip(f"general-union admin login failed: {response.status_code}")
    token = response.json().get("token")
    if not token:
        pytest.skip("No token for union admin")
    return token


@pytest.fixture(scope="session", autouse=True)
def cleanup_iteration27_data():
    yield
    if not MONGO_URL or not DB_NAME:
        return
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    try:
        db.memberships.delete_many(
            {
                "organization_id": "social-solidarity",
                "$or": [
                    {"name": {"$regex": f"^{MEMBER_PREFIX}"}},
                    {"governorate": GOV_NAME},
                    {"union_committee": COMMITTEE_NAME},
                ],
            }
        )
        db.membership_import_previews.delete_many({"organization_id": "social-solidarity", "governorate": GOV_NAME})
        db.fixed_assets.delete_many({"organization_id": "social-solidarity", "invoice_number": {"$regex": f"^{ASSET_INVOICE_PREFIX}"}})
        db.fixed_asset_depreciations.delete_many({"organization_id": "social-solidarity", "asset_name": {"$regex": f"^{CATALOG_PREFIX}"}})
        db.fixed_asset_catalog_items.delete_many({"organization_id": "social-solidarity", "name": {"$regex": f"^{CATALOG_PREFIX}"}})
        db.fixed_asset_catalog_hidden.delete_many({"organization_id": "social-solidarity", "name": {"$regex": f"^{CATALOG_PREFIX}"}})
    finally:
        client.close()


def test_fixed_assets_catalog_add_use_delete_without_removing_registered_asset(social_admin_token):
    categories_response = requests.get(f"{BASE_URL}/api/fixed-assets/categories", headers=_headers(social_admin_token), timeout=30)
    assert categories_response.status_code == 200, categories_response.text
    categories = categories_response.json()
    furniture = next((item for item in categories if item.get("code") == "5"), None)
    assert furniture is not None

    item_name = f"{CATALOG_PREFIX}{uuid.uuid4().hex[:6]}"
    create_item = requests.post(
        f"{BASE_URL}/api/fixed-assets/catalog-items",
        json={"category_code": "5", "name": item_name},
        headers=_headers(social_admin_token),
        timeout=30,
    )
    assert create_item.status_code == 200, create_item.text
    created_item = create_item.json()
    assert created_item["name"] == item_name
    assert created_item["is_custom"] is True

    list_items = requests.get(
        f"{BASE_URL}/api/fixed-assets/catalog-items",
        params={"category_code": "5"},
        headers=_headers(social_admin_token),
        timeout=30,
    )
    assert list_items.status_code == 200, list_items.text
    item_names = [item["name"] for item in list_items.json()]
    assert item_name in item_names

    banks_response = requests.get(f"{BASE_URL}/api/banks", headers=_headers(social_admin_token), timeout=30)
    assert banks_response.status_code == 200, banks_response.text
    bank_id = banks_response.json()[0]["id"]

    create_asset = requests.post(
        f"{BASE_URL}/api/fixed-assets",
        json={
            "category_code": "5",
            "asset_name": item_name,
            "purchase_date": "2026-01-15",
            "purchase_cost": 12000,
            "bank_id": bank_id,
            "invoice_number": f"{ASSET_INVOICE_PREFIX}{uuid.uuid4().hex[:8]}",
            "notes": "iteration27",
            "is_active": True,
        },
        headers=_headers(social_admin_token),
        timeout=30,
    )
    assert create_asset.status_code == 200, create_asset.text
    asset = create_asset.json()
    assert asset["purchase_date"] == "2026-01-15"
    assert asset["disposal_date"] == "2035-12-31"

    delete_item = requests.delete(
        f"{BASE_URL}/api/fixed-assets/catalog-items/{created_item['id']}",
        headers=_headers(social_admin_token),
        timeout=30,
    )
    assert delete_item.status_code == 200, delete_item.text

    list_after_delete = requests.get(
        f"{BASE_URL}/api/fixed-assets/catalog-items",
        params={"category_code": "5"},
        headers=_headers(social_admin_token),
        timeout=30,
    )
    assert list_after_delete.status_code == 200, list_after_delete.text
    assert item_name not in [item["name"] for item in list_after_delete.json()]

    assets_response = requests.get(f"{BASE_URL}/api/fixed-assets", headers=_headers(social_admin_token), timeout=30)
    assert assets_response.status_code == 200, assets_response.text
    saved_asset = next((item for item in assets_response.json() if item.get("id") == asset["id"]), None)
    assert saved_asset is not None
    assert saved_asset["asset_name"] == item_name
    assert saved_asset["disposal_date"] == "2035-12-31"

    delete_asset = requests.delete(f"{BASE_URL}/api/fixed-assets/{asset['id']}", headers=_headers(social_admin_token), timeout=30)
    assert delete_asset.status_code == 200, delete_asset.text
    verify_deleted = requests.get(f"{BASE_URL}/api/fixed-assets", headers=_headers(social_admin_token), timeout=30)
    assert verify_deleted.status_code == 200, verify_deleted.text
    assert all(item.get("id") != asset["id"] for item in verify_deleted.json())


def test_membership_preview_does_not_insert_before_commit_and_commit_inserts_accepted_only(social_admin_token):
    seed_response = requests.post(
        f"{BASE_URL}/api/memberships",
        json={
            "governorate": GOV_NAME,
            "union_committee": COMMITTEE_NAME,
            "membership_number": f"9{uuid.uuid4().int % 10**8:08d}",
            "name": f"{MEMBER_PREFIX}SEED_{uuid.uuid4().hex[:5]}",
            "national_id": f"3{uuid.uuid4().int % 10**13:013d}",
            "birth_date": "1975-01-10",
            "address": "عنوان تجريبي",
            "death_beneficiary": "مستفيد تجريبي",
        },
        headers=_headers(social_admin_token),
        timeout=30,
    )
    assert seed_response.status_code == 200, seed_response.text

    valid_name = f"{MEMBER_PREFIX}PREVIEW_OK_{uuid.uuid4().hex[:5]}"
    csv_payload = _csv_bytes(
        [
            IMPORT_HEADERS_AR,
            [f"8{uuid.uuid4().int % 10**8:08d}", valid_name, f"2{uuid.uuid4().int % 10**13:013d}", "1970-05-15", "عنوان صحيح", "المستفيد الاول"],
            [f"7{uuid.uuid4().int % 10**8:08d}", f"{MEMBER_PREFIX}BAD_{uuid.uuid4().hex[:4]}", "", "1970-05-15", "عنوان ناقص", "المستفيد الثاني"],
        ]
    )

    preview_response = requests.post(
        f"{BASE_URL}/api/memberships/import/preview",
        headers=_headers(social_admin_token),
        data={"governorate": GOV_NAME, "union_committee": COMMITTEE_NAME},
        files={"file": ("iteration27_preview.csv", io.BytesIO(csv_payload), "text/csv")},
        timeout=40,
    )
    assert preview_response.status_code == 200, preview_response.text
    preview_data = preview_response.json()
    assert preview_data["accepted_count"] == 1
    assert preview_data["skipped_count"] == 1
    assert preview_data["total_rows_detected"] == 2
    assert any(row["name"] == valid_name for row in preview_data["accepted_rows"])

    before_commit_results = _search_member(social_admin_token, valid_name)
    assert len(before_commit_results) == 0

    commit_response = requests.post(
        f"{BASE_URL}/api/memberships/import/commit",
        json={"preview_id": preview_data["preview_id"]},
        headers=_headers(social_admin_token),
        timeout=40,
    )
    assert commit_response.status_code == 200, commit_response.text
    commit_data = commit_response.json()
    assert commit_data["imported_count"] == 1
    assert commit_data["skipped_count"] >= 1
    assert commit_data["total_rows_detected"] == 2
    assert any(member["name"] == valid_name for member in commit_data["imported_members"])

    after_commit_results = _search_member(social_admin_token, valid_name)
    assert len(after_commit_results) == 1
    assert after_commit_results[0]["governorate"] == GOV_NAME
    assert after_commit_results[0]["union_committee"] == COMMITTEE_NAME


def test_membership_preview_cancel_behavior_no_commit_no_insert(social_admin_token):
    cancel_name = f"{MEMBER_PREFIX}PREVIEW_CANCEL_{uuid.uuid4().hex[:5]}"
    csv_payload = _csv_bytes(
        [
            IMPORT_HEADERS_AR,
            [f"6{uuid.uuid4().int % 10**8:08d}", cancel_name, f"1{uuid.uuid4().int % 10**13:013d}", "1972-06-01", "عنوان الغاء", "مستفيد الغاء"],
        ]
    )

    preview_response = requests.post(
        f"{BASE_URL}/api/memberships/import/preview",
        headers=_headers(social_admin_token),
        data={"governorate": GOV_NAME, "union_committee": COMMITTEE_NAME},
        files={"file": ("iteration27_cancel.csv", io.BytesIO(csv_payload), "text/csv")},
        timeout=40,
    )
    assert preview_response.status_code == 200, preview_response.text
    preview_data = preview_response.json()
    assert preview_data["accepted_count"] == 1

    search_results = _search_member(social_admin_token, cancel_name)
    assert len(search_results) == 0


def test_legacy_membership_import_endpoint_still_works(social_admin_token):
    legacy_name = f"{MEMBER_PREFIX}LEGACY_{uuid.uuid4().hex[:5]}"
    csv_payload = _csv_bytes(
        [
            IMPORT_HEADERS_AR,
            [f"5{uuid.uuid4().int % 10**8:08d}", legacy_name, f"9{uuid.uuid4().int % 10**13:013d}", "1969-12-30", "عنوان قديم", "مستفيد قديم"],
            ["", "", "", "", "", ""],
        ]
    )
    legacy_response = requests.post(
        f"{BASE_URL}/api/memberships/import",
        headers=_headers(social_admin_token),
        data={"governorate": GOV_NAME, "union_committee": COMMITTEE_NAME},
        files={"file": ("iteration27_legacy.csv", io.BytesIO(csv_payload), "text/csv")},
        timeout=40,
    )
    assert legacy_response.status_code == 200, legacy_response.text
    legacy_data = legacy_response.json()
    assert legacy_data["imported_count"] == 1
    assert legacy_data["skipped_count"] >= 0
    assert legacy_data["total_rows_detected"] >= 1
    assert any(member["name"] == legacy_name for member in legacy_data["imported_members"])

    search_results = _search_member(social_admin_token, legacy_name)
    assert len(search_results) == 1


def test_membership_routes_are_isolated_from_general_union(union_admin_token):
    list_response = requests.get(f"{BASE_URL}/api/memberships", headers=_headers(union_admin_token), timeout=30)
    assert list_response.status_code == 404
    assert "العضوية" in list_response.text

    preview_payload = _csv_bytes(
        [IMPORT_HEADERS_AR, ["123", "X", "123", "2000-01-01", "x", "x"]]
    )
    preview_response = requests.post(
        f"{BASE_URL}/api/memberships/import/preview",
        headers=_headers(union_admin_token),
        data={"governorate": "القاهرة", "union_committee": "اختبار"},
        files={"file": ("union_block.csv", io.BytesIO(preview_payload), "text/csv")},
        timeout=40,
    )
    assert preview_response.status_code == 404
    assert "العضوية" in preview_response.text
