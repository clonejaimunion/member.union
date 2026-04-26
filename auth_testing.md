# Auth Testing Notes

## Required Login Flow
1. Open `/login`.
2. Login with the official admin account from `/app/memory/test_credentials.md`.
3. Admin should be routed to `/secure-admin-control-panel` if 2FA setup is not enabled.

## Admin Permissions
- Admin can access `/secure-admin-control-panel`.
- Admin can create users with scoped permissions.
- Admin can change the admin password only after providing the current password.
- Admin can start Google Authenticator setup and receive QR/manual secret.

## User Permissions
- `enter_deposits`: allows creating deposits.
- `view_reports`: allows reports and statements pages.
- `edit_deposits`: allows deposit update API.
- `manage_users`: reserved for user-management permission, while admin role remains required for admin console.

## 2FA Testing Safety
- Test `/api/admin/2fa/setup` for QR/manual secret.
- Avoid calling `/api/admin/2fa/verify` in automated tests unless the generated TOTP secret is recorded and a recovery plan exists.
