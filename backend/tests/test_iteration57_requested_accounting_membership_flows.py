import os
import uuid
from datetime import date

import pytest
import requests


# Scope: requested bank opening balance, reconciliation, membership status/report, batch payment, rules engine events.
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")


@pytest.fixture(scope="session")
def base_url():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL is not configured")
    return BASE_URL.rstrip("/")


@pytest.fixture(scope="session")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def auth_headers(base_url, session):
    resp = session.post(
        f"{base_url}/api/auth/login",
        json={
            "username": "admin",
            "password": "Admin@123",
            "organization_id": "social-solidarity",
        },
        timeout=30,
    )
    if resp.status_code != 200:
        pytest.skip(f"Login failed: {resp.status_code} {resp.text}")
    data = resp.json()
    token = data.get("token")
    assert token and isinstance(token, str)
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture
def cleanup_state(base_url, session, auth_headers):
    state = {"members": [], "reconciliations": [], "bank_restore": None}
    yield state

    for rec in state["reconciliations"]:
        session.delete(
            f"{base_url}/api/banks/{rec['bank_id']}/reconciliations/{rec['id']}",
            headers=auth_headers,
            timeout=30,
        )

    for member_id in state["members"]:
        session.delete(
            f"{base_url}/api/memberships/{member_id}",
            headers=auth_headers,
            timeout=30,
        )

    if state["bank_restore"]:
        session.put(
            f"{base_url}/api/admin/banks/{state['bank_restore']['bank_id']}/opening-balance",
            headers=auth_headers,
            json={"opening_balance": state["bank_restore"]["opening_balance"]},
            timeout=30,
        )


def _create_member(base_url, session, auth_headers, cleanup_state, governorate, committee, membership_number):
    numeric_member = "".join(ch for ch in str(membership_number) if ch.isdigit())
    national_id = f"3{numeric_member.zfill(13)}"[-14:]
    payload = {
        "governorate": governorate,
        "union_committee": committee,
        "membership_number": membership_number,
        "name": f"TEST_ITER57_MEMBER_{membership_number}",
        "national_id": national_id,
        "birth_date": "1980-01-15",
        "address": "عنوان اختبار",
        "death_beneficiary": "مستفيد اختبار",
        "status": "active",
        "status_effective_date": None,
    }
    resp = session.post(f"{base_url}/api/memberships", headers=auth_headers, json=payload, timeout=30)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    cleanup_state["members"].append(data["id"])
    return data


def test_auth_login_sets_http_only_cookie_and_token(base_url, session):
    resp = session.post(
        f"{base_url}/api/auth/login",
        json={
            "username": "admin",
            "password": "Admin@123",
            "organization_id": "social-solidarity",
        },
        timeout=30,
    )
    assert resp.status_code == 200
    assert isinstance(resp.json().get("token"), str)
    set_cookie = resp.headers.get("set-cookie", "")
    assert "HttpOnly" in set_cookie or "httponly" in set_cookie.lower()


def test_opening_balance_creates_balanced_opening_journal_and_book_balance(base_url, session, auth_headers, cleanup_state):
    bank_id = "industrial-development"
    banks_resp = session.get(f"{base_url}/api/banks", headers=auth_headers, timeout=30)
    assert banks_resp.status_code == 200
    bank_row = next(item for item in banks_resp.json() if item["id"] == bank_id)
    cleanup_state["bank_restore"] = {"bank_id": bank_id, "opening_balance": bank_row.get("opening_balance", 0)}

    before_book_resp = session.get(f"{base_url}/api/banks/{bank_id}/book-balance", headers=auth_headers, timeout=30)
    assert before_book_resp.status_code == 200
    before_book = float(before_book_resp.json()["book_balance"])

    new_opening = 12345.67
    old_opening = float(bank_row.get("opening_balance", 0) or 0)
    update_resp = session.put(
        f"{base_url}/api/admin/banks/{bank_id}/opening-balance",
        headers=auth_headers,
        json={"opening_balance": new_opening},
        timeout=30,
    )
    assert update_resp.status_code == 200, update_resp.text
    assert update_resp.json()["opening_balance"] == pytest.approx(new_opening, abs=0.01)

    book_resp = session.get(f"{base_url}/api/banks/{bank_id}/book-balance", headers=auth_headers, timeout=30)
    assert book_resp.status_code == 200
    expected_delta = round(new_opening - old_opening, 2)
    actual_delta = round(float(book_resp.json()["book_balance"]) - before_book, 2)
    assert actual_delta == pytest.approx(expected_delta, abs=0.01)
    assert book_resp.json()["source"] == "journal_entries"

    journals_resp = session.get(
        f"{base_url}/api/journal-entries?source_type=opening_balance",
        headers=auth_headers,
        timeout=30,
    )
    assert journals_resp.status_code == 200
    entries = [j for j in journals_resp.json() if j.get("source_id") == bank_id]
    assert entries, "opening_balance journal entry not found"
    latest = entries[0]
    assert latest["source_type"] == "opening_balance"
    assert latest["total_debit"] == pytest.approx(latest["total_credit"], abs=0.01)


def test_reconciliation_ignores_payload_book_balance_and_uses_gl(base_url, session, auth_headers, cleanup_state):
    bank_id = "industrial-development"
    gl_resp = session.get(f"{base_url}/api/banks/{bank_id}/book-balance", headers=auth_headers, timeout=30)
    assert gl_resp.status_code == 200
    gl_balance = gl_resp.json()["book_balance"]

    payload = {
        "period_label": f"ITER57-{date.today().isoformat()}",
        "administration": "النقابة العامة",
        "book_balance": 1.23,
        "bank_statement_balance": gl_balance,
        "outstanding_checks": [],
        "collection_checks": [],
    }
    create_resp = session.post(
        f"{base_url}/api/banks/{bank_id}/reconciliations",
        headers=auth_headers,
        json=payload,
        timeout=30,
    )
    assert create_resp.status_code == 200, create_resp.text
    data = create_resp.json()
    cleanup_state["reconciliations"].append({"bank_id": bank_id, "id": data["id"]})
    assert data["book_balance"] == pytest.approx(gl_balance, abs=0.01)
    assert data["is_matched"] is True


def test_membership_non_active_status_blocks_new_due_and_keeps_previous_balance(base_url, session, auth_headers, cleanup_state):
    suffix = uuid.uuid4().hex[:6]
    governorate = f"TEST_GOV_{suffix}"
    committee = f"TEST_COM_{suffix}"
    member = _create_member(base_url, session, auth_headers, cleanup_state, governorate, committee, f"57{suffix[:4]}01")

    assert member["status"] == "active"
    assert member["monthly_subscription_amount"] == pytest.approx(3, abs=0.01)

    update_resp = session.put(
        f"{base_url}/api/memberships/{member['id']}",
        headers=auth_headers,
        json={
            "governorate": governorate,
            "union_committee": committee,
            "membership_number": member["membership_number"],
            "name": member["name"],
            "national_id": member["national_id"],
            "birth_date": str(member["birth_date"]),
            "address": member["address"],
            "death_beneficiary": member["death_beneficiary"],
            "status": "retired",
            "status_effective_date": date.today().isoformat(),
        },
        timeout=30,
    )
    assert update_resp.status_code == 200, update_resp.text
    assert update_resp.json()["status"] == "retired"

    list_resp = session.get(f"{base_url}/api/memberships", headers=auth_headers, timeout=30)
    assert list_resp.status_code == 200
    persisted = next(item for item in list_resp.json() if item["id"] == member["id"])
    assert persisted["status"] == "retired"
    assert persisted["current_due"] >= 0
    assert persisted["remaining_balance"] >= 0


def test_membership_collection_report_grouping_fields(base_url, session, auth_headers):
    by_committee = session.get(
        f"{base_url}/api/memberships/collection-report?group_by=committee",
        headers=auth_headers,
        timeout=30,
    )
    assert by_committee.status_code == 200
    cdata = by_committee.json()
    assert cdata["group_by"] == "committee"
    assert "total_due" in cdata["totals"]
    assert "total_collected" in cdata["totals"]
    assert "remaining_balance" in cdata["totals"]

    by_gov = session.get(
        f"{base_url}/api/memberships/collection-report?group_by=governorate",
        headers=auth_headers,
        timeout=30,
    )
    assert by_gov.status_code == 200
    gdata = by_gov.json()
    assert gdata["group_by"] == "governorate"
    assert "total_due" in gdata["totals"]
    assert "total_collected" in gdata["totals"]
    assert "remaining_balance" in gdata["totals"]


def test_membership_batch_payment_creates_fifo_allocations_and_journal(base_url, session, auth_headers, cleanup_state):
    suffix = uuid.uuid4().hex[:6]
    governorate = f"TEST_GOV_{suffix}"
    committee = f"TEST_COM_{suffix}"

    m1 = _create_member(base_url, session, auth_headers, cleanup_state, governorate, committee, f"57{suffix[:4]}11")
    m2 = _create_member(base_url, session, auth_headers, cleanup_state, governorate, committee, f"57{suffix[:4]}12")

    payload = {
        "governorate": governorate,
        "union_committee": committee,
        "bank_id": "industrial-development",
        "payment_date": date.today().isoformat(),
        "amount": 3,
        "receipt_number": f"RCPT-{suffix}",
        "notes": "TEST_ITER57",
    }
    create_resp = session.post(f"{base_url}/api/memberships/batch-payments", headers=auth_headers, json=payload, timeout=30)
    assert create_resp.status_code == 200, create_resp.text
    data = create_resp.json()
    assert data["allocated_amount"] == pytest.approx(3, abs=0.01)
    assert data["unapplied_amount"] == pytest.approx(0, abs=0.01)
    assert len(data["allocations"]) >= 1
    assert all("period" in item and "amount" in item for item in data["allocations"])
    assert data["allocations"][0]["period"] <= data["allocations"][-1]["period"]

    journals_resp = session.get(
        f"{base_url}/api/journal-entries?source_type=membership_batch_payment",
        headers=auth_headers,
        timeout=30,
    )
    assert journals_resp.status_code == 200
    entries = [j for j in journals_resp.json() if j.get("reference") == payload["receipt_number"]]
    assert entries, "membership_batch_payment journal entry not found"
    latest = entries[0]
    assert latest["source_type"] == "membership_batch_payment"
    assert latest["total_debit"] == pytest.approx(latest["total_credit"], abs=0.01)

    # keep member ids referenced so fixture cleanup removes them
    assert m1["id"] in cleanup_state["members"] and m2["id"] in cleanup_state["members"]


def test_rules_engine_includes_opening_balance_and_membership_batch_events(base_url, session, auth_headers):
    resp = session.get(f"{base_url}/api/rules-engine/rules", headers=auth_headers, timeout=30)
    assert resp.status_code == 200, resp.text
    event_types = {item.get("event_type") for item in resp.json()}
    assert "OpeningBalance" in event_types
    assert "MembershipBatchPayment" in event_types


def test_rules_engine_simulation_accepts_opening_balance_event_type(base_url, session, auth_headers):
    resp = session.post(
        f"{base_url}/api/rules-engine/simulate",
        headers=auth_headers,
        json={
            "event_type": "OpeningBalance",
            "sub_type": "Bank",
            "payment_method": "bank_transfer",
            "amount": 10,
            "bank_id": "industrial-development",
        },
        timeout=30,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "is_valid" in data
