# Auth Testing Notes

## Current Product Auth Policy
- نظام المصادقة الحالي JWT مخصص مع FastAPI + MongoDB + bcrypt.
- 2FA ملغاة نهائياً ولا يجب إعادة اختبار أو تفعيل Google Authenticator.
- سياسة القفل المعتمدة من المستخدم: **3 محاولات خاطئة لمدة 3 دقائق**.
- عند اختبار CORS للتطبيق نفسه، استخدم `http://localhost:8001` لأن public preview يمر عبر Cloudflare/ingress وقد يستبدل preflight headers خارج كود التطبيق.

### Local CORS Preflight Check
```bash
curl -i -X OPTIONS http://localhost:8001/api/auth/login \
  -H "Origin: https://scanner-ocr-test.preview.emergentagent.com" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: content-type,authorization"
```

Expected locally:
- `Access-Control-Allow-Origin` = explicit Origin
- `Access-Control-Allow-Credentials: true`
- `Access-Control-Allow-Headers` includes `content-type,authorization`

## Required Login Flow
1. Open `/login`.
2. Login with the official admin account from `/app/memory/test_credentials.md`.
3. Admin should be routed directly to `/secure-admin-control-panel` without any OTP or 2FA step.

## Admin Permissions
- Admin can access `/secure-admin-control-panel`.
- Only hidden super admin `admin` can create/list/edit/disable/enable/delete users and normal admins.
- Normal admins cannot access `/api/admin/users` and must not see Add User or Registered Users sections.
- Hidden super admin `admin` must not be returned in registered users and cannot be edited/deleted from user-management endpoints.
- Admin can update mandatory Arabic `full_name` from the admin password/profile section.
- Admin can change the admin password only after providing the current password.
- Two-factor authentication is permanently disabled; admins cannot start Google Authenticator setup.

## User Permissions
- `enter_deposits`: allows creating deposits.
- `view_reports`: allows reports and statements pages.
- `edit_deposits`: allows deposit update API.
- `manage_reconciliations`: allows creating/editing reconciliation memos.
- `manage_revenues`: allows creating/editing/deleting revenue records; `view_reports` can view revenue reports only.
- `manage_expenses`: allows creating/editing/deleting expense records; `view_reports` can view expense reports only.
- `manage_users`: reserved for user-management permission, while admin role remains required for admin console.

## Revenue Module Permission Expectations
- Admin can create, edit, delete, search, view, and print revenues.
- Data-entry users with `enter_deposits` or `manage_revenues` can create, edit, delete, search, view, and print revenues.
- View-only users with `view_reports` can view/search/print revenue reports but cannot create, edit, or delete.

## Expense Module Permission Expectations
- Admin can create, edit, delete, search, view, and print expenses.
- Data-entry users with `enter_deposits` or `manage_expenses` can create, edit, delete, search, view, and print expenses.
- View-only users with `view_reports` can view/search/print expense reports but cannot create, edit, or delete.

## 2FA Disabled Regression
- `/api/admin/2fa/setup` must return HTTP 410.
- `/api/admin/2fa/verify` must return HTTP 410.
- No account should have `totp_enabled=true`, `totp_secret`, or `totp_pending_secret` in MongoDB.

## Organization Login Isolation
- Login must include `organization_id` selected by the user before entering credentials.
- Correct credentials with the wrong organization must fail.
- Admin users are scoped to one organization.
- Existing operational data is migrated to `social-solidarity`.
- Collections that store operational data must be filtered by authenticated user's `organization_id`.

## Full Name and Audit Log
- Creating a user requires `full_name` in Arabic.
- Updating admin profile requires `full_name` in Arabic.
- Audit logs must include `actor_full_name` and `arabic_description`.
- Audit log UI must display the Arabic actor name and Arabic detailed description.

## Organization API Checks
```bash
curl -X POST "$REACT_APP_BACKEND_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin_takaful","password":"Admin@123","organization_id":"social-solidarity"}'

curl -X POST "$REACT_APP_BACKEND_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin_union","password":"Admin@123","organization_id":"general-union"}'
```

## Super Admin Shadowing Regression
```bash
curl -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"Admin@123","organization_id":"general-union"}'

curl -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"Admin@123","organization_id":"social-solidarity"}'
```

Expected:
- Username `admin` must authenticate the hidden `super_admin` for both organizations.
- The response must include a token and must not request OTP.
- Any older tenant-scoped `admin` record must not shadow the hidden `super_admin` account.
