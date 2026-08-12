#!/usr/bin/env python3
"""
Backend API Test Suite for Revenues Feature
Tests the electronic payment (payment_order) feature with optional payment_order_number
"""

import requests
import json
from datetime import date, timedelta
from typing import List, Dict, Optional

# Configuration
BACKEND_URL = "https://invoke-app.preview.emergentagent.com/api"
AUTH_CREDENTIALS = {
    "username": "admin",
    "password": "Admin@123",
    "organization_id": "social-solidarity"
}

# Test data tracking for cleanup
created_revenue_ids: List[str] = []
test_results: List[Dict] = []


def log_test(test_name: str, passed: bool, details: str = ""):
    """Log test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status}: {test_name}")
    if details:
        print(f"   Details: {details}")
    test_results.append({
        "test": test_name,
        "passed": passed,
        "details": details
    })


def authenticate() -> str:
    """Authenticate and return Bearer token"""
    print("\n=== AUTHENTICATION ===")
    response = requests.post(
        f"{BACKEND_URL}/auth/login",
        json=AUTH_CREDENTIALS,
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code != 200:
        log_test("Authentication", False, f"HTTP {response.status_code}: {response.text}")
        raise Exception(f"Authentication failed: {response.status_code}")
    
    data = response.json()
    token = data.get("token")
    if not token:
        log_test("Authentication", False, "No token in response")
        raise Exception("No token received")
    
    log_test("Authentication", True, f"Token received for user: {data.get('user', {}).get('username')}")
    return token


def create_revenue(token: str, payload: dict) -> Optional[dict]:
    """Create a revenue and return the response"""
    response = requests.post(
        f"{BACKEND_URL}/revenues",
        json=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    )
    
    if response.status_code == 200:
        revenue = response.json()
        created_revenue_ids.append(revenue["id"])
        return revenue
    
    return None


def get_journal_entries(token: str, source_type: str = None, source_id: str = None) -> List[dict]:
    """Get journal entries"""
    params = {}
    if source_type:
        params["source_type"] = source_type
    if source_id:
        params["source_id"] = source_id
    
    response = requests.get(
        f"{BACKEND_URL}/journal-entries",
        params=params,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if response.status_code == 200:
        return response.json()
    return []


def delete_revenue(token: str, revenue_id: str) -> bool:
    """Delete a revenue"""
    response = requests.delete(
        f"{BACKEND_URL}/revenues/{revenue_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    return response.status_code == 200


def cleanup_test_data(token: str):
    """Delete all created test revenues"""
    print("\n=== CLEANUP ===")
    deleted_count = 0
    failed_count = 0
    
    for revenue_id in created_revenue_ids:
        if delete_revenue(token, revenue_id):
            deleted_count += 1
            print(f"✅ Deleted revenue: {revenue_id}")
        else:
            failed_count += 1
            print(f"❌ Failed to delete revenue: {revenue_id}")
    
    print(f"\nCleanup Summary: {deleted_count} deleted, {failed_count} failed")
    return deleted_count, failed_count


def test_payment_order_with_null_number(token: str):
    """Test 1: Create revenue with payment_order and null payment_order_number (bank-statement mode)"""
    print("\n=== TEST 1: Payment Order with NULL payment_order_number ===")
    
    payload = {
        "receipt_number": "778001",
        "amount": 5000.00,
        "collection_method": "payment_order",
        "payment_order_number": None,
        "bank_id": "industrial-development",
        "dated": str(date.today()),
        "value": "إيراد اختبار - دفع إلكتروني بدون رقم",
        "issued_at": str(date.today()),
        "responsible_employee": "يوسف عبدالغني",
        "bank_collection_status": "under_collection"
    }
    
    response = requests.post(
        f"{BACKEND_URL}/revenues",
        json=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    )
    
    if response.status_code == 200:
        revenue = response.json()
        created_revenue_ids.append(revenue["id"])
        
        # Verify payment_order_number is null
        if revenue.get("payment_order_number") is None:
            log_test("Payment order with null number - Creation", True, 
                    f"Revenue ID: {revenue['id']}, payment_order_number: null")
            return revenue
        else:
            log_test("Payment order with null number - Creation", False, 
                    f"Expected null but got: {revenue.get('payment_order_number')}")
            return None
    else:
        log_test("Payment order with null number - Creation", False, 
                f"HTTP {response.status_code}: {response.text}")
        return None


def test_payment_order_with_numeric_number(token: str):
    """Test 2: Create revenue with payment_order and numeric payment_order_number"""
    print("\n=== TEST 2: Payment Order with Numeric payment_order_number ===")
    
    payload = {
        "receipt_number": "778002",
        "amount": 7500.00,
        "collection_method": "payment_order",
        "payment_order_number": "778001",
        "bank_id": "industrial-development",
        "dated": str(date.today()),
        "value": "إيراد اختبار - دفع إلكتروني برقم",
        "issued_at": str(date.today()),
        "responsible_employee": "يوسف عبدالغني",
        "bank_collection_status": "under_collection"
    }
    
    response = requests.post(
        f"{BACKEND_URL}/revenues",
        json=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    )
    
    if response.status_code == 200:
        revenue = response.json()
        created_revenue_ids.append(revenue["id"])
        
        # Verify payment_order_number is set
        if revenue.get("payment_order_number") == "778001":
            log_test("Payment order with numeric number - Creation", True, 
                    f"Revenue ID: {revenue['id']}, payment_order_number: 778001")
            return revenue
        else:
            log_test("Payment order with numeric number - Creation", False, 
                    f"Expected '778001' but got: {revenue.get('payment_order_number')}")
            return None
    else:
        log_test("Payment order with numeric number - Creation", False, 
                f"HTTP {response.status_code}: {response.text}")
        return None


def test_duplicate_payment_order_number(token: str):
    """Test 3: Try to create duplicate payment_order_number (should fail with 400)"""
    print("\n=== TEST 3: Duplicate payment_order_number Rejection ===")
    
    payload = {
        "receipt_number": "778003",
        "amount": 3000.00,
        "collection_method": "payment_order",
        "payment_order_number": "778001",  # Same as test 2
        "bank_id": "industrial-development",
        "dated": str(date.today()),
        "value": "إيراد اختبار - محاولة تكرار رقم",
        "issued_at": str(date.today()),
        "responsible_employee": "يوسف عبدالغني",
        "bank_collection_status": "under_collection"
    }
    
    response = requests.post(
        f"{BACKEND_URL}/revenues",
        json=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    )
    
    if response.status_code == 400:
        log_test("Duplicate payment_order_number rejection", True, 
                f"HTTP 400 (expected): {response.json().get('detail', '')}")
        return True
    else:
        log_test("Duplicate payment_order_number rejection", False, 
                f"Expected HTTP 400 but got {response.status_code}")
        # If it was created, track it for cleanup
        if response.status_code == 200:
            revenue = response.json()
            created_revenue_ids.append(revenue["id"])
        return False


def test_journal_entries_for_payment_order(token: str, revenue_id: str, expected_status: str):
    """Test 4: Verify journal entries for payment_order revenues"""
    print(f"\n=== TEST 4: Journal Entries for Revenue {revenue_id} ===")
    
    # Get journal entries for this revenue
    entries = get_journal_entries(token, source_type="revenue", source_id=revenue_id)
    
    if not entries:
        log_test(f"Journal entry exists for {revenue_id}", False, "No journal entries found")
        return False
    
    entry = entries[0]
    lines = entry.get("lines", [])
    
    if len(lines) < 2:
        log_test(f"Journal entry structure for {revenue_id}", False, 
                f"Expected 2 lines but got {len(lines)}")
        return False
    
    # Find debit and credit lines
    debit_line = None
    credit_line = None
    
    for line in lines:
        if line.get("debit", 0) > 0:
            debit_line = line
        if line.get("credit", 0) > 0:
            credit_line = line
    
    # Verify credit account is "إيرادات أوامر الدفع"
    credit_account = credit_line.get("account_name", "") if credit_line else ""
    if credit_account == "إيرادات أوامر الدفع":
        log_test(f"Journal credit account for {revenue_id}", True, 
                f"Credits: {credit_account}")
    else:
        log_test(f"Journal credit account for {revenue_id}", False, 
                f"Expected 'إيرادات أوامر الدفع' but got '{credit_account}'")
        return False
    
    # Verify debit account based on collection status
    debit_account = debit_line.get("account_name", "") if debit_line else ""
    expected_debit = "البنك" if expected_status == "collected" else "شيكات تحت التحصيل"
    
    if debit_account == expected_debit:
        log_test(f"Journal debit account for {revenue_id}", True, 
                f"Debits: {debit_account} (status: {expected_status})")
    else:
        log_test(f"Journal debit account for {revenue_id}", False, 
                f"Expected '{expected_debit}' but got '{debit_account}'")
        return False
    
    return True


def test_regression_cash(token: str):
    """Test 5a: Regression - Cash revenue"""
    print("\n=== TEST 5a: Regression - Cash Revenue ===")
    
    payload = {
        "receipt_number": "778004",
        "amount": 2000.00,
        "collection_method": "cash",
        "supplier_name": "محمد أحمد السيد",
        "bank_id": "industrial-development",
        "dated": str(date.today()),
        "value": "إيراد نقدي اختبار",
        "issued_at": str(date.today()),
        "responsible_employee": "يوسف عبدالغني",
        "bank_collection_status": "under_collection"
    }
    
    revenue = create_revenue(token, payload)
    if revenue:
        log_test("Regression - Cash revenue", True, f"Revenue ID: {revenue['id']}")
        return True
    else:
        log_test("Regression - Cash revenue", False, "Failed to create cash revenue")
        return False


def test_regression_check(token: str):
    """Test 5b: Regression - Check revenue"""
    print("\n=== TEST 5b: Regression - Check Revenue ===")
    
    payload = {
        "receipt_number": "778005",
        "amount": 4500.00,
        "collection_method": "check",
        "check_number": "998877",
        "check_clearing_type": "internal",
        "bank_id": "industrial-development",
        "dated": str(date.today()),
        "value": "إيراد شيك اختبار",
        "issued_at": str(date.today()),
        "responsible_employee": "يوسف عبدالغني",
        "bank_collection_status": "under_collection"
    }
    
    revenue = create_revenue(token, payload)
    if revenue:
        log_test("Regression - Check revenue", True, f"Revenue ID: {revenue['id']}")
        return True
    else:
        log_test("Regression - Check revenue", False, "Failed to create check revenue")
        return False


def test_regression_current_account_interest(token: str):
    """Test 5c: Regression - Current account interest revenue"""
    print("\n=== TEST 5c: Regression - Current Account Interest Revenue ===")
    
    payload = {
        "receipt_number": "778006",
        "amount": 1250.00,
        "collection_method": "current_account_interest",
        "bank_id": "industrial-development",
        "dated": str(date.today()),
        "value": "فوائد حساب جاري اختبار",
        "issued_at": str(date.today()),
        "responsible_employee": "يوسف عبدالغني"
    }
    
    revenue = create_revenue(token, payload)
    if revenue:
        log_test("Regression - Current account interest", True, f"Revenue ID: {revenue['id']}")
        return True
    else:
        log_test("Regression - Current account interest", False, 
                "Failed to create current account interest revenue")
        return False


def test_regression_deposit_maturity(token: str):
    """Test 5d: Regression - Deposit maturity revenue"""
    print("\n=== TEST 5d: Regression - Deposit Maturity Revenue ===")
    
    payload = {
        "receipt_number": "778007",
        "amount": 8900.00,
        "collection_method": "deposit_maturity",
        "bank_id": "industrial-development",
        "dated": str(date.today()),
        "value": "استحقاق وديعة اختبار",
        "issued_at": str(date.today()),
        "responsible_employee": "يوسف عبدالغني"
    }
    
    revenue = create_revenue(token, payload)
    if revenue:
        log_test("Regression - Deposit maturity", True, f"Revenue ID: {revenue['id']}")
        return True
    else:
        log_test("Regression - Deposit maturity", False, 
                "Failed to create deposit maturity revenue")
        return False


def print_summary():
    """Print test summary"""
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for r in test_results if r["passed"])
    failed = sum(1 for r in test_results if not r["passed"])
    total = len(test_results)
    
    print(f"\nTotal Tests: {total}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"Success Rate: {(passed/total*100):.1f}%")
    
    if failed > 0:
        print("\n❌ FAILED TESTS:")
        for result in test_results:
            if not result["passed"]:
                print(f"  - {result['test']}")
                if result["details"]:
                    print(f"    {result['details']}")
    
    print("\n" + "="*70)


def main():
    """Main test execution"""
    print("="*70)
    print("REVENUES API TEST SUITE - Electronic Payment Feature")
    print("="*70)
    
    try:
        # Authenticate
        token = authenticate()
        
        # Test 1: Payment order with null payment_order_number
        revenue1 = test_payment_order_with_null_number(token)
        
        # Test 2: Payment order with numeric payment_order_number
        revenue2 = test_payment_order_with_numeric_number(token)
        
        # Test 3: Duplicate payment_order_number rejection
        test_duplicate_payment_order_number(token)
        
        # Test 4: Verify journal entries
        if revenue1:
            test_journal_entries_for_payment_order(token, revenue1["id"], "under_collection")
        
        if revenue2:
            test_journal_entries_for_payment_order(token, revenue2["id"], "under_collection")
        
        # Test 5: Regression tests
        test_regression_cash(token)
        test_regression_check(token)
        test_regression_current_account_interest(token)
        test_regression_deposit_maturity(token)
        
        # Cleanup
        cleanup_test_data(token)
        
        # Print summary
        print_summary()
        
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
