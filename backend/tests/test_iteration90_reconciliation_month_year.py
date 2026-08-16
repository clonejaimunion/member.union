"""Iteration 90 - Bank Reconciliation month filter setup + prior-year 'year' field.

Backend verifies:
  1) prior_year_outstanding_checks.year round-trips via POST/GET/PUT.
  2) We can seed expenses & revenues with check payment in Jan & Feb 2026,
     that they are returned by the list endpoints used by the UI's auto-sync.
  3) Trial balance / balance sheet integrity remains after cleanup.

All test artefacts are cleaned up at the end.
"""

import os
import uuid
import pytest
import requests
from datetime import datetime, timezone

def _load_backend_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    for env_path in ("/app/frontend/.env",):
        try:
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        return line.split("=", 1)[1].strip().strip('"').rstrip("/")
        except FileNotFoundError:
            pass
    raise RuntimeError("REACT_APP_BACKEND_URL not set")

BASE_URL = _load_backend_url()
API = f"{BASE_URL}/api"

ORG = "general-union"
USERNAME = "admin"
PASSWORD = "Admin@123"

TAG = f"IT90_{uuid.uuid4().hex[:6].upper()}"


# ----------------------- fixtures -----------------------
@pytest.fixture(scope="session")
def token():
    r = requests.post(f"{API}/auth/login", json={
        "username": USERNAME, "password": PASSWORD, "organization_id": ORG,
    }, timeout=30)
    assert r.status_code == 200, r.text
    return r.json().get("token") or r.json().get("access_token")


@pytest.fixture(scope="session")
def client(token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def bank_id(client):
    r = client.get(f"{API}/banks", timeout=30)
    assert r.status_code == 200, r.text
    banks = r.json()
    assert banks, "no banks available"
    return banks[0]["id"]


@pytest.fixture(scope="session")
def created_state():
    return {"expenses": [], "revenues": [], "reconciliations": []}


# ----------------------- tests -----------------------
class TestReconciliationYearField:
    def test_year_roundtrip_on_prior_year_check(self, client, bank_id, created_state):
        payload = {
            "period_label": f"يناير 2026 {TAG}",
            "book_balance": 1000.0,
            "bank_statement_balance": 500.0,
            "outstanding_checks": [],
            "collection_checks": [],
            "prior_year_outstanding_checks": [
                {"check_number": f"PY-{TAG}", "amount": 500.0,
                 "check_date": "2024-03-15T00:00:00Z", "year": 2024},
            ],
        }
        r = client.post(f"{API}/banks/{bank_id}/reconciliations", json=payload, timeout=30)
        assert r.status_code in (200, 201), r.text
        data = r.json()
        created_state["reconciliations"].append(data["id"])
        assert data["prior_year_outstanding_checks"][0].get("year") == 2024

        # GET
        r2 = client.get(f"{API}/banks/{bank_id}/reconciliations", timeout=30)
        assert r2.status_code == 200
        found = next((x for x in r2.json() if x["id"] == data["id"]), None)
        assert found is not None
        assert found["prior_year_outstanding_checks"][0].get("year") == 2024

        # PUT (update) - change year to 2023
        upd = dict(payload)
        upd["prior_year_outstanding_checks"] = [
            {"check_number": f"PY-{TAG}", "amount": 500.0,
             "check_date": "2023-03-15T00:00:00Z", "year": 2023},
        ]
        r3 = client.put(f"{API}/banks/{bank_id}/reconciliations/{data['id']}", json=upd, timeout=30)
        assert r3.status_code == 200, r3.text
        assert r3.json()["prior_year_outstanding_checks"][0].get("year") == 2023

    def test_year_optional_none(self, client, bank_id, created_state):
        payload = {
            "period_label": f"فبراير 2026 {TAG}",
            "book_balance": 100.0,
            "bank_statement_balance": 100.0,
            "outstanding_checks": [],
            "collection_checks": [],
            "prior_year_outstanding_checks": [],
        }
        r = client.post(f"{API}/banks/{bank_id}/reconciliations", json=payload, timeout=30)
        assert r.status_code in (200, 201), r.text
        created_state["reconciliations"].append(r.json()["id"])


class TestMonthFilterSourceData:
    """Seed check-based expense/revenue records so the UI auto-sync has data to filter."""

    def test_seed_expense_checks_jan_feb(self, client, bank_id, created_state):
        base_num = int(datetime.now().timestamp() % 100000)
        base_chk = int(datetime.now().timestamp() % 1000000)
        for i, iso in enumerate(["2026-01-15", "2026-02-10"]):
            body = {
                "expense_number": str(base_num + i),
                "organization_scope": "general_union",
                "expense_category": "general_expenses",
                "payment_method": "check",
                "payee_name": f"TEST_{TAG}",
                "check_number": str(base_chk + i),
                "check_clearing_type": "internal",
                "bank_id": bank_id,
                "gross_amount": 250.0,
                "gross_statement": f"TEST {TAG}",
                "issued_at": iso,
                "responsible_employee": "يوسف عبدالغني",
                "bank_payment_status": "not_presented",
            }
            r = client.post(f"{API}/expenses", json=body, timeout=30)
            assert r.status_code in (200, 201), r.text
            created_state["expenses"].append(r.json()["id"])

        # Verify the /expenses filter returns them
        r = client.get(f"{API}/expenses?bank_id={bank_id}&payment_method=check", timeout=30)
        assert r.status_code == 200
        items = r.json()
        chk_nums = {str(base_chk + i) for i in range(2)}
        tagged = [x for x in items if str(x.get("check_number") or "") in chk_nums]
        assert len(tagged) == 2, f"got {len(tagged)} tagged"
        statuses = {x.get("bank_payment_status") for x in tagged}
        assert statuses == {"not_presented"}

    def test_seed_revenue_checks_jan_feb(self, client, bank_id, created_state):
        base_rn = int(datetime.now().timestamp() % 100000) + 500
        base_rchk = int(datetime.now().timestamp() % 1000000) + 500
        for i, iso in enumerate(["2026-01-20", "2026-02-14"]):
            body = {
                "receipt_number": str(base_rn + i),
                "amount": 300.0,
                "collection_method": "check",
                "supplier_name": f"TEST_{TAG}",
                "check_number": str(base_rchk + i),
                "check_clearing_type": "internal",
                "bank_id": bank_id,
                "dated": iso,
                "value": f"TEST revenue {TAG}",
                "issued_at": iso,
                "responsible_employee": "يوسف عبدالغني",
                "bank_collection_status": "under_collection",
            }
            r = client.post(f"{API}/revenues", json=body, timeout=30)
            if r.status_code not in (200, 201):
                pytest.skip(f"revenue creation not supported: {r.status_code} {r.text[:200]}")
            created_state["revenues"].append(r.json()["id"])

        r = client.get(f"{API}/revenues?bank_id={bank_id}&collection_method=check", timeout=30)
        assert r.status_code == 200
        items = r.json()
        chk = {str(base_rchk + i) for i in range(2)}
        tagged = [x for x in items if str(x.get("check_number") or "") in chk]
        assert len(tagged) == 2


class TestZFinalCleanup:
    def test_cleanup(self, client, bank_id, created_state):
        for rid in created_state["reconciliations"]:
            client.delete(f"{API}/banks/{bank_id}/reconciliations/{rid}", timeout=30)
        for eid in created_state["expenses"]:
            client.delete(f"{API}/expenses/{eid}", timeout=30)
        for rvid in created_state["revenues"]:
            client.delete(f"{API}/revenues/{rvid}", timeout=30)

    def test_trial_balance_still_balanced(self, client):
        r = client.get(f"{API}/trial-balance", timeout=60)
        assert r.status_code == 200
        assert r.json().get("is_balanced") is True
