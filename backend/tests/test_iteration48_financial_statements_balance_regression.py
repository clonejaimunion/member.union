"""Regression tests for financial statements balance/reclassification and setup download binary."""

import os
import time
from pathlib import Path

import pytest
import requests


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")

# Module scope: financial statements (accumulated depreciation, bank credit reclass, opening equity carry) + setup download.


@pytest.fixture(scope="session")
def base_url():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL is not set")
    return BASE_URL.rstrip("/")


@pytest.fixture
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


def login(session: requests.Session, base_url: str, organization_id: str, username: str = "admin", password: str = "Admin@123") -> str:
    response = session.post(
        f"{base_url}/api/auth/login",
        json={"username": username, "password": password, "organization_id": organization_id},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert isinstance(body.get("token"), str) and body["token"]
    assert body.get("user", {}).get("organization_id") == organization_id
    return body["token"]


def create_isolated_org(session: requests.Session, base_url: str, super_admin_token: str, suffix: str) -> str:
    org_id = f"iter48-{suffix}-{int(time.time() * 1000)}"
    response = session.post(
        f"{base_url}/api/admin/organizations",
        headers={"Authorization": f"Bearer {super_admin_token}"},
        json={
            "id": org_id,
            "name": f"ITER48 Org {suffix}",
            "login_label": f"ITER48 {suffix}",
            "clone_from": "social-solidarity",
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data.get("id") == org_id
    return org_id


def sync_and_list_accounts(session: requests.Session, base_url: str, headers: dict) -> list:
    sync_response = session.post(f"{base_url}/api/chart-accounts/sync", headers=headers)
    assert sync_response.status_code == 200, sync_response.text
    list_response = session.get(f"{base_url}/api/chart-accounts", headers=headers)
    assert list_response.status_code == 200, list_response.text
    accounts = list_response.json()
    assert isinstance(accounts, list) and len(accounts) > 0
    return accounts


def update_opening_balance(session: requests.Session, base_url: str, headers: dict, account_id: str, opening_balance: float):
    response = session.put(
        f"{base_url}/api/chart-accounts/{account_id}",
        headers=headers,
        json={"opening_balance": opening_balance},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert round(float(data.get("opening_balance") or 0), 2) == round(float(opening_balance), 2)


def test_accumulated_depreciation_credit_nature_not_flagged_reverse(api_client, base_url):
    super_admin_token = login(api_client, base_url, "social-solidarity")
    org_id = create_isolated_org(api_client, base_url, super_admin_token, "accdep")
    org_token = login(api_client, base_url, org_id)
    headers = {"Authorization": f"Bearer {org_token}"}

    accounts = sync_and_list_accounts(api_client, base_url, headers)
    target_codes = ["101-م", "151-م", "155-م", "5-م"]
    target_accounts = [account for account in accounts if account.get("code") in target_codes]
    assert len(target_accounts) == 4

    for account in target_accounts:
        assert account.get("nature") == "credit"
        assert account.get("account_type") == "asset"
        update_opening_balance(api_client, base_url, headers, account["id"], 100.0)

    statement_response = api_client.get(f"{base_url}/api/financial-statements", headers=headers)
    assert statement_response.status_code == 200, statement_response.text
    payload = statement_response.json()
    warnings = [
        item
        for item in payload.get("accounting_errors", [])
        if item.get("error_type") == "رصيد عكسي" and any(code in (item.get("location") or "") for code in target_codes)
    ]
    assert warnings == []


def test_bank_credit_asset_reclassified_to_liabilities_without_reverse_warning(api_client, base_url):
    super_admin_token = login(api_client, base_url, "social-solidarity")
    org_id = create_isolated_org(api_client, base_url, super_admin_token, "bankcredit")
    org_token = login(api_client, base_url, org_id)
    headers = {"Authorization": f"Bearer {org_token}"}

    accounts = sync_and_list_accounts(api_client, base_url, headers)
    bank_account = next(
        (
            account
            for account in accounts
            if account.get("account_type") == "asset"
            and account.get("nature") == "debit"
            and str(account.get("code") or "").startswith("11")
        ),
        None,
    )
    assert bank_account is not None

    update_opening_balance(api_client, base_url, headers, bank_account["id"], -1200.0)

    statement_response = api_client.get(f"{base_url}/api/financial-statements", headers=headers)
    assert statement_response.status_code == 200, statement_response.text
    payload = statement_response.json()

    liabilities = payload["balance_sheet"]["liabilities"]["lines"]
    assets = payload["balance_sheet"]["assets"]["lines"]
    reclassified = [line for line in liabilities if line.get("code") == bank_account.get("code") and "رصيد دائن بالبنك" in (line.get("name") or "")]
    asset_line_same_code = [line for line in assets if line.get("code") == bank_account.get("code")]
    assert len(reclassified) == 1
    assert asset_line_same_code == []
    assert round(float(reclassified[0].get("amount") or 0), 2) == 1200.0

    reverse_warnings = [
        item
        for item in payload.get("accounting_errors", [])
        if item.get("error_type") == "رصيد عكسي" and str(bank_account.get("code")) in (item.get("location") or "")
    ]
    assert reverse_warnings == []


def test_opening_assets_without_equity_adds_opening_carry_line_and_balances_check_total(api_client, base_url):
    super_admin_token = login(api_client, base_url, "social-solidarity")
    org_id = create_isolated_org(api_client, base_url, super_admin_token, "opening")
    org_token = login(api_client, base_url, org_id)
    headers = {"Authorization": f"Bearer {org_token}"}

    accounts = sync_and_list_accounts(api_client, base_url, headers)
    bank_account = next(
        (
            account
            for account in accounts
            if account.get("account_type") == "asset"
            and account.get("nature") == "debit"
            and str(account.get("code") or "").startswith("11")
        ),
        None,
    )
    assert bank_account is not None

    update_opening_balance(api_client, base_url, headers, bank_account["id"], 777.0)

    statement_response = api_client.get(f"{base_url}/api/financial-statements", headers=headers)
    assert statement_response.status_code == 200, statement_response.text
    payload = statement_response.json()

    check_total = round(float(payload["balance_sheet"]["check"].get("total") or 0), 2)
    assert check_total == 0.0

    equity_lines = payload["balance_sheet"]["equity"]["lines"]
    carry_lines = [line for line in equity_lines if line.get("name") == "رصيد افتتاحي مرحل / صافي الأصول"]
    assert len(carry_lines) == 1
    assert round(float(carry_lines[0].get("amount") or 0), 2) == 777.0

    critical_balance_errors = [
        item
        for item in payload.get("accounting_errors", [])
        if item.get("severity") == "critical" and item.get("error_type") == "الميزانية غير متوازنة"
    ]
    assert critical_balance_errors == []


def test_download_setup_endpoint_returns_valid_exe_binary(api_client, base_url):
    response = api_client.get(f"{base_url}/api/download/setup")
    assert response.status_code == 200, response.text
    assert "application/vnd.microsoft.portable-executable" in (response.headers.get("content-type") or "")

    content = response.content
    assert len(content) > 1_000_000
    assert content[:2] == b"MZ"

    local_setup_path = Path("/app/dist/BankDepositSystemSetup.exe")
    assert local_setup_path.exists()
    local_size = local_setup_path.stat().st_size
    assert len(content) == local_size
