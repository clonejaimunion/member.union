"""Iteration 91 - Year field on outstanding_checks / collection_checks / prior_year_outstanding_checks.

Verifies POST/GET/PUT round-trip for the new `year` field on all 3 lists.
"""
import os
import uuid
import pytest
import requests


def _load_backend_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    with open("/app/frontend/.env") as f:
        for line in f:
            line = line.strip()
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().strip('"').rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not set")


BASE_URL = _load_backend_url()
API = f"{BASE_URL}/api"
TAG = f"IT91_{uuid.uuid4().hex[:6].upper()}"


@pytest.fixture(scope="module")
def client():
    r = requests.post(f"{API}/auth/login", json={
        "username": "admin", "password": "Admin@123", "organization_id": "general-union",
    }, timeout=30)
    assert r.status_code == 200, r.text
    tok = r.json().get("token") or r.json().get("access_token")
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def bank_id(client):
    r = client.get(f"{API}/banks", timeout=30)
    assert r.status_code == 200
    return r.json()[0]["id"]


@pytest.fixture(scope="module")
def created():
    return {"reconciliations": []}


class TestYearAllLists:
    def test_year_roundtrip_all_three_lists(self, client, bank_id, created):
        payload = {
            "period_label": f"يناير 2026 {TAG}",
            "book_balance": 1000.0,
            "bank_statement_balance": 500.0,
            "outstanding_checks": [
                {"check_number": f"O-{TAG}", "amount": 100.0,
                 "check_date": "2026-01-20T00:00:00", "year": 2026},
            ],
            "collection_checks": [
                {"check_number": f"C-{TAG}", "amount": 200.0,
                 "check_date": "2026-01-25T00:00:00", "year": 2026},
            ],
            "prior_year_outstanding_checks": [
                {"check_number": f"P-{TAG}", "amount": 300.0,
                 "check_date": "2024-03-15T00:00:00", "year": 2024},
            ],
        }
        r = client.post(f"{API}/banks/{bank_id}/reconciliations", json=payload, timeout=30)
        assert r.status_code in (200, 201), r.text
        data = r.json()
        created["reconciliations"].append(data["id"])

        assert data["outstanding_checks"][0].get("year") == 2026
        assert data["collection_checks"][0].get("year") == 2026
        assert data["prior_year_outstanding_checks"][0].get("year") == 2024

        # GET
        r2 = client.get(f"{API}/banks/{bank_id}/reconciliations", timeout=30)
        assert r2.status_code == 200
        found = next(x for x in r2.json() if x["id"] == data["id"])
        assert found["outstanding_checks"][0].get("year") == 2026
        assert found["collection_checks"][0].get("year") == 2026
        assert found["prior_year_outstanding_checks"][0].get("year") == 2024

        # PUT - update outstanding year to 2025, keep others
        upd = dict(payload)
        upd["outstanding_checks"] = [
            {"check_number": f"O-{TAG}", "amount": 100.0,
             "check_date": "2025-12-30T00:00:00", "year": 2025},
        ]
        r3 = client.put(f"{API}/banks/{bank_id}/reconciliations/{data['id']}", json=upd, timeout=30)
        assert r3.status_code == 200, r3.text
        j3 = r3.json()
        assert j3["outstanding_checks"][0].get("year") == 2025
        assert j3["collection_checks"][0].get("year") == 2026
        assert j3["prior_year_outstanding_checks"][0].get("year") == 2024

    def test_year_optional(self, client, bank_id, created):
        payload = {
            "period_label": f"opt {TAG}",
            "book_balance": 0.0,
            "bank_statement_balance": 0.0,
            "outstanding_checks": [
                {"check_number": f"N-{TAG}", "amount": 5.0,
                 "check_date": "2026-01-20T00:00:00"},
            ],
        }
        r = client.post(f"{API}/banks/{bank_id}/reconciliations", json=payload, timeout=30)
        assert r.status_code in (200, 201), r.text
        created["reconciliations"].append(r.json()["id"])
        assert r.json()["outstanding_checks"][0].get("year") in (None, 0)


class TestZCleanup:
    def test_cleanup(self, client, bank_id, created):
        for rid in created["reconciliations"]:
            client.delete(f"{API}/banks/{bank_id}/reconciliations/{rid}", timeout=30)
