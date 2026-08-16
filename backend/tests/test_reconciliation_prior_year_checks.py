"""Tests for the new 'prior_year_collection_checks' field on bank reconciliations."""
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://invoke-app.preview.emergentagent.com").rstrip("/")
ORG_ID = "social-solidarity"
BANK_ID = "industrial-development"


@pytest.fixture(scope="module")
def token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": "admin", "password": "Admin@123", "organization_id": ORG_ID},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _payload():
    return {
        "period_label": "TEST_PRIOR_YEAR",
        "administration": "TEST",
        "book_balance": 0.0,  # server overrides
        "bank_statement_balance": 1000.0,
        "outstanding_checks": [],
        "collection_checks": [
            {"check_number": "C-CUR-1", "amount": 250.0, "check_date": "2026-01-15T00:00:00"}
        ],
        "prior_year_collection_checks": [
            {"check_number": "PY-01", "amount": 100.0, "check_date": "2025-03-10T00:00:00"},
            {"check_number": "PY-02", "amount": 50.5, "check_date": "2024-06-01T00:00:00"},
        ],
    }


def test_full_prior_year_flow(headers):
    created_ids = []
    try:
        # ---- CREATE ----
        r = requests.post(
            f"{BASE_URL}/api/banks/{BANK_ID}/reconciliations",
            headers=headers, json=_payload(), timeout=30,
        )
        assert r.status_code == 200, r.text
        rec = r.json()
        rec_id = rec["id"]
        created_ids.append(rec_id)

        assert len(rec["prior_year_collection_checks"]) == 2
        assert rec["total_prior_year_collection_checks"] == 150.5
        # total_collection = collection (250) + prior_year (150.5)
        assert rec["total_collection_checks"] == 400.5
        # persistence of numbers
        nums = {c["check_number"] for c in rec["prior_year_collection_checks"]}
        assert nums == {"PY-01", "PY-02"}

        # ---- GET (hydrate) ----
        r = requests.get(f"{BASE_URL}/api/banks/{BANK_ID}/reconciliations/{rec_id}", headers=headers, timeout=30)
        assert r.status_code == 200
        got = r.json()
        assert got["total_prior_year_collection_checks"] == 150.5
        assert len(got["prior_year_collection_checks"]) == 2
        # check_date is parsed to a valid ISO date
        for c in got["prior_year_collection_checks"]:
            assert "check_date" in c and c["check_date"]

        # ---- Trial balance / financial statement still balanced ----
        tb = requests.get(f"{BASE_URL}/api/trial-balance", headers=headers, timeout=30)
        assert tb.status_code == 200
        assert tb.json().get("is_balanced") is True, tb.json()

        fs = requests.get(f"{BASE_URL}/api/financial-statements", headers=headers, timeout=30)
        assert fs.status_code == 200
        check = fs.json().get("balance_sheet", {}).get("check", {})
        assert check.get("total") == 0.0, check

        # ---- UPDATE: modify prior_year list (remove one, add one) ----
        upd = _payload()
        upd["prior_year_collection_checks"] = [
            {"check_number": "PY-01", "amount": 100.0, "check_date": "2025-03-10T00:00:00"},
            {"check_number": "PY-03", "amount": 25.25, "check_date": "2023-12-31T00:00:00"},
        ]
        r = requests.put(
            f"{BASE_URL}/api/banks/{BANK_ID}/reconciliations/{rec_id}",
            headers=headers, json=upd, timeout=30,
        )
        assert r.status_code == 200, r.text
        upd_rec = r.json()
        assert upd_rec["total_prior_year_collection_checks"] == 125.25
        assert upd_rec["total_collection_checks"] == 375.25
        nums2 = {c["check_number"] for c in upd_rec["prior_year_collection_checks"]}
        assert nums2 == {"PY-01", "PY-03"}

        # journal side effect: only reconciliation source, not per-check
        j = requests.get(f"{BASE_URL}/api/journal-entries", headers=headers, timeout=30)
        assert j.status_code == 200
        entries = j.json() if isinstance(j.json(), list) else j.json().get("items", [])
        recon_entries = [e for e in entries if e.get("source_type") == "reconciliation" and e.get("source_id") == rec_id]
        # At most one auto entry for this reconciliation (0 if difference is 0)
        assert len(recon_entries) <= 1

    finally:
        # ---- DELETE cleanup ----
        for rid in created_ids:
            d = requests.delete(f"{BASE_URL}/api/banks/{BANK_ID}/reconciliations/{rid}", headers=headers, timeout=30)
            assert d.status_code in (200, 204), d.text
            g = requests.get(f"{BASE_URL}/api/banks/{BANK_ID}/reconciliations/{rid}", headers=headers, timeout=30)
            assert g.status_code == 404

        # verify still balanced after cleanup
        tb2 = requests.get(f"{BASE_URL}/api/trial-balance", headers=headers, timeout=30)
        assert tb2.status_code == 200 and tb2.json().get("is_balanced") is True
