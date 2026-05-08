import os
from datetime import date, timedelta

import pytest
import requests
from pymongo import MongoClient


# Treasury/Banks read-only endpoint: auth, filters, data source validation, and no-write checks


def _load_base_url() -> str:
    value = os.environ.get("REACT_APP_BACKEND_URL", "").strip().rstrip("/")
    if value:
        return value
    env_path = "/app/frontend/.env"
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    parsed = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if parsed:
                        return parsed.rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL is required for tests")


BASE_URL = _load_base_url()
ORG_ID = "social-solidarity"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Admin@123"


@pytest.fixture(scope="session")
def session_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def mongo_db():
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not mongo_url or not db_name:
        pytest.skip("MONGO_URL/DB_NAME missing; cannot run no-write and source checks")
    client = MongoClient(mongo_url)
    try:
        yield client[db_name]
    finally:
        client.close()


@pytest.fixture(scope="session")
def auth_headers(session_client):
    response = session_client.post(
        f"{BASE_URL}/api/auth/login",
        json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD,
            "organization_id": ORG_ID,
        },
        timeout=20,
    )
    assert response.status_code == 200, f"Login failed: {response.status_code} {response.text}"
    token = response.json().get("token")
    assert isinstance(token, str) and token
    return {"Authorization": f"Bearer {token}"}


def get_treasury_report(session_client, auth_headers, params=None):
    return session_client.get(
        f"{BASE_URL}/api/treasury-banks",
        headers=auth_headers,
        params=params or {},
        timeout=40,
    )


def test_treasury_banks_requires_auth(session_client):
    response = session_client.get(f"{BASE_URL}/api/treasury-banks", timeout=20)
    assert response.status_code in (401, 403)


def test_treasury_banks_returns_expected_shape_and_source(session_client, auth_headers, mongo_db):
    response = get_treasury_report(session_client, auth_headers, {"account_id": "all", "account_kind": "all", "movement_type": "all"})
    assert response.status_code == 200
    data = response.json()

    assert isinstance(data.get("summary"), dict)
    assert isinstance(data.get("accounts"), list)
    assert isinstance(data.get("transactions"), list)
    assert data["summary"].get("source") == "journal_entries_approved_read_only"

    txs = data["transactions"]
    sample = txs[:20]
    for tx in sample:
        found = mongo_db.journal_entries.find_one(
            {"organization_id": ORG_ID, "id": tx.get("entry_id")},
            {"_id": 0, "id": 1},
        )
        assert found is not None, f"entry_id {tx.get('entry_id')} not found in journal_entries"


def test_treasury_banks_rejects_invalid_date_range(session_client, auth_headers):
    response = get_treasury_report(
        session_client,
        auth_headers,
        {"from_date": "2026-12-31", "to_date": "2026-01-01"},
    )
    assert response.status_code == 400
    body = response.json()
    assert "detail" in body


def test_treasury_banks_filters_account_kind_and_account_id(session_client, auth_headers):
    all_response = get_treasury_report(session_client, auth_headers, {"account_kind": "all", "account_id": "all"})
    assert all_response.status_code == 200
    all_data = all_response.json()
    accounts = all_data.get("accounts", [])
    assert len(accounts) >= 1

    bank_response = get_treasury_report(session_client, auth_headers, {"account_kind": "bank", "account_id": "all"})
    assert bank_response.status_code == 200
    for account in bank_response.json().get("accounts", []):
        assert account.get("account_kind") == "bank"

    cash_response = get_treasury_report(session_client, auth_headers, {"account_kind": "cash", "account_id": "all"})
    assert cash_response.status_code == 200
    for account in cash_response.json().get("accounts", []):
        assert account.get("account_kind") == "cash"

    one_account_id = accounts[0].get("id")
    by_id_response = get_treasury_report(session_client, auth_headers, {"account_kind": "all", "account_id": one_account_id})
    assert by_id_response.status_code == 200
    by_id_data = by_id_response.json()
    assert len(by_id_data.get("accounts", [])) == 1
    assert by_id_data["accounts"][0]["id"] == one_account_id
    for tx in by_id_data.get("transactions", []):
        assert tx.get("account_id") == one_account_id


def test_treasury_banks_filters_movement_and_search(session_client, auth_headers):
    response = get_treasury_report(session_client, auth_headers, {"account_id": "all", "movement_type": "all"})
    assert response.status_code == 200
    data = response.json()
    txs = data.get("transactions", [])

    revenue_response = get_treasury_report(session_client, auth_headers, {"movement_type": "revenue", "account_id": "all"})
    assert revenue_response.status_code == 200
    for tx in revenue_response.json().get("transactions", []):
        assert tx.get("movement_type") == "إيراد"

    expense_response = get_treasury_report(session_client, auth_headers, {"movement_type": "expense", "account_id": "all"})
    assert expense_response.status_code == 200
    for tx in expense_response.json().get("transactions", []):
        assert tx.get("movement_type") == "مصروف"

    if txs:
        probe = txs[0]
        search_term = str(probe.get("entry_number"))
        search_response = get_treasury_report(session_client, auth_headers, {"search": search_term, "account_id": "all"})
        assert search_response.status_code == 200
        for tx in search_response.json().get("transactions", []):
            candidate = " ".join(
                [
                    str(tx.get("entry_number") or ""),
                    tx.get("description") or "",
                    tx.get("account_name") or "",
                    tx.get("bank_name") or "",
                    tx.get("reference") or "",
                ]
            )
            assert search_term in candidate


def test_treasury_banks_date_filter_reduces_or_equal_scope(session_client, auth_headers):
    today = date.today()
    week_ago = today - timedelta(days=7)
    broad = get_treasury_report(session_client, auth_headers, {"to_date": today.isoformat(), "account_id": "all"})
    assert broad.status_code == 200
    narrow = get_treasury_report(
        session_client,
        auth_headers,
        {"from_date": week_ago.isoformat(), "to_date": today.isoformat(), "account_id": "all"},
    )
    assert narrow.status_code == 200
    assert len(narrow.json().get("transactions", [])) <= len(broad.json().get("transactions", []))


def test_treasury_banks_accounts_are_only_bank_and_cash_box(mongo_db, session_client, auth_headers):
    response = get_treasury_report(session_client, auth_headers, {"account_id": "all", "account_kind": "all"})
    assert response.status_code == 200
    accounts = response.json().get("accounts", [])
    returned_ids = [item.get("id") for item in accounts if item.get("id")]

    if not returned_ids:
        pytest.skip("No treasury/bank accounts returned for current org")

    docs = list(
        mongo_db.chart_accounts.find(
            {"organization_id": ORG_ID, "id": {"$in": returned_ids}},
            {"_id": 0, "id": 1, "system_key": 1},
        )
    )
    by_id = {doc["id"]: doc for doc in docs}

    for account in accounts:
        doc = by_id.get(account["id"])
        assert doc is not None
        system_key = str(doc.get("system_key") or "")
        assert system_key == "cash_box" or system_key.startswith("bank:"), system_key


def test_treasury_banks_repeated_calls_do_not_write_target_collections(mongo_db, session_client, auth_headers):
    tracked = ["journal_entries", "reconciliations", "bank_settings", "chart_accounts"]
    before_counts = {
        name: mongo_db[name].count_documents({"organization_id": ORG_ID})
        for name in tracked
    }

    for _ in range(3):
        response = get_treasury_report(
            session_client,
            auth_headers,
            {
                "account_id": "all",
                "account_kind": "all",
                "movement_type": "all",
                "search": "",
            },
        )
        assert response.status_code == 200

    after_counts = {
        name: mongo_db[name].count_documents({"organization_id": ORG_ID})
        for name in tracked
    }

    assert after_counts == before_counts
