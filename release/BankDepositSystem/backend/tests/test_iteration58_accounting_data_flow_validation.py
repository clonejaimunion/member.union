import os
from typing import Dict, List, Tuple

import pytest
import requests


# Scope: Validate journal_entries → ledger → trial_balance → financial_statements consistency and account-link integrity.
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
PERIOD_FROM = "1900-01-01"
PERIOD_TO = "2099-12-31"
TARGET_ENTRY_NUMBERS = {122, 123, 128, 129, 130, 131, 132, 133, 138, 139, 144, 145, 146, 147, 152, 153}
ORG_IDS = ["general-union", "social-solidarity"]


@pytest.fixture(scope="session")
def base_url() -> str:
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL is not configured")
    return BASE_URL.rstrip("/")


@pytest.fixture(scope="session")
def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _login(base_url: str, session: requests.Session, organization_id: str) -> Dict[str, str]:
    resp = session.post(
        f"{base_url}/api/auth/login",
        json={
            "username": "admin",
            "password": "Admin@123",
            "organization_id": organization_id,
        },
        timeout=40,
    )
    assert resp.status_code == 200, f"Login failed for {organization_id}: {resp.status_code} {resp.text}"
    token = resp.json().get("token")
    assert isinstance(token, str) and token, f"Missing token for {organization_id}"
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def org_headers(base_url: str, session: requests.Session) -> Dict[str, Dict[str, str]]:
    return {org_id: _login(base_url, session, org_id) for org_id in ORG_IDS}


def _sync_and_get_chart_accounts(base_url: str, session: requests.Session, headers: Dict[str, str]) -> List[dict]:
    sync_resp = session.post(f"{base_url}/api/chart-accounts/sync", headers=headers, timeout=60)
    assert sync_resp.status_code == 200, sync_resp.text

    list_resp = session.get(f"{base_url}/api/chart-accounts", headers=headers, timeout=60)
    assert list_resp.status_code == 200, list_resp.text
    return list_resp.json()


def _fetch_trial_balance(base_url: str, session: requests.Session, headers: Dict[str, str]) -> dict:
    resp = session.get(
        f"{base_url}/api/trial-balance",
        headers=headers,
        params={"from_date": PERIOD_FROM, "to_date": PERIOD_TO},
        timeout=90,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _fetch_financial_statements(base_url: str, session: requests.Session, headers: Dict[str, str]) -> dict:
    resp = session.get(
        f"{base_url}/api/financial-statements",
        headers=headers,
        params={"from_date": PERIOD_FROM, "to_date": PERIOD_TO},
        timeout=120,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.mark.parametrize("organization_id", ORG_IDS)
def test_chart_accounts_have_required_cash_and_membership_alias_targets(
    base_url: str,
    session: requests.Session,
    org_headers: Dict[str, Dict[str, str]],
    organization_id: str,
):
    accounts = _sync_and_get_chart_accounts(base_url, session, org_headers[organization_id])

    by_system_key = {item.get("system_key"): item for item in accounts}

    cash_box = by_system_key.get("cash_box")
    assert cash_box, f"cash_box account missing in {organization_id}"
    assert cash_box.get("code") == "1150", f"cash_box code mismatch in {organization_id}"

    membership_rev = by_system_key.get("membership_subscription_revenue")
    assert membership_rev, f"membership_subscription_revenue account missing in {organization_id}"
    assert membership_rev.get("code") == "4103", f"membership_subscription_revenue code mismatch in {organization_id}"


def test_social_solidarity_target_journal_entries_have_full_account_links(
    base_url: str,
    session: requests.Session,
    org_headers: Dict[str, Dict[str, str]],
):
    headers = org_headers["social-solidarity"]
    resp = session.get(
        f"{base_url}/api/journal-entries",
        headers=headers,
        params={"from_date": PERIOD_FROM, "to_date": PERIOD_TO},
        timeout=90,
    )
    assert resp.status_code == 200, resp.text
    entries = resp.json()

    by_number = {int(item.get("entry_number")): item for item in entries if item.get("entry_number") is not None}
    missing_entries = sorted(number for number in TARGET_ENTRY_NUMBERS if number not in by_number)
    assert not missing_entries, f"Missing target entries in social-solidarity: {missing_entries}"

    incomplete_lines: List[Tuple[int, int, str]] = []
    for entry_number in sorted(TARGET_ENTRY_NUMBERS):
        entry = by_number[entry_number]
        for idx, line in enumerate(entry.get("lines", []), start=1):
            if not line.get("account_id") or not line.get("account_code") or not line.get("account_type"):
                incomplete_lines.append((entry_number, idx, line.get("account_name") or ""))

    assert not incomplete_lines, f"Found lines without full account links: {incomplete_lines}"


@pytest.mark.parametrize("organization_id", ORG_IDS)
def test_financial_statements_valid_and_consistent(
    base_url: str,
    session: requests.Session,
    org_headers: Dict[str, Dict[str, str]],
    organization_id: str,
):
    report = _fetch_financial_statements(base_url, session, org_headers[organization_id])

    assert report.get("is_accounting_valid") is True, f"is_accounting_valid is False for {organization_id}"

    errors = report.get("accounting_errors", [])
    missing_account_errors = [
        item
        for item in errors
        if "سطر قيد بلا حساب" in (item.get("error_type") or "")
        or "بلا حساب" in (item.get("details") or "")
        or "without account" in (item.get("error_type") or "").lower()
        or "without account" in (item.get("details") or "").lower()
    ]
    assert not missing_account_errors, f"Missing-account errors found for {organization_id}: {missing_account_errors}"

    balance_check_total = float(report["balance_sheet"]["check"]["total"])
    assert round(balance_check_total, 2) == 0.0, f"Balance-sheet check total not zero in {organization_id}: {balance_check_total}"

    revenues_total = float(report["revenues_expenses"]["revenues"]["total"])
    expenses_total = float(report["revenues_expenses"]["expenses"]["total"])
    result_total = float(report["revenues_expenses"]["result"]["total"])
    assert round(revenues_total - expenses_total, 2) == round(result_total, 2), (
        f"Income statement mismatch in {organization_id}: revenues-expenses={revenues_total - expenses_total}, result={result_total}"
    )

    receipts_total = float(report["receipts_payments"]["receipts"]["total"])
    payments_total = float(report["receipts_payments"]["payments"]["total"])
    net_cash_total = float(report["receipts_payments"]["net_cash_flow"]["total"])
    assert round(receipts_total - payments_total, 2) == round(net_cash_total, 2), (
        f"Cash flow mismatch in {organization_id}: receipts-payments={receipts_total - payments_total}, net={net_cash_total}"
    )


@pytest.mark.parametrize("organization_id", ORG_IDS)
def test_trial_balance_balanced_and_ledger_matches_all_movement_accounts(
    base_url: str,
    session: requests.Session,
    org_headers: Dict[str, Dict[str, str]],
    organization_id: str,
):
    headers = org_headers[organization_id]
    trial = _fetch_trial_balance(base_url, session, headers)

    total_debit = round(float(trial.get("total_debit") or 0), 2)
    total_credit = round(float(trial.get("total_credit") or 0), 2)
    assert trial.get("is_balanced") is True, f"Trial balance not balanced for {organization_id}"
    assert total_debit == total_credit, (
        f"Trial totals mismatch for {organization_id}: debit={total_debit}, credit={total_credit}"
    )

    rows = trial.get("rows", [])
    rows_with_movement = [
        row
        for row in rows
        if round(float(row.get("total_debit") or 0), 2) != 0 or round(float(row.get("total_credit") or 0), 2) != 0
    ]

    mismatches = []
    for row in rows_with_movement:
        account_id = row.get("account_id")
        account_code = row.get("account_code")
        if not account_id and not account_code:
            mismatches.append(
                {
                    "account_name": row.get("account_name"),
                    "issue": "movement row has no account_id/account_code",
                }
            )
            continue

        params = {"from_date": PERIOD_FROM, "to_date": PERIOD_TO}
        if account_id:
            params["account_id"] = account_id
        else:
            params["account_code"] = account_code

        ledger_resp = session.get(f"{base_url}/api/ledger", headers=headers, params=params, timeout=90)
        if ledger_resp.status_code != 200:
            mismatches.append(
                {
                    "account_name": row.get("account_name"),
                    "account_id": account_id,
                    "account_code": account_code,
                    "issue": f"ledger endpoint returned {ledger_resp.status_code}",
                }
            )
            continue

        ledger = ledger_resp.json()
        ledger_debit = round(float(ledger.get("total_debit") or 0), 2)
        ledger_credit = round(float(ledger.get("total_credit") or 0), 2)
        trial_debit = round(float(row.get("total_debit") or 0), 2)
        trial_credit = round(float(row.get("total_credit") or 0), 2)

        if ledger_debit != trial_debit or ledger_credit != trial_credit:
            mismatches.append(
                {
                    "account_name": row.get("account_name"),
                    "account_id": account_id,
                    "account_code": account_code,
                    "trial_debit": trial_debit,
                    "trial_credit": trial_credit,
                    "ledger_debit": ledger_debit,
                    "ledger_credit": ledger_credit,
                }
            )

    assert not mismatches, f"Ledger vs trial mismatches/orphans in {organization_id}: {mismatches[:10]}"
