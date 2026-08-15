#!/usr/bin/env python3
"""
Backend Test Suite for Arabic Accounting System - Manual Journal Entry Deletion
VERIFICATION: DELETE /api/journal-entries/{id} now HARD-DELETES the entry instead of creating a reversal
"""

import requests
import json
from datetime import date
from typing import Dict, List, Optional

# Configuration
BACKEND_URL = "https://invoke-app.preview.emergentagent.com/api"
AUTH_CREDENTIALS = {
    "username": "admin",
    "password": "Admin@123",
    "organization_id": "social-solidarity"
}
BANK_ID = "industrial-development"

# Test tracking
created_journal_entries = []
created_revenues = []
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


def get_chart_accounts(token: str) -> List[Dict]:
    """Get chart of accounts"""
    url = f"{BACKEND_URL}/chart-accounts"
    response = requests.get(url, headers=get_headers(token))
    
    if response.status_code != 200:
        raise Exception(f"Failed to get chart accounts: {response.status_code} - {response.text}")
    
    return response.json()


def get_trial_balance(token: str, from_date: str = "2026-01-01", to_date: str = "2026-12-31") -> Dict:
    """Get trial balance"""
    url = f"{BACKEND_URL}/trial-balance"
    params = {"from_date": from_date, "to_date": to_date}
    response = requests.get(url, headers=get_headers(token), params=params)
    
    if response.status_code != 200:
        raise Exception(f"Failed to get trial balance: {response.status_code} - {response.text}")
    
    return response.json()


def get_journal_entries(token: str) -> List[Dict]:
    """Get all journal entries"""
    url = f"{BACKEND_URL}/journal-entries"
    response = requests.get(url, headers=get_headers(token))
    
    if response.status_code != 200:
        raise Exception(f"Failed to get journal entries: {response.status_code} - {response.text}")
    
    return response.json()


def get_journal_entry_by_id(token: str, entry_id: str) -> Optional[Dict]:
    """Get a specific journal entry by ID"""
    url = f"{BACKEND_URL}/journal-entries/{entry_id}"
    response = requests.get(url, headers=get_headers(token))
    
    if response.status_code == 404:
        return None
    
    if response.status_code != 200:
        raise Exception(f"Failed to get journal entry: {response.status_code} - {response.text}")
    
    return response.json()


def create_manual_journal_entry(token: str, account1: Dict, account2: Dict, amount: float = 1000.0) -> Dict:
    """Create a balanced manual journal entry"""
    payload = {
        "entry_date": "2026-03-01",
        "description": "قيد يدوي اختبار - Manual test entry",
        "reference": "TEST-001",
        "lines": [
            {
                "account_code": account1["code"],
                "account_name": account1["name"],
                "account_type": account1["account_type"],
                "debit": amount,
                "credit": 0,
                "notes": "مدين - Debit line"
            },
            {
                "account_code": account2["code"],
                "account_name": account2["name"],
                "account_type": account2["account_type"],
                "debit": 0,
                "credit": amount,
                "notes": "دائن - Credit line"
            }
        ]
    }
    
    response = requests.post(f"{BACKEND_URL}/journal-entries", headers=get_headers(token), json=payload)
    
    if response.status_code != 200:
        raise Exception(f"Failed to create journal entry: {response.status_code} - {response.text}")
    
    entry = response.json()
    created_journal_entries.append(entry["id"])
    return entry


def delete_journal_entry(token: str, entry_id: str) -> bool:
    """Delete a manual journal entry"""
    response = requests.delete(f"{BACKEND_URL}/journal-entries/{entry_id}", headers=get_headers(token))
    
    if response.status_code == 200:
        if entry_id in created_journal_entries:
            created_journal_entries.remove(entry_id)
        return True
    
    return False


def create_check_revenue(token: str, receipt_number: str, amount: float, check_number: str) -> Dict:
    """Create a check revenue for regression testing"""
    payload = {
        "receipt_number": receipt_number,
        "amount": amount,
        "collection_method": "check",
        "check_number": check_number,
        "check_clearing_type": "internal",
        "bank_id": BANK_ID,
        "dated": "2026-03-01",
        "value": "اختبار regression",
        "issued_at": "2026-03-01",
        "responsible_employee": "يوسف عبدالغني"
    }
    
    response = requests.post(f"{BACKEND_URL}/revenues", headers=get_headers(token), json=payload)
    
    if response.status_code != 200:
        raise Exception(f"Failed to create revenue: {response.status_code} - {response.text}")
    
    revenue = response.json()
    created_revenues.append(revenue["id"])
    return revenue


def delete_revenue(token: str, revenue_id: str) -> bool:
    """Delete a revenue"""
    response = requests.delete(f"{BACKEND_URL}/revenues/{revenue_id}", headers=get_headers(token))
    
    if response.status_code == 200:
        if revenue_id in created_revenues:
            created_revenues.remove(revenue_id)
        return True
    
    return False


def get_financial_statements(token: str, from_date: str = "2026-01-01", to_date: str = "2026-12-31") -> Dict:
    """Get financial statements"""
    url = f"{BACKEND_URL}/financial-statements"
    params = {"from_date": from_date, "to_date": to_date}
    response = requests.get(url, headers=get_headers(token), params=params)
    
    if response.status_code != 200:
        raise Exception(f"Failed to get financial statements: {response.status_code} - {response.text}")
    
    return response.json()


def find_balance_sheet_line(statements: Dict, line_name: str) -> Optional[Dict]:
    """Find a specific line in balance sheet assets"""
    balance_sheet = statements.get("balance_sheet", {})
    assets = balance_sheet.get("assets", {})
    lines = assets.get("lines", [])
    
    for line in lines:
        if line.get("name") == line_name:
            return line
    
    return None


def test_1_get_chart_accounts(token: str) -> tuple:
    """TEST 1: Get chart accounts to pick two valid accounts"""
    print("\n" + "="*80)
    print("TEST 1: Get Chart Accounts")
    print("="*80)
    
    try:
        accounts = get_chart_accounts(token)
        
        if len(accounts) < 2:
            log_test("TEST 1: Get Chart Accounts", False, 
                    f"Not enough accounts found (need at least 2, found {len(accounts)})")
            raise Exception("Not enough accounts")
        
        # Pick two postable accounts (one asset, one liability or equity for balance)
        asset_account = None
        liability_account = None
        
        for account in accounts:
            if account.get("is_postable") and account.get("account_type") == "asset" and not asset_account:
                asset_account = account
            elif account.get("is_postable") and account.get("account_type") in ["liability", "equity"] and not liability_account:
                liability_account = account
            
            if asset_account and liability_account:
                break
        
        if not asset_account or not liability_account:
            # Fallback: just pick any two postable accounts
            postable = [a for a in accounts if a.get("is_postable")]
            if len(postable) >= 2:
                asset_account = postable[0]
                liability_account = postable[1]
        
        if not asset_account or not liability_account:
            log_test("TEST 1: Get Chart Accounts", False, 
                    "Could not find two postable accounts")
            raise Exception("Could not find suitable accounts")
        
        log_test("TEST 1: Get Chart Accounts", True,
                f"Found {len(accounts)} accounts, selected 2 for testing",
                {
                    "total_accounts": len(accounts),
                    "account1": f"{asset_account['code']} - {asset_account['name']}",
                    "account2": f"{liability_account['code']} - {liability_account['name']}"
                })
        
        return asset_account, liability_account
        
    except Exception as e:
        log_test("TEST 1: Get Chart Accounts", False, f"Exception: {str(e)}")
        raise


def test_2_create_manual_journal_entry(token: str, account1: Dict, account2: Dict) -> tuple:
    """TEST 2: Create a balanced manual journal entry"""
    print("\n" + "="*80)
    print("TEST 2: Create Manual Journal Entry")
    print("="*80)
    
    try:
        # Get trial balance before
        trial_balance_before = get_trial_balance(token)
        total_debit_before = trial_balance_before.get("total_debit", 0)
        total_credit_before = trial_balance_before.get("total_credit", 0)
        
        log_test("TEST 2.1: Get Trial Balance Before", True,
                f"Debit: {total_debit_before}, Credit: {total_credit_before}",
                {"total_debit": total_debit_before, "total_credit": total_credit_before})
        
        # Create manual journal entry
        entry = create_manual_journal_entry(token, account1, account2, 1000.0)
        entry_id = entry["id"]
        
        log_test("TEST 2.2: Create Manual Journal Entry", True,
                f"Successfully created journal entry with ID: {entry_id}",
                {
                    "entry_id": entry_id,
                    "entry_date": entry.get("entry_date"),
                    "description": entry.get("description"),
                    "total_debit": entry.get("total_debit"),
                    "total_credit": entry.get("total_credit")
                })
        
        # Verify entry exists in list
        all_entries = get_journal_entries(token)
        entry_found = any(e.get("id") == entry_id for e in all_entries)
        
        if entry_found:
            log_test("TEST 2.3: Verify Entry in List", True,
                    f"Entry {entry_id} found in journal entries list")
        else:
            log_test("TEST 2.3: Verify Entry in List", False,
                    f"Entry {entry_id} NOT found in journal entries list!")
        
        # Get trial balance after
        trial_balance_after = get_trial_balance(token)
        total_debit_after = trial_balance_after.get("total_debit", 0)
        total_credit_after = trial_balance_after.get("total_credit", 0)
        
        # Verify trial balance increased by 1000
        debit_increase = total_debit_after - total_debit_before
        credit_increase = total_credit_after - total_credit_before
        
        if debit_increase == 1000.0 and credit_increase == 1000.0:
            log_test("TEST 2.4: Verify Trial Balance Impact", True,
                    f"Trial balance increased by 1000.0 on both sides (Debit: {total_debit_before} → {total_debit_after}, Credit: {total_credit_before} → {total_credit_after})",
                    {
                        "debit_before": total_debit_before,
                        "debit_after": total_debit_after,
                        "debit_increase": debit_increase,
                        "credit_before": total_credit_before,
                        "credit_after": total_credit_after,
                        "credit_increase": credit_increase
                    })
        else:
            log_test("TEST 2.4: Verify Trial Balance Impact", False,
                    f"Trial balance did not increase by 1000.0 as expected (Debit increase: {debit_increase}, Credit increase: {credit_increase})",
                    {
                        "debit_increase": debit_increase,
                        "credit_increase": credit_increase,
                        "expected": 1000.0
                    })
        
        return entry_id, total_debit_before, total_credit_before
        
    except Exception as e:
        log_test("TEST 2: Create Manual Journal Entry", False, f"Exception: {str(e)}")
        raise


def test_3_delete_manual_journal_entry(token: str, entry_id: str, debit_before: float, credit_before: float):
    """TEST 3: Delete manual journal entry and verify HARD DELETE (CORE TEST)"""
    print("\n" + "="*80)
    print("TEST 3: Delete Manual Journal Entry (CORE VERIFICATION)")
    print("="*80)
    
    try:
        # Delete the entry
        success = delete_journal_entry(token, entry_id)
        
        if not success:
            log_test("TEST 3.1: Delete Journal Entry", False, 
                    f"Failed to delete journal entry {entry_id}")
            return
        
        log_test("TEST 3.1: Delete Journal Entry", True, 
                f"Successfully deleted journal entry {entry_id} (HTTP 200)")
        
        # TEST 3a: Verify entry no longer appears in list
        all_entries = get_journal_entries(token)
        entry_found = any(e.get("id") == entry_id for e in all_entries)
        
        if not entry_found:
            log_test("TEST 3.2a: Verify Entry Removed from List", True,
                    f"Entry {entry_id} no longer appears in journal entries list ✅")
        else:
            log_test("TEST 3.2a: Verify Entry Removed from List", False,
                    f"Entry {entry_id} STILL appears in journal entries list! ❌")
        
        # TEST 3b: Verify ZERO is_reversal entries exist (CRITICAL)
        reversal_entries = [e for e in all_entries if e.get("is_reversal") == True]
        
        if len(reversal_entries) == 0:
            log_test("TEST 3.2b: Verify NO Reversal Entries Created", True,
                    "✅ CRITICAL: ZERO is_reversal entries found - no reversal was created (hard delete confirmed)!",
                    {"reversal_count": 0})
        else:
            log_test("TEST 3.2b: Verify NO Reversal Entries Created", False,
                    f"❌ CRITICAL: Found {len(reversal_entries)} is_reversal entries - reversal logic still active!",
                    {
                        "reversal_count": len(reversal_entries),
                        "reversal_entries": [
                            {
                                "id": e.get("id"),
                                "description": e.get("description"),
                                "is_reversal": e.get("is_reversal")
                            } for e in reversal_entries
                        ]
                    })
        
        # TEST 3c: Verify trial balance returns to prior state
        trial_balance_after = get_trial_balance(token)
        total_debit_after = trial_balance_after.get("total_debit", 0)
        total_credit_after = trial_balance_after.get("total_credit", 0)
        
        debit_match = abs(total_debit_after - debit_before) < 0.01
        credit_match = abs(total_credit_after - credit_before) < 0.01
        
        if debit_match and credit_match:
            log_test("TEST 3.2c: Verify Trial Balance Restored", True,
                    f"✅ Trial balance returned to prior state (Debit: {debit_before} → {total_debit_after}, Credit: {credit_before} → {total_credit_after})",
                    {
                        "debit_before": debit_before,
                        "debit_after": total_debit_after,
                        "credit_before": credit_before,
                        "credit_after": total_credit_after
                    })
        else:
            log_test("TEST 3.2c: Verify Trial Balance Restored", False,
                    f"❌ Trial balance did NOT return to prior state (Debit: {debit_before} → {total_debit_after}, Credit: {credit_before} → {total_credit_after})",
                    {
                        "debit_before": debit_before,
                        "debit_after": total_debit_after,
                        "debit_diff": total_debit_after - debit_before,
                        "credit_before": credit_before,
                        "credit_after": total_credit_after,
                        "credit_diff": total_credit_after - credit_before
                    })
        
        # CORE ASSERTION
        if not entry_found and len(reversal_entries) == 0 and debit_match and credit_match:
            log_test("TEST 3.3: CORE ASSERTION - Hard Delete Verified", True,
                    "✅ ✅ ✅ HARD DELETE CONFIRMED! Entry removed, NO reversal created, trial balance restored. Bug fix verified!")
        else:
            log_test("TEST 3.3: CORE ASSERTION - Hard Delete Verified", False,
                    "❌ ❌ ❌ HARD DELETE NOT WORKING! Either entry still exists, reversal was created, or trial balance not restored.")
        
    except Exception as e:
        log_test("TEST 3: Delete Manual Journal Entry", False, f"Exception: {str(e)}")
        raise


def test_4_regression_revenue_delete(token: str):
    """TEST 4: Regression - Create check revenue, verify in statements, delete, verify disappears"""
    print("\n" + "="*80)
    print("TEST 4: Regression - Revenue Hard Delete Still Works")
    print("="*80)
    
    try:
        # Create check revenue
        revenue = create_check_revenue(token, "94001", 2500.0, "888001")
        revenue_id = revenue["id"]
        
        log_test("TEST 4.1: Create Check Revenue", True,
                f"Successfully created check revenue with ID: {revenue_id}",
                {"receipt_number": "94001", "amount": 2500.0, "check_number": "888001"})
        
        # Get financial statements
        statements = get_financial_statements(token)
        checks_line = find_balance_sheet_line(statements, "شيكات تحت التحصيل")
        
        if checks_line:
            amount_before = checks_line.get("amount", 0)
            log_test("TEST 4.2: Verify in Financial Statements", True,
                    f"Found 'شيكات تحت التحصيل' line with amount: {amount_before}",
                    {"line_name": "شيكات تحت التحصيل", "amount": amount_before})
        else:
            log_test("TEST 4.2: Verify in Financial Statements", False,
                    "Line 'شيكات تحت التحصيل' not found in balance sheet")
            amount_before = 0
        
        # Delete the revenue
        success = delete_revenue(token, revenue_id)
        
        if not success:
            log_test("TEST 4.3: Delete Revenue", False, f"Failed to delete revenue {revenue_id}")
            return
        
        log_test("TEST 4.3: Delete Revenue", True, f"Successfully deleted revenue {revenue_id}")
        
        # Get financial statements again
        statements = get_financial_statements(token)
        checks_line = find_balance_sheet_line(statements, "شيكات تحت التحصيل")
        
        if checks_line:
            amount_after = checks_line.get("amount", 0)
            expected_amount = amount_before - 2500.0
            
            if abs(amount_after - expected_amount) < 0.01:
                log_test("TEST 4.4: Verify Disappears from Statements", True,
                        f"✅ Revenue correctly disappeared (Before: {amount_before}, After: {amount_after}, Expected: {expected_amount})")
            else:
                log_test("TEST 4.4: Verify Disappears from Statements", False,
                        f"❌ Revenue did not disappear correctly (Before: {amount_before}, After: {amount_after}, Expected: {expected_amount})")
        else:
            # Line disappeared completely
            if abs(amount_before - 2500.0) < 0.01:
                log_test("TEST 4.4: Verify Disappears from Statements", True,
                        "✅ Line 'شيكات تحت التحصيل' completely disappeared (expected)")
            else:
                log_test("TEST 4.4: Verify Disappears from Statements", False,
                        f"Line disappeared but amount_before was {amount_before}, not 2500.0")
        
    except Exception as e:
        log_test("TEST 4: Regression Revenue Delete", False, f"Exception: {str(e)}")
        raise


def test_5_regression_trial_balance_and_statements(token: str):
    """TEST 5: Regression - Trial balance and financial statements still balance"""
    print("\n" + "="*80)
    print("TEST 5: Regression - Trial Balance and Financial Statements Balance")
    print("="*80)
    
    try:
        # Get trial balance
        trial_balance = get_trial_balance(token)
        total_debit = trial_balance.get("total_debit", 0)
        total_credit = trial_balance.get("total_credit", 0)
        is_balanced = trial_balance.get("is_balanced", False)
        
        if is_balanced and abs(total_debit - total_credit) < 0.01:
            log_test("TEST 5.1: Trial Balance Verification", True,
                    f"✅ Trial balance is balanced! Debit ({total_debit}) = Credit ({total_credit})",
                    {"total_debit": total_debit, "total_credit": total_credit, "is_balanced": is_balanced})
        else:
            log_test("TEST 5.1: Trial Balance Verification", False,
                    f"❌ Trial balance is NOT balanced! Debit ({total_debit}) ≠ Credit ({total_credit})",
                    {"total_debit": total_debit, "total_credit": total_credit, "difference": abs(total_debit - total_credit)})
        
        # Get financial statements
        statements = get_financial_statements(token)
        balance_sheet = statements.get("balance_sheet", {})
        
        # Check if balance sheet balances
        assets_total = balance_sheet.get("assets", {}).get("total", 0)
        liabilities_total = balance_sheet.get("liabilities", {}).get("total", 0)
        equity_total = balance_sheet.get("equity", {}).get("total", 0)
        
        liabilities_and_equity = liabilities_total + equity_total
        
        if abs(assets_total - liabilities_and_equity) < 0.01:
            log_test("TEST 5.2: Financial Statements Balance", True,
                    f"✅ Balance sheet balances! Assets ({assets_total}) = Liabilities + Equity ({liabilities_and_equity})",
                    {
                        "assets_total": assets_total,
                        "liabilities_total": liabilities_total,
                        "equity_total": equity_total,
                        "liabilities_and_equity": liabilities_and_equity
                    })
        else:
            log_test("TEST 5.2: Financial Statements Balance", False,
                    f"❌ Balance sheet does NOT balance! Assets ({assets_total}) ≠ Liabilities + Equity ({liabilities_and_equity})",
                    {
                        "assets_total": assets_total,
                        "liabilities_and_equity": liabilities_and_equity,
                        "difference": abs(assets_total - liabilities_and_equity)
                    })
        
    except Exception as e:
        log_test("TEST 5: Regression Balance Check", False, f"Exception: {str(e)}")
        raise


def test_6_final_cleanup(token: str):
    """TEST 6: Final cleanup - Delete all test records and verify clean state"""
    print("\n" + "="*80)
    print("TEST 6: Final Cleanup")
    print("="*80)
    
    try:
        # Delete any remaining journal entries
        for entry_id in list(created_journal_entries):
            delete_journal_entry(token, entry_id)
            print(f"   Cleaned up journal entry: {entry_id}")
        
        # Delete any remaining revenues
        for revenue_id in list(created_revenues):
            delete_revenue(token, revenue_id)
            print(f"   Cleaned up revenue: {revenue_id}")
        
        log_test("TEST 6.1: Cleanup All Test Records", True,
                f"Cleaned up all test records (journal entries: {len(created_journal_entries)}, revenues: {len(created_revenues)})")
        
        # Verify no is_reversal entries exist
        all_entries = get_journal_entries(token)
        reversal_entries = [e for e in all_entries if e.get("is_reversal") == True]
        
        if len(reversal_entries) == 0:
            log_test("TEST 6.2: Verify Zero Reversal Entries", True,
                    "✅ ZERO is_reversal entries in database (confirmed clean state)",
                    {"reversal_count": 0})
        else:
            log_test("TEST 6.2: Verify Zero Reversal Entries", False,
                    f"❌ Found {len(reversal_entries)} is_reversal entries in database!",
                    {
                        "reversal_count": len(reversal_entries),
                        "reversal_entries": [e.get("id") for e in reversal_entries]
                    })
        
        log_test("TEST 6.3: Final Verification", True,
                "All test records cleaned up. Database should only contain pre-existing deposit and its opening-balance journal entry.")
        
    except Exception as e:
        log_test("TEST 6: Final Cleanup", False, f"Exception: {str(e)}")
        raise


def print_summary():
    """Print test summary"""
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    total_tests = len(test_results)
    passed_tests = sum(1 for r in test_results if r.passed)
    failed_tests = total_tests - passed_tests
    
    print(f"\nTotal Tests: {total_tests}")
    print(f"Passed: {passed_tests} ✅")
    print(f"Failed: {failed_tests} ❌")
    print(f"Success Rate: {(passed_tests/total_tests*100):.1f}%")
    
    if failed_tests > 0:
        print("\n" + "="*80)
        print("FAILED TESTS:")
        print("="*80)
        for result in test_results:
            if not result.passed:
                print(f"\n❌ {result.test_name}")
                print(f"   {result.message}")
                if result.details:
                    print(f"   Details: {json.dumps(result.details, ensure_ascii=False, indent=2)}")
    
    print("\n" + "="*80)
    print("CRITICAL ASSERTIONS:")
    print("="*80)
    
    # Find the core assertion test
    core_test = None
    for result in test_results:
        if "CORE ASSERTION" in result.test_name:
            core_test = result
            break
    
    if core_test:
        if core_test.passed:
            print("\n✅ ✅ ✅ HARD DELETE VERIFIED ✅ ✅ ✅")
            print("Manual journal entry deletion now HARD-DELETES the entry!")
            print("NO reversal entries are created - the entry is completely removed.")
            print("Trial balance correctly returns to prior state.")
        else:
            print("\n❌ ❌ ❌ HARD DELETE NOT WORKING ❌ ❌ ❌")
            print("Manual journal entry deletion is NOT working correctly!")
            print("Either the entry still exists, a reversal was created, or trial balance not restored.")
    
    print("\n" + "="*80)


def main():
    """Main test execution"""
    print("\n" + "="*80)
    print("ARABIC ACCOUNTING SYSTEM - MANUAL JOURNAL ENTRY DELETION TEST")
    print("="*80)
    print("\nVERIFICATION: DELETE /api/journal-entries/{id} now HARD-DELETES")
    print("              the entry instead of creating a reversal (is_reversal)")
    print("\n" + "="*80)
    
    try:
        # Authenticate
        token = authenticate()
        
        # TEST 1: Get chart accounts
        account1, account2 = test_1_get_chart_accounts(token)
        
        # TEST 2: Create manual journal entry
        entry_id, debit_before, credit_before = test_2_create_manual_journal_entry(token, account1, account2)
        
        # TEST 3: Delete manual journal entry (CORE TEST)
        test_3_delete_manual_journal_entry(token, entry_id, debit_before, credit_before)
        
        # TEST 4: Regression - Revenue delete still works
        test_4_regression_revenue_delete(token)
        
        # TEST 5: Regression - Trial balance and statements still balance
        test_5_regression_trial_balance_and_statements(token)
        
        # TEST 6: Final cleanup
        test_6_final_cleanup(token)
        
        # Print summary
        print_summary()
        
        # Exit with appropriate code
        failed_count = sum(1 for r in test_results if not r.passed)
        exit(0 if failed_count == 0 else 1)
        
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {str(e)}")
        print_summary()
        exit(1)


if __name__ == "__main__":
    main()
