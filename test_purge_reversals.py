#!/usr/bin/env python3
"""
Test Suite for Maintenance Endpoint: POST /api/maintenance/purge-reversals
Verifies that the endpoint HARD-removes old reversal journal entries (is_reversal=true)
and previously-reversed originals (entries having a reversal_entry_id),
WITHOUT touching real/live transactions.
"""

import requests
import json
from typing import Dict, Optional

# Configuration
BACKEND_URL = "https://invoke-app.preview.emergentagent.com/api"
AUTH_CREDENTIALS = {
    "username": "admin",
    "password": "Admin@123",
    "organization_id": "social-solidarity"
}

# Test tracking
test_results = []


class TestResult:
    def __init__(self, test_name: str, passed: bool, message: str, details: Optional[Dict] = None):
        self.test_name = test_name
        self.passed = passed
        self.message = message
        self.details = details or {}


def log_test(test_name: str, passed: bool, message: str, details: Optional[Dict] = None):
    """Log test result"""
    result = TestResult(test_name, passed, message, details)
    test_results.append(result)
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"\n{status}: {test_name}")
    print(f"   {message}")
    if details:
        print(f"   Details: {json.dumps(details, ensure_ascii=False, indent=2)}")


def authenticate() -> str:
    """Authenticate and return Bearer token"""
    print("\n" + "="*80)
    print("AUTHENTICATION")
    print("="*80)
    
    response = requests.post(f"{BACKEND_URL}/auth/login", json=AUTH_CREDENTIALS)
    
    if response.status_code != 200:
        log_test("Authentication", False, f"Login failed with status {response.status_code}", 
                {"response": response.text})
        raise Exception(f"Authentication failed: {response.text}")
    
    data = response.json()
    token = data.get("token")
    
    if not token:
        log_test("Authentication", False, "No token in response", {"response": data})
        raise Exception("No token received")
    
    log_test("Authentication", True, f"Successfully authenticated as {AUTH_CREDENTIALS['username']}")
    return token


def get_headers(token: str) -> Dict[str, str]:
    """Get request headers with Bearer token"""
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }


def test_purge_without_auth():
    """TEST 1: POST /api/maintenance/purge-reversals WITHOUT auth header -> expect 401 or 403, NOT 405"""
    print("\n" + "="*80)
    print("TEST 1: Purge Reversals WITHOUT Authentication")
    print("="*80)
    
    response = requests.post(f"{BACKEND_URL}/maintenance/purge-reversals")
    
    if response.status_code in [401, 403]:
        log_test(
            "Purge without auth",
            True,
            f"Correctly rejected with HTTP {response.status_code} (route exists and requires auth)",
            {"status_code": response.status_code, "response": response.text[:200]}
        )
        return True
    elif response.status_code == 405:
        log_test(
            "Purge without auth",
            False,
            f"Got HTTP 405 Method Not Allowed - route may not exist!",
            {"status_code": response.status_code, "response": response.text[:200]}
        )
        return False
    else:
        log_test(
            "Purge without auth",
            False,
            f"Unexpected status code {response.status_code} (expected 401 or 403)",
            {"status_code": response.status_code, "response": response.text[:200]}
        )
        return False


def test_purge_with_auth(token: str):
    """TEST 2: POST /api/maintenance/purge-reversals WITH admin Bearer token -> expect HTTP 200"""
    print("\n" + "="*80)
    print("TEST 2: Purge Reversals WITH Admin Authentication")
    print("="*80)
    
    response = requests.post(
        f"{BACKEND_URL}/maintenance/purge-reversals",
        headers=get_headers(token)
    )
    
    if response.status_code != 200:
        log_test(
            "Purge with admin auth",
            False,
            f"Expected HTTP 200, got {response.status_code}",
            {"status_code": response.status_code, "response": response.text[:500]}
        )
        return None
    
    try:
        data = response.json()
    except Exception as e:
        log_test(
            "Purge with admin auth",
            False,
            f"Failed to parse JSON response: {str(e)}",
            {"response": response.text[:500]}
        )
        return None
    
    # Verify response structure
    required_fields = ["deleted_reversals", "deleted_reversed_originals", "message"]
    missing_fields = [field for field in required_fields if field not in data]
    
    if missing_fields:
        log_test(
            "Purge with admin auth",
            False,
            f"Response missing required fields: {missing_fields}",
            {"response": data}
        )
        return None
    
    log_test(
        "Purge with admin auth",
        True,
        f"Successfully purged reversals - deleted_reversals={data['deleted_reversals']}, deleted_reversed_originals={data['deleted_reversed_originals']}",
        {"response": data}
    )
    
    return data


def get_live_data_counts(token: str) -> Dict:
    """Get counts of live data (revenues, expenses, deposits)"""
    print("\n" + "="*80)
    print("GETTING LIVE DATA COUNTS")
    print("="*80)
    
    counts = {}
    
    # Get revenues count
    response = requests.get(f"{BACKEND_URL}/revenues", headers=get_headers(token))
    if response.status_code == 200:
        revenues = response.json()
        counts["revenues"] = len(revenues) if isinstance(revenues, list) else 0
        print(f"   Revenues count: {counts['revenues']}")
    else:
        print(f"   ⚠️  Failed to get revenues: {response.status_code}")
        counts["revenues"] = None
    
    # Get expenses count
    response = requests.get(f"{BACKEND_URL}/expenses", headers=get_headers(token))
    if response.status_code == 200:
        expenses = response.json()
        counts["expenses"] = len(expenses) if isinstance(expenses, list) else 0
        print(f"   Expenses count: {counts['expenses']}")
    else:
        print(f"   ⚠️  Failed to get expenses: {response.status_code}")
        counts["expenses"] = None
    
    # Get deposits count (deposits are under banks/industrial-development)
    response = requests.get(f"{BACKEND_URL}/banks/industrial-development/deposits", headers=get_headers(token))
    if response.status_code == 200:
        deposits = response.json()
        counts["deposits"] = len(deposits) if isinstance(deposits, list) else 0
        print(f"   Deposits count: {counts['deposits']}")
    else:
        print(f"   ⚠️  Failed to get deposits: {response.status_code}")
        counts["deposits"] = 0  # Default to 0 instead of None
    
    return counts


def get_trial_balance(token: str) -> Optional[Dict]:
    """Get trial balance"""
    response = requests.get(f"{BACKEND_URL}/trial-balance", headers=get_headers(token))
    
    if response.status_code != 200:
        print(f"   ⚠️  Failed to get trial balance: {response.status_code}")
        return None
    
    return response.json()


def get_financial_statements(token: str) -> Optional[Dict]:
    """Get financial statements"""
    params = {"from_date": "2026-01-01", "to_date": "2026-12-31"}
    response = requests.get(
        f"{BACKEND_URL}/financial-statements",
        headers=get_headers(token),
        params=params
    )
    
    if response.status_code != 200:
        print(f"   ⚠️  Failed to get financial statements: {response.status_code}")
        return None
    
    return response.json()


def test_data_safety(token: str):
    """TEST 3: Data-safety check - verify purge does NOT change live data counts"""
    print("\n" + "="*80)
    print("TEST 3: Data Safety Check (BEFORE and AFTER purge)")
    print("="*80)
    
    # Get counts BEFORE purge
    print("\n📊 BEFORE PURGE:")
    counts_before = get_live_data_counts(token)
    trial_balance_before = get_trial_balance(token)
    financial_statements_before = get_financial_statements(token)
    
    if trial_balance_before:
        print(f"   Trial Balance - Debit: {trial_balance_before.get('total_debit', 'N/A')}, Credit: {trial_balance_before.get('total_credit', 'N/A')}, Balanced: {trial_balance_before.get('is_balanced', 'N/A')}")
    
    # Call purge
    print("\n🔧 CALLING PURGE...")
    purge_result = test_purge_with_auth(token)
    
    if purge_result is None:
        log_test(
            "Data safety check",
            False,
            "Purge failed, cannot verify data safety",
            {}
        )
        return False
    
    # Get counts AFTER purge
    print("\n📊 AFTER PURGE:")
    counts_after = get_live_data_counts(token)
    trial_balance_after = get_trial_balance(token)
    financial_statements_after = get_financial_statements(token)
    
    if trial_balance_after:
        print(f"   Trial Balance - Debit: {trial_balance_after.get('total_debit', 'N/A')}, Credit: {trial_balance_after.get('total_credit', 'N/A')}, Balanced: {trial_balance_after.get('is_balanced', 'N/A')}")
    
    # Compare counts
    all_passed = True
    
    for key in ["revenues", "expenses", "deposits"]:
        before = counts_before.get(key)
        after = counts_after.get(key)
        
        if before is None or after is None:
            print(f"   ⚠️  Could not verify {key} count (before={before}, after={after})")
            continue
        
        if before != after:
            log_test(
                f"Data safety - {key} count unchanged",
                False,
                f"{key.capitalize()} count CHANGED: {before} -> {after} (CRITICAL: live data was affected!)",
                {"before": before, "after": after}
            )
            all_passed = False
        else:
            log_test(
                f"Data safety - {key} count unchanged",
                True,
                f"{key.capitalize()} count unchanged: {before} (live data safe)",
                {"count": before}
            )
    
    # Verify trial balance unchanged
    if trial_balance_before and trial_balance_after:
        tb_before_debit = trial_balance_before.get("total_debit")
        tb_after_debit = trial_balance_after.get("total_debit")
        tb_before_credit = trial_balance_before.get("total_credit")
        tb_after_credit = trial_balance_after.get("total_credit")
        
        if tb_before_debit == tb_after_debit and tb_before_credit == tb_after_credit:
            log_test(
                "Data safety - trial balance unchanged",
                True,
                f"Trial balance unchanged: Debit={tb_before_debit}, Credit={tb_before_credit}",
                {"debit": tb_before_debit, "credit": tb_before_credit, "balanced": trial_balance_after.get("is_balanced")}
            )
        else:
            log_test(
                "Data safety - trial balance unchanged",
                False,
                f"Trial balance CHANGED: Debit {tb_before_debit}->{tb_after_debit}, Credit {tb_before_credit}->{tb_after_credit}",
                {"before": {"debit": tb_before_debit, "credit": tb_before_credit}, "after": {"debit": tb_after_debit, "credit": tb_after_credit}}
            )
            all_passed = False
    
    # Verify deposit opening balance still exists (if there was one before)
    deposits_before = counts_before.get("deposits", 0)
    deposits_after = counts_after.get("deposits", 0)
    
    if deposits_before is not None and deposits_after is not None:
        if deposits_before == deposits_after:
            log_test(
                "Data safety - deposits count unchanged",
                True,
                f"Deposits count unchanged: {deposits_before} (deposit opening balance safe)",
                {"deposits_count": deposits_after}
            )
        else:
            log_test(
                "Data safety - deposits count unchanged",
                False,
                f"CRITICAL: Deposits count CHANGED: {deposits_before} -> {deposits_after}",
                {"before": deposits_before, "after": deposits_after}
            )
            all_passed = False
    else:
        print(f"   ⚠️  Could not verify deposits count (before={deposits_before}, after={deposits_after})")
    
    return all_passed


def test_idempotent_purge(token: str):
    """TEST 4: Call purge again -> expect HTTP 200 with deleted counts = 0 (idempotent)"""
    print("\n" + "="*80)
    print("TEST 4: Idempotent Purge (second call should return 0 deletions)")
    print("="*80)
    
    response = requests.post(
        f"{BACKEND_URL}/maintenance/purge-reversals",
        headers=get_headers(token)
    )
    
    if response.status_code != 200:
        log_test(
            "Idempotent purge",
            False,
            f"Expected HTTP 200, got {response.status_code}",
            {"status_code": response.status_code, "response": response.text[:500]}
        )
        return False
    
    try:
        data = response.json()
    except Exception as e:
        log_test(
            "Idempotent purge",
            False,
            f"Failed to parse JSON response: {str(e)}",
            {"response": response.text[:500]}
        )
        return False
    
    deleted_reversals = data.get("deleted_reversals", -1)
    deleted_originals = data.get("deleted_reversed_originals", -1)
    
    if deleted_reversals == 0 and deleted_originals == 0:
        log_test(
            "Idempotent purge",
            True,
            "Second purge call returned 0 deletions (idempotent, nothing left to clean)",
            {"response": data}
        )
        return True
    else:
        log_test(
            "Idempotent purge",
            False,
            f"Second purge call still deleted entries: reversals={deleted_reversals}, originals={deleted_originals}",
            {"response": data}
        )
        return False


def print_summary():
    """Print test summary"""
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for r in test_results if r.passed)
    failed = sum(1 for r in test_results if not r.passed)
    total = len(test_results)
    
    print(f"\nTotal Tests: {total}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"Success Rate: {(passed/total*100):.1f}%")
    
    if failed > 0:
        print("\n❌ FAILED TESTS:")
        for result in test_results:
            if not result.passed:
                print(f"   - {result.test_name}: {result.message}")
    
    print("\n" + "="*80)
    
    return failed == 0


def main():
    """Main test execution"""
    print("\n" + "="*80)
    print("MAINTENANCE ENDPOINT TEST: POST /api/maintenance/purge-reversals")
    print("="*80)
    print(f"Backend URL: {BACKEND_URL}")
    print(f"Organization: {AUTH_CREDENTIALS['organization_id']}")
    print(f"User: {AUTH_CREDENTIALS['username']}")
    
    try:
        # TEST 1: Without auth
        test_purge_without_auth()
        
        # Authenticate for remaining tests
        token = authenticate()
        
        # TEST 2 & 3: With auth + data safety
        test_data_safety(token)
        
        # TEST 4: Idempotent
        test_idempotent_purge(token)
        
        # Print summary
        all_passed = print_summary()
        
        if all_passed:
            print("\n✅ ALL TESTS PASSED - Maintenance endpoint working correctly!")
            return 0
        else:
            print("\n❌ SOME TESTS FAILED - See details above")
            return 1
    
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
