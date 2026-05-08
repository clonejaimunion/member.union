"""Inventory + Misc Creditors accounting flow regression tests (public URL)."""

import uuid
from datetime import date
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient


def _env_value(key: str, *env_files: str):
    value = None
    for env_file in env_files:
        data = dotenv_values(env_file)
        value = data.get(key) or value
    return value


BASE_URL = (
    __import__("os").environ.get("REACT_APP_BACKEND_URL")
    or _env_value("REACT_APP_BACKEND_URL", "/app/frontend/.env")
)
MONGO_URL = __import__("os").environ.get("MONGO_URL") or _env_value("MONGO_URL", "/app/backend/.env")
DB_NAME = __import__("os").environ.get("DB_NAME") or _env_value("DB_NAME", "/app/backend/.env")

ORG_ID = "social-solidarity"
USERNAME = "admin"
PASSWORD = "Admin@123"
BANK_ID = "industrial-development"

RUN_PREFIX = f"TEST-ITER72-{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
def api_client():
    assert BASE_URL, "REACT_APP_BACKEND_URL is required"
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def auth_headers(api_client):
    response = api_client.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": USERNAME, "password": PASSWORD, "organization_id": ORG_ID},
        timeout=30,
    )
    assert response.status_code == 200, f"Login failed: {response.status_code} {response.text}"
    data = response.json()
    token = data.get("token")
    assert token and isinstance(token, str)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module", autouse=True)
def cleanup_test_data():
    yield
    if not MONGO_URL or not DB_NAME:
        return

    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]

    q_ref = {"organization_id": ORG_ID, "reference": {"$regex": f"^{RUN_PREFIX}"}}
    q_inventory_item = {"organization_id": ORG_ID, "item_code": {"$regex": f"^{RUN_PREFIX}"}}
    q_misc_creditor = {"organization_id": ORG_ID, "creditor_name": {"$regex": f"^{RUN_PREFIX}"}}

    db.journal_entries.delete_many(q_ref)
    db.inventory_movements.delete_many(q_ref)
    db.misc_creditor_movements.delete_many(q_ref)
    db.inventory_items.delete_many(q_inventory_item)
    db.misc_creditors.delete_many(q_misc_creditor)

    client.close()


@pytest.fixture(scope="module")
def inventory_flow(api_client, auth_headers):
    ref_in = f"{RUN_PREFIX}-INV-IN"
    payload_in = {
        "movement_date": date.today().isoformat(),
        "item_code": f"{RUN_PREFIX}-ITEM-01",
        "item_name": f"{RUN_PREFIX} صنف اختبار",
        "unit": "وحدة",
        "movement_type": "in",
        "quantity": 10,
        "unit_cost": 25,
        "description": f"{RUN_PREFIX} وارد مخزون",
        "reference": ref_in,
    }
    response_in = api_client.post(
        f"{BASE_URL}/api/inventory/movements", json=payload_in, headers=auth_headers, timeout=30
    )
    assert response_in.status_code == 200, response_in.text
    movement_in = response_in.json()

    ref_out = f"{RUN_PREFIX}-INV-OUT"
    payload_out = {
        "movement_date": date.today().isoformat(),
        "item_id": movement_in["item_id"],
        "movement_type": "out",
        "quantity": 3,
        "description": f"{RUN_PREFIX} منصرف مخزون",
        "reference": ref_out,
    }
    response_out = api_client.post(
        f"{BASE_URL}/api/inventory/movements", json=payload_out, headers=auth_headers, timeout=30
    )
    assert response_out.status_code == 200, response_out.text
    movement_out = response_out.json()

    return {"in": movement_in, "out": movement_out, "ref_in": ref_in, "ref_out": ref_out}


@pytest.fixture(scope="module")
def misc_creditor_flow(api_client, auth_headers):
    ref_obligation = f"{RUN_PREFIX}-MC-OBL"
    payload_obligation = {
        "movement_date": date.today().isoformat(),
        "creditor_name": f"{RUN_PREFIX} دائن اختبار",
        "movement_type": "obligation",
        "amount": 300,
        "description": f"{RUN_PREFIX} إثبات التزام",
        "reference": ref_obligation,
    }
    response_obligation = api_client.post(
        f"{BASE_URL}/api/misc-creditors/movements", json=payload_obligation, headers=auth_headers, timeout=30
    )
    assert response_obligation.status_code == 200, response_obligation.text
    movement_obligation = response_obligation.json()

    ref_payment = f"{RUN_PREFIX}-MC-PAY"
    payload_payment = {
        "movement_date": date.today().isoformat(),
        "creditor_id": movement_obligation["creditor_id"],
        "movement_type": "payment",
        "amount": 120,
        "bank_id": BANK_ID,
        "description": f"{RUN_PREFIX} سداد جزئي",
        "reference": ref_payment,
    }
    response_payment = api_client.post(
        f"{BASE_URL}/api/misc-creditors/movements", json=payload_payment, headers=auth_headers, timeout=30
    )
    assert response_payment.status_code == 200, response_payment.text
    movement_payment = response_payment.json()

    return {
        "obligation": movement_obligation,
        "payment": movement_payment,
        "ref_obligation": ref_obligation,
        "ref_payment": ref_payment,
    }


# Inventory + item/movement APIs + auto journal
def test_inventory_in_and_out_create_balances_and_journals(api_client, auth_headers, inventory_flow):
    movement_in = inventory_flow["in"]
    movement_out = inventory_flow["out"]

    assert movement_in["movement_type"] == "in"
    assert movement_in["quantity_balance_after"] == 10
    assert movement_in["value_balance_after"] == 250
    assert movement_in["journal_entry_id"]

    assert movement_out["movement_type"] == "out"
    assert movement_out["quantity_balance_after"] == 7
    assert movement_out["value_balance_after"] == 175
    assert movement_out["journal_entry_id"]

    items_response = api_client.get(f"{BASE_URL}/api/inventory/items", headers=auth_headers, timeout=30)
    assert items_response.status_code == 200
    items = items_response.json()
    item = next((it for it in items if it["id"] == movement_in["item_id"]), None)
    assert item is not None
    assert "_id" not in item
    assert item["quantity_balance"] == 7
    assert item["value_balance"] == 175


def test_inventory_out_rejects_when_quantity_exceeds_available(api_client, auth_headers, inventory_flow):
    response = api_client.post(
        f"{BASE_URL}/api/inventory/movements",
        json={
            "movement_date": date.today().isoformat(),
            "item_id": inventory_flow["in"]["item_id"],
            "movement_type": "out",
            "quantity": 9999,
            "description": f"{RUN_PREFIX} منصرف أكبر من الرصيد",
            "reference": f"{RUN_PREFIX}-INV-OVR",
        },
        headers=auth_headers,
        timeout=30,
    )
    assert response.status_code == 400
    assert "رصيد" in response.json().get("detail", "")


def test_inventory_movements_filters_and_json_shape(api_client, auth_headers, inventory_flow):
    item_id = inventory_flow["in"]["item_id"]
    response = api_client.get(
        f"{BASE_URL}/api/inventory/movements",
        params={"item_id": item_id, "from_date": date.today().isoformat(), "to_date": date.today().isoformat()},
        headers=auth_headers,
        timeout=30,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2
    assert all(row["item_id"] == item_id for row in data)
    assert all("_id" not in row for row in data)


# Misc creditors movement APIs + auto journal
def test_misc_creditor_obligation_and_payment_update_balance_and_journals(api_client, auth_headers, misc_creditor_flow):
    obligation = misc_creditor_flow["obligation"]
    payment = misc_creditor_flow["payment"]

    assert obligation["movement_type"] == "obligation"
    assert obligation["amount"] == 300
    assert obligation["balance_after"] == 300
    assert obligation["journal_entry_id"]

    assert payment["movement_type"] == "payment"
    assert payment["amount"] == 120
    assert payment["balance_after"] == 180
    assert payment["bank_id"] == BANK_ID
    assert payment["journal_entry_id"]

    creditors_response = api_client.get(f"{BASE_URL}/api/misc-creditors", headers=auth_headers, timeout=30)
    assert creditors_response.status_code == 200
    creditors = creditors_response.json()
    creditor = next((c for c in creditors if c["id"] == obligation["creditor_id"]), None)
    assert creditor is not None
    assert "_id" not in creditor
    assert creditor["balance"] == 180


def test_misc_creditor_payment_requires_bank_id(api_client, auth_headers, misc_creditor_flow):
    response = api_client.post(
        f"{BASE_URL}/api/misc-creditors/movements",
        json={
            "movement_date": date.today().isoformat(),
            "creditor_id": misc_creditor_flow["obligation"]["creditor_id"],
            "movement_type": "payment",
            "amount": 10,
            "description": f"{RUN_PREFIX} سداد بدون بنك",
            "reference": f"{RUN_PREFIX}-MC-NOBANK",
        },
        headers=auth_headers,
        timeout=30,
    )
    assert response.status_code == 400
    assert "البنك" in response.json().get("detail", "")


def test_misc_creditor_payment_rejects_if_greater_than_balance(api_client, auth_headers, misc_creditor_flow):
    response = api_client.post(
        f"{BASE_URL}/api/misc-creditors/movements",
        json={
            "movement_date": date.today().isoformat(),
            "creditor_id": misc_creditor_flow["obligation"]["creditor_id"],
            "movement_type": "payment",
            "amount": 9999,
            "bank_id": BANK_ID,
            "description": f"{RUN_PREFIX} سداد أكبر من الرصيد",
            "reference": f"{RUN_PREFIX}-MC-OVR",
        },
        headers=auth_headers,
        timeout=30,
    )
    assert response.status_code == 400
    assert "أكبر" in response.json().get("detail", "")


# Journal filtering + approved status + classifications
def test_journal_entry_filters_for_inventory_and_misc_creditors(api_client, auth_headers, inventory_flow, misc_creditor_flow):
    inv_response = api_client.get(
        f"{BASE_URL}/api/journal-entries",
        params={"entry_category": "inventory", "entry_item": RUN_PREFIX},
        headers=auth_headers,
        timeout=30,
    )
    assert inv_response.status_code == 200
    inv_entries = inv_response.json()
    assert len(inv_entries) >= 2
    assert all(entry["source_type"] == "inventory" for entry in inv_entries)
    assert all(entry["status"] == "approved" for entry in inv_entries)

    misc_response = api_client.get(
        f"{BASE_URL}/api/journal-entries",
        params={"entry_category": "misc_creditors", "entry_item": RUN_PREFIX},
        headers=auth_headers,
        timeout=30,
    )
    assert misc_response.status_code == 200
    misc_entries = misc_response.json()
    assert len(misc_entries) >= 2
    assert all(entry["source_type"] == "misc_creditor" for entry in misc_entries)
    assert all(entry["status"] == "approved" for entry in misc_entries)


def test_trial_balance_and_data_flow_validation_after_transactions(api_client, auth_headers):
    tb_response = api_client.get(
        f"{BASE_URL}/api/trial-balance",
        params={"non_zero_only": "true"},
        headers=auth_headers,
        timeout=30,
    )
    assert tb_response.status_code == 200
    tb = tb_response.json()

    inventory_row = next((row for row in tb.get("rows", []) if row.get("account_name") == "المخزون"), None)
    misc_row = next((row for row in tb.get("rows", []) if row.get("account_name") == "دائنون متنوعون"), None)
    assert inventory_row is not None
    assert inventory_row.get("account_type") == "asset"
    assert misc_row is not None
    assert misc_row.get("account_type") == "liability"

    assert all(row.get("account_code") != "1250" for row in tb.get("rows", []))

    validation_response = api_client.get(
        f"{BASE_URL}/api/admin/data-flow-validation", headers=auth_headers, timeout=30
    )
    assert validation_response.status_code == 200
    validation = validation_response.json()
    assert validation.get("is_valid") is True
    assert any(org.get("accounting", {}).get("is_valid") for org in validation.get("organizations", []))
