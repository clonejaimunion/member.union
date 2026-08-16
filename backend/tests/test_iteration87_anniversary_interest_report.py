"""
Iteration 87 - Verify anniversary-cycle interest calculation for deposit monthly-yield report
matches bank statement rounding methodology.
"""
import os
import pytest
import requests
from dotenv import load_dotenv
load_dotenv("/app/frontend/.env")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
BANK_ID = "industrial-development"
ORG = "social-solidarity"

DEP_772500025 = "146969f5-7a00-450f-ae1e-4a411d0922f0"      # 1.3M @16%, created 2025-07-21
DEP_77240000102 = "268842b0-c19f-455b-8cb3-621589261a16"    # 1.0M @20%, created 2024-09-18

EXPECTED_772500025_2026 = {
    "يناير": 17665.66,
    "فبراير": 17665.66,
    "مارس": 15956.08,
    "أبريل": 17665.66,
    "مايو": 17095.80,
    "يونيو": 17665.66,
    "يوليو": 17096.90,
}
EXPECTED_TOTAL_772500025 = 120811.42


@pytest.fixture(scope="module")
def token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": "admin", "password": "Admin@123", "organization_id": ORG},
        timeout=30,
    )
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()["access_token"] if "access_token" in r.json() else r.json().get("token")


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}"}


def _get(url, headers):
    r = requests.get(url, headers=headers, timeout=60)
    return r


# --- Deposit 772500025: exact monthly and total match ---
class TestDeposit772500025CurrentYear:
    def test_current_year_report_matches_bank(self, headers):
        url = f"{BASE_URL}/api/banks/{BANK_ID}/reports/current-year?deposit_id={DEP_772500025}"
        r = _get(url, headers)
        assert r.status_code == 200, r.text
        data = r.json()
        print("772500025 current-year response keys:", list(data.keys()))
        print("Total interest:", data.get("total_interest"))

        # total interest exactly matches bank
        total = data.get("total_interest") or data.get("summary", {}).get("total_interest")
        assert total is not None, f"missing total_interest in {data}"
        assert round(float(total), 2) == EXPECTED_TOTAL_772500025, \
            f"total_interest {total} != {EXPECTED_TOTAL_772500025}"

        # monthly rows
        rows = data.get("rows") or data.get("monthly_rows") or data.get("months") or data.get("data")
        assert rows, f"no rows in response: {list(data.keys())}"
        # Build map month_name -> interest
        month_map = {}
        for row in rows:
            name = row.get("month") or row.get("month_name") or row.get("name")
            val = row.get("interest") or row.get("interest_amount") or row.get("amount")
            if name is not None and val is not None:
                month_map[str(name)] = float(val)
        print("Month map:", month_map)
        for m, exp in EXPECTED_772500025_2026.items():
            assert m in month_map, f"missing month {m}. Have: {list(month_map.keys())}"
            assert round(month_map[m], 2) == exp, f"{m}: {month_map[m]} != {exp}"

    def test_daily_rate_rounding(self, headers):
        # daily = round(0.16*1_300_000/365, 2) = 569.86
        url = f"{BASE_URL}/api/banks/{BANK_ID}/reports/current-year?deposit_id={DEP_772500025}"
        r = _get(url, headers)
        assert r.status_code == 200
        data = r.json()
        daily = data.get("daily_interest") or data.get("daily_rate") or data.get("daily_interest_amount")
        # If not in top-level, try derive from Jan row (31 days): 569.86 * 31 = 17665.66
        if daily is None:
            rows = data.get("rows") or data.get("monthly_rows") or []
            for row in rows:
                name = row.get("month") or row.get("month_name")
                days = row.get("active_days") or row.get("days") or row.get("day_count")
                interest = row.get("interest_amount") or row.get("interest") or row.get("amount")
                if name == "يناير" and days and interest:
                    daily = round(float(interest) / float(days), 2)
                    break
        assert daily is not None, "cannot determine daily interest"
        assert round(float(daily), 2) == 569.86, f"daily {daily} != 569.86"


# --- Deposit 77240000102: 18th-cycle, full year 2026 = 200000.0 ---
class TestDeposit77240000102FullYear:
    def test_current_year_exact_annual_interest(self, headers):
        url = f"{BASE_URL}/api/banks/{BANK_ID}/reports/current-year?deposit_id={DEP_77240000102}"
        r = _get(url, headers)
        assert r.status_code == 200, r.text
        data = r.json()
        total = data.get("total_interest") or data.get("summary", {}).get("total_interest")
        assert total is not None
        assert round(float(total), 2) == 200000.00, f"expected 200000.0 got {total}"


# --- Previous-year endpoint sanity ---
class TestPreviousYear:
    @pytest.mark.parametrize("dep_id", [DEP_772500025, DEP_77240000102])
    def test_previous_year_no_error(self, headers, dep_id):
        url = f"{BASE_URL}/api/banks/{BANK_ID}/reports/previous-year?deposit_id={dep_id}"
        r = _get(url, headers)
        assert r.status_code == 200, f"prev-year {dep_id}: {r.status_code} {r.text}"
        data = r.json()
        assert isinstance(data, dict)


# --- Financial integrity ---
class TestFinancialIntegrity:
    def test_trial_balance_balanced_2026(self, headers):
        url = f"{BASE_URL}/api/trial-balance?from_date=2026-01-01&to_date=2026-12-31"
        r = _get(url, headers)
        assert r.status_code == 200, r.text
        data = r.json()
        print("trial-balance keys:", list(data.keys()))
        is_balanced = data.get("is_balanced")
        td = data.get("total_debit")
        tc = data.get("total_credit")
        assert is_balanced is True or (td is not None and tc is not None and round(float(td), 2) == round(float(tc), 2)), \
            f"unbalanced: debit={td} credit={tc} is_balanced={is_balanced}"

    def test_financial_statements_2026_balanced(self, headers):
        url = f"{BASE_URL}/api/financial-statements?from_date=2026-01-01&to_date=2026-12-31"
        r = _get(url, headers)
        assert r.status_code == 200, r.text
        data = r.json()
        bs = data.get("balance_sheet") or {}
        chk = bs.get("check") or {}
        total_diff = chk.get("total")
        print("balance_sheet check:", chk)
        assert total_diff is not None
        assert round(float(total_diff), 2) == 0.0, f"balance diff {total_diff}"
        errs = data.get("accounting_errors") or []
        critical = [e for e in errs if str(e.get("severity", "")).lower() == "critical"]
        assert not critical, f"critical accounting errors: {critical}"


# --- Detailed bank statement ---
class TestDetailedStatement:
    def test_detailed_yearly_2026(self, headers):
        url = f"{BASE_URL}/api/banks/{BANK_ID}/statements/detailed?period_type=yearly&year=2026"
        r = _get(url, headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, dict)
        rows = data.get("rows") or data.get("deposits") or data.get("data") or []
        assert rows, f"no rows in detailed statement, keys={list(data.keys())}"
        # ensure current_year_interest exists on at least some rows
        has_cyi = any(("current_year_interest" in r_) for r_ in rows if isinstance(r_, dict))
        assert has_cyi, f"no current_year_interest column. Sample row: {rows[0] if rows else None}"
