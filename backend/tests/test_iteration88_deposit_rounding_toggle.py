"""
Iteration 88 - Per-deposit daily-interest rounding toggle (super-admin only).
Tests:
- GET  /api/admin/deposits-rounding  (super_admin only)
- PATCH /api/admin/deposits/{deposit_id}/rounding (password gated)
- Effect of use_daily_rounding on current-year report
- Financial integrity (trial balance / financial statements)
"""

import os
import pytest
import requests

def _load_env():
    p = "/app/frontend/.env"
    if os.path.exists(p):
        for line in open(p):
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.strip().split("=", 1)
                os.environ.setdefault(k, v)
_load_env()
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
ORG = "social-solidarity"
SUPER_PWD = "Admin@123"

CERT_DEP_ID = "268842b0-c19f-455b-8cb3-621589261a16"   # 77240000102, certificate, 1,000,000 @ 20%
REG_DEP_ID  = "146969f5-7a00-450f-ae1e-4a411d0922f0"   # 772500025, regular, 1,300,000 @ 16%
BANK_SLUG   = "industrial-development"


@pytest.fixture(scope="session")
def token():
    r = requests.post(f"{API}/auth/login", json={
        "username": "admin", "password": SUPER_PWD, "organization_id": ORG
    }, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def h(token):
    return {"Authorization": f"Bearer {token}"}


# --- listing ---
def _deposits(resp_json):
    if isinstance(resp_json, dict) and "deposits" in resp_json:
        return resp_json["deposits"]
    return resp_json


def test_list_deposits_rounding(h):
    r = requests.get(f"{API}/admin/deposits-rounding", headers=h, timeout=30)
    assert r.status_code == 200, r.text
    data = _deposits(r.json())
    assert isinstance(data, list) and len(data) > 0
    row = data[0]
    for k in ("id", "bank_id", "bank_name", "deposit_number", "amount",
              "monthly_interest_rate", "use_daily_rounding"):
        assert k in row, f"missing key {k} in {row}"
    ids = {d["id"] for d in data}
    assert CERT_DEP_ID in ids
    assert REG_DEP_ID in ids


def test_list_deposits_rounding_requires_auth():
    r = requests.get(f"{API}/admin/deposits-rounding", timeout=30)
    assert r.status_code in (401, 403)


# --- patch: wrong password ---
def test_patch_wrong_password(h):
    r = requests.patch(
        f"{API}/admin/deposits/{CERT_DEP_ID}/rounding",
        headers=h,
        json={"use_daily_rounding": True, "password": "wrong-pwd"},
        timeout=30,
    )
    assert r.status_code == 403, r.text
    assert "كلمة مرور السوبر أدمن غير صحيحة" in r.json().get("detail", "")


# --- patch: invalid id ---
def test_patch_invalid_deposit_id(h):
    r = requests.patch(
        f"{API}/admin/deposits/does-not-exist/rounding",
        headers=h,
        json={"use_daily_rounding": True, "password": SUPER_PWD},
        timeout=30,
    )
    assert r.status_code == 404, r.text


# --- patch: correct password sets certificate to False ---
def test_patch_certificate_to_false(h):
    r = requests.patch(
        f"{API}/admin/deposits/{CERT_DEP_ID}/rounding",
        headers=h,
        json={"use_daily_rounding": False, "password": SUPER_PWD},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("use_daily_rounding") is False
    # verify via list
    lst = _deposits(requests.get(f"{API}/admin/deposits-rounding", headers=h, timeout=30).json())
    row = next(d for d in lst if d["id"] == CERT_DEP_ID)
    assert row["use_daily_rounding"] is False


# --- report: certificate full precision (Jan = 16986.30) ---
def test_certificate_january_full_precision(h):
    r = requests.get(
        f"{API}/banks/{BANK_SLUG}/reports/current-year",
        headers=h,
        params={"deposit_id": CERT_DEP_ID},
        timeout=60,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    rows = data.get("rows") or data.get("months") or data.get("data") or []
    # try common shapes
    if not rows and isinstance(data, dict):
        # maybe nested under deposits
        for v in data.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                rows = v
                break
    assert rows, f"No rows in response: {list(data.keys()) if isinstance(data, dict) else type(data)}"
    # find January row
    jan = None
    for row in rows:
        # month numeric or name
        m = row.get("month") or row.get("month_number") or row.get("month_name") or row.get("label")
        if m in (1, "1", "01", "January", "يناير") or (isinstance(m, str) and "يناير" in m):
            jan = row
            break
    if jan is None:
        jan = rows[0]
    interest = jan.get("interest_amount") or jan.get("interest") or jan.get("monthly_interest") or jan.get("amount") or jan.get("value")
    assert interest is not None, f"No interest field in row: {jan}"
    assert round(float(interest), 2) == 16986.30, f"Expected 16986.30, got {interest}"


# --- regular deposit remains rounded ---
def test_regular_deposit_unaffected(h):
    # ensure toggle is True
    requests.patch(
        f"{API}/admin/deposits/{REG_DEP_ID}/rounding",
        headers=h,
        json={"use_daily_rounding": True, "password": SUPER_PWD},
        timeout=30,
    )
    r = requests.get(
        f"{API}/banks/{BANK_SLUG}/reports/current-year",
        headers=h,
        params={"deposit_id": REG_DEP_ID},
        timeout=60,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    rows = data.get("rows") or data.get("months") or data.get("data") or []
    if not rows and isinstance(data, dict):
        for v in data.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                rows = v
                break
    assert rows
    jan = None
    for row in rows:
        m = row.get("month") or row.get("month_number") or row.get("month_name") or row.get("label")
        if m in (1, "1", "01", "January", "يناير") or (isinstance(m, str) and "يناير" in m):
            jan = row; break
    if jan is None:
        jan = rows[0]
    interest = jan.get("interest_amount") or jan.get("interest") or jan.get("monthly_interest") or jan.get("amount") or jan.get("value")
    assert round(float(interest), 2) == 17665.66, f"Expected 17665.66, got {interest}"
    total = data.get("total_interest") or data.get("total") or sum(
        float(r.get("interest_amount") or r.get("interest") or r.get("monthly_interest") or r.get("amount") or 0) for r in rows
    )
    assert round(float(total), 2) == 120811.42, f"Expected 120811.42, got {total}"


# --- financial integrity ---
def test_trial_balance_balanced(h):
    r = requests.get(f"{API}/trial-balance",
                     headers=h,
                     params={"from_date": "2026-01-01", "to_date": "2026-12-31"},
                     timeout=60)
    assert r.status_code == 200, r.text
    assert r.json().get("is_balanced") is True


def test_financial_statements_check(h):
    r = requests.get(f"{API}/financial-statements",
                     headers=h,
                     params={"from_date": "2026-01-01", "to_date": "2026-12-31"},
                     timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    check = data.get("balance_sheet", {}).get("check", {})
    assert float(check.get("total", 0.0)) == 0.0, f"balance_sheet.check.total={check}"
    critical = [e for e in data.get("accounting_errors", []) if (isinstance(e, dict) and e.get("severity") == "critical")]
    assert not critical, f"Critical accounting_errors: {critical}"


# --- restore final state: leave CERT (102) at use_daily_rounding=False, also 103 (per request) ---
CERT2_DEP_ID_NUMBER = "77240000103"

def test_final_state_cert_false(h):
    # ensure 102 stays False
    lst = _deposits(requests.get(f"{API}/admin/deposits-rounding", headers=h, timeout=30).json())
    row102 = next(d for d in lst if d["id"] == CERT_DEP_ID)
    if row102["use_daily_rounding"]:
        requests.patch(
            f"{API}/admin/deposits/{CERT_DEP_ID}/rounding",
            headers=h,
            json={"use_daily_rounding": False, "password": SUPER_PWD},
            timeout=30,
        )
    # ensure 103 (find by number) is False
    row103 = next((d for d in lst if d["deposit_number"] == CERT2_DEP_ID_NUMBER), None)
    if row103 and row103["use_daily_rounding"]:
        requests.patch(
            f"{API}/admin/deposits/{row103['id']}/rounding",
            headers=h,
            json={"use_daily_rounding": False, "password": SUPER_PWD},
            timeout=30,
        )
    # verify
    lst2 = _deposits(requests.get(f"{API}/admin/deposits-rounding", headers=h, timeout=30).json())
    r102 = next(d for d in lst2 if d["id"] == CERT_DEP_ID)
    assert r102["use_daily_rounding"] is False
