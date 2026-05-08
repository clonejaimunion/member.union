import os
import uuid

import pytest
import requests
from dotenv import dotenv_values


# Bank prints module: external fetch, pre-print request archive, status updates, and read-only side-effect checks.
FRONTEND_ENV = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or FRONTEND_ENV.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
ORG_ID = "social-solidarity"
BANK_ID = "banque-misr"
TEST_NOTE = "TEST_AUTOMATION_BANK_PRINT_DELETE_ME"


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
    token = response.json().get("token")
    if not token:
        pytest.skip("admin token missing")
    return token


@pytest.fixture(scope="module")
def snapshot_counts(base_url, admin_token):
    journal_response = requests.get(
        f"{base_url}/api/journal-entries",
        headers=_headers(admin_token),
        timeout=90,
    )
    assert journal_response.status_code == 200, journal_response.text
    journals = journal_response.json()

    reconciliation_response = requests.get(
        f"{base_url}/api/banks/{BANK_ID}/reconciliations",
        headers=_headers(admin_token),
        timeout=90,
    )
    assert reconciliation_response.status_code == 200, reconciliation_response.text
    reconciliations = reconciliation_response.json()

    banks_response = requests.get(
        f"{base_url}/api/banks",
        headers=_headers(admin_token),
        timeout=90,
    )
    assert banks_response.status_code == 200, banks_response.text
    banks = banks_response.json()
    banque_misr = next((bank for bank in banks if bank.get("id") == BANK_ID), None)
    assert banque_misr is not None

    return {
        "journal_count": len(journals),
        "reconciliation_count": len(reconciliations),
        "banque_misr_opening_balance": float(banque_misr.get("opening_balance") or 0),
        "banque_misr_opening_balance_date": banque_misr.get("opening_balance_date"),
    }


def test_external_data_fetch_returns_real_source_shape(base_url, admin_token):
    response = requests.get(
        f"{base_url}/api/bank-prints/banque-misr/external-data",
        headers=_headers(admin_token),
        timeout=120,
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["bank_id"] == BANK_ID
    assert body["source_url"] == "https://www.banquemisr.ae/#tab-2"
    assert body["status"] in ["OK", "NO_DATA"]
    assert isinstance(body["rows"], list)
    assert isinstance(body["checksum"], str)
    assert len(body["checksum"]) == 64
    assert isinstance(body["fetched_at"], str)
    # Real external fetch should produce non-empty rows under normal conditions.
    assert len(body["rows"]) > 0


def test_create_request_saves_before_print_and_embeds_external_and_manual(base_url, admin_token):
    unique_suffix = uuid.uuid4().hex[:8]
    manual_inputs = {
        "bank_notes": f"{TEST_NOTE}::{unique_suffix}",
        "checks_or_settlements_numbers": "CHK-1001",
        "descriptive_adjustments": "Automation pre-print adjustment",
        "period_from": "2026-01-01",
        "period_to": "2026-01-31",
        "internal_approver_name": "QA Automation",
        "internal_signature": "QA-SIGN",
        "approval_code": f"APR-{unique_suffix}",
    }

    create_response = requests.post(
        f"{base_url}/api/bank-prints/banque-misr/requests",
        json={"manual_inputs": manual_inputs},
        headers=_headers(admin_token),
        timeout=120,
    )
    assert create_response.status_code == 200, create_response.text
    created = create_response.json()

    assert isinstance(created.get("id"), str) and len(created["id"]) > 0
    assert created["bank_id"] == BANK_ID
    assert created["status"] == "saved_before_print"
    assert created["manual_inputs"]["bank_notes"] == manual_inputs["bank_notes"]
    assert created["external_data"]["source_url"] == "https://www.banquemisr.ae/#tab-2"
    assert isinstance(created["external_data"]["rows"], list)

    archive_response = requests.get(
        f"{base_url}/api/bank-prints/requests",
        params={"bank_id": BANK_ID},
        headers=_headers(admin_token),
        timeout=90,
    )
    assert archive_response.status_code == 200, archive_response.text
    archive = archive_response.json()
    archived = next((item for item in archive if item.get("id") == created["id"]), None)
    assert archived is not None
    assert archived["manual_inputs"]["bank_notes"] == manual_inputs["bank_notes"]

    get_response = requests.get(
        f"{base_url}/api/bank-prints/requests/{created['id']}",
        headers=_headers(admin_token),
        timeout=90,
    )
    assert get_response.status_code == 200, get_response.text
    fetched = get_response.json()
    assert fetched["id"] == created["id"]
    assert fetched["manual_inputs"]["bank_notes"] == manual_inputs["bank_notes"]
    assert fetched["external_data"]["source_url"] == "https://www.banquemisr.ae/#tab-2"


def test_patch_status_printed_then_cancelled_updates_fields(base_url, admin_token):
    create_response = requests.post(
        f"{base_url}/api/bank-prints/banque-misr/requests",
        json={
            "manual_inputs": {
                "bank_notes": f"{TEST_NOTE}::status-flow",
                "checks_or_settlements_numbers": "CHK-2002",
                "descriptive_adjustments": "status update check",
                "period_from": "2026-02-01",
                "period_to": "2026-02-28",
                "internal_approver_name": "QA",
                "internal_signature": "SIG",
                "approval_code": "APR-STATUS",
            }
        },
        headers=_headers(admin_token),
        timeout=120,
    )
    assert create_response.status_code == 200, create_response.text
    request_id = create_response.json()["id"]

    printed_response = requests.patch(
        f"{base_url}/api/bank-prints/requests/{request_id}/status",
        json={"status": "printed"},
        headers=_headers(admin_token),
        timeout=90,
    )
    assert printed_response.status_code == 200, printed_response.text
    printed = printed_response.json()
    assert printed["status"] == "printed"
    assert isinstance(printed.get("printed_at"), str) and len(printed["printed_at"]) > 0

    cancelled_response = requests.patch(
        f"{base_url}/api/bank-prints/requests/{request_id}/status",
        json={"status": "cancelled"},
        headers=_headers(admin_token),
        timeout=90,
    )
    assert cancelled_response.status_code == 200, cancelled_response.text
    cancelled = cancelled_response.json()
    assert cancelled["status"] == "cancelled"


def test_bank_print_endpoints_do_not_change_accounting_collections_or_balances(base_url, admin_token, snapshot_counts):
    requests.get(
        f"{base_url}/api/bank-prints/banque-misr/external-data",
        headers=_headers(admin_token),
        timeout=120,
    )
    requests.post(
        f"{base_url}/api/bank-prints/banque-misr/requests",
        json={
            "manual_inputs": {
                "bank_notes": f"{TEST_NOTE}::readonly-check",
                "checks_or_settlements_numbers": "CHK-3003",
                "descriptive_adjustments": "readonly verification",
                "period_from": "2026-03-01",
                "period_to": "2026-03-31",
                "internal_approver_name": "QA",
                "internal_signature": "SIG",
                "approval_code": "APR-RO",
            }
        },
        headers=_headers(admin_token),
        timeout=120,
    )

    journal_response = requests.get(
        f"{base_url}/api/journal-entries",
        headers=_headers(admin_token),
        timeout=90,
    )
    assert journal_response.status_code == 200, journal_response.text
    journals_after = journal_response.json()

    reconciliation_response = requests.get(
        f"{base_url}/api/banks/{BANK_ID}/reconciliations",
        headers=_headers(admin_token),
        timeout=90,
    )
    assert reconciliation_response.status_code == 200, reconciliation_response.text
    reconciliations_after = reconciliation_response.json()

    banks_response = requests.get(
        f"{base_url}/api/banks",
        headers=_headers(admin_token),
        timeout=90,
    )
    assert banks_response.status_code == 200, banks_response.text
    banks = banks_response.json()
    banque_misr_after = next((bank for bank in banks if bank.get("id") == BANK_ID), None)
    assert banque_misr_after is not None

    assert len(journals_after) == snapshot_counts["journal_count"]
    assert len(reconciliations_after) == snapshot_counts["reconciliation_count"]
    assert float(banque_misr_after.get("opening_balance") or 0) == snapshot_counts["banque_misr_opening_balance"]
    assert banque_misr_after.get("opening_balance_date") == snapshot_counts["banque_misr_opening_balance_date"]
