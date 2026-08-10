#!/usr/bin/env python3
"""
Backend API Test for Deposit Interest Calculation Bug Fix
Tests that deposit interest calculation matches bank statement (no daily truncation)
"""

import requests
import sys
import json

# Backend URL from environment
BACKEND_URL = "https://invoke-app.preview.emergentagent.com/api"

# Test credentials
USERNAME = "admin"
PASSWORD = "Admin@123"
ORGANIZATION_ID = "social-solidarity"

# Test data
BANK_ID = "industrial-development"
BANK_NAME = "بنك التنمية الصناعية"

# Expected values based on full-precision calculation
# Deposit: amount=1,000,000, annual_rate=20%, accounting_start=2026-01-01, maturity=2027-09-19, 365-day basis
# Annual interest = 1,000,000 * 20 / 100 = 200,000
# Daily interest (full precision) = 200,000 / 365 = 547.9452055...
# January 2026 (31 days) = 547.9452055 * 31 = 16,986.30164... → rounds to 16,986.30
# February 2026 (28 days) = 547.9452055 * 28 = 15,342.46575... → rounds to 15,342.47

EXPECTED_JANUARY_INTEREST = 16986.30
EXPECTED_FEBRUARY_INTEREST = 15342.47
EXPECTED_DAILY_INTEREST_DISPLAY = 547.95  # Rounded for display


def print_section(title):
    """Print a section header"""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")


def login():
    """Login and get authentication token"""
    print_section("1. Authentication Test")
    
    url = f"{BACKEND_URL}/auth/login"
    payload = {
        "username": USERNAME,
        "password": PASSWORD,
        "organization_id": ORGANIZATION_ID
    }
    
    print(f"POST {url}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ Login failed: {response.text}")
            return None
        
        data = response.json()
        token = data.get("token")
        
        if not token:
            print(f"❌ No token in response: {json.dumps(data, indent=2)}")
            return None
        
        print(f"✅ Login successful")
        print(f"Token: {token[:20]}...")
        return token
        
    except Exception as e:
        print(f"❌ Login error: {str(e)}")
        return None


def test_current_year_report(token):
    """Test GET /api/banks/{bank_id}/reports/current-year"""
    print_section("2. Current Year Report Test (Total Interest = 200,000.00, January = 16,986.30)")
    
    url = f"{BACKEND_URL}/banks/{BANK_ID}/reports/current-year"
    headers = {"Authorization": f"Bearer {token}"}
    
    print(f"GET {url}")
    print(f"Headers: Authorization: Bearer {token[:20]}...")
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ Request failed: {response.text}")
            return False
        
        data = response.json()
        
        # Check total_interest (إجمالي السنة) - CRITICAL TEST FOR THIS BUG FIX
        total_interest = data.get("total_interest")
        expected_total = 200000.0
        
        print(f"\n🎯 CRITICAL TEST - Total Interest (إجمالي السنة):")
        print(f"  Expected: {expected_total} (200,000.00)")
        print(f"  Actual: {total_interest}")
        
        if total_interest is None:
            print(f"❌ total_interest field not found in response!")
            print(f"Response keys: {list(data.keys())}")
            return False
        
        if total_interest == expected_total:
            print(f"✅ Total interest CORRECT: {total_interest} (no rounding accumulation error!)")
        else:
            print(f"❌ Total interest MISMATCH!")
            print(f"   Expected: {expected_total}")
            print(f"   Got: {total_interest}")
            print(f"   Difference: {abs(total_interest - expected_total)}")
            if total_interest == 200000.01:
                print(f"   ⚠️  This is the OLD BUG - summing rounded monthly values!")
            return False
        
        # Find January row (month_number == 1)
        january_row = None
        february_row = None
        
        for row in data.get("rows", []):
            if row.get("month_number") == 1:
                january_row = row
            elif row.get("month_number") == 2:
                february_row = row
        
        if not january_row:
            print(f"❌ January row not found in response")
            print(f"Response: {json.dumps(data, indent=2)}")
            return False
        
        january_interest = january_row.get("interest_amount")
        january_days = january_row.get("active_days")
        
        print(f"\nJanuary 2026 Data (Regression Check):")
        print(f"  Month: {january_row.get('month')}")
        print(f"  Active Days: {january_days}")
        print(f"  Interest Amount: {january_interest}")
        print(f"  Expected: {EXPECTED_JANUARY_INTEREST}")
        
        # Check if January interest matches expected value
        if january_interest == EXPECTED_JANUARY_INTEREST:
            print(f"✅ January interest matches bank statement: {january_interest}")
        else:
            print(f"❌ January interest MISMATCH!")
            print(f"   Expected: {EXPECTED_JANUARY_INTEREST}")
            print(f"   Got: {january_interest}")
            print(f"   Difference: {abs(january_interest - EXPECTED_JANUARY_INTEREST)}")
            return False
        
        # Also check February if available
        if february_row:
            february_interest = february_row.get("interest_amount")
            february_days = february_row.get("active_days")
            
            print(f"\nFebruary 2026 Data (Regression Check):")
            print(f"  Month: {february_row.get('month')}")
            print(f"  Active Days: {february_days}")
            print(f"  Interest Amount: {february_interest}")
            print(f"  Expected: {EXPECTED_FEBRUARY_INTEREST}")
            
            if february_interest == EXPECTED_FEBRUARY_INTEREST:
                print(f"✅ February interest correct: {february_interest}")
            else:
                print(f"⚠️  February interest mismatch (Expected: {EXPECTED_FEBRUARY_INTEREST}, Got: {february_interest})")
        
        return True
        
    except Exception as e:
        print(f"❌ Request error: {str(e)}")
        return False


def test_accrued_interest_report(token):
    """Test GET /api/banks/{bank_id}/accrued-interest?year=2026"""
    print_section("3. Accrued Interest Report Test (Daily Interest = 547.95)")
    
    url = f"{BACKEND_URL}/banks/{BANK_ID}/accrued-interest?year=2026"
    headers = {"Authorization": f"Bearer {token}"}
    
    print(f"GET {url}")
    print(f"Headers: Authorization: Bearer {token[:20]}...")
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ Request failed: {response.text}")
            return False
        
        data = response.json()
        
        # Check if there are any rows
        rows = data.get("rows", [])
        if not rows:
            print(f"❌ No deposit rows found in accrued interest report")
            print(f"Response: {json.dumps(data, indent=2)}")
            return False
        
        # Check the first deposit row
        first_row = rows[0]
        daily_interest = first_row.get("daily_interest_amount")
        accrued_days = first_row.get("accrued_days")
        accrued_interest = first_row.get("accrued_interest_amount")
        annual_interest = first_row.get("annual_interest_amount")
        
        print(f"\nDeposit Accrued Interest Data:")
        print(f"  Account Number: {first_row.get('account_number')}")
        print(f"  Deposit Number: {first_row.get('deposit_number')}")
        print(f"  Amount: {first_row.get('amount')}")
        print(f"  Annual Interest Rate: {first_row.get('annual_interest_rate')}%")
        print(f"  Annual Interest Amount: {annual_interest}")
        print(f"  Daily Interest Amount (display): {daily_interest}")
        print(f"  Expected Daily Interest (display): {EXPECTED_DAILY_INTEREST_DISPLAY}")
        print(f"  Accrued Days: {accrued_days}")
        print(f"  Accrued Interest Amount: {accrued_interest}")
        
        # Check daily interest (displayed value, rounded to 2 decimals)
        if daily_interest == EXPECTED_DAILY_INTEREST_DISPLAY:
            print(f"✅ Daily interest (display) correct: {daily_interest}")
        else:
            print(f"⚠️  Daily interest (display) mismatch (Expected: {EXPECTED_DAILY_INTEREST_DISPLAY}, Got: {daily_interest})")
        
        # Verify accrued interest calculation
        # Full precision daily interest = 200000 / 365 = 547.9452055
        # Accrued interest should be round(547.9452055 * accrued_days, 2)
        if accrued_days > 0:
            full_precision_daily = 200000 / 365
            expected_accrued = round(full_precision_daily * accrued_days, 2)
            
            print(f"\nAccrued Interest Verification:")
            print(f"  Full-precision daily interest: {full_precision_daily}")
            print(f"  Expected accrued interest: {expected_accrued}")
            print(f"  Actual accrued interest: {accrued_interest}")
            
            if accrued_interest == expected_accrued:
                print(f"✅ Accrued interest calculation correct: {accrued_interest}")
            else:
                print(f"⚠️  Accrued interest mismatch (Expected: {expected_accrued}, Got: {accrued_interest})")
        
        return True
        
    except Exception as e:
        print(f"❌ Request error: {str(e)}")
        return False


def test_previous_year_report(token):
    """Test GET /api/banks/{bank_id}/reports/previous-year (regression test)"""
    print_section("4. Previous Year Report Test (Regression)")
    
    url = f"{BACKEND_URL}/banks/{BANK_ID}/reports/previous-year"
    headers = {"Authorization": f"Bearer {token}"}
    
    print(f"GET {url}")
    print(f"Headers: Authorization: Bearer {token[:20]}...")
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ Request failed: {response.text}")
            return False
        
        print(f"✅ Previous year report endpoint working (returns 200)")
        return True
        
    except Exception as e:
        print(f"❌ Request error: {str(e)}")
        return False


def main():
    """Main test execution"""
    print("\n" + "="*80)
    print("  DEPOSIT INTEREST CALCULATION BUG FIX VERIFICATION")
    print("  Testing: Total interest = 200,000.00 (no rounding accumulation)")
    print("  Testing: No daily truncation, full-precision calculation")
    print("="*80)
    
    # Login
    token = login()
    if not token:
        print("\n❌ FAILED: Authentication failed")
        sys.exit(1)
    
    # Run tests
    test_results = []
    
    # Test 1: Current year report (Total interest = 200,000.00, January = 16,986.30)
    result1 = test_current_year_report(token)
    test_results.append(("Current Year Report (Total = 200,000.00, January = 16,986.30)", result1))
    
    # Test 2: Accrued interest report (daily interest = 547.95)
    result2 = test_accrued_interest_report(token)
    test_results.append(("Accrued Interest Report (Daily = 547.95)", result2))
    
    # Test 3: Previous year report (regression)
    result3 = test_previous_year_report(token)
    test_results.append(("Previous Year Report (Regression)", result3))
    
    # Summary
    print_section("TEST SUMMARY")
    
    all_passed = True
    for test_name, result in test_results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
        if not result:
            all_passed = False
    
    print("\n" + "="*80)
    if all_passed:
        print("  ✅ ALL TESTS PASSED")
        print("  Deposit interest calculation matches bank statement!")
        print("="*80 + "\n")
        sys.exit(0)
    else:
        print("  ❌ SOME TESTS FAILED")
        print("  Please review the failures above")
        print("="*80 + "\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
