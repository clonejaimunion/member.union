"""Reconciliation save integrity: calculated balance must match computed breakdown balance."""

import os
import uuid

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient


FRONTEND_ENV = dotenv_values("/app/frontend/.env")
BACKEND_ENV = dotenv_values("/app/backend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or FRONTEND_ENV.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
MONGO_URL = (BACKEND_ENV.get("MONGO_URL") or "").strip('"')
DB_NAME = (BACKEND_ENV.get("DB_NAME") or "").strip('"')
ORG_ID = "social-solidarity"
BANK_ID = "industrial-development"
ITER_PREFIX = f"TEST-ITER71-RECON-{uuid.uuid4().hex[:8]}"


def _headers(token: str | None = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


@pytest.fixture(scope="session")
def base_url():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL is not configured")
    return BASE_URL


@pytest.fixture(scope="session")
def admin_token(base_url):
    response = requests.post(
        f"{base_url}/api/auth/login",
        json={"username": "admin", "password": "Admin@123", "organization_id": ORG_ID},
        headers=_headers(),
        timeout=60,
    )
    if response.status_code != 200:
        pytest.skip(f"admin login failed: {response.status_code} {response.text}")
    return response.json()["token"]


@pytest.fixture(scope="session", autouse=True)
def cleanup_iter71_reconciliation_data():
    yield
    if not MONGO_URL or not DB_NAME:
        return
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    db.reconciliations.delete_many({"organization_id": ORG_ID, "period_label": {"$regex": f"^{ITER_PREFIX}"}})
    client.close()


# Modules/features: save/update reconciliation should keep calculated_balance equal to breakdown.reconciliation_balance.
def test_reconciliation_save_uses_breakdown_balance_without_double_check_application(base_url, admin_token):
    period_label = f"{ITER_PREFIX} أبريل 2199"
    payload = {
        "period_label": period_label,
        "administration": "مشروع التكافل الاجتماعي",
        "book_balance": 1,
        "bank_statement_balance": 2,
        "outstanding_checks": [
            {"check_number": f"{ITER_PREFIX}-O1", "amount": 100.0, "check_date": "2199-04-10T00:00:00+00:00"}
        ],
        "collection_checks": [
            {"check_number": f"{ITER_PREFIX}-C1", "amount": 50.0, "check_date": "2199-04-11T00:00:00+00:00"}
        ],
    }

    create = requests.post(
        f"{base_url}/api/banks/{BANK_ID}/reconciliations",
        json=payload,
        headers=_headers(admin_token),
        timeout=90,
    )
    assert create.status_code == 200, create.text
    created = create.json()

    expected = round(float(created["balance_breakdown"]["reconciliation_balance"]), 2)
    assert round(float(created["book_balance"]), 2) == expected
    assert round(float(created["calculated_balance"]), 2) == expected

    update_payload = {
        **payload,
        "book_balance": 999999,
        "bank_statement_balance": expected,
    }
    update = requests.put(
        f"{base_url}/api/banks/{BANK_ID}/reconciliations/{created['id']}",
        json=update_payload,
        headers=_headers(admin_token),
        timeout=90,
    )
    assert update.status_code == 200, update.text
    updated = update.json()

    updated_expected = round(float(updated["balance_breakdown"]["reconciliation_balance"]), 2)
    assert round(float(updated["book_balance"]), 2) == updated_expected
    assert round(float(updated["calculated_balance"]), 2) == updated_expected
