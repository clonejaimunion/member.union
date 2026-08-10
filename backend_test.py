#!/usr/bin/env python3
"""
Final verification test for deposit-interest calculation before Windows update packaging.
Tests the exact requirements from the review request.
"""

import requests
import json
import sys

# Backend URL from frontend/.env
BASE_URL = "https://invoke-app.preview.emergentagent.com/api"

def print_section(title):
    """Print a formatted section header"""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")

def test_auth_login():
    """Test authentication and return Bearer token"""
    print_section("TEST 1: Authentication")
    
    url = f"{BASE_URL}/auth/login"
    payload = {
        "username": "admin",
        "password": "Admin@123",
        "organization_id": "social-solidarity"
    }
    
    print(f"POST {url}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response data: {json.dumps(data, indent=2)}")
            token = data.get('access_token') or data.get('token')
            print(f"✅ Login successful")
            print(f"Token received: {token[:50]}..." if token else "No token")
            return token
        else:
            print(f"❌ Login failed")
            print(f"Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Exception during login: {e}")
        return None

def test_current_year_report(token):
    """Test current year report - CRITICAL: Verify January and total_interest values"""
    print_section("TEST 2: Current Year Report (CRITICAL)")
    
    url = f"{BASE_URL}/banks/industrial-development/reports/current-year"
    headers = {"Authorization": f"Bearer {token}"}
    
    print(f"GET {url}")
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            # Extract critical values
            total_interest = data.get('total_interest')
            rows = data.get('rows', [])
            
            # Find January and February
            january = next((m for m in rows if m.get('month_number') == 1), None)
            february = next((m for m in rows if m.get('month_number') == 2), None)
            
            print(f"\n📊 CRITICAL VALUES:")
            print(f"   total_interest: {total_interest}")
            print(f"   Number of rows in response: {len(rows)}")
            
            if january:
                jan_interest = january.get('interest_amount')
                jan_days = january.get('days')
                print(f"   January (month_number 1):")
                print(f"      - days: {jan_days}")
                print(f"      - interest_amount: {jan_interest}")
                
                # CRITICAL CHECK
                if jan_interest == 16986.30:
                    print(f"      ✅ MATCHES EXPECTED: 16986.30")
                else:
                    print(f"      ❌ MISMATCH! Expected: 16986.30, Got: {jan_interest}")
            else:
                print(f"   ❌ January data not found!")
            
            if february:
                feb_interest = february.get('interest_amount')
                feb_days = february.get('days')
                print(f"   February (month_number 2):")
                print(f"      - days: {feb_days}")
                print(f"      - interest_amount: {feb_interest}")
                
                # CRITICAL CHECK
                if feb_interest == 15342.47:
                    print(f"      ✅ MATCHES EXPECTED: 15342.47")
                else:
                    print(f"      ❌ MISMATCH! Expected: 15342.47, Got: {feb_interest}")
            else:
                print(f"   ❌ February data not found!")
            
            # CRITICAL CHECK: total_interest must be exactly 200000.0
            if total_interest == 200000.0:
                print(f"\n   ✅ total_interest MATCHES EXPECTED: 200000.0 (exact)")
            else:
                print(f"\n   ❌ total_interest MISMATCH! Expected: 200000.0, Got: {total_interest}")
            
            print(f"\n✅ HTTP 200 - Endpoint working")
            return True
        else:
            print(f"❌ Request failed")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

def test_accrued_interest(token):
    """Test accrued interest report - Verify daily_interest_amount"""
    print_section("TEST 3: Accrued Interest Report")
    
    url = f"{BASE_URL}/banks/industrial-development/accrued-interest?year=2026"
    headers = {"Authorization": f"Bearer {token}"}
    
    print(f"GET {url}")
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            # Extract values from response
            rows = data.get('rows', [])
            
            # Get daily_interest_amount from first row (if exists)
            daily_interest = None
            accrued_interest = None
            accrued_days = None
            
            if rows and len(rows) > 0:
                first_row = rows[0]
                daily_interest = first_row.get('daily_interest_amount')
                accrued_interest = first_row.get('accrued_interest_amount')
                accrued_days = first_row.get('accrued_days')
            
            print(f"\n📊 VALUES:")
            print(f"   daily_interest_amount: {daily_interest}")
            print(f"   accrued_days: {accrued_days}")
            print(f"   accrued_interest_amount: {accrued_interest}")
            
            # CRITICAL CHECK
            if daily_interest == 547.95:
                print(f"\n   ✅ daily_interest_amount MATCHES EXPECTED: 547.95")
            else:
                print(f"\n   ❌ daily_interest_amount MISMATCH! Expected: 547.95, Got: {daily_interest}")
            
            print(f"\n✅ HTTP 200 - Endpoint working")
            return True
        else:
            print(f"❌ Request failed")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

def test_previous_year_report(token):
    """Test previous year report - Regression test (should not crash)"""
    print_section("TEST 4: Previous Year Report (Regression)")
    
    url = f"{BASE_URL}/banks/industrial-development/reports/previous-year"
    headers = {"Authorization": f"Bearer {token}"}
    
    print(f"GET {url}")
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print(f"✅ HTTP 200 - No crash, endpoint working")
            return True
        else:
            print(f"❌ Request failed")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

def test_auth_me(token):
    """Test /auth/me endpoint - Basic regression test"""
    print_section("TEST 5: Auth Me (Regression)")
    
    url = f"{BASE_URL}/auth/me"
    headers = {"Authorization": f"Bearer {token}"}
    
    print(f"GET {url}")
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            username = data.get('username')
            print(f"✅ HTTP 200 - Auth working, user: {username}")
            return True
        else:
            print(f"❌ Request failed")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

def main():
    """Run all verification tests"""
    print("\n" + "="*80)
    print("  FINAL VERIFICATION - Deposit Interest Calculation")
    print("  Windows Update Package Pre-Deployment Check")
    print("="*80)
    
    # Step 1: Authenticate
    token = test_auth_login()
    if not token:
        print("\n❌ VERIFICATION FAILED: Cannot authenticate")
        sys.exit(1)
    
    # Step 2: Run all verification tests
    results = {
        "current_year_report": test_current_year_report(token),
        "accrued_interest": test_accrued_interest(token),
        "previous_year_report": test_previous_year_report(token),
        "auth_me": test_auth_me(token)
    }
    
    # Final Summary
    print_section("FINAL SUMMARY")
    
    all_passed = all(results.values())
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print("\n" + "="*80)
    if all_passed:
        print("  ✅ ALL VERIFICATION TESTS PASSED")
        print("  Ready for Windows update packaging")
    else:
        print("  ❌ VERIFICATION FAILED")
        print("  DO NOT package for Windows update")
    print("="*80 + "\n")
    
    sys.exit(0 if all_passed else 1)

if __name__ == "__main__":
    main()
