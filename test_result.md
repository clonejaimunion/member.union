#====================================================================================================
# START - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================

# THIS SECTION CONTAINS CRITICAL TESTING INSTRUCTIONS FOR BOTH AGENTS
# BOTH MAIN_AGENT AND TESTING_AGENT MUST PRESERVE THIS ENTIRE BLOCK

# Communication Protocol:
# If the `testing_agent` is available, main agent should delegate all testing tasks to it.
#
# You have access to a file called `test_result.md`. This file contains the complete testing state
# and history, and is the primary means of communication between main and the testing agent.
#
# Main and testing agents must follow this exact format to maintain testing data. 
# The testing data must be entered in yaml format Below is the data structure:
# 
## user_problem_statement: {problem_statement}
## backend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.py"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## frontend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.js"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## metadata:
##   created_by: "main_agent"
##   version: "1.0"
##   test_sequence: 0
##   run_ui: false
##
## test_plan:
##   current_focus:
##     - "Task name 1"
##     - "Task name 2"
##   stuck_tasks:
##     - "Task name with persistent issues"
##   test_all: false
##   test_priority: "high_first"  # or "sequential" or "stuck_first"
##
## agent_communication:
##     -agent: "main"  # or "testing" or "user"
##     -message: "Communication message between agents"

# Protocol Guidelines for Main agent
#
# 1. Update Test Result File Before Testing:
#    - Main agent must always update the `test_result.md` file before calling the testing agent
#    - Add implementation details to the status_history
#    - Set `needs_retesting` to true for tasks that need testing
#    - Update the `test_plan` section to guide testing priorities
#    - Add a message to `agent_communication` explaining what you've done
#
# 2. Incorporate User Feedback:
#    - When a user provides feedback that something is or isn't working, add this information to the relevant task's status_history
#    - Update the working status based on user feedback
#    - If a user reports an issue with a task that was marked as working, increment the stuck_count
#    - Whenever user reports issue in the app, if we have testing agent and task_result.md file so find the appropriate task for that and append in status_history of that task to contain the user concern and problem as well 
#
# 3. Track Stuck Tasks:
#    - Monitor which tasks have high stuck_count values or where you are fixing same issue again and again, analyze that when you read task_result.md
#    - For persistent issues, use websearch tool to find solutions
#    - Pay special attention to tasks in the stuck_tasks list
#    - When you fix an issue with a stuck task, don't reset the stuck_count until the testing agent confirms it's working
#
# 4. Provide Context to Testing Agent:
#    - When calling the testing agent, provide clear instructions about:
#      - Which tasks need testing (reference the test_plan)
#      - Any authentication details or configuration needed
#      - Specific test scenarios to focus on
#      - Any known issues or edge cases to verify
#
# 5. Call the testing agent with specific instructions referring to test_result.md
#
# IMPORTANT: Main agent must ALWAYS update test_result.md BEFORE calling the testing agent, as it relies on this file to understand what to test next.

#====================================================================================================
# END - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================



#====================================================================================================
# Testing Data - Main Agent and testing sub agent both should log testing data below this section
#====================================================================================================

user_problem_statement: |
  Deposit interest calculation in the Social Solidarity project (بنك التنمية الصناعية) did not match the
  real bank statement. Example deposit: amount 1,000,000, annual rate 20%, accounting start 2026-01-01,
  365-day basis. Bank statement January 2026 interest = 16,986.30, but the app showed 16,986.14.
  Root cause: the app truncated (math.floor) the DAILY interest to 2 decimals BEFORE multiplying by days,
  losing fractions. Fix: compute daily interest at FULL precision (annual/365, no floor) and round only the
  final monthly/period/accrued amount to 2 decimals — exactly like the bank.

backend:
  - task: "Deposit interest calculation matches bank statement (no daily truncation)"
    implemented: true
    working: true
    file: "backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: "NA"
        -agent: "main"
        -comment: |
          Removed math.floor truncation of daily interest in 3 functions:
          calculate_interest_rows (monthly report), calculate_deposit_interest_for_period (period),
          and calculate_daily_interest_amount (used by accrued report). Daily interest is now
          annual_interest / 365 at full precision; only final amounts are rounded to 2 decimals.
          Displayed daily_interest_amount in accrued report is rounded to 2 decimals for display only.
          Manual API check: January 2026 = 16,986.30 (matches bank). Needs testing_agent verification.
        -working: true
        -agent: "testing"
        -comment: |
          ✅ ALL TESTS PASSED - Bug fix verified successfully!
          
          Tested deposit: amount=1,000,000, annual_rate=20%, accounting_start=2026-01-01, maturity=2027-09-19, 365-day basis
          Full-precision daily interest: 200,000 / 365 = 547.9452055...
          
          Test Results:
          1. ✅ Current Year Report (GET /api/banks/industrial-development/reports/current-year):
             - January 2026: 31 days × 547.9452055 = 16,986.30 (MATCHES BANK STATEMENT EXACTLY!)
             - February 2026: 28 days × 547.9452055 = 15,342.47 (correct)
             - HTTP 200, no errors
          
          2. ✅ Accrued Interest Report (GET /api/banks/industrial-development/accrued-interest?year=2026):
             - Daily interest (display): 547.95 (correctly rounded for display)
             - Accrued interest (9 days): 547.9452055 × 9 = 4,931.51 (correct full-precision calculation)
             - HTTP 200, no errors
          
          3. ✅ Previous Year Report (GET /api/banks/industrial-development/reports/previous-year):
             - HTTP 200, no errors (regression test passed)
          
          The fix successfully removed daily truncation. Daily interest is now computed at FULL precision
          and only the FINAL monthly/period/accrued amounts are rounded to 2 decimals - exactly like the bank does.
          This matches the real bank statement perfectly!

metadata:
  created_by: "main_agent"
  version: "1.2"
  test_sequence: 2
  run_ui: false

test_plan:
  current_focus:
    - "Deposit interest calculation matches bank statement (no daily truncation)"
  stuck_tasks: []
  test_all: false
  test_priority: "high_first"

agent_communication:
    -agent: "main"
    -message: |
      Please verify deposit interest calc for bank_id=industrial-development, org=social-solidarity,
      login admin/Admin@123. Endpoints:
      GET /api/banks/industrial-development/reports/current-year  -> January (month_number 1) interest_amount MUST equal 16986.30 (31 days).
      GET /api/banks/industrial-development/accrued-interest?year=2026 -> daily_interest_amount should be 547.95,
      accrued_interest_amount = round(547.9452055 * accrued_days, 2).
      Confirm the numbers reflect full-precision daily interest (annual 200000 / 365) with only final rounding.
      Also confirm no regression: reports endpoints return 200 and stay balanced.
    -agent: "testing"
    -message: |
      ✅ TESTING COMPLETE - ALL TESTS PASSED!
      
      Bug fix verified successfully. The deposit interest calculation now matches the bank statement exactly.
      
      Key Findings:
      - January 2026 interest: 16,986.30 (MATCHES BANK STATEMENT - this was the core bug!)
      - February 2026 interest: 15,342.47 (correct)
      - Daily interest calculation uses full precision (547.9452055) with only final rounding
      - All 3 endpoints tested: current-year, accrued-interest, previous-year - all return HTTP 200
      - No regressions detected
      
      The fix successfully removed the math.floor truncation that was causing the 0.16 EGP discrepancy.
      Daily interest is now computed at full precision (200,000 / 365 = 547.9452055) and only the
      FINAL monthly/period/accrued amounts are rounded to 2 decimals - exactly like the bank does.
      
      Ready for production deployment.