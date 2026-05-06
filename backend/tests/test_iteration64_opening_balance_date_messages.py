import os
import uuid
from datetime import date, timedelta

import pytest
import requests
from dotenv import dotenv_values


# Modules/features under test: opening balance date enforcement, Arabic rejection messages, and validation endpoint health
FRONTEND_ENV = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or FRONTEND_ENV.get("REACT_APP_BACKEND_URL") or "").rstrip("/")


@pytest.fixture(scope="session")
def base_url():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL is not configured")
    return BASE_URL


@pytest.fixture(scope="session")
def session_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


def _login(base_url: str, session_client: requests.Session, username: str, password: str, organization_id: str):
    return session_client.post(
        f"{base_url}/api/auth/login",
        json={"username": username, "password": password, "organization_id": organization_id},
        timeout=40,
    )


@pytest.fixture(scope="session")
def super_admin_auth(base_url, session_client):
    response = _login(base_url, session_client, "admin", "Admin@123", "social-solidarity")
    if response.status_code != 200:
        pytest.skip(f"super admin login failed: {response.status_code} {response.text}")
    token = response.json().get("token")
    if not token:
        pytest.skip("missing super admin token")
    return {
        "headers": {"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        "login_response": response,
    }


@pytest.fixture()
def iter64_seed_bank(base_url, session_client, super_admin_auth):
    headers = super_admin_auth["headers"]
    opening_date = (date.today() - timedelta(days=5)).isoformat()
    bank_name = f"TEST_ITER64_{uuid.uuid4().hex[:8]}"
    payload = {
        "name": bank_name,
        "code": f"I64{uuid.uuid4().hex[:4].upper()}",
        "swift_code": "TESTEGCX",
        "logo_url": "",
        "color": "#125f9a",
        "opening_balance": 1000.0,
        "opening_balance_date": opening_date,
    }
    create_resp = session_client.post(f"{base_url}/api/admin/banks", headers=headers, json=payload, timeout=60)
    assert create_resp.status_code == 200, create_resp.text
    created_bank = create_resp.json()
    created_deposit_ids = []

    yield {
        "id": created_bank["id"],
        "name": created_bank["name"],
        "opening_date": opening_date,
        "deposit_ids": created_deposit_ids,
    }

    for deposit_id in created_deposit_ids:
        session_client.delete(
            f"{base_url}/api/banks/{created_bank['id']}/deposits/{deposit_id}",
            headers=headers,
            timeout=40,
        )
    session_client.delete(f"{base_url}/api/admin/banks/{created_bank['id']}", headers=headers, timeout=40)


def _create_deposit(base_url: str, session_client: requests.Session, headers: dict, bank_id: str, on_date: date):
    maturity_date = on_date + timedelta(days=45)
    payload = {
        "account_number": f"ACC-I64-{uuid.uuid4().hex[:6]}",
        "deposit_number": f"DEP-I64-{uuid.uuid4().hex[:6]}",
        "amount": 1500.0,
        "creation_datetime": f"{on_date.isoformat()}T09:00:00Z",
        "maturity_datetime": f"{maturity_date.isoformat()}T09:00:00Z",
        "monthly_interest_rate": 1.0,
    }
    return session_client.post(f"{base_url}/api/banks/{bank_id}/deposits", headers=headers, json=payload, timeout=60)


def test_login_sets_httponly_cookie(base_url, super_admin_auth):
    login_response = super_admin_auth["login_response"]
    assert login_response.status_code == 200
    set_cookie_header = login_response.headers.get("set-cookie", "")
    assert "access_token=" in set_cookie_header
    assert "HttpOnly" in set_cookie_header


def test_opening_balance_date_after_existing_transactions_rejected_with_arabic_message(base_url, session_client, super_admin_auth, iter64_seed_bank):
    headers = super_admin_auth["headers"]
    bank_id = iter64_seed_bank["id"]
    tx_date = date.fromisoformat(iter64_seed_bank["opening_date"]) + timedelta(days=1)

    create_deposit = _create_deposit(base_url, session_client, headers, bank_id, tx_date)
    assert create_deposit.status_code == 200, create_deposit.text
    iter64_seed_bank["deposit_ids"].append(create_deposit.json()["id"])

    invalid_opening_date = tx_date + timedelta(days=1)
    update_resp = session_client.put(
        f"{base_url}/api/admin/banks/{bank_id}/opening-balance",
        headers=headers,
        json={"opening_balance": 2000.0, "opening_balance_date": invalid_opening_date.isoformat()},
        timeout=60,
    )
    assert update_resp.status_code == 400, update_resp.text
    detail = update_resp.json().get("detail", "")
    assert "لا يمكن تعيين تاريخ الرصيد الافتتاحي بعد معاملات مسجلة بالفعل لهذا البنك" in detail
    assert "اختر تاريخاً يسبق أو يساوي أقدم معاملة" in detail
    assert "الودائع" in detail


def test_transaction_before_opening_balance_date_rejected_with_bank_and_dates(base_url, session_client, super_admin_auth, iter64_seed_bank):
    headers = super_admin_auth["headers"]
    bank_id = iter64_seed_bank["id"]
    opening_date = date.fromisoformat(iter64_seed_bank["opening_date"])
    before_date = opening_date - timedelta(days=1)

    resp = _create_deposit(base_url, session_client, headers, bank_id, before_date)
    assert resp.status_code == 400, resp.text
    detail = resp.json().get("detail", "")
    assert "لا يُسمح بإجراء أي معاملة مالية قبل تاريخ الرصيد الافتتاحي" in detail
    assert iter64_seed_bank["name"] in detail
    assert before_date.isoformat().replace("-", "/") in detail
    assert opening_date.isoformat().replace("-", "/") in detail


def test_transaction_on_opening_balance_date_allowed(base_url, session_client, super_admin_auth, iter64_seed_bank):
    headers = super_admin_auth["headers"]
    bank_id = iter64_seed_bank["id"]
    opening_date = date.fromisoformat(iter64_seed_bank["opening_date"])

    resp = _create_deposit(base_url, session_client, headers, bank_id, opening_date)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data.get("bank_id") == bank_id
    assert data.get("id")
    iter64_seed_bank["deposit_ids"].append(data["id"])


def test_transaction_after_opening_balance_date_allowed(base_url, session_client, super_admin_auth, iter64_seed_bank):
    headers = super_admin_auth["headers"]
    bank_id = iter64_seed_bank["id"]
    opening_date = date.fromisoformat(iter64_seed_bank["opening_date"])
    after_date = opening_date + timedelta(days=2)

    resp = _create_deposit(base_url, session_client, headers, bank_id, after_date)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data.get("bank_id") == bank_id
    assert data.get("id")
    iter64_seed_bank["deposit_ids"].append(data["id"])


def test_admin_data_flow_validation_is_valid(base_url, session_client, super_admin_auth):
    resp = session_client.get(f"{base_url}/api/admin/data-flow-validation", headers=super_admin_auth["headers"], timeout=90)
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload.get("is_valid") is True
    assert isinstance(payload.get("organizations"), list)
